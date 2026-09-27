#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pose Control workflow: Armature & character pose control (ControlNet OpenPose / DWPose) for Godot 4.
Produces:
- OpenPose skeleton map (RGB COCO 18 points)
- Cut-out character sprite aligned with the pose
- Godot 4 scene (.tscn) with Sprite2D and dynamic Marker2D anchor points (hands, head, feet)
- Armature JSON file and anchor boxes
"""

import json
import os
from typing import Any, Dict
from PIL import Image

from core.config import DEFAULT_CONTROLNET_POSE, DEFAULT_OUTPUT_DIR, DEFAULT_SDXL_MODEL, slugifier_texte
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
    """Character generation under controlled pose (OpenPose) with Godot 4 Marker2D hierarchy."""

    name = "pose_control"
    description = "Armature & character pose control (ControlNet OpenPose) + Godot scene (.tscn) and Marker2D"

    emoji = "🕺"

    # CLI declaration (audit §2.2, migration from the flat table of cli/parser.py:
    # help/defaults taken as-is, unchanged surface).
    PARAMETRES = [
        dict(flags=("--pose",), choices=["idle", "slash_attack", "cast_spell", "shield_block", "jump", "walk"], default="idle",
             help="OpenPose pose for pose_control."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        concept = params.get("prompt") or "chevalier en armure sombre"
        pose_nom = params.get("pose") or params.get("type") or "idle"
        if pose_nom in ["item", "1", "2", "3"]:
            pose_nom = "idle"

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        taille = params.get("size", 512) or 512
        nom_base = params.get("output") or f"{slugifier_texte(concept)}_{pose_nom}"
        chemin_controlnet = self.config.get("controlnet_pose", DEFAULT_CONTROLNET_POSE)

        os.makedirs(output_dir, exist_ok=True)

        self.log(f"Preparing the OpenPose pose: [{pose_nom}] for '{concept}'...")

        # 1. Get the coordinates and draw the OpenPose skeleton
        points_pose = obtenir_pose(pose_nom)
        img_squelette = dessiner_squelette_openpose(points_pose, largeur=taille, hauteur=taille)
        chemin_squelette = os.path.join(output_dir, f"{nom_base}_openpose_skeleton.png")
        img_squelette.save(chemin_squelette, "PNG")

        input_image = params.get("input")
        if input_image and os.path.exists(input_image):
            self.log(f"Using the existing source image: {input_image}")
            img_brute = Image.open(input_image)
        else:
            # 2. Pose-oriented prompt construction
            self.log("Generating the armature-guided character sprite...")
            prompt_pose = f"{concept}, in dynamic {pose_nom} action stance, full body character sprite"
            prompt_complet = construire_prompt_coherant(
                concept=prompt_pose,
                type_asset="character",
                llama_cli=self.config.get("llama_cli"),
                llm_model=self.config.get("llm_model"),
                style_anchor=self.config.get("style_anchor"),
                custom_cadrage="full body character sprite, head to toe visible, isolated on plain white background",
                sans_llm=params.get("sans_llm", params.get("no_llm", True))
            )

            # 3. Diffusion render — REAL ControlNet conditioning when the OpenPose
            # ControlNet model is present (recipe validated 2026-09-26, MEMORY_BANK §1.29:
            # the skeleton imposes the pose instead of only steering the prompt);
            # otherwise historical prompt-only fallback (skeleton = Marker2D artifact only).
            kwargs_rendu = dict(
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
            if os.path.exists(chemin_squelette) and os.path.exists(chemin_controlnet):
                # The xinsir ControlNet is SDXL only (sd-cli refuses Flux):
                # switch to the SDXL checkpoint validated with the recipe.
                modele_controlnet = self.config.get("controlnet_sd_model", DEFAULT_SDXL_MODEL)
                if os.path.exists(modele_controlnet):
                    self.log(f"Conditionnement ControlNet OpenPose : {os.path.basename(chemin_controlnet)}"
                             f" + SDXL model {os.path.basename(modele_controlnet)}")
                    kwargs_rendu.update(sd_model=modele_controlnet, control_image=chemin_squelette,
                                        control_net=chemin_controlnet, control_strength=0.9)
                else:
                    self.log(f"⚠️ SDXL checkpoint not found ({modele_controlnet}) — prompt-only generation.")
            else:
                self.log("⚠️ OpenPose ControlNet missing — prompt-only generation (pose not guaranteed).")
            img_brute = generer_image_vulkan(**kwargs_rendu)

        # 4. Cutout and centering
        img_propre = post_process_asset(img_brute, redimensionner=taille)
        chemin_sprite = os.path.join(output_dir, f"{nom_base}.png")
        img_propre.save(chemin_sprite, "PNG")

        # 5. Godot anchor point extraction (Marker2D)
        self.log("Computing the Godot anchor points (Hands, Head, Feet)...")
        ancrages = extraire_points_ancrage_godot(points_pose, largeur=taille, hauteur=taille)

        # Export JSON
        chemin_json = os.path.join(output_dir, f"{nom_base}_rig.json")
        with open(chemin_json, "w", encoding="utf-8") as f:
            json.dump({
                "character": nom_base,
                "pose": pose_nom,
                "markers": ancrages
            }, f, indent=2)

        # 6. Godot scene export (.tscn)
        nom_rel_tex = f"res://{nom_base}.png"
        chemin_tscn = exporter_scene_pose_godot(nom_base, output_dir, ancrages, nom_rel_tex)

        self.log(f"Character and OpenPose armature generated in '{output_dir}/':", emoji="🎉")
        self.log(f"  • Sprite 2D       : {chemin_sprite}")
        self.log(f"  • Pose skeleton   : {chemin_squelette}")
        self.log(f"  • Godot 4 scene   : {chemin_tscn} (built-in Marker2D)")
        self.log(f"  • Rig manifest    : {chemin_json}", emoji="💎")

        return {
            "sprite": chemin_sprite,
            "skeleton": chemin_squelette,
            "scene_tscn": chemin_tscn,
            "rig_json": chemin_json,
            "markers": ancrages,
            "files": [chemin_sprite, chemin_squelette, chemin_tscn, chemin_json]
        }
