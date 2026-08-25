#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Mesh 3D : Génération de modèles 3D (.glb) complets pour Godot Engine via Blender headless.
Prend un prompt ou une image, génère le pack de textures PBR, et exporte le modèle 3D .glb prêt à l'emploi.
"""

import os
from pathlib import Path
from typing import Any, Dict
from PIL import Image

from core.blender_ops import exporter_mesh_pbr_glb, verifier_blender
from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class Mesh3DWorkflow(BaseWorkflow):
    name = "mesh3d"
    description = "Génération de modèle 3D maillé (.glb) complet avec textures PBR pour Godot (Blender Headless)"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        concept = params.get("prompt")
        input_image = params.get("input")
        shape = params.get("shape", "tile").lower()
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)

        if not concept and not input_image:
            raise ValueError("Le paramètre 'prompt' ou 'input' est requis pour le workflow mesh3d.")

        if not verifier_blender():
            raise EnvironmentError("Blender n'est pas détecté dans le PATH système. Veuillez installer Blender ou l'ajouter au PATH.")

        os.makedirs(output_dir, exist_ok=True)
        nom_base = params.get("output") or (slugifier_texte(concept) if concept else Path(input_image).stem)

        # 1. Génération ou récupération des textures PBR
        self.log(f"Préparation des textures PBR pour le modèle 3D ({shape.upper()})...")
        wf_pbr = WorkflowRegistry.get("material3d")(self.config)
        pbr_res = wf_pbr.run(params)

        albedo_path = pbr_res.get("albedo")
        normal_path = pbr_res.get("normal")
        orm_path = pbr_res.get("orm")
        height_path = pbr_res.get("height")

        # 2. Construction et Export GLB via Blender headless
        self.log(f"Construction du maillage 3D ({shape}) et export .glb via Blender...", emoji="🔨")
        fichier_glb = exporter_mesh_pbr_glb(
            nom_base=nom_base,
            output_dir=output_dir,
            shape=shape,
            albedo_path=albedo_path,
            normal_path=normal_path,
            orm_path=orm_path,
            height_path=height_path
        )

        self.log(f"Modèle 3D Godot prêt : {fichier_glb}", emoji="🎮")

        return {
            "glb_path": fichier_glb,
            "pbr_textures": pbr_res,
            "shape": shape
        }
