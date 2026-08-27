#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module de génération de cartes de shaders techniques pour Godot 4 (Flow Maps, Dissolve Noise, Shaders GLSL).
"""

import math
import os
from typing import Dict, Optional, Tuple
import numpy as np
from PIL import Image


def _generer_perlin_noise_2d(shape: Tuple[int, int], res: Tuple[int, int] = (8, 8)) -> np.ndarray:
    """Génère un bruit pseudo-Perlin 2D fluide avec interpolation cosinus."""
    ny, nx = shape
    ry, rx = res
    grid_y = np.linspace(0, ry, ny, endpoint=False)
    grid_x = np.linspace(0, rx, nx, endpoint=False)

    np.random.seed(42)
    # Gradients aléatoires
    angles = 2 * np.pi * np.random.rand(ry + 1, rx + 1)
    gradients = np.stack((np.cos(angles), np.sin(angles)), axis=-1)

    # Coordonnées de cellule
    x0 = grid_x.astype(int)
    x1 = x0 + 1
    y0 = grid_y.astype(int)
    y1 = y0 + 1

    fx = grid_x - x0
    fy = grid_y - y0

    # Fonction de lissage (smoothstep)
    sx = fx * fx * (3 - 2 * fx)
    sy = fy * fy * (3 - 2 * fy)

    # Produits scalaires aux 4 coins
    g00 = gradients[y0[:, None], x0[None, :]]
    g10 = gradients[y0[:, None], x1[None, :]]
    g01 = gradients[y1[:, None], x0[None, :]]
    g11 = gradients[y1[:, None], x1[None, :]]

    v00 = fx[None, :] * g00[:, :, 0] + fy[:, None] * g00[:, :, 1]
    v10 = (fx[None, :] - 1) * g10[:, :, 0] + fy[:, None] * g10[:, :, 1]
    v01 = fx[None, :] * g01[:, :, 0] + (fy[:, None] - 1) * g01[:, :, 1]
    v11 = (fx[None, :] - 1) * g11[:, :, 0] + (fy[:, None] - 1) * g11[:, :, 1]

    # Interpolation
    top = v00 * (1 - sx[None, :]) + v10 * sx[None, :]
    bottom = v01 * (1 - sx[None, :]) + v11 * sx[None, :]
    noise = top * (1 - sy[:, None]) + bottom * sy[:, None]

    # Normalisation [0, 1]
    noise = (noise - noise.min()) / (noise.max() - noise.min() + 1e-6)
    return noise.astype(np.float32)


def generer_flowmap(
    type_flux: str = "river",
    resolution: int = 1024,
    angle_deg: float = 0.0,
    turbulence: float = 0.3,
    image_a: Optional[Image.Image] = None,
    image_b: Optional[Image.Image] = None
) -> Image.Image:
    """
    Génère une Flow Map (R=Vecteur X, G=Vecteur Y, B=Magnitude, A=255).
    128 = Vecteur 0, 0 = -1.0, 255 = +1.0.
    
    Types disponibles :
    - 'river' : Flux directionnel continu (avec méandres et bruit de turbulence)
    - 'vortex' : Tourbillon / spirale avec aspiration vers le centre
    - 'radial' : Expansion radiale vers l'extérieur (onde de choc / explosion)
    - 'optical' : Calcul du flux optique entre image_a et image_b via OpenCV
    """
    h, w = resolution, resolution

    if type_flux == "optical" and image_a and image_b:
        import cv2
        img1 = np.array(image_a.convert("L").resize((w, h)))
        img2 = np.array(image_b.convert("L").resize((w, h)))
        flow = cv2.calcOpticalFlowFarneback(img1, img2, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        vx = flow[..., 0]
        vy = flow[..., 1]
        # Normalisation
        max_mag = np.max(np.sqrt(vx**2 + vy**2)) + 1e-6
        vx /= max_mag
        vy /= max_mag
    else:
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        cx, cy = w / 2.0, h / 2.0
        dx = (x - cx) / cx
        dy = (y - cy) / cy
        dist = np.sqrt(dx**2 + dy**2) + 1e-5

        if type_flux in ("vortex", "whirlpool", "swirl"):
            # Vitesse tangentielle (tourbillon) + légère attraction vers le centre
            tangent_x = -dy / dist
            tangent_y = dx / dist
            inward_x = -dx
            inward_y = -dy
            vx = tangent_x * 0.85 + inward_x * 0.15
            vy = tangent_y * 0.85 + inward_y * 0.15
            # Atténuation vers les bords
            vx *= np.clip(1.2 - dist, 0.0, 1.0)
            vy *= np.clip(1.2 - dist, 0.0, 1.0)

        elif type_flux in ("radial", "explosion", "shockwave"):
            # Expansion du centre vers l'extérieur
            vx = dx / dist
            vy = dy / dist

        else:  # "river", "linear", default
            # Direction linéaire selon l'angle spécifié
            rad = math.radians(angle_deg)
            base_vx = math.cos(rad)
            base_vy = math.sin(rad)
            vx = np.full((h, w), base_vx, dtype=np.float32)
            vy = np.full((h, w), base_vy, dtype=np.float32)

            # Ajout de turbulences / méandres par Curl Noise
            if turbulence > 0:
                noise_a = _generer_perlin_noise_2d((h, w), (6, 6))
                noise_b = _generer_perlin_noise_2d((h, w), (12, 12))
                combined_noise = noise_a * 0.7 + noise_b * 0.3
                
                # Gradient orthogonal pour conserver l'incompressibilité
                grad_y, grad_x = np.gradient(combined_noise)
                curl_x = -grad_y * 10.0 * turbulence
                curl_y = grad_x * 10.0 * turbulence
                
                vx += curl_x
                vy += curl_y

    # Calcul de la magnitude
    magnitude = np.sqrt(vx**2 + vy**2)
    max_m = np.maximum(magnitude.max(), 1.0)
    vx_norm = vx / max_m
    vy_norm = vy / max_m
    mag_norm = (magnitude / max_m).clip(0.0, 1.0)

    # Conversion en RGBA 8-bit standard Flowmap (128 = 0)
    r = ((vx_norm * 0.5 + 0.5) * 255.0).clip(0, 255).astype(np.uint8)
    g = ((vy_norm * 0.5 + 0.5) * 255.0).clip(0, 255).astype(np.uint8)
    b = (mag_norm * 255.0).clip(0, 255).astype(np.uint8)
    a = np.full((h, w), 255, dtype=np.uint8)

    flow_arr = np.stack([r, g, b, a], axis=-1)
    return Image.fromarray(flow_arr, mode="RGBA")


def exporter_shader_flow_godot(nom_base: str, output_dir: str, mode_2d: bool = False) -> Tuple[str, str]:
    """
    Génère un fichier shader Godot 4 (.gdshader) avec double-sampling et déphasage fluide
    ainsi que sa ressource ShaderMaterial (.tres).
    """
    os.makedirs(output_dir, exist_ok=True)
    chemin_shader = os.path.join(output_dir, f"{nom_base}_water.gdshader")
    chemin_tres = os.path.join(output_dir, f"{nom_base}_material.tres")

    shader_type = "canvas_item" if mode_2d else "spatial"
    
    code_shader = f"""shader_type {shader_type};
// Shader de flux d'eau / lave animé avec Flowmap (Double sampling déphasé)
// Généré automatiquement par Generator Assets pour Godot 4

uniform sampler2D albedo_texture : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D flowmap_texture : hint_default_black, filter_linear_mipmap, repeat_enable;
uniform vec4 tint_color : source_color = vec4(0.2, 0.5, 0.9, 0.9);
uniform float flow_speed : hint_range(0.0, 2.0) = 0.4;
uniform float flow_strength : hint_range(0.0, 1.0) = 0.15;

void fragment() {{
    vec2 flow = texture(flowmap_texture, UV).rg * 2.0 - vec2(1.0);
    float time = TIME * flow_speed;

    // Deux échantillons déphasés de 0.5 cycle pour une boucle continue sans raccord visible
    float phase0 = fract(time);
    float phase1 = fract(time + 0.5);

    vec2 uv0 = UV + flow * phase0 * flow_strength;
    vec2 uv1 = UV + flow * phase1 * flow_strength;

    vec4 col0 = texture(albedo_texture, uv0);
    vec4 col1 = texture(albedo_texture, uv1);

    float blend_weight = abs(0.5 - phase0) / 0.5;
    vec4 final_color = mix(col0, col1, blend_weight) * tint_color;

    {"COLOR = final_color;" if mode_2d else "ALBEDO = final_color.rgb; ALPHA = final_color.a; ROUGHNESS = 0.05; METALLIC = 0.0;"}
}}
"""
    with open(chemin_shader, "w", encoding="utf-8") as f:
        f.write(code_shader)

    code_tres = f"""[gd_resource type="ShaderMaterial" load_steps=3 format=3]

[ext_resource type="Shader" path="res://{os.path.basename(chemin_shader)}" id="1_shader"]
[ext_resource type="Texture2D" path="res://{nom_base}_flowmap.png" id="2_flow"]

[resource]
shader = ExtResource("1_shader")
shader_parameter/tint_color = Color(0.2, 0.55, 0.9, 0.9)
shader_parameter/flow_speed = 0.4
shader_parameter/flow_strength = 0.15
shader_parameter/flowmap_texture = ExtResource("2_flow")
"""
    with open(chemin_tres, "w", encoding="utf-8") as f:
        f.write(code_tres)

    return chemin_shader, chemin_tres
