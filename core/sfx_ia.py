#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génération de bruitages (SFX) par IA : Stable Audio 3 Small SFX via audio.cpp.

Moteur validé par l'utilisateur le 2026-09-09 (4/5 échantillons « ok » : épée, pas
gravier, porte, whoosh) sur les SFX du cas d'usage jeu Godot — RTF ~0,2 Vulkan,
le plus rapide du poste. Le sample pluie/orage rejeté (« faible volume pas top »)
l'était sur le niveau de sortie : ce module applique une normalisation de crête
systématique pour garantir un niveau exploitable en jeu.

Écueils intégrés :
- sortie SA3 = 44,1 kHz stéréo (le workflow sfx historique était mono procédural ;
  l'export Godot WAV/OGG accepte les deux)
- OGG interdit via soundfile (stack overflow libsndfile, règle §1.10) — l'export
  final passe par exporter_sfx_godot (ffmpeg), ce module ne fait que le WAV intermédiaire
"""

import os
import re
import subprocess
import tempfile
from typing import Any, Dict

import numpy as np
import soundfile as sf

from core.music_ai import resoudre_audiocpp

MODELE_SA3_SFX = os.getenv(
    "SA3_SFX_MODEL",
    os.path.join(
        "C:\\Modeles_LLM",
        "Stable-Audio-3-Small-SFX-GGUF",
        "stable-audio-3-small-sfx-f16.gguf",
    ),
)

# Normalisation de crête (~ -0,9 dBFS) : même convention que la synthèse procédurale (0,9).
PIC_CIBLE = 0.9


def generer_sfx_ia(
    prompt: str,
    duree: float = 2.0,
    seed: int = 42,
    backend: str = "vulkan",
) -> Dict[str, Any]:
    """
    Génère un effet sonore par IA (stable_audio, texte → audio).
    Retourne {"audio": float32 (stéréo), "sr": 44100, "rtf": float|None, "pic_source": float}.
    Graine < 0 = laisser le défaut du runtime (déterministe).
    """
    if not os.path.exists(MODELE_SA3_SFX):
        raise FileNotFoundError(
            f"Paquet SA3 Small SFX introuvable : {MODELE_SA3_SFX} — le télécharger depuis "
            f"audio-cpp/audio.cpp-gguf (Stable-Audio-3-Small-SFX-GGUF/stable-audio-3-small-sfx-f16.gguf, "
            f"2,20 Gio ; téléchargeur parallèle recommandé)."
        )

    fd, wav_brut = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    cmd = [
        resoudre_audiocpp(), "--task", "gen", "--family", "stable_audio",
        "--model", MODELE_SA3_SFX, "--backend", backend, "--metrics",
        "--text", prompt, "--duration-seconds", str(float(duree)),
        "--out", wav_brut,
    ]
    if seed is not None and seed >= 0:
        cmd += ["--seed", str(int(seed))]

    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=int(duree * 10 + 300), encoding="utf-8", errors="replace",
        )
        if res.returncode != 0 or not os.path.exists(wav_brut):
            extrait = (res.stderr or res.stdout or "").strip()[-400:]
            raise RuntimeError(f"Génération SFX IA échouée (exit {res.returncode}) : {extrait}")

        rtf = None
        m = re.search(r"metrics\.rtf=([\d.]+)", res.stdout)
        if m:
            rtf = float(m.group(1))

        audio, sr = sf.read(wav_brut, always_2d=False, dtype="float32")
    finally:
        if os.path.exists(wav_brut):
            os.remove(wav_brut)

    pic = float(np.max(np.abs(audio))) if audio.size else 0.0
    if pic > 0:
        audio = (audio / pic) * PIC_CIBLE

    return {"audio": audio.astype(np.float32), "sr": int(sr), "rtf": rtf, "pic_source": pic}
