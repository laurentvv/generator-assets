#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Version watch of the local stack: audio.cpp, sd-cli (stable-diffusion.cpp),
trellis.cpp (image → 3D, mesh_ia workflow) + TRELLIS.2 GGUF on HF, FFmpeg,
Python + uv packages, GGUF model packages (ACE-Step 1.5…), the audio-cpp org
on HF (dedicated repos + new files), official repos (ACE-Step, sa3.cpp —
C++/GGML port of Stable Audio 3, commits as info source, llama.cpp, qwentts.cpp —
C++/GGML port of Qwen3-TTS installed in C:\\IA\\qwentts.cpp, commits compared to
the local HEAD), the ComfyUI ecosystem
(core releases, commits of key repos, new topic:comfyui repos — source of
workflow ideas, see docs/recherche_comfyui_2026-09-09.md), versioned system
tools (LunarG Vulkan SDK — prerequisite of native builds; Blender — MPFB
skins; Godot — game engine; uv; CMake).

Each source is compared against the remembered state (output/veille/etat.json): only
NEW items are reported (🆕), with full release notes archived
in output/veille/notes/. The complete report is logged in
output/veille/rapports.log. Never blocking: an unavailable source is
reported and skipped.

When an update is decided: follow the "🔄 Update process" section of AGENTS.md
(one component at a time, smoke test, READMEs, rollback).
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

VERSION_AUDIOCPP_INSTALLEE = "v0.7.2"  # fallback if version.json is unreadable

# ComfyUI repos watched at commit level (video/3D workflow idea watch;
# short label → "comfyui-<label>" source in the report)
COMFYUI_REPOS_SURVEILLES = [
    ("hr-endless", "hradec/ComfyUI-HR-Endless-Sampler"),       # base of the h3_ref2va workflow
    ("h3-motion-context", "NikoDemon80/ComfyUI-H3-Motion-Context"),  # H3 clip chaining
    ("exemples", "comfyanonymous/ComfyUI_examples"),           # official example workflows
    ("ltxvideo", "Lightricks/ComfyUI-LTXVideo"),               # LTX-2 workflows (IC-LoRA…)
]


def _github_derniere_release(repo: str) -> dict:
    """Latest release of a GitHub repo (tag, name, date, full notes)."""
    r = requests.get(f"https://api.github.com/repos/{repo}/releases/latest", timeout=30)
    r.raise_for_status()
    donnees = r.json()
    return {"tag": donnees.get("tag_name", "?"), "nom": donnees.get("name", ""),
            "date": donnees.get("published_at", "")[:10], "notes": donnees.get("body", "") or ""}


def _commits_entre(repo: str, ref_avant: str, ref_apres: str, limite: int = 40) -> str:
    """List the commits between two refs (GitHub compare API) — fallback notes
    section when an upstream release has no body (sd-cli master snapshots)."""
    try:
        r = requests.get(f"https://api.github.com/repos/{repo}/compare/{ref_avant}...{ref_apres}",
                         timeout=30)
        r.raise_for_status()
        commits = r.json().get("commits", [])
        lignes = [f"- {c['sha'][:7]} {c['commit']['message'].splitlines()[0]}"
                  for c in commits[-limite:]]
        if lignes:
            return (f"\n## Commits {ref_avant} → {ref_apres} ({len(commits)} total)\n"
                    + "\n".join(lignes) + "\n")
    except Exception:
        pass  # not blocking: empty notes remain acceptable
    return ""


def _archiver_notes(source: str, release: dict, repo: str = "", ref_avant: str = ""):
    """Archive the release notes of a new item → output/veille/notes/.
    If the upstream release has no notes (e.g. sd-cli master snapshots) and
    repo+ref_avant are provided, complete with the list of commits between the
    last seen version and this one (otherwise the upstream knowledge is lost)."""
    dossier = os.path.join(DOSSIER_ETAT, "notes")
    os.makedirs(dossier, exist_ok=True)
    corps = release.get("notes") or ""
    if not corps.strip() and repo and ref_avant:
        corps = _commits_entre(repo, ref_avant, release["tag"])
    chemin = os.path.join(dossier, f"{source}_{release['tag']}.md")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(f"# {source} {release['tag']} — {release['nom']} ({release['date']})\n\n{corps}\n")
    return chemin


def _version_normale(v: str) -> str:
    """'v5.2.1' / '4.7.2-stable' → '5.2.1' / '4.7.2' (loose comparison)."""
    v = (v or "").strip().lstrip("v")
    return v.split("-")[0].split("+")[0]


def _derniere_version_lunarg_sdk():
    """Latest LunarG Vulkan SDK version (Windows) via the official "latest"
    URL: the version is read from the download's Content-Disposition
    header (no public JSON feed, no GitHub releases)."""
    try:
        r = requests.head("https://sdk.lunarg.com/sdk/download/latest/windows/vulkan-sdk.zip",
                          timeout=30, allow_redirects=True)
        m = re.search(r"vulkansdk-windows-X64-([\d.]+)\.exe",
                      r.headers.get("Content-Disposition", ""))
        return m.group(1) if m else None
    except Exception:
        return None


def _github_dernier_tag(repo: str):
    """Latest tag of a GitHub repo (projects without "releases", e.g. Blender)."""
    try:
        r = requests.get(f"https://api.github.com/repos/{repo}/tags?per_page=1", timeout=30)
        r.raise_for_status()
        donnees = r.json()
        return donnees[0]["name"] if donnees else None
    except Exception:
        return None


def _version_exe(commande: list, motif: str):
    """Installed version of an executable (regex on the --version output)."""
    try:
        r = subprocess.run(commande, capture_output=True, text=True, timeout=60)
        m = re.search(motif, (r.stdout or "") + (r.stderr or ""))
        return m.group(1) if m else None
    except Exception:
        return None


def _dernier_sous_dossier(parent: str, motif: str):
    """Highest-version subdirectory under `parent` (e.g. C:/VulkanSDK/1.4.304.1,
    "Blender 5.2") — detects the installed version without launching the tool."""
    try:
        candidats = [d for d in os.listdir(parent) if re.fullmatch(motif, d)]
        if not candidats:
            return None
        return max(candidats, key=lambda v: [int(x) for x in re.findall(r"\d+", v)])
    except Exception:
        return None


def _veille_version_outil(etat, rapport, cle, version_amont, version_installee, contexte):
    """Generic "versioned system tool" source: alert only once per new
    upstream version, while always showing the installed version. Pure
    info: no automatic update (AGENTS.md process + user approval)."""
    deja_vue = etat.get(cle, {}).get("derniere_vue")
    if not version_amont:
        rapport.ajouter("⚠️", cle, "check impossible: upstream version unavailable")
        return
    if version_amont != deja_vue and _version_normale(version_amont) != _version_normale(version_installee or ""):
        rapport.ajouter("🆕", cle, f"new version available: {version_amont} "
                        f"(installed: {version_installee or '?'}) — {contexte}")
    elif version_amont != deja_vue:
        rapport.ajouter("✅", cle, f"latest version: {version_amont} (installed identical)")
    else:
        rapport.ajouter("✅", cle, f"no new version ({version_amont}) — "
                        f"installed: {version_installee or '?'}")
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
    """Synchronizes output/veille/maj_en_attente.json (read by the SessionStart hook).

    An entry persists as long as the update is not applied: an item
    reported once stays pending even if subsequent runs
    go back to ✅; it disappears when the installed version catches up with the
    last seen one (resolus) or when the agent removes it (AGENTS.md convention).
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
        self.nouveautes: list = []  # (source, message, notes_path) for maj_en_attente.json

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
    resolus: dict = {}  # source → True if the installed version caught up with the last seen one
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
                            f"new release {derniere['tag']} (installed: {installee}, on {derniere['date']}) — "
                            f"'{derniere['nom']}' → update: C:\\audio-cpp\\update.ps1 — "
                            f"detailed changes: {chemin_notes}", notes=chemin_notes)
        else:
            rapport.ajouter("✅", "audio.cpp", f"up to date ({installee}, latest release {derniere['tag']})")
        etat["audio.cpp"] = {"installee": installee, "derniere_vue": derniere["tag"]}
        resolus["audio.cpp"] = (installee == derniere["tag"])
    except Exception as e:
        rapport.ajouter("⚠️", "audio.cpp", f"check impossible: {e}")

    # ------------------------------------------- sd-cli (stable-diffusion.cpp)
    # No version.json: the commit is embedded in the binary, and the upstream
    # release tag looks like "master-841-6b3edaa" (sha as suffix).
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
            # master snapshots WITHOUT upstream changelog → notes completed with the
            # commit compare between the already-seen version and the new one
            chemin_notes = _archiver_notes("sd-cli", derniere,
                                           repo="leejet/stable-diffusion.cpp",
                                           ref_avant=deja_vue)
            rapport.ajouter("🆕", "sd-cli",
                            f"new release {derniere['tag']} (installed: commit {installe}, on {derniere['date']}) — "
                            f"asset: sd-master-<sha>-bin-win-vulkan-x64.zip ; back up C:\\SD\\*.exe/*.dll to "
                            f"backups/ before replacing — detailed changes: {chemin_notes}", notes=chemin_notes)
        else:
            rapport.ajouter("✅", "sd-cli", f"up to date (commit {installe}, latest release {derniere['tag']})")
        etat["sd_cli"] = {"installe": installe, "derniere_vue": commit_dernier}
        resolus["sd-cli"] = (installe != "?" and installe == commit_dernier)
    except Exception as e:
        rapport.ajouter("⚠️", "sd-cli", f"check impossible: {e}")

    # ------------------------------------------- trellis.cpp (image → 3D, mesh_ia)
    # No --version flag in trellis-cli: the installed version is
    # recorded manually in C:\trellis\version.json (at every update).
    try:
        installee = "unknown"
        chemin_vj = r"C:\trellis\version.json"
        if os.path.exists(chemin_vj):
            with open(chemin_vj, encoding="utf-8-sig") as f:
                installee = json.load(f).get("version", installee)
        derniere = _github_derniere_release("pwilkin/trellis.cpp")
        deja_vue = etat.get("trellis.cpp", {}).get("derniere_vue", installee)
        if derniere["tag"] != deja_vue:
            chemin_notes = _archiver_notes("trellis-cpp", derniere)
            rapport.ajouter("🆕", "trellis.cpp",
                            f"new release {derniere['tag']} (installed: {installee}, on {derniere['date']}) — "
                            f"asset: trellis-vulkan-windows-x64.zip ; back up C:\\trellis\\*.exe/*.dll to "
                            f"C:\\trellis\\backups\\ before replacing, then update version.json and "
                            f"C:\\trellis\\README.md — detailed changes: {chemin_notes}", notes=chemin_notes)
        else:
            rapport.ajouter("✅", "trellis.cpp", f"up to date ({installee}, latest release {derniere['tag']})")
        etat["trellis.cpp"] = {"installee": installee, "derniere_vue": derniere["tag"]}
        resolus["trellis.cpp"] = (installee == derniere["tag"])
    except Exception as e:
        rapport.ajouter("⚠️", "trellis.cpp", f"check impossible: {e}")

    # -------------------------------- GGUF TRELLIS.2 (ilintar/trellis2-gguf on HF)
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
                            f"new GGUF on ilintar/trellis2-gguf: {', '.join(nouveaux)} — "
                            f"quantized variant or new cascade potentially worth testing (mesh_ia workflow)")
        else:
            rapport.ajouter("✅", "trellis-gguf", f"{len(fichiers)} GGUF, none new (ilintar/trellis2-gguf)")
        etat["trellis_gguf"] = {"fichiers": fichiers}
    except Exception as e:
        rapport.ajouter("⚠️", "trellis-gguf", f"check impossible: {e}")

    # ------------------------------------------------------- FFmpeg (GitHub tags)
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
                            f"new version {derniere} (local build: {installee}) → "
                            f"MSYSTEM=UCRT64 /c/msys64/usr/bin/bash.exe -lc 'cd /c/ffmpeg && bash update.sh' — "
                            f"changes: https://ffmpeg.org/index.html#news")
        else:
            rapport.ajouter("✅", "ffmpeg", f"up to date (local build {installee})")
        etat["ffmpeg"] = {"installee": installee, "derniere_vue": derniere}
        resolus["ffmpeg"] = (installee == derniere)
    except Exception as e:
        rapport.ajouter("⚠️", "ffmpeg", f"check impossible: {e}")

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
            rapport.ajouter("🆕", "python", f"{mineur_installee}.{derniere.split('.')[-1]} available "
                            f"(in use: {installee}) → uv python install {mineur_derniere} if useful")
        else:
            rapport.ajouter("✅", "python", f"in use: {installee} (latest stable: {derniere})")
        etat["python"] = {"installee": installee, "derniere_vue": derniere}
    except Exception as e:
        rapport.ajouter("⚠️", "python", f"check impossible: {e}")

    # --------------------------------------------------- Python packages (uv env)
    try:
        r = subprocess.run(["uv", "pip", "list", "--outdated"], capture_output=True,
                           text=True, timeout=300, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        lignes = [ligne for ligne in (r.stdout or "").splitlines()
                  if ligne and not ligne.startswith(("Package", "-"))]
        cles = sorted(ligne.split()[0] for ligne in lignes if ligne.split())
        deja_vues = etat.get("paquets_python", {}).get("obsolete", [])
        nouvelles = [p for p in cles if p not in deja_vues]
        if nouvelles:
            # changelog/repo link for each new package (via PyPI)
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
                            f"{len(cles)} package(s) with an update available, including new: "
                            f"{', '.join(nouvelles[:8])}{'…' if len(nouvelles) > 8 else ''} "
                            f"→ uv lock --upgrade && uv sync — changelogs: {' | '.join(details)}")
        elif cles:
            rapport.ajouter("✅", "paquets-python", f"{len(cles)} possible update(s), already reported")
        else:
            rapport.ajouter("✅", "paquets-python", "all up to date")
        etat["paquets_python"] = {"obsolete": cles}
        resolus["paquets-python"] = (not cles)
    except Exception as e:
        rapport.ajouter("⚠️", "paquets-python", f"check impossible: {e}")

    # --------------------------------------------- ACE-Step 1.5 GGUF packages (HF)
    try:
        r = requests.get("https://huggingface.co/api/models/audio-cpp/audio.cpp-gguf", timeout=30)
        r.raise_for_status()
        fichiers = sorted(s["rfilename"] for s in r.json().get("siblings", [])
                          if s["rfilename"].startswith("ACE-Step"))
        deja_vus = etat.get("acestep_gguf", {}).get("fichiers", [])
        nouveaux = [f for f in fichiers if f not in deja_vus]
        if deja_vus and nouveaux:
            rapport.ajouter("🆕", "modeles-gguf", f"new HF packages: {', '.join(nouveaux)} "
                            f"→ uv run python scripts/download_acestep15_gguf.py")
        elif fichiers:
            rapport.ajouter("✅", "modeles-gguf", f"{len(fichiers)} ACE-Step packages on HF (none new)")
        etat["acestep_gguf"] = {"fichiers": fichiers}
    except Exception as e:
        rapport.ajouter("⚠️", "modeles-gguf", f"check impossible: {e}")

    # ------------------------------------ audio-cpp org: repos and files (HF)
    # Some models live in DEDICATED repos outside the main
    # collection (e.g. MiniMax-Music3-GGUF, VibeVoice-7B-GGUF): we therefore watch
    # the whole org — new repos AND new files (new
    # families/variants in audio.cpp-gguf included).
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
                                f"new items: {'; '.join(resume)}"
                                f"{'…' if len(nouveaux_repos) + len(nouveaux_fichiers) > 6 else ''}")
            else:
                rapport.ajouter("✅", "org-audio-cpp",
                                f"{len(repos)} repos ({', '.join(repos)}) — no new file")
        else:
            rapport.ajouter("✅", "org-audio-cpp", f"baseline recorded: {len(repos)} repos ({', '.join(repos)})")
        etat["org_audio_cpp"] = {"repos": fichiers_par_repo}
    except Exception as e:
        rapport.ajouter("⚠️", "org-audio-cpp", f"check impossible: {e}")

    # --------------------- New trending LLM/VLM/audio GGUF models (HF)
    # Goal: spot the GGUF models EMERGING on Hugging Face (top
    # trending), not all of HF (thousands of repos/day). Diff of the
    # trending top (text-generation + image-text-to-text + text-to-audio, including the
    # music engines — current ceiling: rock instrumental realism, see
    # MEMORY_BANK §1.11) between two runs; the first run records the
    # baseline without reporting anything. Role: info only — check
    # compatibility (llama.cpp, audio.cpp, Vulkan) before any download,
    # following the AGENTS.md process.
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
        for m in modeles:  # dedupe keeping the best trending rank
            if m.get("id") and m["id"] not in vus:
                vus.add(m["id"])
                top.append(m)

        def _resume_modele(m: dict) -> str:
            return (f"{m['id']} (dl {m.get('downloads', 0)}, ♥{m.get('likes', 0)}, "
                    f"created {m.get('createdAt', '?')[:10]})")

        deja_vus = etat.get("hf_modeles_gguf", {}).get("top")
        if deja_vus:
            nouveaux = [m for m in top if m["id"] not in set(deja_vus)]
            if nouveaux:
                details = ", ".join(_resume_modele(m) for m in nouveaux[:5])
                rapport.ajouter("🆕", "hf-modeles-gguf",
                                f"{len(nouveaux)} new GGUF model(s) trending on HF: "
                                f"{details}{'…' if len(nouveaux) > 5 else ''} → info: check "
                                f"engine compatibility (llama.cpp/audio.cpp, Vulkan) before use")
            else:
                rapport.ajouter("✅", "hf-modeles-gguf",
                                f"stable GGUF trending top ({len(top)} models, none new)")
        else:
            rapport.ajouter("✅", "hf-modeles-gguf",
                            f"baseline recorded: top {len(top)} GGUF trending on HF (e.g. "
                            f"{', '.join(_resume_modele(m) for m in top[:3])})")
        etat["hf_modeles_gguf"] = {"top": [m["id"] for m in top]}
    except Exception as e:
        rapport.ajouter("⚠️", "hf-modeles-gguf", f"check impossible: {e}")

    # ----------------------------------------------------------- ACE-Step (repo)
    try:
        derniere = _github_derniere_release("ace-step/ACE-Step-1.5")
        deja_vue = etat.get("acestep_repo", {}).get("derniere_vue", derniere["tag"])
        if derniere["tag"] != deja_vue:
            chemin_notes = _archiver_notes("ace-step", derniere)
            rapport.ajouter("🆕", "ace-step", f"new model release {derniere['tag']} "
                            f"'{derniere['nom']}' ({derniere['date']}) — check whether audio.cpp supports it — "
                            f"detailed changes: {chemin_notes}")
        else:
            rapport.ajouter("✅", "ace-step", f"latest model release: {derniere['tag']}")
        etat["acestep_repo"] = {"derniere_vue": derniere["tag"]}
    except Exception as e:
        rapport.ajouter("⚠️", "ace-step", f"check impossible: {e}")

    # ---------------------------------------------------------------- sa3.cpp
    # Alternative C++/GGML port of Stable Audio 3 (CPU/CUDA/Vulkan/Metal, zero
    # PyTorch), discovered on 2026-09-09 via the thepatch multi-file GGUFs —
    # the stable_audio family is VALIDATED on this machine via audio.cpp (sfx
    # workflow, MEMORY_BANK §1.11): a dedicated faster/richer engine would be a
    # direct candidate. Info source: not installed locally, to evaluate as
    # needed. Repo WITHOUT releases or tags (404 on /releases/latest) →
    # commit-level watch, same mechanism as the ComfyUI repos.
    try:
        r = requests.get(
            "https://api.github.com/repos/betweentwomidnights/sa3.cpp/commits?per_page=1",
            timeout=30)
        r.raise_for_status()
        commit = r.json()[0]
        sha, sujet = commit["sha"][:7], (commit["commit"]["message"] or "").split("\n")[0][:90]
        deja_vu = etat.get("sa3.cpp", {}).get("dernier_commit")
        if deja_vu and sha != deja_vu:
            rapport.ajouter("🆕", "sa3.cpp", f"new commits on betweentwomidnights/sa3.cpp: "
                            f"{sujet} — C++/GGML port of Stable Audio 3 (Vulkan, zero PyTorch; "
                            f"stable_audio family already validated via audio.cpp, sfx workflow) — not installed "
                            f"locally: to evaluate if SFX/music is needed")
        elif deja_vu:
            rapport.ajouter("✅", "sa3.cpp", f"sa3.cpp: no new commit ({sha})")
        else:
            rapport.ajouter("✅", "sa3.cpp", f"baseline recorded: sa3.cpp ({sha}) — not installed, info source")
        etat["sa3.cpp"] = {"dernier_commit": sha}
    except Exception as e:
        rapport.ajouter("⚠️", "sa3.cpp", f"check impossible: {e}")

    # ------------------------------------------------------------ qwentts.cpp
    # C++17/GGML TTS engine (port of Qwen3-TTS 12 Hz: named speakers, zero-shot
    # voice cloning, voice design, streaming, OpenAI-compatible server;
    # Vulkan build on this machine), installed in C:\IA\qwentts.cpp (clone of
    # ServeurpersoCom/qwentts.cpp) — voice-over candidate for the YouTube channel.
    # Management rule (user approval 2026-09-12): the clone is NEVER
    # modified by hand (no custom README inside, docs live in the repo); its
    # management (updates + models) was taken over from the ai-doc2video project
    # that same evening: scripts/manage_qwentts.py. Repo WITHOUT releases →
    # commit-level watch, compared to the local HEAD.
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
                local = g.stdout.strip()  # e.g. "779c7cb 2026-09-11"
        except Exception:
            pass
        if local:
            sha_local = local.split()[0]
            if sha == sha_local:
                rapport.ajouter("✅", "qwentts.cpp", f"up to date (upstream {sha} = installed)")
            else:
                rapport.ajouter("🆕", "qwentts.cpp", f"new upstream commits on "
                                f"ServeurpersoCom/qwentts.cpp (upstream {sha} vs installed {local}) — "
                                f"Qwen3-TTS TTS engine (voice cloning, named speakers, OpenAI "
                                f"server) — procedure: `uv run python scripts/manage_qwentts.py "
                                f"--update` (binary backup + git pull + Vulkan build + smoke "
                                f"test + auto rollback) ; never edit the clone's files "
                                f"by hand (docs in the repo, MEMORY_BANK §1.20)")
        else:
            deja_vu = etat.get("qwentts.cpp", {}).get("dernier_commit")
            if deja_vu and sha != deja_vu:
                rapport.ajouter("🆕", "qwentts.cpp", f"new commits on "
                                f"ServeurpersoCom/qwentts.cpp ({sha}) — no local clone detected")
            elif not deja_vu:
                rapport.ajouter("✅", "qwentts.cpp", f"baseline recorded: qwentts.cpp ({sha}) "
                                f"— no local clone detected")
            else:
                rapport.ajouter("✅", "qwentts.cpp", f"qwentts.cpp: no new commit ({sha})")
        etat["qwentts.cpp"] = {"dernier_commit": sha}
    except Exception as e:
        rapport.ajouter("⚠️", "qwentts.cpp", f"check impossible: {e}")

    # ------------------------------------------------------------- llama.cpp
    try:
        derniere = _github_derniere_release("ggml-org/llama.cpp")
        deja_vue = etat.get("llama.cpp", {}).get("derniere_vue", derniere["tag"])
        if derniere["tag"] != deja_vue:
            chemin_notes = _archiver_notes("llama-cpp", derniere)
            rapport.ajouter("🆕", "llama.cpp", f"new release {derniere['tag']} ({derniere['date']}) — "
                            f"update via C:\\llama.cpp if in use — detailed changes: {chemin_notes}")
        else:
            rapport.ajouter("✅", "llama.cpp", f"latest release: {derniere['tag']}")
        etat["llama.cpp"] = {"derniere_vue": derniere["tag"]}
    except Exception as e:
        rapport.ajouter("⚠️", "llama.cpp", f"check impossible: {e}")

    # -------------------- Versioned system tools (SDKs, builds, game engine)
    # Local components outside the "media engines": LunarG Vulkan SDK (prerequisite
    # of all native builds: sd-cli CMake, qwentts.cpp, audio.cpp builds),
    # Blender (MPFB skins pipeline §1.15), Godot (game engine, consumer
    # of the assets), uv (repo's Python env manager) and CMake. Info
    # sources: no automatic update — a version is only bumped when an
    # engine/workflow requires it ("update" process + user approval).
    try:
        _veille_version_outil(etat, rapport, "vulkan-sdk", _derniere_version_lunarg_sdk(),
                              _dernier_sous_dossier(r"C:\VulkanSDK", r"\d+\.\d+\.\d+\.\d+"),
                              "SDK required for the Vulkan native builds (LunarG "
                              "installer from vulkan.lunarg.com, no auto update)")
    except Exception as e:
        rapport.ajouter("⚠️", "vulkan-sdk", f"check impossible: {e}")

    try:
        blender_dossier = _dernier_sous_dossier(r"C:\Program Files\Blender Foundation",
                                                r"Blender \d+\.\d+")
        blender_exe = os.path.join(r"C:\Program Files\Blender Foundation",
                                   blender_dossier or "", "blender.exe")
        _veille_version_outil(etat, rapport, "blender", _github_dernier_tag("Blender/Blender"),
                              _version_exe([blender_exe, "--version"],
                                           r"Blender (\d+\.\d+[\d.]*)"),
                              "MPFB skins pipeline (§1.15) — update via blender.org installer")
    except Exception as e:
        rapport.ajouter("⚠️", "blender", f"check impossible: {e}")

    try:
        _veille_version_outil(etat, rapport, "godot",
                              _github_derniere_release("godotengine/godot")["tag"],
                              _version_exe([r"C:\Godot\godot_console.exe", "--version"],
                                           r"(\d+\.\d+(?:\.\d+)?)"),
                              "game engine, consumer of the assets — update via godotengine.org")
    except Exception as e:
        rapport.ajouter("⚠️", "godot", f"check impossible: {e}")

    try:
        _veille_version_outil(etat, rapport, "uv",
                              _github_derniere_release("astral-sh/uv")["tag"],
                              _version_exe(["uv", "--version"], r"uv (\d+\.\d+\.\d+)"),
                              "repo's Python environment manager (update: uv self update)")
    except Exception as e:
        rapport.ajouter("⚠️", "uv", f"check impossible: {e}")

    try:
        _veille_version_outil(etat, rapport, "cmake",
                              _github_derniere_release("Kitware/CMake")["tag"],
                              _version_exe(["cmake", "--version"],
                                           r"cmake version (\d+\.\d+\.\d+)"),
                              "native builds (qwentts.cpp, audio.cpp, sd-cli) — update via "
                              "Kitware installer")
    except Exception as e:
        rapport.ajouter("⚠️", "cmake", f"check impossible: {e}")

    # ---------------------------------- ComfyUI ecosystem (workflow ideas)
    # ComfyUI is the structuring source of inspiration for the video workflows
    # (h3_ref2va reproduces the "HR Endless Sampler" in CLI). Three parts:
    # core releases (new families/nodes — TRELLIS2, Wan 3.0, H3 masks
    # … — good predictor of sd-cli evolutions), latest commits of a
    # curated list of key repos, and the appearance of fast-growing new
    # topic:comfyui repos (diff of the top created over the last 45
    # days; first run = baseline, same mechanism as hf-modeles-gguf).
    try:
        derniere = _github_derniere_release("comfyanonymous/ComfyUI")
        deja_vue = etat.get("comfyui_core", {}).get("derniere_vue", derniere["tag"])
        if derniere["tag"] != deja_vue:
            chemin_notes = _archiver_notes("comfyui-core", derniere)
            rapport.ajouter("🆕", "comfyui-core",
                            f"ComfyUI release {derniere['tag']} '{derniere['nom']}' ({derniere['date']}) — "
                            f"idea info: new families/nodes often a sign of what sd-cli "
                            f"will add — notes: {chemin_notes}", notes=chemin_notes)
        else:
            rapport.ajouter("✅", "comfyui-core", f"latest ComfyUI release: {derniere['tag']}")
        etat["comfyui_core"] = {"derniere_vue": derniere["tag"]}
    except Exception as e:
        rapport.ajouter("⚠️", "comfyui-core", f"check impossible: {e}")

    for nom_court, repo_comfy in COMFYUI_REPOS_SURVEILLES:
        try:
            r = requests.get(f"https://api.github.com/repos/{repo_comfy}/commits?per_page=1", timeout=30)
            r.raise_for_status()
            commit = r.json()[0]
            sha, sujet = commit["sha"][:7], (commit["commit"]["message"] or "").split("\n")[0][:90]
            deja_vu = etat.get("comfyui_repos", {}).get(repo_comfy)
            if deja_vu and sha != deja_vu:
                rapport.ajouter("🆕", f"comfyui-{nom_court}",
                                f"new commits on {repo_comfy}: {sujet} — info: technique "
                                f"potentially adaptable to the CLI workflows "
                                f"(see docs/recherche_comfyui_2026-09-09.md)")
            elif deja_vu:
                rapport.ajouter("✅", f"comfyui-{nom_court}", f"{repo_comfy}: no new commit")
            else:
                rapport.ajouter("✅", f"comfyui-{nom_court}", f"baseline recorded: {repo_comfy}")
            etat.setdefault("comfyui_repos", {})[repo_comfy] = sha
        except Exception as e:
            rapport.ajouter("⚠️", f"comfyui-{nom_court}", f"check impossible: {e}")

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
                                f"{len(nouveaux)} new comfyui repo(s) growing: {details}"
                                f"{'…' if len(nouveaux) > 5 else ''} — info: workflow idea(s) to "
                                f"evaluate (see docs/recherche_comfyui_2026-09-09.md)")
            else:
                rapport.ajouter("✅", "comfyui-nouveaux-repos",
                                f"stable recent comfyui repos top {len(top)} (45 d window)")
        else:
            rapport.ajouter("✅", "comfyui-nouveaux-repos",
                            f"baseline recorded: top {len(top)} comfyui repos created after {fenetre}")
        etat["comfyui_nouveaux_repos"] = {"repos": [x["full_name"] for x in top]}
    except Exception as e:
        rapport.ajouter("⚠️", "comfyui-nouveaux-repos", f"check impossible: {e}")

    # ------------------------------------------------------------------- logging
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
