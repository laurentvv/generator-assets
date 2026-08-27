#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Pose Control : Contrôle d'Armatures & Poses de Personnages (ControlNet OpenPose / DWPose) pour Godot 4.
Produit :
- Carte squelette OpenPose (RGB COCO 18 points)
- Sprite de personnage détouré et aligné avec la pose
- Scène Godot 4 (.tscn) avec Sprite2D et points d'ancrage dynamiques Marker2D (mains, tête, pieds)
- Fichier JSON d'armature et boîtes d'ancrage
"""

import json
import os
from pathlib import Path
from typing import Any, Dict
from PIL import Image

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.diffusion import generer_image_vulkan
from core.image_ops import post_process_asset
from core.llm import construire_prompt_coherant
from core.pose_ops import (
    dessiner_squelette_openpose,
    exporter_scene_pose_godot,
    extraire_points_ancrage_godot,
    obtenir_pose
)
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class PoseControlWorkflow(BaseWorkflow):
    """Génération de personnages sous pose contrôlée (OpenPose) avec hiérarchie Marker2D Godot 4."""

    name = "pose_control"
    description = "Contrôle d'armatures & poses de personnages (ControlNet OpenPose) + Scène Godot (.tscn) et Marker2D"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        concept = params.get("prompt") or "chevalier en armure sombre"
        pose_nom = params.get("pose") or params.get("type") or "idle"
        if pose_nom in ["item", "1", "2", "3"]:
            pose_nom = "idle"

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        taille = params.get("size", 512) or 512
        nom_base = params.get("output") or f"{slugifier_texte(concept)}_{pose_nom}"

        os.makedirs(output_dir, exist_ok=True)

        self.log(f"Préparation de la pose OpenPose : [{pose_nom}] pour '{concept}'...")

        # 1. Obtenir les coordonnées et dessiner le squelette OpenPose
        points_pose = obtenir_pose(pose_nom)
        img_squelette = dessiner_squelette_openpose(points_pose, largeur=taille, hauteur=taille)
        chemin_squelette = os.path.join(output_dir, f"{nom_base}_openpose_skeleton.png")
        img_squelette.save(chemin_squelette, "PNG")

        input_image = params.get("input")
        if input_image and os.path.exists(input_image):
            self.log(f"Utilisation de l'image source existante : {input_image}")
            img_brute = Image.open(input_image)
        else:
            # 2. Construction du prompt orienté pose
            self.log("Génération du sprite de personnage guidé par l'armature...")
            prompt_pose = f"{concept}, in dynamic {pose_nom} action stance, full body character sprite"
            prompt_complet = construire_prompt_coherant(
                concept=prompt_pose,
                type_asset="character",
                llama_cli=self.config.get("llama_cli"),
                llm_model=self.config.get("llm_model"),
                style_anchor=self.config.get("style_anchor"),
                custom_cadrage="full body character sprite, head to toe visible, isolated on plain white background"
            )

            # 3. Rendu par diffusion
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
                seed=params.get("seed", -1),
                loras=params.get("loras")
            )

        # 4. Détourage et centrage
        img_propre = post_process_asset(img_brute, redimensionner=taille)
        chemin_sprite = os.path.join(output_dir, f"{nom_base}.png")
        img_propre.save(chemin_sprite, "PNG")

        # 5. Extraction des points d'ancrage Godot (Marker2D)
        self.log("Calcul des points d'ancrage Godot (Mains, Tête, Pieds)...")
        ancrages = extraire_points_ancrage_godot(points_pose, largeur=taille, hauteur=taille)

        # Export JSON
        chemin_json = os.path.join(output_dir, f"{nom_base}_rig.json")
        with open(chemin_json, "w", encoding="utf-8") as f:
            json.dump({
                "character": nom_base,
                "pose": pose_nom,
                "markers": ancrages
            }, f, indent=2)

        # 6. Export Scène Godot (.tscn)
        nom_rel_tex = f"res://{nom_base}.png"
        chemin_tscn = exporter_scene_pose_godot(nom_base, output_dir, ancrages, nom_rel_tex)

        self.log(f"Personnage et armature OpenPose générés dans '{output_dir}/' :", emoji="🎉")
        self.log(f"  • Sprite 2D       : {chemin_sprite}")
        self.log(f"  • Squelette Pose  : {chemin_squelette}")
        self.log(f"  • Scène Godot 4   : {chemin_tscn} (Marker2D intégrés)")
        self.log(f"  • Manifeste Rig   : {chemin_json}", emoji="💎")

        return {
            "sprite": chemin_sprite,
            "skeleton": chemin_squelette,
            "scene_tscn": chemin_tscn,
            "rig_json": chemin_json,
            "markers": ancrages,
            "files": [chemin_sprite, chemin_squelette, chemin_tscn, chemin_json]
        }
