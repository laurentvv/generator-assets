#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LFM3-Audio-2B voice synthesis (LiquidAI) via llama.cpp `llama-tts`.

Compact 2B audio model, speech-to-text AND text-to-speech; this module only
exposes the TTS path (ASR stays a direct llama-mtmd-cli exercise until a use
case justifies wrapping it). Runs on the RX 6950 XT through the Vulkan backend
like every other llama.cpp tool of the factory — measured faster than real
time (1.14x EN / 2.09x FR wall-clock on the validation smokes, 24 kHz output).

Pipeline USER VALIDATED 2026-10-28 ("voix parfaite") — MEMORY_BANK §1.48.
"""

import os
from typing import Any, Dict

from core.config import (
    DEFAULT_LLAMA_TTS,
    DEFAULT_LFM3_TTS_MODEL,
    DEFAULT_LFM3_TTS_MMPROJ,
)
from core.process import run_engine

VOIX_DISPONIBLES = ("female", "male")


def generer_voix_lfm3(
    texte: str,
    sortie: str = "lfm3_tts.wav",
    langue: str = "fr",
    voix: str = "female",
    llama_tts: str = DEFAULT_LLAMA_TTS,
    modele: str = DEFAULT_LFM3_TTS_MODEL,
    mmproj: str = DEFAULT_LFM3_TTS_MMPROJ,
    ngl: int = 99,
) -> Dict[str, Any]:
    """
    Synthesizes speech from `texte` with LFM3-Audio-2B.

    langue: ISO 639-1 code (fr default — the factory's functional language).
    voix: 'female' (model default) or 'male'. No seed: the audio sampling
    parameters baked into the GGUF rule the generation (deterministic enough
    for the validated use; A/B via texte edits, not seeds).
    """
    if not texte or not texte.strip():
        raise ValueError("Empty text: nothing to synthesize.")
    if voix not in VOIX_DISPONIBLES:
        raise ValueError(f"Unknown voice: {voix} (choices: {', '.join(VOIX_DISPONIBLES)})")
    for chemin, role in ((llama_tts, "llama-tts"), (modele, "model"), (mmproj, "mmproj")):
        if not os.path.exists(chemin):
            raise FileNotFoundError(f"{role} not found: {chemin}")

    commande = [
        llama_tts,
        "-m", modele,
        "-mm", mmproj,
        "-p", texte,
        "--tts-lang", langue,
        "--tts-voice", voix,
        "-ngl", str(ngl),
        "-o", sortie,
    ]

    try:
        print(f"🎙️ LFM3-Audio-2B voice synthesis: lang={langue}, voice={voix}…")
    except UnicodeEncodeError:
        print(f"LFM3-Audio-2B voice synthesis: lang={langue}, voice={voix}…")
    run_engine(commande, capture=False, check=True, timeout=600, etiquette="llama-tts lfm3")
    if not os.path.exists(sortie):
        raise RuntimeError(f"The generation did not produce {sortie}")

    taille_mo = os.path.getsize(sortie) / (1024 * 1024)
    print(f"✅ Voice saved: {sortie} ({taille_mo:.2f} MB)")
    return {"sortie": sortie, "moteur": "lfm3_audio_2b", "langue": langue, "voix": voix}
