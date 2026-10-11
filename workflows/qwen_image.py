#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qwen-Image-2.1 text-to-image AND compositing workflow (7B DiT, Vulkan GGUF).

Capabilities: free-form natural language prompts, reliable in-image text
rendering, RGBA transparency driven by the prompt itself. Compositing mode
(-i <cutout paste> + -l <lora:name:weight>): product pasted on a background
gets consistent lighting, specular highlights and a natural contact shadow.
Validated compositing recipe (2026-10-05 night A/B): CUTOUT paste of the
product (white-keyed — a pasted WHITE BOX survives img2img), prompt starting
with the LoRA trigger word "pengyu", strength 0.65, 24 steps, LoRA
Qwenimag21_c2-st2000. Engine recipe in core.diffusion.generer_image_qwen21;
upstream pinned doc in scratch/upstream_docs/sd-cli_qwen-image-21/.

Turbo mode (--turbo, USER VALIDATED 2026-10-11 "Atomic très bien"): the
official 8-step distilled checkpoint (AtomicChat sd.cpp-native Q8_0 quant,
same TE/VAE) — 123 s/image measured vs 962 s base, typography quality kept.
Forces the checkpoint's single validated schedule (8 steps, CFG 1, custom
sigmas).

⚠️ Qwen RESEARCH license: the renders are for PERSONAL / NON-COMMERCIAL use
ONLY — do not feed monetized channels or games with them (Chroma1-HD /
`generate` remain the production paths).
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict

from core.config import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_QWEN_IMAGE21_MODEL,
    DEFAULT_QWEN_IMAGE21_TURBO_MODEL,
    QWEN_IMAGE21_TURBO_SIGMAS,
    slugifier_texte,
)
from core.diffusion import generer_image_qwen21
from core.process import run_engine
from workflows.base import BaseWorkflow, WorkflowRegistry

SCRIPT_CHECK_CHARGE = Path(__file__).resolve().parent.parent / "scripts" / "check_charge_systeme.py"


@WorkflowRegistry.register
class QwenImageWorkflow(BaseWorkflow):
    name = "qwen_image"
    description = (
        "Qwen-Image-2.1 text-to-image AND compositing (7B Vulkan, in-image text rendering, "
        "RGBA via prompt; -i cutout paste + -l lora = product blend with contact shadow, "
        "trigger 'pengyu' first; RESEARCH license = personal/non-commercial use only)"
    )

    emoji = "🖼️"

    # CLI declaration (audit §2.2 keystone). --steps/--cfg-scale/--seed/--width/
    # --height stay in the flat table (shared across families).
    PARAMETRES = [
        dict(flags=("--negative-prompt",),
             help="qwen_image: negative prompt (only acts because cfg-scale > 1)."),
        dict(flags=("--negative-prompt-file",),
             help="qwen_image: UTF-8 text file holding the negative prompt (wins over --negative-prompt)."),
        dict(flags=("--qwen-turbo",), action="store_true",
             help="qwen_image: 8-step distilled turbo checkpoint (USER VALIDATED 2026-10-11) — "
                  "~2 min/image vs ~16 base, same typography quality. Forces steps=8 / cfg-scale=1.0 "
                  "and the checkpoint's custom sigma schedule (the only schedule evaluated upstream); "
                  "do not pass --steps/--cfg-scale with it. Compositing (-i/-l) is mechanically "
                  "compatible but its 8-step quality is untested. (--turbo is taken by h3_ref2va.)"),
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

        # Flat CLI defaults (--steps 25, --cfg-scale 1.0, --strength 0.55) are NOT
        # the validated Qwen recipes (cfg 1.0 silently disables the negative
        # prompt). Omitted flags arrive as those sentinel values — snap them to
        # the recipe; explicit non-default values pass through.
        raw_steps = params.get("steps")
        raw_cfg = params.get("cfg_scale")
        steps = 40 if raw_steps in (None, 25) else int(raw_steps)
        cfg_scale = 6.0 if raw_cfg in (None, 1.0) else float(raw_cfg)
        seed = params.get("seed")
        seed = int(seed) if seed is not None else -1

        # Turbo mode: the distilled checkpoint ships ONE validated schedule
        # (8 steps, CFG 1). Explicit steps/cfg alongside it would silently
        # desync the sigma schedule — refuse instead of guessing.
        turbo = bool(params.get("qwen_turbo"))
        sigmas = None
        qwen_model = DEFAULT_QWEN_IMAGE21_MODEL
        if turbo:
            if raw_steps not in (None, 25, 8) or raw_cfg not in (None, 1.0):
                raise ValueError(
                    "--turbo locks the distilled schedule (8 steps, CFG 1.0); "
                    "drop --steps/--cfg-scale."
                )
            steps, cfg_scale = 8, 1.0
            sigmas = QWEN_IMAGE21_TURBO_SIGMAS
            qwen_model = DEFAULT_QWEN_IMAGE21_TURBO_MODEL

        # Compositing mode (flat flags -i/-l/--lora-dir/--strength, shared with
        # the other families). Sentinel snapping to the validated recipe:
        # strength 0.65; 24 steps in img2img (40 stays the t2i recipe).
        init_image = params.get("input")
        loras = params.get("loras")
        lora_dir = params.get("lora_dir")
        strength = params.get("strength")
        strength = 0.65 if strength in (None, 0.55) else float(strength)
        if init_image and steps == 40:
            steps = 24

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

        mode_str = "img2img" if init_image else "t2i"
        if loras:
            mode_str += f" + {len(loras)} LoRA(s)"
        if turbo:
            mode_str += " [turbo 8-step]"
        self.log(f"Qwen-Image-2.1 rendering ({mode_str}, {width}x{height}, steps={steps}, cfg={cfg_scale}, strength={strength}) — RESEARCH license: personal/non-commercial use only.")
        generer_image_qwen21(
            prompt=prompt,
            negative_prompt=negative_prompt,
            model=qwen_model,
            width=width,
            height=height,
            steps=steps,
            cfg_scale=cfg_scale,
            seed=seed,
            output_path=output_path,
            init_image=init_image,
            strength=strength,
            loras=loras,
            lora_dir=lora_dir,
            sigmas=sigmas,
        )
        self.log(f"Image saved: {output_path}", emoji="✅")
        return {"image": output_path}
