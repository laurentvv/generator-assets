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

from core.audio_restore import RECIPE, restaurer_apollo, restaurer_reuse
from core.config import slugifier_texte
from core.music_ai import convertir_mp3
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class AudioRestaureWorkflow(BaseWorkflow):
    """Audio restoration: RE-USE speech (Vulkan, 2026-11-05) or Apollo 44.1 kHz music (2026-11-14)."""

    name = "audio_restaure"
    description = ("Audio restoration via RE-USE (speech repair, 8-48 kHz, OpenMDW-1.1) or "
                   "Apollo (--restore-engine apollo: 44.1 kHz music bandwidth restoration, "
                   "-1 dBTP peak guard, MIT, RTF ~0.074)")

    emoji = "🩺"

    # CLI declarations (same contract as audio_upscale: workflow-specific
    # options default to None CLI-side, the recipe default applies here).
    PARAMETRES = [
        dict(flags=("--restore-engine",), dest="restore_engine",
             choices=["reuse", "apollo"], default="reuse",
             help="Restoration engine for audio_restaure: reuse (speech NemotronLabs F32, "
                  "default) | apollo (44.1 kHz music restoration with -1 dBTP peak guard, MIT)."),
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

        engine = (params.get("restore_engine") or "reuse").lower()
        suffixe = "apollo" if engine == "apollo" else "restaure"
        wav = os.path.join(dossier, f"{nom}_{suffixe}.wav")
        mp3 = os.path.join(dossier, f"{nom}_{suffixe}.mp3")

        if engine == "apollo":
            res = restaurer_apollo(source, wav, chunk=chunk, overlap=overlap)
            label = "Music restoration done (Apollo 44.1 kHz, Vulkan, -1 dBTP peak guard):"
            fmt = "44.1 kHz stereo WAV (-1 dBTP headroom)"
        else:
            res = restaurer_reuse(source, wav, chunk=chunk, overlap=overlap)
            label = "Speech restoration done (RE-USE NemotronLabs, Vulkan):"
            fmt = "input rate/channels preserved"

        convertir_mp3(wav, mp3)

        self.log(label, emoji="🎉")
        self.log(f"  • WAV: {wav} ({fmt})", "💾")
        self.log(f"  • Listening MP3: {mp3}", "💎")

        return {
            "wav": wav,
            "mp3": mp3,
            "files": [wav, mp3],
            "chunk": res["chunk"],
            "moteur": engine,
        }
