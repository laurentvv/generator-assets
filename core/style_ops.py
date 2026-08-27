#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module d'analyse stylistique, cohérence d'assets (IP-Adapter) et extraction de palettes de couleurs pour Godot 4.
Gère :
- L'extraction de palettes dominantes (K-Means / Quantification)
- L'exportation de palettes Godot 4 (.tres), Aseprite/GIMP (.gpl) et JSON
- L'analyse de la signature de style et la construction d'ancres visuelles verrouillées
- L'assemblage de planches de cohérence visuelle
"""

import json
import math
import os
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def extraire_palette_image(image: Image.Image, n_couleurs: int = 6) -> List[Dict[str, Any]]:
    """
    Extrait les N couleurs les plus représentatives de l'image (ignorant la transparence).
    """
    img_rgb = image.convert("RGBA")
    arr = np.array(img_rgb)
    
    # Filtrer les pixels non-transparents
    mask = arr[..., 3] > 40
    pixels = arr[mask][:, :3]
    if len(pixels) < 100:
        pixels = arr.reshape(-1, 4)[:, :3]

    # Quantification via Pillow
    img_opaque = Image.fromarray(pixels.reshape(-1, 1, 3))
    quantisee = img_opaque.quantize(colors=n_couleurs, method=Image.Quantize.MEDIANCUT)
    palette_raw = quantisee.getpalette()[:n_couleurs * 3]

    palette_list = []
    for i in range(0, len(palette_raw), 3):
        r, g, b = palette_raw[i], palette_raw[i+1], palette_raw[i+2]
        hex_code = f"#{r:02x}{g:02x}{b:02x}".upper()
        palette_list.append({
            "rgb": [int(r), int(g), int(b)],
            "hex": hex_code,
            "color_godot": f"Color({r/255.0:.3f}, {g/255.0:.3f}, {b/255.0:.3f}, 1.0)"
        })

    return palette_list


def analyser_signature_stylistique(image: Image.Image, palette: List[Dict[str, Any]]) -> str:
    """Construit un prompt de verrouillage de style (Style Lock Anchor) à partir de la palette."""
    hex_list = [c["hex"] for c in palette[:4]]
    hex_str = ", ".join(hex_list)

    # Analyse de luminosité et saturation
    arr = np.array(image.convert("RGB")).astype(np.float32) / 255.0
    luminance = np.mean(0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2])
    
    ambiance = "dark moody high contrast" if luminance < 0.45 else "vibrant clear lighting"
    style_lock = (
        f"matching exact art style, strict color harmony [{hex_str}], "
        f"{ambiance}, cohesive materials, uniform shading and bevels, 2D game asset icon"
    )
    return style_lock


def generer_image_palette_preview(palette: List[Dict[str, Any]], largeur: int = 512, hauteur: int = 80) -> Image.Image:
    """Crée un bandeau visuel affichant les pastilles de couleur et leurs codes hexadécimaux."""
    img = Image.new("RGBA", (largeur, hauteur), (25, 25, 30, 255))
    draw = ImageDraw.Draw(img)

    n = len(palette)
    swatch_w = largeur // n

    for i, col in enumerate(palette):
        x0 = i * swatch_w
        x1 = x0 + swatch_w
        rgb = tuple(col["rgb"])
        draw.rectangle([x0 + 4, 6, x1 - 4, hauteur - 24], fill=rgb, outline=(60, 60, 70))
        # Texte HEX
        draw.text((x0 + 6, hauteur - 18), col["hex"], fill=(220, 220, 230))

    return img


def exporter_palette_godot(
    nom_base: str,
    output_dir: str,
    palette: List[Dict[str, Any]]
) -> Tuple[str, str, str, str]:
    """Exporte la palette en ressource Godot 4 (.tres), format Aseprite (.gpl), JSON et aperçu PNG."""
    os.makedirs(output_dir, exist_ok=True)
    chemin_tres = os.path.join(output_dir, f"{nom_base}_palette.tres")
    chemin_gpl = os.path.join(output_dir, f"{nom_base}.gpl")
    chemin_json = os.path.join(output_dir, f"{nom_base}_palette.json")
    chemin_png = os.path.join(output_dir, f"{nom_base}_palette_preview.png")

    # 1. Ressource Gradient Godot 4
    n = len(palette)
    offsets = [round(i / max(n - 1, 1), 3) for i in range(n)]
    colors_str = ", ".join([col["color_godot"] for col in palette])
    offsets_str = ", ".join([str(o) for o in offsets])

    code_tres = f"""[gd_resource type="Gradient" format=3]

[resource]
offsets = PackedFloat32Array({offsets_str})
colors = PackedColorArray({colors_str})
"""
    with open(chemin_tres, "w", encoding="utf-8") as f:
        f.write(code_tres)

    # 2. Format GPL (GIMP / Aseprite / Krita)
    lignes_gpl = ["GIMP Palette", f"Name: {nom_base}", "Columns: 6", "#"]
    for col in palette:
        r, g, b = col["rgb"]
        lignes_gpl.append(f"{r:3d} {g:3d} {b:3d}\t{col['hex']}")
    with open(chemin_gpl, "w", encoding="utf-8") as f:
        f.write("\n".join(lignes_gpl))

    # 3. JSON
    with open(chemin_json, "w", encoding="utf-8") as f:
        json.dump(palette, f, indent=2)

    # 4. Preview PNG
    img_preview = generer_image_palette_preview(palette)
    img_preview.save(chemin_png, "PNG")

    return chemin_tres, chemin_gpl, chemin_json, chemin_png


def assembler_planche_coherence(
    image_ref: Image.Image,
    variantes: List[Tuple[str, Image.Image]],
    taille_cellule: int = 256
) -> Image.Image:
    """Crée une planche récapitulative de cohérence visuelle avec l'image de référence."""
    nb_vars = len(variantes)
    nb_colonnes = 1 + min(nb_vars, 4)
    nb_lignes = 1 + (nb_vars - 1) // 4 if nb_vars > 4 else 1

    largeur_totale = nb_colonnes * taille_cellule
    hauteur_totale = nb_lignes * taille_cellule + 40

    planche = Image.new("RGBA", (largeur_totale, hauteur_totale), (20, 20, 25, 255))
    draw = ImageDraw.Draw(planche)

    # Titre
    draw.text((16, 12), "IP-ADAPTER STYLE CONSISTENCY BOARD (GODOT 4)", fill=(240, 200, 80))

    # Image de référence à gauche
    ref_redim = image_ref.convert("RGBA").resize((taille_cellule - 20, taille_cellule - 20), Image.Resampling.LANCZOS)
    draw.rectangle([10, 38, taille_cellule - 10, 38 + taille_cellule - 20], outline=(220, 160, 40), width=2)
    planche.paste(ref_redim, (10, 38), ref_redim)
    draw.text((14, 42), "REFERENCE", fill=(255, 200, 50))

    # Variantes cohérentes
    for idx, (label, img_var) in enumerate(variantes):
        col_idx = 1 + (idx % 4)
        lig_idx = idx // 4
        x0 = col_idx * taille_cellule + 10
        y0 = 38 + lig_idx * taille_cellule
        var_redim = img_var.convert("RGBA").resize((taille_cellule - 20, taille_cellule - 20), Image.Resampling.LANCZOS)
        
        draw.rectangle([x0, y0, x0 + taille_cellule - 20, y0 + taille_cellule - 20], outline=(80, 120, 180), width=1)
        planche.paste(var_redim, (x0, y0), var_redim)
        draw.text((x0 + 6, y0 + 6), label[:20].upper(), fill=(140, 200, 255))

    return planche
