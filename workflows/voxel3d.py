#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Voxel 3D workflow: turning 2D sprites or concepts into Voxel 3D models (.GLB) for Godot 4 & GridMap.
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
    """Voxel 3D model (.GLB) generation with vertex colors for Godot 4."""

    name = "voxel3d"
    description = "Optimized meshed Voxel 3D models (.GLB) (Crossy Road, Minecraft, Godot 4 GridMap)"

    emoji = "🧊"

    # CLI declarations (audit §2.2, migration from the flat table of cli/parser.py:
    # help/defaults taken as-is, unchanged surface). --grid-size (shared
    # with pixelart) lives in pixelart.
    PARAMETRES = [
        dict(flags=("--voxel-depth",), type=int, default=4,
             help="Thickness in voxels for the 3D extrusion (voxel3d workflow)."),
        dict(flags=("--voxel-scale",), type=float, default=0.05,
             help="Size of one voxel in Godot units (voxel3d workflow)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if not verifier_blender():
            raise RuntimeError("Blender 4.x / 5.x is required to run the voxel3d workflow.")

        concept = params.get("prompt")
        input_image = params.get("input")

        if not concept and not input_image:
            raise ValueError("The voxel3d workflow requires a 'prompt' or an image '-i / --input'.")

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        grid_size = int(params.get("grid_size", 32))
        voxel_depth = int(params.get("voxel_depth", 4))
        voxel_scale = float(params.get("voxel_scale", 0.05))

        os.makedirs(output_dir, exist_ok=True)

        if input_image and os.path.exists(input_image):
            self.log(f"Loading the source sprite: {input_image}...")
            img_src = Image.open(input_image).convert("RGBA")
            nom_base = params.get("output") or f"{Path(input_image).stem}_voxel"
        else:
            self.log(f"Generating a Voxel 3D asset: '{concept}'...")
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

        # 1. Voxelization
        self.log(f"Discretizing into a voxel volume ({grid_size}x{grid_size}x{voxel_depth})...")
        occupancy, colors = image_vers_grille_voxels(
            img_src,
            grid_size=grid_size,
            epaisseur_max=voxel_depth,
            mode_relief=True
        )

        nb_voxels = np.sum(occupancy)
        self.log(f"Volume generated: {nb_voxels} active voxels.")

        # 2. Face culling & Blender GLB export
        self.log("Geometric optimization and GLB export via Blender Headless...")
        chemin_glb = exporter_voxel_glb(
            nom_base=nom_base,
            output_dir=output_dir,
            occupancy=occupancy,
            colors=colors,
            voxel_scale=voxel_scale
        )

        self.log(f"Voxel 3D model exported successfully to '{output_dir}/':", emoji="🎉")
        self.log(f"  • GLB 3D model: {chemin_glb}", emoji="💎")

        return {
            "glb": chemin_glb,
            "voxels_count": int(nb_voxels),
            "files": [chemin_glb]
        }
