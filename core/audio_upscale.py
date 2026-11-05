#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio super-resolution → 48 kHz via UniverSR (audio.cpp, `universr` family).

Recipe VALIDATED by the user on 2026-09-18 (MEMORY_BANK §1.27):
- Voice 16 kHz → 48 kHz (`speech` package): "bug-free copy, even perfect".
- Music 24 kHz → 48 kHz (`audio` package): "very good, nice drums".

⚠️ Engine state — VERSION-BOUND, retest at every audio.cpp update
(MEMORY_BANK §1.27, measured 2026-11-05 on v0.9.4):
- Vulkan WORKS on this family again for short inputs — the v0.8.1
  "unsupported backend op 'MUL_MAT'" refusal was silently lifted upstream
  between v0.8.2 and v0.9.4 (no fix announced in any release note) — but
  only up to ~14 s of input: ≥15 s fails deterministically with the same
  "UniverSR conditioning contains unsupported backend op 'MUL_MAT'" error
  (graph-size ceiling). On the lengths it accepts, Vulkan is
  bit-equivalent-class to CPU (same seed: correlation 1.00000, max 12 LSB,
  all bands ≤0.03 dB incl. 12-24 kHz, both speech and audio packages) at
  RTF ~1.5-2.2 instead of ~41-50 → `backend="auto"` (default) tries Vulkan
  first and falls back to CPU (like core/music_ai.py), so whole scenes
  (45 s class, the production voice-over case) keep the exact pre-11-05
  CPU behavior until an upstream fix.
- CPU RTF measured 41-50 on v0.9.4 (10-12 s clips, 20 threads) — slower
  than the ~13.3 of the v0.8.1 campaign; budget minutes, not seconds.
- MONO output only (stereo input is swallowed) — voice over, the main
  use case, is natively mono.
- Chunked inference (`audio_chunk_duration_sec`) would let long inputs
  avoid the ceiling but changes the global normalization context per
  chunk → output differs from the ear-validated CPU whole-file recipe;
  deliberately NOT wired.

Input bands exposed by the spec: 8000/12000/16000/24000 Hz. The file
is automatically resampled (FFmpeg) to the declared band if its
frequency differs; above 24 kHz the input is already full band →
refusal (super-resolution no longer makes sense).
"""

import os
import shutil
from typing import Any, Dict

from core.music_ai import resoudre_audiocpp, resoudre_ffmpeg
from core.process import EngineError, run_engine

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
    "threads": 20,         # CPU fallback (i7-13700KF) — used above the Vulkan ~14 s ceiling
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
    backend: str = "auto",
) -> Dict[str, Any]:
    """Full pipeline: auto/forced band → pre-resampling → UniverSR (Vulkan → CPU).

    `backend`: "auto" (default) = Vulkan first, CPU fallback on engine failure
    (pattern of core/music_ai.py); "vulkan"/"cpu" force one backend. The
    fallback is what keeps long inputs (>~14 s MUL_MAT ceiling, v0.9.4)
    working — see the module docstring for the measured, version-bound state.
    MONO 48 kHz WAV output (engine limit).
    """
    essais = {"auto": ("vulkan", "cpu"), "vulkan": ("vulkan",), "cpu": ("cpu",)}[backend]
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

    binaire = resoudre_audiocpp()
    if essais[0] == "vulkan":
        print(f"🧪 UniverSR ({variante}, band {bande} Hz, Vulkan first — "
              f"RTF ~1.5-2.2; CPU fallback above the ~14 s ceiling)")
    else:
        print(f"🧪 UniverSR ({variante}, band {bande} Hz, CPU {threads} threads — "
              f"RTF ~41-50 measured, expect several minutes)")
    backend_utilise = essais[-1]
    for i, backend_cible in enumerate(essais):
        if i:
            print(f"🔄 New attempt: backend={backend_cible} (RTF ~41-50 on CPU, "
                  f"expect several minutes)...")
        cmd = [
            binaire, "--task", "s2s", "--family", "universr",
            "--model", modele, "--backend", backend_cible, "--threads", str(threads),
            "--audio", entree,
            "--request-option", f"input_sample_rate={bande}",
            "--request-option", f"num_inference_steps={steps}",
            "--request-option", f"seed={seed}",
            "--metrics", "--out", sortie,
        ]
        try:
            run_engine(cmd, capture=False, check=True, timeout=7200,
                       etiquette=f"audio.cpp universr ({backend_cible})")
            backend_utilise = backend_cible
            break
        except EngineError:
            if i == len(essais) - 1:
                raise
    if entree != source:
        os.remove(entree)
    if not os.path.exists(sortie):
        raise RuntimeError(f"The restoration did not produce {sortie}")
    return {"sortie": sortie, "bande": bande, "variante": variante,
            "frequence_source": frequence, "backend": backend_utilise}
