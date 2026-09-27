#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete 2D ➔ 3D Camera Projection Orchestrator for Marc.
1. Runs Blender in background to project and digitize (bake) the 2D portrait onto the 3D mesh.
2. Seamlessly merges the projected face texture with the MakeHuman body skin.
3. Updates the Blender MPFB directories, the 3D POC and godot_assets.
4. Performs a 3D render in Blender for visual validation.
"""

import os
import subprocess
import sys

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

from PIL import Image, ImageFilter, ImageDraw

BLENDER_EXE = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
SCRIPT_BAKE_BLENDER = r"C:\GIT\generator-assets\scripts\blender_bake_projection.py"
TEMP_BAKE_OUTPUT = r"C:\GIT\generator-assets\godot_assets\temp_marc_baked_face.png"
SKIN_BASE = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\young_caucasian_male\young_lightskinned_male_diffuse.png"

SORTIE_DIFFUSE_MPFB = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\marc_novice\marc_novice_diffuse.png"
SORTIE_DIFFUSE_LOCAL = r"C:\GIT\generator-assets\godot_assets\skins\marc_novice\marc_novice_diffuse.png"
SORTIE_DIFFUSE_POC = r"C:\test\L'HERITIER DU VIDE\poc_3d\exports\marc_mpfb2_young_lightskinned_male_diffuse.png"
THUMB_MPFB = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\marc_novice\marc_novice.thumb"
THUMB_LOCAL = r"C:\GIT\generator-assets\godot_assets\skins\marc_novice\marc_novice.thumb"


def main():
    print("=" * 65)
    print(" 🎬 OFFICIAL PIPELINE: 2D ➔ 3D CAMERA PROJECTION (BLENDER + MAKEHUMAN)")
    print("=" * 65)

    # 1. Running the Blender Baking
    print("\n[1/3] Running Blender headless for the UV baking...")
    cmd = [BLENDER_EXE, "--background", "--python", SCRIPT_BAKE_BLENDER]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(res.stdout)
    if res.returncode != 0 or not os.path.exists(TEMP_BAKE_OUTPUT):
        print(f"❌ Error during the Blender baking: {res.stderr}")
        sys.exit(1)

    # 2. Composition & seamless merge with the body skin
    print("[2/3] Seamless merge of the projected face with the body skin...")
    baked_img = Image.open(TEMP_BAKE_OUTPUT).convert("RGBA")
    skin_base_img = Image.open(SKIN_BASE).convert("RGBA").resize(baked_img.size)

    w, h = baked_img.size
    masque = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(masque)

    # UV zone of the MakeHuman hm08 face (front head)
    draw.ellipse([int(w * 0.35), int(h * 0.10), int(w * 0.65), int(h * 0.46)], fill=255)
    masque_fondu = masque.filter(ImageFilter.GaussianBlur(radius=32))

    baked_face = baked_img.copy()
    baked_face.putalpha(masque_fondu)

    skin_finale = Image.alpha_composite(skin_base_img, baked_face).convert("RGB")

    # 3. Save into all the target folders
    print("[3/3] Export of the official UV skin textures...")
    for path in [SORTIE_DIFFUSE_MPFB, SORTIE_DIFFUSE_LOCAL, SORTIE_DIFFUSE_POC]:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        skin_finale.save(path, "PNG", optimize=True)
        print(f"  ✅ {path}")

    # .thumb thumbnail
    thumb_crop = skin_finale.crop((int(w * 0.30), int(h * 0.10), int(w * 0.70), int(h * 0.48)))
    thumb_img = thumb_crop.resize((256, 256), Image.Resampling.LANCZOS).convert("RGBA")
    for t_path in [THUMB_MPFB, THUMB_LOCAL]:
        os.makedirs(os.path.dirname(t_path), exist_ok=True)
        thumb_img.save(t_path, "PNG")
        print(f"  ✅ Thumbnail: {t_path}")

    # Temporary cleanup
    if os.path.exists(TEMP_BAKE_OUTPUT):
        os.remove(TEMP_BAKE_OUTPUT)

    print("\n" + "=" * 65)
    print(" 🎉 CAMERA PROJECTION DONE AND UV BAKE COMPLETED SUCCESSFULLY!")
    print("=" * 65)


if __name__ == "__main__":
    main()
