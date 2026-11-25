#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MOSS-Image-SFT text-to-image workflow (OpenMOSS 5.1B DiT flow-matching, Vulkan GGUF).

Capabilities: free-form natural language prompts, reliable in-image text
rendering (the model's headline strength), clean layout composition.
Pipeline USER VALIDATED 2026-10-24 ("Moss parfait oui"): sd-cli arch
`moss_image` (since master-973) + Qwen3.5-9B-Q8_0 text encoder + external
tokenizer + flux2 VAE, euler, everything resident in VRAM.

DEFAULT recipe since 2026-11-24 (user "VALIDÉ", VALIDATION_20261124 card 2):
the distilled 4-step LoRA at CFG 1.0 — 97 s vs 2102 s for the 50-step CFG-3
teacher (÷21), typo word-perfect, richer composition. --no-lora restores the
teacher recipe (50 steps CFG 3.0, ~36 min; 42.5-43.0 s/step at 1024x1024 on
RDNA2). Known weakness: small secondary text garbles (documented base
limitation).

Apache-2.0 license: commercial use OK (unlike the Qwen-Image RESEARCH path).
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.diffusion import generer_image_moss
from core.process import run_engine
from workflows.base import BaseWorkflow, WorkflowRegistry

SCRIPT_CHECK_CHARGE = Path(__file__).resolve().parent.parent / "scripts" / "check_charge_systeme.py"


@WorkflowRegistry.register
class MossImageWorkflow(BaseWorkflow):
    name = "moss_image"
    description = (
        "MOSS-Image-SFT text-to-image (OpenMOSS 5.1B Vulkan, strong in-image text rendering, "
        "Apache-2.0 = commercial OK; default = VALIDATED 4-step LoRA, ~97 s; --no-lora = "
        "50-step CFG-3 teacher)"
    )

    emoji = "🌿"

    # CLI declaration (audit §2.2 keystone). --steps/--cfg-scale/--seed/--width/
    # --height stay in the flat table (shared across families).
    PARAMETRES = [
        dict(flags=("--no-lora",), dest="no_lora", action="store_true", default=False,
             help="moss_image: run the 50-step CFG-3.0 teacher recipe (~36 min) instead of the "
                  "VALIDATED 4-step LoRA default (97 s, user 'VALIDÉ' 2026-11-24)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        prompt = params.get("prompt")
        if not prompt:
            raise ValueError("The 'prompt' parameter is required for the moss_image workflow.")

        # Dimensions: sd-cli requires multiples of 32 for this architecture —
        # round down to the grid instead of failing the launch.
        width = int(params.get("width") or 1024)
        height = int(params.get("height") or 1024)
        width -= width % 32
        height -= height % 32

        # Flat CLI defaults (--steps 25, --cfg-scale 1.0) arrive as sentinel
        # values when omitted — snap them to the active recipe; explicit values
        # pass through. Default recipe = VALIDATED 4-step LoRA (24-11);
        # --no-lora restores the 50-step CFG-3 teacher.
        no_lora = bool(params.get("no_lora"))
        raw_steps = params.get("steps")
        raw_cfg = params.get("cfg_scale")
        if no_lora:
            steps = 50 if raw_steps in (None, 25) else int(raw_steps)
            cfg_scale = 3.0 if raw_cfg in (None, 1.0) else float(raw_cfg)
        else:
            steps = 4 if raw_steps in (None, 25) else int(raw_steps)
            cfg_scale = 1.0 if raw_cfg in (None, 1.0) else float(raw_cfg)
        seed = params.get("seed")
        seed = int(seed) if seed is not None else -1
        if params.get("size") is not None:
            self.log(
                f"⚠️ Ignoring -s/--size ({params['size']}) on moss_image: "
                "use --seed for determinism and --width/--height for dimensions.",
            )

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)
        nom_sortie = params.get("output") or f"{slugifier_texte(prompt)[:60]}_moss"
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

        self.log(f"MOSS-Image-SFT rendering (t2i, {width}x{height}, steps={steps}, cfg={cfg_scale}, "
                 f"{'lora4 default' if not no_lora else 'no-lora teacher'}) — Apache-2.0 license.")
        generer_image_moss(
            prompt=prompt,
            width=width,
            height=height,
            steps=steps,
            cfg_scale=cfg_scale,
            seed=seed,
            use_lora=not no_lora,
            output_path=output_path,
        )
        self.log(f"Image saved: {output_path}", emoji="✅")
        return {"image": output_path}
