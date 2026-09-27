# -*- coding: utf-8 -*-
"""
project_marc_portrait_to_uv.py
High-fidelity projection and blending of Marc's 2D portrait (scars, dark circles, grime, gaze)
directly onto the official MakeHuman / MPFB2 UV map.
"""

import os
import sys
from PIL import Image, ImageFilter
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
    print(" 🎨 HIGH-FIDELITY PROJECTION: 2D PORTRAIT -> MAKEHUMAN TEXTURE")
    print("=" * 65)

    base_skin = Image.open(BASE_SKIN_PATH).convert("RGBA")
    w_base, h_base = base_skin.size
    print(f"MakeHuman base texture: {w_base}x{h_base}")

    portrait = Image.open(PORTRAIT_PATH).convert("RGBA")
    w_p, h_p = portrait.size
    print(f"Marc source portrait: {w_p}x{h_p}")

    # 1. Extracting Marc's face from the portrait
    # In marc_portrait.png (1024x1024):
    # Centered head: X: 220..804, Y: 130..750
    face_crop = portrait.crop((220, 130, 804, 750))  # ~584 x 620 px

    # 90° counter-clockwise rotation (Top -> Left / Front toward the MakeHuman skull, Chin to the right)
    face_rot = face_crop.rotate(90, expand=True, resample=Image.Resampling.BICUBIC)

    # 2. Dimensions and positioning on the MakeHuman head UV island
    target_w = int(w_base * 0.25)  # ~512 px sur 2048
    target_h = int(h_base * 0.25)
    face_scaled = face_rot.resize((target_w, target_h), Image.Resampling.LANCZOS)

    # 3. Soft elliptical feathered mask
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

    # 4. Global harmonization of the body skin with Marc's weathered / medieval complexion
    arr_base = np.array(base_skin, dtype=np.float32)
    # Slightly darken and desaturate the skin to remove any plastic overexposure
    arr_base[:, :, :3] *= 0.85  # Darker, realistic, contrasted complexion
    arr_base[:, :, 0] *= 0.95   # Less candy pink
    arr_base[:, :, 2] *= 1.04   # Cold winter hue
    base_harmonisee = Image.fromarray(np.clip(arr_base, 0, 255).astype(np.uint8))

    # 5. Exact positioning of the projected face on the MakeHuman head
    # The MakeHuman feature center (nose/eyes/mouth) is located at X = 0.865 * w_base, Y = 0.500 * h_base
    pos_x = int(w_base * 0.865 - target_w / 2.0)
    pos_y = int(h_base * 0.500 - target_h / 2.0)

    # Pasting with the feathered mask
    final_diffuse = base_harmonisee.copy()
    final_diffuse.paste(face_scaled, (pos_x, pos_y), mask)

    # 6. Saving the Diffuse textures
    for d in [OUT_MPFB_DIR, OUT_LOCAL_DIR]:
        os.makedirs(d, exist_ok=True)

    diff_mpfb = os.path.join(OUT_MPFB_DIR, "marc_novice_diffuse.png")
    diff_local = os.path.join(OUT_LOCAL_DIR, "marc_novice_diffuse.png")

    final_diffuse.convert("RGB").save(diff_mpfb, "PNG", optimize=True)
    final_diffuse.convert("RGB").save(diff_local, "PNG", optimize=True)
    print(f"✅ Diffuse texture with high-fidelity face saved: {diff_mpfb}")

    # 7. Generating the high-resolution Normal Map with scars & pores
    from core.image_ops import generer_normal_map
    norm_img = generer_normal_map(final_diffuse.convert("RGB"), strength=3.0)
    norm_mpfb = os.path.join(OUT_MPFB_DIR, "marc_novice_normal.png")
    norm_local = os.path.join(OUT_LOCAL_DIR, "marc_novice_normal.png")
    norm_img.save(norm_mpfb, "PNG")
    norm_img.save(norm_local, "PNG")
    print(f"✅ Normal Map with scars and micro-relief saved: {norm_mpfb}")

    # 8. Generating the MakeHuman .mhmat file
    mhmat_path = os.path.join(OUT_MPFB_DIR, "marc_novice.mhmat")
    with open(mhmat_path, "w", encoding="utf-8") as f:
        f.write("""# Material file for MakeHuman / MPFB - Marc Novice (Grey-Wind High Fidelity)
name marc_novice
tag MPFB
diffuseTexture marc_novice_diffuse.png
normalTexture marc_novice_normal.png
roughness 0.65
metallic 0.0
alphaToCoverage False
shaderConfig transparency False
""")
    print(f"✅ .mhmat file updated: {mhmat_path}")
    print("=" * 65)

if __name__ == "__main__":
    main()
