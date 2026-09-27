#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SpriteSheet workflow: multi-view generation and sprite sheet assembly for Godot.
Generates the angles (front, right profile, back, left profile), performs the cutout and assembles the grid.
"""

import json
import os
from typing import Any, Dict

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.diffusion import generer_image_vulkan
from core.image_ops import assembler_spritesheet, post_process_asset
from core.llm import construire_prompt_coherant
from workflows.base import BaseWorkflow, WorkflowRegistry

ANGLES_4 = [
    ("front", "front view, neutral pose, single centered character sprite"),
    ("right", "side profile view facing right, single centered character sprite"),
    ("back", "back view, facing away, single centered character sprite"),
    ("left", "side profile view facing left, single centered character sprite")
]


@WorkflowRegistry.register
class SpriteSheetWorkflow(BaseWorkflow):
    name = "spritesheet"
    description = "Multi-angle sprite sheet generation (Front, Profiles, Back) with Godot JSON export"

    emoji = "📊"
    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        concept = params.get("prompt")
        if not concept:
            raise ValueError("The 'prompt' parameter is required for the spritesheet workflow.")

        nom_base = params.get("output") or slugifier_texte(concept)
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        cell_size = params.get("size", 256)
        tolerance = params.get("tolerance", 60)
        colonnes = params.get("columns", 4)
        seed = params.get("seed", 42)

        os.makedirs(output_dir, exist_ok=True)
        self.log(f"Creating a sprite sheet for '{concept}' (4 angles, cell size={cell_size}px)...")

        images_angles = []
        noms_angles = []

        for nom_angle, description_angle in ANGLES_4:
            self.log(f"Generating view: {nom_angle.upper()}...")

            prompt_angle = construire_prompt_coherant(
                concept=f"{concept}, {nom_angle} angle",
                type_asset="character",
                llama_cli=self.config.get("llama_cli"),
                llm_model=self.config.get("llm_model"),
                style_anchor=self.config.get("style_anchor"),
                custom_cadrage=description_angle,
                sans_llm=params.get("sans_llm", params.get("no_llm", True))
            )

            # Flux.1 render (with the same base seed to ensure consistency)
            img_brute = generer_image_vulkan(
                prompt=prompt_angle,
                sd_cli=self.config.get("sd_cli"),
                sd_model=self.config.get("sd_model"),
                clip_l=self.config.get("clip_l"),
                t5xxl=self.config.get("t5xxl"),
                vae=self.config.get("vae"),
                backend=self.config.get("backend"),
                threads=self.config.get("threads"),
                steps=params.get("steps", 25),
                guidance=params.get("guidance", 3.5),
                seed=seed if seed >= 0 else -1
            )

            img_traitee = post_process_asset(
                image=img_brute,
                tolerance=tolerance,
                redimensionner=cell_size
            )

            images_angles.append(img_traitee)
            noms_angles.append(f"{nom_base}_{nom_angle}")

        # Grid assembly
        self.log("Assembling the sprite sheet and generating the Godot JSON...")
        sheet_img, metadata = assembler_spritesheet(images_angles, noms_angles, colonnes=colonnes)

        chemin_sheet = os.path.join(output_dir, f"{nom_base}_spritesheet.png")
        chemin_json = os.path.join(output_dir, f"{nom_base}_spritesheet.json")

        sheet_img.save(chemin_sheet, "PNG")
        with open(chemin_json, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        self.log(f"Sprite sheet saved: {chemin_sheet}", emoji="✅")
        self.log(f"Godot metadata saved: {chemin_json}", emoji="📄")

        return {
            "spritesheet_path": chemin_sheet,
            "json_path": chemin_json,
            "metadata": metadata,
            "sheet_size": sheet_img.size
        }
