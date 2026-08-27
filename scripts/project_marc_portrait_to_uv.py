# -*- coding: utf-8 -*-
"""
project_marc_portrait_to_uv.py
Projection et fusion haute fidélité du portrait 2D de Marc (cicatrices, cernes, crasse, regard)
directement sur la carte UV officielle MakeHuman / MPFB2.
"""

import os
import sys
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import numpy as np

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RACINE not in sys.path:
    sys.path.insert(0, RACINE)

PORTRAIT_PATH = r"C:\test\L'HERITIER DU VIDE\assets\portraits\marc_portrait.png"
BASE_SKIN_PATH = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\young_caucasian_male\young_lightskinned_male_diffuse.png"

OUT_MPFB_DIR = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\marc_novice"
OUT_LOCAL_DIR = r"C:\GIT\generator-assets\godot_assets\skins\marc_novice"

def main():
    print("=" * 65)
    print(" 🎨 PROJECTION HAUTE FIDÉLITÉ : PORTRAIT 2D -> TEXTURE MAKEHUMAN")
    print("=" * 65)

    base_skin = Image.open(BASE_SKIN_PATH).convert("RGBA")
    w_base, h_base = base_skin.size
    print(f"Texture de base MakeHuman : {w_base}x{h_base}")

    portrait = Image.open(PORTRAIT_PATH).convert("RGBA")
    w_p, h_p = portrait.size
    print(f"Portrait source Marc : {w_p}x{h_p}")

    # 1. Extraction du visage de Marc depuis le portrait
    # Dans marc_portrait.png (1024x1024) :
    # Tête centrée : X: 220..804, Y: 130..750
    face_crop = portrait.crop((220, 130, 804, 750))  # ~584 x 620 px
    
    # Rotation 90° anti-horaire (Top -> Left / Front vers le crâne MakeHuman, Menton vers la droite)
    face_rot = face_crop.rotate(90, expand=True, resample=Image.Resampling.BICUBIC)

    # 2. Dimensions et positionnement sur l'île UV de la tête MakeHuman
    target_w = int(w_base * 0.25)  # ~512 px sur 2048
    target_h = int(h_base * 0.25)
    face_scaled = face_rot.resize((target_w, target_h), Image.Resampling.LANCZOS)

    # 3. Masque d'estompage elliptique doux
    mask = Image.new("L", (target_w, target_h), 0)
    arr_mask = np.zeros((target_h, target_w), dtype=np.float32)
    cx, cy = target_w / 2.0, target_h / 2.0
    rx, ry = target_w * 0.44, target_h * 0.42
    
    for y in range(target_h):
        for x in range(target_w):
            d = np.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2)
            if d < 0.60:
                arr_mask[y, x] = 255.0
            elif d < 1.0:
                f = (1.0 - np.cos((1.0 - d) / 0.40 * np.pi)) / 2.0
                arr_mask[y, x] = f * 255.0
            else:
                arr_mask[y, x] = 0.0

    mask = Image.fromarray(arr_mask.astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius=6))

    # 4. Harmonisation globale de la peau du corps avec le teint patiné / médiéval de Marc
    arr_base = np.array(base_skin, dtype=np.float32)
    # Assombrir et désaturer légèrement la peau pour éliminer toute surexposition plastique
    arr_base[:, :, :3] *= 0.85  # Teint plus sombre, réaliste et contrasté
    arr_base[:, :, 0] *= 0.95   # Moins rose bonbon
    arr_base[:, :, 2] *= 1.04   # Teinte froide d'hiver
    base_harmonisee = Image.fromarray(np.clip(arr_base, 0, 255).astype(np.uint8))

    # 5. Positionnement exact du visage projeté sur la tête MakeHuman
    # Le centre des traits (nez/yeux/bouche) MakeHuman est situé à X = 0.865 * w_base, Y = 0.500 * h_base
    pos_x = int(w_base * 0.865 - target_w / 2.0)
    pos_y = int(h_base * 0.500 - target_h / 2.0)

    # Collage avec le masque d'estompage
    final_diffuse = base_harmonisee.copy()
    final_diffuse.paste(face_scaled, (pos_x, pos_y), mask)

    # 6. Sauvegarde des textures Diffuse
    for d in [OUT_MPFB_DIR, OUT_LOCAL_DIR]:
        os.makedirs(d, exist_ok=True)

    diff_mpfb = os.path.join(OUT_MPFB_DIR, "marc_novice_diffuse.png")
    diff_local = os.path.join(OUT_LOCAL_DIR, "marc_novice_diffuse.png")
    
    final_diffuse.convert("RGB").save(diff_mpfb, "PNG", optimize=True)
    final_diffuse.convert("RGB").save(diff_local, "PNG", optimize=True)
    print(f"✅ Texture Diffuse avec visage haute fidélité enregistrée : {diff_mpfb}")

    # 7. Génération de la Normal Map haute résolution avec cicatrices & pores
    from core.image_ops import generer_normal_map
    norm_img = generer_normal_map(final_diffuse.convert("RGB"), strength=3.0)
    norm_mpfb = os.path.join(OUT_MPFB_DIR, "marc_novice_normal.png")
    norm_local = os.path.join(OUT_LOCAL_DIR, "marc_novice_normal.png")
    norm_img.save(norm_mpfb, "PNG")
    norm_img.save(norm_local, "PNG")
    print(f"✅ Normal Map avec cicatrices et micro-relief enregistrée : {norm_mpfb}")

    # 8. Génération du fichier .mhmat MakeHuman
    mhmat_path = os.path.join(OUT_MPFB_DIR, "marc_novice.mhmat")
    with open(mhmat_path, "w", encoding="utf-8") as f:
        f.write(f"""# Material file for MakeHuman / MPFB - Marc Novice (Vent-Gris Haute Fidélité)
name marc_novice
tag MPFB
diffuseTexture marc_novice_diffuse.png
normalTexture marc_novice_normal.png
roughness 0.65
metallic 0.0
alphaToCoverage False
shaderConfig transparency False
""")
    print(f"✅ Fichier .mhmat mis à jour : {mhmat_path}")
    print("=" * 65)

if __name__ == "__main__":
    main()
