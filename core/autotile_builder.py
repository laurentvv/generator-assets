#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module de génération d'atlas d'Autotile 47 tuiles (Terrain Minimal 3x3 / Wang Tiles) pour Godot 4.
Génère l'atlas d'images PNG et la ressource TileSet (.tres) avec peering bits pré-configurés.
"""

import os
from typing import Dict, List, Tuple
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def _creer_masque_tuile_3x3(
    voisins: Tuple[int, int, int, int, int, int, int, int],
    tile_size: int = 128,
    radius: float = 0.5
) -> Image.Image:
    """
    Génère un masque Alpha 2D pour une tuile selon l'état de ses 8 voisins (TL, T, TR, R, BR, B, BL, L).
    0 = Biome B (fond), 1 = Biome A (premier plan / terrain principal).
    """
    tl, t, tr, r, br, b, bl, l = voisins
    mask = Image.new("L", (tile_size, tile_size), 255)
    draw = ImageDraw.Draw(mask)

    demi = tile_size // 2

    # Si un côté cardinal est vide (0), découper la bordure
    if not t:
        draw.rectangle([0, 0, tile_size, demi // 2], fill=0)
    if not b:
        draw.rectangle([0, tile_size - demi // 2, tile_size, tile_size], fill=0)
    if not l:
        draw.rectangle([0, 0, demi // 2, tile_size], fill=0)
    if not r:
        draw.rectangle([tile_size - demi // 2, 0, tile_size, tile_size], fill=0)

    # Coins intérieurs / extérieurs
    if not tl and t and l:
        draw.rectangle([0, 0, demi // 2, demi // 2], fill=0)
    if not tr and t and r:
        draw.rectangle([tile_size - demi // 2, 0, tile_size, demi // 2], fill=0)
    if not bl and b and l:
        draw.rectangle([0, tile_size - demi // 2, demi // 2, tile_size], fill=0)
    if not br and b and r:
        draw.rectangle([tile_size - demi // 2, tile_size - demi // 2, tile_size, tile_size], fill=0)

    # Lissage léger des transitions
    mask_smooth = mask.filter(ImageFilter.GaussianBlur(radius=max(1, tile_size // 32)))
    return mask_smooth


# Liste des 47 configurations canoniques de voisins pour le Minimal 3x3 Godot 4
# Format des 8 voisins : (TL, T, TR, R, BR, B, BL, L)
CONFIGS_47_TUILES = [
    # 0-7 : Plein, isolés et fins
    (1, 1, 1, 1, 1, 1, 1, 1), # 0 : Plein centre
    (0, 0, 0, 0, 0, 0, 0, 0), # 1 : Îlot isolé
    (0, 1, 0, 0, 0, 1, 0, 0), # 2 : Ligne verticale
    (0, 0, 0, 1, 0, 0, 0, 1), # 3 : Ligne horizontale
    (0, 1, 0, 0, 0, 0, 0, 0), # 4 : Bout haut
    (0, 0, 0, 1, 0, 0, 0, 0), # 5 : Bout droite
    (0, 0, 0, 0, 0, 1, 0, 0), # 6 : Bout bas
    (0, 0, 0, 0, 0, 0, 0, 1), # 7 : Bout gauche
    # 8-15 : Bordures cardinales simples
    (0, 0, 0, 1, 1, 1, 1, 1), # 8 : Bord haut
    (1, 1, 0, 0, 0, 1, 1, 1), # 9 : Bord droite
    (1, 1, 1, 1, 0, 0, 0, 1), # 10 : Bord bas
    (0, 1, 1, 1, 1, 1, 0, 0), # 11 : Bord gauche
    (0, 0, 0, 1, 1, 1, 0, 0), # 12 : Coin externe haut-gauche
    (0, 0, 0, 0, 0, 1, 1, 1), # 13 : Coin externe haut-droite
    (1, 1, 0, 0, 0, 0, 0, 1), # 14 : Coin externe bas-droite
    (0, 1, 1, 1, 0, 0, 0, 0), # 15 : Coin externe bas-gauche
    # 16-23 : T-junctions et croix
    (0, 0, 0, 1, 1, 1, 1, 1),
    (1, 1, 1, 1, 0, 1, 1, 1),
    (1, 1, 1, 1, 1, 1, 0, 1),
    (1, 1, 0, 1, 1, 1, 1, 1),
    (0, 1, 1, 1, 1, 1, 1, 1),
    (1, 1, 1, 0, 0, 1, 1, 1),
    (1, 1, 1, 1, 0, 0, 1, 1),
    (1, 1, 1, 1, 1, 0, 0, 1),
    # 24-31 : Coins internes (concaves)
    (0, 1, 1, 1, 1, 1, 1, 1), # 24 : Coin interne TL
    (1, 1, 0, 1, 1, 1, 1, 1), # 25 : Coin interne TR
    (1, 1, 1, 1, 0, 1, 1, 1), # 26 : Coin interne BR
    (1, 1, 1, 1, 1, 1, 0, 1), # 27 : Coin interne BL
    (0, 1, 0, 1, 1, 1, 1, 1), # 28 : Double coin interne haut
    (1, 1, 0, 1, 0, 1, 1, 1), # 29 : Double coin interne droite
    (1, 1, 1, 1, 0, 1, 0, 1), # 30 : Double coin interne bas
    (0, 1, 1, 1, 1, 1, 0, 1), # 31 : Double coin interne gauche
    # 32-39 : Diagonales et combinaisons complexes
    (0, 1, 0, 1, 0, 1, 1, 1),
    (1, 1, 0, 1, 0, 1, 0, 1),
    (0, 1, 1, 1, 0, 1, 0, 1),
    (0, 1, 0, 1, 1, 1, 0, 1),
    (0, 1, 0, 1, 0, 1, 0, 1),
    (1, 0, 1, 1, 1, 1, 1, 1),
    (1, 1, 1, 1, 1, 0, 1, 1),
    (1, 1, 1, 0, 1, 1, 1, 1),
    # 40-46 : Remplissages d'angles
    (1, 1, 1, 1, 1, 1, 1, 0),
    (0, 0, 1, 1, 1, 1, 1, 1),
    (1, 1, 0, 0, 1, 1, 1, 1),
    (1, 1, 1, 1, 0, 0, 1, 1),
    (1, 1, 1, 1, 1, 1, 0, 0),
    (0, 1, 0, 0, 1, 1, 1, 1),
    (1, 1, 0, 1, 0, 0, 1, 1),
]


def generer_atlas_47_tuiles(
    image_biome_a: Image.Image,
    image_biome_b: Image.Image,
    tile_size: int = 128,
    colonnes: int = 8
) -> Image.Image:
    """Compose la planche atlas de 47 tuiles avec transitions propres entre les deux biomes."""
    lignes = (len(CONFIGS_47_TUILES) + colonnes - 1) // colonnes
    atlas_w = colonnes * tile_size
    atlas_h = lignes * tile_size

    atlas = Image.new("RGBA", (atlas_w, atlas_h), (0, 0, 0, 0))

    tile_a = image_biome_a.convert("RGBA").resize((tile_size, tile_size), Image.Resampling.LANCZOS)
    tile_b = image_biome_b.convert("RGBA").resize((tile_size, tile_size), Image.Resampling.LANCZOS)

    for idx, voisins in enumerate(CONFIGS_47_TUILES):
        col = idx % colonnes
        lig = idx // colonnes
        pos_x = col * tile_size
        pos_y = lig * tile_size

        mask = _creer_masque_tuile_3x3(voisins, tile_size=tile_size)

        # Fond = Biome B, Premier plan = Biome A masqué
        tuile_composite = tile_b.copy()
        tuile_composite.paste(tile_a, (0, 0), mask)

        atlas.paste(tuile_composite, (pos_x, pos_y))

    return atlas


def exporter_tileset_godot(
    nom_base: str,
    output_dir: str,
    tile_size: int = 128,
    colonnes: int = 8
) -> str:
    """Génère la ressource TileSet (.tres) Godot 4 avec TerrainSet et peering bits 3x3 minimal configurés."""
    chemin_tres = os.path.join(output_dir, f"{nom_base}_tileset.tres")

    # Mappage des peering bits Godot 4 :
    # 0 = top_left, 1 = top, 2 = top_right, 3 = right, 4 = bottom_right, 5 = bottom, 6 = bottom_left, 7 = left
    peering_names = [
        "top_left_corner", "top_side", "top_right_corner", "right_side",
        "bottom_right_corner", "bottom_side", "bottom_left_corner", "left_side"
    ]

    lignes_tuiles = []
    for idx, voisins in enumerate(CONFIGS_47_TUILES):
        col = idx % colonnes
        lig = idx // colonnes
        coords = f"Vector2i({col}, {lig})"

        bits_str = [f"0:0/0/terrain_set = 0", f"0:0/0/terrain = 0"]
        for p_idx, p_name in enumerate(peering_names):
            if voisins[p_idx] == 1:
                bits_str.append(f"0:0/0/terrains_peering_bit/{p_name} = 0")

        # Configuration de la tuile dans la source TileSetAtlasSource
        tuile_block = f"""{coords}/0 = 0
{coords}/0/terrain_set = 0
{coords}/0/terrain = 0"""
        for p_idx, p_name in enumerate(peering_names):
            if voisins[p_idx] == 1:
                tuile_block += f"\n{coords}/0/terrains_peering_bit/{p_name} = 0"
        lignes_tuiles.append(tuile_block)

    tiles_payload = "\n".join(lignes_tuiles)

    code_tres = f"""[gd_resource type="TileSet" load_steps=3 format=3]

[ext_resource type="Texture2D" path="res://{nom_base}_atlas.png" id="1_tex"]

[sub_resource type="TileSetAtlasSource" id="TileSetAtlasSource_1"]
texture = ExtResource("1_tex")
texture_region_size = Vector2i({tile_size}, {tile_size})
{tiles_payload}

[resource]
tile_size = Vector2i({tile_size}, {tile_size})
terrain_set_0/mode = 0
terrain_set_0/terrain_0/name = "Terrain_{nom_base}"
terrain_set_0/terrain_0/color = Color(0.3, 0.7, 0.2, 1.0)
sources/0 = SubResource("TileSetAtlasSource_1")
"""
    with open(chemin_tres, "w", encoding="utf-8") as f:
        f.write(code_tres)

    return chemin_tres
