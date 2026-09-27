#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
English robot voice (recipe VALIDATED by the user on 2026-09-17, trial 17
"quiet little robot"): TTS Kokoro-82M via audio.cpp (Vulkan) then "little
robot" FFmpeg effect.

Validated recipe (output/test_voix_robot/essai17_kokoro_ringmod120_tranquille.mp3):
1. TTS      : kokoro_tts family, `af_heart` voice, en-us, 24 kHz mono, normal rate.
2. FF effect: pitch +30% (asetrate 31200), atempo 0.65 (settled rate, pitch intact),
              120 Hz ring modulation (aeval — the voice multiplied by a sine loses
              its fundamental → metallic timbre), gain -4 dB.

⚠️ Engine: the audio.cpp release zip (v0.7.4 and v0.8.0) cannot launch
kokoro_tts ("Could not load eSpeak-ng" — neither shared espeak DLL nor static
pack provided, see MEMORY_BANK §1.21) → the scratch binary `build-357` (embedded espeak)
is resolved automatically as long as it exists; overridable via the
AUDIOCPP_KOKORO_CLI environment variable. To revisit if a release ships espeak.
"""

import os
from typing import Any, Dict

from core.config import DEFAULT_MODEL_DIR
from core.music_ai import convertir_mp3, resoudre_ffmpeg
from core.process import run_engine

# Kokoro-82M GGUF package (audio-cpp org, see MEMORY_BANK §1.21).
MODELE_KOKORO = os.getenv(
    "KOKORO_TTS_MODEL",
    os.path.join(DEFAULT_MODEL_DIR, "Kokoro-82M-GGUF", "kokoro-82m-q8_0.gguf"),
)

# Scratch binary with embedded espeak-ng (kokoro_tts unusable in the release,
# see docstring). Override: AUDIOCPP_KOKORO_CLI.
BINARIE_SCRATCH_KOKORO = (
    r"C:\IA\audio_cpp_master_test\build-357\bin\Release\audiocpp_cli.exe"
)

# Settings validated by the user (trial 17) — workflow defaults.
RECIPE = {
    "voice_id": "af_heart",
    "pitch": 1.30,        # asetrate = 24000 * pitch (1.30 = +30%)
    "ringmod_hz": 120.0,  # ring modulation frequency
    "tempo": 0.65,        # post-pitch atempo (0.65 = validated "quiet" rate)
    "gain_db": -4.0,      # final volume (validated "calm" voice)
}


def resoudre_audiocpp_kokoro() -> str:
    """Resolves an audiocpp binary able to run kokoro_tts (espeak present)."""
    surcharge = os.getenv("AUDIOCPP_KOKORO_CLI")
    if surcharge and os.path.exists(surcharge):
        return surcharge
    if os.path.exists(BINARIE_SCRATCH_KOKORO):
        return BINARIE_SCRATCH_KOKORO
    # Fallback: release binary (will fail on kokoro without shared espeak-ng —
    # the "Could not load eSpeak-ng" error stays explicit).
    from core.music_ai import resoudre_audiocpp
    return resoudre_audiocpp()


def generer_base_kokoro(
    texte: str,
    sortie: str,
    voice_id: str = "af_heart",
    speaking_rate: float = 1.0,
    backend: str = "vulkan",
) -> Dict[str, Any]:
    """Synthesizes English speech (Kokoro-82M, 24 kHz mono) before the robot effect."""
    if not os.path.exists(MODELE_KOKORO):
        raise FileNotFoundError(
            f"Kokoro-82M not found: {MODELE_KOKORO} — download it from "
            f"audio-cpp/Kokoro-82M-GGUF (scripts/telecharger_gros_fichier_parallele.py)."
        )
    audiocpp = resoudre_audiocpp_kokoro()
    cmd = [
        audiocpp, "--task", "tts", "--family", "kokoro_tts",
        "--model", MODELE_KOKORO, "--backend", backend,
        "--language", "en-us", "--voice-id", voice_id,
        "--metrics", "--out", sortie,
    ]
    if speaking_rate != 1.0:
        cmd += ["--speaking-rate", str(speaking_rate)]
    cmd += ["--text", texte]

    print(f"🤖 TTS Kokoro (voice {voice_id}, backend {backend}) — binary: {audiocpp}")
    run_engine(cmd, capture=False, check=True, timeout=600, etiquette="audio.cpp kokoro")
    if not os.path.exists(sortie):
        raise RuntimeError(f"The generation did not produce {sortie}")
    return {"sortie": sortie, "voice_id": voice_id}


def appliquer_effet_robot(
    source: str,
    sortie: str,
    pitch: float = RECIPE["pitch"],
    ringmod_hz: float = RECIPE["ringmod_hz"],
    tempo: float = RECIPE["tempo"],
    gain_db: float = RECIPE["gain_db"],
) -> str:
    """
    Validated "little robot" effect: pitch up (asetrate), settled rate (atempo),
    ring modulation (aeval, mono sine), final gain. Chain identical to trial 17.
    """
    ffmpeg = resoudre_ffmpeg()
    asetrate = int(24000 * pitch)
    filtre = (
        f"asetrate={asetrate},aresample=24000,atempo={tempo},"
        f"aeval='val(0)*sin(2*PI*{ringmod_hz:g}*t)',volume={gain_db:g}dB"
    )
    run_engine(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", source,
         "-af", filtre, "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", sortie],
        capture=False, check=True, timeout=180, etiquette="ffmpeg robot effect",
    )
    return sortie


def generer_voix_robot(
    texte: str,
    dossier: str,
    nom: str = "voix_robot",
    voice_id: str = RECIPE["voice_id"],
    pitch: float = RECIPE["pitch"],
    ringmod_hz: float = RECIPE["ringmod_hz"],
    tempo: float = RECIPE["tempo"],
    gain_db: float = RECIPE["gain_db"],
    speaking_rate: float = 1.0,
    backend: str = "vulkan",
) -> Dict[str, Any]:
    """Full pipeline: TTS base → robot effect → final WAV + listening MP3."""
    os.makedirs(dossier, exist_ok=True)
    wav_base = os.path.join(dossier, f"{nom}_brut.wav")
    wav_final = os.path.join(dossier, f"{nom}.wav")
    mp3_final = os.path.join(dossier, f"{nom}.mp3")

    generer_base_kokoro(texte, wav_base, voice_id=voice_id,
                        speaking_rate=speaking_rate, backend=backend)
    appliquer_effet_robot(wav_base, wav_final, pitch=pitch,
                          ringmod_hz=ringmod_hz, tempo=tempo, gain_db=gain_db)
    convertir_mp3(wav_final, mp3_final)
    return {"wav": wav_final, "mp3": mp3_final, "brut": wav_base}
