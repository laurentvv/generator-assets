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
import shutil
from typing import Any, Dict

from core.music_ai import convertir_mp3, resoudre_audiocpp, resoudre_ffmpeg
from core.process import run_engine

MODELE_HTDEMUCS = os.getenv(
    "HTDEMUCS_MODEL",
    os.path.join("C:\\Modeles_LLM", "HTDemucs-GGUF", "htdemucs-f16.gguf"),
)
SR_HDEMUCS = 44100
STEMS_INSTRUMENTAL = ("drums", "bass", "other")

# SAM Audio (text-prompted separation) — engine support = upstream PR #711, shipped in
# the production audio.cpp v0.9.0 (installed 2026-09-30). Validated on the scratch build
# 2026-09-28, validated on the production binary 2026-10-01 (night leg sam_cpu_929:
# 30 s excerpt, 91 s, RTF ~3.0 vs 2.9 on the scratch). Scratch build retired.
BINAIRE_SAM_AUDIO = os.getenv(
    "SAM_AUDIO_ENGINE",
    os.path.join("C:\\audio-cpp", "audiocpp_cli.exe"),
)
MODELE_SAM_AUDIO = os.getenv(
    "SAM_AUDIO_MODEL",
    os.path.join("C:\\Modeles_LLM", "SAM-Audio-GGUF", "sam-audio-small-q8_0.gguf"),
)


def separate_sam_audio(chemin_audio: str, dossier_travail: str, texte: str = "the singing voice") -> Dict[str, Any]:
    """
    Separates a text-described sound (default: the singing voice) via SAM Audio.
    User-validated 2026-09-28 (A/B vs HTDemucs on a sung-voice excerpt).
    Returns the paths {instrumental_wav, instrumental_mp3, stems_dir, voix_wav}
    (same contract as retirer_voix: target = voix, residual = instrumental).
    """
    if not os.path.exists(BINAIRE_SAM_AUDIO):
        raise FileNotFoundError(
            f"SAM-Audio-capable audio.cpp binary not found: {BINAIRE_SAM_AUDIO} — "
            f"update audio.cpp to >= v0.9.0 (C:\\audio-cpp\\update.ps1) or point "
            f"SAM_AUDIO_ENGINE at a newer binary."
        )
    if not os.path.exists(MODELE_SAM_AUDIO):
        raise FileNotFoundError(
            f"SAM Audio GGUF not found: {MODELE_SAM_AUDIO} — download it from "
            f"audio-cpp/SAM-Audio-GGUF (small or base q8_0)."
        )
    os.makedirs(dossier_travail, exist_ok=True)

    # The source is fed AS-IS (no resample — unlike HTDemucs, SAM Audio has no
    # input-rate requirement and resamples itself to 48 kHz mono; the validated
    # recipe fed the raw file, and double resampling measurably alters samples).
    sortie_sam = os.path.join(dossier_travail, "sam")
    os.makedirs(sortie_sam, exist_ok=True)
    run_engine(
        [BINAIRE_SAM_AUDIO, "--task", "s2s", "--family", "sam_audio",
         "--model", MODELE_SAM_AUDIO, "--backend", "cpu", "--threads", "16",
         "--audio", chemin_audio, "--text", texte, "--seed", "42",
         "--out-dir", sortie_sam],
        capture=False, check=True, timeout=3600, etiquette="audio.cpp sam_audio",
    )
    cible = os.path.join(sortie_sam, "target.wav")
    residu = os.path.join(sortie_sam, "residual.wav")
    manquants = [n for n, p in (("target.wav", cible), ("residual.wav", residu))
                 if not os.path.exists(p)]
    if manquants:
        raise RuntimeError(f"Missing SAM Audio outputs: {', '.join(manquants)}")

    # 3) Contract identical to retirer_voix: voix.wav + instrumental.wav + mp3
    voix = os.path.join(dossier_travail, "voix.wav")
    instrumental = os.path.join(dossier_travail, "instrumental.wav")
    shutil.copyfile(cible, voix)
    shutil.copyfile(residu, instrumental)
    mp3 = convertir_mp3(instrumental, instrumental.replace(".wav", ".mp3"), 192)
    return {
        "instrumental_wav": instrumental,
        "instrumental_mp3": mp3,
        "stems_dir": sortie_sam,
        "voix_wav": voix,
    }


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
