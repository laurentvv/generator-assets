#!/usr/bin/env python3 -*-
# -*- coding: utf-8 -*-
"""
Character voice synthesis (English) — recipes VALIDATED by the novel2video-ai
pilot casting (user verdicts 2026-09-27, MEMORY_BANK §1.31).

Engines:
- Kokoro-82M via audio.cpp: raw HUMAN preset voice (no robot effect — for the
  robot use core/voix_robot.py). Language auto-resolved from the voice prefix:
  audio.cpp rejects `b*` (British) voices with en-us ("voice bm_george requires
  lang_code=b").
- Qwen3-TTS 1.7B VoiceDesign via qwentts.cpp (managed clone C:\\IA\\qwentts.cpp,
  scripts/manage_qwentts.py): voice designed by an English instruction,
  `--lang English`, deterministic with a fixed seed. The `voix_off` qwen3 path
  (audio.cpp) hardcodes `--language French` + a mandatory voice reference —
  unusable for 100 % English instruct voices, hence this module.

Post chains (FFmpeg, 44.1 kHz PCM16 mono output), all validated on the pilot:
- pitch ratio: source-rate-aware `asetrate` (engine outputs are 24 kHz — a
  44100-based recipe would apply ~1.8x the intended factor) + compensating
  `atempo` (duration preserved). Marc = 0.90.
- whisper: lowpass 1800 Hz / volume 0.5 / aecho 60 ms (Elder treatment).
- hollow: lowpass 900 Hz / aecho 120 ms / +6 dB (Void treatment — the explicit
  gain compensation is MANDATORY: a bare lowpass chain measures -35 dB mean,
  literally inaudible).
"""

import os
import wave
from typing import Any, Dict

from core.music_ai import resoudre_ffmpeg
from core.process import run_engine
from core.voix_robot import generer_base_kokoro

__all__ = [
    "generer_voix_kokoro",
    "generer_voix_design_qwen",
    "langue_kokoro",
    "appliquer_ratio_pitch",
    "appliquer_whisper",
    "appliquer_hollow",
]

# qwentts.cpp clone managed by scripts/manage_qwentts.py (never edited by hand).
DOSSIER_QWENTTS = os.getenv("QWENTTS_DIR", r"C:\IA\qwentts.cpp")
BINARIE_QWEN_TTS = os.path.join(DOSSIER_QWENTTS, "build", "Release", "qwen-tts.exe")
DOSSIER_MODELES_QWENTTS = os.getenv(
    "QWENTTS_MODELS_DIR", os.path.join(DOSSIER_QWENTTS, "models")
)
MODELE_TALKER_VOICEDESIGN = os.path.join(
    DOSSIER_MODELES_QWENTTS, "qwen-talker-1.7b-voicedesign-Q8_0.gguf"
)
MODELE_CODEC_QWEN = os.path.join(
    DOSSIER_MODELES_QWENTTS, "qwen-tokenizer-12hz-Q8_0.gguf"
)

# Compensation of the lowpass attenuation, validated on the Void casting
# (round 1 inaudible at -35.5 dB mean, round 2 validated with +6 dB).
GAIN_HOLLOW_DB = 6.0


def langue_kokoro(voice_id: str) -> str:
    """Resolves the audio.cpp --language value matching a Kokoro voice id.

    Kokoro voice prefixes: `a*` = American English, `b*` = British English —
    the engine enforces voice <-> lang_code (frontend rejects b* with en-us).
    """
    return "en-gb" if voice_id.startswith("b") else "en-us"


def generer_voix_kokoro(
    texte: str,
    sortie: str,
    voice_id: str,
    speaking_rate: float = 1.0,
    backend: str = "vulkan",
) -> Dict[str, Any]:
    """Raw Kokoro preset render (24 kHz mono), language auto-resolved."""
    langue = langue_kokoro(voice_id)
    res = generer_base_kokoro(
        texte, sortie, voice_id=voice_id,
        speaking_rate=speaking_rate, backend=backend, language=langue,
    )
    return {**res, "langue": langue}


def resoudre_qwen_tts() -> str:
    """Checks the qwentts.cpp binary and models, with actionable errors."""
    if not os.path.exists(BINARIE_QWEN_TTS):
        raise FileNotFoundError(
            f"qwen-tts.exe not found: {BINARIE_QWEN_TTS} — engine health: "
            f"uv run python scripts/manage_qwentts.py --check"
        )
    for modele in (MODELE_TALKER_VOICEDESIGN, MODELE_CODEC_QWEN):
        if not os.path.exists(modele):
            raise FileNotFoundError(
                f"qwentts model missing: {modele} — download: "
                f"uv run python scripts/manage_qwentts.py --models"
            )
    return BINARIE_QWEN_TTS


def generer_voix_design_qwen(
    texte: str,
    instruct: str,
    sortie: str,
    langue: str = "English",
    seed: int = 42,
    timeout: float = 1800.0,
) -> Dict[str, Any]:
    """Voice designed by an English instruction (qwentts.cpp VoiceDesign).

    Text is piped on stdin (the engine reads no --text flag). ~10-20 s per
    line on Vulkan (RTF ~0.9).
    """
    binaire = resoudre_qwen_tts()
    cmd = [
        binaire,
        "--model", MODELE_TALKER_VOICEDESIGN,
        "--codec", MODELE_CODEC_QWEN,
        "--lang", langue,
        "--instruct", instruct,
        "--seed", str(seed),
        "-o", sortie,
    ]
    print(f"🎭 Qwen3 VoiceDesign (lang {langue}, seed {seed}) — binary: {binaire}")
    run_engine(cmd, entree_stdin=texte, capture=False, check=True,
               timeout=timeout, etiquette="qwentts voice design")
    if not os.path.exists(sortie):
        raise RuntimeError(f"The generation did not produce {sortie}")
    return {"sortie": sortie, "instruct": instruct, "langue": langue, "seed": seed}


def _lire_taux_echantillonnage(chemin: str) -> int:
    """Sample rate of a PCM WAV via the stdlib (engines output 24 kHz WAV)."""
    with wave.open(chemin, "rb") as wav:
        return wav.getframerate()


def _executer_filtre(source: str, sortie: str, filtre: str, etiquette: str) -> str:
    ffmpeg = resoudre_ffmpeg()
    run_engine(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", source,
         "-af", filtre, "-ar", "44100", "-ac", "1", "-c:a", "pcm_s16le", sortie],
        capture=False, check=True, timeout=180, etiquette=etiquette,
    )
    return sortie


def appliquer_ratio_pitch(source: str, sortie: str, ratio: float) -> str:
    """Pitch shift preserving duration: asetrate at the SOURCE rate x ratio,
    then a compensating atempo (1/ratio). Rate-aware: engine outputs are
    24 kHz, a hardcoded 44100-based chain would apply ~1.8x the factor."""
    if ratio <= 0:
        raise ValueError(f"Pitch ratio must be > 0 (got {ratio}).")
    if abs(ratio - 1.0) < 1e-6:
        return source
    taux = _lire_taux_echantillonnage(source)
    asetrate = int(round(taux * ratio))
    filtre = f"asetrate={asetrate},aresample=44100,atempo={1.0 / ratio:.6f}"
    return _executer_filtre(source, sortie, filtre, f"ffmpeg pitch x{ratio:g}")


def appliquer_whisper(source: str, sortie: str) -> str:
    """Dry haunting whisper: lowpass 1800 Hz, half volume, tight 60 ms echo."""
    return _executer_filtre(
        source, sortie,
        "lowpass=f=1800,volume=0.5,aecho=0.6:0.4:60:0.3",
        "ffmpeg whisper",
    )


def appliquer_hollow(source: str, sortie: str, gain_db: float = GAIN_HOLLOW_DB) -> str:
    """Cavernous hollow voice: lowpass 900 Hz, 120 ms echo, compensated gain.

    The +gain is NOT optional: the lowpass strips so much energy that the
    bare chain measures ~-35 dB mean (inaudible) — see MEMORY_BANK §1.31.
    """
    return _executer_filtre(
        source, sortie,
        f"lowpass=f=900,aecho=0.8:0.9:120:0.5,volume={gain_db:g}dB",
        "ffmpeg hollow",
    )
