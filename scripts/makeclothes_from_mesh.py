# -*- coding: utf-8 -*-
"""
makeclothes_from_mesh.py
MakeClothes automation script for MPFB2 / Blender 5.2.
Turns any external 3D mesh (from a 3D AI like Trellis, Tripo3D, Hunyuan3D or modeled in Blender)
into an official MakeHuman garment (.mhclo, .obj, .mhmat, .thumb).

Usage:
    uv run python scripts/makeclothes_from_mesh.py --mesh "path/to/garment.obj" --name "cape_voyageur" --category "clothes"
"""

import argparse
import os
import sys
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import DEFAULT_MPFB_DATA_DIR

BLENDER_EXE = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"

def main():
    parser = argparse.ArgumentParser(description="Compile a 3D mesh into a MakeHuman garment (.mhclo)")
    parser.add_argument("--mesh", required=True, help="Path of the 3D file (.obj, .glb, .fbx)")
    parser.add_argument("--name", required=True, help="Garment asset name (e.g. cape_voyageur)")
    parser.add_argument("--category", default="clothes", help="Category (clothes, shoes, hair)")
    parser.add_argument("--author", default="Generator-Assets AI", help="Author")
    parser.add_argument("--z-depth", type=int, default=50, help="Stacking order (Z-Depth)")
    args = parser.parse_args()

    mesh_path = os.path.abspath(args.mesh)
    if not os.path.exists(mesh_path):
        print(f"❌ Error: 3D file not found: {mesh_path}")
        sys.exit(1)

    out_dir = os.path.join(DEFAULT_MPFB_DATA_DIR, args.category, args.name)
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 65)
    print(f" 👗 MAKECLOTHES COMPILATION: '{args.name}'")
    print(f" 📦 3D source   : {mesh_path}")
    print(f" 📂 Destination : {out_dir}")
    print("=" * 65)

    script_blender = f"""# -*- coding: utf-8 -*-
import bpy, importlib, os, sys

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
ClothesService = dynamic_import("mpfb.services.clothesservice", "ClothesService")
AssetService = dynamic_import("mpfb.services.assetservice", "AssetService")

# 1. Creation of the MakeHuman reference body
human = HumanService.create_human(mask_helpers=False, detailed_helpers=True)

# 2. Import of the 3D mesh
mesh_path = r"{mesh_path}"
ext = os.path.splitext(mesh_path)[1].lower()

if ext == ".obj":
    bpy.ops.wm.obj_import(filepath=mesh_path)
elif ext in [".glb", ".gltf"]:
    bpy.ops.import_scene.gltf(filepath=mesh_path)
elif ext == ".fbx":
    bpy.ops.import_scene.fbx(filepath=mesh_path)

# Retrieval of the imported garment object
cloth_objs = [o for o in bpy.context.selected_objects if o != human and o.type == 'MESH']
if not cloth_objs:
    cloth_objs = [o for o in bpy.data.objects if o != human and o.type == 'MESH']

if not cloth_objs:
    raise RuntimeError("No garment 3D mesh found after import.")

cloth_obj = cloth_objs[0]
cloth_obj.name = "{args.name}"

# 3. Assignment of the 'body' vertex group for MPFB validation
if "body" not in cloth_obj.vertex_groups:
    body_vg = cloth_obj.vertex_groups.new(name="body")
    body_vg.add(list(range(len(cloth_obj.data.vertices))), 1.0, "REPLACE")

# 4. Running MakeClothes to compute the barycentric link
props = {{
    "name": "{args.name}",
    "author": "{args.author}",
    "category": "{args.category}",
    "z_depth": {args.z_depth}
}}

print("[MAKECLOTHES] Computing barycentric coordinates...")
mhclo = ClothesService.create_mhclo_from_clothes_matching(
    human,
    cloth_obj,
    properties_dict=props,
    delete_group=None
)

out_folder = r"{out_dir}"
mhclo_path = os.path.join(out_folder, f"{args.name}.mhclo")
ref_scale = ClothesService.get_reference_scale(human)
mhclo.write_mhclo(mhclo_path, reference_scale=ref_scale, also_export_obj=True, also_export_mhmat=True)
print(f"[MAKECLOTHES] ✅ .mhclo file generated successfully: {{mhclo_path}}")

# 5. Creation of a .thumb thumbnail
thumb_path = os.path.join(out_folder, f"{args.name}.thumb")
if not os.path.exists(thumb_path):
    from PIL import Image
    im = Image.new("RGB", (128, 128), (60, 65, 75))
    im.save(thumb_path)

AssetService.update_all_asset_lists()
print("[MAKECLOTHES] ✅ MakeHuman asset registered in the MPFB library.")
"""
    cmd = [BLENDER_EXE, "--background", "--python-expr", script_blender]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(res.stdout)
    if res.returncode == 0:
        print(f"🎉 Garment '{args.name}' compiled and available in Blender MPFB!")
    else:
        print(f"⚠️ Error during MakeClothes compilation: {res.stderr}")

if __name__ == "__main__":
    main()
