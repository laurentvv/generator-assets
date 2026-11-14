#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vocal Removal Workflow: removal of the vocals from a track by HTDemucs source
separation (audio.cpp, Vulkan). User-validated on
2026-09-06 on a full 4 min 07 s track.

Produces the vocal-free instrumental (drums+bass+other mix at preserved
levels) + the 4 full stems (drums, bass, other, vocals).
"""

import os
from typing import Any, Dict

from core.config import slugifier_texte
from core.separation import retirer_voix, separate_sam_audio
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class RetraitVoixWorkflow(BaseWorkflow):
    """Vocal removal: HTDemucs, Mel-Band/BS-RoFormer + optional Apollo polish, or SAM Audio."""

    name = "retrait_voix"
    description = ("Removes vocals from a track: HTDemucs (default, 4 stems), "
                   "Mel-Band/BS-RoFormer (--sep-engine mel_roformer|bs_roformer, SOTA 2-stem, "
                   "optional --apollo 44.1 kHz polish), or SAM Audio (--sep-engine sam).")

    emoji = "🎧"

    PARAMETRES = [
        dict(flags=("--sep-engine",), dest="sep_engine",
             choices=["htdemucs", "mel_roformer", "bs_roformer", "sam"], default="htdemucs",
             help="Separation engine for retrait_voix: htdemucs (4 stems, default) | "
                  "mel_roformer (7.2x faster SOTA 2-stem, Wave 1 validated) | bs_roformer "
                  "(band-split 2-stem) | sam (text-prompted SAM Audio, CPU)."),
        dict(flags=("--apollo",), action="store_true", default=False,
             help="Polish the extracted instrumental via Apollo 44.1 kHz restoration (-1 dBTP peak guard)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        source = params.get("input")
        if not source or not os.path.exists(source):
            raise ValueError("Audio source not found: pass it via -i <MP3/WAV>.")
        backend = params.get("music_backend") or "vulkan"
        if backend == "auto":
            backend = "vulkan"
        sep_engine = (params.get("sep_engine") or "htdemucs").lower()
        apollo = bool(params.get("apollo"))

        nom = slugifier_texte(params.get("output") or os.path.splitext(os.path.basename(source))[0])[:60]
        if sep_engine == "sam" or (sep_engine == "htdemucs" and backend == "sam"):
            dossier = os.path.join("output", "retrait_voix", f"{nom}_sam")
            self.log(f"SAM Audio separation of {source} (CPU — Vulkan impossible on RDNA2)", "🎧")
            res = separate_sam_audio(source, dossier)
            self.log(f"Instrumental ready: {res['instrumental_mp3']} — listen to validate", "✅")
            self.log(f"Raw outputs kept: {res['stems_dir']} (target.wav/residual.wav)", "📦")
            return res

        suffixe = f"_{sep_engine}" if sep_engine != "htdemucs" else ""
        if apollo:
            suffixe += "_apollo"
        dossier = os.path.join("output", "retrait_voix", f"{nom}{suffixe}")
        self.log(
            f"{sep_engine} separation of {source} (backend {backend}"
            + (", +Apollo 44.1kHz" if apollo else "") + ")",
            "🎧",
        )
        res = retirer_voix(source, dossier, backend=backend, moteur=sep_engine, apollo=apollo)
        self.log(f"Instrumental ready: {res['instrumental_mp3']} — listen to validate", "✅")
        self.log(f"Stems kept: {res['stems_dir']} (isolated vocals: vocals.wav)", "📦")
        return res
