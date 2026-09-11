#!/usr/bin/env bash
# =============================================================================
# install_unix.sh — Installateur generator-assets pour Linux x64 et macOS.
#
# Fait la même chose que scripts/install_windows.ps1 :
#   1. Preflight : outils (curl/tar/unzip/python3), uv (auto-install), espace disque.
#   2. uv sync (dépendances Python du dépôt).
#   3. Moteurs C++ téléchargés depuis les RELEASES OFFICIELLES upstream
#      (versions épinglées lues dans scripts/engines_manifest.json, clé de
#      plateforme 'linux', 'macos-arm64' ou 'macos-x64') + FFmpeg standard
#      (BtbN Linux / Homebrew macOS). Idempotent : un moteur déjà présent
#      est ignoré sauf --force.
#   4. Packs de modèles via scripts/download_models.py (défaut base,onnx,upscalers).
#   5. Vérification finale : uv run python main.py --check.
#
# Linux utilise le backend Vulkan (pilotes requis : Mesa/RADV pour AMD) ;
# macOS utilise Metal natif (aucun Vulkan requis). trellis.cpp n'est pas
# publié pour macOS : il est ignoré avec un message (build source possible).
#
# Les exécutables sont installés sous --prefix (défaut
# $HOME/.local/share/generator-assets), liés symboliquement dans
# $HOME/.local/bin, et les variables d'environnement attendues par
# core/config.py (SD_CLI_PATH, LLAMA_CLI_PATH, AUDIOCPP_PATH,
# TRELLIS_CLI_PATH, FFMPEG_PATH, MODEL_DIR) sont écrites dans
# <prefix>/env.sh (à sourcer dans ~/.bashrc ou ~/.zshrc).
#
# Usage :
#   bash scripts/install_unix.sh [--prefix DIR] [--engines "a,b"] [--packs "p1,p2"]
#        [--skip-models] [--skip-uv-sync] [--skip-check] [--force] [--dry-run]
#
# Variable de test : GENERATOR_ASSETS_FORCE_OS=linux|macos-arm64|macos-x64
# force la plateforme cible (utile pour --dry-run depuis un autre OS).
# =============================================================================
set -euo pipefail

PREFIX="${HOME}/.local/share/generator-assets"
ENGINES="sd-cli,llama.cpp,audio.cpp,trellis.cpp,ffmpeg"
PACKS="base,onnx,upscalers"
SKIP_MODELS=0 ; SKIP_UV_SYNC=0 ; SKIP_CHECK=0 ; FORCE=0 ; DRYRUN=0

usage() { sed -n '2,40p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//' ; }

while [ $# -gt 0 ] ; do
    case "$1" in
        --prefix)        PREFIX="$2" ; shift 2 ;;
        --engines)       ENGINES="$2" ; shift 2 ;;
        --packs)         PACKS="$2" ; shift 2 ;;
        --skip-models)   SKIP_MODELS=1 ; shift ;;
        --skip-uv-sync)  SKIP_UV_SYNC=1 ; shift ;;
        --skip-check)    SKIP_CHECK=1 ; shift ;;
        --force)         FORCE=1 ; shift ;;
        --dry-run)       DRYRUN=1 ; shift ;;
        -h|--help)       usage ; exit 0 ;;
        *) echo "Option inconnue : $1 (voir --help)" ; exit 1 ;;
    esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="$REPO_ROOT/scripts/engines_manifest.json"

# ---------------------------------------------------------------- affichage

if [ -t 1 ] ; then
    C_ETAPE=$'\033[35m' ; C_OK=$'\033[32m' ; C_INFO=$'\033[36m' ; C_ALERTE=$'\033[33m' ; C_FIN=$'\033[0m'
else
    C_ETAPE="" ; C_OK="" ; C_INFO="" ; C_ALERTE="" ; C_FIN=""
fi
etape()   { printf '\n==> %s\n' "$1" ; }
ok()      { printf '  %s[ok]%s %s\n' "$C_OK" "$C_FIN" "$1" ; }
info()    { printf '  %s..  %s%s\n' "$C_INFO" "$C_FIN" "$1" ; }
alerte()  { printf '  %s[!] %s%s\n' "$C_ALERTE" "$C_FIN" "$1" ; }

# ---------------------------------------------------------------- plateforme

PLATEFORME="${GENERATOR_ASSETS_FORCE_OS:-}"
if [ -z "$PLATEFORME" ] ; then
    UNAME_S="$(uname -s)"
    case "$UNAME_S" in
        MINGW*|MSYS*|CYGWIN*)
            echo "Windows detecte : utilisez scripts/install_windows.ps1 (PowerShell)." ; exit 1 ;;
        Linux*)  PLATEFORME="linux" ;;
        Darwin*)
            case "$(uname -m)" in
                arm64)  PLATEFORME="macos-arm64" ;;
                x86_64) PLATEFORME="macos-x64" ;;
                *) echo "Architecture macOS inconnue : $(uname -m)" ; exit 1 ;;
            esac ;;
        *) echo "OS non supporte : $UNAME_S" ; exit 1 ;;
    esac
fi

# ---------------------------------------------------------------- prérequis outils

PY_CMD=""
for c in python3 python ; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c "import json" >/dev/null 2>&1 ; then
        PY_CMD="$c" ; break
    fi
done
if [ -z "$PY_CMD" ] && command -v uv >/dev/null 2>&1 ; then PY_CMD="uv run python" ; fi
if [ -z "$PY_CMD" ] ; then
    echo "python3 introuvable : installez python3 (ou uv) puis relancez." ; exit 1
fi

manque=""
for outil in curl tar unzip ; do
    command -v "$outil" >/dev/null 2>&1 || manque="$manque $outil"
done
if [ -n "$manque" ] ; then
    echo "Outils manquants :$manque"
    echo "  Linux (Debian/Ubuntu) : sudo apt install curl tar unzip"
    echo "  macOS : fournis avec le systeme (xcode-select --install au besoin)"
    exit 1
fi

if ! command -v uv >/dev/null 2>&1 ; then
    alerte "uv introuvable -> installation automatique..."
    if [ "$DRYRUN" -eq 1 ] ; then
        info "DRYRUN : curl -LsSf https://astral.sh/uv/install.sh | sh"
    else
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
        command -v uv >/dev/null 2>&1 || {
            echo "uv non disponible apres installation : ouvrez un nouveau terminal et relancez." ; exit 1 ;
        }
    fi
fi

mkdir -p "$PREFIX"
LIBRE_GO="$(df -PG "$PREFIX" 2>/dev/null | awk 'NR==2 {gsub(/G/,"",$4) ; print $4}' || true)"
LIBRE_GO="${LIBRE_GO:-?}"
if [ "$LIBRE_GO" != "?" ] && [ "$LIBRE_GO" -lt 20 ] 2>/dev/null ; then
    alerte "Seulement ${LIBRE_GO} Go libres sur $PREFIX (~20 Go conseilles moteurs + pack base)."
else
    ok "Espace disque suffisant sur $PREFIX (${LIBRE_GO} Go libres)"
fi

printf '\n========================================================\n'
printf ' generator-assets - INSTALLATION UNIX (%s)\n' "$PLATEFORME"
printf '========================================================\n'
[ "$DRYRUN" -eq 1 ] && alerte "Mode DRYRUN : aucun telechargement ni installation reelle."

# ---------------------------------------------------------------- lecture manifeste

# fiche_moteur <moteur> : charge la fiche plateforme dans FICHE_MOTEUR (lignes CLE=VALEUR).
# Code retour 3 = plateforme non publiee en amont ; affiche __INCONNU__ si moteur inconnu.
fiche_moteur() { # $1 = moteur
    $PY_CMD - "$MANIFEST" "$1" "$PLATEFORME" <<'PYEOF'
import json, sys
m = json.load(open(sys.argv[1], encoding="utf-8"))
eng = (m.get("moteurs") or {}).get(sys.argv[2])
if not eng:
    print("__INCONNU__")
    sys.exit(0)
plat = (eng.get("plateformes") or {}).get(sys.argv[3])
if not plat:
    sys.exit(3)
print("repo=%s" % eng.get("repo", ""))
for k, v in plat.items():
    if isinstance(v, (str, int)):
        print("%s=%s" % (k, v))
PYEOF
}

# resoudre_url : renseigne ASSET_URL / ASSET_LABEL depuis la fiche F_* courante.
resoudre_url() {
    if [ -n "${F_URL:-}" ] ; then
        ASSET_URL="$F_URL" ; ASSET_LABEL="$(basename "$F_URL")" ; return 0
    fi
    if [ -n "${F_EPINGLE:-}" ] && [ -n "${F_ASSET:-}" ] ; then
        ASSET_URL="https://github.com/${F_REPO}/releases/download/${F_EPINGLE}/${F_ASSET}"
        ASSET_LABEL="${F_ASSET} (epingle ${F_EPINGLE})" ; return 0
    fi
    local api_json
    if [ "${F_RELEASE:-}" = "latest" ] ; then
        info "Recherche de la derniere release ${F_REPO}..."
        api_json="https://api.github.com/repos/${F_REPO}/releases/latest"
    elif [ -n "${F_SCAN_RELEASES:-}" ] ; then
        info "Scan des ${F_SCAN_RELEASES} dernieres releases ${F_REPO}..."
        api_json="https://api.github.com/repos/${F_REPO}/releases?per_page=${F_SCAN_RELEASES}"
    else
        echo "Fiche plateforme incomplete dans engines_manifest.json (ni url, ni epingle, ni release/scan_releases)" ; return 1
    fi
    local ligne
    # Le script python passe par -c (et non stdin) pour laisser le pipe alimenter json.load.
    ligne="$(curl -sS -H "User-Agent: generator-assets-installer/1.0" "$api_json" | $PY_CMD -c '
import fnmatch, json, sys
pat = sys.argv[1]
data = json.load(sys.stdin)
for rel in (data if isinstance(data, list) else [data]):
    for a in rel.get("assets", []):
        if fnmatch.fnmatch(a.get("name", ""), pat):
            print("%s\t%s (%s)" % (a["browser_download_url"], a["name"], rel.get("tag_name", "")))
            sys.exit(0)
sys.exit(4)
' "${F_ASSET_PATTERN:-}" 2>/dev/null)" || { echo "Aucun asset '${F_ASSET_PATTERN:-}' trouve pour ${F_REPO} (API GitHub injoignable ou rate-limit ?)" ; return 1 ; }
    ASSET_URL="$(printf '%s' "$ligne" | cut -f1)"
    ASSET_LABEL="$(printf '%s' "$ligne" | cut -f2)"
}

# Variables d'environnement attendues par core/config.py, par moteur.
var_env_moteur() {
    case "$1" in
        sd-cli)     echo "SD_CLI_PATH" ;;
        llama.cpp)  echo "LLAMA_CLI_PATH" ;;
        audio.cpp)  echo "AUDIOCPP_PATH" ;;
        trellis.cpp) echo "TRELLIS_CLI_PATH" ;;
        ffmpeg)     echo "FFMPEG_PATH" ;;
        *)          echo "" ;;
    esac
}

ENV_SH="${PREFIX}/env.sh"
: > "$ENV_SH"

# ---------------------------------------------------------------- installation moteurs

TMP_BASE="$(mktemp -d)"
trap 'rm -rf "$TMP_BASE"' EXIT

installer_moteur() { # $1 = moteur
    local nom="$1"
    etape "Moteur $nom"

    local rc=0 FICHE
    FICHE="$(fiche_moteur "$nom")" || rc=$?
    if [ "$rc" -eq 3 ] ; then
        alerte "Moteur $nom : pas de binaire publie en amont pour $PLATEFORME -> ignore"
        [ "$nom" = "trellis.cpp" ] && info "Workflow mesh_ia sous macOS : compiler depuis https://github.com/pwilkin/trellis.cpp"
        return 0
    fi
    if [ "$rc" -ne 0 ] || [ "$FICHE" = "__INCONNU__" ] ; then
        echo "Moteur '$nom' inconnu dans engines_manifest.json" ; return 1
    fi

    unset F_REPO F_URL F_EPINGLE F_ASSET F_RELEASE F_SCAN_RELEASES F_ASSET_PATTERN F_SOUS_DOSSIER F_EXE F_GESTIONNAIRE F_PAQUET 2>/dev/null || true
    local k v k_maj
    while IFS='=' read -r k v ; do
        # tr : bash 3.2 de macOS n'a pas ${k^^} ; suppression du \r final
        # (python de Windows traduit \n en \r\n sur stdout).
        k_maj="$(printf '%s' "$k" | tr '[:lower:]' '[:upper:]')"
        v="${v%$'\r'}"
        [ -n "$k_maj" ] && printf -v "F_$k_maj" '%s' "$v"
    done <<< "$FICHE"

    # Cas particulier Homebrew (ffmpeg macOS) : rien a telecharger ni extraire.
    if [ "${F_GESTIONNAIRE:-}" = "brew" ] ; then
        if ! command -v brew >/dev/null 2>&1 ; then
            alerte "Homebrew requis pour $nom : https://brew.sh -> ignore" ; return 0
        fi
        if [ "$DRYRUN" -eq 1 ] ; then
            info "DRYRUN : brew install ${F_PAQUET}" ; return 0
        fi
        if brew list --formula "${F_PAQUET}" >/dev/null 2>&1 ; then
            ok "brew : ${F_PAQUET} deja installe"
        else
            info "brew install ${F_PAQUET}..." ; brew install "${F_PAQUET}"
        fi
        local brew_exe
        brew_exe="$(brew --prefix)/bin/${F_EXE}"
        [ -f "$brew_exe" ] && env_enregistrer "$nom" "$brew_exe"
        return 0
    fi

    local dir="${PREFIX}/${F_SOUS_DOSSIER:-}"
    local exe="${dir}/${F_EXE}"

    if [ -f "$exe" ] && [ "$FORCE" -eq 0 ] ; then
        ok "$exe deja present -> ignore (--force pour reinstaller)"
        env_enregistrer "$nom" "$exe"
        return 0
    fi

    resoudre_url
    info "Asset : $ASSET_LABEL"
    if [ "$DRYRUN" -eq 1 ] ; then
        alerte "DRYRUN : telechargement/extraction simules vers $dir" ; return 0
    fi

    local tmp="$TMP_BASE/$nom" archive
    # Nom reel de l'archive : le cas sur extension choisit le bon extracteur.
    mkdir -p "$TMP_BASE/archives" "$tmp"
    archive="$TMP_BASE/archives/$(basename "$ASSET_URL")"
    info "Telechargement $ASSET_URL"
    curl -L --fail --retry 3 --progress-bar -o "$archive" "$ASSET_URL"
    ok "Telecharge ($(( $(stat -c%s "$archive" 2>/dev/null || stat -f%z "$archive") / 1048576 )) Mo)"

    info "Extraction..."
    case "$archive" in
        *.zip)          unzip -q -o "$archive" -d "$tmp" ;;
        *.tar.gz|*.tgz) tar -xzf "$archive" -C "$tmp" ;;
        *.tar.xz|*.txz) tar -xJf "$archive" -C "$tmp" ;;
        *)              tar -xf  "$archive" -C "$tmp" ;;
    esac

    local exe_trouve
    exe_trouve="$(find "$tmp" -type f -name "${F_EXE}" | head -n1)"
    if [ -z "$exe_trouve" ] ; then
        echo "${F_EXE} introuvable dans l'archive de $nom" ; return 1
    fi

    mkdir -p "$dir"
    find "$(dirname "$exe_trouve")" -maxdepth 1 -type f -exec cp -f {} "$dir/" \;
    chmod +x "$dir"/* 2>/dev/null || true
    [ -f "$exe" ] || { echo "Echec de l'installation de $nom ($exe absent)" ; return 1 ; }
    ok "Installe dans $dir"

    if mkdir -p "$HOME/.local/bin" 2>/dev/null ; then
        ln -sf "$exe" "$HOME/.local/bin/$(basename "$F_EXE")" 2>/dev/null || true
        if [ "$nom" = "ffmpeg" ] && [ -f "$dir/ffprobe" ] ; then
            ln -sf "$dir/ffprobe" "$HOME/.local/bin/ffprobe" 2>/dev/null || true
        fi
        info "Lien symbolique : $HOME/.local/bin/$(basename "$F_EXE")"
    fi

    env_enregistrer "$nom" "$exe"
}

# Record la variable d'env du moteur dans env.sh + le processus courant.
env_enregistrer() { # $1 = moteur, $2 = chemin exe
    local var chemin
    var="$(var_env_moteur "$1")"
    [ -z "$var" ] && return 0
    chemin="$2"
    export "$var=$chemin"
    printf 'export %s="%s"\n' "$var" "$chemin" >> "$ENV_SH"
}

# ---------------------------------------------------------------- dependances python

if [ "$SKIP_UV_SYNC" -eq 1 ] ; then
    etape "uv sync : ignore (--skip-uv-sync)"
elif [ "$DRYRUN" -eq 1 ] ; then
    etape "uv sync : simule (DRYRUN)"
else
    etape "Synchronisation des dependances Python (uv sync)"
    (cd "$REPO_ROOT" && uv sync)
    ok "Dependances synchronisees"
fi

# ---------------------------------------------------------------- moteurs

export MODEL_DIR="${MODEL_DIR:-${PREFIX}/modeles}"
printf 'export MODEL_DIR="%s"\n' "$MODEL_DIR" >> "$ENV_SH"

IFS=',' read -ra MOTEURS <<< "$ENGINES"
for nom in "${MOTEURS[@]}" ; do
    installer_moteur "$(printf '%s' "$nom" | tr -d '[:space:]')"
done

# ---------------------------------------------------------------- modeles

if [ "$SKIP_MODELS" -eq 1 ] ; then
    etape "Modeles : ignore (--skip-models)"
else
    IFS=',' read -ra PACKS_L <<< "$PACKS"
    for pack in "${PACKS_L[@]}" ; do
        pack="$(printf '%s' "$pack" | tr -d '[:space:]')"
        etape "Pack de modeles '$pack' (download_models.py)"
        if [ "$DRYRUN" -eq 1 ] ; then
            alerte "DRYRUN : uv run python scripts/download_models.py --pack $pack" ; continue
        fi
        (cd "$REPO_ROOT" && uv run python scripts/download_models.py --pack "$pack")
    done
fi

# ---------------------------------------------------------------- verification

if [ "$SKIP_CHECK" -eq 1 ] ; then
    etape "Verification finale : ignoree (--skip-check)"
elif [ "$DRYRUN" -eq 1 ] ; then
    etape "Verification finale : simulee (DRYRUN) -> uv run python main.py --check"
else
    etape "Verification finale (main.py --check)"
    (cd "$REPO_ROOT" && uv run python main.py --check) || \
        alerte "La verification signale des elements manquants (Blender, packs optionnels...) : cf. messages ci-dessus."
fi

# ---------------------------------------------------------------- récapitulatif

etape "Environnement"
ok "Variables d'environnement ecrites dans $ENV_SH"
info "Pour les activer dans votre shell, ajoutez a ~/.bashrc (ou ~/.zshrc) :"
info "    source $ENV_SH"
if [ "$PLATEFORME" = "linux" ] ; then
    info "GPU : pilotes Vulkan requis (AMD : Mesa/RADV ; test : vulkaninfo --summary)."
else
    info "GPU : les moteurs utilisent Metal nativement (aucun Vulkan requis)."
    info "Workflow mesh_ia (trellis.cpp) indisponible sous macOS : build source requis."
fi

printf '\n========================================================\n'
printf ' Installation terminee.\n'
printf ' Demarrage :  uv run python main.py --interactive\n'
printf ' Autres packs de modeles : video, video-14b, all (cf. README, section Modeles).\n'
printf '========================================================\n\n'
