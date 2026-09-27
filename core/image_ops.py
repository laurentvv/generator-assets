#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Advanced image operations module for 2D & 3D assets (Godot Engine).
Flood-fill background removal, centering, square cropping, PBR map generation (Normal, Roughness, Height, AO, ORM),
spritesheet assembly, pixel-art quantization, and Godot material file (.tres) export.
"""

import math
import os
from typing import List, Optional, Tuple
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

# Famous retro palettes for the Pixel Art workflow
PALETTES_RETRO = {
    "pico8": [
        (0, 0, 0), (29, 43, 83), (126, 37, 83), (0, 135, 81),
        (171, 82, 54), (95, 87, 79), (194, 195, 199), (255, 241, 232),
        (255, 0, 77), (255, 163, 0), (255, 236, 39), (0, 228, 54),
        (41, 173, 255), (131, 118, 156), (255, 119, 168), (255, 204, 170)
    ],
    "gameboy": [
        (15, 56, 15), (48, 98, 48), (139, 172, 15), (155, 188, 15)
    ],
    "endesga32": [
        (190, 74, 47), (215, 118, 67), (234, 212, 170), (228, 166, 114),
        (184, 111, 80), (115, 62, 57), (62, 39, 49), (162, 38, 51),
        (228, 59, 68), (247, 118, 34), (254, 174, 52), (254, 231, 97),
        (99, 199, 77), (62, 137, 72), (38, 92, 66), (25, 60, 62),
        (18, 78, 137), (0, 153, 219), (44, 232, 245), (255, 255, 255),
        (192, 203, 220), (139, 155, 180), (90, 105, 136), (58, 68, 102),
        (38, 43, 68), (24, 20, 37), (255, 0, 68), (254, 91, 140),
        (254, 174, 187), (255, 214, 219), (181, 80, 136), (118, 66, 138)
    ]
}


# ==============================================================================
# 1. Background Removal & Centering (2D)
# ==============================================================================
def detourer_fond_blanc(image: Image.Image, tolerance: int = 60) -> Image.Image:
    """
    Removes the white background by flood-fill from the 4 outer corners.
    Keeps the internal white areas of the objects intact.
    """
    rgb = image.convert("RGB")
    largeur, hauteur = rgb.size
    SENTINELLE = (255, 0, 255)

    for graine in [(0, 0), (largeur - 1, 0), (0, hauteur - 1), (largeur - 1, hauteur - 1)]:
        pixel = rgb.getpixel(graine)
        if all(abs(c - 255) <= 40 for c in pixel[:3]):
            ImageDraw.floodfill(rgb, graine, SENTINELLE, thresh=tolerance)

    sentinelle_img = Image.new("RGB", rgb.size, SENTINELLE)
    diff = ImageChops.difference(rgb, sentinelle_img).convert("L")
    alpha = diff.point(lambda p: 0 if p <= 12 else 255)

    rgba = image.convert("RGBA")
    rgba.putalpha(alpha)
    return rgba


def centrer_et_recadrer(
    image_rgba: Image.Image,
    redimensionner: int = 512,
    marge_ratio: float = 0.06
) -> Image.Image:
    """Detects the bounding box and centers the object in a square canvas with margin."""
    boite = image_rgba.getbbox()
    if boite:
        contenu = image_rgba.crop(boite)
        cote = max(contenu.size)
        marge = max(1, int(cote * marge_ratio))
        canevas_dim = cote + 2 * marge
        canvas = Image.new("RGBA", (canevas_dim, canevas_dim), (0, 0, 0, 0))
        canvas.paste(contenu, ((canevas_dim - contenu.width) // 2, (canevas_dim - contenu.height) // 2), contenu)
        resultat = canvas
    else:
        resultat = image_rgba

    if redimensionner and redimensionner > 0:
        resultat = resultat.resize((redimensionner, redimensionner), Image.Resampling.LANCZOS)

    return resultat


def post_process_asset(
    image: Image.Image,
    tolerance: int = 60,
    redimensionner: int = 512,
    marge_ratio: float = 0.06,
    segmenter: str = "auto"
) -> Image.Image:
    """
    Combines background removal (RMBG/BiRefNet AI or Flood-fill), centered cropping and resizing.
    """
    if segmenter == "none":
        if redimensionner and redimensionner > 0 and image.size != (redimensionner, redimensionner):
            return image.resize((redimensionner, redimensionner), Image.Resampling.LANCZOS)
        return image
    elif segmenter in ("floodfill", "classic"):
        detouree = detourer_fond_blanc(image, tolerance=tolerance)
    else:  # "auto", "birefnet", "rmbg", "ia"
        try:
            from core.segmentation import detourer_ia
            detouree = detourer_ia(image)
        except Exception as e:
            print(f"⚠️ [ImageOps] Falling back to floodfill background removal: {e}")
            detouree = detourer_fond_blanc(image, tolerance=tolerance)

    return centrer_et_recadrer(detouree, redimensionner=redimensionner, marge_ratio=marge_ratio)


# ==============================================================================
# 2. PBR Map Generation for 3D (Normal, Roughness, Height, AO, ORM)
# ==============================================================================
def generer_height_map(image: Image.Image) -> Image.Image:
    """Generates a balanced grayscale height/displacement map."""
    gray = image.convert("L")
    # Slight equalization to spread the contrasts
    enhanced = ImageOps.autocontrast(gray, cutoff=2)
    return enhanced


def generer_normal_map(image: Image.Image, strength: float = 3.5) -> Image.Image:
    """
    Computes a Tangent-Space Normal Map (OpenGL format, Godot 4 compatible)
    via horizontal and vertical Sobel gradients.
    """
    height_map = generer_height_map(image)
    arr = np.array(height_map, dtype=np.float32) / 255.0

    # Gradients Sobel 3x3
    dx = np.zeros_like(arr)
    dy = np.zeros_like(arr)

    dx[:, 1:-1] = (arr[:, 2:] - arr[:, :-2]) * 0.5
    dy[1:-1, :] = (arr[2:, :] - arr[:-2, :]) * 0.5

    # Edges
    dx[:, 0] = arr[:, 1] - arr[:, 0]
    dx[:, -1] = arr[:, -1] - arr[:, -2]
    dy[0, :] = arr[1, :] - arr[0, :]
    dy[-1, :] = arr[-1, :] - arr[-2, :]

    nx = -dx * strength
    ny = -dy * strength
    nz = np.ones_like(arr)

    norm = np.sqrt(nx**2 + ny**2 + nz**2)
    norm[norm == 0] = 1.0
    nx /= norm
    ny /= norm
    nz /= norm

    # OpenGL encoding (X+ to the right, Y+ up, Z+ outward)
    r = ((nx * 0.5 + 0.5) * 255).astype(np.uint8)
    g = (((-ny) * 0.5 + 0.5) * 255).astype(np.uint8)
    b = ((nz * 0.5 + 0.5) * 255).astype(np.uint8)

    return Image.fromarray(np.stack([r, g, b], axis=-1), mode="RGB")


def generer_roughness_map(image: Image.Image, inverser: bool = False, contraste: float = 1.3) -> Image.Image:
    """Generates the roughness map from texture frequencies."""
    gray = image.convert("L")

    # High-pass filter to capture micro-roughness
    blur = gray.filter(ImageFilter.GaussianBlur(radius=3))
    high_pass = ImageChops.difference(gray, blur)
    high_pass = ImageOps.autocontrast(high_pass)

    # Blend with the base luminance
    roughness = ImageChops.add(gray, high_pass, scale=1.5, offset=-20)

    # Contrast adjustment
    enhancer = ImageEnhance.Contrast(roughness)
    roughness = enhancer.enhance(contraste)

    if inverser:
        roughness = ImageOps.invert(roughness)

    return roughness


def generer_ao_map(image: Image.Image, force: float = 1.5) -> Image.Image:
    """Generates an ambient occlusion map for crevice shadows."""
    gray = image.convert("L")
    blur = gray.filter(ImageFilter.GaussianBlur(radius=8))
    ao = ImageChops.multiply(gray, blur)
    ao = ImageOps.autocontrast(ao, cutoff=3)
    enhancer = ImageEnhance.Contrast(ao)
    return enhancer.enhance(force)


def generer_orm_pack(ao_img: Image.Image, roughness_img: Image.Image, metallic_img: Optional[Image.Image] = None) -> Image.Image:
    """
    Assembles a combined ORM texture for Godot 4:
    - Red (R)   = Ambient Occlusion
    - Green (G) = Roughness
    - Blue (B)  = Metallic (black by default for dielectric/stone/wood materials)
    """
    ao = ao_img.convert("L")
    rough = roughness_img.convert("L")

    if metallic_img:
        metal = metallic_img.convert("L")
    else:
        metal = Image.new("L", ao.size, 0) # Non-metallic by default

    return Image.merge("RGB", (ao, rough, metal))


def exporter_fichier_materiau_godot(nom_base: str, output_dir: str) -> str:
    """
    Generates a Godot 4 StandardMaterial3D resource file (.tres)
    ready to be applied directly to any 3D Mesh.
    """
    fichier_tres = os.path.join(output_dir, f"{nom_base}_material.tres")

    contenu_tres = f"""[gd_resource type="StandardMaterial3D" load_steps=5 format=3]

[ext_resource type="Texture2D" path="res://assets/{nom_base}_albedo.png" id="1"]
[ext_resource type="Texture2D" path="res://assets/{nom_base}_normal.png" id="2"]
[ext_resource type="Texture2D" path="res://assets/{nom_base}_orm.png" id="3"]
[ext_resource type="Texture2D" path="res://assets/{nom_base}_height.png" id="4"]

[resource]
albedo_texture = ExtResource("1")
roughness = 1.0
roughness_texture = ExtResource("3")
roughness_texture_channel = 1
normal_enabled = true
normal_scale = 1.0
normal_texture = ExtResource("2")
ao_enabled = true
ao_light_affect = 0.5
ao_texture = ExtResource("3")
ao_texture_channel = 0
heightmap_enabled = true
heightmap_scale = 2.0
heightmap_texture = ExtResource("4")
uv1_scale = Vector3(1, 1, 1)
"""
    with open(fichier_tres, "w", encoding="utf-8") as f:
        f.write(contenu_tres)

    return fichier_tres


def exporter_fichier_skybox_godot(nom_base: str, output_dir: str) -> str:
    """Generates a Godot 4 (.tres) Environment file with 360° equirectangular Skybox."""
    fichier_tres = os.path.join(output_dir, f"{nom_base}_sky_env.tres")

    contenu_tres = f"""[gd_resource type="Environment" load_steps=3 format=3]

[ext_resource type="Texture2D" path="res://assets/{nom_base}_sky.png" id="1"]

[sub_resource type="PanoramaSkyMaterial" id="PanoramaSkyMaterial_1"]
panorama = ExtResource("1")

[sub_resource type="Sky" id="Sky_1"]
sky_material = SubResource("PanoramaSkyMaterial_1")

[resource]
background_mode = 2
sky = SubResource("Sky_1")
ambient_light_source = 3
reflected_light_source = 2
tonemap_mode = 2
ssr_enabled = true
ssao_enabled = true
glow_enabled = true
"""
    with open(fichier_tres, "w", encoding="utf-8") as f:
        f.write(contenu_tres)

    return fichier_tres


# ==============================================================================
# 3. Assembly & Pixel Art
# ==============================================================================
def convertir_pixel_art(
    image: Image.Image,
    taille_grille: int = 64,
    taille_export: int = 512,
    palette_nom: str = "pico8"
) -> Image.Image:
    """Turns an asset into a sharp Pixel Art sprite with quantization."""
    rgba = image.convert("RGBA")
    pixel_img = rgba.resize((taille_grille, taille_grille), Image.Resampling.BILINEAR)

    r, g, b, a = pixel_img.split()
    rgb_img = Image.merge("RGB", (r, g, b))

    palette_colors = PALETTES_RETRO.get(palette_nom.lower(), PALETTES_RETRO["pico8"])

    palette_data = []
    for couleur in palette_colors:
        palette_data.extend(couleur)
    palette_data.extend([0] * (768 - len(palette_data)))

    palette_img = Image.new("P", (1, 1))
    palette_img.putpalette(palette_data)

    rgb_quantifie = rgb_img.quantize(palette=palette_img, dither=Image.Dither.FLOYDSTEINBERG).convert("RGB")
    masque_alpha = a.point(lambda p: 255 if p > 120 else 0)

    r_q, g_q, b_q = rgb_quantifie.split()
    pixel_art_final = Image.merge("RGBA", (r_q, g_q, b_q, masque_alpha))

    if taille_export > taille_grille:
        pixel_art_final = pixel_art_final.resize((taille_export, taille_export), Image.Resampling.NEAREST)

    return pixel_art_final


def assembler_spritesheet(
    images: List[Image.Image],
    noms: List[str],
    colonnes: Optional[int] = None
) -> Tuple[Image.Image, dict]:
    """Assembles a list of images into a sprite sheet with a Godot 4 JSON."""
    if not images:
        raise ValueError("No image to assemble.")

    nb_images = len(images)
    cell_w, cell_h = images[0].size

    if not colonnes or colonnes <= 0:
        colonnes = math.ceil(math.sqrt(nb_images))
    lignes = math.ceil(nb_images / colonnes)

    largeur_sheet = colonnes * cell_w
    hauteur_sheet = lignes * cell_h

    sheet = Image.new("RGBA", (largeur_sheet, hauteur_sheet), (0, 0, 0, 0))
    metadata = {
        "cell_width": cell_w,
        "cell_height": cell_h,
        "columns": colonnes,
        "rows": lignes,
        "total_frames": nb_images,
        "frames": []
    }

    for idx, (img, nom) in enumerate(zip(images, noms)):
        col = idx % colonnes
        row = idx // colonnes
        x = col * cell_w
        y = row * cell_h

        if img.size != (cell_w, cell_h):
            img = img.resize((cell_w, cell_h), Image.Resampling.LANCZOS)

        sheet.paste(img, (x, y), img)
        metadata["frames"].append({
            "name": nom,
            "index": idx,
            "x": x,
            "y": y,
            "width": cell_w,
            "height": cell_h
        })

    return sheet, metadata


def creer_apercu_tuilage(image: Image.Image, rep_x: int = 3, rep_y: int = 3) -> Image.Image:
    """Generates a 3x3 grid to check the perfect tiling of a seamless texture."""
    w, h = image.size
    apercu = Image.new(image.mode, (w * rep_x, h * rep_y))
    for i in range(rep_x):
        for j in range(rep_y):
            apercu.paste(image, (i * w, j * h))
    return apercu
