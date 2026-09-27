#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skybox workflow: generating an equirectangular 360° sky / panorama for Godot 3D.
Generates a 2:1 image (e.g.: 2048x1024) with horizontal looping and exports the Environment resource (.tres).
"""

import os
from typing import Any, Dict
from PIL import Image

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.diffusion import generer_image_vulkan
from core.image_ops import exporter_fichier_skybox_godot
from core.llm import construire_prompt_coherant
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class SkyboxWorkflow(BaseWorkflow):
    name = "skybox"
    description = "Equirectangular 360° Skybox Environment generation and Godot 4 Environment file"

    emoji = "🌌"
    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        concept = params.get("prompt")
        if not concept:
            raise ValueError("The 'prompt' parameter is required for the skybox workflow.")

        nom_base = params.get("output") or f"{slugifier_texte(concept)}_sky"
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        # `or` required: via the CLI, main.py now provides width/height
        # as None when the flags are not passed (same guard as pixelart).
        largeur = int(params.get("width") or 2048)
        hauteur = int(params.get("height") or 1024)

        os.makedirs(output_dir, exist_ok=True)
        self.log(f"Generating a 360° panorama for '{concept}' ({largeur}x{hauteur})...")

        style_skybox = (
            "360 degree equirectangular panorama projection, seamless spherical environment map, "
            "atmospheric horizon, ultra wide dynamic range, game skybox background, photorealistic digital matte painting"
        )

        prompt_complet = construire_prompt_coherant(
            concept=concept,
            type_asset="tile",
            llama_cli=self.config.get("llama_cli"),
            llm_model=self.config.get("llm_model"),
            style_anchor=style_skybox,
            custom_cadrage="360 equirectangular spherical panorama, horizontal seamless looping",
            sans_llm=params.get("sans_llm", params.get("no_llm", True))
        )

        # 2:1 render
        img_sky = generer_image_vulkan(
            prompt=prompt_complet,
            sd_cli=self.config.get("sd_cli"),
            sd_model=self.config.get("sd_model"),
            clip_l=self.config.get("clip_l"),
            t5xxl=self.config.get("t5xxl"),
            vae=self.config.get("vae"),
            backend=self.config.get("backend"),
            threads=self.config.get("threads"),
            width=1024,
            height=512,
            circular=True,
            steps=params.get("steps", 25),
            guidance=params.get("guidance", 3.5),
            seed=params.get("seed", -1),
            loras=params.get("loras")
        )

        # Upscale to the requested size (e.g.: 2048x1024)
        if (largeur, hauteur) != img_sky.size:
            img_sky = img_sky.resize((largeur, hauteur), Image.Resampling.LANCZOS)

        chemin_sky = os.path.join(output_dir, f"{nom_base}.png")
        img_sky.save(chemin_sky, "PNG")

        # Export the Godot 4 Environment resource
        chemin_tres = exporter_fichier_skybox_godot(nom_base, output_dir)

        self.log(f"360° Skybox texture saved: {chemin_sky}", emoji="🌌")
        self.log(f"Godot 4 Environment resource ready: {chemin_tres}", emoji="💎")

        return {
            "sky_texture": chemin_sky,
            "environment_tres": chemin_tres,
            "dimensions": img_sky.size
        }
