#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MOSS-Image-SFT text-to-image workflow (OpenMOSS 5.1B DiT flow-matching, Vulkan GGUF).

Capabilities: free-form natural language prompts, reliable in-image text
rendering (the model's headline strength), clean layout composition.
Pipeline USER VALIDATED 2026-10-24 ("Moss parfait oui"): sd-cli arch
`moss_image` (since master-973) + Qwen3.5-9B-Q8_0 text encoder + external
tokenizer + flux2 VAE; euler 50 steps CFG 3.0, everything resident in VRAM
(11.4 GB on the 16 GB card). Measured 42.5-43.0 s/step at 1024x1024 on RDNA2
(~36 min/image) — the arch is new on Vulkan, kernels still young. Known
weakness: small secondary text garbles (documented base limitation).

Variant `--moss-variante lora-4step` USER VALIDATED 2026-11-24 (night 23-11/24
A/B planche): lvladikov MOSS-SFT-Distill-4step-LoRA (Apache-2.0), 4 steps
CFG 1.0 strength 1.0 strict on the Q8_0 base — 97 s vs 2102 s teacher
(≈ ÷21), in-image typo word-perfect and larger than the teacher's.

Apache-2.0 license: commercial use OK (unlike the Qwen-Image RESEARCH path).
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict

from core.config import (
    DEFAULT_MOSS_IMAGE_4STEP_LORA,
    DEFAULT_MOSS_IMAGE_LORA_BASE_MODEL,
    DEFAULT_OUTPUT_DIR,
    slugifier_texte,
)
from core.diffusion import generer_image_moss
from core.process import run_engine
from workflows.base import BaseWorkflow, WorkflowRegistry

SCRIPT_CHECK_CHARGE = Path(__file__).resolve().parent.parent / "scripts" / "check_charge_systeme.py"


@WorkflowRegistry.register
class MossImageWorkflow(BaseWorkflow):
    name = "moss_image"
    description = (
        "MOSS-Image-SFT text-to-image (OpenMOSS 5.1B Vulkan, strong in-image text rendering, "
        "Apache-2.0 = commercial OK; --variante base = 50 steps CFG 3 (~36 min) | "
        "lora-4step = distilled LoRA 4 steps CFG 1 (~97 s, validated 2026-11-24))"
    )

    emoji = "🌿"

    # CLI declarations (audit §2.2 keystone). --steps/--cfg-scale/--seed/--width/
    # --height stay in the flat table (shared across families).
    PARAMETRES = [
        dict(flags=("--moss-variante",), dest="moss_variante", choices=["base", "lora-4step"], default="base",
             help="moss_image variant: base = 50 steps CFG 3 teacher (default, ~36 min) | "
                  "lora-4step = the distilled LoRA at 4 steps CFG 1 strength 1.0 "
                  "(USER VALIDATED 2026-11-24, ~97 s, typo word-perfect; validated "
                  "pairing = Q8_0 base, the variant routes to it automatically)."),
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

        # Flat CLI defaults (--steps 25, --cfg-scale 1.0) are NOT the validated
        # MOSS recipe (50 steps, CFG 3.0). Omitted flags arrive as those
        # sentinel values — snap them to the recipe; explicit values pass through.
        raw_steps = params.get("steps")
        raw_cfg = params.get("cfg_scale")
        steps = 50 if raw_steps in (None, 25) else int(raw_steps)
        cfg_scale = 3.0 if raw_cfg in (None, 1.0) else float(raw_cfg)
        seed = params.get("seed")
        seed = int(seed) if seed is not None else -1

        lora_path = None
        base_model = None
        variante = params.get("moss_variante") or "base"
        if variante == "lora-4step":
            # Validated distill recipe: 4 steps CFG 1.0 strength 1.0 STRICT
            # (higher strength doubles edges), euler, Q8_0 base — the pairing
            # validated in the night 23-11/24 A/B (MEMORY_BANK §1.45).
            base_model = DEFAULT_MOSS_IMAGE_LORA_BASE_MODEL
            lora_path = DEFAULT_MOSS_IMAGE_4STEP_LORA
            if not os.path.exists(lora_path):
                raise FileNotFoundError(
                    f"The lora-4step LoRA file is missing: {lora_path} — "
                    "check MOSS_IMAGE_4STEP_LORA_PATH."
                )
            if raw_steps not in (None, 25) and int(raw_steps) != 4:
                self.log("⚠️ lora-4step pins steps=4 (validated recipe) — explicit value overridden.")
            if raw_cfg not in (None, 1.0) and float(raw_cfg) != 1.0:
                self.log("⚠️ lora-4step pins cfg-scale=1.0 (validated recipe) — explicit value overridden.")
            steps, cfg_scale = 4, 1.0

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

        self.log(
            f"MOSS-Image-SFT rendering (t2i, {width}x{height}, steps={steps}, cfg={cfg_scale}, "
            f"variante={variante}) — Apache-2.0 license."
        )
        generer_image_moss(
            prompt=prompt,
            width=width,
            height=height,
            steps=steps,
            cfg_scale=cfg_scale,
            seed=seed,
            output_path=output_path,
            lora_path=lora_path,
            base_model=base_model,
        )
        self.log(f"Image saved: {output_path}", emoji="✅")
        return {"image": output_path}
