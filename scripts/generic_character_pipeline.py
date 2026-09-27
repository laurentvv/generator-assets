#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generic MakeHuman / MPFB2 3D Character Creation Pipeline for Godot 4.
Universal, clean and reproducible process:
1. Starts from the origin MakeHuman skin (unmodified).
2. Applies a distortion-free colorimetric calibration (complexion, undertone, SSS).
3. Compiles the official MPFB pack (.mhmat, .thumb, diffuse.png, normal.png).
4. Builds the 3D body headless in Blender (macros, morphology, skeleton, shape keys).
5. Adds the native anatomical 3D assets (eyes, eyebrows, eyelashes, hair, outfit).
6. Exports the GLB model for Godot (static & animated) and generates a validation render.
"""

import argparse
import os
import subprocess
import sys

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if racine not in sys.path:
    sys.path.insert(0, racine)

from PIL import Image, ImageEnhance
import numpy as np

BLENDER_EXE = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
MPFB_SKINS_DIR = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins"
SKIN_ORIGINAL_DEFAULT = os.path.join(MPFB_SKINS_DIR, "young_caucasian_male", "young_lightskinned_male_diffuse.png")


def etalonner_peau(image_pil: Image.Image, teinte: str) -> Image.Image:
    """Cleanly adjusts the skin complexion without any artifact or patchwork."""
    arr = np.array(image_pil.convert("RGB"), dtype=np.float32)

    if teinte == "cold_pale":
        # Diaphanous/pale winter complexion (e.g. Marc of Vent-Gris)
        arr[:, :, 0] *= 0.99  # Softened red
        arr[:, :, 2] = np.clip(arr[:, :, 2] * 1.02, 0, 255)  # Cold undertone
        img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        img = ImageEnhance.Brightness(img).enhance(1.04)
        img = ImageEnhance.Color(img).enhance(0.92)
        return img
    elif teinte == "warm_tan":
        # Tanned / adventurer complexion
        arr[:, :, 0] = np.clip(arr[:, :, 0] * 1.03, 0, 255)
        arr[:, :, 1] = np.clip(arr[:, :, 1] * 0.98, 0, 255)
        img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        return ImageEnhance.Color(img).enhance(1.08)
    elif teinte == "dark":
        # Matte / dark complexion
        img = ImageEnhance.Brightness(image_pil).enhance(0.85)
        return ImageEnhance.Color(img).enhance(0.95)
    else:
        return image_pil


def generer_pack_skin(
    nom_skin: str,
    skin_base_path: str = SKIN_ORIGINAL_DEFAULT,
    teinte: str = "cold_pale",
    dossier_sortie_projet: str = r"godot_assets\skins"
) -> dict:
    """Generates the full MPFB skin pack (.mhmat, .thumb, diffuse.png, normal.png)."""
    print(f"\n[1/4] 🎨 Generation of the '{nom_skin}' skin pack from the origin skin...")

    if not os.path.exists(skin_base_path):
        raise FileNotFoundError(f"Origin skin not found: {skin_base_path}")

    base_img = Image.open(skin_base_path).convert("RGB")
    skin_traitee = etalonner_peau(base_img, teinte)

    # Target folders
    dossier_mpfb = os.path.join(MPFB_SKINS_DIR, nom_skin)
    dossier_local = os.path.join(dossier_sortie_projet, nom_skin)
    os.makedirs(dossier_mpfb, exist_ok=True)
    os.makedirs(dossier_local, exist_ok=True)

    # 1. Diffuse
    diff_mpfb = os.path.join(dossier_mpfb, f"{nom_skin}_diffuse.png")
    diff_local = os.path.join(dossier_local, f"{nom_skin}_diffuse.png")
    skin_traitee.save(diff_mpfb, "PNG", optimize=True)
    skin_traitee.save(diff_local, "PNG", optimize=True)

    # 2. PBR Normal Map
    from core.image_ops import generer_normal_map
    norm_img = generer_normal_map(skin_traitee, strength=2.0)
    norm_mpfb = os.path.join(dossier_mpfb, f"{nom_skin}_normal.png")
    norm_local = os.path.join(dossier_local, f"{nom_skin}_normal.png")
    norm_img.save(norm_mpfb, "PNG")
    norm_img.save(norm_local, "PNG")

    # 3. .thumb vignette
    w, h = skin_traitee.size
    thumb_crop = skin_traitee.crop((int(w * 0.35), int(h * 0.15), int(w * 0.65), int(h * 0.45)))
    thumb_img = thumb_crop.resize((256, 256), Image.Resampling.LANCZOS).convert("RGBA")
    thumb_mpfb = os.path.join(dossier_mpfb, f"{nom_skin}.thumb")
    thumb_local = os.path.join(dossier_local, f"{nom_skin}.thumb")
    thumb_img.save(thumb_mpfb, "PNG")
    thumb_img.save(thumb_local, "PNG")

    # 4. .mhmat material
    mhmat_content = f"""# Material file for MakeHuman / MPFB
name {nom_skin}
tag MakeHuman™
tag {nom_skin}

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
alphaToCoverage True
backfaceCull True
depthless False
castShadows True
receiveShadows True

diffuseTexture {nom_skin}_diffuse.png
normalTexture {nom_skin}_normal.png
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
shaderConfig transparency True
shaderConfig diffuse True
"""
    mhmat_mpfb = os.path.join(dossier_mpfb, f"{nom_skin}.mhmat")
    mhmat_local = os.path.join(dossier_local, f"{nom_skin}.mhmat")
    with open(mhmat_mpfb, "w", encoding="utf-8") as f:
        f.write(mhmat_content)
    with open(mhmat_local, "w", encoding="utf-8") as f:
        f.write(mhmat_content)

    print(f"  ✅ MPFB skin pack installed: {dossier_mpfb}")
    return {
        "diffuse": diff_mpfb,
        "normal": norm_mpfb,
        "mhmat": mhmat_mpfb,
        "thumb": thumb_mpfb
    }


def generer_script_blender_personnage(config: dict) -> str:
    """Generates an ephemeral headless Blender Python script to assemble the character."""
    nom = config["name"]
    age = config.get("age", 0.17)
    gender = config.get("gender", 1.0)
    muscle = config.get("muscle", 0.3)
    weight = config.get("weight", 0.25)
    target_height = config.get("target_height", 1.18)
    hair = config.get("hair", "short01.mhclo")
    glb_out = config.get("export_glb", f"godot_assets/{nom}.glb")
    preview_out = config.get("render_preview", f"godot_assets/{nom}_render.png")

    script = f"""# -*- coding: utf-8 -*-
import bpy, importlib, mathutils, os, sys

def dynamic_import(absolute_package_str, key):
    for amod in sys.modules:
        if amod.endswith(absolute_package_str):
            mpfb_mod = importlib.import_module(amod)
            if hasattr(mpfb_mod, key):
                return getattr(mpfb_mod, key)
    raise ValueError(f"Module {{absolute_package_str}} not found")

bpy.ops.wm.read_factory_settings(use_empty=True)
try:
    bpy.ops.preferences.addon_enable(module="bl_ext.user_default.mpfb")
except Exception:
    pass

HumanService = dynamic_import("mpfb.services.humanservice", "HumanService")
AssetService = dynamic_import("mpfb.services.assetservice", "AssetService")
TargetService = dynamic_import("mpfb.services.targetservice", "TargetService")

# 1. Anatomical MakeHuman base body
macros = {{
    "gender": {gender},
    "age": {age},
    "muscle": {muscle},
    "weight": {weight},
    "proportions": 0.5,
    "height": 0.5,
    "race": {{"caucasian": 1.0, "asian": 0.0, "african": 0.0}}
}}
basemesh = HumanService.create_human(macro_detail_dict=macros)
TargetService.reapply_macro_details(basemesh)
bpy.context.view_layer.update()

# 2. Applying the Custom Skin
skin_path = os.path.join(r"C:/Users/laurent/AppData/Roaming/Blender Foundation/Blender/5.2/mpfb/data/skins", "{nom}", "{nom}.mhmat")
if not os.path.exists(skin_path):
    skin_path = AssetService.find_asset_absolute_path("{nom}.mhmat", asset_subdir="skins")

if skin_path and os.path.exists(skin_path):
    HumanService.set_character_skin(skin_path, basemesh, skin_type="GAMEENGINE")
    print(f"[BLENDER] Skin '{nom}' successfully applied from: {{skin_path}}")
else:
    print(f"[BLENDER] Note: Skin '{nom}' not found.")

# 3. Adding the Separate 3D Assets (Eyes, Eyebrows, Eyelashes, Teeth, Hair)
for subdir, fname, atype in [
    ("eyes",      "low-poly.mhclo",     "Eyes"),
    ("eyebrows",  "eyebrow001.mhclo",   "Eyebrows"),
    ("eyelashes", "eyelashes01.mhclo",  "Eyelashes"),
    ("tongue",    "tongue01.mhclo",     "Tongue"),
    ("teeth",     "teeth_base.mhclo",   "Teeth"),
    ("hair",      "{hair}",             "Hair"),
]:
    p = AssetService.find_asset_absolute_path(fname, asset_subdir=subdir)
    if p:
        HumanService.add_mhclo_asset(p, basemesh, asset_type=atype, material_type="GAMEENGINE")

# Base outfit
suit_p = AssetService.find_asset_absolute_path("male_worksuit01.mhclo", asset_subdir="clothes")
shoes_p = AssetService.find_asset_absolute_path("shoes01.mhclo", asset_subdir="clothes")
if suit_p:
    HumanService.add_mhclo_asset(suit_p, basemesh, asset_type="Clothes", material_type="GAMEENGINE")
if shoes_p:
    HumanService.add_mhclo_asset(shoes_p, basemesh, asset_type="Clothes", material_type="GAMEENGINE")

bpy.context.view_layer.update()

# 4. Bake the shape keys to freeze the exact morphology
dg = bpy.context.evaluated_depsgraph_get()
for obj in [basemesh] + [o for o in bpy.data.objects if o.type == 'MESH' and o is not basemesh]:
    if obj.data.shape_keys:
        ev = obj.evaluated_get(dg)
        me = bpy.data.meshes.new_from_object(ev)
        old_me = obj.data
        obj.data = me
        me.name = old_me.name
        bpy.data.meshes.remove(old_me)

# Remove the masks
for o in bpy.data.objects:
    if o.type == 'MESH':
        for m in list(o.modifiers):
            if m.type == 'MASK':
                o.modifiers.remove(m)

# 5. Height calibration ({target_height}m) and feet on the ground (Z=0)
all_objs = [o for o in bpy.data.objects if o.type == 'MESH']
all_verts = [o.matrix_world @ v.co for o in all_objs for v in o.data.vertices]
z_min, z_max = min(p.z for p in all_verts), max(p.z for p in all_verts)
h_reelle = z_max - z_min
echelle = {target_height} / h_reelle

for o in all_objs:
    o.scale *= echelle
bpy.context.view_layer.update()

all_verts_scaled = [o.matrix_world @ v.co for o in all_objs for v in o.data.vertices]
z_min_s = min(p.z for p in all_verts_scaled)
for o in all_objs:
    o.location.z -= z_min_s
bpy.context.view_layer.update()

# 6. GLB export for Godot
os.makedirs(os.path.dirname(r"{glb_out}"), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=r"{glb_out}", export_format='GLB', use_selection=False)
print(f"[BLENDER] GLB model exported: r'{glb_out}'")

# 7. Validation Studio Render
if bpy.context.scene.world is None:
    bpy.context.scene.world = bpy.data.worlds.new("World")
bpy.context.scene.world.use_nodes = True
bg = bpy.context.scene.world.node_tree.nodes.get("Background")
if bg:
    bg.inputs['Color'].default_value = (0.04, 0.04, 0.05, 1.0)

key_data = bpy.data.lights.new(name="KeyLight", type='AREA')
key_data.energy = 75.0
key_data.size = 0.6
key_obj = bpy.data.objects.new("KeyLight", key_data)
bpy.context.collection.objects.link(key_obj)
key_obj.location = mathutils.Vector((0.35, -0.65, {target_height} * 0.88 + 0.25))

fill_data = bpy.data.lights.new(name="FillLight", type='AREA')
fill_data.energy = 25.0
fill_data.size = 0.9
fill_obj = bpy.data.objects.new("FillLight", fill_data)
bpy.context.collection.objects.link(fill_obj)
fill_obj.location = mathutils.Vector((-0.50, -0.55, {target_height} * 0.88 - 0.05))

cam_data = bpy.data.cameras.new("BustCam")
cam_data.lens = 85.0
cam_obj = bpy.data.objects.new("BustCam", cam_data)
bpy.context.collection.objects.link(cam_obj)
cam_obj.location = mathutils.Vector((0.0, -0.85, {target_height} * 0.88 - 0.04))
cam_obj.rotation_euler = mathutils.Euler((1.5708, 0, 0), 'XYZ')
bpy.context.scene.camera = cam_obj

bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.samples = 32
bpy.context.scene.render.resolution_x = 1024
bpy.context.scene.render.resolution_y = 1024
bpy.context.scene.render.filepath = r"{preview_out}"
bpy.context.scene.render.image_settings.file_format = 'PNG'

os.makedirs(os.path.dirname(r"{preview_out}"), exist_ok=True)
bpy.ops.render.render(write_still=True)
print(f"[BLENDER] Validation render saved: r'{preview_out}'")
"""
    chemin_script_temp = os.path.join(racine, "scripts", "temp_blender_gen.py")
    with open(chemin_script_temp, "w", encoding="utf-8") as f:
        f.write(script)
    return chemin_script_temp


def executer_pipeline_complet(config: dict):
    """Global orchestration of the generic pipeline."""
    nom = config["name"]
    print("=" * 65)
    print(f" 🚀 GENERIC 3D CHARACTER PIPELINE: '{nom.upper()}'")
    print("=" * 65)

    # 1. Generation of the clean skin pack
    generer_pack_skin(
        nom_skin=nom,
        skin_base_path=config.get("skin_base", SKIN_ORIGINAL_DEFAULT),
        teinte=config.get("skin_tone", "cold_pale")
    )

    # 2. Generation and execution of the Blender script
    print("\n[2/4] 🔨 Anatomical assembly of the 3D model under Blender 5.2...")
    script_blender = generer_script_blender_personnage(config)
    cmd = [BLENDER_EXE, "--background", "--python", script_blender]
    res = subprocess.run(cmd, capture_output=True, text=True)

    if os.path.exists(script_blender):
        os.remove(script_blender)

    if res.returncode != 0:
        print(f"❌ Blender error: {res.stderr}")
        sys.exit(1)

    print(res.stdout)
    print("=" * 65)
    print(f" 🎉 CHARACTER '{nom}' CREATED, PACKAGED AND EXPORTED SUCCESSFULLY!")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(description="Generic MakeHuman 3D character creation pipeline for Godot.")
    parser.add_argument("--name", default="marc_novice", help="Unique identifier of the character (e.g. marc_novice, elian_peasant).")
    parser.add_argument("--age", type=float, default=0.17, help="MakeHuman age (0.0=baby, 0.18=8-year-old child, 0.5=adult).")
    parser.add_argument("--gender", type=float, default=1.0, help="MakeHuman gender (1.0=male, 0.0=female).")
    parser.add_argument("--height", type=float, default=1.18, help="Calibrated real height in meters (e.g. 1.18).")
    parser.add_argument("--skin-tone", choices=["cold_pale", "warm_tan", "dark", "neutral"], default="cold_pale", help="Skin colorimetric calibration.")
    parser.add_argument("--hair", default="short01.mhclo", help="MakeHuman hair model (.mhclo).")
    parser.add_argument("--export-glb", help="Path of the output GLB file.")
    parser.add_argument("--render-preview", help="Path of the PNG studio render image.")
    args = parser.parse_args()

    config = {
        "name": args.name,
        "age": args.age,
        "gender": args.gender,
        "target_height": args.height,
        "skin_tone": args.skin_tone,
        "hair": args.hair,
        "export_glb": args.export_glb or os.path.abspath(f"godot_assets/{args.name}.glb"),
        "render_preview": args.render_preview or os.path.abspath(f"godot_assets/{args.name}_render.png")
    }

    executer_pipeline_complet(config)


if __name__ == "__main__":
    main()
