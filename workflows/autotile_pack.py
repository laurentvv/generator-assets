#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Autotile Pack workflow: generating 47-tile Autotile sheets (Minimal 3x3 Terrain) and TileSet.tres for Godot 4.
"""

import os
from typing import Any, Dict
from PIL import Image

from core.autotile_builder import exporter_tileset_godot, generer_atlas_47_tuiles
from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.diffusion import generer_image_vulkan
from core.llm import construire_prompt_coherant
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class AutotilePackWorkflow(BaseWorkflow):
    """Complete 47-tile Autotile generation and Godot 4 TileSet.tres resource."""

    name = "autotile_pack"
    description = "47-tile Autotile sheets (Wang / Minimal 3x3) + Godot 4 TileSet.tres resource"

    emoji = "🗺️"

    # CLI declarations (audit §2.2, migration from the flat table of cli/parser.py:
    # help/defaults taken as-is, unchanged surface).
    PARAMETRES = [
        dict(flags=("--biome-a",),
             help="Description or image of the first biome for autotile_pack."),
        dict(flags=("--biome-b",),
             help="Description or image of the second biome for autotile_pack."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        biome_a_param = params.get("biome_a") or params.get("prompt") or "herbe verte fleurie"
        biome_b_param = params.get("biome_b") or "terre rocheuse sombre"

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        tile_size = int(params.get("size", 128)) or 128
        colonnes = int(params.get("columns", 8))
        nom_base = params.get("output") or f"{slugifier_texte(biome_a_param)}_vers_{slugifier_texte(biome_b_param)}"

        os.makedirs(output_dir, exist_ok=True)

        # 1. Biome A load or generation
        if os.path.exists(biome_a_param):
            self.log(f"Loading Biome A (Foreground): {biome_a_param}...")
            img_a = Image.open(biome_a_param).convert("RGB")
        else:
            self.log(f"Generating the texture for Biome A: '{biome_a_param}'...")
            prompt_a = construire_prompt_coherant(
                concept=biome_a_param,
                type_asset="tile",
                llama_cli=self.config.get("llama_cli"),
                llm_model=self.config.get("llm_model"),
                style_anchor="2D game top-down tileable texture, seamless pattern",
                custom_cadrage="seamless repeatable tileable texture",
                sans_llm=params.get("sans_llm", params.get("no_llm", True))
            )
            img_a = generer_image_vulkan(
                prompt=prompt_a,
                sd_cli=self.config.get("sd_cli"),
                sd_model=self.config.get("sd_model"),
                clip_l=self.config.get("clip_l"),
                t5xxl=self.config.get("t5xxl"),
                vae=self.config.get("vae"),
                backend=self.config.get("backend"),
                threads=self.config.get("threads"),
                circular=True,
                steps=params.get("steps", 25)
            )

        # 2. Biome B load or generation
        if os.path.exists(biome_b_param):
            self.log(f"Loading Biome B (Background): {biome_b_param}...")
            img_b = Image.open(biome_b_param).convert("RGB")
        else:
            self.log(f"Generating the texture for Biome B: '{biome_b_param}'...")
            prompt_b = construire_prompt_coherant(
                concept=biome_b_param,
                type_asset="tile",
                llama_cli=self.config.get("llama_cli"),
                llm_model=self.config.get("llm_model"),
                style_anchor="2D game top-down tileable texture, seamless pattern",
                custom_cadrage="seamless repeatable tileable texture",
                sans_llm=params.get("sans_llm", params.get("no_llm", True))
            )
            img_b = generer_image_vulkan(
                prompt=prompt_b,
                sd_cli=self.config.get("sd_cli"),
                sd_model=self.config.get("sd_model"),
                clip_l=self.config.get("clip_l"),
                t5xxl=self.config.get("t5xxl"),
                vae=self.config.get("vae"),
                backend=self.config.get("backend"),
                threads=self.config.get("threads"),
                circular=True,
                steps=params.get("steps", 25)
            )

        # 3. 47-tile Atlas composition
        self.log(f"Composing the 47-tile atlas ({colonnes} columns, {tile_size}x{tile_size} tiles)...")
        atlas = generer_atlas_47_tuiles(img_a, img_b, tile_size=tile_size, colonnes=colonnes)
        chemin_atlas = os.path.join(output_dir, f"{nom_base}_atlas.png")
        atlas.save(chemin_atlas, "PNG")

        # 4. Godot 4 TileSet export
        self.log("Generating the Godot 4 TileSet (.tres) resource with peering bits...")
        chemin_tres = exporter_tileset_godot(nom_base, output_dir, tile_size=tile_size, colonnes=colonnes)

        self.log(f"Complete Autotile pack exported to '{output_dir}/':", emoji="🎉")
        self.log(f"  • 47-Tile Atlas    : {chemin_atlas}")
        self.log(f"  • Godot resource   : {chemin_tres} (TileSet with Terrains)", emoji="💎")

        return {
            "atlas": chemin_atlas,
            "tileset_tres": chemin_tres,
            "tile_count": 47,
            "files": [chemin_atlas, chemin_tres]
        }
