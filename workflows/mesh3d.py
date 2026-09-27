#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mesh 3D Workflow: generation of complete 3D models (.glb) for Godot Engine via Blender headless.
Takes a prompt or an image, generates the PBR texture pack, and exports the ready-to-use .glb 3D model.
"""

import os
from pathlib import Path
from typing import Any, Dict

from core.blender_ops import exporter_mesh_pbr_glb, verifier_blender
from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class Mesh3DWorkflow(BaseWorkflow):
    name = "mesh3d"
    description = "Complete meshed 3D model (.glb) generation with PBR textures for Godot (Blender Headless)"

    emoji = "🎲"
    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        concept = params.get("prompt")
        input_image = params.get("input")
        shape = params.get("shape", "tile").lower()
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)

        if not concept and not input_image:
            raise ValueError("The 'prompt' or 'input' parameter is required for the mesh3d workflow.")

        if not verifier_blender():
            raise EnvironmentError("Blender is not detected in the system PATH. Please install Blender or add it to the PATH.")

        os.makedirs(output_dir, exist_ok=True)
        nom_base = params.get("output") or (slugifier_texte(concept) if concept else Path(input_image).stem)

        # 1. Generation or retrieval of the PBR textures
        self.log(f"Preparing the PBR textures for the 3D model ({shape.upper()})...")
        wf_pbr = WorkflowRegistry.get("material3d")(self.config)
        pbr_res = wf_pbr.run(params)

        albedo_path = pbr_res.get("albedo")
        normal_path = pbr_res.get("normal")
        orm_path = pbr_res.get("orm")
        height_path = pbr_res.get("height")

        # 2. Build and GLB export via Blender headless
        self.log(f"Building the 3D mesh ({shape}) and exporting the .glb via Blender...", emoji="🔨")
        fichier_glb = exporter_mesh_pbr_glb(
            nom_base=nom_base,
            output_dir=output_dir,
            shape=shape,
            albedo_path=albedo_path,
            normal_path=normal_path,
            orm_path=orm_path,
            height_path=height_path
        )

        self.log(f"Godot 3D model ready: {fichier_glb}", emoji="🎮")

        return {
            "glb_path": fichier_glb,
            "pbr_textures": pbr_res,
            "shape": shape
        }
