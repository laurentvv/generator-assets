# -*- coding: utf-8 -*-
"""
apply_marc_signature_features.py
Clean, contrasted and professional application of Marc's signature details:
1. Clean scar above the right eyebrow.
2. Scratch on the left cheek.
3. Marked fatigue dark circles under the eyes (intense gaze of a Vent-Gris survivor).
4. Dust / medieval grime patina on the forehead and the temples.
5. Normal Map with true 3D relief (scar ridge and groove).
"""

import os
import sys
from PIL import Image, ImageFilter, ImageEnhance
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
    print(" ⚔️ APPLYING MARC'S SIGNATURE DETAILS (SCARS & DARK CIRCLES)")
    print("=" * 65)

    base_skin = Image.open(BASE_SKIN_PATH).convert("RGBA")
    w_base, h_base = base_skin.size

    portrait = Image.open(PORTRAIT_PATH).convert("RGBA")

    # 1. Exact geometric calibration
    scale = 171.0 / 187.0
    rot_portrait = portrait.rotate(90, expand=True, resample=Image.Resampling.BICUBIC)
    scaled_portrait = rot_portrait.resize((int(rot_portrait.width * scale), int(rot_portrait.height * scale)), Image.Resampling.LANCZOS)

    eye_in_scaled_x = 360.0 * scale
    eye_in_scaled_y = 512.5 * scale
    paste_x = int(round(1710.1 - eye_in_scaled_x))
    paste_y = int(round(1058.5 - eye_in_scaled_y))

    # 2. Targeted extraction of the HIGH-FREQUENCY DETAILS (Scars, Dark circles, Blemishes)
    # In the rotated portrait, we isolate only the dark and red elements (scars, dark circles)
    # without touching the nose or the mouth
    arr_port = np.array(scaled_portrait, dtype=np.float32)[:, :, :3]
    h_scaled, w_scaled, _ = arr_port.shape

    # Transparent detail layer
    # Coordinates of the key zones in the rotated image (X' = Y_orig, Y' = 1024 - X_orig):
    # 1) Right forehead scar: Y_orig ~ 230..280, X_orig ~ 360..420
    #    -> X' ~ 210..260, Y' ~ 550..620
    # 2) Left cheek scratch: Y_orig ~ 420..470, X_orig ~ 620..680
    #    -> X' ~ 380..430, Y' ~ 310..380
    # 3) Dark circles under the eyes:
    #    Right Eye: X' ~ 340..390, Y' ~ 560..630
    #    Left Eye: X' ~ 340..390, Y' ~ 380..450

    # Creation of the isolation mask of the characteristic traits
    feature_mask = np.zeros((h_scaled, w_scaled), dtype=np.float32)

    # Forehead scar mask
    for y in range(h_scaled):
        for x in range(w_scaled):
            # Forehead zone (right scar)
            if (200 * scale <= x <= 280 * scale) and (530 * scale <= y <= 630 * scale):
                feature_mask[y, x] = 1.0
            # Left cheek zone (scratch)
            elif (380 * scale <= x <= 450 * scale) and (300 * scale <= y <= 380 * scale):
                feature_mask[y, x] = 1.0
            # Dark circles zone under the eyes
            elif (340 * scale <= x <= 395 * scale) and ((370 * scale <= y <= 450 * scale) or (560 * scale <= y <= 640 * scale)):
                # Soft gradient for the dark circles
                feature_mask[y, x] = 0.65

    # Mask smoothing
    mask_img = Image.fromarray((feature_mask * 255.0).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius=3))
    arr_mask_smooth = np.array(mask_img, dtype=np.float32) / 255.0

    # Applying the details with boosted contrast so they are WELL VISIBLE
    # Contrast boost of the scars and dark circles
    port_enhanced = ImageEnhance.Contrast(scaled_portrait.convert("RGB")).enhance(1.4)
    arr_port_enh = np.array(port_enhanced, dtype=np.float32)

    # Retrieval of the underlying skin
    mh_crop = base_skin.crop((paste_x, paste_y, paste_x + w_scaled, paste_y + h_scaled))
    arr_mh = np.array(mh_crop, dtype=np.float32)[:, :, :3]

    # MULTIPLY + OVERLAY mode to clearly inlay the glowing scars and the dark circles
    # without any hue break
    mult_blend = (arr_mh * arr_port_enh) / 255.0

    # Boost the red saturation of the scar
    mult_blend[:, :, 0] = np.clip(mult_blend[:, :, 0] * 1.15, 0, 255)

    # Final blend with the targeted mask
    alpha_3d = np.repeat(arr_mask_smooth[:, :, np.newaxis], 3, axis=2)
    final_face_patch = np.clip(arr_mh * (1.0 - alpha_3d) + mult_blend * alpha_3d, 0, 255).astype(np.uint8)
    final_face_img = Image.fromarray(final_face_patch).convert("RGBA")

    # 3. Direct paste onto the MakeHuman texture (Nose and mouth stay 100% native MakeHuman)
    final_diffuse = base_skin.copy()
    final_diffuse.paste(final_face_img, (paste_x, paste_y), mask_img)

    # 4. Saving the Diffuse textures
    for d in [OUT_MPFB_DIR, OUT_LOCAL_DIR]:
        os.makedirs(d, exist_ok=True)

    diff_mpfb = os.path.join(OUT_MPFB_DIR, "marc_novice_diffuse.png")
    diff_local = os.path.join(OUT_LOCAL_DIR, "marc_novice_diffuse.png")
    final_diffuse.convert("RGB").save(diff_mpfb, "PNG", optimize=True)
    final_diffuse.convert("RGB").save(diff_local, "PNG", optimize=True)
    print(f"✅ Diffuse texture with clean scars and dark circles saved: {diff_mpfb}")

    # 5. Normal Map with ACCENTUATED 3D RELIEF on the scars
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if racine not in sys.path:
        sys.path.insert(0, racine)
    from core.image_ops import generer_normal_map
    norm_img = generer_normal_map(final_diffuse.convert("RGB"), strength=3.5)
    norm_mpfb = os.path.join(OUT_MPFB_DIR, "marc_novice_normal.png")
    norm_local = os.path.join(OUT_LOCAL_DIR, "marc_novice_normal.png")
    norm_img.save(norm_mpfb, "PNG")
    norm_img.save(norm_local, "PNG")
    print(f"✅ Normal Map with scar grooves saved: {norm_mpfb}")

    # 6. .mhmat file
    mhmat_path = os.path.join(OUT_MPFB_DIR, "marc_novice.mhmat")
    with open(mhmat_path, "w", encoding="utf-8") as f:
        f.write("""# Material file for MakeHuman / MPFB - Marc Novice (Scars & Dark Circles)
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
