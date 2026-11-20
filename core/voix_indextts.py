#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IndexTTS2.5 voice synthesis (audio.cpp `index_tts2` family, Vulkan GGUF).

Zero-shot TTS with voice cloning: the timbre comes from a mandatory
`--voice-ref` WAV (the model ships no built-in voices — it refuses to run
without one). First user verdicts 2026-11-20 (MEMORY_BANK §1.67): the EN
neutral narration path is VALIDATED for doc2video voice-over.

Measured pitfall baked into this module as a gate: **the output loudness
FOLLOWS the reference loudness** (a -39 LUFS reference produced -39 LUFS
speech; EBU R128 measurements, §1.67). The reference is therefore
loudness-normalized (ffmpeg `loudnorm`, EBU R128 target -16 LUFS) before the
call, unless explicitly disabled.
"""

import os
import re
from typing import Any, Dict, Optional

from core.config import DEFAULT_AUDIOCPP_CLI, DEFAULT_INDEXTTS25_MODEL
from core.process import run_engine

# Languages officially supported by the IndexTTS2.5 tokenizer (model spec
# index_tts2.json). Off-spec languages (e.g. fr) DO generate audible speech
# (measured datapoint 2026-11-20) but stay unsupported-by-spec: a warning is
# logged, the call is allowed.
SPEC_LANGUAGES = ("zh", "en", "ja", "es", "ar")

# EBU R128 gates. A reference already in the sane band (>= REFERENCE_SANE_LUFS)
# is passed through untouched; below it, it is normalized to
# REFERENCE_TARGET_LUFS (true-peak clamped) into a sibling temp file.
REFERENCE_SANE_LUFS = -23.0
REFERENCE_TARGET_LUFS = -16.0
REFERENCE_TRUE_PEAK = -1.5

_LUFS_PATTERN = re.compile(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS")


def mesurer_lufs(chemin: str) -> Optional[float]:
    """Integrated loudness (LUFS) of a WAV via ffmpeg ebur128, None if unmeasurable."""
    commande = ["ffmpeg", "-hide_banner", "-nostats", "-i", chemin,
                "-af", "ebur128", "-f", "null", "-"]
    retour = run_engine(commande, capture=True, check=False, timeout=120,
                        etiquette="ebur128 loudness")
    correspondances = _LUFS_PATTERN.findall(retour.stdout or "")
    if not correspondances:
        correspondances = _LUFS_PATTERN.findall(retour.stderr or "")
    if not correspondances:
        return None
    return float(correspondances[-1])


def normaliser_reference(reference: str, cible: float = REFERENCE_TARGET_LUFS) -> str:
    """Returns the reference path, normalized when its loudness is too low.

    A quiet reference yields quiet speech (§1.67) — anything below
    REFERENCE_SANE_LUFS goes through ffmpeg loudnorm into a sibling
    `<stem>_ttsnorm.wav`. Already-sane references are returned untouched.
    """
    mesure = mesurer_lufs(reference)
    if mesure is None:
        print("⚠️ Reference loudness unmeasurable (ffmpeg ebur128 empty) — using it as-is.")
        return reference
    if mesure >= REFERENCE_SANE_LUFS:
        print(f"🔊 Reference loudness OK ({mesure:.1f} LUFS) — no normalization.")
        return reference
    dossier = os.path.dirname(os.path.abspath(reference))
    racine = os.path.splitext(os.path.basename(reference))[0]
    cible_chemin = os.path.join(dossier, f"{racine}_ttsnorm.wav")
    print(f"⚠️ Reference too quiet ({mesure:.1f} LUFS < {REFERENCE_SANE_LUFS} LUFS) — "
          f"normalizing to {cible:.0f} LUFS: {cible_chemin}")
    commande = ["ffmpeg", "-hide_banner", "-y", "-i", reference,
                "-af", f"loudnorm=I={cible}:TP={REFERENCE_TRUE_PEAK}",
                "-ar", "48000", cible_chemin]
    run_engine(commande, capture=True, check=True, timeout=120,
               etiquette="reference loudnorm")
    return cible_chemin


def generer_voix_indextts(
    texte: str,
    sortie: str,
    reference: str,
    langue: str = "en",
    graine: int = 42,
    backend: str = "vulkan",
    normaliser_ref: bool = True,
    audiocpp: str = DEFAULT_AUDIOCPP_CLI,
    modele: str = DEFAULT_INDEXTTS25_MODEL,
) -> Dict[str, Any]:
    """
    Synthesizes speech from `texte` with IndexTTS2.5, timbre cloned from `reference`.

    langue: ISO 639-1 code, default 'en' (the user-validated narration path).
    Off-spec languages are allowed with a warning (fr datapoint, §1.67).
    normaliser_ref: keep ON — the output follows the reference level
    (measured §1.67); disable only for level diagnostics.
    """
    if not texte or not texte.strip():
        raise ValueError("Empty text: nothing to synthesize.")
    if not reference:
        raise ValueError("A voice reference is required (--tts-reference): "
                         "IndexTTS2.5 refuses to run without one (zero-shot design).")
    for chemin, role in ((audiocpp, "audiocpp_cli"), (modele, "model"), (reference, "voice reference")):
        if not os.path.exists(chemin):
            raise FileNotFoundError(f"{role} not found: {chemin}")

    langue = (langue or "en").lower()
    if langue not in SPEC_LANGUAGES:
        print(f"⚠️ Language '{langue}' is outside the IndexTTS2.5 spec list "
              f"({', '.join(SPEC_LANGUAGES)}) — generation allowed, quality unguaranteed.")

    reference_eff = normaliser_reference(reference) if normaliser_ref else reference

    commande = [
        audiocpp,
        "--task", "tts", "--family", "index_tts2",
        "--model", modele,
        "--backend", backend,
        "--voice-ref", reference_eff,
        "--text", texte,
        "--language", langue,
        "--seed", str(graine),
        "--metrics",
        "--out", sortie,
    ]
    try:
        print(f"🎙️ IndexTTS2.5 voice synthesis: lang={langue}, seed={graine}, "
              f"ref={os.path.basename(reference_eff)}…")
    except UnicodeEncodeError:
        print(f"IndexTTS2.5 voice synthesis: lang={langue}, seed={graine}…")
    # Warm RTF ~3-4x on short texts (incl. model load, §1.67); long-form texts
    # chunk internally — keep a generous ceiling.
    run_engine(commande, capture=False, check=True, timeout=1800, etiquette="audiocpp indextts25")
    if not os.path.exists(sortie):
        raise RuntimeError(f"The generation did not produce {sortie}")

    taille_mo = os.path.getsize(sortie) / (1024 * 1024)
    print(f"✅ Voice saved: {sortie} ({taille_mo:.2f} MB)")
    return {
        "sortie": sortie,
        "moteur": "indextts25_q8_0",
        "langue": langue,
        "graine": graine,
        "reference": reference_eff,
        "reference_normalisee": normaliser_ref and reference_eff != reference,
    }
