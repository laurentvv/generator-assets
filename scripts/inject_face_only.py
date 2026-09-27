# -*- coding: utf-8 -*-
"""
inject_face_only.py
Injects ONLY the facial features (scars, eye bags, gaze, nose, mouth)
from Marc's portrait onto the original MakeHuman skin texture,
WITHOUT TOUCHING any other part of the body or the texture.
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
    print(" 🎯 FACE-ONLY INJECTION (ORIGINAL BODY 100% PRESERVED)")
    print("=" * 65)

    # 1. Load the original MakeHuman texture (100% intact)
    base_skin = Image.open(BASE_SKIN_PATH).convert("RGBA")
    w_base, h_base = base_skin.size
    print(f"Original MakeHuman texture: {w_base}x{h_base}")

    # 2. Load Marc's portrait
    portrait = Image.open(PORTRAIT_PATH).convert("RGBA")

    # 3. Surgical crop of the face (forehead, eyebrows with scar, eyes with eye bags, nose, mouth, cheeks)
    # Dans marc_portrait.png (1024x1024) :
    face_crop = portrait.crop((230, 160, 794, 720))  # 564 x 560 px

    # 90° counter-clockwise rotation to match the MakeHuman UV orientation
    face_rot = face_crop.rotate(90, expand=True, resample=Image.Resampling.BICUBIC)

    # Precise resizing to match the MakeHuman facial scale
    target_w = 460
    target_h = 460
    face_scaled = face_rot.resize((target_w, target_h), Image.Resampling.LANCZOS)

    # 4. Soft feathering mask to blend only the face
    mask = Image.new("L", (target_w, target_h), 0)
    arr_mask = np.zeros((target_h, target_w), dtype=np.float32)
    cx, cy = target_w / 2.0, target_h / 2.0
    rx, ry = target_w * 0.42, target_h * 0.40

    for y in range(target_h):
        for x in range(target_w):
            d = np.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2)
            if d < 0.55:
                arr_mask[y, x] = 255.0
            elif d < 1.0:
                f = (1.0 - np.cos((1.0 - d) / 0.45 * np.pi)) / 2.0
                arr_mask[y, x] = f * 255.0
            else:
                arr_mask[y, x] = 0.0

    mask = Image.fromarray(arr_mask.astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius=8))

    # 5. Exact positioning of the face on the MakeHuman facial coordinates
    # MakeHuman eyes/nose center on the 2048x2048 texture: X=1770, Y=1024
    pos_x = int(1770 - target_w / 2.0)
    pos_y = int(1024 - target_h / 2.0)

    # Pasting the face onto the original skin (NOTHING ELSE IS TOUCHED)
    final_diffuse = base_skin.copy()
    final_diffuse.paste(face_scaled, (pos_x, pos_y), mask)

    # 6. Saving the files
    for d in [OUT_MPFB_DIR, OUT_LOCAL_DIR]:
        os.makedirs(d, exist_ok=True)

    diff_mpfb = os.path.join(OUT_MPFB_DIR, "marc_novice_diffuse.png")
    diff_local = os.path.join(OUT_LOCAL_DIR, "marc_novice_diffuse.png")

    final_diffuse.convert("RGB").save(diff_mpfb, "PNG", optimize=True)
    final_diffuse.convert("RGB").save(diff_local, "PNG", optimize=True)
    print(f"✅ Diffuse texture (face only) saved: {diff_mpfb}")

    # 7. Normal map
    from core.image_ops import generer_normal_map
    norm_img = generer_normal_map(final_diffuse.convert("RGB"), strength=2.5)
    norm_mpfb = os.path.join(OUT_MPFB_DIR, "marc_novice_normal.png")
    norm_local = os.path.join(OUT_LOCAL_DIR, "marc_novice_normal.png")
    norm_img.save(norm_mpfb, "PNG")
    norm_img.save(norm_local, "PNG")
    print(f"✅ Normal Map saved: {norm_mpfb}")

    # 8. .mhmat file
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
