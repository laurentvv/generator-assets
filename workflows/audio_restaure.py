#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Speech Restoration Workflow: degraded/denoised voice repair via RE-USE
(audio.cpp `reuse` family, NemotronLabs F32, Vulkan — see the docstring
of core/audio_restore.py).

RECIPE USER-VALIDATED on 2026-11-05: "OK" on the restored A/B
(degraded synthetic voice vs restored — MEMORY_BANK §1.53).
Output WAV at the input rate/channels/length + listening MP3.
"""

import os
from typing import Any, Dict

from core.audio_restore import RECIPE, restaurer_reuse
from core.config import slugifier_texte
from core.music_ai import convertir_mp3
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class AudioRestaureWorkflow(BaseWorkflow):
    """Speech restoration via RE-USE (Vulkan, validated recipe 2026-11-05)."""

    name = "audio_restaure"
    description = ("Speech restoration (denoise / degraded voice repair) via RE-USE "
                   "NemotronLabs F32, Vulkan: 8-48 kHz input, output = same rate/channels/"
                   "length WAV + MP3, RTF ~0.5 (validated recipe 2026-11-05)")

    emoji = "🩺"

    # CLI declarations (same contract as audio_upscale: workflow-specific
    # options default to None CLI-side, the recipe default applies here).
    PARAMETRES = [
        dict(flags=("--restore-chunk",), dest="restore_chunk", type=float, default=None,
             help="Chunk duration in seconds for long recordings (default: 0 = whole "
                  "recording in one pass; chunking bounds per-chunk graph memory but "
                  "changes the bidirectional context)."),
        dict(flags=("--restore-overlap",), dest="restore_overlap", type=float, default=None,
             help="Hann-weighted chunk overlap in seconds (default: 1; only used when "
                  "--restore-chunk > 0, must stay shorter than the chunk)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        source = params.get("input")
        if not source or not os.path.exists(source):
            raise ValueError(
                f"Source audio file not found: {source} — "
                f"pass the degraded voice WAV/MP3 (8-48 kHz) via -i."
            )

        chunk = params.get("restore_chunk")
        chunk = RECIPE["chunk"] if chunk is None else float(chunk)
        overlap = params.get("restore_overlap")
        overlap = RECIPE["overlap"] if overlap is None else float(overlap)

        nom = slugifier_texte(
            params.get("output")
            or os.path.splitext(os.path.basename(source))[0]
        )[:60]
        output_dir = params.get("output_dir") or ""
        if not output_dir or output_dir == "godot_assets":
            output_dir = "output/audio_restaure"
        dossier = os.path.join(output_dir, nom)
        os.makedirs(dossier, exist_ok=True)

        wav = os.path.join(dossier, f"{nom}_restaure.wav")
        mp3 = os.path.join(dossier, f"{nom}_restaure.mp3")

        res = restaurer_reuse(source, wav, chunk=chunk, overlap=overlap)
        convertir_mp3(wav, mp3)

        self.log("Speech restoration done (RE-USE NemotronLabs, Vulkan):", emoji="🎉")
        self.log(f"  • WAV: {wav} (input rate/channels preserved)", "💾")
        self.log(f"  • Listening MP3: {mp3}", "💎")

        return {"wav": wav, "mp3": mp3, "files": [wav, mp3], "chunk": res["chunk"]}
