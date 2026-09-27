# -*- coding: utf-8 -*-
"""
warp_face_to_exact_uv.py
Sub-pixel-exact affine alignment of Marc's portrait eyes, nose and mouth
onto the MakeHuman UV holes.
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
    print(" 🎯 RIGIDLY CALIBRATED AFFINE ALIGNMENT ON THE MAKEHUMAN UV HOLES")
    print("=" * 65)

    base_skin = Image.open(BASE_SKIN_PATH).convert("RGBA")
    w_base, h_base = base_skin.size
    print(f"MakeHuman base: {w_base}x{h_base}")

    portrait = Image.open(PORTRAIT_PATH).convert("RGBA")

    # Exact landmarks on the portrait (1024x1024):
    # Right Eye: (418, 360), Left Eye: (605, 360), Nose: (512, 460), Mouth: (512, 550)
    # Eye center on portrait: (511.5, 360.0)
    # Portrait interpupillary distance = 187.0 px

    # MakeHuman target landmarks on the 2048x2048 texture:
    # Right Eye: (1710.1, 1144.0), Left Eye: (1710.1, 973.0), Nose: (1743.3, 1074.0)
    # MakeHuman eye center: (1710.1, 1058.5)
    # MakeHuman interpupillary distance = 171.0 px

    # Ideal scale = 171.0 / 187.0 = 0.914438
    scale = 171.0 / 187.0

    # 1. 90° rotation of the portrait
    # In the rotated frame:
    # - Left Eye becomes on top
    # - Right Eye becomes at the bottom
    rot_portrait = portrait.rotate(90, expand=True, resample=Image.Resampling.BICUBIC)

    # 2. Global resize at MakeHuman scale
    w_rot, h_rot = rot_portrait.size
    scaled_w = int(w_rot * scale)
    scaled_h = int(h_rot * scale)
    scaled_portrait = rot_portrait.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)

    # Eye-center position in the rotated and scaled image:
    # In the original portrait: (511.5, 360.0)
    # After 90° rotate (center 512, 512): X' = 360, Y' = 1024 - 511.5 = 512.5
    # After scale: X_eye = 360 * scale = 329.2 px, Y_eye = 512.5 * scale = 468.6 px
    eye_in_scaled_x = 360.0 * scale
    eye_in_scaled_y = 512.5 * scale

    # Paste position so the eye center lands EXACTLY at (1710.1, 1058.5):
    paste_x = int(round(1710.1 - eye_in_scaled_x))
    paste_y = int(round(1058.5 - eye_in_scaled_y))

    print(f"Alignment: paste_x = {paste_x}, paste_y = {paste_y}, scale = {scale:.4f}")

    # 3. Surgical feathered mask (face only: nose, eyes, mouth, scars)
    mask = Image.new("L", (scaled_w, scaled_h), 0)
    arr_mask = np.zeros((scaled_h, scaled_w), dtype=np.float32)

    # Mask center on the nose / middle of the face
    # Nose in the scaled frame: (460 * scale, 512 * scale) = (420.6, 468.2)
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

    # 4. Face blend onto the base skin (ENTIRE BODY STRICTLY UNTOUCHED)
    final_diffuse = base_skin.copy()
    final_diffuse.paste(scaled_portrait, (paste_x, paste_y), mask)

    # 5. Saving the textures
    for d in [OUT_MPFB_DIR, OUT_LOCAL_DIR]:
        os.makedirs(d, exist_ok=True)

    diff_mpfb = os.path.join(OUT_MPFB_DIR, "marc_novice_diffuse.png")
    diff_local = os.path.join(OUT_LOCAL_DIR, "marc_novice_diffuse.png")
    final_diffuse.convert("RGB").save(diff_mpfb, "PNG", optimize=True)
    final_diffuse.convert("RGB").save(diff_local, "PNG", optimize=True)
    print(f"✅ Surgical Diffuse texture saved: {diff_mpfb}")

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
    print(f"✅ Normal Map saved: {norm_mpfb}")

    # .mhmat file
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
    print(f"✅ .mhmat file saved: {mhmat_path}")
    print("=" * 65)

if __name__ == "__main__":
    main()
