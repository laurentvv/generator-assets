#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Générateur et Assembleur de Skin MPFB / MakeHuman pour Marc (8 ans, novice de Vent-Gris).
Génère la texture de peau UV complète (2048x2048), le fichier de matériau .mhmat,
et la vignette .thumb dans la bibliothèque officielle MPFB Blender.
"""

import os
import sys
import shutil
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw
import numpy as np

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

DOSSIER_MPFB_SKINS = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins"
SKIN_SOURCE_DEFAULT = os.path.join(DOSSIER_MPFB_SKINS, "young_caucasian_male", "young_lightskinned_male_diffuse.png")
DOSSIER_MARC_SKIN = os.path.join(DOSSIER_MPFB_SKINS, "marc_novice")


def creer_skin_marc_mpfb(
    skin_base_path: str = SKIN_SOURCE_DEFAULT,
    dossier_sortie_mpfb: str = DOSSIER_MARC_SKIN,
    dossier_projet_assets: str = "godot_assets/skins/marc_novice"
) -> dict:
    """
    Crée le pack de skin MakeHuman/MPFB complet pour Marc (8 ans).
    """
    os.makedirs(dossier_sortie_mpfb, exist_ok=True)
    os.makedirs(dossier_projet_assets, exist_ok=True)

    if not os.path.exists(skin_base_path):
        raise FileNotFoundError(f"Texture de peau source introuvable : {skin_base_path}")

    print(f"🎨 Chargement du gabarit de peau source : {skin_base_path}")
    base_img = Image.open(skin_base_path).convert("RGB")
    w, h = base_img.size  # 2048 x 2048

    # 1. Ajustement global du teint : peau plus pâle, hivernale, légèrement désaturée (Vent-Gris)
    color_enhancer = ImageEnhance.Color(base_img)
    img_pale = color_enhancer.enhance(0.88)  # Légère désaturation hivernale

    bright_enhancer = ImageEnhance.Brightness(img_pale)
    img_skin = bright_enhancer.enhance(1.03)  # Teint diaphane / pâle

    # 2. Travail spécifique sur les zones UV du visage de Marc (yeux, nez, joues, lèvres)
    # Sur la carte UV MakeHuman (2048x2048), la tête est déployée dans la partie haute (Y: 0..1024)
    calque_details = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(calque_details)

    # Coordonnées des zones faciales UV MakeHuman hm08 :
    # A. Cernes sous les yeux (hazel/brown sombre et froid)
    # B. Rougeurs dues au froid mordant sur le bout du nez et les pommettes
    # C. Traces légères de suie / sueur séchée de forteresse médiévale
    # D. Lèvres gercées légèrement décolorées

    # Rougeurs de froid sur le nez et les joues (teinte rouge-violacée douce)
    couleur_froid = (180, 75, 75, 45)
    # Zone nez & joues UV
    draw.ellipse([w * 0.44, h * 0.30, w * 0.56, h * 0.42], fill=couleur_froid)  # Nez
    draw.ellipse([w * 0.36, h * 0.32, w * 0.45, h * 0.44], fill=(175, 70, 70, 35))  # Joue gauche
    draw.ellipse([w * 0.55, h * 0.32, w * 0.64, h * 0.44], fill=(175, 70, 70, 35))  # Joue droite

    # Cernes sous les yeux (teinte bleu-gris/brun froid)
    couleur_cernes = (70, 60, 75, 40)
    draw.ellipse([w * 0.38, h * 0.26, w * 0.46, h * 0.32], fill=couleur_cernes)  # Sous œil gauche
    draw.ellipse([w * 0.54, h * 0.26, w * 0.62, h * 0.32], fill=couleur_cernes)  # Sous œil droit

    # Traces subtiles de suie / poussière de pierre (forteresse de Vent-Gris)
    couleur_suie = (45, 40, 38, 25)
    draw.ellipse([w * 0.34, h * 0.28, w * 0.42, h * 0.38], fill=couleur_suie)
    draw.ellipse([w * 0.58, h * 0.28, w * 0.66, h * 0.38], fill=couleur_suie)
    draw.ellipse([w * 0.46, h * 0.16, w * 0.54, h * 0.24], fill=(45, 40, 38, 20))  # Front

    # Floutage gaussien doux du calque pour fondre naturellement les nuances dans la texture
    calque_floute = calque_details.filter(ImageFilter.GaussianBlur(radius=18))

    # Fusion avec la peau de base
    skin_rgba = img_skin.convert("RGBA")
    skin_finale = Image.alpha_composite(skin_rgba, calque_floute).convert("RGB")

    # Chemins des fichiers de sortie
    diffuse_mpfb = os.path.join(dossier_sortie_mpfb, "marc_novice_diffuse.png")
    mhmat_mpfb = os.path.join(dossier_sortie_mpfb, "marc_novice.mhmat")
    thumb_mpfb = os.path.join(dossier_sortie_mpfb, "marc_novice.thumb")

    diffuse_local = os.path.join(dossier_projet_assets, "marc_novice_diffuse.png")
    mhmat_local = os.path.join(dossier_projet_assets, "marc_novice.mhmat")
    thumb_local = os.path.join(dossier_projet_assets, "marc_novice.thumb")

    # Sauvegarde des textures Diffuse (2048x2048)
    skin_finale.save(diffuse_mpfb, "PNG", optimize=True)
    skin_finale.save(diffuse_local, "PNG", optimize=True)
    print(f"✅ Texture Diffuse enregistrée : {diffuse_mpfb}")

    # 3. Création du fichier de matériau .mhmat (MakeHuman Material)
    mhmat_content = """# Material file for MakeHuman / MPFB - Marc Novice (Vent-Gris)
# Character: Marc (8 years old medieval novice boy)
# Project: L'HERITIER DU VIDE

name marc_novice
tag MakeHuman™
tag young
tag caucasian
tag male
tag novice
tag vent_gris

ambientColor 0.28 0.26 0.27
diffuseColor 1.0 1.0 1.0
specularColor 0.025 0.025 0.025
shininess 0.45
emissiveColor 0.15 0.08 0.08
opacity 1.0
translucency 0.0
shadeless False
wireframe False
transparent False
alphaToCoverage True
backfaceCull True
depthless False
castShadows True
receiveShadows True

diffuseTexture marc_novice_diffuse.png
sssEnabled True
sssRScale 4.8
sssGScale 2.1
sssBScale 0.85

shader data/shaders/glsl/litsphere
shaderParam litsphereTexture data/litspheres/lit_standard_skin.png

shaderConfig ambientOcclusion True
shaderConfig normal False
shaderConfig bump True
shaderConfig displacement False
shaderConfig vertexColors True
shaderConfig spec True
shaderConfig transparency True
shaderConfig diffuse True
"""
    with open(mhmat_mpfb, "w", encoding="utf-8") as f:
        f.write(mhmat_content)
    with open(mhmat_local, "w", encoding="utf-8") as f:
        f.write(mhmat_content)
    print(f"✅ Matériau .mhmat enregistré : {mhmat_mpfb}")

    # 4. Création de la vignette d'aperçu .thumb (256x256)
    # Découpage centré sur le visage de Marc pour la vignette
    face_box = (int(w * 0.32), int(h * 0.12), int(w * 0.68), int(h * 0.48))
    face_crop = skin_finale.crop(face_box)
    thumb_img = face_crop.resize((256, 256), Image.Resampling.LANCZOS).convert("RGBA")

    thumb_img.save(thumb_mpfb, "PNG")
    thumb_img.save(thumb_local, "PNG")
    print(f"✅ Vignette .thumb enregistrée : {thumb_mpfb}")

    return {
        "mpfb_dir": dossier_sortie_mpfb,
        "diffuse": diffuse_mpfb,
        "mhmat": mhmat_mpfb,
        "thumb": thumb_mpfb,
        "local_copy": dossier_projet_assets
    }


if __name__ == "__main__":
    res = creer_skin_marc_mpfb()
    print("\n🎉 Pack Skin MPFB 'marc_novice' créé avec succès !")
    for k, v in res.items():
        print(f"  • {k}: {v}")
