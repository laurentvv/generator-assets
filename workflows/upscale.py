#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Upscale : Super-résolution haute fidélité pour assets 2D.
Supporte les modèles IA ESRGAN (RealESRGAN_x4plus, Anime_6B, 4x-UltraSharp) sous Vulkan et Smart Lanczos.
"""

import os
from pathlib import Path
from typing import Any, Dict
from PIL import Image

from core.config import DEFAULT_OUTPUT_DIR, resoudre_upscaler, slugifier_texte
from core.upscaler import upscaler_asset, upscale_video
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class UpscaleWorkflow(BaseWorkflow):
    name = "upscale"
    description = "Super-résolution IA (ESRGAN Vulkan / Lanczos) pour Images et Vidéos (.webm / .mp4)"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        input_path = params.get("input")
        if not input_path or not os.path.exists(input_path):
            raise FileNotFoundError(f"Fichier source introuvable : {input_path}")

        facteur = float(params.get("factor", 2.0))
        taille_cible = params.get("size")
        mode = params.get("mode", "auto")
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        nom_sortie = params.get("output")
        modele_demande = params.get("upscale_model") or self.config.get("esrgan_model")

        os.makedirs(output_dir, exist_ok=True)

        # 1. Détection et traitement des fichiers Vidéo (.webm, .mp4, .avi)
        ext_in = Path(input_path).suffix.lower()
        if ext_in in [".webm", ".mp4", ".avi", ".mov", ".mkv"]:
            self.log(f"🎬 Détection d'un fichier vidéo : {input_path}")
            stem_source = Path(input_path).stem
            nom_final = nom_sortie or f"{stem_source}_upscaled_{int(facteur)}x.mp4"
            if not nom_final.lower().endswith((".mp4", ".webm")):
                nom_final += ".mp4"
            chemin_sortie = os.path.join(output_dir, nom_final)

            video_upscaled = upscale_video(
                video_input_path=input_path,
                output_path=chemin_sortie,
                facteur=facteur,
                taille_cible=taille_cible,
                mode=mode,
                upscale_model=modele_demande,
                sd_cli=self.config.get("sd_cli"),
                backend=self.config.get("backend", "diffusion=vulkan0,te=cpu"),
                log_fn=self.log
            )

            # Scène Godot 4 VideoStreamPlayer associée
            godot_scene = os.path.splitext(video_upscaled)[0] + "_player.tscn"
            rel_name = os.path.basename(video_upscaled)
            try:
                with open(godot_scene, "w", encoding="utf-8") as f:
                    f.write(f"""[gd_scene format=3 uid="uid://video_{slugifier_texte(stem_source)}"]

[node name="VideoPlayer" type="VideoStreamPlayer"]
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2
autoplay = true
loop = true
expand = true
# stream = ExtResource("res://assets/{rel_name}")
""")
            except Exception as e:
                self.log(f"Avertissement création scène Godot : {e}", emoji="⚠️")

            return {
                "output_path": video_upscaled,
                "godot_scene": godot_scene,
                "is_video": True
            }

        # 2. Traitement standard des Images 2D
        img_source = Image.open(input_path)
        self.log(f"Chargement de l'image source : {input_path} ({img_source.size[0]}x{img_source.size[1]} {img_source.mode})")

        img_upscaled = upscaler_asset(
            image_entree=img_source,
            facteur=facteur,
            taille_cible=taille_cible,
            mode=mode,
            upscale_model=modele_demande,
            sd_cli=self.config.get("sd_cli"),
            backend=self.config.get("backend", "diffusion=vulkan0,te=cpu")
        )

        stem_source = Path(input_path).stem
        nom_final = nom_sortie or f"{stem_source}_upscaled_{img_upscaled.size[0]}x{img_upscaled.size[1]}"
        chemin_sortie = os.path.join(output_dir, f"{Path(nom_final).stem}.png")

        img_upscaled.save(chemin_sortie, "PNG")
        self.log(f"Image agrandie sauvegardée : {chemin_sortie} ({img_upscaled.size[0]}x{img_upscaled.size[1]} {img_upscaled.mode})", emoji="✅")

        return {
            "output_path": chemin_sortie,
            "image": img_upscaled,
            "dimensions": img_upscaled.size
        }
