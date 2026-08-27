# -*- coding: utf-8 -*-
"""
makeclothes_from_mesh.py
Script d'automatisation MakeClothes pour MPFB2 / Blender 5.2.
Permet de transformer n'importe quel maillage 3D externe (issu d'une IA 3D comme Trellis,
Tripo3D, Hunyuan3D ou modélisé sous Blender) en un vêtement MakeHuman officiel (.mhclo, .obj, .mhmat, .thumb).

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
    parser = argparse.ArgumentParser(description="Compiler un maillage 3D en vêtement MakeHuman (.mhclo)")
    parser.add_argument("--mesh", required=True, help="Chemin du fichier 3D (.obj, .glb, .fbx)")
    parser.add_argument("--name", required=True, help="Nom de l'asset vêtement (ex: cape_voyageur)")
    parser.add_argument("--category", default="clothes", help="Catégorie (clothes, shoes, hair)")
    parser.add_argument("--author", default="Generator-Assets AI", help="Auteur")
    parser.add_argument("--z-depth", type=int, default=50, help="Ordre d'empilement (Z-Depth)")
    args = parser.parse_args()

    mesh_path = os.path.abspath(args.mesh)
    if not os.path.exists(mesh_path):
        print(f"❌ Erreur : Fichier 3D introuvable : {mesh_path}")
        sys.exit(1)

    out_dir = os.path.join(DEFAULT_MPFB_DATA_DIR, args.category, args.name)
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 65)
    print(f" 👗 COMPILATION MAKECLOTHES : '{args.name}'")
    print(f" 📦 Source 3D   : {mesh_path}")
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
    raise ValueError(f"Module {{absolute_package_str}} introuvable")

bpy.ops.wm.read_factory_settings(use_empty=True)
try:
    bpy.ops.preferences.addon_enable(module="bl_ext.user_default.mpfb")
except Exception:
    pass

HumanService = dynamic_import("mpfb.services.humanservice", "HumanService")
ClothesService = dynamic_import("mpfb.services.clothesservice", "ClothesService")
AssetService = dynamic_import("mpfb.services.assetservice", "AssetService")

# 1. Création du corps de référence MakeHuman
human = HumanService.create_human(mask_helpers=False, detailed_helpers=True)

# 2. Importation du maillage 3D
mesh_path = r"{mesh_path}"
ext = os.path.splitext(mesh_path)[1].lower()

if ext == ".obj":
    bpy.ops.wm.obj_import(filepath=mesh_path)
elif ext in [".glb", ".gltf"]:
    bpy.ops.import_scene.gltf(filepath=mesh_path)
elif ext == ".fbx":
    bpy.ops.import_scene.fbx(filepath=mesh_path)

# Récupération de l'objet vêtement importé
cloth_objs = [o for o in bpy.context.selected_objects if o != human and o.type == 'MESH']
if not cloth_objs:
    cloth_objs = [o for o in bpy.data.objects if o != human and o.type == 'MESH']

if not cloth_objs:
    raise RuntimeError("Aucun maillage 3D vêtement trouvé après import.")

cloth_obj = cloth_objs[0]
cloth_obj.name = "{args.name}"

# 3. Assignation du vertex group 'body' pour validation MPFB
if "body" not in cloth_obj.vertex_groups:
    body_vg = cloth_obj.vertex_groups.new(name="body")
    body_vg.add(list(range(len(cloth_obj.data.vertices))), 1.0, "REPLACE")

# 4. Exécution de MakeClothes pour calculer le lien barycentrique
props = {{
    "name": "{args.name}",
    "author": "{args.author}",
    "category": "{args.category}",
    "z_depth": {args.z_depth}
}}

print("[MAKECLOTHES] Calcul des coordonnées barycentriques...")
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
print(f"[MAKECLOTHES] ✅ Fichier .mhclo généré avec succès : {{mhclo_path}}")

# 5. Création d'une vignette .thumb
thumb_path = os.path.join(out_folder, f"{args.name}.thumb")
if not os.path.exists(thumb_path):
    from PIL import Image
    im = Image.new("RGB", (128, 128), (60, 65, 75))
    im.save(thumb_path)

AssetService.update_all_asset_lists()
print("[MAKECLOTHES] ✅ Asset MakeHuman enregistré dans la bibliothèque MPFB.")
"""
    cmd = [BLENDER_EXE, "--background", "--python-expr", script_blender]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(res.stdout)
    if res.returncode == 0:
        print(f"🎉 Vêtement '{args.name}' compilé et disponible dans Blender MPFB !")
    else:
        print(f"⚠️ Erreur lors de la compilation MakeClothes : {res.stderr}")

if __name__ == "__main__":
    main()
