#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Creation and Restoration of Marc's Official Clean Skin for MakeHuman / MPFB2.
Generates a seamless, homogeneous, anatomically perfect skin texture,
with the canonical Grey-Wind color grading (diaphanous/winter-pale complexion, cold undertone).
"""

import os
import sys

racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if racine not in sys.path:
    sys.path.insert(0, racine)

from PIL import Image, ImageEnhance
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
    print(" 🎨 RESTORATION OF MARC'S OFFICIAL SKIN (GREY-WIND) ")
    print("=" * 65)

    if not os.path.exists(SKIN_BASE_ORIGINALE):
        raise FileNotFoundError(f"Original MakeHuman texture not found: {SKIN_BASE_ORIGINALE}")

    print(f"📖 Loading the original MakeHuman UV template: {SKIN_BASE_ORIGINALE}")
    base_img = Image.open(SKIN_BASE_ORIGINALE).convert("RGB")

    # Marc color grading (Grey-Wind: 8-year-old child, winter, cold fortress):
    # - Soft paleness (slightly increased brightness)
    # - Adjusted saturation (diaphanous complexion)
    # - Subtle cold undertone
    enh_bright = ImageEnhance.Brightness(base_img)
    img_bright = enh_bright.enhance(1.04)

    enh_color = ImageEnhance.Color(img_bright)
    img_desat = enh_color.enhance(0.92)

    # Slightly colder hue
    arr = np.array(img_desat, dtype=np.float32)
    arr[:, :, 0] *= 0.99  # Red very slightly softened
    arr[:, :, 2] = np.clip(arr[:, :, 2] * 1.02, 0, 255)  # Blue subtly boosted (cold)
    skin_marc = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    # 1. Diffuse save
    for d in [DOSSIER_MPFB, DOSSIER_LOCAL]:
        os.makedirs(d, exist_ok=True)

    skin_marc.save(DIFFUSE_MPFB, "PNG", optimize=True)
    skin_marc.save(DIFFUSE_LOCAL, "PNG", optimize=True)
    if os.path.exists(DOSSIER_POC):
        skin_marc.save(DIFFUSE_POC, "PNG", optimize=True)
    print(f"✅ Clean Diffuse texture exported: {DIFFUSE_MPFB}")

    # 2. PBR Normal Map generation (pore micro-relief)
    from core.image_ops import generer_normal_map
    print("🧊 Generating the PBR Normal Map...")
    norm_img = generer_normal_map(skin_marc, strength=2.0)
    norm_img.save(NORMAL_MPFB, "PNG")
    norm_img.save(NORMAL_LOCAL, "PNG")
    print(f"✅ Normal Map exported: {NORMAL_MPFB}")

    # 3. Clean .thumb thumbnail for MPFB
    w, h = skin_marc.size
    thumb_crop = skin_marc.crop((int(w * 0.35), int(h * 0.15), int(w * 0.65), int(h * 0.45)))
    thumb_img = thumb_crop.resize((256, 256), Image.Resampling.LANCZOS).convert("RGBA")
    thumb_img.save(THUMB_MPFB, "PNG")
    thumb_img.save(THUMB_LOCAL, "PNG")
    print(f"✅ .thumb thumbnail exported: {THUMB_MPFB}")

    # 4. MakeHuman .mhmat material file
    mhmat_content = """# Material file for MakeHuman / MPFB - Marc Novice (Grey-Wind)
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
    print(f"✅ .mhmat material exported: {MHMAT_MPFB}")

    print("\n" + "=" * 65)
    print(" 🎉 OFFICIAL SKIN AND MATERIAL SUCCESSFULLY RESTORED! ")
    print("=" * 65)


if __name__ == "__main__":
    main()
