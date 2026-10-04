#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qwen-Image-2.1 text-to-image workflow (7B DiT, Vulkan GGUF).

Capabilities: free-form natural language prompts, reliable in-image text
rendering, RGBA transparency driven by the prompt itself. Engine recipe in
core.diffusion.generer_image_qwen21; upstream pinned doc in
scratch/upstream_docs/sd-cli_qwen-image-21/.

⚠️ Qwen RESEARCH license: the renders are for PERSONAL / NON-COMMERCIAL use
ONLY — do not feed monetized channels or games with them (Chroma1-HD /
`generate` remain the production paths).
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.diffusion import generer_image_qwen21
from core.process import run_engine
from workflows.base import BaseWorkflow, WorkflowRegistry

SCRIPT_CHECK_CHARGE = Path(__file__).resolve().parent.parent / "scripts" / "check_charge_systeme.py"


@WorkflowRegistry.register
class QwenImageWorkflow(BaseWorkflow):
    name = "qwen_image"
    description = (
        "Qwen-Image-2.1 text-to-image (7B Vulkan, in-image text rendering, RGBA via prompt; "
        "RESEARCH license = personal/non-commercial use only)"
    )

    emoji = "🖼️"

    # CLI declaration (audit §2.2 keystone). --steps/--cfg-scale/--seed/--width/
    # --height stay in the flat table (shared across families).
    PARAMETRES = [
        dict(flags=("--negative-prompt",),
             help="qwen_image: negative prompt (only acts because cfg-scale > 1)."),
        dict(flags=("--negative-prompt-file",),
             help="qwen_image: UTF-8 text file holding the negative prompt (wins over --negative-prompt)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        prompt = params.get("prompt")
        if not prompt:
            raise ValueError("The 'prompt' parameter is required for the qwen_image workflow.")

        # Dimensions: sd-cli requires multiples of 32 for this architecture —
        # round down to the grid instead of failing the launch.
        width = int(params.get("width") or 1152)
        height = int(params.get("height") or 640)
        width -= width % 32
        height -= height % 32

        # Flat CLI defaults (--steps 25, --cfg-scale 1.0) are NOT the validated
        # Qwen recipe (cfg 1.0 silently disables the negative prompt). Omitted
        # flags arrive as those sentinel values — snap them to the recipe;
        # explicit non-default values pass through.
        steps = params.get("steps")
        steps = 40 if steps in (None, 25) else int(steps)
        cfg_scale = params.get("cfg_scale")
        cfg_scale = 6.0 if cfg_scale in (None, 1.0) else float(cfg_scale)
        seed = params.get("seed")
        seed = int(seed) if seed is not None else -1

        negative_prompt = params.get("negative_prompt")
        fichier_negatif = params.get("negative_prompt_file")
        if fichier_negatif:
            negative_prompt = Path(fichier_negatif).read_text(encoding="utf-8").strip()

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)
        nom_sortie = params.get("output") or f"{slugifier_texte(prompt)[:60]}_qwen21"
        output_path = os.path.join(output_dir, f"{nom_sortie}.png")

        # Load pre-check (AGENTS.md rule: never launch heavy generation on a busy machine)
        if SCRIPT_CHECK_CHARGE.exists():
            self.log("System load pre-check (CPU/GPU/RAM/VRAM)...")
            retour = run_engine(
                [sys.executable, str(SCRIPT_CHECK_CHARGE)],
                capture=False, check=False, timeout=300, etiquette="load check",
            )
            if retour.returncode == 1:
                raise RuntimeError("Busy machine (check_charge_systeme exit 1) — wait for a free slot before relaunching.")

        self.log(f"Qwen-Image-2.1 rendering ({width}x{height}, steps={steps}, cfg={cfg_scale}) — RESEARCH license: personal/non-commercial use only.")
        generer_image_qwen21(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            steps=steps,
            cfg_scale=cfg_scale,
            seed=seed,
            output_path=output_path,
        )
        self.log(f"Image saved: {output_path}", emoji="✅")
        return {"image": output_path}
