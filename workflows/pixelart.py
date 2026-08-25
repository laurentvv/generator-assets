#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Pixel Art : Stylisation Rétro et Quantification de Couleurs pour Godot.
Transforme un asset 2D (existant ou généré à la volée) en sprite Pixel Art net avec palettes célèbres.
"""

import os
from pathlib import Path
from typing import Any, Dict
from PIL import Image

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.image_ops import convertir_pixel_art, PALETTES_RETRO
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class PixelArtWorkflow(BaseWorkflow):
    name = "pixelart"
    description = "Conversion & quantification rétro Pixel Art (Pico-8, Endesga-32, GameBoy) pour jeux rétro"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        input_image = params.get("input")
        prompt = params.get("prompt")

        if not input_image and not prompt:
            raise ValueError("Le paramètre 'input' (fichier image) ou 'prompt' est requis.")

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        palette = params.get("palette", "pico8").lower()
        grid_size = int(params.get("grid_size", 64))
        export_size = int(params.get("size", 512))
        nom_sortie = params.get("output")

        os.makedirs(output_dir, exist_ok=True)

        if input_image and os.path.exists(input_image):
            img_source = Image.open(input_image)
            nom_base = nom_sortie or f"{Path(input_image).stem}_pixelart_{palette}"
        elif prompt:
            # Générer d'abord l'asset via le workflow generate
            self.log(f"Génération préalable de l'asset pour '{prompt}'...")
            wf_gen = WorkflowRegistry.get("generate")(self.config)
            res_gen = wf_gen.run(params)
            img_source = res_gen["image"]
            nom_base = nom_sortie or f"{slugifier_texte(prompt)}_pixelart_{palette}"
        else:
            raise FileNotFoundError(f"Image source introuvable : {input_image}")

        self.log(f"Conversion en Pixel Art (Grille: {grid_size}x{grid_size}, Palette: {palette.upper()})...")

        img_pixel = convertir_pixel_art(
            image=img_source,
            taille_grille=grid_size,
            taille_export=export_size,
            palette_nom=palette
        )

        chemin_fichier = os.path.join(output_dir, f"{Path(nom_base).stem}.png")
        img_pixel.save(chemin_fichier, "PNG")
        self.log(f"Sprite Pixel Art exporté : {chemin_fichier} ({img_pixel.size[0]}x{img_pixel.size[1]} RGBA)", emoji="✅")

        return {
            "output_path": chemin_fichier,
            "image": img_pixel,
            "palette": palette,
            "grid_size": grid_size
        }
