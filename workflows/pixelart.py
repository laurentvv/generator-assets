#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pixel Art workflow: retro stylization and color quantization for Godot.
Turns a 2D asset (existing or generated on the fly) into a crisp Pixel Art sprite with famous palettes.
"""

import os
from pathlib import Path
from typing import Any, Dict
from PIL import Image

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.image_ops import convertir_pixel_art
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class PixelArtWorkflow(BaseWorkflow):
    name = "pixelart"
    description = "Pixel Art retro conversion & quantization (Pico-8, Endesga-32, GameBoy) for retro games"

    emoji = "👾"

    # CLI declarations (audit §2.2, migration from the flat table of cli/parser.py:
    # help/defaults taken as-is, unchanged surface). --grid-size is also read
    # by voxel3d (same 2D family): it lives here, primary user of the help.
    PARAMETRES = [
        dict(flags=("--palette",), default="pico8", choices=["pico8", "gameboy", "endesga32"],
             help="Palette for the pixelart workflow."),
        dict(flags=("--grid-size",), type=int, default=64,
             help="Grid size for the pixel art (e.g.: 32, 64)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        input_image = params.get("input")
        prompt = params.get("prompt")

        if not input_image and not prompt:
            raise ValueError("The 'input' (image file) or 'prompt' parameter is required.")

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        palette = params.get("palette", "pico8").lower()
        # `or` required: via the batch workflow, main.py provides global keys
        # with None values (e.g. size=None) that .get(value) would return.
        grid_size = int(params.get("grid_size") or 64)
        export_size = int(params.get("size") or 512)
        nom_sortie = params.get("output")

        os.makedirs(output_dir, exist_ok=True)

        if input_image and os.path.exists(input_image):
            img_source = Image.open(input_image)
            nom_base = nom_sortie or f"{Path(input_image).stem}_pixelart_{palette}"
        elif prompt:
            # First generate the asset via the generate workflow
            self.log(f"Pre-generating the asset for '{prompt}'...")
            wf_gen = WorkflowRegistry.get("generate")(self.config)
            res_gen = wf_gen.run(params)
            img_source = res_gen["image"]
            nom_base = nom_sortie or f"{slugifier_texte(prompt)}_pixelart_{palette}"
        else:
            raise FileNotFoundError(f"Source image not found: {input_image}")

        self.log(f"Pixel Art conversion (Grid: {grid_size}x{grid_size}, Palette: {palette.upper()})...")

        img_pixel = convertir_pixel_art(
            image=img_source,
            taille_grille=grid_size,
            taille_export=export_size,
            palette_nom=palette
        )

        chemin_fichier = os.path.join(output_dir, f"{Path(nom_base).stem}.png")
        img_pixel.save(chemin_fichier, "PNG")
        self.log(f"Pixel Art sprite exported: {chemin_fichier} ({img_pixel.size[0]}x{img_pixel.size[1]} RGBA)", emoji="✅")

        return {
            "output_path": chemin_fichier,
            "image": img_pixel,
            "palette": palette,
            "grid_size": grid_size
        }
