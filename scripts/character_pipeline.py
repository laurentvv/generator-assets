#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Universal Generic 3D Character Creation Pipeline (MakeHuman / MPFB2 / Godot 4).

Required inputs:
  1. --portrait       : Path of the canonical HD 2D portrait of the character (visual reference & colorimetry).
  2. --recipe-script  : Path of the Blender 3D assembly recipe script (morphology, macros, clothes, animations).
  3. --name           : Unique identifier of the character / skin (e.g. marc_novice, elian_peasant).

Optional inputs:
  --base-skin         : Origin MakeHuman skin template (default: young_caucasian_male).
  --blender-exe       : Path of the Blender executable (default: Blender 5.2).
  --output-dir        : Output folder for the validation renders (default: godot_assets/).

Run example:
  uv run python scripts/character_pipeline.py \
    --portrait "C:\\test\\L'HERITIER DU VIDE\\assets\\portraits\\marc_portrait.png" \
    --recipe-script "C:\\test\\L'HERITIER DU VIDE\\poc_3d\\create_marc_mpfb2.py" \
    --name marc_novice
"""

import argparse
import os
import subprocess
import sys

# Windows console: force UTF-8
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if racine not in sys.path:
    sys.path.insert(0, racine)

from PIL import Image
import numpy as np

BLENDER_EXE_DEFAULT = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
MPFB_SKINS_DIR = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\data\skins"
BASE_SKIN_DEFAULT = os.path.join(MPFB_SKINS_DIR, "young_caucasian_male", "young_lightskinned_male_diffuse.png")


def extraire_colorimetrie_portrait(chemin_portrait: str) -> dict:
    """Analyzes the 2D portrait to extract its color balance and skin brightness."""
    if not os.path.exists(chemin_portrait):
        print(f"⚠️ Portrait '{chemin_portrait}' not found, using the default colorimetry.")
        return {"brightness": 1.03, "saturation": 0.92, "r_mult": 0.99, "b_mult": 1.02}

    img = Image.open(chemin_portrait).convert("RGB")
    arr = np.array(img, dtype=np.float32)

    # Skin pixel detection (warm/light hue)
    mask_skin = (arr[:, :, 0] > 70) & (arr[:, :, 0] > arr[:, :, 2]) & (arr[:, :, 1] > arr[:, :, 2])
    if np.sum(mask_skin) > 500:
        pixels_skin = arr[mask_skin]
        mean_rgb = np.mean(pixels_skin, axis=0)
        # Compute the adjustments against a standard skin
        lum = (mean_rgb[0] * 0.299 + mean_rgb[1] * 0.587 + mean_rgb[2] * 0.114) / 255.0
        brightness_factor = 1.0 + (lum - 0.55) * 0.2
        cold_tone = mean_rgb[2] / (mean_rgb[0] + 1e-5)
        b_factor = 1.0 + (cold_tone - 0.60) * 0.3
    else:
        brightness_factor = 1.03
        b_factor = 1.02

    return {
        "brightness": float(np.clip(brightness_factor, 0.90, 1.15)),
        "saturation": 0.92,
        "r_mult": 0.99,
        "b_mult": float(np.clip(b_factor, 0.95, 1.08))
    }


def etape_1_generer_pack_skin(nom_personnage: str, chemin_base_skin: str, chemin_portrait: str, dossier_sortie_godot: str) -> dict:
    """Step 1: Generates the full MPFB pack (.mhmat, .thumb, diffuse, normal) without destructive alteration."""
    print(f"\n[1/3] 🎨 STEP 1: Generation of the '{nom_personnage}' skin pack...")

    if not os.path.exists(chemin_base_skin):
        raise FileNotFoundError(f"Origin MakeHuman skin not found: {chemin_base_skin}")

    # 1. Load the origin MakeHuman skin
    base_skin = Image.open(chemin_base_skin).convert("RGBA")
    w, h = base_skin.size

    # 2. Fatigue dark-circle layer under the eyes
    from PIL import ImageDraw, ImageFilter
    cerne_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_cerne = ImageDraw.Draw(cerne_layer)
    # Crescent under the left eye (top UV)
    draw_cerne.ellipse([1700, 935, 1750, 995], fill=(55, 32, 28, 120))
    # Crescent under the right eye (bottom UV)
    draw_cerne.ellipse([1700, 1120, 1750, 1180], fill=(55, 32, 28, 120))
    cerne_blurred = cerne_layer.filter(ImageFilter.GaussianBlur(radius=10))

    # 3. Forehead scar layer and cheek scratch
    scar_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_scar = ImageDraw.Draw(scar_layer)
    # Forehead scar (above the right eyebrow)
    draw_scar.line([(1615, 1180), (1638, 1205)], fill=(185, 95, 80, 200), width=6)
    draw_scar.line([(1617, 1182), (1636, 1203)], fill=(90, 20, 18, 255), width=3)
    draw_scar.line([(1630, 1172), (1645, 1185)], fill=(110, 30, 25, 220), width=2)
    # Left cheek scratch
    draw_scar.line([(1765, 905), (1785, 925)], fill=(160, 75, 65, 180), width=4)
    draw_scar.line([(1767, 907), (1783, 923)], fill=(85, 22, 18, 240), width=2)
    scar_blurred = scar_layer.filter(ImageFilter.GaussianBlur(radius=0.8))

    # Layer merging
    skin_finale = Image.alpha_composite(base_skin, cerne_blurred)
    skin_finale = Image.alpha_composite(skin_finale, scar_blurred)

    # Target folders (MPFB + Godot)
    dossier_mpfb = os.path.join(MPFB_SKINS_DIR, nom_personnage)
    dossier_local = os.path.join(dossier_sortie_godot, "skins", nom_personnage)
    os.makedirs(dossier_mpfb, exist_ok=True)
    os.makedirs(dossier_local, exist_ok=True)

    # 1. Diffuse PNG
    diff_mpfb = os.path.join(dossier_mpfb, f"{nom_personnage}_diffuse.png")
    diff_local = os.path.join(dossier_local, f"{nom_personnage}_diffuse.png")
    skin_finale.convert("RGB").save(diff_mpfb, "PNG", optimize=True)
    skin_finale.convert("RGB").save(diff_local, "PNG", optimize=True)

    # 2. PBR Normal Map
    from core.image_ops import generer_normal_map
    norm_img = generer_normal_map(skin_finale, strength=2.0)
    norm_mpfb = os.path.join(dossier_mpfb, f"{nom_personnage}_normal.png")
    norm_local = os.path.join(dossier_local, f"{nom_personnage}_normal.png")
    norm_img.save(norm_mpfb, "PNG")
    norm_img.save(norm_local, "PNG")

    # 3. .thumb vignette for the Blender interface
    w, h = skin_finale.size
    thumb_crop = skin_finale.crop((int(w * 0.35), int(h * 0.15), int(w * 0.65), int(h * 0.45)))
    thumb_img = thumb_crop.resize((256, 256), Image.Resampling.LANCZOS).convert("RGBA")
    thumb_mpfb = os.path.join(dossier_mpfb, f"{nom_personnage}.thumb")
    thumb_local = os.path.join(dossier_local, f"{nom_personnage}.thumb")
    thumb_img.save(thumb_mpfb, "PNG")
    thumb_img.save(thumb_local, "PNG")

    # 4. .mhmat material
    mhmat_code = f"""# Material file for MakeHuman / MPFB
name {nom_personnage}
tag MakeHuman™
tag {nom_personnage}

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

diffuseTexture {nom_personnage}_diffuse.png
normalTexture {nom_personnage}_normal.png
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
    mhmat_mpfb = os.path.join(dossier_mpfb, f"{nom_personnage}.mhmat")
    mhmat_local = os.path.join(dossier_local, f"{nom_personnage}.mhmat")
    with open(mhmat_mpfb, "w", encoding="utf-8") as f:
        f.write(mhmat_code)
    with open(mhmat_local, "w", encoding="utf-8") as f:
        f.write(mhmat_code)

    print(f"  ✅ Skin pack deployed into Blender MPFB: {dossier_mpfb}")
    return {
        "diffuse": diff_mpfb,
        "normal": norm_mpfb,
        "mhmat": mhmat_mpfb,
        "thumb": thumb_mpfb
    }


def etape_2_executer_recette_blender(chemin_blender: str, chemin_recette: str):
    """Step 2: Runs the Blender recipe script to build the 3D mesh and export the GLBs."""
    print("\n[2/3] 🔨 STEP 2: Running the 3D recipe in Blender...")
    if not os.path.exists(chemin_recette):
        raise FileNotFoundError(f"Blender recipe script not found: {chemin_recette}")

    cmd = [chemin_blender, "--background", "--python", chemin_recette]
    res = subprocess.run(cmd, capture_output=True, text=True)

    if res.returncode != 0:
        print(f"❌ Error while running the Blender recipe: {res.stderr}")
        sys.exit(1)

    print(res.stdout)
    print("  ✅ 3D model built and exported successfully.")


def etape_3_rendre_validation(chemin_blender: str, glb_path: str, sortie_render: str):
    """Step 3: Cycles studio render validating the generated GLB model."""
    print("\n[3/3] 📸 STEP 3: 3D validation studio render...")

    if not os.path.exists(glb_path):
        print(f"⚠️ GLB file '{glb_path}' not found for the validation render, step skipped.")
        return

    script_render = f"""# -*- coding: utf-8 -*-
import bpy, mathutils, os

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=r"{glb_path}")

all_objs = [o for o in bpy.data.objects if o.type == 'MESH']
all_verts = [o.matrix_world @ v.co for o in all_objs for v in o.data.vertices]
z_max, z_min = max(p.z for p in all_verts), min(p.z for p in all_verts)
y_min, y_max = min(p.y for p in all_verts), max(p.y for p in all_verts)
y_center = (y_min + y_max) / 2.0
head_z = z_max - 0.15

# Dramatic Chiaroscuro lighting (Vent-Gris)
if bpy.context.scene.world is None:
    bpy.context.scene.world = bpy.data.worlds.new("World")
bpy.context.scene.world.use_nodes = True
bg = bpy.context.scene.world.node_tree.nodes.get("Background")
if bg:
    bg.inputs['Color'].default_value = (0.02, 0.03, 0.04, 1.0)

key_data = bpy.data.lights.new(name="KeyLight", type='AREA')
key_data.energy = 45.0
key_data.size = 0.5
key_data.color = (0.98, 0.92, 0.85)  # Soft warm light
key_obj = bpy.data.objects.new("KeyLight", key_data)
bpy.context.collection.objects.link(key_obj)
key_obj.location = mathutils.Vector((0.35, y_center - 0.90, head_z + 0.25))

fill_data = bpy.data.lights.new(name="FillLight", type='AREA')
fill_data.energy = 15.0
fill_data.size = 0.8
fill_data.color = (0.75, 0.80, 0.88)  # Cold nordic ambience
fill_obj = bpy.data.objects.new("FillLight", fill_data)
bpy.context.collection.objects.link(fill_obj)
fill_obj.location = mathutils.Vector((-0.45, y_center - 0.80, head_z - 0.05))

rim_data = bpy.data.lights.new(name="RimLight", type='AREA')
rim_data.energy = 60.0
rim_data.size = 0.4
rim_data.color = (0.85, 0.90, 1.0)
rim_obj = bpy.data.objects.new("RimLight", rim_data)
bpy.context.collection.objects.link(rim_obj)
rim_obj.location = mathutils.Vector((0.20, y_center + 0.55, head_z + 0.35))

# Bust / Portrait camera
cam_data = bpy.data.cameras.new("BustCam")
cam_data.lens = 55.0
cam_obj = bpy.data.objects.new("BustCam", cam_data)
bpy.context.collection.objects.link(cam_obj)
cam_obj.location = mathutils.Vector((0.0, y_center - 1.25, head_z - 0.06))
cam_obj.rotation_euler = mathutils.Euler((1.5708, 0, 0), 'XYZ')
bpy.context.scene.camera = cam_obj

bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.samples = 64
bpy.context.scene.render.resolution_x = 1024
bpy.context.scene.render.resolution_y = 1024
bpy.context.scene.render.filepath = r"{sortie_render}"
bpy.context.scene.render.image_settings.file_format = 'PNG'

os.makedirs(os.path.dirname(r"{sortie_render}"), exist_ok=True)
bpy.ops.render.render(write_still=True)
"""
    tmp_script = os.path.join(racine, "scripts", "temp_beauty_render.py")
    with open(tmp_script, "w", encoding="utf-8") as f:
        f.write(script_render)

    cmd = [chemin_blender, "--background", "--python", tmp_script]
    subprocess.run(cmd, capture_output=True, text=True)

    if os.path.exists(tmp_script):
        os.remove(tmp_script)

    if os.path.exists(sortie_render):
        print(f"  ✅ Validation render saved: {sortie_render}")


def main():
    parser = argparse.ArgumentParser(
        description="Generic 3D character creation pipeline (MakeHuman + MPFB2 + Godot 4).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  uv run python scripts/character_pipeline.py \\
    --portrait "C:\\test\\L'HERITIER DU VIDE\\assets\\portraits\\marc_portrait.png" \\
    --recipe-script "C:\\test\\L'HERITIER DU VIDE\\poc_3d\\create_marc_mpfb2.py" \\
    --name marc_novice
        """
    )
    parser.add_argument("-p", "--portrait", required=True, help="Absolute path of the canonical HD 2D portrait of the character.")
    parser.add_argument("-r", "--recipe-script", required=True, help="Absolute path of the Blender 3D assembly recipe script (.py).")
    parser.add_argument("-n", "--name", required=True, help="Name / unique identifier of the character (e.g. marc_novice, elian_peasant).")
    parser.add_argument("-s", "--base-skin", default=BASE_SKIN_DEFAULT, help="Path of the origin MakeHuman skin template.")
    parser.add_argument("-o", "--output-dir", default="godot_assets", help="Output folder of the assets and renders (default: godot_assets/).")
    parser.add_argument("--blender-exe", default=BLENDER_EXE_DEFAULT, help="Path of the Blender executable.")

    args = parser.parse_args()

    print("=" * 65)
    print(f" 🚀 GENERIC 3D CHARACTER PIPELINE: '{args.name.upper()}'")
    print(f" 👤 Source Portrait : {args.portrait}")
    print(f" 📜 3D Recipe      : {args.recipe_script}")
    print("=" * 65)

    # Step 1: MPFB Skin Pack
    etape_1_generer_pack_skin(
        nom_personnage=args.name,
        chemin_base_skin=args.base_skin,
        chemin_portrait=args.portrait,
        dossier_sortie_godot=args.output_dir
    )

    # Step 2: Running the Blender Recipe
    etape_2_executer_recette_blender(
        chemin_blender=args.blender_exe,
        chemin_recette=args.recipe_script
    )

    # Step 3: Validation Studio Render
    glb_exporte = os.path.join(r"C:\test\L'HERITIER DU VIDE\poc_3d\exports", f"{args.name}.glb")
    if not os.path.exists(glb_exporte):
        # Look for the _mpfb2 variant
        glb_exporte = os.path.join(r"C:\test\L'HERITIER DU VIDE\poc_3d\exports", f"{args.name.split('_')[0]}_mpfb2.glb")

    render_preview = os.path.abspath(os.path.join(args.output_dir, f"{args.name}_beauty_render.png"))
    etape_3_rendre_validation(
        chemin_blender=args.blender_exe,
        glb_path=glb_exporte,
        sortie_render=render_preview
    )

    print("\n" + "=" * 65)
    print(f" 🎉 PIPELINE COMPLETED SUCCESSFULLY FOR '{args.name.upper()}'!")
    print("=" * 65)


if __name__ == "__main__":
    main()
