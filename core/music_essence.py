#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génération musicale par « essence » d'une référence (Stable Audio 3 Medium, init_audio).

Capacité validée par l'utilisateur les 2026-09-08/09 sur la référence Love Like Blood :
le conditionnement audio (init_audio) transmet le groove/timbre de la référence là où
le prompt texte seul sort du pop. Échelles validées : plateau 0,40-0,45 à graine fixe
(0,5+ = loterie selon la graine, ≤0,35 = zone quasi-copie avec bave du chant source).
La bave de voix se retire ensuite via HTDemucs (core.separation.retirer_voix).

Écueils intégrés :
- SA3 n'a pas d'options planner (bpm/keyscale) — tempo/tonalité passent dans le texte
- la sortie SA3 est en 44,1 kHz stéréo (prête pour HTDemucs, aucun rééchantillonnage)
"""

import os
import re
import subprocess
from typing import Any, Dict, Optional

from core.music_ai import convertir_mp3, resoudre_audiocpp

MODELE_SA3_MEDIUM = os.getenv(
    "SA3_MEDIUM_MODEL",
    os.path.join("C:\\Modeles_LLM", "Stable-Audio-3-Medium-GGUF", "stable-audio-3-medium-f16.gguf"),
)

# Plateau validé le 2026-09-09 (graine 42) : 0,40 et 0,45 (réf 30 ou 60 s) tiennent l'essence.
DEFAULT_SCALE = 0.45


def generer_essence_sa3(
    style: str,
    reference: str,
    duree: float = 30.0,
    scale: float = DEFAULT_SCALE,
    seed: int = 42,
    sortie_wav: str = "essence.wav",
    backend: str = "vulkan",
) -> Dict[str, Any]:
    """
    Génère `duree` secondes de musique à l'essence de `reference` (mode init_audio).
    Retourne {wav, mp3, rtf}. Le chant de la référence peut baver dans la sortie
    (échelles basses) — passer le résultat par retirer_voix pour un instrumental pur.
    """
    if not os.path.exists(MODELE_SA3_MEDIUM):
        raise FileNotFoundError(
            f"Paquet SA3 Medium introuvable : {MODELE_SA3_MEDIUM} — le télécharger depuis "
            f"audio-cpp/audio.cpp-gguf (Stable-Audio-3-Medium-GGUF/stable-audio-3-medium-f16.gguf, "
            f"5,43 Gio ; téléchargeur parallèle recommandé)."
        )
    if not os.path.exists(reference):
        raise FileNotFoundError(f"Référence audio introuvable : {reference}")

    sortie_wav = os.path.abspath(sortie_wav)
    os.makedirs(os.path.dirname(sortie_wav), exist_ok=True)
    cmd = [
        resoudre_audiocpp(), "--task", "gen", "--family", "stable_audio",
        "--model", MODELE_SA3_MEDIUM, "--backend", backend, "--metrics",
        "--audio", os.path.abspath(reference), "--text", style,
        "--duration-seconds", str(int(duree)), "--seed", str(int(seed)),
        "--request-option", "audio_input_kind=init_audio",
        "--request-option", f"init_noise_level={scale}",
        "--out", sortie_wav,
    ]
    res = subprocess.run(
        cmd, capture_output=True, text=True, timeout=int(duree * 10 + 300),
        encoding="utf-8", errors="replace",
    )
    if res.returncode != 0 or not os.path.exists(sortie_wav):
        extrait = (res.stderr or res.stdout or "").strip()[-400:]
        raise RuntimeError(f"Génération SA3 échouée (exit {res.returncode}) : {extrait}")

    rtf = None
    m = re.search(r"metrics\.rtf=([\d.]+)", res.stdout)
    if m:
        rtf = float(m.group(1))
    mp3 = convertir_mp3(sortie_wav, sortie_wav.replace(".wav", ".mp3"), 320)
    return {"wav": sortie_wav, "mp3": mp3, "rtf": rtf}
