#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Variations : Génération de variantes d'éléments, tiers ou skins.
Prend une image de base ou un concept et génère plusieurs déclinaisons (Feu, Glace, Poison, Vide, Foudre, etc.).
"""

import os
from pathlib import Path
from typing import Any, Dict, List
from PIL import Image

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.diffusion import generer_image_vulkan
from core.image_ops import post_process_asset
from core.llm import construire_prompt_coherant
from workflows.base import BaseWorkflow, WorkflowRegistry

THEMES_DEFAUT = ["feu / flammes ardentes", "glace / givre cristallin", "poison / acide toxique", "foudre / electricite", "vide abyssal"]


@WorkflowRegistry.register
class VariationsWorkflow(BaseWorkflow):
    name = "variations"
    description = "Génération de variantes thématiques (Feu, Glace, Poison, Foudre, etc.) pour un asset"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        concept = params.get("prompt")
        input_image = params.get("input")

        if not concept and not input_image:
            raise ValueError("Le paramètre 'prompt' ou 'input' est requis pour les variations.")

        if not concept and input_image:
            concept = Path(input_image).stem.replace("_", " ")

        themes_input = params.get("themes")
        if isinstance(themes_input, str):
            themes = [t.strip() for t in themes_input.split(",") if t.strip()]
        elif isinstance(themes_input, list):
            themes = themes_input
        else:
            themes = THEMES_DEFAUT

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        taille = params.get("size", 512)
        tolerance = params.get("tolerance", 60)
        nom_base = params.get("output") or slugifier_texte(concept)

        os.makedirs(output_dir, exist_ok=True)
        self.log(f"Génération de {len(themes)} variantes pour '{concept}'...")

        resultats = []

        for theme in themes:
            theme_slug = slugifier_texte(theme, max_longueur=20)
            self.log(f"Variante thématique : {theme.upper()}...")

            concept_variante = f"{concept} (version {theme})"
            prompt_variante = construire_prompt_coherant(
                concept=concept_variante,
                type_asset=params.get("type", "item"),
                llama_cli=self.config.get("llama_cli"),
                llm_model=self.config.get("llm_model"),
                style_anchor=self.config.get("style_anchor"),
                sans_llm=params.get("sans_llm", params.get("no_llm", True))
            )

            # Rendu Flux.1
            img_brute = generer_image_vulkan(
                prompt=prompt_variante,
                sd_cli=self.config.get("sd_cli"),
                sd_model=self.config.get("sd_model"),
                clip_l=self.config.get("clip_l"),
                t5xxl=self.config.get("t5xxl"),
                vae=self.config.get("vae"),
                backend=self.config.get("backend"),
                threads=self.config.get("threads"),
                steps=params.get("steps", 25),
                guidance=params.get("guidance", 3.5),
                init_img=input_image if input_image and os.path.exists(input_image) else None,
                strength=float(params.get("strength", 0.70))
            )

            img_traitee = post_process_asset(
                image=img_brute,
                tolerance=tolerance,
                redimensionner=taille
            )

            chemin_fichier = os.path.join(output_dir, f"{nom_base}_{theme_slug}.png")
            img_traitee.save(chemin_fichier, "PNG")
            resultats.append(chemin_fichier)
            self.log(f"Variante créée : {chemin_fichier}", emoji="✅")

        return {
            "variants": resultats,
            "total": len(resultats)
        }
