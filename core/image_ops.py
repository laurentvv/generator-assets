#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module d'opérations d'images avancées pour assets 2D & 3D (Godot Engine).
Détourage flood-fill, centrage, cadrage carré, génération de maps PBR (Normal, Roughness, Height, AO, ORM),
assemblage spritesheet, quantification pixel art, et export de fichiers matériaux Godot (.tres).
"""

import json
import math
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

# Palettes rétro célèbres pour le workflow Pixel Art
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
# 1. Détourage & Centrage (2D)
# ==============================================================================
def detourer_fond_blanc(image: Image.Image, tolerance: int = 60) -> Image.Image:
    """
    Détoure le fond blanc par flood-fill depuis les 4 coins extérieurs.
    Préserve intactes les zones blanches internes des objets.
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
    """Détecte la boîte englobante et centre l'objet dans un canevas carré avec marge."""
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
    marge_ratio: float = 0.06
) -> Image.Image:
    """Combine le détourage flood-fill, le recadrage centré et le redimensionnement."""
    detouree = detourer_fond_blanc(image, tolerance=tolerance)
    return centrer_et_recadrer(detouree, redimensionner=redimensionner, marge_ratio=marge_ratio)


# ==============================================================================
# 2. Génération de Maps PBR pour la 3D (Normal, Roughness, Height, AO, ORM)
# ==============================================================================
def generer_height_map(image: Image.Image) -> Image.Image:
    """Génère une map de hauteur/déplacement en niveaux de gris équilibrés."""
    gray = image.convert("L")
    # Légère égalisation pour étaler les contrastes
    enhanced = ImageOps.autocontrast(gray, cutoff=2)
    return enhanced


def generer_normal_map(image: Image.Image, strength: float = 3.5) -> Image.Image:
    """
    Calcule une Tangent-Space Normal Map (format OpenGL compatible Godot 4)
    via gradients Sobel horizontaux et verticaux.
    """
    height_map = generer_height_map(image)
    arr = np.array(height_map, dtype=np.float32) / 255.0

    # Gradients Sobel 3x3
    dx = np.zeros_like(arr)
    dy = np.zeros_like(arr)
    
    dx[:, 1:-1] = (arr[:, 2:] - arr[:, :-2]) * 0.5
    dy[1:-1, :] = (arr[2:, :] - arr[:-2, :]) * 0.5
    
    # Bords
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

    # Encodage OpenGL (X+ vers la droite, Y+ vers le haut, Z+ vers l'extérieur)
    r = ((nx * 0.5 + 0.5) * 255).astype(np.uint8)
    g = (((-ny) * 0.5 + 0.5) * 255).astype(np.uint8)
    b = ((nz * 0.5 + 0.5) * 255).astype(np.uint8)

    return Image.fromarray(np.stack([r, g, b], axis=-1), mode="RGB")


def generer_roughness_map(image: Image.Image, inverser: bool = False, contraste: float = 1.3) -> Image.Image:
    """Génère la map de rugosité (Roughness) à partir des fréquences de texture."""
    gray = image.convert("L")
    
    # Filtre passe-haut pour capter les micro-rugosités
    blur = gray.filter(ImageFilter.GaussianBlur(radius=3))
    high_pass = ImageChops.difference(gray, blur)
    high_pass = ImageOps.autocontrast(high_pass)
    
    # Mélange avec la luminosité de base
    roughness = ImageChops.add(gray, high_pass, scale=1.5, offset=-20)
    
    # Ajustement de contraste
    enhancer = ImageEnhance.Contrast(roughness)
    roughness = enhancer.enhance(contraste)

    if inverser:
        roughness = ImageOps.invert(roughness)

    return roughness


def generer_ao_map(image: Image.Image, force: float = 1.5) -> Image.Image:
    """Génère une map d'occlusion ambiante (Ambient Occlusion) pour les ombres de creux."""
    gray = image.convert("L")
    blur = gray.filter(ImageFilter.GaussianBlur(radius=8))
    ao = ImageChops.multiply(gray, blur)
    ao = ImageOps.autocontrast(ao, cutoff=3)
    enhancer = ImageEnhance.Contrast(ao)
    return enhancer.enhance(force)


def generer_orm_pack(ao_img: Image.Image, roughness_img: Image.Image, metallic_img: Optional[Image.Image] = None) -> Image.Image:
    """
    Assemble une texture ORM combinée pour Godot 4 :
    - Rouge (R) = Ambient Occlusion
    - Vert (G)  = Roughness
    - Bleu (B)  = Metallic (noir par défaut pour les matériaux diélectriques/pierre/bois)
    """
    ao = ao_img.convert("L")
    rough = roughness_img.convert("L")
    
    if metallic_img:
        metal = metallic_img.convert("L")
    else:
        metal = Image.new("L", ao.size, 0) # Non métallique par défaut
        
    return Image.merge("RGB", (ao, rough, metal))


def exporter_fichier_materiau_godot(nom_base: str, output_dir: str) -> str:
    """
    Génère un fichier de ressource Godot 4 (.tres) StandardMaterial3D
    prêt à être appliqué directement sur n'importe quel Mesh 3D.
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
    """Génère un fichier Godot 4 (.tres) Environment avec Skybox 360° équirectangulaire."""
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
# 3. Assemblage & Pixel Art
# ==============================================================================
def convertir_pixel_art(
    image: Image.Image,
    taille_grille: int = 64,
    taille_export: int = 512,
    palette_nom: str = "pico8"
) -> Image.Image:
    """Transforme un asset en sprite Pixel Art net avec quantification."""
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
    """Assemble une liste d'images dans une feuille de sprites avec JSON Godot 4."""
    if not images:
        raise ValueError("Aucune image à assembler.")

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
    """Génère une grille 3x3 pour vérifier le raccord parfait d'une texture seamless."""
    w, h = image.size
    apercu = Image.new(image.mode, (w * rep_x, h * rep_y))
    for i in range(rep_x):
        for j in range(rep_y):
            apercu.paste(image, (i * w, j * h))
    return apercu
