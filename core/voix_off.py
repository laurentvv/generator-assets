#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Voice-over generation via local TTS (audio.cpp, Vulkan) with voice cloning.

GGUF engines (monolithic q8_0 packages in C:\\Modeles_LLM):
- qwen3   : Qwen3-TTS 12Hz 1.7B Base (Apache-2.0) — cloning with transcript,
            expression via --instruct, 24 kHz output
- voxcpm2 : VoxCPM2 (Apache-2.0) — cloning WITHOUT transcript, 48 kHz output
- fish    : Fish Audio S2 Pro (research license, paid commercial) — zero-shot
            or cloning with transcript, inline expression tags ([whisper]...),
            44.1 kHz output

Built-in pipeline: reference conversion/resampling, level control
(minimum -26 dB mean, otherwise normalization -18 LUFS / -1.5 dBTP),
automatic transcription by qwen3-asr (0.6B) when the engine requires it,
final voice normalization (default -16 LUFS, YouTube dialogue standard).
"""

import os
import re
from typing import Any, Dict, Optional

from core.config import DEFAULT_MODEL_DIR
from core.music_ai import (
    convertir_mp3,
    exporter_bed_lufs,
    mesurer_lufs,
    resoudre_audiocpp,
    resoudre_ffmpeg,
)
from core.process import run_engine

# GGUF package paths (overridable via environment variable).
MODELE_QWEN3_TTS = os.getenv(
    "QWEN3_TTS_MODEL",
    os.path.join(DEFAULT_MODEL_DIR, "Qwen3-TTS-12Hz-1.7B-Base-GGUF",
                 "qwen3-tts-12hz-1.7b-base-q8_0_v2.gguf"),
)
MODELE_QWEN3_ASR = os.getenv(
    "QWEN3_ASR_MODEL",
    os.path.join(DEFAULT_MODEL_DIR, "Qwen3-ASR-0.6B-GGUF", "qwen3-asr-0.6b-q8_0.gguf"),
)
MODELE_VOXCPM2 = os.getenv(
    "VOXCPM2_MODEL",
    os.path.join(DEFAULT_MODEL_DIR, "VoxCPM2-GGUF", "voxcpm2-q8_0.gguf"),
)
MODELE_FISH = os.getenv(
    "FISH_S2PRO_MODEL",
    os.path.join(DEFAULT_MODEL_DIR, "Fish-Audio-S2-Pro-GGUF", "fish-audio-s2-pro-q8_0.gguf"),
)

MOTEURS: Dict[str, Dict[str, Any]] = {
    "qwen3": {
        "famille": "qwen3_tts",
        "modele": MODELE_QWEN3_TTS,
        "ref_obligatoire": True,
        "transcript_obligatoire": True,
        "langue": "French",
        "licence": "Apache-2.0",
    },
    "voxcpm2": {
        "famille": "voxcpm2",
        "modele": MODELE_VOXCPM2,
        "ref_obligatoire": False,
        "transcript_obligatoire": False,
        "langue": "French",
        "licence": "Apache-2.0",
    },
    "fish": {
        "famille": "fish_audio",
        "modele": MODELE_FISH,
        "ref_obligatoire": False,      # zero-shot possible, cloning if a ref is provided
        "transcript_obligatoire": False,  # ... but transcript required WHEN a ref is provided
        "langue": None,                # auto detection
        "licence": "Fish Audio Research (non-commercial without license)",
    },
}

SEUIL_NIVEAU_DB = -26.0  # below: the reference is deemed too weak
LUFS_REF = -18.0         # voice reference normalization target
TP_REF = -1.5            # reference peak ceiling


def _verifier_modele(moteur: str) -> str:
    """Checks that the engine GGUF package is present, otherwise raises a clear error."""
    chemin = MOTEURS[moteur]["modele"]
    if not os.path.exists(chemin):
        raise FileNotFoundError(
            f"GGUF package for engine '{moteur}' not found: {chemin} — "
            f"download it from audio-cpp/audio.cpp-gguf "
            f"(scripts/telecharger_gros_fichier_parallele.py)."
        )
    return chemin


def mesurer_niveau_db(chemin: str) -> Dict[str, float]:
    """Measures the (dB) levels of an audio file via ffmpeg volumedetect."""
    ffmpeg = resoudre_ffmpeg()
    resultat = run_engine(
        [ffmpeg, "-hide_banner", "-i", chemin, "-af", "volumedetect", "-f", "null", "-"],
        check=False, timeout=120, etiquette="ffmpeg volumedetect",
    )
    texte = resultat.stderr or ""
    def _extraire(motif: str) -> float:
        m = re.search(motif + r"\s*:\s*([-\d.]+) dB", texte)
        return float(m.group(1)) if m else -120.0
    return {"mean": _extraire("mean_volume"), "max": _extraire("max_volume")}


def preparer_reference(chemin_ref: str, dossier_travail: str) -> str:
    """
    Prepares the voice reference: WAV mono 48 kHz conversion if needed, then,
    if the mean level is below SEUIL_NIVEAU_DB, normalization -18 LUFS / -1.5 dBTP.
    Returns the path of the actual WAV to use (the original if it is fine).
    """
    ffmpeg = resoudre_ffmpeg()
    os.makedirs(dossier_travail, exist_ok=True)
    base = os.path.splitext(os.path.basename(chemin_ref))[0]
    wav_converti = os.path.join(dossier_travail, f"ref_{base}.wav")
    if not os.path.exists(wav_converti):
        run_engine(
            [ffmpeg, "-hide_banner", "-y", "-i", chemin_ref,
             "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", wav_converti],
            check=True, timeout=180, etiquette="ffmpeg reference wav",
        )

    niveaux = mesurer_niveau_db(wav_converti)
    if niveaux["mean"] >= SEUIL_NIVEAU_DB:
        print(f"ℹ️ Reference {chemin_ref}: mean level {niveaux['mean']:.1f} dB (OK, ≥ {SEUIL_NIVEAU_DB:.0f} dB).")
        return wav_converti

    print(f"⚠️ Reference too weak ({niveaux['mean']:.1f} dB mean) → normalization {LUFS_REF} LUFS / {TP_REF} dBTP.")
    wav_normalise = os.path.join(dossier_travail, f"ref_{base}_norm.wav")
    mesures = mesurer_lufs(wav_converti)
    filtre = (
        f"loudnorm=I={LUFS_REF}:TP={TP_REF}:LRA=7.0:"
        f"measured_I={mesures['I']}:measured_TP={mesures['TP']}:"
        f"measured_LRA={mesures['LRA']}:measured_thresh={mesures['thresh']}:"
        f"offset={mesures['offset']}:linear=true"
    )
    run_engine(
        [ffmpeg, "-hide_banner", "-y", "-i", wav_converti, "-af", filtre,
         "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", wav_normalise],
        check=True, timeout=180, etiquette="ffmpeg reference normalization",
    )
    apres = mesurer_niveau_db(wav_normalise)
    print(f"✅ Reference normalized: {apres['mean']:.1f} dB mean / {apres['max']:.1f} dB peak.")
    return wav_normalise


def transcrire_reference(wav_ref: str, dossier_travail: str, backend: str = "vulkan") -> str:
    """
    Transcribes the voice reference with qwen3-asr 0.6B (cache memory next to the WAV).
    Required by qwen3-tts (ICL mode) and fish (inline cloning).
    """
    cache = os.path.splitext(wav_ref)[0] + "_transcript.txt"
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            return f.read().strip()

    if not os.path.exists(MODELE_QWEN3_ASR):
        raise FileNotFoundError(
            f"qwen3-asr not found ({MODELE_QWEN3_ASR}) — needed to transcribe "
            f"the reference (or provide the transcript next to the WAV: {cache})."
        )
    audiocpp = resoudre_audiocpp()
    resultat = run_engine(
        [audiocpp, "--task", "asr", "--family", "qwen3_asr", "--model", MODELE_QWEN3_ASR,
         "--backend", backend, "--language", "fr", "--audio", wav_ref],
        check=False, timeout=600, etiquette="audio.cpp asr",
    )
    m = re.search(r"text_output=(.+)", (resultat.stdout or "") + (resultat.stderr or ""))
    if not m or not m.group(1).strip():
        raise RuntimeError(f"Empty ASR transcript for {wav_ref}")
    transcript = m.group(1).strip()
    with open(cache, "w", encoding="utf-8") as f:
        f.write(transcript)
    print(f"📝 Reference transcript (qwen3-asr): \"{transcript[:80]}…\"")
    return transcript


def generer_voix_off(
    texte: str,
    moteur: str = "qwen3",
    wav_ref: Optional[str] = None,
    instruct: Optional[str] = None,
    sortie: str = "voix_off.wav",
    backend: str = "vulkan",
    seed: Optional[int] = None,
    dossier_travail: str = ".",
) -> Dict[str, Any]:
    """
    Generates a voice over with the chosen engine. If wav_ref is provided, clones the voice
    (automatic ASR transcription for qwen3/fish). instruct = style/emotion
    directive (qwen3). The fish expression tags ([whisper], [excited]...) go
    directly into `texte`.
    """
    if moteur not in MOTEURS:
        raise ValueError(f"Unknown engine: {moteur} (choices: {', '.join(MOTEURS)})")
    conf = MOTEURS[moteur]
    modele = _verifier_modele(moteur)

    if conf["ref_obligatoire"] and not wav_ref:
        raise ValueError(f"The '{moteur}' engine requires a voice reference (--voix-ref).")

    ref_effective = preparer_reference(wav_ref, dossier_travail) if wav_ref else None

    cmd = [resoudre_audiocpp(), "--task", "tts", "--family", conf["famille"],
           "--model", modele, "--backend", backend, "--text", texte,
           "--metrics", "--out", sortie]
    if conf["langue"]:
        cmd += ["--language", conf["langue"]]
    if ref_effective:
        cmd += ["--voice-ref", ref_effective]
        if conf["famille"] in ("qwen3_tts", "fish_audio"):
            transcript = transcrire_reference(ref_effective, dossier_travail, backend)
            cmd += ["--reference-text", transcript]
    if instruct and moteur == "qwen3":
        cmd += ["--instruct", instruct]
    if seed is not None and seed >= 0:
        cmd += ["--seed", str(seed)]

    print(f"🎙️ Voice over generation: engine={moteur}, cloning={'yes' if ref_effective else 'no'}, backend={backend}…")
    # audio.cpp progress live on the console (generation = minutes)
    run_engine(cmd, capture=False, check=True, timeout=3600, etiquette="audio.cpp voice over")
    if not os.path.exists(sortie):
        raise RuntimeError(f"The generation did not produce {sortie}")
    return {"sortie": sortie, "moteur": moteur, "clonage": bool(ref_effective),
            "licence": conf["licence"]}


def finaliser_voix(wav_source: str, lufs_cible: float = -16.0) -> Dict[str, str]:
    """
    Normalizes the voice (loudnorm 2 passes → target LUFS, 48 kHz PCM16) and produces
    a listening MP3. Default -16 LUFS = YouTube dialogue standard.
    """
    base = os.path.splitext(wav_source)[0]
    wav_final = f"{base}_final.wav"
    mp3_final = f"{base}_final.mp3"
    mesures = exporter_bed_lufs(wav_source, wav_final, lufs_cible=lufs_cible)
    convertir_mp3(wav_final, mp3_final)
    print(f"✅ Finalized voice: {wav_final} ({mesures['I']:.1f} LUFS) + {mp3_final}")
    return {"wav": wav_final, "mp3": mp3_final, "lufs": f"{mesures['I']:.1f}"}
