# -*- coding: utf-8 -*-
"""
blend_portrait_details_clean.py
High-fidelity detail transfer through soft embedding (Luminance Overlay / Soft Light):
1. Preserves 100% of the natural, even skin tone of the MakeHuman skin.
2. Embeds Marc's scars, grain, gaze and features without any dark mask or blotch.
3. Photorealistic, clean and perfectly integrated result in 3D.
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
    print(" 🎨 DETAIL TRANSFER AND NATURAL HARMONIZATION OF THE FACE")
    print("=" * 65)

    base_skin = Image.open(BASE_SKIN_PATH).convert("RGBA")
    w_base, h_base = base_skin.size

    portrait = Image.open(PORTRAIT_PATH).convert("RGBA")

    # 1. Rigid calibration on the MakeHuman UV holes
    scale = 171.0 / 187.0
    rot_portrait = portrait.rotate(90, expand=True, resample=Image.Resampling.BICUBIC)

    w_rot, h_rot = rot_portrait.size
    scaled_w = int(w_rot * scale)
    scaled_h = int(h_rot * scale)
    scaled_portrait = rot_portrait.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)

    eye_in_scaled_x = 360.0 * scale
    eye_in_scaled_y = 512.5 * scale
    paste_x = int(round(1710.1 - eye_in_scaled_x))
    paste_y = int(round(1058.5 - eye_in_scaled_y))

    # 2. Cropping of the underlying MakeHuman area
    mh_face_area = base_skin.crop((paste_x, paste_y, paste_x + scaled_w, paste_y + scaled_h))

    # 3. "Soft Light" / Luminance blending to inject scars and features without darkening
    # Conversion to numpy float [0..1]
    mh_arr = np.array(mh_face_area, dtype=np.float32)[:, :, :3] / 255.0
    port_arr = np.array(scaled_portrait, dtype=np.float32)[:, :, :3] / 255.0

    # Portrait luminance normalization to match the MakeHuman skin
    mean_mh = np.mean(mh_arr)
    mean_port = np.mean(port_arr)
    port_normalized = np.clip(port_arr * (mean_mh / (mean_port + 1e-5)), 0.0, 1.0)

    # Soft Light blend : 2 * A * B + A^2 * (1 - 2B)
    soft_light = np.where(
        port_normalized < 0.5,
        2.0 * mh_arr * port_normalized + (mh_arr ** 2.0) * (1.0 - 2.0 * port_normalized),
        2.0 * mh_arr * (1.0 - port_normalized) + np.sqrt(mh_arr) * (2.0 * port_normalized - 1.0)
    )

    # Mix 75% Soft Light + 25% direct details to keep the scars sharp
    blended_face = np.clip((soft_light * 0.70 + port_normalized * 0.30) * 255.0, 0, 255).astype(np.uint8)
    blended_face_img = Image.fromarray(blended_face).convert("RGBA")

    # 4. Ultra-soft feathering mask (extended circular feathering)
    mask = Image.new("L", (scaled_w, scaled_h), 0)
    arr_mask = np.zeros((scaled_h, scaled_w), dtype=np.float32)
    cx = 420.6
    cy = 468.2
    rx = 175.0 * scale
    ry = 165.0 * scale

    for y in range(scaled_h):
        for x in range(scaled_w):
            d = np.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2)
            if d < 0.35:
                arr_mask[y, x] = 255.0
            elif d < 1.0:
                f = (1.0 - np.cos((1.0 - d) / 0.65 * np.pi)) / 2.0
                arr_mask[y, x] = f * 255.0
            else:
                arr_mask[y, x] = 0.0

    mask = Image.fromarray(arr_mask.astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius=10))

    # 5. Final paste onto the MakeHuman skin texture
    final_diffuse = base_skin.copy()
    final_diffuse.paste(blended_face_img, (paste_x, paste_y), mask)

    # 6. Saving the textures
    for d in [OUT_MPFB_DIR, OUT_LOCAL_DIR]:
        os.makedirs(d, exist_ok=True)

    diff_mpfb = os.path.join(OUT_MPFB_DIR, "marc_novice_diffuse.png")
    diff_local = os.path.join(OUT_LOCAL_DIR, "marc_novice_diffuse.png")
    final_diffuse.convert("RGB").save(diff_mpfb, "PNG", optimize=True)
    final_diffuse.convert("RGB").save(diff_local, "PNG", optimize=True)
    print(f"✅ Perfectly harmonized diffuse texture: {diff_mpfb}")

    # Normal Map
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if racine not in sys.path:
        sys.path.insert(0, racine)
    from core.image_ops import generer_normal_map
    norm_img = generer_normal_map(final_diffuse.convert("RGB"), strength=2.0)
    norm_mpfb = os.path.join(OUT_MPFB_DIR, "marc_novice_normal.png")
    norm_local = os.path.join(OUT_LOCAL_DIR, "marc_novice_normal.png")
    norm_img.save(norm_mpfb, "PNG")
    norm_img.save(norm_local, "PNG")
    print(f"✅ Normal Map saved: {norm_mpfb}")

    # .mhmat
    mhmat_path = os.path.join(OUT_MPFB_DIR, "marc_novice.mhmat")
    with open(mhmat_path, "w", encoding="utf-8") as f:
        f.write("""# Material file for MakeHuman / MPFB - Marc Novice Harmonized
name marc_novice
tag MPFB
diffuseTexture marc_novice_diffuse.png
normalTexture marc_novice_normal.png
roughness 0.60
metallic 0.0
alphaToCoverage False
shaderConfig transparency False
""")
    print("=" * 65)

if __name__ == "__main__":
    main()
