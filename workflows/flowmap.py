#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flowmap workflow: generating vector Flowmaps and animated Shaders (Water, Lava, Tornado) for Godot 4.
"""

import os
from typing import Any, Dict

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.shader_maps import exporter_shader_flow_godot, generer_flowmap
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class FlowmapWorkflow(BaseWorkflow):
    """Vector Flowmap and Godot 4 Shader generation."""

    name = "flowmap"
    description = "Vector flow maps (Flowmaps) and animated water/lava Shaders for Godot 4"

    emoji = "🌊"

    # CLI declarations (audit §2.2, migration from the flat table of cli/parser.py:
    # help/defaults taken as-is, unchanged surface). --flow-type is also read
    # as a fallback by anim_loop and audio_ambience; --mode-2d (shared) lives in
    # anim_loop.
    PARAMETRES = [
        dict(flags=("--angle",), type=float, default=90.0,
             help="Direction angle in degrees for the flowmap workflow (default: 90 = down)."),
        dict(flags=("--flow-type",), default="river", choices=["river", "vortex", "radial", "optical"],
             help="Flow type for the flowmap workflow."),
        dict(flags=("--turbulence",), type=float, default=0.35,
             help="Swirl/meander intensity for flowmap (default: 0.35)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        prompt = params.get("prompt") or "river"
        type_flux = params.get("flow_type") or ("vortex" if "vortex" in prompt or "whirlpool" in prompt else "river")
        if "radial" in prompt or "explosion" in prompt:
            type_flux = "radial"

        nom_base = params.get("output") or f"{slugifier_texte(prompt)}_flow"
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        resolution = params.get("size", 1024) or 1024
        angle = float(params.get("angle", 90.0))  # 90° = flow toward the bottom by default
        turbulence = float(params.get("turbulence", 0.35))
        mode_2d = params.get("mode_2d", False)

        os.makedirs(output_dir, exist_ok=True)
        chemin_flowmap = os.path.join(output_dir, f"{nom_base}_flowmap.png")

        self.log(f"Generating the '{type_flux}' Flowmap ({resolution}x{resolution}, angle={angle}°, turb={turbulence})...")
        img_flow = generer_flowmap(
            type_flux=type_flux,
            resolution=resolution,
            angle_deg=angle,
            turbulence=turbulence
        )
        img_flow.save(chemin_flowmap, "PNG")

        # Generation of the associated Godot 4 Shader (.gdshader + .tres)
        self.log("Generating the Godot 4 shader script and the ShaderMaterial resource...")
        chemin_shader, chemin_tres = exporter_shader_flow_godot(nom_base, output_dir, mode_2d=mode_2d)

        self.log(f"Flowmap pack ready for Godot 4 in '{output_dir}/':", emoji="🎉")
        self.log(f"  • Flowmap texture: {chemin_flowmap}")
        self.log(f"  • Shader code     : {chemin_shader} (.gdshader)")
        self.log(f"  • Resource        : {chemin_tres} (ShaderMaterial)", emoji="💎")

        return {
            "flowmap": chemin_flowmap,
            "shader": chemin_shader,
            "material_tres": chemin_tres,
            "files": [chemin_flowmap, chemin_shader, chemin_tres]
        }
