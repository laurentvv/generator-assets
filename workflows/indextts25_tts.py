#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IndexTTS2.5 voice synthesis workflow (audio.cpp `index_tts2` family, Vulkan).

Zero-shot TTS with voice cloning from a mandatory reference WAV. EN neutral
narration USER VALIDATED 2026-11-20 (MEMORY_BANK §1.67); clone timbre quality
is pending re-validation (reference-level pitfall measured and gated in
core/voix_indextts.py). The reference loudness is normalized before the call
(output follows the reference level — measured -39 LUFS ref -> -39 LUFS speech).
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.process import run_engine
from core.voix_indextts import SPEC_LANGUAGES, generer_voix_indextts
from workflows.base import BaseWorkflow, WorkflowRegistry

SCRIPT_CHECK_CHARGE = Path(__file__).resolve().parent.parent / "scripts" / "check_charge_systeme.py"


@WorkflowRegistry.register
class Indextts25TtsWorkflow(BaseWorkflow):
    name = "indextts25_tts"
    description = (
        "IndexTTS2.5 voice synthesis (audio.cpp Vulkan, zero-shot cloning from a "
        "reference WAV; EN default validated 2026-11-20 for doc2video narration; "
        "reference loudness auto-normalized — output follows the reference level)"
    )

    emoji = "🗣️"

    # CLI declaration (audit §2.2 keystone). --output comes from the flat table.
    # Namespace `--indextts-*`: `--tts-langue`/`--tts-voix` are taken by lfm3_tts.
    PARAMETRES = [
        dict(flags=("--indextts-langue",), dest="indextts_langue", default="en",
             help="Voice language for indextts25_tts, ISO 639-1 (default: en, the "
                  "validated path; spec languages: zh/en/ja/es/ar — off-spec allowed "
                  "with a warning)."),
        dict(flags=("--indextts-reference",), dest="indextts_reference", default=None,
             help="WAV voice reference to clone (MANDATORY — the model refuses to run "
                  "without one). Loudness-normalized to -16 LUFS when too quiet."),
        dict(flags=("--indextts-seed",), dest="indextts_seed", type=int, default=42,
             help="Sampling seed (default: 42 — reproducible A/B)."),
        dict(flags=("--indextts-raw-ref",), dest="indextts_raw_ref", action="store_true", default=False,
             help="Disable the reference loudness normalization (diagnostics only — "
                  "the output follows the reference level)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        texte = params.get("prompt")
        if not texte:
            raise ValueError("The 'prompt' parameter (text to speak) is required for the indextts25_tts workflow.")

        reference = params.get("indextts_reference")
        if not reference:
            raise ValueError("A voice reference is required (--indextts-reference PATH): "
                             "IndexTTS2.5 is zero-shot and ships no built-in voices.")

        langue = params.get("indextts_langue") or "en"
        graine = int(params.get("indextts_seed") or 42)

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)
        nom_sortie = params.get("output") or f"{slugifier_texte(texte)[:60]}_indextts25"
        output_path = os.path.join(output_dir, f"{nom_sortie}.wav")

        # Load pre-check (AGENTS.md rule: never launch heavy generation on a busy machine)
        if SCRIPT_CHECK_CHARGE.exists():
            self.log("System load pre-check (CPU/GPU/RAM/VRAM)...")
            retour = run_engine(
                [sys.executable, str(SCRIPT_CHECK_CHARGE)],
                capture=False, check=False, timeout=300, etiquette="load check",
            )
            if retour.returncode == 1:
                raise RuntimeError("Busy machine (check_charge_systeme exit 1) — wait for a free slot before relaunching.")

        self.log(f"Voice synthesis ({langue}, seed {graine}) — EN narration path validated 2026-11-20.")
        resultat = generer_voix_indextts(
            texte=texte,
            sortie=output_path,
            reference=reference,
            langue=langue,
            graine=graine,
            normaliser_ref=not bool(params.get("indextts_raw_ref")),
        )
        if resultat.get("reference_normalisee"):
            self.log("Reference was normalized (too quiet) — output level follows the reference.", emoji="⚠️")
        if langue not in SPEC_LANGUAGES:
            self.log(f"Language '{langue}' is off-spec — treat quality as a datapoint, not a validated path.", emoji="⚠️")
        self.log(f"Voice saved: {resultat['sortie']}", emoji="✅")
        return resultat
