#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Tileable : Génération de textures raccordables (Seamless / Tileable) pour TileMaps Godot.
Utilise le mode circular padding de sd-cli et produit la tuile ainsi qu'un aperçu de raccordement 3x3.
"""

import os
from pathlib import Path
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
    description = "Génération de textures seamless / tuiles de terrain infinies pour TileMaps Godot"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        concept = params.get("prompt")
        if not concept:
            raise ValueError("Le paramètre 'prompt' est requis pour le workflow tileable.")

        nom_base = params.get("output") or slugifier_texte(concept)
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        taille = params.get("size", 512)
        creer_preview = params.get("preview", True)

        os.makedirs(output_dir, exist_ok=True)
        self.log(f"Génération d'une texture seamless pour '{concept}'...")

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

        # Rendu avec le flag circular pour forcer le bouclage des bords
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
        self.log(f"Tuile seamless sauvegardée : {chemin_tuile}", emoji="✅")

        # Générer un aperçu de répétition 3x3 pour valider visuellement le raccord
        chemin_preview = None
        if creer_preview:
            img_preview = creer_apercu_tuilage(img_tuile, rep_x=3, rep_y=3)
            chemin_preview = os.path.join(output_dir, f"{nom_base}_tile_preview3x3.png")
            img_preview.save(chemin_preview, "PNG")
            self.log(f"Aperçu de tuilage 3x3 généré : {chemin_preview}", emoji="🖼️")

        return {
            "tile_path": chemin_tuile,
            "preview_path": chemin_preview,
            "dimensions": img_tuile.size
        }
