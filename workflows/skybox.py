#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Skybox : Génération de ciel / panorama 360° équirectangulaire pour Godot 3D.
Génère une image 2:1 (ex: 2048x1024) avec boucle horizontale et exporte la ressource Environment (.tres).
"""

import os
from pathlib import Path
from typing import Any, Dict
from PIL import Image

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.diffusion import generer_image_vulkan
from core.image_ops import exporter_fichier_skybox_godot
from core.llm import construire_prompt_coherant
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class SkyboxWorkflow(BaseWorkflow):
    name = "skybox"
    description = "Génération d'Environnement Skybox 360° équirectangulaire et fichier Environment Godot 4"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        concept = params.get("prompt")
        if not concept:
            raise ValueError("Le paramètre 'prompt' est requis pour le workflow skybox.")

        nom_base = params.get("output") or f"{slugifier_texte(concept)}_sky"
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        largeur = int(params.get("width", 2048))
        hauteur = int(params.get("height", 1024))

        os.makedirs(output_dir, exist_ok=True)
        self.log(f"Génération d'un panorama 360° pour '{concept}' ({largeur}x{hauteur})...")

        style_skybox = (
            "360 degree equirectangular panorama projection, seamless spherical environment map, "
            "atmospheric horizon, ultra wide dynamic range, game skybox background, photorealistic digital matte painting"
        )

        prompt_complet = construire_prompt_coherant(
            concept=concept,
            type_asset="tile",
            llama_cli=self.config.get("llama_cli"),
            llm_model=self.config.get("llm_model"),
            style_anchor=style_skybox,
            custom_cadrage="360 equirectangular spherical panorama, horizontal seamless looping"
        )

        # Rendu 2:1
        img_sky = generer_image_vulkan(
            prompt=prompt_complet,
            sd_cli=self.config.get("sd_cli"),
            sd_model=self.config.get("sd_model"),
            clip_l=self.config.get("clip_l"),
            t5xxl=self.config.get("t5xxl"),
            vae=self.config.get("vae"),
            backend=self.config.get("backend"),
            threads=self.config.get("threads"),
            width=1024,
            height=512,
            circular=True,
            steps=params.get("steps", 25),
            guidance=params.get("guidance", 3.5),
            seed=params.get("seed", -1),
            loras=params.get("loras")
        )

        # Agrandir à la taille demandée (ex: 2048x1024)
        if (largeur, hauteur) != img_sky.size:
            img_sky = img_sky.resize((largeur, hauteur), Image.Resampling.LANCZOS)

        chemin_sky = os.path.join(output_dir, f"{nom_base}.png")
        img_sky.save(chemin_sky, "PNG")

        # Exporter la ressource Environment Godot 4
        chemin_tres = exporter_fichier_skybox_godot(nom_base, output_dir)

        self.log(f"Texture Skybox 360° sauvegardée : {chemin_sky}", emoji="🌌")
        self.log(f"Ressource Environment Godot 4 prête : {chemin_tres}", emoji="💎")

        return {
            "sky_texture": chemin_sky,
            "environment_tres": chemin_tres,
            "dimensions": img_sky.size
        }
