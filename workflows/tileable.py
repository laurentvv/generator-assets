#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tileable workflow: generating seamless textures (Seamless / Tileable) for Godot TileMaps.
Uses the sd-cli circular padding mode and produces the tile plus a 3x3 seam-check preview.
"""

import os
from typing import Any, Dict
from PIL import Image

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.diffusion import generer_image_vulkan
from core.image_ops import creer_apercu_tuilage
from core.llm import construire_prompt_coherant
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class TileableWorkflow(BaseWorkflow):
    name = "tileable"
    description = "Seamless texture generation / infinite terrain tiles for Godot TileMaps"

    emoji = "🔲"

    # CLI declaration (audit §2.2, migration from the flat table of cli/parser.py:
    # help/defaults taken as-is, unchanged surface). The no_preview dest is
    # turned into the preview key by cli/parser.construire_params.
    PARAMETRES = [
        dict(flags=("--no-preview",), action="store_true",
             help="Disables the 3x3 preview for the tileable workflow."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        concept = params.get("prompt")
        if not concept:
            raise ValueError("The 'prompt' parameter is required for the tileable workflow.")

        nom_base = params.get("output") or slugifier_texte(concept)
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        taille = params.get("size", 512)
        creer_preview = params.get("preview", True)

        os.makedirs(output_dir, exist_ok=True)
        self.log(f"Generating a seamless texture for '{concept}'...")

        style_tuile = (
            "seamless texture, continuous repeating pattern, top-down view, "
            "dark fantasy dungeon terrain, clean edges, tileable texture, photorealistic digital painting"
        )

        prompt_complet = construire_prompt_coherant(
            concept=concept,
            type_asset="tile",
            llama_cli=self.config.get("llama_cli"),
            llm_model=self.config.get("llm_model"),
            style_anchor=style_tuile,
            custom_cadrage="seamless repeatable tile texture",
            sans_llm=params.get("sans_llm", params.get("no_llm", True))
        )

        # Render with the circular flag to force edge looping
        img_tuile = generer_image_vulkan(
            prompt=prompt_complet,
            sd_cli=self.config.get("sd_cli"),
            sd_model=self.config.get("sd_model"),
            clip_l=self.config.get("clip_l"),
            t5xxl=self.config.get("t5xxl"),
            vae=self.config.get("vae"),
            backend=self.config.get("backend"),
            threads=self.config.get("threads"),
            circular=True,
            steps=params.get("steps", 25),
            guidance=params.get("guidance", 3.5),
            seed=params.get("seed", -1)
        )

        if taille and taille > 0 and img_tuile.size != (taille, taille):
            img_tuile = img_tuile.resize((taille, taille), Image.Resampling.LANCZOS)

        chemin_tuile = os.path.join(output_dir, f"{nom_base}_tile.png")
        img_tuile.save(chemin_tuile, "PNG")
        self.log(f"Seamless tile saved: {chemin_tuile}", emoji="✅")

        # Generate a 3x3 repeat preview to visually validate the seam
        chemin_preview = None
        if creer_preview:
            img_preview = creer_apercu_tuilage(img_tuile, rep_x=3, rep_y=3)
            chemin_preview = os.path.join(output_dir, f"{nom_base}_tile_preview3x3.png")
            img_preview.save(chemin_preview, "PNG")
            self.log(f"3x3 tiling preview generated: {chemin_preview}", emoji="🖼️")

        return {
            "tile_path": chemin_tuile,
            "preview_path": chemin_preview,
            "dimensions": img_tuile.size
        }
