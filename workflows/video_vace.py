#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VACE Video Workflow: motion-locked video via Wan 2.1 VACE (control-video guidance).

The appearance is locked by the reference image (--input), the motion by the
control-frames folder (--control-video, e.g. pose/depth/skeleton frames extracted
as PNGs). Engine support: sd-cli vid_gen (upstream PR #819).

VALIDATED 2026-10-01 (user verdict "très bien" on the knight I2V+VACE run):
distilled LightX2V route (8 steps, cfg 1.0) — 4x faster than the plain 14B VACE
Q3_K_S 20-step recipe, which was REJECTED the same day ("nul"). Recipe and
comparison: MEMORY_BANK §1.28. Mandatory memory placement on 16 GB:
--offload-to-cpu --vae-on-cpu (GPU VAE decode alone requests ~19.4 GB).
"""

import os
from typing import Any, Dict

from core.config import DEFAULT_OUTPUT_DIR, DEFAULT_VACE_MODEL, DEFAULT_VACE_T5XXL, DEFAULT_WAN_VAE, slugifier_texte
from core.diffusion import generer_video_vulkan
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class VideoVaceWorkflow(BaseWorkflow):
    """Motion-locked video (I2V + control-video) via Wan 2.1 VACE, validated LightX2V distilled route."""

    name = "video_vace"
    description = (
        "VACE motion-locked video: reference image (--input) + control frames (--control-video) "
        "via Wan 2.1 14B VACE LightX2V distilled (validated 2026-10-01, 8 steps)"
    )

    emoji = "🕹️"

    # NOTE: --control-video is NOT redeclared here — it is already part of the global
    # CLI surface (declared once by workflows/video.py); this workflow only consumes it.
    PARAMETRES = []

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        prompt = params.get("prompt")
        if not prompt:
            raise ValueError("The 'prompt' parameter is required for the video_vace workflow (describe the motion).")
        input_img = params.get("input")
        if not input_img:
            raise ValueError(
                "The 'input' reference image is required for video_vace (I2V+VACE: appearance is "
                "locked by --input, motion by --control-video) — validated use case only."
            )
        control_dir = params.get("control_video")
        if not control_dir:
            raise ValueError(
                "The '--control-video' frame folder is required for video_vace (VACE guidance) — "
                "preprocess pose/depth/skeleton frames first (see MEMORY_BANK §1.28)."
            )

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)

        nom_base = params.get("output") or f"{slugifier_texte(prompt)[:50]}_vace"
        if not nom_base.lower().endswith((".webm", ".mp4")):
            video_output_path = os.path.join(output_dir, f"{nom_base}.webm")
        else:
            video_output_path = os.path.join(output_dir, nom_base)

        # Validated recipe (MEMORY_BANK §1.28, 2026-10-01): distilled 8 steps, cfg 1.0,
        # 13 frames @ 16 fps 832x480, euler, no flow-shift, no temporal tiling,
        # --offload-to-cpu --vae-on-cpu, plain vulkan backend, seed 42 (A/B convention).
        frames = int(params.get("frames", 13)) or 13
        fps = int(params.get("fps", 16)) or 16
        width = int(params.get("width", 832)) or 832
        height = int(params.get("height", 480)) or 480
        steps = int(params.get("steps", 8)) or 8
        cfg_scale = float(params.get("cfg_scale", 1.0))
        seed = int(params.get("seed", 42))

        self.log(
            f"VACE generation ({frames} frames @ {fps} fps, {width}x{height}, {steps} steps, "
            f"LightX2V distilled) — appearance: {input_img} | control: {control_dir}"
        )

        video_path = generer_video_vulkan(
            prompt=prompt,
            sd_cli=self.config.get("sd_cli"),
            model_path=params.get("diffusion_model") or DEFAULT_VACE_MODEL,
            vae_path=params.get("vae") or DEFAULT_WAN_VAE,
            t5xxl_path=params.get("t5xxl") or DEFAULT_VACE_T5XXL,
            video_frames=frames,
            fps=fps,
            width=width,
            height=height,
            steps=steps,
            cfg_scale=cfg_scale,
            flow_shift=None,
            sampling_method="euler",
            seed=seed,
            negative_prompt=params.get("negative_prompt"),
            init_img=input_img,
            control_video_dir=control_dir,
            offload_to_cpu=True,
            diffusion_fa=True,
            temporal_tiling=False,
            vae_on_cpu=True,
            backend=self.config.get("backend_vace", "vulkan"),
            threads=int(self.config.get("threads", 16)),
            output_path=video_output_path,
        )

        return {
            "prompt": prompt,
            "video_path": video_path,
            "reference_image": input_img,
            "control_video_dir": control_dir,
            "frames": frames,
            "fps": fps,
            "resolution": f"{width}x{height}",
            "steps": steps,
            "seed": seed,
            "status": "success",
        }
