#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module de gestion et rendu des squelettes de pose ControlNet (OpenPose / DWPose).
Gère la topologie 18 points COCO, les presets de postures de jeux vidéo,
le rendu du squelette de guidage et l'exportation des points d'ancrage Godot (Marker2D).
"""

import json
import math
import os
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from PIL import Image, ImageDraw

# Définition des 18 points COCO OpenPose (0-indexed)
KEYPOINTS_COCO = [
    "nose",         # 0
    "neck",         # 1
    "r_shoulder",   # 2
    "r_elbow",      # 3
    "r_wrist",      # 4
    "l_shoulder",   # 5
    "l_elbow",      # 6
    "l_wrist",      # 7
    "r_hip",        # 8
    "r_knee",       # 9
    "r_ankle",      # 10
    "l_hip",        # 11
    "l_knee",       # 12
    "l_ankle",      # 13
    "r_eye",        # 14
    "l_eye",        # 15
    "r_ear",        # 16
    "l_ear"         # 17
]

# Paires d'os (connexions entre points)
LIMB_PAIRS = [
    ("neck", "nose"),
    ("neck", "r_shoulder"),
    ("r_shoulder", "r_elbow"),
    ("r_elbow", "r_wrist"),
    ("neck", "l_shoulder"),
    ("l_shoulder", "l_elbow"),
    ("l_elbow", "l_wrist"),
    ("neck", "r_hip"),
    ("r_hip", "r_knee"),
    ("r_knee", "r_ankle"),
    ("neck", "l_hip"),
    ("l_hip", "l_knee"),
    ("l_knee", "l_ankle"),
    ("nose", "r_eye"),
    ("r_eye", "r_ear"),
    ("nose", "l_eye"),
    ("l_eye", "l_ear")
]

# Couleurs standard OpenPose (RGB)
COLORS = [
    (255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0),
    (170, 255, 0), (85, 255, 0), (0, 255, 0), (0, 255, 85),
    (0, 255, 170), (0, 255, 255), (0, 170, 255), (0, 85, 255),
    (0, 0, 255), (85, 0, 255), (170, 0, 255), (255, 0, 255),
    (255, 0, 170), (255, 0, 85)
]

# Presets de poses canoniques pour les sprites de jeu (coordonnées normalisées [0.0 - 1.0])
POSE_PRESETS: Dict[str, Dict[str, Tuple[float, float]]] = {
    "idle": {
        "nose": (0.50, 0.20), "neck": (0.50, 0.27),
        "r_shoulder": (0.43, 0.29), "r_elbow": (0.40, 0.44), "r_wrist": (0.42, 0.58),
        "l_shoulder": (0.57, 0.29), "l_elbow": (0.60, 0.44), "l_wrist": (0.58, 0.58),
        "r_hip": (0.45, 0.56), "r_knee": (0.44, 0.73), "r_ankle": (0.43, 0.90),
        "l_hip": (0.55, 0.56), "l_knee": (0.56, 0.73), "l_ankle": (0.57, 0.90),
        "r_eye": (0.48, 0.18), "l_eye": (0.52, 0.18),
        "r_ear": (0.45, 0.19), "l_ear": (0.55, 0.19)
    },
    "slash_attack": {
        "nose": (0.52, 0.22), "neck": (0.50, 0.28),
        "r_shoulder": (0.42, 0.30), "r_elbow": (0.30, 0.22), "r_wrist": (0.20, 0.15),  # Bras armé levé
        "l_shoulder": (0.58, 0.28), "l_elbow": (0.68, 0.38), "l_wrist": (0.75, 0.45),
        "r_hip": (0.46, 0.55), "r_knee": (0.38, 0.72), "r_ankle": (0.32, 0.88),       # Fente avant
        "l_hip": (0.56, 0.56), "l_knee": (0.65, 0.74), "l_ankle": (0.74, 0.89),
        "r_eye": (0.50, 0.20), "l_eye": (0.54, 0.20),
        "r_ear": (0.47, 0.21), "l_ear": (0.56, 0.21)
    },
    "cast_spell": {
        "nose": (0.50, 0.19), "neck": (0.50, 0.26),
        "r_shoulder": (0.42, 0.28), "r_elbow": (0.32, 0.20), "r_wrist": (0.28, 0.10),  # Bras levés en l'air
        "l_shoulder": (0.58, 0.28), "l_elbow": (0.68, 0.20), "l_wrist": (0.72, 0.10),
        "r_hip": (0.45, 0.55), "r_knee": (0.42, 0.72), "r_ankle": (0.40, 0.88),
        "l_hip": (0.55, 0.55), "l_knee": (0.58, 0.72), "l_ankle": (0.60, 0.88),
        "r_eye": (0.48, 0.17), "l_eye": (0.52, 0.17),
        "r_ear": (0.45, 0.18), "l_ear": (0.55, 0.18)
    },
    "shield_block": {
        "nose": (0.50, 0.23), "neck": (0.50, 0.29),
        "r_shoulder": (0.42, 0.31), "r_elbow": (0.38, 0.45), "r_wrist": (0.39, 0.55),
        "l_shoulder": (0.57, 0.30), "l_elbow": (0.52, 0.38), "l_wrist": (0.46, 0.34),  # Bouclier devant le torse
        "r_hip": (0.44, 0.57), "r_knee": (0.40, 0.75), "r_ankle": (0.38, 0.90),
        "l_hip": (0.54, 0.57), "l_knee": (0.56, 0.74), "l_ankle": (0.58, 0.89),
        "r_eye": (0.48, 0.21), "l_eye": (0.52, 0.21),
        "r_ear": (0.46, 0.22), "l_ear": (0.54, 0.22)
    },
    "jump": {
        "nose": (0.50, 0.15), "neck": (0.50, 0.22),
        "r_shoulder": (0.42, 0.24), "r_elbow": (0.32, 0.20), "r_wrist": (0.25, 0.18),
        "l_shoulder": (0.58, 0.24), "l_elbow": (0.68, 0.20), "l_wrist": (0.75, 0.18),
        "r_hip": (0.45, 0.50), "r_knee": (0.38, 0.62), "r_ankle": (0.42, 0.72),       # Jambes repliées
        "l_hip": (0.55, 0.50), "l_knee": (0.62, 0.62), "l_ankle": (0.58, 0.72),
        "r_eye": (0.48, 0.13), "l_eye": (0.52, 0.13),
        "r_ear": (0.45, 0.14), "l_ear": (0.55, 0.14)
    },
    "walk": {
        "nose": (0.50, 0.20), "neck": (0.50, 0.27),
        "r_shoulder": (0.44, 0.29), "r_elbow": (0.40, 0.42), "r_wrist": (0.36, 0.54),
        "l_shoulder": (0.56, 0.29), "l_elbow": (0.62, 0.42), "l_wrist": (0.68, 0.52),
        "r_hip": (0.46, 0.55), "r_knee": (0.40, 0.72), "r_ankle": (0.34, 0.88),       # Pas en avant
        "l_hip": (0.54, 0.55), "l_knee": (0.59, 0.72), "l_ankle": (0.66, 0.87),
        "r_eye": (0.48, 0.18), "l_eye": (0.52, 0.18),
        "r_ear": (0.46, 0.19), "l_ear": (0.54, 0.19)
    }
}


def obtenir_pose(nom_pose: str) -> Dict[str, Tuple[float, float]]:
    """Récupère les points normalisés d'une pose prédéfinie."""
    nom = nom_pose.lower().strip()
    return POSE_PRESETS.get(nom, POSE_PRESETS["idle"])


def dessiner_squelette_openpose(
    points: Dict[str, Tuple[float, float]],
    largeur: int = 512,
    hauteur: int = 512,
    epaisseur_os: int = 4,
    rayon_joint: int = 4
) -> Image.Image:
    """Génère la carte OpenPose RGB standard prête pour ControlNet."""
    canvas = Image.new("RGB", (largeur, hauteur), (0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    # Conversion en pixels réels
    pts_px = {k: (int(v[0] * largeur), int(v[1] * hauteur)) for k, v in points.items()}

    # Dessin des membres (os)
    for idx, (k1, k2) in enumerate(LIMB_PAIRS):
        if k1 in pts_px and k2 in pts_px:
            p1, p2 = pts_px[k1], pts_px[k2]
            couleur = COLORS[idx % len(COLORS)]
            draw.line([p1, p2], fill=couleur, width=epaisseur_os)

    # Dessin des articulations (joints)
    for idx, (k, pt) in enumerate(pts_px.items()):
        couleur = COLORS[idx % len(COLORS)]
        draw.ellipse([pt[0] - rayon_joint, pt[1] - rayon_joint, pt[0] + rayon_joint, pt[1] + rayon_joint], fill=couleur)

    return canvas


def extraire_points_ancrage_godot(
    points: Dict[str, Tuple[float, float]],
    largeur: int = 512,
    hauteur: int = 512
) -> Dict[str, Dict[str, float]]:
    """
    Extrait les points d'attachement clés relatifs au centre du sprite (Godot Marker2D).
    (0,0 = centre du sprite, X positif à droite, Y positif en bas).
    """
    cx, cy = largeur / 2.0, hauteur / 2.0
    ancrages = {}

    noms_godot = {
        "r_wrist": "RightHandMarker",
        "l_wrist": "LeftHandMarker",
        "nose": "HeadMarker",
        "neck": "ChestMarker",
        "r_ankle": "RightFootMarker",
        "l_ankle": "LeftFootMarker"
    }

    for k, nom_node in noms_godot.items():
        if k in points:
            px, py = points[k][0] * largeur, points[k][1] * hauteur
            ancrages[nom_node] = {
                "x": round(px - cx, 1),
                "y": round(py - cy, 1)
            }

    return ancrages


def exporter_scene_pose_godot(
    nom_base: str,
    output_dir: str,
    ancrages: Dict[str, Dict[str, float]],
    chemin_rel_texture: str
) -> str:
    """Génère une scène Godot 4 (.tscn) avec le Sprite2D et tous les Marker2D d'armature."""
    os.makedirs(output_dir, exist_ok=True)
    chemin_tscn = os.path.join(output_dir, f"{nom_base}_character.tscn")

    code_markers = ""
    for idx, (nom_marker, pos) in enumerate(ancrages.items(), 2):
        code_markers += f"""
[node name="{nom_marker}" type="Marker2D" parent="."]
position = Vector2({pos['x']}, {pos['y']})
"""

    code_tscn = f"""[gd_scene load_steps=2 format=3]

[ext_resource type="Texture2D" path="{chemin_rel_texture}" id="1_tex"]

[node name="{nom_base}" type="Node2D"]

[node name="Sprite2D" type="Sprite2D" parent="."]
texture = ExtResource("1_tex")
{code_markers}
"""
    with open(chemin_tscn, "w", encoding="utf-8") as f:
        f.write(code_tscn)

    return chemin_tscn
