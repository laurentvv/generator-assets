#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LFM3-Audio-2B voice synthesis workflow (LiquidAI, llama.cpp Vulkan).

Compact 2B text-to-speech running faster than real time on the RX 6950 XT
(24 kHz output, female/male voices, FR/EN among 10+ languages). Pipeline
USER VALIDATED 2026-10-28 ("voix parfaite" on the EN/FR listening samples) —
MEMORY_BANK §1.48. Voice-over route for short lines and drafts; the mastered
production voices stay on the validated audio.cpp engines (voix_off).
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.process import run_engine
from core.voix_lfm3 import generer_voix_lfm3
from workflows.base import BaseWorkflow, WorkflowRegistry

SCRIPT_CHECK_CHARGE = Path(__file__).resolve().parent.parent / "scripts" / "check_charge_systeme.py"


@WorkflowRegistry.register
class Lfm3TtsWorkflow(BaseWorkflow):
    name = "lfm3_tts"
    description = (
        "LFM3-Audio-2B voice synthesis (LiquidAI 2B, llama.cpp Vulkan, faster than "
        "real time; FR default, female/male; validated 2026-10-28 'voix parfaite')"
    )

    emoji = "🎧"

    # CLI declaration (audit §2.2 keystone). --output comes from the flat table.
    PARAMETRES = [
        dict(flags=("--tts-langue",), default="fr",
             help="Voice language for lfm3_tts, ISO 639-1 (default: fr)."),
        dict(flags=("--tts-voix",), default="female",
             help="Voice for lfm3_tts: female (default) or male."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        texte = params.get("prompt")
        if not texte:
            raise ValueError("The 'prompt' parameter (text to speak) is required for the lfm3_tts workflow.")

        langue = params.get("tts_langue") or "fr"
        voix = params.get("tts_voix") or "female"

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)
        nom_sortie = params.get("output") or f"{slugifier_texte(texte)[:60]}_lfm3"
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

        self.log(f"Voice synthesis ({langue}, {voix}) — validated pipeline 2026-10-28.")
        resultat = generer_voix_lfm3(
            texte=texte,
            sortie=output_path,
            langue=langue,
            voix=voix,
        )
        self.log(f"Voice saved: {resultat['sortie']}", emoji="✅")
        return resultat
