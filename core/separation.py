#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vocal removal via HTDemucs source separation (audio.cpp, Vulkan).

Capability validated by the user on 2026-09-06 ("vocal removal: OK")
on the full Love Like Blood track. Produces:
- the instrumental without vocals (drums+bass+other mix, levels preserved)
- the 4 full stems (drums, bass, other, vocals) for later use

Integrated pitfalls:
- HTDemucs requires 44.1 kHz ("sample rate mismatch" otherwise) → automatic
  resampling of any source
- writing stems requires --out-dir (named multi-output); --out is rejected
"""

import os
from typing import Any, Dict

from core.music_ai import convertir_mp3, resoudre_audiocpp, resoudre_ffmpeg
from core.process import run_engine

MODELE_HTDEMUCS = os.getenv(
    "HTDEMUCS_MODEL",
    os.path.join("C:\\Modeles_LLM", "HTDemucs-GGUF", "htdemucs-f16.gguf"),
)
SR_HDEMUCS = 44100
STEMS_INSTRUMENTAL = ("drums", "bass", "other")


def retirer_voix(chemin_audio: str, dossier_travail: str, backend: str = "vulkan") -> Dict[str, Any]:
    """
    Separates audio into HTDemucs stems and builds the instrumental without vocals.
    Returns the paths {instrumental_wav, instrumental_mp3, stems_dir, voix_wav}.
    """
    if not os.path.exists(MODELE_HTDEMUCS):
        raise FileNotFoundError(
            f"HTDemucs package not found: {MODELE_HTDEMUCS} — download it from "
            f"audio-cpp/audio.cpp-gguf (HTDemucs-GGUF/htdemucs-f16.gguf, 84 MB)."
        )
    ffmpeg = resoudre_ffmpeg()
    os.makedirs(dossier_travail, exist_ok=True)

    # 1) 44.1 kHz stereo resampling (required by HTDemucs)
    wav44 = os.path.join(dossier_travail, "source_44k.wav")
    run_engine(
        [ffmpeg, "-hide_banner", "-y", "-i", chemin_audio,
         "-ar", str(SR_HDEMUCS), "-ac", "2", "-c:a", "pcm_s16le", wav44],
        check=True, timeout=600, etiquette="ffmpeg 44k resampling",
    )

    # 2) Stem separation (multi-output => --out-dir mandatory)
    stems_dir = os.path.join(dossier_travail, "stems")
    os.makedirs(stems_dir, exist_ok=True)
    # Live HTDemucs progress (separation = minutes)
    run_engine(
        [resoudre_audiocpp(), "--task", "sep", "--family", "htdemucs",
         "--model", MODELE_HTDEMUCS, "--backend", backend, "--threads", "16",
         "--audio", wav44, "--out-dir", stems_dir],
        capture=False, check=True, timeout=3600, etiquette="audio.cpp htdemucs",
    )
    manquants = [s for s in STEMS_INSTRUMENTAL + ("vocals",)
                 if not os.path.exists(os.path.join(stems_dir, f"{s}.wav"))]
    if manquants:
        raise RuntimeError(f"Missing HTDemucs stems: {', '.join(manquants)}")

    # 3) Instrumental = drums + bass + other (sum without vocals, levels preserved)
    instrumental = os.path.join(dossier_travail, "instrumental.wav")
    entrees: list = []
    for s in STEMS_INSTRUMENTAL:
        entrees += ["-i", os.path.join(stems_dir, f"{s}.wav")]
    filtre = "".join(f"[{i}:a]" for i in range(len(STEMS_INSTRUMENTAL)))
    filtre += f"amix=inputs={len(STEMS_INSTRUMENTAL)}:normalize=0"
    run_engine(
        [ffmpeg, "-hide_banner", "-y", *entrees, "-filter_complex", filtre,
         "-c:a", "pcm_s16le", instrumental],
        check=True, timeout=600, etiquette="ffmpeg amix instrumental",
    )

    # 4) Listening MP3
    mp3 = convertir_mp3(instrumental, instrumental.replace(".wav", ".mp3"), 192)
    return {
        "instrumental_wav": instrumental,
        "instrumental_mp3": mp3,
        "stems_dir": stems_dir,
        "voix_wav": os.path.join(stems_dir, "vocals.wav"),
    }
