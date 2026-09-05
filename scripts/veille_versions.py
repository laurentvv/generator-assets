#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Veille des versions de la stack locale : audio.cpp, FFmpeg, Python + paquets
uv, paquets GGUF de modèles (ACE-Step 1.5…), repos officiels (ACE-Step,
llama.cpp).

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
from datetime import datetime

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

DOSSIER_ETAT = os.path.join("output", "veille")
CHEMIN_ETAT = os.path.join(DOSSIER_ETAT, "etat.json")
CHEMIN_LOG = os.path.join(DOSSIER_ETAT, "rapports.log")

VERSION_AUDIOCPP_INSTALLEE = "v0.7.2"  # fallback si version.json illisible


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


def _charger_etat() -> dict:
    if os.path.exists(CHEMIN_ETAT):
        with open(CHEMIN_ETAT, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _sauver_etat(etat: dict):
    os.makedirs(DOSSIER_ETAT, exist_ok=True)
    with open(CHEMIN_ETAT, "w", encoding="utf-8") as f:
        json.dump(etat, f, indent=2, ensure_ascii=False)


class Rapport:
    def __init__(self):
        self.lignes: list = []

    def ajouter(self, emoji: str, source: str, message: str):
        self.lignes.append(f"{emoji} [{source}] {message}")

    def sortie(self) -> str:
        return "\n".join(self.lignes)


def veille() -> tuple:
    etat = _charger_etat()
    etat_avant = json.dumps(etat, sort_keys=True)
    rapport = Rapport()
    maintenant = datetime.now().strftime("%Y-%m-%d %H:%M")

    # ------------------------------------------------------------------ audio.cpp
    try:
        installee = VERSION_AUDIOCPP_INSTALLEE
        chemin_vj = r"C:\audio-cpp\version.json"
        if os.path.exists(chemin_vj):
            with open(chemin_vj, encoding="utf-8") as f:
                installee = json.load(f).get("version", installee)
        derniere = _github_derniere_release("0xShug0/audio.cpp")
        deja_vue = etat.get("audio.cpp", {}).get("derniere_vue", installee)
        if derniere["tag"] != deja_vue:
            chemin_notes = _archiver_notes("audio-cpp", derniere)
            rapport.ajouter("🆕", "audio.cpp",
                            f"nouvelle release {derniere['tag']} (installée : {installee}, le {derniere['date']}) — "
                            f"« {derniere['nom']} » → mise à jour : C:\\audio-cpp\\update.ps1 — "
                            f"nouveautés détaillées : {chemin_notes}")
        else:
            rapport.ajouter("✅", "audio.cpp", f"à jour ({installee}, dernière release {derniere['tag']})")
        etat["audio.cpp"] = {"installee": installee, "derniere_vue": derniere["tag"]}
    except Exception as e:
        rapport.ajouter("⚠️", "audio.cpp", f"vérification impossible : {e}")

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
                            f"MSYSTEM=UCRT64 /c/ffmpeg/msys64/usr/bin/bash.exe -lc 'cd /c/ffmpeg && bash update.sh' — "
                            f"nouveautés : https://ffmpeg.org/index.html#news")
        else:
            rapport.ajouter("✅", "ffmpeg", f"à jour (build local {installee})")
        etat["ffmpeg"] = {"installee": installee, "derniere_vue": derniere}
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
            rapport.ajouter("🆕", "paquets-python",
                            f"{len(cles)} paquet(s) avec mise à jour disponible, dont nouveaux : "
                            f"{', '.join(nouvelles[:8])}{'…' if len(nouvelles) > 8 else ''} "
                            f"→ uv lock --upgrade && uv sync")
        elif cles:
            rapport.ajouter("✅", "paquets-python", f"{len(cles)} mise(s) à jour possible(s), déjà signalées")
        else:
            rapport.ajouter("✅", "paquets-python", "tous à jour")
        etat["paquets_python"] = {"obsolete": cles}
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

    # ------------------------------------------------------------- journalisation
    os.makedirs(DOSSIER_ETAT, exist_ok=True)
    if json.dumps(etat, sort_keys=True) != etat_avant:
        _sauver_etat(etat)
    texte = rapport.sortie()
    with open(CHEMIN_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n===== {maintenant} =====\n{texte}\n")
    return texte


if __name__ == "__main__":
    print(veille())
