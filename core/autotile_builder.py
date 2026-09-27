#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
47-tile Autotile atlas generation module (Minimal 3x3 Terrain / Wang Tiles) for Godot 4.
Generates the PNG image atlas and the TileSet resource (.tres) with pre-configured peering bits.
"""

import os
from typing import Tuple
from PIL import Image, ImageDraw, ImageFilter


def _creer_masque_tuile_3x3(
    voisins: Tuple[int, int, int, int, int, int, int, int],
    tile_size: int = 128,
    radius: float = 0.5
) -> Image.Image:
    """
    Generates a 2D Alpha mask for a tile based on the state of its 8 neighbors (TL, T, TR, R, BR, B, BL, L).
    0 = Biome B (background), 1 = Biome A (foreground / main terrain).
    """
    tl, t, tr, r, br, b, bl, gauche = voisins
    mask = Image.new("L", (tile_size, tile_size), 255)
    draw = ImageDraw.Draw(mask)

    demi = tile_size // 2

    # If a cardinal side is empty (0), cut the border
    if not t:
        draw.rectangle([0, 0, tile_size, demi // 2], fill=0)
    if not b:
        draw.rectangle([0, tile_size - demi // 2, tile_size, tile_size], fill=0)
    if not gauche:
        draw.rectangle([0, 0, demi // 2, tile_size], fill=0)
    if not r:
        draw.rectangle([tile_size - demi // 2, 0, tile_size, tile_size], fill=0)

    # Inner / outer corners
    if not tl and t and gauche:
        draw.rectangle([0, 0, demi // 2, demi // 2], fill=0)
    if not tr and t and r:
        draw.rectangle([tile_size - demi // 2, 0, tile_size, demi // 2], fill=0)
    if not bl and b and gauche:
        draw.rectangle([0, tile_size - demi // 2, demi // 2, tile_size], fill=0)
    if not br and b and r:
        draw.rectangle([tile_size - demi // 2, tile_size - demi // 2, tile_size, tile_size], fill=0)

    # Light smoothing of the transitions
    mask_smooth = mask.filter(ImageFilter.GaussianBlur(radius=max(1, tile_size // 32)))
    return mask_smooth


# List of the 47 canonical neighbor configurations for the Godot 4 Minimal 3x3
# Format of the 8 neighbors: (TL, T, TR, R, BR, B, BL, L)
CONFIGS_47_TUILES = [
    # 0-7: Full, isolated and thin
    (1, 1, 1, 1, 1, 1, 1, 1), # 0: Full center
    (0, 0, 0, 0, 0, 0, 0, 0), # 1: Isolated islet
    (0, 1, 0, 0, 0, 1, 0, 0), # 2: Vertical line
    (0, 0, 0, 1, 0, 0, 0, 1), # 3: Horizontal line
    (0, 1, 0, 0, 0, 0, 0, 0), # 4: Top end
    (0, 0, 0, 1, 0, 0, 0, 0), # 5: Right end
    (0, 0, 0, 0, 0, 1, 0, 0), # 6: Bottom end
    (0, 0, 0, 0, 0, 0, 0, 1), # 7: Left end
    # 8-15: Simple cardinal borders
    (0, 0, 0, 1, 1, 1, 1, 1), # 8: Top border
    (1, 1, 0, 0, 0, 1, 1, 1), # 9: Right border
    (1, 1, 1, 1, 0, 0, 0, 1), # 10: Bottom border
    (0, 1, 1, 1, 1, 1, 0, 0), # 11: Left border
    (0, 0, 0, 1, 1, 1, 0, 0), # 12: Top-left outer corner
    (0, 0, 0, 0, 0, 1, 1, 1), # 13: Top-right outer corner
    (1, 1, 0, 0, 0, 0, 0, 1), # 14: Bottom-right outer corner
    (0, 1, 1, 1, 0, 0, 0, 0), # 15: Bottom-left outer corner
    # 16-23: T-junctions and crosses
    (0, 0, 0, 1, 1, 1, 1, 1),
    (1, 1, 1, 1, 0, 1, 1, 1),
    (1, 1, 1, 1, 1, 1, 0, 1),
    (1, 1, 0, 1, 1, 1, 1, 1),
    (0, 1, 1, 1, 1, 1, 1, 1),
    (1, 1, 1, 0, 0, 1, 1, 1),
    (1, 1, 1, 1, 0, 0, 1, 1),
    (1, 1, 1, 1, 1, 0, 0, 1),
    # 24-31: Inner corners (concave)
    (0, 1, 1, 1, 1, 1, 1, 1), # 24: TL inner corner
    (1, 1, 0, 1, 1, 1, 1, 1), # 25: TR inner corner
    (1, 1, 1, 1, 0, 1, 1, 1), # 26: BR inner corner
    (1, 1, 1, 1, 1, 1, 0, 1), # 27: BL inner corner
    (0, 1, 0, 1, 1, 1, 1, 1), # 28: Double inner corner top
    (1, 1, 0, 1, 0, 1, 1, 1), # 29: Double inner corner right
    (1, 1, 1, 1, 0, 1, 0, 1), # 30: Double inner corner bottom
    (0, 1, 1, 1, 1, 1, 0, 1), # 31: Double inner corner left
    # 32-39: Diagonals and complex combinations
    (0, 1, 0, 1, 0, 1, 1, 1),
    (1, 1, 0, 1, 0, 1, 0, 1),
    (0, 1, 1, 1, 0, 1, 0, 1),
    (0, 1, 0, 1, 1, 1, 0, 1),
    (0, 1, 0, 1, 0, 1, 0, 1),
    (1, 0, 1, 1, 1, 1, 1, 1),
    (1, 1, 1, 1, 1, 0, 1, 1),
    (1, 1, 1, 0, 1, 1, 1, 1),
    # 40-46: Corner fills
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
    """Composes the 47-tile atlas board with clean transitions between the two biomes."""
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

        # Background = Biome B, Foreground = masked Biome A
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
    """Generates the Godot 4 TileSet resource (.tres) with the minimal 3x3 TerrainSet and peering bits configured."""
    chemin_tres = os.path.join(output_dir, f"{nom_base}_tileset.tres")

    # Godot 4 peering bits mapping:
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

        bits_str = ["0:0/0/terrain_set = 0", "0:0/0/terrain = 0"]
        for p_idx, p_name in enumerate(peering_names):
            if voisins[p_idx] == 1:
                bits_str.append(f"0:0/0/terrains_peering_bit/{p_name} = 0")

        # Tile configuration in the TileSetAtlasSource source
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
