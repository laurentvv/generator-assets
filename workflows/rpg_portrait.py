#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow RPG Portrait : Galerie de Portraits de Personnages Multi-Émotions pour Dialogues RPG dans Godot 4.
Produit :
- Portraits individuels détourés (Neutre, Joie, Colère, Tristesse, Surprise, Blessé)
- Planche récapitulative des expressions
- Base de données JSON prête pour les systèmes de dialogues Godot (Dialogic / Custom)
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List
from PIL import Image

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.diffusion import generer_image_vulkan
from core.image_ops import post_process_asset
from core.llm import construire_prompt_coherant
from workflows.base import BaseWorkflow, WorkflowRegistry

# Descriptions des émotions pour le prompt
EMOTION_PROMPTS = {
    "neutral": "neutral calm serious expression, closed mouth, direct eye contact",
    "happy": "warm gentle smile, happy bright eyes, pleased joyful expression",
    "angry": "fierce angry expression, furrowed eyebrows, intense shouting grimace, wrathful eyes",
    "sad": "sad mournful expression, downcast eyes, slight sorrowful frown, melancholic",
    "surprised": "shocked surprised wide eyes, slightly open mouth, astonishment",
    "hurt": "strained pained expression, gritting teeth, bruised wincing face, battle damage"
}


def assembler_grille_portraits(portraits: List[Image.Image], colonnes: int = 3) -> Image.Image:
    """Assemble une liste de portraits en une grille récapitulative."""
    if not portraits:
        return Image.new("RGBA", (1, 1))
    pw, ph = portraits[0].size
    nb = len(portraits)
    lignes = (nb + colonnes - 1) // colonnes

    grid = Image.new("RGBA", (pw * colonnes, ph * lignes), (0, 0, 0, 0))
    for idx, p in enumerate(portraits):
        c = idx % colonnes
        l = idx // colonnes
        grid.paste(p, (c * pw, l * ph))
    return grid


@WorkflowRegistry.register
class RPGPortraitWorkflow(BaseWorkflow):
    """Génération de galeries de dialogues RPG multi-émotions pour Godot 4."""

    name = "rpg_portrait"
    description = "Galerie de portraits de dialogues RPG avec émotions cohérentes (Neutre, Joie, Colère, etc.) + JSON Godot"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        concept = params.get("prompt")
        input_image = params.get("input")

        if not concept and not input_image:
            raise ValueError("Le workflow rpg_portrait nécessite un 'prompt' ou une image de référence '-i / --input'.")

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        taille = params.get("size", 512) or 512
        emotions_str = params.get("emotions", "neutral,happy,angry,sad,hurt")
        emotions_list = [e.strip().lower() for e in emotions_str.split(",") if e.strip()]
        seed_base = params.get("seed", -1)
        if seed_base == -1:
            import random
            seed_base = random.randint(1, 999999)

        nom_perso = params.get("output") or (Path(input_image).stem if input_image else slugifier_texte(concept))
        os.makedirs(output_dir, exist_ok=True)

        dossier_perso = os.path.join(output_dir, f"{nom_perso}_dialogues")
        os.makedirs(dossier_perso, exist_ok=True)

        self.log(f"Génération des portraits RPG pour '{nom_perso}' ({len(emotions_list)} émotions)...")

        images_portraits = []
        dialogue_database = {
            "character_id": nom_perso,
            "seed": seed_base,
            "portraits": {}
        }

        style_portrait = (
            "2D RPG visual novel character portrait, bust shot, head and shoulders, "
            "dark fantasy digital painting, crisp clean edges, isolated on solid plain white background"
        )

        for emo in emotions_list:
            desc_emo = EMOTION_PROMPTS.get(emo, f"{emo} facial expression")
            self.log(f"  • Rendu de l'expression : [{emo}]...")

            if input_image and os.path.exists(input_image):
                # Utiliser l'image fournie comme base (si une seule émotion)
                img_brute = Image.open(input_image)
            else:
                prompt_emo = f"{concept}, {desc_emo}"
                prompt_complet = construire_prompt_coherant(
                    concept=prompt_emo,
                    type_asset="character",
                    llama_cli=self.config.get("llama_cli"),
                    llm_model=self.config.get("llm_model"),
                    style_anchor=style_portrait,
                    custom_cadrage="bust shot portrait, head and shoulders centered",
                    sans_llm=params.get("sans_llm", params.get("no_llm", True))
                )

                img_brute = generer_image_vulkan(
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
                    seed=seed_base,  # Même graine pour maximiser la cohérence
                    loras=params.get("loras")
                )

            # Détourage et centrage
            img_propre = post_process_asset(img_brute, redimensionner=taille)
            chemin_emo = os.path.join(dossier_perso, f"{nom_perso}_{emo}.png")
            img_propre.save(chemin_emo, "PNG")

            images_portraits.append(img_propre)
            dialogue_database["portraits"][emo] = f"res://{dossier_perso}/{nom_perso}_{emo}.png".replace("\\", "/")

        # Planche récapitulative
        grid_img = assembler_grille_portraits(images_portraits, colonnes=3)
        chemin_grille = os.path.join(output_dir, f"{nom_perso}_expressions_grid.png")
        grid_img.save(chemin_grille, "PNG")

        # Export JSON pour système de dialogue Godot
        chemin_json = os.path.join(dossier_perso, f"{nom_perso}_dialogue.json")
        with open(chemin_json, "w", encoding="utf-8") as f:
            json.dump(dialogue_database, f, indent=2, ensure_ascii=False)

        self.log(f"Galerie de dialogues RPG prête dans '{dossier_perso}/' :", emoji="🎉")
        self.log(f"  • Planche Globale  : {chemin_grille}")
        self.log(f"  • Base de données  : {chemin_json} (JSON Godot)", emoji="💎")

        return {
            "dialogue_json": chemin_json,
            "grid_preview": chemin_grille,
            "emotions": list(dialogue_database["portraits"].keys()),
            "files": [chemin_json, chemin_grille]
        }
