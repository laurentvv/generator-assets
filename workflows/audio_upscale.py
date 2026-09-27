#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio Super-Resolution Workflow: restoration → 48 kHz via UniverSR
(audio.cpp, CPU backend — Vulkan broken on this family, see the docstring
of core/audio_upscale.py).

RECIPE USER-VALIDATED on 2026-09-18: 16 kHz voice "copie sans bug,
parfait même", 24 kHz music "très bien" (MEMORY_BANK §1.27).
Output 48 kHz mono WAV + listening MP3.
"""

import os
from typing import Any, Dict

from core.audio_upscale import RECIPE, restaurer_universr
from core.config import slugifier_texte
from core.music_ai import convertir_mp3
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class AudioUpscaleWorkflow(BaseWorkflow):
    """Audio super-resolution → 48 kHz (UniverSR CPU, validated recipe)."""

    name = "audio_upscale"
    description = ("Audio super-resolution → 48 kHz via UniverSR (CPU): 16 kHz voice "
                   "or 24 kHz music restored (validated recipe 2026-09-18) — "
                   "48 kHz mono WAV + MP3, RTF ~13")

    emoji = "🔊"

    # CLI declarations (audit §2.2, migration from cli/parser.py's flat table:
    # help/defaults kept as-is, unchanged surface).
    PARAMETRES = [
        dict(flags=("--upsr-variante",), dest="upsr_variante", choices=["speech", "audio"], default="speech",
             help="UniverSR variant for audio_upscale: speech = voice (default, main case) | audio = music."),
        dict(flags=("--upsr-rate",), dest="upsr_rate", type=int, default=0,
             help="Input band declared to UniverSR in Hz (8000/12000/16000/24000; default: 0 = auto from the file's sample rate; above 24000 = refused)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        source = params.get("input")
        if not source or not os.path.exists(source):
            raise ValueError(
                f"Source audio file not found: {source} — "
                f"pass a reduced-band WAV/MP3 (8/12/16/24 kHz) via -i."
            )

        variante = params.get("upsr_variante") or RECIPE["variante"]
        bande = int(params.get("upsr_rate") or 0)
        # The CLI global --seed is -1 ("random") by default: universr requires
        # an unsigned integer → negative seed = recipe default (42).
        seed = int(params.get("seed") or 0)
        if seed < 0:
            seed = RECIPE["seed"]

        nom = slugifier_texte(
            params.get("output")
            or os.path.splitext(os.path.basename(source))[0]
        )[:60]
        output_dir = params.get("output_dir") or ""
        if not output_dir or output_dir == "godot_assets":
            output_dir = "output/audio_upscale"
        dossier = os.path.join(output_dir, nom)
        os.makedirs(dossier, exist_ok=True)

        wav = os.path.join(dossier, f"{nom}_48k.wav")
        mp3 = os.path.join(dossier, f"{nom}_48k.mp3")

        res = restaurer_universr(source, wav, variante=variante,
                                 bande=bande, seed=seed)
        convertir_mp3(wav, mp3)

        self.log(
            f"Restoration {res['frequence_source']} → 48 kHz "
            f"(variant {res['variante']}, declared band {res['bande']} Hz):",
            emoji="🎉",
        )
        self.log(f"  • WAV: {wav} (48 kHz mono)", "💾")
        self.log(f"  • Listening MP3: {mp3}", "💎")

        return {"wav": wav, "mp3": mp3, "files": [wav, mp3]}
