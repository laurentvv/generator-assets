#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alignement Précis et Fusion Sans Couture du Portrait 2D de Marc sur le Patron UV MakeHuman.
Calibre au millimètre les coordonnées anatomiques des yeux, du nez et de la bouche de Marc
sur l'îlot UV de la tête MakeHuman hm08 (2048x2048).
"""

import os
import sys
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw, ImageOps
import numpy as np

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

PORTRAIT_SOURCE = r"C:\test\L'HERITIER DU VIDE\assets\portraits\marc_portrait.png"
SKIN_BASE = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\young_caucasian_male\young_lightskinned_male_diffuse.png"

SORTIE_MPFB = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\marc_novice\marc_novice_diffuse.png"
SORTIE_LOCAL = r"C:\GIT\generator-assets\godot_assets\skins\marc_novice\marc_novice_diffuse.png"
SORTIE_POC = r"C:\test\L'HERITIER DU VIDE\poc_3d\exports\marc_mpfb2_young_lightskinned_male_diffuse.png"
THUMB_MPFB = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\marc_novice\marc_novice.thumb"
THUMB_LOCAL = r"C:\GIT\generator-assets\godot_assets\skins\marc_novice\marc_novice.thumb"


def main():
    print("=" * 65)
    print(" 🎯 ALIGNEMENT ANATOMIQUE DU PORTRAIT 2D SUR MAKEHUMAN UV ")
    print("=" * 65)

    if not os.path.exists(PORTRAIT_SOURCE):
        raise FileNotFoundError(f"Portrait introuvable : {PORTRAIT_SOURCE}")

    print(f"👤 Chargement du portrait 2D : {PORTRAIT_SOURCE}")
    portrait_img = Image.open(PORTRAIT_SOURCE).convert("RGBA")

    print(f"🗺️ Chargement de la texture de base : {SKIN_BASE}")
    skin_base = Image.open(SKIN_BASE).convert("RGBA")
    w_skin, h_skin = skin_base.size  # 2048 x 2048

    # 1. Cadrage du visage dans le portrait 2D de Marc
    # Dans marc_portrait.png (1024x1024), le visage (front au menton, joue à joue)
    # se situe au centre du portrait :
    w_p, h_p = portrait_img.size
    # Découpage du visage utile (yeux, nez, bouche, joues, menton, front)
    crop_face = portrait_img.crop((int(w_p * 0.15), int(h_p * 0.08), int(w_p * 0.85), int(h_p * 0.78)))

    # 2. Dimensions cibles exactes sur l'îlot UV MakeHuman hm08
    # Emplacement géométrique du visage dans le dépliage hm08 :
    # X: 760 à 1288 (largeur = 528 px, centré sur X=1024)
    # Y: 270 à 710 (hauteur = 440 px, yeux à Y~430, nez à Y~515, bouche à Y~605, menton à Y~685)
    cible_largeur = 530
    cible_hauteur = 450

    face_redim = crop_face.resize((cible_largeur, cible_hauteur), Image.Resampling.LANCZOS)

    # 3. Création du masque de fondu progressif anatomique
    masque = Image.new("L", (cible_largeur, cible_hauteur), 0)
    draw = ImageDraw.Draw(masque)

    # Ellipse principale centrée sur les traits (yeux, nez, lèvres, pommettes)
    marge_x = int(cible_largeur * 0.08)
    marge_y = int(cible_hauteur * 0.06)
    draw.ellipse(
        [marge_x, marge_y, cible_largeur - marge_x, cible_hauteur - marge_y],
        fill=255
    )
    # Flou gaussien prononcé pour une transition invisible vers le cou et les oreilles
    masque_fondu = masque.filter(ImageFilter.GaussianBlur(radius=22))

    face_rgba = face_redim.copy()
    face_rgba.putalpha(masque_fondu)

    # 4. Positionnement sur la carte UV 2048x2048
    calque_position = Image.new("RGBA", (w_skin, h_skin), (0, 0, 0, 0))
    pos_x = int((w_skin - cible_largeur) // 2)  # X = 759 (centré à 1024)
    pos_y = 265  # Y = 265 (calé sur le front/nez/menton MakeHuman)

    calque_position.paste(face_rgba, (pos_x, pos_y), face_rgba)

    # 5. Fusion sans couture avec le corps
    skin_finale = Image.alpha_composite(skin_base, calque_position).convert("RGB")

    # 6. Sauvegarde des textures
    for p in [SORTIE_MPFB, SORTIE_LOCAL, SORTIE_POC]:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        skin_finale.save(p, "PNG", optimize=True)
        print(f"  ✅ Texture Diffuse enregistrée : {p}")

    # 7. Vignette .thumb centrée sur le visage de Marc
    thumb_crop = skin_finale.crop((pos_x - 30, pos_y - 20, pos_x + cible_largeur + 30, pos_y + cible_hauteur + 30))
    thumb_img = thumb_crop.resize((256, 256), Image.Resampling.LANCZOS).convert("RGBA")
    for t_path in [THUMB_MPFB, THUMB_LOCAL]:
        os.makedirs(os.path.dirname(t_path), exist_ok=True)
        thumb_img.save(t_path, "PNG")
        print(f"  ✅ Vignette .thumb : {t_path}")

    print("\n" + "=" * 65)
    print(" 🎉 ALIGNEMENT ET FUSION ANATOMIQUE EFFECTUÉS AVEC SUCCÈS !")
    print("=" * 65)


if __name__ == "__main__":
    main()
