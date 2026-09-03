#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow IP-Adapter : Cohérence d'Assets & Charte Graphique pour Jeux Vidéo (Godot 4).
Produit :
- Série d'assets dérivés partageant strictement la palette, les matériaux et le style de l'image de référence
- Planche de cohérence visuelle comparative (Consistency Board)
- Ressources de palette de couleurs Godot 4 (.tres), Aseprite (.gpl) et JSON
"""

import os
from pathlib import Path
from typing import Any, Dict, List
from PIL import Image

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.diffusion import generer_image_vulkan
from core.image_ops import post_process_asset
from core.llm import construire_prompt_coherant
from core.style_ops import (
    analyser_signature_stylistique,
    assembler_planche_coherence,
    exporter_palette_godot,
    extraire_palette_image
)
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class IPAdapterWorkflow(BaseWorkflow):
    """Génération cohérente d'assets avec verrouillage de style (IP-Adapter) et palettes Godot 4."""

    name = "ip_adapter"
    description = "Cohérence de style & charte graphique (IP-Adapter) depuis une image de référence + Palettes Godot"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        input_image_path = params.get("input")
        concept = params.get("prompt")

        if not input_image_path and not concept:
            raise ValueError("Le workflow ip_adapter requiert une image de référence '-i / --input' ou un concept 'prompt'.")

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        taille = params.get("size", 512) or 512
        items_str = params.get("themes") or params.get("items") or "sword,shield,potion,helmet"
        items_list = [it.strip() for it in items_str.split(",") if it.strip()]

        seed = params.get("seed", -1)
        if seed == -1:
            import random
            seed = random.randint(1, 999999)

        nom_base = params.get("output") or (Path(input_image_path).stem if input_image_path else slugifier_texte(concept))
        os.makedirs(output_dir, exist_ok=True)
        dossier_set = os.path.join(output_dir, f"{nom_base}_consistent_set")
        os.makedirs(dossier_set, exist_ok=True)

        # 1. Charger ou générer l'image de référence
        if input_image_path and os.path.exists(input_image_path):
            self.log(f"Chargement de l'image de référence stylistique : {input_image_path}")
            img_ref = Image.open(input_image_path).convert("RGBA")
        else:
            self.log(f"Génération de l'asset de référence pour '{concept}'...")
            prompt_ref = construire_prompt_coherant(
                concept=concept,
                type_asset="item",
                llama_cli=self.config.get("llama_cli"),
                llm_model=self.config.get("llm_model"),
                style_anchor=self.config.get("style_anchor"),
                sans_llm=params.get("sans_llm", params.get("no_llm", True))
            )
            img_brute = generer_image_vulkan(
                prompt=prompt_ref,
                sd_cli=self.config.get("sd_cli"),
                sd_model=self.config.get("sd_model"),
                clip_l=self.config.get("clip_l"),
                t5xxl=self.config.get("t5xxl"),
                vae=self.config.get("vae"),
                backend=self.config.get("backend"),
                threads=self.config.get("threads"),
                steps=params.get("steps", 25),
                guidance=params.get("guidance", 3.5),
                seed=seed,
                loras=params.get("loras")
            )
            img_ref = post_process_asset(img_brute, redimensionner=taille)
            chemin_ref_save = os.path.join(dossier_set, f"{nom_base}_reference.png")
            img_ref.save(chemin_ref_save, "PNG")

        # 2. Analyse stylistique et extraction de palette
        self.log("Extraction de la signature de style et de la palette de couleurs...")
        palette = extraire_palette_image(img_ref, n_couleurs=6)
        style_verrouille = analyser_signature_stylistique(img_ref, palette)

        # Exportation des formats de palettes Godot
        p_tres, p_gpl, p_json, p_png = exporter_palette_godot(nom_base, dossier_set, palette)
        self.log(f"Palette de couleurs exportée dans '{dossier_set}/' :")
        self.log(f"  • Ressource Godot 4 : {p_tres}")
        self.log(f"  • Format Aseprite   : {p_gpl}")

        # 3. Génération des assets cohérents dérivés
        self.log(f"Génération de la série cohérente ({len(items_list)} items)...")
        variantes_produites = []
        fichiers_items = []

        for item_name in items_list:
            self.log(f"  • Déclinaison de l'item : [{item_name}]...")
            prompt_item = f"{item_name}, {style_verrouille}"

            prompt_complet = construire_prompt_coherant(
                concept=prompt_item,
                type_asset="item",
                llama_cli=self.config.get("llama_cli"),
                llm_model=self.config.get("llm_model"),
                style_anchor=self.config.get("style_anchor"),
                custom_cadrage="isolated single game icon, clean transparent background",
                sans_llm=params.get("sans_llm", params.get("no_llm", True))
            )

            img_item_brute = generer_image_vulkan(
                prompt=prompt_complet,
                sd_cli=self.config.get("sd_cli"),
                sd_model=self.config.get("sd_model"),
                clip_l=self.config.get("clip_l"),
                t5xxl=self.config.get("t5xxl"),
                vae=self.config.get("vae"),
                backend=self.config.get("backend"),
                threads=self.config.get("threads"),
                steps=params.get("steps", 25),
                guidance=params.get("guidance", 3.5),
                seed=seed,  # Même seed pour la cohérence
                loras=params.get("loras")
            )

            img_item = post_process_asset(img_item_brute, redimensionner=taille)
            nom_item_slug = slugifier_texte(item_name)
            chemin_item = os.path.join(dossier_set, f"{nom_base}_{nom_item_slug}.png")
            img_item.save(chemin_item, "PNG")

            variantes_produites.append((item_name, img_item))
            fichiers_items.append(chemin_item)

        # 4. Assemblage de la planche de cohérence
        planche = assembler_planche_coherence(img_ref, variantes_produites, taille_cellule=256)
        chemin_planche = os.path.join(output_dir, f"{nom_base}_consistency_board.png")
        planche.save(chemin_planche, "PNG")

        self.log(f"Set d'assets cohérents généré avec succès dans '{dossier_set}/' :", emoji="🎉")
        self.log(f"  • Planche Globale : {chemin_planche}")
        self.log(f"  • Palette Godot   : {p_tres}", emoji="💎")

        return {
            "board": chemin_planche,
            "palette_tres": p_tres,
            "palette_gpl": p_gpl,
            "items": fichiers_items,
            "files": [chemin_planche, p_tres, p_gpl] + fichiers_items
        }
