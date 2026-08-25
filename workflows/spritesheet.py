#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow SpriteSheet : Génération multi-vues et assemblage de feuille de sprites pour Godot.
Génère les angles (face, profil droit, dos, profil gauche), effectue le détourage et assemble la grille.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List
from PIL import Image

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
    description = "Génération d'une planche de sprites multi-angles (Face, Profils, Dos) avec export JSON Godot"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        concept = params.get("prompt")
        if not concept:
            raise ValueError("Le paramètre 'prompt' est requis pour le workflow spritesheet.")

        nom_base = params.get("output") or slugifier_texte(concept)
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        cell_size = params.get("size", 256)
        tolerance = params.get("tolerance", 60)
        colonnes = params.get("columns", 4)
        seed = params.get("seed", 42)

        os.makedirs(output_dir, exist_ok=True)
        self.log(f"Création d'une planche de sprites pour '{concept}' (4 angles, taille cellule={cell_size}px)...")

        images_angles = []
        noms_angles = []

        for nom_angle, description_angle in ANGLES_4:
            self.log(f"Génération de la vue : {nom_angle.upper()}...")
            
            prompt_angle = construire_prompt_coherant(
                concept=f"{concept}, {nom_angle} angle",
                type_asset="character",
                llama_cli=self.config.get("llama_cli"),
                llm_model=self.config.get("llm_model"),
                style_anchor=self.config.get("style_anchor"),
                custom_cadrage=description_angle
            )

            # Rendu Flux.1 (avec même graine de base pour assurer la cohérence)
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

        # Assemblage en grille
        self.log("Assemblage de la feuille de sprites et génération du JSON Godot...")
        sheet_img, metadata = assembler_spritesheet(images_angles, noms_angles, colonnes=colonnes)

        chemin_sheet = os.path.join(output_dir, f"{nom_base}_spritesheet.png")
        chemin_json = os.path.join(output_dir, f"{nom_base}_spritesheet.json")

        sheet_img.save(chemin_sheet, "PNG")
        with open(chemin_json, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        self.log(f"Planche de sprites sauvegardée : {chemin_sheet}", emoji="✅")
        self.log(f"Métadonnées Godot sauvegardées : {chemin_json}", emoji="📄")

        return {
            "spritesheet_path": chemin_sheet,
            "json_path": chemin_json,
            "metadata": metadata,
            "sheet_size": sheet_img.size
        }
