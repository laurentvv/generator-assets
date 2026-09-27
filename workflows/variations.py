#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Variations workflow: generating variants of items, tiers or skins.
Takes a base image or a concept and generates several declinations (Fire, Ice, Poison, Void, Lightning, etc.).
"""

import os
from pathlib import Path
from typing import Any, Dict

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.diffusion import generer_image_vulkan
from core.image_ops import post_process_asset
from core.llm import construire_prompt_coherant
from workflows.base import BaseWorkflow, WorkflowRegistry

THEMES_DEFAUT = ["feu / flammes ardentes", "glace / givre cristallin", "poison / acide toxique", "foudre / electricite", "vide abyssal"]


@WorkflowRegistry.register
class VariationsWorkflow(BaseWorkflow):
    name = "variations"
    description = "Thematic variant generation (Fire, Ice, Poison, Lightning, etc.) for an asset"

    emoji = "🌈"

    # CLI declaration (audit §2.2, migration from the flat table of cli/parser.py:
    # help/defaults taken as-is, unchanged surface). --themes is also read
    # by ip_adapter (same 2D family): it lives here, primary user of the help.
    PARAMETRES = [
        dict(flags=("--themes",),
             help="Comma-separated list of themes for the variations workflow."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        concept = params.get("prompt")
        input_image = params.get("input")

        if not concept and not input_image:
            raise ValueError("The 'prompt' or 'input' parameter is required for variations.")

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
        self.log(f"Generating {len(themes)} variants for '{concept}'...")

        resultats = []

        for theme in themes:
            theme_slug = slugifier_texte(theme, max_longueur=20)
            self.log(f"Thematic variant: {theme.upper()}...")

            concept_variante = f"{concept} (version {theme})"
            prompt_variante = construire_prompt_coherant(
                concept=concept_variante,
                type_asset=params.get("type", "item"),
                llama_cli=self.config.get("llama_cli"),
                llm_model=self.config.get("llm_model"),
                style_anchor=self.config.get("style_anchor"),
                sans_llm=params.get("sans_llm", params.get("no_llm", True))
            )

            # Flux.1 render
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
            self.log(f"Variant created: {chemin_fichier}", emoji="✅")

        return {
            "variants": resultats,
            "total": len(resultats)
        }
