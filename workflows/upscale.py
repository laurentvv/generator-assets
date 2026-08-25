#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Upscale : Super-résolution haute fidélité pour assets 2D.
Supporte les modèles IA ESRGAN (RealESRGAN_x4plus, Anime_6B, 4x-UltraSharp) sous Vulkan et Smart Lanczos.
"""

import os
from pathlib import Path
from typing import Any, Dict
from PIL import Image

from core.config import DEFAULT_OUTPUT_DIR, resoudre_upscaler
from core.upscaler import upscaler_asset
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class UpscaleWorkflow(BaseWorkflow):
    name = "upscale"
    description = "Super-résolution IA (ESRGAN Vulkan / Lanczos) avec préservation du canal Alpha"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        input_path = params.get("input")
        if not input_path or not os.path.exists(input_path):
            raise FileNotFoundError(f"Image source introuvable : {input_path}")

        facteur = float(params.get("factor", 2.0))
        taille_cible = params.get("size")
        mode = params.get("mode", "auto")
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        nom_sortie = params.get("output")
        modele_demande = params.get("upscale_model") or self.config.get("esrgan_model")

        os.makedirs(output_dir, exist_ok=True)
        img_source = Image.open(input_path)

        self.log(f"Chargement de l'image source : {input_path} ({img_source.size[0]}x{img_source.size[1]} {img_source.mode})")

        img_upscaled = upscaler_asset(
            image_entree=img_source,
            facteur=facteur,
            taille_cible=taille_cible,
            mode=mode,
            upscale_model=modele_demande,
            sd_cli=self.config.get("sd_cli"),
            backend=self.config.get("backend", "diffusion=vulkan0,te=cpu")
        )

        stem_source = Path(input_path).stem
        nom_final = nom_sortie or f"{stem_source}_upscaled_{img_upscaled.size[0]}x{img_upscaled.size[1]}"
        chemin_sortie = os.path.join(output_dir, f"{Path(nom_final).stem}.png")

        img_upscaled.save(chemin_sortie, "PNG")
        self.log(f"Image agrandie sauvegardée : {chemin_sortie} ({img_upscaled.size[0]}x{img_upscaled.size[1]} {img_upscaled.mode})", emoji="✅")

        return {
            "output_path": chemin_sortie,
            "image": img_upscaled,
            "dimensions": img_upscaled.size
        }
