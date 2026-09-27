#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VFX Flipbook workflow: generating particle sheets and animated visual effects (Flipbooks) for Godot 4.
Produces:
- Flipbook texture (4x4 or 8x8 atlas)
- Godot 4 StandardMaterial3D / CanvasItemMaterial resource configured with UV Flipbook
- ParticleProcessMaterial resource (.tres)
- Sample GPUParticles scene (.tscn)
"""

import os
from typing import Any, Dict, Tuple
from PIL import Image

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.diffusion import generer_image_vulkan
from core.llm import construire_prompt_coherant
from workflows.base import BaseWorkflow, WorkflowRegistry


def exporter_materiau_flipbook_godot(
    nom_base: str,
    output_dir: str,
    h_frames: int = 4,
    v_frames: int = 4,
    mode_2d: bool = False
) -> Tuple[str, str, str]:
    """Generates the Flipbook material, the ParticleProcessMaterial and the GPUParticles scene for Godot 4."""
    chemin_mat = os.path.join(output_dir, f"{nom_base}_vfx_material.tres")
    chemin_part = os.path.join(output_dir, f"{nom_base}_particles_process.tres")
    chemin_tscn = os.path.join(output_dir, f"{nom_base}_vfx.tscn")

    if mode_2d:
        code_mat = f"""[gd_resource type="CanvasItemMaterial" format=3]

[resource]
blend_mode = 1
particles_animation = true
particles_anim_h_frames = {h_frames}
particles_anim_v_frames = {v_frames}
particles_anim_loop = false
"""
    else:
        code_mat = f"""[gd_resource type="StandardMaterial3D" load_steps=2 format=3]

[ext_resource type="Texture2D" path="res://{nom_base}_flipbook.png" id="1_tex"]

[resource]
transparency = 1
blend_mode = 1
shading_mode = 0
albedo_texture = ExtResource("1_tex")
billboard_mode = 3
billboard_keep_scale = true
particles_anim_h_frames = {h_frames}
particles_anim_v_frames = {v_frames}
particles_anim_loop = false
"""

    with open(chemin_mat, "w", encoding="utf-8") as f:
        f.write(code_mat)

    code_part = """[gd_resource type="ParticleProcessMaterial" format=3]

[resource]
gravity = Vector3(0, 0, 0)
scale_min = 0.8
scale_max = 1.2
anim_speed_min = 1.0
anim_speed_max = 1.0
"""
    with open(chemin_part, "w", encoding="utf-8") as f:
        f.write(code_part)

    if mode_2d:
        code_tscn = f"""[gd_scene load_steps=4 format=3]

[ext_resource type="Material" path="res://{os.path.basename(chemin_mat)}" id="1_mat"]
[ext_resource type="Material" path="res://{os.path.basename(chemin_part)}" id="2_proc"]
[ext_resource type="Texture2D" path="res://{nom_base}_flipbook.png" id="3_tex"]

[node name="VFX_{nom_base.capitalize()}" type="GPUParticles2D"]
material = ExtResource("1_mat")
emitting = true
amount = 1
process_material = ExtResource("2_proc")
texture = ExtResource("3_tex")
lifetime = 1.0
one_shot = false
"""
    else:
        code_tscn = f"""[gd_scene load_steps=3 format=3]

[ext_resource type="Material" path="res://{os.path.basename(chemin_mat)}" id="1_mat"]
[ext_resource type="Material" path="res://{os.path.basename(chemin_part)}" id="2_proc"]

[node name="VFX_{nom_base.capitalize()}" type="GPUParticles3D"]
material_override = ExtResource("1_mat")
emitting = true
amount = 1
process_material = ExtResource("2_proc")
lifetime = 1.0
one_shot = false
"""

    with open(chemin_tscn, "w", encoding="utf-8") as f:
        f.write(code_tscn)

    return chemin_mat, chemin_part, chemin_tscn


@WorkflowRegistry.register
class VFXFlipbookWorkflow(BaseWorkflow):
    """Particle sheet and visual effect (Flipbook) generation for Godot 4."""

    name = "vfx_flipbook"
    description = "Visual effect / particle animation sheets (4x4 Flipbooks) and Godot 4 materials"

    emoji = "💥"

    # CLI declaration (audit §2.2, migration from the flat table of cli/parser.py:
    # help/defaults taken as-is, unchanged surface). --vfx-type is also read
    # as a fallback by anim_loop and audio_ambience; --mode-2d (shared) lives in
    # anim_loop; --frames stays in the flat table (cross-family).
    PARAMETRES = [
        dict(flags=("--vfx-type",), default="explosion", choices=["explosion", "fire", "lightning", "portal", "slash", "aura"],
             help="Effect type for vfx_flipbook."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        concept = params.get("prompt") or "explosion magique violette"
        input_image = params.get("input")
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        vfx_type = params.get("vfx_type", "explosion")
        resolution = params.get("size", 2048) or 2048
        mode_2d = params.get("mode_2d", False)
        nom_base = params.get("output") or f"{slugifier_texte(concept)}_vfx"

        os.makedirs(output_dir, exist_ok=True)
        chemin_flipbook = os.path.join(output_dir, f"{nom_base}_flipbook.png")

        h_frames = 4
        v_frames = 4
        total_frames = h_frames * v_frames

        if input_image and os.path.exists(input_image):
            self.log(f"Loading the source image: {input_image}...")
            img_src = Image.open(input_image).convert("RGBA")
        else:
            self.log(f"Generating the 4x4 VFX Flipbook sheet ({total_frames} frames) for '{concept}'...")

            style_vfx = (
                f"game visual effect sprite sheet, 4x4 animated grid sprite sequence of {vfx_type}, "
                "isolated on solid pure black background, progression from start to finish, magical energy glow, cinematic particles"
            )

            prompt_complet = construire_prompt_coherant(
                concept=f"4x4 sprite sheet grid of {concept}, chronological animation sequence",
                type_asset="prop",
                llama_cli=self.config.get("llama_cli"),
                llm_model=self.config.get("llm_model"),
                style_anchor=style_vfx,
                custom_cadrage="4x4 grid sprite sheet sequence",
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
            img_src = img_brute.convert("RGBA")

        # Resizing to the target resolution
        if img_src.size != (resolution, resolution):
            img_src = img_src.resize((resolution, resolution), Image.Resampling.LANCZOS)

        img_src.save(chemin_flipbook, "PNG")

        # Godot 4 resource export
        self.log("Generating the Godot 4 resources (Material, ParticleProcessMaterial, GPUParticles)...")
        chemin_mat, chemin_part, chemin_tscn = exporter_materiau_flipbook_godot(
            nom_base=nom_base,
            output_dir=output_dir,
            h_frames=h_frames,
            v_frames=v_frames,
            mode_2d=mode_2d
        )

        self.log(f"VFX Flipbook pack ready for Godot 4 in '{output_dir}/':", emoji="🎉")
        self.log(f"  • Flipbook texture : {chemin_flipbook} ({h_frames}x{v_frames} frames)")
        self.log(f"  • Godot 4 material : {chemin_mat} (Particles Anim)", emoji="💎")
        self.log(f"  • Particle emitter : {chemin_part}")
        self.log(f"  • GPUParticles scene: {chemin_tscn}")

        return {
            "flipbook": chemin_flipbook,
            "material": chemin_mat,
            "particle_process": chemin_part,
            "scene": chemin_tscn,
            "grid": (h_frames, v_frames),
            "files": [chemin_flipbook, chemin_mat, chemin_part, chemin_tscn]
        }
