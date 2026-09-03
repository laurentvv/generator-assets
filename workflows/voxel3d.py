#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Voxel 3D : Transformation de sprites 2D ou concepts en modèles 3D Voxel (.GLB) pour Godot 4 & GridMap.
"""

import os
from pathlib import Path
from typing import Any, Dict
import numpy as np
from PIL import Image

from core.blender_ops import verifier_blender
from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.diffusion import generer_image_vulkan
from core.image_ops import post_process_asset
from core.llm import construire_prompt_coherant
from core.voxel_ops import exporter_voxel_glb, image_vers_grille_voxels
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class Voxel3DWorkflow(BaseWorkflow):
    """Génération de Modèles 3D Voxel (.GLB) avec Vertex Colors pour Godot 4."""

    name = "voxel3d"
    description = "Modèles 3D Voxel maillés (.GLB) optimisés (Crossy Road, Minecraft, GridMap Godot 4)"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not verifier_blender():
            raise RuntimeError("Blender 4.x / 5.x est requis pour exécuter le workflow voxel3d.")

        concept = params.get("prompt")
        input_image = params.get("input")

        if not concept and not input_image:
            raise ValueError("Le workflow voxel3d nécessite un 'prompt' ou une image '-i / --input'.")

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        grid_size = int(params.get("grid_size", 32))
        voxel_depth = int(params.get("voxel_depth", 4))
        voxel_scale = float(params.get("voxel_scale", 0.05))

        os.makedirs(output_dir, exist_ok=True)

        if input_image and os.path.exists(input_image):
            self.log(f"Chargement du sprite source : {input_image}...")
            img_src = Image.open(input_image).convert("RGBA")
            nom_base = params.get("output") or f"{Path(input_image).stem}_voxel"
        else:
            self.log(f"Génération d'un asset pour Voxel 3D : '{concept}'...")
            nom_base = params.get("output") or f"{slugifier_texte(concept)}_voxel"

            style_voxel = (
                "pixel art game sprite, sharp crisp pixel art, clean silhouette, "
                "isolated on solid plain white background, vibrant colors, centered"
            )

            prompt_complet = construire_prompt_coherant(
                concept=concept,
                type_asset="item",
                llama_cli=self.config.get("llama_cli"),
                llm_model=self.config.get("llm_model"),
                style_anchor=style_voxel,
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
                seed=params.get("seed", -1),
                loras=params.get("loras")
            )
            img_src = post_process_asset(img_brute, redimensionner=grid_size * 4)

        # 1. Voxelisation
        self.log(f"Discrétisation en volume voxel ({grid_size}x{grid_size}x{voxel_depth})...")
        occupancy, colors = image_vers_grille_voxels(
            img_src,
            grid_size=grid_size,
            epaisseur_max=voxel_depth,
            mode_relief=True
        )

        nb_voxels = np.sum(occupancy)
        self.log(f"Volume généré : {nb_voxels} voxels actifs.")

        # 2. Culling des faces & Export Blender GLB
        self.log("Optimisation géométrique et export GLB via Blender Headless...")
        chemin_glb = exporter_voxel_glb(
            nom_base=nom_base,
            output_dir=output_dir,
            occupancy=occupancy,
            colors=colors,
            voxel_scale=voxel_scale
        )

        self.log(f"Modèle 3D Voxel exporté avec succès dans '{output_dir}/' :", emoji="🎉")
        self.log(f"  • Modèle 3D GLB : {chemin_glb}", emoji="💎")

        return {
            "glb": chemin_glb,
            "voxels_count": int(nb_voxels),
            "files": [chemin_glb]
        }
