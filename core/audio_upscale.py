#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio super-resolution → 48 kHz via UniverSR (audio.cpp, `universr` family).

Recipe VALIDATED by the user on 2026-09-18 (MEMORY_BANK §1.27):
- Voice 16 kHz → 48 kHz (`speech` package): "bug-free copy, even perfect".
- Music 24 kHz → 48 kHz (`audio` package): "very good, nice drums".

⚠️ Engine limits (audio.cpp v0.8.1):
- broken Vulkan backend ("UniverSR conditioning contains unsupported backend op
  'MUL_MAT'") → CPU MANDATORY, RTF ~13 (28 s → ~6 min; a 3-minute voice
  over → ~40 min). To be retested if a Vulkan path lands upstream.
- MONO output only (stereo input is swallowed) — voice over, the main
  use case, is natively mono.

Input bands exposed by the spec: 8000/12000/16000/24000 Hz. The file
is automatically resampled (FFmpeg) to the declared band if its
frequency differs; above 24 kHz the input is already full band →
refusal (super-resolution no longer makes sense).
"""

import os
import shutil
from typing import Any, Dict

from core.music_ai import resoudre_audiocpp, resoudre_ffmpeg
from core.process import run_engine

# UniverSR GGUF packages (audio-cpp org, 229 MB each — see MEMORY_BANK §1.27).
MODELE_UNIVERSR_AUDIO = os.getenv(
    "UNIVERSR_AUDIO_MODEL",
    os.path.join("C:\\Modeles_LLM", "UniverSR-GGUF", "universr-audio-orig.gguf"),
)
MODELE_UNIVERSR_SPEECH = os.getenv(
    "UNIVERSR_SPEECH_MODEL",
    os.path.join("C:\\Modeles_LLM", "UniverSR-GGUF", "universr-speech-orig.gguf"),
)

# Default settings (validated recipe — steps/seed = spec defaults).
RECIPE = {
    "variante": "speech",  # speech = voice over (main case) | audio = music
    "steps": 4,            # ODE integration steps (midpoint sampler)
    "seed": 42,            # flow noise seed (A/B reproducibility)
    "threads": 20,         # CPU (i7-13700KF) — Vulkan unavailable on this family
}

# Input bands exposed by the universr spec.
BANDES_AUTORISEES = (8000, 12000, 16000, 24000)
BANDE_MAX = 24000


def resoudre_modele(variante: str) -> str:
    """Path of the UniverSR GGUF for the requested variant (speech|audio)."""
    if variante == "speech":
        modele = MODELE_UNIVERSR_SPEECH
    elif variante == "audio":
        modele = MODELE_UNIVERSR_AUDIO
    else:
        raise ValueError(f"Unknown UniverSR variant: {variante} (speech|audio).")
    if not os.path.exists(modele):
        raise FileNotFoundError(
            f"UniverSR GGUF not found: {modele} — downloadable from "
            f"audio-cpp/audio.cpp-gguf (UniverSR-GGUF folder)."
        )
    return modele


def detecter_frequence(chemin: str) -> int:
    """Sample rate of the first audio stream (ffprobe)."""
    probe = shutil.which("ffprobe")
    if not probe:
        voisin = os.path.join(os.path.dirname(resoudre_ffmpeg()), "ffprobe.exe")
        probe = voisin if os.path.exists(voisin) else "ffprobe"
    out = run_engine(
        [probe, "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=sample_rate", "-of", "csv=p=0", chemin],
        check=True, timeout=60, etiquette="ffprobe frequency",
    ).stdout.strip()
    return int(out or 0)


def choisir_bande(frequence: int, bande_forcee: int = 0) -> int:
    """Input band to declare to the model (8000/12000/16000/24000).

    Forced band (--upsr-rate) = full control (file resampled
    to it). Otherwise: the file frequency if it is a supported band,
    otherwise the largest supported band BELOW that frequency (22050 → 16000,
    11025 → 8000...); above 24 kHz → refusal (already full band).
    """
    if bande_forcee:
        if bande_forcee not in BANDES_AUTORISEES:
            raise ValueError(
                f"Band {bande_forcee} Hz not supported by universr "
                f"(allowed: {', '.join(map(str, BANDES_AUTORISEES))})."
            )
        return bande_forcee
    if frequence in BANDES_AUTORISEES:
        return frequence
    candidates = [b for b in BANDES_AUTORISEES if b < frequence]
    if not candidates:
        raise ValueError(
            f"Input at {frequence} Hz: above the universr max band "
            f"({BANDE_MAX} Hz) — already full band, super-resolution pointless. "
            f"Force a band with --upsr-rate if that is intended."
        )
    return max(candidates)


def restaurer_universr(
    source: str,
    sortie: str,
    variante: str = RECIPE["variante"],
    bande: int = 0,
    steps: int = RECIPE["steps"],
    seed: int = RECIPE["seed"],
    threads: int = RECIPE["threads"],
) -> Dict[str, Any]:
    """Full pipeline: auto/forced band → pre-resampling → UniverSR CPU.

    MONO 48 kHz WAV output (engine limit, see module docstring).
    """
    modele = resoudre_modele(variante)
    frequence = detecter_frequence(source)
    if frequence <= 0:
        raise ValueError(f"Unreadable audio track or no audio stream: {source}")
    bande = choisir_bande(frequence, bande)

    entree = source
    if frequence != bande:
        ffmpeg = resoudre_ffmpeg()
        entree = os.path.splitext(sortie)[0] + f"_entree_{bande}.wav"
        print(f"🎚️ Pre-resampling {frequence} → {bande} Hz (band declared to the model)")
        run_engine(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", source,
             "-af", f"aresample={bande}", "-ac", "1", "-c:a", "pcm_s16le", entree],
            capture=False, check=True, timeout=600, etiquette="ffmpeg band resample",
        )

    cmd = [
        resoudre_audiocpp(), "--task", "s2s", "--family", "universr",
        "--model", modele, "--backend", "cpu", "--threads", str(threads),
        "--audio", entree,
        "--request-option", f"input_sample_rate={bande}",
        "--request-option", f"num_inference_steps={steps}",
        "--request-option", f"seed={seed}",
        "--metrics", "--out", sortie,
    ]
    print(f"🧪 UniverSR ({variante}, band {bande} Hz, CPU {threads} threads — "
          f"RTF ~13, expect several minutes)")
    # Live progress: RTF ~13 on CPU (28 s → ~6 min, 3-min voice → ~40 min)
    run_engine(cmd, capture=False, check=True, timeout=7200, etiquette="audio.cpp universr")
    if entree != source:
        os.remove(entree)
    if not os.path.exists(sortie):
        raise RuntimeError(f"The restoration did not produce {sortie}")
    return {"sortie": sortie, "bande": bande, "variante": variante,
            "frequence_source": frequence}
