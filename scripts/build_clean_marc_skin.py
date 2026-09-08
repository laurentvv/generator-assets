#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Création et Restauration du Skin Propre Officiel de Marc pour MakeHuman / MPFB2.
Génère une texture de peau sans couture, homogène et anatomiquement parfaite,
avec la colorimétrie canonique de Vent-Gris (teint diaphane/pâle d'hiver, sous-ton froid).
"""

import os
import sys

racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if racine not in sys.path:
    sys.path.insert(0, racine)

from PIL import Image, ImageEnhance, ImageOps
import numpy as np

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

SKIN_BASE_ORIGINALE = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\young_caucasian_male\young_lightskinned_male_diffuse.png"

DOSSIER_MPFB = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\marc_novice"
DOSSIER_LOCAL = r"C:\GIT\generator-assets\godot_assets\skins\marc_novice"
DOSSIER_POC = r"C:\test\L'HERITIER DU VIDE\poc_3d\exports"

DIFFUSE_MPFB = os.path.join(DOSSIER_MPFB, "marc_novice_diffuse.png")
NORMAL_MPFB = os.path.join(DOSSIER_MPFB, "marc_novice_normal.png")
MHMAT_MPFB = os.path.join(DOSSIER_MPFB, "marc_novice.mhmat")
THUMB_MPFB = os.path.join(DOSSIER_MPFB, "marc_novice.thumb")

DIFFUSE_LOCAL = os.path.join(DOSSIER_LOCAL, "marc_novice_diffuse.png")
NORMAL_LOCAL = os.path.join(DOSSIER_LOCAL, "marc_novice_normal.png")
MHMAT_LOCAL = os.path.join(DOSSIER_LOCAL, "marc_novice.mhmat")
THUMB_LOCAL = os.path.join(DOSSIER_LOCAL, "marc_novice.thumb")

DIFFUSE_POC = os.path.join(DOSSIER_POC, "marc_mpfb2_young_lightskinned_male_diffuse.png")


def main():
    print("=" * 65)
    print(" 🎨 RESTAURATION DE LA PEAU OFFICIELLE DE MARC (VENT-GRIS) ")
    print("=" * 65)

    if not os.path.exists(SKIN_BASE_ORIGINALE):
        raise FileNotFoundError(f"Texture originale MakeHuman introuvable : {SKIN_BASE_ORIGINALE}")

    print(f"📖 Chargement du gabarit UV original MakeHuman : {SKIN_BASE_ORIGINALE}")
    base_img = Image.open(SKIN_BASE_ORIGINALE).convert("RGB")

    # Colorimétrie Marc (Vent-Gris : enfant 8 ans, hiver, forteresse froide) :
    # - Pâleur douce (luminosité légèrement augmentée)
    # - Saturation ajustée (teint diaphane)
    # - Sous-ton froid subtil
    enh_bright = ImageEnhance.Brightness(base_img)
    img_bright = enh_bright.enhance(1.04)

    enh_color = ImageEnhance.Color(img_bright)
    img_desat = enh_color.enhance(0.92)

    # Teinte légèrement plus froide
    arr = np.array(img_desat, dtype=np.float32)
    arr[:, :, 0] *= 0.99  # Rouge très légèrement adouci
    arr[:, :, 2] = np.clip(arr[:, :, 2] * 1.02, 0, 255)  # Bleu subtilement rehaussé (froid)
    skin_marc = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    # 1. Sauvegarde Diffuse
    for d in [DOSSIER_MPFB, DOSSIER_LOCAL]:
        os.makedirs(d, exist_ok=True)

    skin_marc.save(DIFFUSE_MPFB, "PNG", optimize=True)
    skin_marc.save(DIFFUSE_LOCAL, "PNG", optimize=True)
    if os.path.exists(DOSSIER_POC):
        skin_marc.save(DIFFUSE_POC, "PNG", optimize=True)
    print(f"✅ Texture Diffuse propre exportée : {DIFFUSE_MPFB}")

    # 2. Génération de la Normal Map PBR (Micro-relief des pores)
    from core.image_ops import generer_normal_map
    print("🧊 Génération de la Normal Map PBR...")
    norm_img = generer_normal_map(skin_marc, strength=2.0)
    norm_img.save(NORMAL_MPFB, "PNG")
    norm_img.save(NORMAL_LOCAL, "PNG")
    print(f"✅ Normal Map exportée : {NORMAL_MPFB}")

    # 3. Vignette .thumb propre pour MPFB
    w, h = skin_marc.size
    thumb_crop = skin_marc.crop((int(w * 0.35), int(h * 0.15), int(w * 0.65), int(h * 0.45)))
    thumb_img = thumb_crop.resize((256, 256), Image.Resampling.LANCZOS).convert("RGBA")
    thumb_img.save(THUMB_MPFB, "PNG")
    thumb_img.save(THUMB_LOCAL, "PNG")
    print(f"✅ Vignette .thumb exportée : {THUMB_MPFB}")

    # 4. Fichier Matériau .mhmat MakeHuman
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
alphaToCoverage False
backfaceCull True
depthless False
castShadows True
receiveShadows True

diffuseTexture marc_novice_diffuse.png
normalmapTexture marc_novice_normal.png
sssEnabled True
sssRScale 4.8
sssGScale 2.1
sssBScale 0.85

shader data/shaders/glsl/litsphere
shaderParam litsphereTexture data/litspheres/lit_standard_skin.png

shaderConfig ambientOcclusion True
shaderConfig normal True
shaderConfig bump True
shaderConfig displacement False
shaderConfig vertexColors True
shaderConfig spec True
shaderConfig transparency False
shaderConfig diffuse True
"""
    with open(MHMAT_MPFB, "w", encoding="utf-8") as f:
        f.write(mhmat_content)
    with open(MHMAT_LOCAL, "w", encoding="utf-8") as f:
        f.write(mhmat_content)
    print(f"✅ Matériau .mhmat exporté : {MHMAT_MPFB}")

    print("\n" + "=" * 65)
    print(" 🎉 PEAU ET MATÉRIAU OFFICIELS RESTAURÉS AVEC SUCCÈS ! ")
    print("=" * 65)


if __name__ == "__main__":
    main()
