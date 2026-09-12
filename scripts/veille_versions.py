#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Veille des versions de la stack locale : audio.cpp, sd-cli (stable-diffusion.cpp),
trellis.cpp (image → 3D, workflow mesh_ia) + GGUF TRELLIS.2 sur HF, FFmpeg,
Python + paquets uv, paquets GGUF de modèles (ACE-Step 1.5…), org audio-cpp
sur HF (repos dédiés + nouveaux fichiers), repos officiels (ACE-Step, sa3.cpp —
port C++/GGML de Stable Audio 3, commits en source info, llama.cpp, qwentts.cpp —
port C++/GGML de Qwen3-TTS installé dans C:\\IA\\qwentts.cpp, commits comparés au
HEAD local), écosystème ComfyUI
(releases du cœur, commits de repos clés, nouveaux repos topic:comfyui — source
d'idées de workflows, cf. docs/recherche_comfyui_2026-09-09.md), outils système
versionnés (SDK Vulkan LunarG — prérequis des builds natifs ; Blender — skins
MPFB ; Godot — moteur du jeu ; uv ; CMake).

Chaque source est comparée à l'état mémorisé (output/veille/etat.json) : seules
les NOUVEAUTÉS sont signalées (🆕), avec les notes de release complètes archivées
dans output/veille/notes/. Le rapport complet est journalisé dans
output/veille/rapports.log. Jamais bloquant : une source indisponible est
signalée et ignorée.

Quand une mise à jour est décidée : suivre la section « 🔄 Process de mise à
jour » de AGENTS.md (une composante à la fois, smoke test, READMEs, rollback).
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

DOSSIER_ETAT = os.path.join("output", "veille")
CHEMIN_ETAT = os.path.join(DOSSIER_ETAT, "etat.json")
CHEMIN_LOG = os.path.join(DOSSIER_ETAT, "rapports.log")
CHEMIN_MAJ = os.path.join(DOSSIER_ETAT, "maj_en_attente.json")

VERSION_AUDIOCPP_INSTALLEE = "v0.7.2"  # fallback si version.json illisible

# Repos ComfyUI surveillés au commit près (veille idées de workflows vidéo/3D ;
# libellé court → source « comfyui-<libellé> » dans le rapport)
COMFYUI_REPOS_SURVEILLES = [
    ("hr-endless", "hradec/ComfyUI-HR-Endless-Sampler"),       # base du workflow h3_ref2va
    ("h3-motion-context", "NikoDemon80/ComfyUI-H3-Motion-Context"),  # chaînage clips H3
    ("exemples", "comfyanonymous/ComfyUI_examples"),           # workflows d'exemple officiels
    ("ltxvideo", "Lightricks/ComfyUI-LTXVideo"),               # workflows LTX-2 (IC-LoRA…)
]


def _github_derniere_release(repo: str) -> dict:
    """Dernière release d'un repo GitHub (tag, nom, date, notes complètes)."""
    r = requests.get(f"https://api.github.com/repos/{repo}/releases/latest", timeout=30)
    r.raise_for_status()
    donnees = r.json()
    return {"tag": donnees.get("tag_name", "?"), "nom": donnees.get("name", ""),
            "date": donnees.get("published_at", "")[:10], "notes": donnees.get("body", "") or ""}


def _archiver_notes(source: str, release: dict):
    """Archive les notes de release d'une nouveauté → output/veille/notes/."""
    dossier = os.path.join(DOSSIER_ETAT, "notes")
    os.makedirs(dossier, exist_ok=True)
    chemin = os.path.join(dossier, f"{source}_{release['tag']}.md")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(f"# {source} {release['tag']} — {release['nom']} ({release['date']})\n\n{release['notes']}\n")
    return chemin


def _version_normale(v: str) -> str:
    """« v5.2.1 » / « 4.7.2-stable » → « 5.2.1 » / « 4.7.2 » (comparaison souple)."""
    v = (v or "").strip().lstrip("v")
    return v.split("-")[0].split("+")[0]


def _derniere_version_lunarg_sdk():
    """Dernière version du SDK Vulkan LunarG (Windows) via l'URL « latest »
    officielle : la version se lit dans l'en-tête Content-Disposition du
    téléchargement (pas de flux JSON public, pas de releases GitHub)."""
    try:
        r = requests.head("https://sdk.lunarg.com/sdk/download/latest/windows/vulkan-sdk.zip",
                          timeout=30, allow_redirects=True)
        m = re.search(r"vulkansdk-windows-X64-([\d.]+)\.exe",
                      r.headers.get("Content-Disposition", ""))
        return m.group(1) if m else None
    except Exception:
        return None


def _github_dernier_tag(repo: str):
    """Dernier tag d'un repo GitHub (projets sans « releases », ex. Blender)."""
    try:
        r = requests.get(f"https://api.github.com/repos/{repo}/tags?per_page=1", timeout=30)
        r.raise_for_status()
        donnees = r.json()
        return donnees[0]["name"] if donnees else None
    except Exception:
        return None


def _version_exe(commande: list, motif: str):
    """Version installée d'un exécutable (regex sur la sortie de --version)."""
    try:
        r = subprocess.run(commande, capture_output=True, text=True, timeout=60)
        m = re.search(motif, (r.stdout or "") + (r.stderr or ""))
        return m.group(1) if m else None
    except Exception:
        return None


def _dernier_sous_dossier(parent: str, motif: str):
    """Sous-dossier de plus haute version sous `parent` (ex. C:/VulkanSDK/1.4.304.1,
    « Blender 5.2 ») — détection de la version installée sans lancer l'outil."""
    try:
        candidats = [d for d in os.listdir(parent) if re.fullmatch(motif, d)]
        if not candidats:
            return None
        return max(candidats, key=lambda v: [int(x) for x in re.findall(r"\d+", v)])
    except Exception:
        return None


def _veille_version_outil(etat, rapport, cle, version_amont, version_installee, contexte):
    """Source générique « outil système versionné » : alerte une seule fois par
    version amont nouvelle, en affichant toujours la version installée. Pure
    info : aucune maj automatique (process AGENTS.md + accord utilisateur)."""
    deja_vue = etat.get(cle, {}).get("derniere_vue")
    if not version_amont:
        rapport.ajouter("⚠️", cle, "vérification impossible : version amont indisponible")
        return
    if version_amont != deja_vue and _version_normale(version_amont) != _version_normale(version_installee or ""):
        rapport.ajouter("🆕", cle, f"nouvelle version disponible : {version_amont} "
                        f"(installé : {version_installee or '?'}) — {contexte}")
    elif version_amont != deja_vue:
        rapport.ajouter("✅", cle, f"dernière version : {version_amont} (installé identique)")
    else:
        rapport.ajouter("✅", cle, f"aucune nouvelle version ({version_amont}) — "
                        f"installé : {version_installee or '?'}")
    etat[cle] = {"derniere_vue": version_amont}


def _charger_etat() -> dict:
    if os.path.exists(CHEMIN_ETAT):
        with open(CHEMIN_ETAT, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _sauver_etat(etat: dict):
    os.makedirs(DOSSIER_ETAT, exist_ok=True)
    with open(CHEMIN_ETAT, "w", encoding="utf-8") as f:
        json.dump(etat, f, indent=2, ensure_ascii=False)


def _sauver_maj_en_attente(rapport: "Rapport", resolus: dict):
    """Synchronise output/veille/maj_en_attente.json (lu par le hook SessionStart).

    Une entrée persiste tant que la mise à jour n'est pas appliquée : une
    nouveauté signalée une fois reste en attente même si les runs suivants
    reviennent au ✅ ; elle disparaît quand la version installée rattrape la
    dernière vue (resolus) ou si l'agent la retire (convention AGENTS.md).
    """
    existant = {}
    if os.path.exists(CHEMIN_MAJ):
        try:
            with open(CHEMIN_MAJ, encoding="utf-8") as f:
                existant = json.load(f)
        except Exception:
            existant = {}
    items = {it.get("source"): it for it in existant.get("items", [])
             if isinstance(it, dict) and it.get("source")}
    for source, resolu in resolus.items():
        if resolu:
            items.pop(source, None)
    for source, message, notes in rapport.nouveautes:
        item = {"source": source, "details": message}
        if notes:
            item["notes"] = notes
        items[source] = item
    os.makedirs(DOSSIER_ETAT, exist_ok=True)
    with open(CHEMIN_MAJ, "w", encoding="utf-8") as f:
        json.dump({"detecte_le": datetime.now().strftime("%Y-%m-%d %H:%M"),
                   "items": list(items.values())},
                  f, indent=2, ensure_ascii=False)


class Rapport:
    def __init__(self):
        self.lignes: list = []
        self.nouveautes: list = []  # (source, message, chemin_notes) pour maj_en_attente.json

    def ajouter(self, emoji: str, source: str, message: str, notes: str = ""):
        self.lignes.append(f"{emoji} [{source}] {message}")
        if emoji == "🆕":
            self.nouveautes.append((source, message, notes))

    def sortie(self) -> str:
        return "\n".join(self.lignes)


def veille() -> tuple:
    etat = _charger_etat()
    etat_avant = json.dumps(etat, sort_keys=True)
    rapport = Rapport()
    resolus: dict = {}  # source → True si la version installée rattrape la dernière vue
    maintenant = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ------------------------------------------------------------------ audio.cpp
    try:
        installee = VERSION_AUDIOCPP_INSTALLEE
        chemin_vj = r"C:\audio-cpp\version.json"
        if os.path.exists(chemin_vj):
            with open(chemin_vj, encoding="utf-8-sig") as f:
                installee = json.load(f).get("version", installee)
        derniere = _github_derniere_release("0xShug0/audio.cpp")
        deja_vue = etat.get("audio.cpp", {}).get("derniere_vue", installee)
        if derniere["tag"] != deja_vue:
            chemin_notes = _archiver_notes("audio-cpp", derniere)
            rapport.ajouter("🆕", "audio.cpp",
                            f"nouvelle release {derniere['tag']} (installée : {installee}, le {derniere['date']}) — "
                            f"« {derniere['nom']} » → mise à jour : C:\\audio-cpp\\update.ps1 — "
                            f"nouveautés détaillées : {chemin_notes}", notes=chemin_notes)
        else:
            rapport.ajouter("✅", "audio.cpp", f"à jour ({installee}, dernière release {derniere['tag']})")
        etat["audio.cpp"] = {"installee": installee, "derniere_vue": derniere["tag"]}
        resolus["audio.cpp"] = (installee == derniere["tag"])
    except Exception as e:
        rapport.ajouter("⚠️", "audio.cpp", f"vérification impossible : {e}")

    # ------------------------------------------- sd-cli (stable-diffusion.cpp)
    # Pas de version.json : le commit est embarqué dans le binaire, et le tag
    # de release amont est de la forme « master-841-6b3edaa » (sha en suffixe).
    try:
        r = subprocess.run([r"C:\SD\sd-cli.exe", "--version"],
                           capture_output=True, text=True, timeout=30)
        sortie = (r.stdout or "") + (r.stderr or "")
        m = re.search(r"commit ([0-9a-f]{7,40})", sortie)
        installe = m.group(1)[:7] if m else "?"
        derniere = _github_derniere_release("leejet/stable-diffusion.cpp")
        m2 = re.search(r"([0-9a-f]{7,40})$", derniere["tag"])
        commit_dernier = m2.group(1)[:7] if m2 else derniere["tag"]
        deja_vue = etat.get("sd_cli", {}).get("derniere_vue", commit_dernier)
        if commit_dernier != deja_vue:
            chemin_notes = _archiver_notes("sd-cli", derniere)
            rapport.ajouter("🆕", "sd-cli",
                            f"nouvelle release {derniere['tag']} (installé : commit {installe}, le {derniere['date']}) — "
                            f"asset : sd-master-<sha>-bin-win-vulkan-x64.zip ; sauvegarder C:\\SD\\*.exe/*.dll dans "
                            f"backups/ avant remplacement — nouveautés détaillées : {chemin_notes}", notes=chemin_notes)
        else:
            rapport.ajouter("✅", "sd-cli", f"à jour (commit {installe}, dernière release {derniere['tag']})")
        etat["sd_cli"] = {"installe": installe, "derniere_vue": commit_dernier}
        resolus["sd-cli"] = (installe != "?" and installe == commit_dernier)
    except Exception as e:
        rapport.ajouter("⚠️", "sd-cli", f"vérification impossible : {e}")

    # ------------------------------------------- trellis.cpp (image → 3D, mesh_ia)
    # Pas de flag --version dans trellis-cli : la version installée est
    # consignée manuellement dans C:\trellis\version.json (à chaque maj).
    try:
        installee = "inconnue"
        chemin_vj = r"C:\trellis\version.json"
        if os.path.exists(chemin_vj):
            with open(chemin_vj, encoding="utf-8-sig") as f:
                installee = json.load(f).get("version", installee)
        derniere = _github_derniere_release("pwilkin/trellis.cpp")
        deja_vue = etat.get("trellis.cpp", {}).get("derniere_vue", installee)
        if derniere["tag"] != deja_vue:
            chemin_notes = _archiver_notes("trellis-cpp", derniere)
            rapport.ajouter("🆕", "trellis.cpp",
                            f"nouvelle release {derniere['tag']} (installée : {installee}, le {derniere['date']}) — "
                            f"asset : trellis-vulkan-windows-x64.zip ; sauvegarder C:\\trellis\\*.exe/*.dll dans "
                            f"C:\\trellis\\backups\\ avant remplacement, puis mettre à jour version.json et "
                            f"C:\\trellis\\README.md — nouveautés détaillées : {chemin_notes}", notes=chemin_notes)
        else:
            rapport.ajouter("✅", "trellis.cpp", f"à jour ({installee}, dernière release {derniere['tag']})")
        etat["trellis.cpp"] = {"installee": installee, "derniere_vue": derniere["tag"]}
        resolus["trellis.cpp"] = (installee == derniere["tag"])
    except Exception as e:
        rapport.ajouter("⚠️", "trellis.cpp", f"vérification impossible : {e}")

    # -------------------------------- GGUF TRELLIS.2 (ilintar/trellis2-gguf sur HF)
    try:
        r = requests.get(
            "https://huggingface.co/api/models/ilintar/trellis2-gguf/tree/main?recursive=true",
            timeout=30)
        r.raise_for_status()
        fichiers = sorted(item["path"] for item in r.json()
                          if item.get("type") == "file" and item["path"].endswith(".gguf"))
        deja_vus = set(etat.get("trellis_gguf", {}).get("fichiers", fichiers))
        nouveaux = [f for f in fichiers if f not in deja_vus]
        if nouveaux:
            rapport.ajouter("🆕", "trellis-gguf",
                            f"nouveaux GGUF sur ilintar/trellis2-gguf : {', '.join(nouveaux)} — "
                            f"variante quantifiée ou nouveau cascade potentiellement à tester (workflow mesh_ia)")
        else:
            rapport.ajouter("✅", "trellis-gguf", f"{len(fichiers)} GGUF, aucun nouveau (ilintar/trellis2-gguf)")
        etat["trellis_gguf"] = {"fichiers": fichiers}
    except Exception as e:
        rapport.ajouter("⚠️", "trellis-gguf", f"vérification impossible : {e}")

    # ------------------------------------------------------- FFmpeg (tags GitHub)
    try:
        r = subprocess.run([r"C:\ffmpeg\dist\bin\ffmpeg.exe", "-version"],
                           capture_output=True, text=True, timeout=30)
        m = re.search(r"ffmpeg version (\d+\.\d+(\.\d+)?)", r.stdout or "")
        installee = m.group(1) if m else "?"
        r = requests.get("https://api.github.com/repos/FFmpeg/FFmpeg/tags?per_page=100", timeout=30)
        r.raise_for_status()
        tags = [t["name"] for t in r.json()]
        versions = sorted(
            (tuple(int(x) for x in t[1:].split(".")) for t in tags
             if re.fullmatch(r"n\d+\.\d+(\.\d+)?", t)),
        )
        derniere = ".".join(str(x) for x in versions[-1]) if versions else "?"
        deja_vue = etat.get("ffmpeg", {}).get("derniere_vue", installee)
        if derniere != deja_vue:
            rapport.ajouter("🆕", "ffmpeg",
                            f"nouvelle version {derniere} (build local : {installee}) → "
                            f"MSYSTEM=UCRT64 /c/msys64/usr/bin/bash.exe -lc 'cd /c/ffmpeg && bash update.sh' — "
                            f"nouveautés : https://ffmpeg.org/index.html#news")
        else:
            rapport.ajouter("✅", "ffmpeg", f"à jour (build local {installee})")
        etat["ffmpeg"] = {"installee": installee, "derniere_vue": derniere}
        resolus["ffmpeg"] = (installee == derniere)
    except Exception as e:
        rapport.ajouter("⚠️", "ffmpeg", f"vérification impossible : {e}")

    # ------------------------------------------------------------------- Python
    try:
        r = subprocess.run([sys.executable, "--version"], capture_output=True, text=True, timeout=30)
        installee = (r.stdout or r.stderr).strip().split()[-1]
        r = requests.get("https://endoflife.date/api/python.json", timeout=30)
        r.raise_for_status()
        cycle = r.json()[0]
        derniere = cycle["latest"]
        deja_vue = etat.get("python", {}).get("derniere_vue", installee)
        mineur_installee = ".".join(installee.split(".")[:2])
        mineur_derniere = ".".join(derniere.split(".")[:2])
        if derniere != deja_vue and mineur_derniere == mineur_installee:
            rapport.ajouter("🆕", "python", f"{mineur_installee}.{derniere.split('.')[-1]} disponible "
                            f"(utilisée : {installee}) → uv python install {mineur_derniere} si utile")
        else:
            rapport.ajouter("✅", "python", f"utilisée : {installee} (dernière stable : {derniere})")
        etat["python"] = {"installee": installee, "derniere_vue": derniere}
    except Exception as e:
        rapport.ajouter("⚠️", "python", f"vérification impossible : {e}")

    # --------------------------------------------------- Paquets Python (uv env)
    try:
        r = subprocess.run(["uv", "pip", "list", "--outdated"], capture_output=True,
                           text=True, timeout=300, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        lignes = [l for l in (r.stdout or "").splitlines()
                  if l and not l.startswith(("Package", "-"))]
        cles = sorted(l.split()[0] for l in lignes if l.split())
        deja_vues = etat.get("paquets_python", {}).get("obsolete", [])
        nouvelles = [p for p in cles if p not in deja_vues]
        if nouvelles:
            # Lien changelog/dépôt pour chaque nouveau paquet (via PyPI)
            details = []
            for paquet in nouvelles[:5]:
                try:
                    rp = requests.get(f"https://pypi.org/pypi/{paquet}/json", timeout=20).json()
                    urls = rp.get("info", {}).get("project_urls", {}) or {}
                    source = (urls.get("Changelog") or urls.get("Release Notes")
                              or urls.get("Source") or urls.get("Repository") or "")
                    details.append(f"{paquet}: {source}" if source else paquet)
                except Exception:
                    details.append(paquet)
            rapport.ajouter("🆕", "paquets-python",
                            f"{len(cles)} paquet(s) avec mise à jour disponible, dont nouveaux : "
                            f"{', '.join(nouvelles[:8])}{'…' if len(nouvelles) > 8 else ''} "
                            f"→ uv lock --upgrade && uv sync — changelogs : {' | '.join(details)}")
        elif cles:
            rapport.ajouter("✅", "paquets-python", f"{len(cles)} mise(s) à jour possible(s), déjà signalées")
        else:
            rapport.ajouter("✅", "paquets-python", "tous à jour")
        etat["paquets_python"] = {"obsolete": cles}
        resolus["paquets-python"] = (not cles)
    except Exception as e:
        rapport.ajouter("⚠️", "paquets-python", f"vérification impossible : {e}")

    # --------------------------------------------- Paquets GGUF ACE-Step 1.5 (HF)
    try:
        r = requests.get("https://huggingface.co/api/models/audio-cpp/audio.cpp-gguf", timeout=30)
        r.raise_for_status()
        fichiers = sorted(s["rfilename"] for s in r.json().get("siblings", [])
                          if s["rfilename"].startswith("ACE-Step"))
        deja_vus = etat.get("acestep_gguf", {}).get("fichiers", [])
        nouveaux = [f for f in fichiers if f not in deja_vus]
        if deja_vus and nouveaux:
            rapport.ajouter("🆕", "modeles-gguf", f"nouveaux paquets HF : {', '.join(nouveaux)} "
                            f"→ uv run python scripts/download_acestep15_gguf.py")
        elif fichiers:
            rapport.ajouter("✅", "modeles-gguf", f"{len(fichiers)} paquets ACE-Step sur HF (aucun nouveau)")
        etat["acestep_gguf"] = {"fichiers": fichiers}
    except Exception as e:
        rapport.ajouter("⚠️", "modeles-gguf", f"vérification impossible : {e}")

    # ------------------------------------ Org audio-cpp : repos et fichiers (HF)
    # Certains modèles vivent dans des repos DÉDIÉS hors de la collection
    # principale (ex. MiniMax-Music3-GGUF, VibeVoice-7B-GGUF) : on surveille
    # donc toute l'org — nouveaux repos ET nouveaux fichiers (nouvelles
    # familles/variantes dans audio.cpp-gguf y compris).
    try:
        r = requests.get("https://huggingface.co/api/models?author=audio-cpp&limit=100", timeout=30)
        r.raise_for_status()
        repos = sorted(m["id"].split("/", 1)[1] for m in r.json())
        anciens = etat.get("org_audio_cpp", {}).get("repos")
        fichiers_par_repo = {}
        for repo in repos:
            rr = requests.get(f"https://huggingface.co/api/models/audio-cpp/{repo}", timeout=30)
            rr.raise_for_status()
            fichiers_par_repo[repo] = sorted(s["rfilename"] for s in rr.json().get("siblings", []))
        if anciens:
            nouveaux_repos = [x for x in repos if x not in anciens]
            nouveaux_fichiers = [f"{repo}/{f}" for repo in repos
                                 for f in fichiers_par_repo[repo]
                                 if repo in anciens and f not in anciens[repo]]
            if nouveaux_repos or nouveaux_fichiers:
                resume = (["repo " + x for x in nouveaux_repos] + nouveaux_fichiers)[:6]
                rapport.ajouter("🆕", "org-audio-cpp",
                                f"nouveautés : {'; '.join(resume)}"
                                f"{'…' if len(nouveaux_repos) + len(nouveaux_fichiers) > 6 else ''}")
            else:
                rapport.ajouter("✅", "org-audio-cpp",
                                f"{len(repos)} repos ({', '.join(repos)}) — aucun nouveau fichier")
        else:
            rapport.ajouter("✅", "org-audio-cpp", f"baseline enregistrée : {len(repos)} repos ({', '.join(repos)})")
        etat["org_audio_cpp"] = {"repos": fichiers_par_repo}
    except Exception as e:
        rapport.ajouter("⚠️", "org-audio-cpp", f"vérification impossible : {e}")

    # --------------------- Nouveaux modèles LLM/VLM/audio GGUF tendance (HF)
    # Objectif : repérer les modèles GGUF qui ÉMERGENT sur Hugging Face (top
    # trending), pas tout HF (des milliers de dépôts/jour). Diff du top
    # trending (text-generation + image-text-to-text + text-to-audio, dont les
    # moteurs musicaux — plafond actuel : réalisme instrumental rock, cf.
    # MEMORY_BANK §1.11) entre deux runs ; le premier run enregistre la
    # baseline sans rien signaler. Rôle : info uniquement — vérifier la
    # compatibilité (llama.cpp, audio.cpp, Vulkan) avant tout téléchargement,
    # selon le process AGENTS.md.
    try:
        modeles = []
        for pipeline in ("text-generation", "image-text-to-text", "text-to-audio"):
            r = requests.get(
                "https://huggingface.co/api/models",
                params={"sort": "trendingScore", "direction": -1, "limit": 30,
                        "library": "gguf", "pipeline_tag": pipeline},
                timeout=30)
            r.raise_for_status()
            modeles += r.json()
        vus, top = set(), []
        for m in modeles:  # dédoublonnage en gardant le meilleur rang trending
            if m.get("id") and m["id"] not in vus:
                vus.add(m["id"])
                top.append(m)

        def _resume_modele(m: dict) -> str:
            return (f"{m['id']} (dl {m.get('downloads', 0)}, ♥{m.get('likes', 0)}, "
                    f"créé {m.get('createdAt', '?')[:10]})")

        deja_vus = etat.get("hf_modeles_gguf", {}).get("top")
        if deja_vus:
            nouveaux = [m for m in top if m["id"] not in set(deja_vus)]
            if nouveaux:
                details = ", ".join(_resume_modele(m) for m in nouveaux[:5])
                rapport.ajouter("🆕", "hf-modeles-gguf",
                                f"{len(nouveaux)} nouveau(x) modèle(s) GGUF en tendance HF : "
                                f"{details}{'…' if len(nouveaux) > 5 else ''} → info : vérifier "
                                f"compatibilité moteur (llama.cpp/audio.cpp, Vulkan) avant usage")
            else:
                rapport.ajouter("✅", "hf-modeles-gguf",
                                f"top tendance GGUF stable ({len(top)} modèles, aucun nouveau)")
        else:
            rapport.ajouter("✅", "hf-modeles-gguf",
                            f"baseline enregistrée : top {len(top)} GGUF tendance HF (ex. "
                            f"{', '.join(_resume_modele(m) for m in top[:3])})")
        etat["hf_modeles_gguf"] = {"top": [m["id"] for m in top]}
    except Exception as e:
        rapport.ajouter("⚠️", "hf-modeles-gguf", f"vérification impossible : {e}")

    # ----------------------------------------------------------- ACE-Step (repo)
    try:
        derniere = _github_derniere_release("ace-step/ACE-Step-1.5")
        deja_vue = etat.get("acestep_repo", {}).get("derniere_vue", derniere["tag"])
        if derniere["tag"] != deja_vue:
            chemin_notes = _archiver_notes("ace-step", derniere)
            rapport.ajouter("🆕", "ace-step", f"nouvelle release modèle {derniere['tag']} "
                            f"« {derniere['nom']} » ({derniere['date']}) — vérifier si audio.cpp la supporte — "
                            f"nouveautés détaillées : {chemin_notes}")
        else:
            rapport.ajouter("✅", "ace-step", f"dernière release modèle : {derniere['tag']}")
        etat["acestep_repo"] = {"derniere_vue": derniere["tag"]}
    except Exception as e:
        rapport.ajouter("⚠️", "ace-step", f"vérification impossible : {e}")

    # ---------------------------------------------------------------- sa3.cpp
    # Port C++/GGML alternatif de Stable Audio 3 (CPU/CUDA/Vulkan/Metal, zéro
    # PyTorch), découvert le 2026-09-09 via les GGUF multi-fichiers thepatch —
    # la famille stable_audio est VALIDÉE sur ce poste via audio.cpp (workflow
    # sfx, MEMORY_BANK §1.11) : un moteur dédié plus rapide/riche serait un
    # candidat direct. Source info : pas installé localement, à évaluer au
    # besoin. Repo SANS releases ni tags (404 sur /releases/latest) →
    # surveillance au commit près, même mécanique que les repos ComfyUI.
    try:
        r = requests.get(
            "https://api.github.com/repos/betweentwomidnights/sa3.cpp/commits?per_page=1",
            timeout=30)
        r.raise_for_status()
        commit = r.json()[0]
        sha, sujet = commit["sha"][:7], (commit["commit"]["message"] or "").split("\n")[0][:90]
        deja_vu = etat.get("sa3.cpp", {}).get("dernier_commit")
        if deja_vu and sha != deja_vu:
            rapport.ajouter("🆕", "sa3.cpp", f"nouveaux commits sur betweentwomidnights/sa3.cpp : "
                            f"{sujet} — port C++/GGML de Stable Audio 3 (Vulkan, zéro PyTorch ; famille "
                            f"stable_audio déjà validée via audio.cpp, workflow sfx) — pas installé "
                            f"localement : à évaluer si besoin SFX/musique")
        elif deja_vu:
            rapport.ajouter("✅", "sa3.cpp", f"sa3.cpp : aucun nouveau commit ({sha})")
        else:
            rapport.ajouter("✅", "sa3.cpp", f"baseline enregistrée : sa3.cpp ({sha}) — pas installé, source info")
        etat["sa3.cpp"] = {"dernier_commit": sha}
    except Exception as e:
        rapport.ajouter("⚠️", "sa3.cpp", f"vérification impossible : {e}")

    # ------------------------------------------------------------ qwentts.cpp
    # Moteur TTS C++17/GGML (port de Qwen3-TTS 12 Hz : speakers nommés, clonage
    # de voix zero-shot, voice design, streaming, serveur OpenAI-compatible ;
    # build Vulkan sur ce poste), installé dans C:\IA\qwentts.cpp (clone
    # ServeurpersoCom/qwentts.cpp) — candidat voix off de la chaîne YouTube.
    # Règle de gestion (accord utilisateur 2026-09-12) : le clone n'est JAMAIS
    # modifié à la main (aucun README custom dedans, doc dans le dépôt) ; la
    # gestion (maj + modèles) a été récupérée du projet ai-doc2video le soir
    # même : scripts/manage_qwentts.py. Repo SANS releases → surveillance au
    # commit près, comparée au HEAD local.
    try:
        r = requests.get(
            "https://api.github.com/repos/ServeurpersoCom/qwentts.cpp/commits?per_page=1",
            timeout=30)
        r.raise_for_status()
        commit_amont = r.json()[0]
        sha = commit_amont["sha"][:7]
        local = None
        try:
            g = subprocess.run(
                ["git", "-C", r"C:\IA\qwentts.cpp", "log", "-1", "--format=%h %cs"],
                capture_output=True, text=True, timeout=30)
            if g.returncode == 0 and g.stdout.strip():
                local = g.stdout.strip()  # ex. « 779c7cb 2026-09-11 »
        except Exception:
            pass
        if local:
            sha_local = local.split()[0]
            if sha == sha_local:
                rapport.ajouter("✅", "qwentts.cpp", f"à jour (amont {sha} = installé)")
            else:
                rapport.ajouter("🆕", "qwentts.cpp", f"nouveaux commits amont sur "
                                f"ServeurpersoCom/qwentts.cpp (amont {sha} vs installé {local}) — "
                                f"moteur TTS Qwen3-TTS (clonage de voix, speakers nommés, serveur "
                                f"OpenAI) — procédure : `uv run python scripts/manage_qwentts.py "
                                f"--update` (sauvegarde binaire + git pull + build Vulkan + smoke "
                                f"test + rollback auto) ; ne jamais éditer les fichiers du clone "
                                f"à la main (doc dans le dépôt, MEMORY_BANK §1.20)")
        else:
            deja_vu = etat.get("qwentts.cpp", {}).get("dernier_commit")
            if deja_vu and sha != deja_vu:
                rapport.ajouter("🆕", "qwentts.cpp", f"nouveaux commits sur "
                                f"ServeurpersoCom/qwentts.cpp ({sha}) — pas de clone local détecté")
            elif not deja_vu:
                rapport.ajouter("✅", "qwentts.cpp", f"baseline enregistrée : qwentts.cpp ({sha}) "
                                f"— pas de clone local détecté")
            else:
                rapport.ajouter("✅", "qwentts.cpp", f"qwentts.cpp : aucun nouveau commit ({sha})")
        etat["qwentts.cpp"] = {"dernier_commit": sha}
    except Exception as e:
        rapport.ajouter("⚠️", "qwentts.cpp", f"vérification impossible : {e}")

    # ------------------------------------------------------------- llama.cpp
    try:
        derniere = _github_derniere_release("ggml-org/llama.cpp")
        deja_vue = etat.get("llama.cpp", {}).get("derniere_vue", derniere["tag"])
        if derniere["tag"] != deja_vue:
            chemin_notes = _archiver_notes("llama-cpp", derniere)
            rapport.ajouter("🆕", "llama.cpp", f"nouvelle release {derniere['tag']} ({derniere['date']}) — "
                            f"mise à jour via C:\\llama.cpp si utilisée — nouveautés détaillées : {chemin_notes}")
        else:
            rapport.ajouter("✅", "llama.cpp", f"dernière release : {derniere['tag']}")
        etat["llama.cpp"] = {"derniere_vue": derniere["tag"]}
    except Exception as e:
        rapport.ajouter("⚠️", "llama.cpp", f"vérification impossible : {e}")

    # -------------------- Outils système versionnés (SDK, builds, moteur jeu)
    # Composants locaux hors « moteurs média » : SDK Vulkan LunarG (prérequis de
    # tous les builds natifs : sd-cli CMake, qwentts.cpp, builds audio.cpp),
    # Blender (pipeline skins MPFB §1.15), Godot (moteur du jeu, consommateur
    # des assets), uv (gestionnaire d'env Python du dépôt) et CMake. Sources
    # info : aucune maj automatique — on ne monte une version que si un
    # moteur/workflow l'exige (process « mise à jour » + accord utilisateur).
    try:
        _veille_version_outil(etat, rapport, "vulkan-sdk", _derniere_version_lunarg_sdk(),
                              _dernier_sous_dossier(r"C:\VulkanSDK", r"\d+\.\d+\.\d+\.\d+"),
                              "SDK requis pour les builds natifs Vulkan (installateur "
                              "LunarG depuis vulkan.lunarg.com, pas de maj auto)")
    except Exception as e:
        rapport.ajouter("⚠️", "vulkan-sdk", f"vérification impossible : {e}")

    try:
        blender_dossier = _dernier_sous_dossier(r"C:\Program Files\Blender Foundation",
                                                r"Blender \d+\.\d+")
        blender_exe = os.path.join(r"C:\Program Files\Blender Foundation",
                                   blender_dossier or "", "blender.exe")
        _veille_version_outil(etat, rapport, "blender", _github_dernier_tag("Blender/Blender"),
                              _version_exe([blender_exe, "--version"],
                                           r"Blender (\d+\.\d+[\d.]*)"),
                              "pipeline skins MPFB (§1.15) — maj via installateur blender.org")
    except Exception as e:
        rapport.ajouter("⚠️", "blender", f"vérification impossible : {e}")

    try:
        _veille_version_outil(etat, rapport, "godot",
                              _github_derniere_release("godotengine/godot")["tag"],
                              _version_exe([r"C:\Godot\godot_console.exe", "--version"],
                                           r"(\d+\.\d+(?:\.\d+)?)"),
                              "moteur du jeu, consommateur des assets — maj via godotengine.org")
    except Exception as e:
        rapport.ajouter("⚠️", "godot", f"vérification impossible : {e}")

    try:
        _veille_version_outil(etat, rapport, "uv",
                              _github_derniere_release("astral-sh/uv")["tag"],
                              _version_exe(["uv", "--version"], r"uv (\d+\.\d+\.\d+)"),
                              "gestionnaire d'environnement Python du dépôt (maj : uv self update)")
    except Exception as e:
        rapport.ajouter("⚠️", "uv", f"vérification impossible : {e}")

    try:
        _veille_version_outil(etat, rapport, "cmake",
                              _github_derniere_release("Kitware/CMake")["tag"],
                              _version_exe(["cmake", "--version"],
                                           r"cmake version (\d+\.\d+\.\d+)"),
                              "builds natifs (qwentts.cpp, audio.cpp, sd-cli) — maj via "
                              "installateur Kitware")
    except Exception as e:
        rapport.ajouter("⚠️", "cmake", f"vérification impossible : {e}")

    # ---------------------------------- Écosystème ComfyUI (idées de workflows)
    # ComfyUI est la source d'inspiration structurante des workflows vidéo
    # (h3_ref2va reproduit le « HR Endless Sampler » en CLI). Trois volets :
    # releases du cœur (nouvelles familles/nœuds — TRELLIS2, Wan 3.0, masques
    # H3… — bon prédicteur des évolutions sd-cli), derniers commits d'une
    # liste curatée de repos clés, et apparition de nouveaux repos
    # topic:comfyui à forte croissance (diff du top créé sur les 45 derniers
    # jours ; premier run = baseline, même mécanique que hf-modeles-gguf).
    try:
        derniere = _github_derniere_release("comfyanonymous/ComfyUI")
        deja_vue = etat.get("comfyui_core", {}).get("derniere_vue", derniere["tag"])
        if derniere["tag"] != deja_vue:
            chemin_notes = _archiver_notes("comfyui-core", derniere)
            rapport.ajouter("🆕", "comfyui-core",
                            f"release ComfyUI {derniere['tag']} « {derniere['nom']} » ({derniere['date']}) — "
                            f"info idées : nouvelles familles/nœuds souvent un signe de ce que sd-cli "
                            f"ajoutera — notes : {chemin_notes}", notes=chemin_notes)
        else:
            rapport.ajouter("✅", "comfyui-core", f"dernière release ComfyUI : {derniere['tag']}")
        etat["comfyui_core"] = {"derniere_vue": derniere["tag"]}
    except Exception as e:
        rapport.ajouter("⚠️", "comfyui-core", f"vérification impossible : {e}")

    for nom_court, repo_comfy in COMFYUI_REPOS_SURVEILLES:
        try:
            r = requests.get(f"https://api.github.com/repos/{repo_comfy}/commits?per_page=1", timeout=30)
            r.raise_for_status()
            commit = r.json()[0]
            sha, sujet = commit["sha"][:7], (commit["commit"]["message"] or "").split("\n")[0][:90]
            deja_vu = etat.get("comfyui_repos", {}).get(repo_comfy)
            if deja_vu and sha != deja_vu:
                rapport.ajouter("🆕", f"comfyui-{nom_court}",
                                f"nouveaux commits sur {repo_comfy} : {sujet} — info : technique "
                                f"potentiellement adaptable aux workflows CLI "
                                f"(cf. docs/recherche_comfyui_2026-09-09.md)")
            elif deja_vu:
                rapport.ajouter("✅", f"comfyui-{nom_court}", f"{repo_comfy} : aucun nouveau commit")
            else:
                rapport.ajouter("✅", f"comfyui-{nom_court}", f"baseline enregistrée : {repo_comfy}")
            etat.setdefault("comfyui_repos", {})[repo_comfy] = sha
        except Exception as e:
            rapport.ajouter("⚠️", f"comfyui-{nom_court}", f"vérification impossible : {e}")

    try:
        fenetre = (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d")
        r = requests.get("https://api.github.com/search/repositories",
                         params={"q": f"topic:comfyui created:>{fenetre}",
                                 "sort": "stars", "order": "desc", "per_page": 20},
                         timeout=30)
        r.raise_for_status()
        top = r.json().get("items", [])
        deja_vus = etat.get("comfyui_nouveaux_repos", {}).get("repos")
        if deja_vus:
            nouveaux = [x for x in top
                        if x["full_name"] not in set(deja_vus) and x.get("stargazers_count", 0) >= 20]
            if nouveaux:
                details = ", ".join(f"{x['full_name']} ({x['stargazers_count']}★)" for x in nouveaux[:5])
                rapport.ajouter("🆕", "comfyui-nouveaux-repos",
                                f"{len(nouveaux)} nouveau(x) repo(s) comfyui en croissance : {details}"
                                f"{'…' if len(nouveaux) > 5 else ''} — info : idée(s) de workflow à "
                                f"évaluer (cf. docs/recherche_comfyui_2026-09-09.md)")
            else:
                rapport.ajouter("✅", "comfyui-nouveaux-repos",
                                f"top {len(top)} repos comfyui récents stable (fenêtre 45 j)")
        else:
            rapport.ajouter("✅", "comfyui-nouveaux-repos",
                            f"baseline enregistrée : top {len(top)} repos comfyui créés après {fenetre}")
        etat["comfyui_nouveaux_repos"] = {"repos": [x["full_name"] for x in top]}
    except Exception as e:
        rapport.ajouter("⚠️", "comfyui-nouveaux-repos", f"vérification impossible : {e}")

    # ------------------------------------------------------------- journalisation
    os.makedirs(DOSSIER_ETAT, exist_ok=True)
    if json.dumps(etat, sort_keys=True) != etat_avant:
        _sauver_etat(etat)
    _sauver_maj_en_attente(rapport, resolus)
    texte = rapport.sortie()
    with open(CHEMIN_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n===== {maintenant} =====\n{texte}\n")
    return texte


if __name__ == "__main__":
    print(veille())
