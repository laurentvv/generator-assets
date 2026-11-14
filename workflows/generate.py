#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standard Workflow: single 2D asset generation for Godot.
LLM (enrichment) -> Flux.1 (Vulkan + LoRAs) -> Floodfill cutout -> Centering -> PNG export.
"""

import os
from pathlib import Path
from typing import Any, Dict

from core.config import DEFAULT_CONTROLNET_UNION, DEFAULT_OUTPUT_DIR, DEFAULT_SDXL_MODEL, slugifier_texte
from core.diffusion import generer_image_vulkan
from core.image_ops import post_process_asset
from core.llm import construire_prompt_coherant
from core.upscaler import upscaler_asset
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class GenerateWorkflow(BaseWorkflow):
    name = "generate"
    description = "Generation of a single 2D asset (LLM -> Diffusion -> Cutout -> Godot centering -> optional ControlNet/upscale)"

    emoji = "🎨"

    # CLI declaration (audit §2.2, migration from cli/parser.py's flat table + Wave 2 ProMax).
    PARAMETRES = [
        dict(flags=("--segmenter",), default="auto", choices=["auto", "birefnet", "rmbg", "floodfill", "none"],
             help="2D cutout engine."),
        dict(flags=("--control-image",), dest="control_image", default=None,
             help="generate: structural or reference control image for ControlNet++ Union SDXL ProMax (pair with --control-type; auto-switches checkpoint to SDXL)."),
        dict(flags=("--control-type",), dest="control_type", default=None, choices=["canny", "tile"],
             help="generate: ControlNet++ Union ProMax mode (USER VALIDATED 2026-11-14: canny | tile)."),
        dict(flags=("--control-strength",), dest="control_strength", type=float, default=None,
             help="generate: ControlNet++ Union ProMax conditioning strength (0.0-1.0; default: 0.85 for canny, 0.75 for tile)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        concept = params.get("prompt")
        if not concept:
            raise ValueError("The 'prompt' parameter is required for the generate workflow.")

        type_asset = params.get("type", "item")
        nom_sortie = params.get("output") or slugifier_texte(concept)
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        taille_sprite = params.get("size", 512)
        width_param = params.get("width")
        height_param = params.get("height")
        gen_width = int(width_param or 1024)
        gen_height = int(height_param or 1024)
        upscale_actif = params.get("upscale", False)
        facteur_upscale = float(params.get("factor", 4.0 if upscale_actif else 2.0))
        modele_upscale = params.get("upscale_model") or self.config.get("esrgan_model")
        sans_llm = params.get("sans_llm", params.get("no_llm", True))
        tolerance = params.get("tolerance", 60)
        steps = params.get("steps", 25)
        guidance = params.get("guidance", 3.5)
        cfg_scale = params.get("cfg_scale", 1.0)
        seed = params.get("seed", -1)
        loras = params.get("loras")
        lora_dir = params.get("lora_dir") or self.config.get("lora_dir")

        control_image = params.get("control_image")
        control_type = params.get("control_type")
        if bool(control_image) != bool(control_type):
            raise ValueError(
                "ControlNet++ Union ProMax requires both '--control-image' and '--control-type' (canny | tile)."
            )

        sd_model_effectif = self.config.get("sd_model")
        control_net = None
        control_strength = 0.9
        if control_image and control_type:
            if not os.path.exists(control_image):
                raise FileNotFoundError(f"ControlNet control image not found: {control_image}")
            control_net = self.config.get("controlnet_union", DEFAULT_CONTROLNET_UNION)
            if not os.path.exists(control_net):
                raise FileNotFoundError(f"ControlNet++ Union ProMax model not found: {control_net}")
            sd_model_effectif = self.config.get("controlnet_sd_model", DEFAULT_SDXL_MODEL)
            if not os.path.exists(sd_model_effectif):
                raise FileNotFoundError(f"SDXL checkpoint for ControlNet not found: {sd_model_effectif}")
            control_strength = (
                float(params["control_strength"])
                if params.get("control_strength") is not None
                else (0.85 if control_type == "canny" else 0.75)
            )
            if not 0.0 <= control_strength <= 1.0:
                raise ValueError(
                    f"--control-strength must be between 0.0 and 1.0 (got {control_strength})."
                )
            self.log(
                f"ControlNet++ Union ProMax [{control_type}] strength={control_strength:.2f} "
                f"({os.path.basename(control_image)}) + SDXL {os.path.basename(sd_model_effectif)}"
            )

        os.makedirs(output_dir, exist_ok=True)

        # 1. LLM step
        if sans_llm:
            self.log("Direct mode: raw prompt without LLM.")
            prompt_complet = f"{concept}, {self.config.get('style_anchor')}"
        else:
            self.log(f"Art direction for '{concept}'...")
            prompt_complet = construire_prompt_coherant(
                concept=concept,
                type_asset=type_asset,
                llama_cli=self.config.get("llama_cli"),
                llm_model=self.config.get("llm_model"),
                style_anchor=self.config.get("style_anchor")
            )

        # 2. Diffusion step (Flux.1 or SDXL + LoRAs + Init Img + ControlNet++ Union ProMax)
        init_image = params.get("input")
        force_denoise = float(params.get("strength", 0.55)) if init_image else 0.75
        if init_image:
            self.log(f"Guidance from source image ({init_image}, strength={force_denoise})...")
        self.log(f"Vulkan diffusion rendering ({gen_width}x{gen_height}, {steps} steps, guidance={guidance})...")
        img_brute = generer_image_vulkan(
            prompt=prompt_complet,
            sd_cli=self.config.get("sd_cli"),
            sd_model=sd_model_effectif,
            clip_l=self.config.get("clip_l"),
            t5xxl=self.config.get("t5xxl"),
            vae=self.config.get("vae"),
            backend=self.config.get("backend"),
            threads=self.config.get("threads"),
            width=gen_width,
            height=gen_height,
            steps=steps,
            guidance=guidance,
            cfg_scale=cfg_scale,
            seed=seed,
            init_img=init_image,
            strength=force_denoise,
            control_image=control_image,
            control_net=control_net,
            control_strength=control_strength,
            control_type=control_type,
            loras=loras,
            lora_dir=lora_dir
        )

        # 3. Post-Processing & Cutout
        segmenter_mode = params.get("segmenter", "auto")
        if segmenter_mode != "none":
            self.log("Cutting out the background and centering to a square...")
        else:
            self.log("Framing the image (no background cutout)...")
        dim_redim = (
            None
            if (
                upscale_actif
                or (taille_sprite and taille_sprite > 1024)
                or width_param
                or height_param
                or (control_image and segmenter_mode == "none")
            )
            else taille_sprite
        )
        img_finale = post_process_asset(
            image=img_brute,
            tolerance=tolerance,
            redimensionner=dim_redim,
            segmenter=segmenter_mode
        )

        # 4. Optional AI Upscaling (1024 -> 4096 px)
        if upscale_actif or (taille_sprite and taille_sprite > 1024):
            taille_cible = taille_sprite if (taille_sprite and taille_sprite > 1024) else None
            self.log(f"🔍 ESRGAN AI upscaling ({facteur_upscale}x)...")
            img_finale = upscaler_asset(
                image_entree=img_finale,
                facteur=facteur_upscale,
                taille_cible=taille_cible,
                upscale_model=modele_upscale,
                sd_cli=self.config.get("sd_cli"),
                backend=self.config.get("backend")
            )
            self.log(f"Asset upscaled to resolution {img_finale.size[0]}x{img_finale.size[1]} px", emoji="✨")

        chemin_fichier = os.path.join(output_dir, f"{Path(nom_sortie).stem}.png")
        img_finale.save(chemin_fichier, "PNG")
        self.log(f"Asset exported successfully: {chemin_fichier} ({img_finale.size[0]}x{img_finale.size[1]} px)", emoji="✅")

        return {
            "output_path": chemin_fichier,
            "image": img_finale,
            "prompt_used": prompt_complet,
            "dimensions": img_finale.size,
            "control_type": control_type,
            "control_image": control_image,
        }
