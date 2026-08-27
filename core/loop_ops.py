#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module de génération de boucles d'animation temporelles parfaites (Loop Engine) et Shaders Godot 4.
Gère :
- Le bouclage temporel cyclique (Cross-Dissolve sinusoïdal / Morphing de phase)
- La génération d'effets visuels procéduraux en boucle fermée (Portail, Feu, Cascade, Nébuleuse)
- L'assemblage d'atlas d'animation (Spritesheets)
- L'exportation de Shaders Godot 4 (.gdshader) avec double échantillonnage déphasé et AnimatedTexture (.tres)
"""

import math
import os
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from PIL import Image


def creer_boucle_temporelle_circulaire(trames: List[Image.Image]) -> List[Image.Image]:
    """
    Rend une séquence temporelle parfaitement bouclable à 360° sans à-coup entre la fin et le début
    en appliquant un fondu croisé temporel harmonique (phase blending).
    """
    n = len(trames)
    if n <= 1:
        return trames

    trames_rgba = [t.convert("RGBA") for t in trames]
    largeur, hauteur = trames_rgba[0].size
    trames_bouclees = []

    for i in range(n):
        # Angle de phase [0, 2*pi]
        theta = (2.0 * math.pi * i) / n
        # Poids harmonique de bouclage
        w1 = (1.0 + math.cos(theta)) / 2.0
        w2 = 1.0 - w1

        # Mélange entre la trame courante et la trame déphasée de n/2
        idx_oppose = (i + n // 2) % n
        arr1 = np.array(trames_rgba[i]).astype(np.float32)
        arr2 = np.array(trames_rgba[idx_oppose]).astype(np.float32)

        arr_mix = (arr1 * w1 + arr2 * w2).clip(0, 255).astype(np.uint8)
        trames_bouclees.append(Image.fromarray(arr_mix, "RGBA"))

    return trames_bouclees


def generer_sequence_vfx_boucle(
    resolution: int = 512,
    nb_trames: int = 16,
    type_effet: str = "portal"
) -> List[Image.Image]:
    """
    Génère une séquence procédurale d'effets visuels animés en boucle mathématique parfaite.
    """
    h, w = resolution, resolution
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w / 2.0, h / 2.0
    dx = (x - cx) / (w / 2.0)
    dy = (y - cy) / (h / 2.0)
    dist = np.sqrt(dx**2 + dy**2)
    angle = np.arctan2(dy, dx)

    trames = []
    type_effet = type_effet.lower()

    for k in range(nb_trames):
        t_norm = k / float(nb_trames)  # [0, 1[
        phase = 2.0 * np.pi * t_norm

        if any(e in type_effet for e in ["portal", "vortex", "swirl"]):
            # Spirale rotative infinie
            spiral = np.sin(5.0 * angle - phase * 2.0 + 8.0 * np.log(dist + 0.1))
            ring = np.exp(-((dist - 0.6)**2) / 0.08)
            intensity = (0.5 + 0.5 * spiral) * ring
            # Couleurs violet mystique / cyan
            r = (intensity * 180 + 30 * np.sin(phase)).clip(0, 255)
            g = (intensity * 80 + 20).clip(0, 255)
            b = (intensity * 255).clip(0, 255)
            alpha = (intensity * 255 * np.clip(1.2 - dist, 0, 1)).clip(0, 255)

        elif any(e in type_effet for e in ["fire", "flame", "torch"]):
            # Ondulations ascendantes périodiques
            wave1 = np.sin(4.0 * dx + phase) * 0.15
            wave2 = np.cos(6.0 * dy - phase * 2.0) * 0.1
            dist_flame = np.sqrt(dx**2 + (dy - 0.2 + wave1 + wave2)**2)
            intensity = np.exp(-(dist_flame**2) / 0.18) * np.clip(1.0 - (dy + 0.5), 0, 1)
            # Couleurs feu (jaune -> orange -> rouge)
            r = (intensity * 255).clip(0, 255)
            g = (intensity**1.8 * 200).clip(0, 255)
            b = (intensity**3.0 * 50).clip(0, 255)
            alpha = (intensity * 255).clip(0, 255)

        elif any(e in type_effet for e in ["waterfall", "water", "cascade"]):
            # Flux descendant périodique
            wave_v = np.sin(8.0 * dy + phase * 2.0 + 4.0 * np.sin(3.0 * dx))
            foam = 0.5 + 0.5 * wave_v
            r = (foam * 70 + 40).clip(0, 255)
            g = (foam * 140 + 100).clip(0, 255)
            b = (foam * 200 + 55).clip(0, 255)
            alpha = (np.clip(1.0 - np.abs(dx)*1.2, 0, 1) * 230).clip(0, 255)

        else:  # Nebula / Magic Orb
            pulse = 0.5 + 0.5 * np.sin(phase)
            orb = np.exp(-(dist**2) / (0.15 + 0.05 * pulse))
            rings = 0.5 + 0.5 * np.sin(10.0 * dist - phase * 2.0)
            val = orb * rings
            r = (val * 160 + 50).clip(0, 255)
            g = (val * 230).clip(0, 255)
            b = (val * 255).clip(0, 255)
            alpha = (orb * 255).clip(0, 255)

        rgba = np.stack([r, g, b, alpha], axis=-1).astype(np.uint8)
        trames.append(Image.fromarray(rgba, "RGBA"))

    return trames


def assembler_spritesheet_loop(trames: List[Image.Image], colonnes: int = 4) -> Image.Image:
    """Assemble une série de trames en une grille d'atlas (Spritesheet)."""
    if not trames:
        return Image.new("RGBA", (1, 1))

    tw, th = trames[0].size
    nb = len(trames)
    lignes = (nb + colonnes - 1) // colonnes

    atlas = Image.new("RGBA", (tw * colonnes, th * lignes), (0, 0, 0, 0))
    for idx, trame in enumerate(trames):
        c = idx % colonnes
        l = idx // colonnes
        atlas.paste(trame, (c * tw, l * th))

    return atlas


def exporter_shader_loop_godot(
    nom_base: str,
    output_dir: str,
    mode_2d: bool = False
) -> Tuple[str, str]:
    """
    Génère un Shader Godot 4 (.gdshader) avec double-échantillonnage temporel déphasé
    et son ShaderMaterial (.tres) pour des boucles de textures fluides infinies.
    """
    os.makedirs(output_dir, exist_ok=True)
    chemin_shader = os.path.join(output_dir, f"{nom_base}_loop.gdshader")
    chemin_mat = os.path.join(output_dir, f"{nom_base}_loop_material.tres")

    shader_type = "canvas_item" if mode_2d else "spatial"
    unshaded = "unshaded," if not mode_2d else ""

    code_shader = f"""shader_type {shader_type};
render_mode blend_mix, {unshaded} cull_disabled;

uniform sampler2D albedo_texture : source_color, repeat_enable, filter_linear_mipmap;
uniform vec2 scroll_speed = vec2(0.0, 0.25);
uniform float loop_frequency = 1.0;
uniform vec4 tint_color : source_color = vec4(1.0, 1.0, 1.0, 1.0);

void fragment() {{
	float t1 = fract(TIME * loop_frequency);
	float t2 = fract(TIME * loop_frequency + 0.5);

	vec2 uv1 = UV + scroll_speed * t1;
	vec2 uv2 = UV + scroll_speed * t2;

	vec4 tex1 = texture(albedo_texture, uv1);
	vec4 tex2 = texture(albedo_texture, uv2);

	// Fondu croisé triangulaire entre les 2 échantillons déphasés
	float weight = abs((t1 - 0.5) * 2.0);
	vec4 final_color = mix(tex2, tex1, weight) * tint_color;

	{"COLOR = final_color;" if mode_2d else "ALBEDO = final_color.rgb; ALPHA = final_color.a;"}
}}
"""
    with open(chemin_shader, "w", encoding="utf-8") as f:
        f.write(code_shader)

    code_mat = f"""[gd_resource type="ShaderMaterial" load_steps=2 format=3]

[ext_resource type="Shader" path="res://{nom_base}_loop.gdshader" id="1_shader"]

[resource]
render_priority = 0
shader = ExtResource("1_shader")
shader_parameter/scroll_speed = Vector2(0, 0.25)
shader_parameter/loop_frequency = 1.0
shader_parameter/tint_color = Color(1, 1, 1, 1)
"""
    with open(chemin_mat, "w", encoding="utf-8") as f:
        f.write(code_mat)

    return chemin_shader, chemin_mat


def exporter_animated_texture_godot(
    nom_base: str,
    output_dir: str,
    nb_trames: int = 16,
    fps: float = 12.0
) -> str:
    """Génère la ressource AnimatedTexture Godot 4 configurée."""
    os.makedirs(output_dir, exist_ok=True)
    chemin_anim = os.path.join(output_dir, f"{nom_base}_animated_tex.tres")

    code_anim = f"""[gd_resource type="AnimatedTexture" format=3]

[resource]
frames = {nb_trames}
fps = {fps:.1f}
"""
    with open(chemin_anim, "w", encoding="utf-8") as f:
        f.write(code_anim)

    return chemin_anim
