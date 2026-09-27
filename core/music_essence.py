#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Music generation from the "essence" of a reference track (Stable Audio 3 Medium, init_audio).

Capability validated by the user on 2026-09-08/09 against the Love Like Blood reference:
audio conditioning (init_audio) carries over the groove/timbre of the reference where a
text-only prompt drifts into pop. Validated scales: 0.40-0.45 plateau at fixed seed
(0.5+ = seed-dependent lottery, <=0.35 = near-copy zone with vocal bleed from the source).
The vocal bleed is then removed via HTDemucs (core.separation.retirer_voix).

Integrated pitfalls:
- SA3 has no planner options (bpm/keyscale) — tempo/key go into the text prompt
- SA3 output is 44.1 kHz stereo (ready for HTDemucs, no resampling)
"""

import os
import re
from typing import Any, Dict

from core.music_ai import convertir_mp3, resoudre_audiocpp
from core.process import run_engine

MODELE_SA3_MEDIUM = os.getenv(
    "SA3_MEDIUM_MODEL",
    os.path.join("C:\\Modeles_LLM", "Stable-Audio-3-Medium-GGUF", "stable-audio-3-medium-f16.gguf"),
)

# Plateau validated on 2026-09-09 (seed 42): 0.40 and 0.45 (30 or 60 s ref) hold the essence.
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
    Generates `duree` seconds of music with the essence of `reference` (init_audio mode).
    Returns {wav, mp3, rtf}. The reference vocals may bleed into the output
    (low scales) — pass the result through retirer_voix for a pure instrumental.
    """
    if not os.path.exists(MODELE_SA3_MEDIUM):
        raise FileNotFoundError(
            f"SA3 Medium package not found: {MODELE_SA3_MEDIUM} — download it from "
            f"audio-cpp/audio.cpp-gguf (Stable-Audio-3-Medium-GGUF/stable-audio-3-medium-f16.gguf, "
            f"5.43 GiB; parallel downloader recommended)."
        )
    if not os.path.exists(reference):
        raise FileNotFoundError(f"Audio reference not found: {reference}")

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
    res = run_engine(
        cmd, check=False, capture=True,
        timeout=int(duree * 10 + 300), etiquette="audio.cpp sa3 essence",
    )
    if res.returncode != 0 or not os.path.exists(sortie_wav):
        extrait = (res.stderr or res.stdout or "").strip()[-400:]
        raise RuntimeError(f"SA3 generation failed (exit {res.returncode}): {extrait}")

    rtf = None
    m = re.search(r"metrics\.rtf=([\d.]+)", res.stdout)
    if m:
        rtf = float(m.group(1))
    mp3 = convertir_mp3(sortie_wav, sortie_wav.replace(".wav", ".mp3"), 320)
    return {"wav": sortie_wav, "mp3": mp3, "rtf": rtf}
