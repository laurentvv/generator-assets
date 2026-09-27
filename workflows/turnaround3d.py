#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Turnaround 3D workflow: generating modeling sheets for Blender (orthogonal views).
Generates aligned Front and Profile views to serve as reference images in the Blender viewport.
"""

import os
from typing import Any, Dict
from PIL import Image, ImageDraw

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.diffusion import generer_image_vulkan
from core.image_ops import post_process_asset
from core.llm import construire_prompt_coherant
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class Turnaround3DWorkflow(BaseWorkflow):
    name = "turnaround3d"
    description = "3D modeling sheet (Front + Profile orthogonal views calibrated for Blender)"

    emoji = "📐"
    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        concept = params.get("prompt")
        if not concept:
            raise ValueError("The 'prompt' parameter is required for the turnaround3d workflow.")

        nom_base = params.get("output") or f"{slugifier_texte(concept)}_model_sheet"
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        cell_size = int(params.get("size", 512) or 512)
        tolerance = params.get("tolerance", 60)
        seed = int(params.get("seed", 42))

        os.makedirs(output_dir, exist_ok=True)
        self.log(f"Generating 3D modeling views for '{concept}'...")

        vues = [
            ("front", "orthographic front view, T-pose or A-pose, perfectly centered, modeling reference sheet"),
            ("side", "orthographic side profile view facing right, arms down, modeling reference sheet")
        ]

        images_vues = []
        for nom_v, desc_v in vues:
            self.log(f"Rendering view: {nom_v.upper()}...")
            prompt_v = construire_prompt_coherant(
                concept=f"{concept}, {nom_v} view",
                type_asset="character",
                llama_cli=self.config.get("llama_cli"),
                llm_model=self.config.get("llm_model"),
                style_anchor=self.config.get("style_anchor"),
                custom_cadrage=desc_v,
                sans_llm=params.get("sans_llm", params.get("no_llm", True))
            )

            img_b = generer_image_vulkan(
                prompt=prompt_v,
                sd_cli=self.config.get("sd_cli"),
                sd_model=self.config.get("sd_model"),
                clip_l=self.config.get("clip_l"),
                t5xxl=self.config.get("t5xxl"),
                vae=self.config.get("vae"),
                backend=self.config.get("backend"),
                threads=self.config.get("threads"),
                steps=params.get("steps", 25),
                guidance=params.get("guidance", 3.5),
                seed=seed if seed >= 0 else -1,
                loras=params.get("loras")
            )

            img_p = post_process_asset(img_b, tolerance=tolerance, redimensionner=cell_size)
            images_vues.append(img_p)

        # Assemble side by side with alignment guide lines for Blender
        largeur_totale = cell_size * 2
        hauteur_totale = cell_size
        planche = Image.new("RGBA", (largeur_totale, hauteur_totale), (30, 30, 35, 255))

        # Paste Front on the left and Profile on the right
        planche.paste(images_vues[0], (0, 0), images_vues[0])
        planche.paste(images_vues[1], (cell_size, 0), images_vues[1])

        # Draw discreet guide lines (eyes, shoulders, hips, feet)
        draw = ImageDraw.Draw(planche)
        couleur_repere = (80, 80, 120, 150)
        for pct in [0.15, 0.30, 0.50, 0.70, 0.90]:
            y = int(hauteur_totale * pct)
            draw.line([(0, y), (largeur_totale, y)], fill=couleur_repere, width=1)

        chemin_planche = os.path.join(output_dir, f"{nom_base}.png")
        planche.save(chemin_planche, "PNG")

        self.log(f"Blender modeling sheet saved: {chemin_planche}", emoji="📐")

        return {
            "model_sheet": chemin_planche,
            "dimensions": planche.size
        }
