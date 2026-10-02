#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Voice conversion via audio.cpp `chatterbox` family: renders an existing
recording (speech/singing) in the voice of a reference sample, keeping the
original prosody and timing.

User-validated 2026-10-02 ("voix anglaise bien") on the E01 narration A/B
pair: qwen_expr take → voxcpm voice ref, Vulkan, ~11 s rendered in seconds.
Successor of the rejected VeVo2 singing/VC path (MEMORY_BANK §1.34) for
character voices.

Built-in pitfalls (2026-10-02):
- the family name is EMBEDDED in the GGUF: `chatterbox` for the standard
  package, `chatterbox_turbo` for the turbo one — and the TURBO variant only
  supports TTS ("Chatterbox Turbo supports TTS only"), VC requires the
  standard package (this module pins it explicitly);
- output = 24 kHz mono WAV (speech-grade, NOT studio/music quality): keep it
  for dialogue/voice lines, not for musical beds.
"""

import os

from core.music_ai import resoudre_audiocpp
from core.process import run_engine

MODELE_CHATTERBOX = os.getenv(
    "CHATTERBOX_MODEL",
    os.path.join("C:\\Modeles_LLM", "Chatterbox-GGUF", "chatterbox-q8_0.gguf"),
)


def generer_conversion_voix(
    chemin_audio: str,
    chemin_ref_voix: str,
    chemin_sortie: str,
    backend: str = "vulkan",
    timeout_s: int = 900,
) -> str:
    """
    Converts `chemin_audio` into the voice carried by `chemin_ref_voix`
    (chatterbox `vc` task). Returns the output WAV path (24 kHz mono).
    """
    if not os.path.exists(chemin_audio):
        raise FileNotFoundError(f"Source recording not found: {chemin_audio}")
    if not os.path.exists(chemin_ref_voix):
        raise FileNotFoundError(f"Voice reference not found: {chemin_ref_voix}")
    if not os.path.exists(MODELE_CHATTERBOX):
        raise FileNotFoundError(
            f"Chatterbox model not found: {MODELE_CHATTERBOX}\n"
            "→ download audio-cpp/audio.cpp-gguf (Chatterbox-GGUF/chatterbox-q8_0.gguf, "
            "1.94 GiB — NOT the Turbo variant: TTS only, no VC)."
        )

    exe = resoudre_audiocpp()
    cmd = [
        exe, "--task", "vc", "--family", "chatterbox",
        "--model", MODELE_CHATTERBOX, "--backend", backend,
        "--audio", chemin_audio,
        "--voice-ref", chemin_ref_voix,
        "--out", chemin_sortie,
        "--log",
    ]

    resultat = run_engine(
        cmd, check=False, capture=True, timeout=timeout_s,
        etiquette="audio.cpp chatterbox vc",
    )
    erreurs = (resultat.stderr or "") + (resultat.stdout or "")
    if resultat.returncode != 0 or not os.path.exists(chemin_sortie) or os.path.getsize(chemin_sortie) <= 4096:
        raise RuntimeError(
            f"Chatterbox voice conversion failed (code {resultat.returncode}): {erreurs.strip()[-600:]}"
        )
    return chemin_sortie
