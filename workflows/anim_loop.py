#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Anim Loop : Boucles de Textures & Shaders Animés (AnimateDiff / LTX Loop Engine) pour Godot 4.
Produit :
- Planche de spritesheet d'animation cyclique (Atlas)
- Shader Godot 4 (.gdshader) avec double-échantillonnage temporel déphasé sans saccade
- Ressource ShaderMaterial (.tres)
- Ressource AnimatedTexture (.tres) pour UI et CanvasItem
"""

import os
from pathlib import Path
from typing import Any, Dict, List
from PIL import Image

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.loop_ops import (
    assembler_spritesheet_loop,
    creer_boucle_temporelle_circulaire,
    exporter_animated_texture_godot,
    exporter_shader_loop_godot,
    generer_sequence_vfx_boucle
)
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class AnimLoopWorkflow(BaseWorkflow):
    """Génération de boucles de textures et shaders animés continus pour Godot 4."""

    name = "anim_loop"
    description = "Boucles de textures & shaders animés fluides (AnimateDiff / LTX Loop) pour Godot 4 (.gdshader / .tres)"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        prompt = params.get("prompt") or "magical portal vortex"
        input_image = params.get("input")
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        nb_trames = int(params.get("frames", 16)) or 16
        fps = float(params.get("fps", 12.0))
        colonnes = int(params.get("columns", 4))
        mode_2d = bool(params.get("mode_2d", False))
        vfx_type = params.get("vfx_type") or params.get("flow_type") or "portal"

        nom_base = params.get("output") or f"{slugifier_texte(prompt)}_loop"
        os.makedirs(output_dir, exist_ok=True)

        self.log(f"Génération de la séquence temporelle en boucle ({nb_trames} trames, type '{vfx_type}')...")

        # 1. Génération de la séquence d'animation
        if input_image and os.path.exists(input_image):
            self.log(f"Utilisation de l'image source pour bouclage : {input_image}")
            img_src = Image.open(input_image).convert("RGBA")
            # Création de variations périodiques
            trames_brutes = []
            for i in range(nb_trames):
                angle = (360.0 * i) / nb_trames
                t_rot = img_src.rotate(angle, resample=Image.Resampling.BICUBIC)
                trames_brutes.append(t_rot)
        else:
            trames_brutes = generer_sequence_vfx_boucle(resolution=512, nb_trames=nb_trames, type_effet=vfx_type)

        # 2. Bouclage harmonique 360° (phase blending)
        self.log("Application du fondu croisé circulaire harmonique (Seamless Time Loop)...")
        trames_bouclees = creer_boucle_temporelle_circulaire(trames_brutes)

        # 3. Assemblage Spritesheet
        spritesheet = assembler_spritesheet_loop(trames_bouclees, colonnes=colonnes)
        chemin_sheet = os.path.join(output_dir, f"{nom_base}_spritesheet.png")
        spritesheet.save(chemin_sheet, "PNG")

        # 4. Exportation Shaders et AnimatedTexture Godot 4
        self.log("Génération des shaders et ressources Godot 4...")
        chemin_shader, chemin_mat = exporter_shader_loop_godot(nom_base, output_dir, mode_2d=mode_2d)
        chemin_anim = exporter_animated_texture_godot(nom_base, output_dir, nb_trames=nb_trames, fps=fps)

        self.log(f"Boucle animée exportée avec succès dans '{output_dir}/' :", emoji="🎉")
        self.log(f"  • Spritesheet Loop : {chemin_sheet}")
        self.log(f"  • Shader Godot 4   : {chemin_shader}")
        self.log(f"  • ShaderMaterial   : {chemin_mat}")
        self.log(f"  • AnimatedTexture  : {chemin_anim}", emoji="💎")

        return {
            "spritesheet": chemin_sheet,
            "shader": chemin_shader,
            "material": chemin_mat,
            "animated_texture": chemin_anim,
            "frames_count": nb_trames,
            "files": [chemin_sheet, chemin_shader, chemin_mat, chemin_anim]
        }
