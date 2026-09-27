#!/usr/bin/env bash
# =============================================================================
# install_unix.sh — generator-assets installer for Linux x64 and macOS.
#
# Does the same thing as scripts/install_windows.ps1 :
#   1. Preflight: tools (curl/tar/unzip/python3), uv (auto-install), disk space.
#   2. uv sync (repo Python dependencies).
#   3. C++ engines downloaded from upstream OFFICIAL RELEASES
#      (pinned versions read from scripts/engines_manifest.json, platform key
#      'linux', 'macos-arm64' or 'macos-x64') + standard FFmpeg
#      (BtbN Linux / Homebrew macOS). Idempotent: an already-present engine
#      is skipped unless --force.
#   4. Model packs via scripts/download_models.py (default base,onnx,upscalers).
#   5. Final check: uv run python main.py --check.
#
# Linux uses the Vulkan backend (required drivers: Mesa/RADV for AMD) ;
# macOS uses native Metal (no Vulkan required). trellis.cpp is not
# published for macOS: it is skipped with a message (source build possible).
#
# The executables are installed under --prefix (default
# $HOME/.local/share/generator-assets), symbolically linked into
# $HOME/.local/bin, and the environment variables expected by
# core/config.py (SD_CLI_PATH, LLAMA_CLI_PATH, AUDIOCPP_PATH,
# TRELLIS_CLI_PATH, FFMPEG_PATH, MODEL_DIR) are written into
# <prefix>/env.sh (to be sourced in ~/.bashrc or ~/.zshrc).
#
# Usage:
#   bash scripts/install_unix.sh [--prefix DIR] [--engines "a,b"] [--packs "p1,p2"]
#        [--skip-models] [--skip-uv-sync] [--skip-check] [--force] [--dry-run]
#
# Test variable: GENERATOR_ASSETS_FORCE_OS=linux|macos-arm64|macos-x64
# forces the target platform (useful for --dry-run from another OS).
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
        *) echo "Unknown option: $1 (see --help)" ; exit 1 ;;
    esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="$REPO_ROOT/scripts/engines_manifest.json"

# ---------------------------------------------------------------- display

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
            echo "Windows detected: use scripts/install_windows.ps1 (PowerShell)." ; exit 1 ;;
        Linux*)  PLATEFORME="linux" ;;
        Darwin*)
            case "$(uname -m)" in
                arm64)  PLATEFORME="macos-arm64" ;;
                x86_64) PLATEFORME="macos-x64" ;;
                *) echo "Unknown macOS architecture: $(uname -m)" ; exit 1 ;;
            esac ;;
        *) echo "Unsupported OS: $UNAME_S" ; exit 1 ;;
    esac
fi

# ---------------------------------------------------------------- tool prerequisites

PY_CMD=""
for c in python3 python ; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c "import json" >/dev/null 2>&1 ; then
        PY_CMD="$c" ; break
    fi
done
if [ -z "$PY_CMD" ] && command -v uv >/dev/null 2>&1 ; then PY_CMD="uv run python" ; fi
if [ -z "$PY_CMD" ] ; then
    echo "python3 not found: install python3 (or uv) then run again." ; exit 1
fi

manque=""
for outil in curl tar unzip ; do
    command -v "$outil" >/dev/null 2>&1 || manque="$manque $outil"
done
if [ -n "$manque" ] ; then
    echo "Missing tools:$manque"
    echo "  Linux (Debian/Ubuntu): sudo apt install curl tar unzip"
    echo "  macOS: shipped with the system (xcode-select --install if needed)"
    exit 1
fi

if ! command -v uv >/dev/null 2>&1 ; then
    alerte "uv not found -> automatic install..."
    if [ "$DRYRUN" -eq 1 ] ; then
        info "DRYRUN: curl -LsSf https://astral.sh/uv/install.sh | sh"
    else
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
        command -v uv >/dev/null 2>&1 || {
            echo "uv not available after install: open a new terminal and run again." ; exit 1 ;
        }
    fi
fi

mkdir -p "$PREFIX"
LIBRE_GO="$(df -PG "$PREFIX" 2>/dev/null | awk 'NR==2 {gsub(/G/,"",$4) ; print $4}' || true)"
LIBRE_GO="${LIBRE_GO:-?}"
if [ "$LIBRE_GO" != "?" ] && [ "$LIBRE_GO" -lt 20 ] 2>/dev/null ; then
    alerte "Only ${LIBRE_GO} GB free on $PREFIX (~20 GB recommended for engines + base pack)."
else
    ok "Enough disk space on $PREFIX (${LIBRE_GO} GB free)"
fi

printf '\n========================================================\n'
printf ' generator-assets - INSTALLATION UNIX (%s)\n' "$PLATEFORME"
printf '========================================================\n'
[ "$DRYRUN" -eq 1 ] && alerte "DRYRUN mode: no real download or installation."

# ---------------------------------------------------------------- lecture manifeste

# fiche_moteur <engine>: loads the platform sheet into FICHE_MOTEUR (KEY=VALUE lines).
# Return code 3 = platform not published upstream; prints __INCONNU__ if unknown engine.
fiche_moteur() { # $1 = engine
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

# resoudre_url: fills ASSET_URL / ASSET_LABEL / ASSET_SHA256 from the current F_* sheet.
# ASSET_SHA256: 'sha256' key of the manifest (pinned asset) or 'digest' field of the GitHub API
# ('latest'/scan release); empty on moving direct URL (no verification possible).
resoudre_url() {
    if [ -n "${F_URL:-}" ] ; then
        ASSET_URL="$F_URL" ; ASSET_LABEL="$(basename "$F_URL")" ; ASSET_SHA256="" ; return 0
    fi
    if [ -n "${F_EPINGLE:-}" ] && [ -n "${F_ASSET:-}" ] ; then
        ASSET_URL="https://github.com/${F_REPO}/releases/download/${F_EPINGLE}/${F_ASSET}"
        ASSET_LABEL="${F_ASSET} (pinned ${F_EPINGLE})" ; ASSET_SHA256="${F_SHA256:-}" ; return 0
    fi
    local api_json
    if [ "${F_RELEASE:-}" = "latest" ] ; then
        info "Looking up the latest ${F_REPO} release..."
        api_json="https://api.github.com/repos/${F_REPO}/releases/latest"
    elif [ -n "${F_RELEASE:-}" ] ; then
        info "Resolving the pinned release ${F_RELEASE} (${F_REPO})..."
        api_json="https://api.github.com/repos/${F_REPO}/releases/tags/${F_RELEASE}"
    elif [ -n "${F_SCAN_RELEASES:-}" ] ; then
        info "Scanning the last ${F_SCAN_RELEASES} ${F_REPO} releases..."
        api_json="https://api.github.com/repos/${F_REPO}/releases?per_page=${F_SCAN_RELEASES}"
    else
        echo "Incomplete platform sheet in engines_manifest.json (no url, no pin, no release/scan_releases)" ; return 1
    fi
    local ligne
    # The python script goes through -c (not stdin) so the pipe feeds json.load.
    ligne="$(curl -sS -H "User-Agent: generator-assets-installer/1.0" "$api_json" | $PY_CMD -c '
import fnmatch, json, sys
pat = sys.argv[1]
data = json.load(sys.stdin)
for rel in (data if isinstance(data, list) else [data]):
    for a in rel.get("assets", []):
        if fnmatch.fnmatch(a.get("name", ""), pat):
            print("%s\t%s (%s)\t%s" % (a["browser_download_url"], a["name"], rel.get("tag_name", ""),
                                       (a.get("digest") or "").replace("sha256:", "")))
            sys.exit(0)
sys.exit(4)
' "${F_ASSET_PATTERN:-}" 2>/dev/null)" || { echo "No asset '${F_ASSET_PATTERN:-}' found for ${F_REPO} (GitHub API unreachable or rate-limited?)" ; return 1 ; }
    ASSET_URL="$(printf '%s' "$ligne" | cut -f1)"
    ASSET_LABEL="$(printf '%s' "$ligne" | cut -f2)"
    ASSET_SHA256="$(printf '%s' "$ligne" | cut -f3)"
    # The manifest sha256 (known-good, maintained by the update process) takes precedence over the API digest.
    ASSET_SHA256="${F_SHA256:-$ASSET_SHA256}"
}

# Checks the sha256 fingerprint of a downloaded archive (failure = installation refused).
verifier_sha256() { # $1 = archive, $2 = expected fingerprint (empty = check skipped)
    [ -n "$2" ] || { alerte "No known sha256 for this asset: integrity not verified." ; return 0 ; }
    local obtenu=""
    if command -v sha256sum >/dev/null 2>&1 ; then
        obtenu="$(sha256sum "$1" | awk '{print $1}')"
    elif command -v shasum >/dev/null 2>&1 ; then
        obtenu="$(shasum -a 256 "$1" | awk '{print $1}')"
    else
        alerte "sha256sum/shasum not found: integrity check skipped."
        return 0
    fi
    if [ "$(printf '%s' "$obtenu" | tr '[:upper:]' '[:lower:]')" != "$(printf '%s' "$2" | tr '[:upper:]' '[:lower:]')" ] ; then
        echo "invalid sha256 for $1: expected $2, got $obtenu (corrupted or tampered asset?)"
        return 1
    fi
    ok "sha256 verified ($(printf '%s' "$2" | cut -c1-12)...)"
}

# Environment variables expected by core/config.py, per engine.
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

# ---------------------------------------------------------------- engine installation

TMP_BASE="$(mktemp -d)"
trap 'rm -rf "$TMP_BASE"' EXIT

installer_moteur() { # $1 = engine
    local nom="$1"
    etape "Engine $nom"

    local rc=0 FICHE
    FICHE="$(fiche_moteur "$nom")" || rc=$?
    if [ "$rc" -eq 3 ] ; then
        alerte "Engine $nom: no binary published upstream for $PLATEFORME -> skipped"
        [ "$nom" = "trellis.cpp" ] && info "mesh_ia workflow on macOS: build from https://github.com/pwilkin/trellis.cpp"
        return 0
    fi
    if [ "$rc" -ne 0 ] || [ "$FICHE" = "__INCONNU__" ] ; then
        echo "Engine '$nom' unknown in engines_manifest.json" ; return 1
    fi

    unset F_REPO F_URL F_EPINGLE F_ASSET F_RELEASE F_SCAN_RELEASES F_ASSET_PATTERN F_SHA256 F_SOUS_DOSSIER F_EXE F_GESTIONNAIRE F_PAQUET 2>/dev/null || true
    local k v k_maj
    while IFS='=' read -r k v ; do
        # tr: macOS bash 3.2 lacks ${k^^} ; stripping the trailing \r
        # (Windows python translates \n to \r\n on stdout).
        k_maj="$(printf '%s' "$k" | tr '[:lower:]' '[:upper:]')"
        v="${v%$'\r'}"
        [ -n "$k_maj" ] && printf -v "F_$k_maj" '%s' "$v"
    done <<< "$FICHE"

    # Homebrew special case (ffmpeg macOS): nothing to download or extract.
    if [ "${F_GESTIONNAIRE:-}" = "brew" ] ; then
        if ! command -v brew >/dev/null 2>&1 ; then
            alerte "Homebrew required for $nom: https://brew.sh -> skipped" ; return 0
        fi
        if [ "$DRYRUN" -eq 1 ] ; then
            info "DRYRUN : brew install ${F_PAQUET}" ; return 0
        fi
        if brew list --formula "${F_PAQUET}" >/dev/null 2>&1 ; then
            ok "brew: ${F_PAQUET} already installed"
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
        ok "$exe already present -> skipped (--force to reinstall)"
        env_enregistrer "$nom" "$exe"
        return 0
    fi

    resoudre_url
    info "Asset: $ASSET_LABEL"
    if [ "$DRYRUN" -eq 1 ] ; then
        alerte "DRYRUN: download/extraction simulated into $dir" ; return 0
    fi

    local tmp="$TMP_BASE/$nom" archive
    # Real archive name: the extension case picks the right extractor.
    mkdir -p "$TMP_BASE/archives" "$tmp"
    archive="$TMP_BASE/archives/$(basename "$ASSET_URL")"
    info "Downloading $ASSET_URL"
    curl -L --fail --retry 3 --progress-bar -o "$archive" "$ASSET_URL"
    ok "Downloaded ($(( $(stat -c%s "$archive" 2>/dev/null || stat -f%z "$archive") / 1048576 )) MB)"
    verifier_sha256 "$archive" "$ASSET_SHA256" || return 1

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
        echo "${F_EXE} not found in the $nom archive" ; return 1
    fi

    mkdir -p "$dir"
    find "$(dirname "$exe_trouve")" -maxdepth 1 -type f -exec cp -f {} "$dir/" \;
    chmod +x "$dir"/* 2>/dev/null || true
    [ -f "$exe" ] || { echo "$nom installation failed ($exe missing)" ; return 1 ; }
    ok "Installed in $dir"

    if mkdir -p "$HOME/.local/bin" 2>/dev/null ; then
        ln -sf "$exe" "$HOME/.local/bin/$(basename "$F_EXE")" 2>/dev/null || true
        if [ "$nom" = "ffmpeg" ] && [ -f "$dir/ffprobe" ] ; then
            ln -sf "$dir/ffprobe" "$HOME/.local/bin/ffprobe" 2>/dev/null || true
        fi
        info "Symbolic link: $HOME/.local/bin/$(basename "$F_EXE")"
    fi

    env_enregistrer "$nom" "$exe"
}

# Records the engine env variable into env.sh + the current process.
env_enregistrer() { # $1 = engine, $2 = exe path
    local var chemin
    var="$(var_env_moteur "$1")"
    [ -z "$var" ] && return 0
    chemin="$2"
    export "$var=$chemin"
    printf 'export %s="%s"\n' "$var" "$chemin" >> "$ENV_SH"
}

# ---------------------------------------------------------------- dependances python

if [ "$SKIP_UV_SYNC" -eq 1 ] ; then
    etape "uv sync: skipped (--skip-uv-sync)"
elif [ "$DRYRUN" -eq 1 ] ; then
    etape "uv sync: simulated (DRYRUN)"
else
    etape "Syncing Python dependencies (uv sync)"
    (cd "$REPO_ROOT" && uv sync)
    ok "Dependencies synced"
fi

# ---------------------------------------------------------------- engines

export MODEL_DIR="${MODEL_DIR:-${PREFIX}/modeles}"
printf 'export MODEL_DIR="%s"\n' "$MODEL_DIR" >> "$ENV_SH"

IFS=',' read -ra MOTEURS <<< "$ENGINES"
for nom in "${MOTEURS[@]}" ; do
    installer_moteur "$(printf '%s' "$nom" | tr -d '[:space:]')"
done

# ---------------------------------------------------------------- models

if [ "$SKIP_MODELS" -eq 1 ] ; then
    etape "Models: skipped (--skip-models)"
else
    IFS=',' read -ra PACKS_L <<< "$PACKS"
    for pack in "${PACKS_L[@]}" ; do
        pack="$(printf '%s' "$pack" | tr -d '[:space:]')"
        etape "Model pack '$pack' (download_models.py)"
        if [ "$DRYRUN" -eq 1 ] ; then
            alerte "DRYRUN: uv run python scripts/download_models.py --pack $pack" ; continue
        fi
        (cd "$REPO_ROOT" && uv run python scripts/download_models.py --pack "$pack")
    done
fi

# ---------------------------------------------------------------- check

if [ "$SKIP_CHECK" -eq 1 ] ; then
    etape "Final check: skipped (--skip-check)"
elif [ "$DRYRUN" -eq 1 ] ; then
    etape "Final check: simulated (DRYRUN) -> uv run python main.py --check"
else
    etape "Final check (main.py --check)"
    (cd "$REPO_ROOT" && uv run python main.py --check) || \
        alerte "The check reports missing items (Blender, optional packs...): see messages above."
fi

# ---------------------------------------------------------------- summary

etape "Environment"
ok "Environment variables written to $ENV_SH"
info "To activate them in your shell, add to ~/.bashrc (or ~/.zshrc):"
info "    source $ENV_SH"
if [ "$PLATEFORME" = "linux" ] ; then
    info "GPU: Vulkan drivers required (AMD: Mesa/RADV; test: vulkaninfo --summary)."
else
    info "GPU: the engines use Metal natively (no Vulkan required)."
    info "mesh_ia workflow (trellis.cpp) unavailable on macOS: source build required."
fi

printf '\n========================================================\n'
printf ' Installation complete.\n'
printf ' Getting started:  uv run python main.py --interactive\n'
printf ' Other model packs: video, video-14b, all (see README, Models section).\n'
printf '========================================================\n\n'
