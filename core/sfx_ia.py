#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI sound-effect (SFX) generation: Stable Audio 3 Small SFX via audio.cpp.

Engine validated by the user on 2026-09-09 (4/5 samples "ok": sword, gravel
steps, door, whoosh) on the Godot game use-case SFX — RTF ~0.2 Vulkan,
fastest on this machine.

Built-in processing (from the listening iterations on the rain/thunder sample):
- **Prompt selection = first quality lever.** The model can output unbalanced
  textures: "heavy rain on window glass, distant thunder rumble" produces a
  50-250 Hz rumble at +18 dB with the HF crackle at −17..−28 dB ("muffled",
  user verdict); "heavy rain falling on glass, dense patter with natural
  splashes" is spectrally balanced (HF/LF ≈ −2 dB). Naming THE CONTENT (patter,
  splashes) rather than the ambience (thunder rumble) steers the spectrum.
- **Trimming of leading/trailing silences**: SA3 fades out the tail (up to several
  silent seconds) — automatic edge trimming below −45 dBFS (safety guard:
  never more than 50% of the file).
- **Two level treatments** (volume alone is not enough, "sound too low" verdict):
  "pad" texture (I < threshold) = gain toward the LUFS target + ceiling limiter
  (alimiter — only touches the peaks that exceed it, preserves the crackle; the
  1st version with acompressor threshold −20 dB crushed the texture modulation
  and muffled it further); transient SFX = simple peak normalization
  (historical behavior, validated samples unchanged).

Built-in pitfalls:
- SA3 output = 44.1 kHz stereo (the historical sfx workflow was procedural mono;
  the Godot WAV/OGG export accepts both)
- OGG forbidden via soundfile (libsndfile stack overflow, rule §1.10) — the final
  export goes through exporter_sfx_godot (ffmpeg); this module only produces the intermediate WAV
"""

import os
import re
import tempfile
from typing import Any, Dict

import numpy as np
import soundfile as sf

from core.music_ai import mesurer_lufs, resoudre_audiocpp, resoudre_ffmpeg
from core.process import run_engine

MODELE_SA3_SFX = os.getenv(
    "SA3_SFX_MODEL",
    os.path.join(
        "C:\\Modeles_LLM",
        "Stable-Audio-3-Small-SFX-GGUF",
        "stable-audio-3-small-sfx-f16.gguf",
    ),
)

# Peak normalization (~ -0.9 dBFS): same convention as the procedural synthesis (0.9).
PIC_CIBLE = 0.9

# "Pad" texture: detection threshold, body loudness target and peak ceiling.
SEUIL_NAPPE_LUFS = -20.0
LUFS_CIBLE_NAPPE = -16.0
PLAFOND_DBFS = -1.5

# Trimming of leading/trailing silences (structural SA3 fade).
SEUIL_ROGNAGE_DB = -45.0
MARGE_ROGNAGE_S = 0.05
MAX_ROGNAGE_FRAC = 0.5


def _rogner_silences(audio: np.ndarray, sr: int) -> np.ndarray:
    """Cuts the silent edges (approx. 20 ms RMS below SEUIL_ROGNAGE_DB, margin kept).

    Safety guard: no trimming if more than MAX_ROGNAGE_FRAC of the file would
    disappear (degenerate generation — left as is).
    """
    mono = audio.mean(axis=1) if audio.ndim > 1 else audio
    w = max(int(sr * 0.02), 1)
    env = np.sqrt(np.convolve(mono.astype(np.float64) ** 2, np.ones(w) / w, mode="same"))
    db = 20 * np.log10(env + 1e-12)
    actifs = np.where(db > SEUIL_ROGNAGE_DB)[0]
    if actifs.size == 0:
        return audio
    marge = int(MARGE_ROGNAGE_S * sr)
    i0 = max(0, int(actifs[0]) - marge)
    i1 = min(len(audio), int(actifs[-1]) + 1 + marge)
    if (i1 - i0) < int(len(audio) * MAX_ROGNAGE_FRAC):
        return audio
    return audio[i0:i1]


def _traiter_loudness_nappe(chemin_wav: str, gain_db: float) -> None:
    """Raises the signal body toward LUFS_CIBLE_NAPPE and caps the peaks (in place).

    Linear gain then alimiter: the limiter only touches the peaks that exceed
    the ceiling — the texture (crackle modulation) stays intact. An earlier
    version with a fixed acompressor threshold crushed the texture itself (muffled rendering).
    """
    ffmpeg = resoudre_ffmpeg()
    chaine = (
        f"volume={gain_db:.2f}dB,"
        f"alimiter=limit={10 ** (PLAFOND_DBFS / 20):.4f}:attack=2:release=50:level=disabled"
    )
    tmp = chemin_wav + ".lufs.wav"
    try:
        run_engine(
            [ffmpeg, "-hide_banner", "-y", "-i", chemin_wav, "-af", chaine,
             "-ar", "44100", "-c:a", "pcm_s16le", tmp],
            check=True, timeout=180, etiquette="ffmpeg sfx normalization",
        )
        os.replace(tmp, chemin_wav)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def generer_sfx_ia(
    prompt: str,
    duree: float = 2.0,
    seed: int = 42,
    backend: str = "vulkan",
) -> Dict[str, Any]:
    """
    Generates an AI sound effect (stable_audio, text → audio).
    Returns {"audio": float32 (stereo), "sr": 44100, "rtf": float|None,
    "pic_source": float, "niveau_mode": "crete"|"nappe", "lufs_source": float|None,
    "rognage_pct": float}.
    Seed < 0 = leave the runtime default (deterministic).
    """
    if not os.path.exists(MODELE_SA3_SFX):
        raise FileNotFoundError(
            f"SA3 Small SFX package not found: {MODELE_SA3_SFX} — download it from "
            f"audio-cpp/audio.cpp-gguf (Stable-Audio-3-Small-SFX-GGUF/stable-audio-3-small-sfx-f16.gguf, "
            f"2.20 GiB; parallel downloader recommended)."
        )

    fd, wav_brut = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    cmd = [
        resoudre_audiocpp(), "--task", "gen", "--family", "stable_audio",
        "--model", MODELE_SA3_SFX, "--backend", backend, "--metrics",
        "--text", prompt, "--duration-seconds", str(float(duree)),
        "--out", wav_brut,
    ]
    if seed is not None and seed >= 0:
        cmd += ["--seed", str(int(seed))]

    try:
        res = run_engine(
            cmd, check=False, capture=True,
            timeout=int(duree * 10 + 300), etiquette="audio.cpp sfx",
        )
        if res.returncode != 0 or not os.path.exists(wav_brut):
            extrait = (res.stderr or res.stdout or "").strip()[-400:]
            raise RuntimeError(f"AI SFX generation failed (exit {res.returncode}): {extrait}")

        rtf = None
        m = re.search(r"metrics\.rtf=([\d.]+)", res.stdout)
        if m:
            rtf = float(m.group(1))

        audio, sr = sf.read(wav_brut, always_2d=False, dtype="float32")

        # Trimming of structural lead-in/out fades/silences.
        taille_avant = len(audio)
        audio = _rogner_silences(audio, sr)
        rognage_pct = 100.0 * (1.0 - len(audio) / max(taille_avant, 1))
        if rognage_pct > 0.01:
            sf.write(wav_brut, audio, sr, subtype="PCM_16", format="WAV")

        # Level treatment: pad (gain + ceiling) or simple peak.
        lufs_source = None
        niveau_mode = "crete"
        gain_db = 0.0
        try:
            mesures = mesurer_lufs(wav_brut)
            lufs_source = mesures["I"]
        except RuntimeError:
            mesures = None
        if mesures and mesures["I"] < SEUIL_NAPPE_LUFS:
            niveau_mode = "nappe"
            gain_db = LUFS_CIBLE_NAPPE - mesures["I"]
            _traiter_loudness_nappe(wav_brut, gain_db)
            audio, sr = sf.read(wav_brut, always_2d=False, dtype="float32")
    finally:
        if os.path.exists(wav_brut):
            os.remove(wav_brut)

    pic = float(np.max(np.abs(audio))) if audio.size else 0.0
    if pic > 0:
        audio = (audio / pic) * PIC_CIBLE

    return {
        "audio": audio.astype(np.float32), "sr": int(sr), "rtf": rtf,
        "pic_source": pic, "niveau_mode": niveau_mode, "lufs_source": lufs_source,
        "gain_db": round(gain_db, 1), "rognage_pct": round(rognage_pct, 1),
    }
