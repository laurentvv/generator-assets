#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Flowmap : Génération de Flowmaps vectorielles et Shaders animés (Eau, Lave, Tornade) pour Godot 4.
"""

import os
from pathlib import Path
from typing import Any, Dict
from PIL import Image

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.shader_maps import exporter_shader_flow_godot, generer_flowmap
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class FlowmapWorkflow(BaseWorkflow):
    """Génération de Flowmaps vectorielles et Shaders Godot 4."""

    name = "flowmap"
    description = "Cartes de flux vectoriels (Flowmaps) et Shaders d'eau/lave animés pour Godot 4"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        prompt = params.get("prompt") or "river"
        type_flux = params.get("flow_type") or ("vortex" if "vortex" in prompt or "whirlpool" in prompt else "river")
        if "radial" in prompt or "explosion" in prompt:
            type_flux = "radial"

        nom_base = params.get("output") or f"{slugifier_texte(prompt)}_flow"
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        resolution = params.get("size", 1024) or 1024
        angle = float(params.get("angle", 90.0))  # 90° = flux vers le bas par défaut
        turbulence = float(params.get("turbulence", 0.35))
        mode_2d = params.get("mode_2d", False)

        os.makedirs(output_dir, exist_ok=True)
        chemin_flowmap = os.path.join(output_dir, f"{nom_base}_flowmap.png")

        self.log(f"Génération de la Flowmap '{type_flux}' ({resolution}x{resolution}, angle={angle}°, turb={turbulence})...")
        img_flow = generer_flowmap(
            type_flux=type_flux,
            resolution=resolution,
            angle_deg=angle,
            turbulence=turbulence
        )
        img_flow.save(chemin_flowmap, "PNG")

        # Génération du Shader Godot 4 associé (.gdshader + .tres)
        self.log("Génération du script shader Godot 4 et de la ressource ShaderMaterial...")
        chemin_shader, chemin_tres = exporter_shader_flow_godot(nom_base, output_dir, mode_2d=mode_2d)

        self.log(f"Pack Flowmap prêt pour Godot 4 dans '{output_dir}/' :", emoji="🎉")
        self.log(f"  • Texture Flowmap : {chemin_flowmap}")
        self.log(f"  • Code Shader     : {chemin_shader} (.gdshader)")
        self.log(f"  • Ressource       : {chemin_tres} (ShaderMaterial)", emoji="💎")

        return {
            "flowmap": chemin_flowmap,
            "shader": chemin_shader,
            "material_tres": chemin_tres,
            "files": [chemin_flowmap, chemin_shader, chemin_tres]
        }
