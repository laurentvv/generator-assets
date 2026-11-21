#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Word-timestamped subtitle factory (Qwen3-ForcedAligner-0.6B via audio.cpp).

Two engine paths (USER VALIDATED 2026-11-21, v2 page 3/3 — MEMORY_BANK §1.68):
- standalone align: EXACT transcript in -> word timestamps out. Short clips
  only (no upstream chunking), 14-70x real time Vulkan, q8_0 == f16 outputs.
- ASR -> aligner: long audio. Qwen3-ASR-0.6B produces the words (Silero VAD
  chunking exercised across > 15 s clips) and attaches word timestamps through
  the forced aligner session options. Input is resampled to 16 kHz mono first
  (Silero VAD is 16 kHz only) and the VAD weights must be provided — the
  portable install ships no default VAD assets.

Output JSON = [{"start_sample", "end_sample", "word", "confidence"}] in the
sample domain of the file actually fed to the engine; `ecrire_srt_mots`
converts it to a word-level SRT (80 ms timestamp grid = subtitle grade).
"""

import json
import os
import subprocess
import wave
from typing import Any, Dict, List, Optional, Tuple

from core.config import DEFAULT_MODEL_DIR
from core.music_ai import resoudre_audiocpp, resoudre_ffmpeg
from core.process import run_engine
from core.voix_off import MODELE_QWEN3_ASR

# GGUF paths (overridable via environment variables). The aligner GGUFs sit
# flat in the models dir, unlike the ASR package folder.
MODELE_FORCED_ALIGNER = os.getenv(
    "QWEN3_FORCED_ALIGNER_MODEL",
    os.path.join(DEFAULT_MODEL_DIR, "qwen3-forced-aligner-0.6b-q8_0.gguf"),
)
MODELE_FORCED_ALIGNER_F16 = os.getenv(
    "QWEN3_FORCED_ALIGNER_F16_MODEL",
    os.path.join(DEFAULT_MODEL_DIR, "qwen3-forced-aligner-0.6b-f16.gguf"),
)
# Silero VAD weights directory (16 kHz only) — the engine wants the DIRECTORY.
DOSSIER_VAD_SILERO = os.getenv("QWEN3_VAD_DIR", r"C:\Modeles_LLM\vad\silero_vad")

TAUX_SILERO = 16000
# Upstream doc pin (docs/models/qwen3_forced_aligner.md @ main, fetched 11-21):
# standalone align does NOT chunk audio — keep clips short (one transcript/audio pair).
DUREE_ALIGN_STANDALONE_MAX_S = 15.0


def duree_audio(chemin_audio: str) -> Optional[float]:
    """Returns the audio duration in seconds (stdlib wave) or None if unreadable."""
    try:
        with wave.open(chemin_audio, "rb") as lecteur:
            return lecteur.getnframes() / float(lecteur.getframerate())
    except Exception:
        return None


def _resoudre_modele_aligner(quant: str) -> str:
    """Resolves the aligner GGUF for the requested quantization."""
    modele = MODELE_FORCED_ALIGNER_F16 if quant == "f16" else MODELE_FORCED_ALIGNER
    if not os.path.exists(modele):
        raise FileNotFoundError(
            f"Aligner GGUF not found: {modele} — fetch audio-cpp/audio.cpp-gguf/Qwen3-ForcedAligner-0.6B-GGUF/"
        )
    return modele


def _taux_echantillonnage(chemin_audio: str) -> int:
    """Reads the sample rate of a WAV file (stdlib wave, ffprobe fallback)."""
    try:
        with wave.open(chemin_audio, "rb") as lecteur:
            return lecteur.getframerate()
    except Exception:
        ffprobe = os.path.join(os.path.dirname(resoudre_ffmpeg()), "ffprobe.exe")
        if not os.path.exists(ffprobe):
            ffprobe = "ffprobe"
        retour = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=sample_rate", "-of", "default=nw=1:nk=1",
             chemin_audio],
            capture_output=True, text=True, timeout=60, check=True,
        )
        return int(retour.stdout.strip().splitlines()[0])


def _resampler_16k_mono(chemin_audio: str, chemin_sortie: str) -> str:
    """Resamples the input to 16 kHz mono WAV (Silero VAD requirement)."""
    ffmpeg = resoudre_ffmpeg()
    run_engine(
        [ffmpeg, "-y", "-i", chemin_audio, "-ar", str(TAUX_SILERO), "-ac", "1",
         chemin_sortie],
        capture=True, check=True, timeout=300, etiquette="resample 16k mono",
    )
    return chemin_sortie


def aligner_mots(
    chemin_audio: str,
    transcript: str,
    chemin_json: str,
    langue: str = "fr",
    quant: str = "q8_0",
    backend: str = "vulkan",
) -> Tuple[List[Dict[str, Any]], int]:
    """Standalone forced alignment: EXACT transcript -> word timestamps.

    Returns (words, sample_rate_of_input). Raises ValueError on a transcript
    that does not match the audio exactly (align is not ASR).
    """
    if not transcript or not transcript.strip():
        raise ValueError("Standalone align needs the EXACT transcript (workflow prompt -p).")
    modele = _resoudre_modele_aligner(quant)
    run_engine(
        [resoudre_audiocpp(), "--task", "align", "--family", "qwen3_forced_aligner",
         "--model", modele, "--backend", backend, "--audio", chemin_audio,
         "--text", transcript, "--language", langue,
         "--words-out", chemin_json, "--metrics"],
        capture=True, check=True, timeout=300, etiquette="forced align",
    )
    mots = _lire_mots(chemin_json)
    return mots, _taux_echantillonnage(chemin_audio)


def transcrire_aligner(
    chemin_audio: str,
    chemin_json: str,
    langue: str = "fr",
    backend: str = "vulkan",
    quant: str = "q8_0",
    vad_dir: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], str, int]:
    """Long-audio path: Qwen3-ASR-0.6B words + forced-aligner timestamps.

    Resamples the input to 16 kHz mono, runs the ASR with the aligner + Silero
    VAD session options, returns (words, transcript_text, sample_rate). The
    transcript is taken from the engine stdout (words JSON carries timestamps).
    `vad_dir` overrides the Silero weights directory (default: DOSSIER_VAD_SILERO).
    """
    dossier_vad = vad_dir or DOSSIER_VAD_SILERO
    if not os.path.isdir(dossier_vad):
        raise FileNotFoundError(
            f"Silero VAD weights directory not found: {dossier_vad} — the portable "
            "install ships no default VAD assets (MEMORY_BANK §1.68 gotcha ①)"
        )
    audio_16k = os.path.splitext(chemin_json)[0] + "_src16k.wav"
    _resampler_16k_mono(chemin_audio, audio_16k)
    modele = _resoudre_modele_aligner(quant)
    retour = run_engine(
        [resoudre_audiocpp(), "--task", "asr", "--family", "qwen3_asr",
         "--model", MODELE_QWEN3_ASR, "--backend", backend, "--language", langue,
         "--audio", audio_16k, "--words-out", chemin_json,
         "--session-option", f"qwen3_asr.forced_aligner_path={modele}",
         "--session-option", f"qwen3_asr.vad_model_path={dossier_vad}"],
        capture=True, check=True, timeout=1800, etiquette="asr words + aligner",
    )
    transcript = os.path.splitext(chemin_json)[0] + "_transcript.txt"
    texte = (retour.stdout or "").strip()
    with open(transcript, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(texte + "\n")
    mots = _lire_mots(chemin_json)
    return mots, texte, TAUX_SILERO


def _lire_mots(chemin_json: str) -> List[Dict[str, Any]]:
    """Loads the engine words JSON and sanity-checks monotonicity in seconds."""
    with open(chemin_json, "r", encoding="utf-8") as handle:
        mots = json.load(handle)
    if not isinstance(mots, list) or not mots:
        raise ValueError(f"Empty or malformed words JSON: {chemin_json}")
    return mots


def ecrire_srt_mots(mots: List[Dict[str, Any]], taux: int, chemin_srt: str) -> str:
    """Converts the engine words JSON to a word-level SRT (one cue per word)."""
    def horodatage_ms(ms: int) -> str:
        ms = max(0, ms)
        heures, reste = divmod(ms, 3_600_000)
        minutes, reste = divmod(reste, 60_000)
        secondes, ms = divmod(reste, 1000)
        return f"{heures:02d}:{minutes:02d}:{secondes:02d},{ms:03d}"

    blocs = []
    for index, mot in enumerate(mots):
        ms_debut = int(round(mot["start_sample"] / float(taux) * 1000))
        ms_fin = int(round(mot["end_sample"] / float(taux) * 1000))
        if ms_fin <= ms_debut:
            ms_fin = ms_debut + 1  # zero/negative cues are invalid SRT
        blocs.append(f"{index + 1}\n{horodatage_ms(ms_debut)} --> {horodatage_ms(ms_fin)}\n{mot['word']}\n")
    with open(chemin_srt, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(blocs))
    return chemin_srt
