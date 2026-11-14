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

from core.config import DEFAULT_BS_ROFORMER_MODEL, DEFAULT_MEL_ROFORMER_MODEL
from core.music_ai import convertir_mp3, resoudre_audiocpp, resoudre_ffmpeg
from core.process import run_engine

MODELE_HTDEMUCS = os.getenv(
    "HTDEMUCS_MODEL",
    os.path.join("C:\\Modeles_LLM", "HTDemucs-GGUF", "htdemucs-f16.gguf"),
)
MODELE_MEL_ROFORMER = os.getenv("MEL_ROFORMER_MODEL", DEFAULT_MEL_ROFORMER_MODEL)
MODELE_BS_ROFORMER = os.getenv("BS_ROFORMER_MODEL", DEFAULT_BS_ROFORMER_MODEL)
SR_HDEMUCS = 44100
STEMS_INSTRUMENTAL = ("drums", "bass", "other")

# RoFormer separation families validated in Wave 1 (2026-11-14).
_ROFORMER_SPECS = {
    "mel_roformer": ("mel_band_roformer", lambda: MODELE_MEL_ROFORMER, "Mel-Band RoFormer"),
    "bs_roformer": ("bs_roformer", lambda: MODELE_BS_ROFORMER, "BS-RoFormer"),
}

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


def _preparer_audio_44k(chemin_audio: str, wav_dest: str) -> str:
    """Resamples any audio input to 44.1 kHz stereo PCM16 WAV (separation contract)."""
    ffmpeg = resoudre_ffmpeg()
    run_engine(
        [ffmpeg, "-hide_banner", "-y", "-i", chemin_audio,
         "-ar", str(SR_HDEMUCS), "-ac", "2", "-c:a", "pcm_s16le", wav_dest],
        check=True, timeout=600, etiquette="ffmpeg 44k resampling",
    )
    return wav_dest


def retirer_voix(
    chemin_audio: str,
    dossier_travail: str,
    backend: str = "vulkan",
    moteur: str = "htdemucs",
    apollo: bool = False,
) -> Dict[str, Any]:
    """
    Separates audio into stems and builds the vocal-free instrumental.

    Engines supported:
    - ``htdemucs`` (default, 4 stems: drums/bass/other/vocals)
    - ``mel_roformer`` (Mel-Band RoFormer 2-stem, RTF ~0.20 Vulkan, Wave 1 validated)
    - ``bs_roformer`` (BS-RoFormer ep368 2-stem, RTF ~1.44 Vulkan, Wave 1 validated)

    When ``apollo=True``, polishes the separated instrumental via Apollo 44.1 kHz
    (-1 dBTP peak guard). Returns {instrumental_wav, instrumental_mp3, stems_dir, voix_wav}.
    """
    engine = (moteur or "htdemucs").lower()
    if engine in _ROFORMER_SPECS:
        family, get_model, display_name = _ROFORMER_SPECS[engine]
        modele = get_model()
        if not os.path.exists(modele):
            raise FileNotFoundError(f"{display_name} package not found: {modele}")
    elif engine == "htdemucs":
        modele = MODELE_HTDEMUCS
        if not os.path.exists(modele):
            raise FileNotFoundError(
                f"HTDemucs package not found: {modele} — download it from "
                f"audio-cpp/audio.cpp-gguf (HTDemucs-GGUF/htdemucs-f16.gguf, 84 MB)."
            )
    else:
        raise ValueError(
            f"Unknown separation engine '{moteur}' (choices: htdemucs, mel_roformer, bs_roformer)."
        )

    ffmpeg = resoudre_ffmpeg()
    os.makedirs(dossier_travail, exist_ok=True)
    wav44 = _preparer_audio_44k(chemin_audio, os.path.join(dossier_travail, "source_44k.wav"))
    stems_dir = os.path.join(dossier_travail, "stems")
    os.makedirs(stems_dir, exist_ok=True)
    instrumental_raw = os.path.join(dossier_travail, "instrumental_raw.wav")
    instrumental = os.path.join(dossier_travail, "instrumental.wav")

    if engine in _ROFORMER_SPECS:
        run_engine(
            [resoudre_audiocpp(), "--task", "sep", "--family", family,
             "--model", modele, "--backend", backend, "--threads", "16",
             "--audio", wav44, "--out-dir", stems_dir, "--log", "--metrics"],
            capture=False, check=True, timeout=3600, etiquette=f"audio.cpp {family}",
        )
        manquants = [s for s in ("vocals", "instrumental")
                     if not os.path.exists(os.path.join(stems_dir, f"{s}.wav"))]
        if manquants:
            raise RuntimeError(f"Missing {display_name} stems: {', '.join(manquants)}")
        src_inst = os.path.join(stems_dir, "instrumental.wav")
        shutil.copy2(src_inst, instrumental_raw if apollo else instrumental)
    else:
        run_engine(
            [resoudre_audiocpp(), "--task", "sep", "--family", "htdemucs",
             "--model", modele, "--backend", backend, "--threads", "16",
             "--audio", wav44, "--out-dir", stems_dir],
            capture=False, check=True, timeout=3600, etiquette="audio.cpp htdemucs",
        )
        manquants = [s for s in STEMS_INSTRUMENTAL + ("vocals",)
                     if not os.path.exists(os.path.join(stems_dir, f"{s}.wav"))]
        if manquants:
            raise RuntimeError(f"Missing HTDemucs stems: {', '.join(manquants)}")

        entrees: list = []
        for s in STEMS_INSTRUMENTAL:
            entrees += ["-i", os.path.join(stems_dir, f"{s}.wav")]
        filtre = "".join(f"[{i}:a]" for i in range(len(STEMS_INSTRUMENTAL)))
        filtre += f"amix=inputs={len(STEMS_INSTRUMENTAL)}:normalize=0"
        cible_mix = instrumental_raw if apollo else instrumental
        run_engine(
            [ffmpeg, "-hide_banner", "-y", *entrees, "-filter_complex", filtre,
             "-c:a", "pcm_s16le", cible_mix],
            check=True, timeout=600, etiquette="ffmpeg amix instrumental",
        )

    if apollo:
        from core.audio_restore import restaurer_apollo
        restaurer_apollo(instrumental_raw, instrumental, backend=backend)

    mp3 = convertir_mp3(instrumental, instrumental.replace(".wav", ".mp3"), 192)
    return {
        "instrumental_wav": instrumental,
        "instrumental_mp3": mp3,
        "stems_dir": stems_dir,
        "voix_wav": os.path.join(stems_dir, "vocals.wav"),
        "moteur": engine,
        "apollo": apollo,
    }
