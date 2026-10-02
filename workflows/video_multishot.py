#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multishot Video Workflow: several named cuts + a continuous soundtrack in ONE
LTX-2.5 T2V generation (native multishot).

VALIDATED 2026-10-02 (user verdict "super" on the 65-frame lighthouse two-shot
run, MEMORY_BANK §1.34): the named hard cut appears where the prompt asks for
it, the keeper's appearance holds across the cut, and the generated soundtrack
is present. Recipe = the §1.17 distilled constants (8 steps, official sigmas,
euler_a, cfg 1.0, --max-vram 10, te/vae on CPU) plus the audio VAE, WITHOUT a
negative prompt, on the pinned LTX binary (the main build cannot fit LTX, #1976).

Prompting rules (docs.ltx.io, adopted 2026-10-01): describe each shot in order,
name the cut explicitly ("A hard cut transitions to…"), and include the audio
bed — the model generates the soundtrack from that block.
"""

import os
from typing import Any, Dict

from core.cinema import generate_ltx_multishot
from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class VideoMultishotWorkflow(BaseWorkflow):
    """Multi-cut video with continuous soundtrack in a single LTX-2.5 generation (validated recipe)."""

    name = "video_multishot"
    description = (
        "Native LTX-2.5 multishot: several named cuts + a continuous soundtrack in ONE T2V "
        "generation (validated 2026-10-02; the prompt must name the cuts and describe the audio bed)"
    )

    emoji = "🎬"

    # Consumes the global CLI surface (--frames/--fps/--seed/-o) — shared flags are
    # declared ONCE (cli/parser.py + workflows/video.py); redeclaring them here
    # would raise an argparse conflict (2026-10-01 pitfall).
    PARAMETRES = []

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        prompt = params.get("prompt")
        if not prompt:
            raise ValueError(
                "The 'prompt' parameter is required for video_multishot — describe each shot in "
                "order, name the cut explicitly ('A hard cut transitions to…') and include the "
                "audio bed (crashing waves, distant thunder…): the model generates the soundtrack "
                "from that block (official LTX prompting rules)."
            )

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)

        nom_base = params.get("output") or f"{slugifier_texte(prompt)[:50]}_multishot"
        if not nom_base.lower().endswith((".webm", ".mp4")):
            video_output_path = os.path.join(output_dir, f"{nom_base}.webm")
        else:
            video_output_path = os.path.join(output_dir, nom_base)

        # Validated envelope (MEMORY_BANK §1.34, 2026-10-02): 65 frames @ 24 fps,
        # 8 steps official sigmas baked in the core route, seed 42 (A/B convention).
        frames = int(params.get("frames", 65)) or 65
        fps = int(params.get("fps", 24)) or 24
        seed = int(params.get("seed", 42))

        self.log(
            f"LTX multishot generation ({frames} frames @ {fps} fps, seed {seed}) — "
            "cuts + soundtrack in one pass"
        )

        video_path = generate_ltx_multishot(
            prompt=prompt,
            sortie=video_output_path,
            frames=frames,
            fps=fps,
            seed=seed,
            log_fn=lambda m: self.log(m.strip()),
        )

        return {
            "prompt": prompt,
            "video_path": video_path,
            "frames": frames,
            "fps": fps,
            "resolution": "832x480",
            "seed": seed,
            "status": "success",
        }
