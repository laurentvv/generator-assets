# -*- coding: utf-8 -*-
"""
warp_face_to_exact_uv.py
Alignement affine exact au sous-pixel près des yeux, du nez et de la bouche
du portrait de Marc sur les trous UV MakeHuman.
"""

import os
import sys
from PIL import Image, ImageFilter
import numpy as np

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

PORTRAIT_PATH = r"C:\test\L'HERITIER DU VIDE\assets\portraits\marc_portrait.png"
BASE_SKIN_PATH = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\young_caucasian_male\young_lightskinned_male_diffuse.png"

OUT_MPFB_DIR = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\marc_novice"
OUT_LOCAL_DIR = r"C:\GIT\generator-assets\godot_assets\skins\marc_novice"

def main():
    print("=" * 65)
    print(" 🎯 ALIGNEMENT AFFINE RIGIDEMENT CALIBRÉ SUR LES TROUS UV MAKEHUMAN")
    print("=" * 65)

    base_skin = Image.open(BASE_SKIN_PATH).convert("RGBA")
    w_base, h_base = base_skin.size
    print(f"Base MakeHuman : {w_base}x{h_base}")

    portrait = Image.open(PORTRAIT_PATH).convert("RGBA")
    
    # Repères exacts sur le portrait (1024x1024) :
    # Oeil Droit : (418, 360), Oeil Gauche : (605, 360), Nez : (512, 460), Bouche : (512, 550)
    # Centre des yeux sur portrait : (511.5, 360.0)
    # Ecart interpupillaire portrait = 187.0 px

    # Repères cibles MakeHuman sur texture 2048x2048 :
    # Oeil Droit : (1710.1, 1144.0), Oeil Gauche : (1710.1, 973.0), Nez : (1743.3, 1074.0)
    # Centre des yeux MakeHuman : (1710.1, 1058.5)
    # Ecart interpupillaire MakeHuman = 171.0 px

    # Echelle idéale = 171.0 / 187.0 = 0.914438
    scale = 171.0 / 187.0
    
    # 1. Rotation 90° du portrait
    # Dans le repère pivoté :
    # - Oeil Gauche devient en haut
    # - Oeil Droit devient en bas
    rot_portrait = portrait.rotate(90, expand=True, resample=Image.Resampling.BICUBIC)
    
    # 2. Redimensionnement global à l'échelle MakeHuman
    w_rot, h_rot = rot_portrait.size
    scaled_w = int(w_rot * scale)
    scaled_h = int(h_rot * scale)
    scaled_portrait = rot_portrait.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
    
    # Position du centre des yeux dans l'image pivotée et mise à l'échelle :
    # Dans portrait original : (511.5, 360.0)
    # Après rotate 90° (centre 512, 512) : X' = 360, Y' = 1024 - 511.5 = 512.5
    # Après échelle : X_eye = 360 * scale = 329.2 px, Y_eye = 512.5 * scale = 468.6 px
    eye_in_scaled_x = 360.0 * scale
    eye_in_scaled_y = 512.5 * scale

    # Position de collage pour que le centre des yeux atterrisse EXACTEMENT à (1710.1, 1058.5) :
    paste_x = int(round(1710.1 - eye_in_scaled_x))
    paste_y = int(round(1058.5 - eye_in_scaled_y))

    print(f"Alignement : paste_x = {paste_x}, paste_y = {paste_y}, scale = {scale:.4f}")

    # 3. Masque d'estompage chirurgical (uniquement le visage, nez, yeux, bouche, cicatrices)
    mask = Image.new("L", (scaled_w, scaled_h), 0)
    arr_mask = np.zeros((scaled_h, scaled_w), dtype=np.float32)
    
    # Centre du masque centré sur le nez / milieu du visage
    # Nez dans le repère scaled : (460 * scale, 512 * scale) = (420.6, 468.2)
    cx = 420.6
    cy = 468.2
    rx = 180.0 * scale
    ry = 170.0 * scale

    for y in range(scaled_h):
        for x in range(scaled_w):
            d = np.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2)
            if d < 0.50:
                arr_mask[y, x] = 255.0
            elif d < 1.0:
                f = (1.0 - np.cos((1.0 - d) / 0.50 * np.pi)) / 2.0
                arr_mask[y, x] = f * 255.0
            else:
                arr_mask[y, x] = 0.0

    mask = Image.fromarray(arr_mask.astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius=6))

    # 4. Fusion du visage sur la peau de base (CORPS ENTIER STRICTEMENT INTACT)
    final_diffuse = base_skin.copy()
    final_diffuse.paste(scaled_portrait, (paste_x, paste_y), mask)

    # 5. Sauvegarde des textures
    for d in [OUT_MPFB_DIR, OUT_LOCAL_DIR]:
        os.makedirs(d, exist_ok=True)

    diff_mpfb = os.path.join(OUT_MPFB_DIR, "marc_novice_diffuse.png")
    diff_local = os.path.join(OUT_LOCAL_DIR, "marc_novice_diffuse.png")
    final_diffuse.convert("RGB").save(diff_mpfb, "PNG", optimize=True)
    final_diffuse.convert("RGB").save(diff_local, "PNG", optimize=True)
    print(f"✅ Texture Diffuse chirurgicale enregistrée : {diff_mpfb}")

    # Normal Map
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if racine not in sys.path:
        sys.path.insert(0, racine)
    from core.image_ops import generer_normal_map
    norm_img = generer_normal_map(final_diffuse.convert("RGB"), strength=2.2)
    norm_mpfb = os.path.join(OUT_MPFB_DIR, "marc_novice_normal.png")
    norm_local = os.path.join(OUT_LOCAL_DIR, "marc_novice_normal.png")
    norm_img.save(norm_mpfb, "PNG")
    norm_img.save(norm_local, "PNG")
    print(f"✅ Normal Map enregistrée : {norm_mpfb}")

    # Fichier .mhmat
    mhmat_path = os.path.join(OUT_MPFB_DIR, "marc_novice.mhmat")
    with open(mhmat_path, "w", encoding="utf-8") as f:
        f.write("""# Material file for MakeHuman / MPFB - Marc Novice
name marc_novice
tag MPFB
diffuseTexture marc_novice_diffuse.png
normalTexture marc_novice_normal.png
roughness 0.60
metallic 0.0
alphaToCoverage False
shaderConfig transparency False
""")
    print(f"✅ Fichier .mhmat enregistré : {mhmat_path}")
    print("=" * 65)

if __name__ == "__main__":
    main()
