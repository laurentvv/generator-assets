#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Anim Loop workflow: texture loops & animated shaders (AnimateDiff / LTX Loop Engine) for Godot 4.
Produces:
- Cyclic animation spritesheet (Atlas)
- Godot 4 shader (.gdshader) with phase-shifted temporal double-sampling without judder
- ShaderMaterial resource (.tres)
- AnimatedTexture resource (.tres) for UI and CanvasItem
"""

import os
from typing import Any, Dict
from PIL import Image

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.loop_ops import (
    assembler_spritesheet_loop,
    creer_boucle_temporelle_circulaire,
    exporter_animated_texture_godot,
    exporter_shader_loop_godot,
    generer_sequence_vfx_boucle
)
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class AnimLoopWorkflow(BaseWorkflow):
    """Continuous texture loop and animated shader generation for Godot 4."""

    name = "anim_loop"
    description = "Smooth animated texture loops & shaders (AnimateDiff / LTX Loop) for Godot 4 (.gdshader / .tres)"

    emoji = "🔄"

    # CLI declaration (audit §2.2, migration from the flat table of cli/parser.py:
    # help/defaults taken as-is, unchanged surface). --mode-2d is shared
    # with flowmap and vfx_flipbook (same 2D family): it lives here, first
    # user in the registry. --frames/--fps/--columns stay in the flat
    # table (shared with video/rife_interp, cross-family).
    PARAMETRES = [
        dict(flags=("--mode-2d",), action="store_true",
             help="Generates a Godot 2D-oriented shader or setup instead of 3D."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        prompt = params.get("prompt") or "magical portal vortex"
        input_image = params.get("input")
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        nb_trames = int(params.get("frames", 16)) or 16
        fps = float(params.get("fps", 12.0))
        colonnes = int(params.get("columns", 4))
        mode_2d = bool(params.get("mode_2d", False))
        vfx_type = params.get("vfx_type") or params.get("flow_type") or "portal"

        nom_base = params.get("output") or f"{slugifier_texte(prompt)}_loop"
        os.makedirs(output_dir, exist_ok=True)

        self.log(f"Generating the looping temporal sequence ({nb_trames} frames, type '{vfx_type}')...")

        # 1. Animation sequence generation
        if input_image and os.path.exists(input_image):
            self.log(f"Using the source image for looping: {input_image}")
            img_src = Image.open(input_image).convert("RGBA")
            # Creating periodic variations
            trames_brutes = []
            for i in range(nb_trames):
                angle = (360.0 * i) / nb_trames
                t_rot = img_src.rotate(angle, resample=Image.Resampling.BICUBIC)
                trames_brutes.append(t_rot)
        else:
            trames_brutes = generer_sequence_vfx_boucle(resolution=512, nb_trames=nb_trames, type_effet=vfx_type)

        # 2. Harmonic 360° looping (phase blending)
        self.log("Applying the harmonic circular cross-fade (Seamless Time Loop)...")
        trames_bouclees = creer_boucle_temporelle_circulaire(trames_brutes)

        # 3. Spritesheet assembly
        spritesheet = assembler_spritesheet_loop(trames_bouclees, colonnes=colonnes)
        chemin_sheet = os.path.join(output_dir, f"{nom_base}_spritesheet.png")
        spritesheet.save(chemin_sheet, "PNG")

        # 4. Godot 4 shader and AnimatedTexture export
        self.log("Generating the Godot 4 shaders and resources...")
        chemin_shader, chemin_mat = exporter_shader_loop_godot(nom_base, output_dir, mode_2d=mode_2d)
        chemin_anim = exporter_animated_texture_godot(nom_base, output_dir, nb_trames=nb_trames, fps=fps)

        self.log(f"Animated loop exported successfully to '{output_dir}/':", emoji="🎉")
        self.log(f"  • Spritesheet Loop : {chemin_sheet}")
        self.log(f"  • Godot 4 shader   : {chemin_shader}")
        self.log(f"  • ShaderMaterial   : {chemin_mat}")
        self.log(f"  • AnimatedTexture  : {chemin_anim}", emoji="💎")

        return {
            "spritesheet": chemin_sheet,
            "shader": chemin_shader,
            "material": chemin_mat,
            "animated_texture": chemin_anim,
            "frames_count": nb_trames,
            "files": [chemin_sheet, chemin_shader, chemin_mat, chemin_anim]
        }
