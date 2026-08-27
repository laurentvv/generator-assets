# -*- coding: utf-8 -*-
import bpy
import bmesh
import importlib
import mathutils
import os
import sys

def dynamic_import(absolute_package_str, key):
    for amod in sys.modules:
        if amod.endswith(absolute_package_str):
            mpfb_mod = importlib.import_module(amod)
            if hasattr(mpfb_mod, key):
                return getattr(mpfb_mod, key)
    raise ValueError(f"Module {absolute_package_str} introuvable")

bpy.ops.wm.read_factory_settings(use_empty=True)
try:
    bpy.ops.preferences.addon_enable(module="bl_ext.user_default.mpfb")
except Exception:
    pass

HumanService = dynamic_import("mpfb.services.humanservice", "HumanService")
AssetService = dynamic_import("mpfb.services.assetservice", "AssetService")
TargetService = dynamic_import("mpfb.services.targetservice", "TargetService")

# 1. Création corps enfant natif
macros = {
    "gender": 1.0, "age": 0.18, "muscle": 0.30, "weight": 0.25,
    "proportions": 0.50, "height": 0.50,
    "race": {"caucasian": 1.0, "asian": 0.0, "african": 0.0}
}
basemesh = HumanService.create_human(macro_detail_dict=macros)
TargetService.reapply_macro_details(basemesh)
bpy.context.view_layer.update()

# 2. Skin Marc
skin_mhmat = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\marc_novice\marc_novice.mhmat"
if os.path.exists(skin_mhmat):
    HumanService.set_character_skin(skin_mhmat, basemesh, skin_type="GAMEENGINE")

# 3. Ajout des assets natifs (ajustés sur le morph enfant)
assets = [
    ("eyes",      "low-poly.mhclo",        "Eyes"),
    ("eyebrows",  "eyebrow001.mhclo",      "Eyebrows"),
    ("eyelashes", "eyelashes01.mhclo",     "Eyelashes"),
    ("tongue",    "tongue01.mhclo",        "Tongue"),
    ("teeth",     "teeth_base.mhclo",      "Teeth"),
    ("hair",      "short01.mhclo",         "Hair"),
    ("clothes",   "male_worksuit01.mhclo", "Clothes"),
    ("clothes",   "shoes01.mhclo",         "Clothes"),
]
for subdir, fname, atype in assets:
    p = AssetService.find_asset_absolute_path(fname, asset_subdir=subdir)
    if p:
        HumanService.add_mhclo_asset(p, basemesh, asset_type=atype, material_type="GAMEENGINE")

bpy.context.view_layer.update()

# 4. SUPPRESSION PROPRE DES GÉOMÉTRIES D'AIDE (HelperGeometry)
# MakeHuman génère des géométries d'aide (jupes, yeux internes, etc.) qui doivent être retirées
helper_vg = basemesh.vertex_groups.get("HelperGeometry")
if helper_vg:
    bm = bmesh.new()
    bm.from_mesh(basemesh.data)
    dlayer = bm.verts.layers.deform.verify()
    helper_idx = helper_vg.index
    verts_to_delete = [v for v in bm.verts if helper_idx in v[dlayer] and v[dlayer][helper_idx] > 0.5]
    bmesh.ops.delete(bm, geom=verts_to_delete, context='VERTS')
    bm.to_mesh(basemesh.data)
    bm.free()
    basemesh.data.update()

# 5. Fix opacité matériaux
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        for mat in obj.data.materials:
            if mat and mat.node_tree:
                bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
                if bsdf and bsdf.inputs.get("Alpha"):
                    for lk in list(bsdf.inputs["Alpha"].links):
                        mat.node_tree.links.remove(lk)
                    bsdf.inputs["Alpha"].default_value = 1.0
                an = mat.node_tree.nodes.get("AlphaMapTexture")
                if an:
                    mat.node_tree.nodes.remove(an)

# 6. Sauvegarde et export GLB
out_blend = r"C:\test\L'HERITIER DU VIDE\poc_3d\exports\marc_mpfb2.blend"
out_glb = r"C:\test\L'HERITIER DU VIDE\poc_3d\exports\marc_mpfb2.glb"
bpy.ops.wm.save_as_mainfile(filepath=out_blend)

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=out_glb, export_format='GLB', use_selection=True)

# 7. Rendu portrait propre
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=out_glb)

all_objs = [o for o in bpy.data.objects if o.type == 'MESH']
all_verts = [o.matrix_world @ v.co for o in all_objs for v in o.data.vertices]
z_max, z_min = max(p.z for p in all_verts), min(p.z for p in all_verts)
y_center = (min(p.y for p in all_verts) + max(p.y for p in all_verts)) / 2.0
head_z = z_max - 0.12

# Éclairage 3 points
k_data = bpy.data.lights.new("Key", 'AREA')
k_data.energy = 50.0
k = bpy.data.objects.new("Key", k_data)
bpy.context.collection.objects.link(k)
k.location = (0.4, y_center - 0.8, head_z + 0.3)

f_data = bpy.data.lights.new("Fill", 'AREA')
f_data.energy = 20.0
f = bpy.data.objects.new("Fill", f_data)
bpy.context.collection.objects.link(f)
f.location = (-0.5, y_center - 0.7, head_z)

cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 60.0
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.collection.objects.link(cam)
cam.location = (0.0, y_center - 0.95, head_z - 0.05)
cam.rotation_euler = (1.5708, 0, 0)
bpy.context.scene.camera = cam

bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT' if hasattr(bpy.types.RenderSettings, 'engine') else 'CYCLES'
bpy.context.scene.render.filepath = r"C:\GIT\generator-assets\godot_assets\marc_3d_beauty_render.png"
bpy.ops.render.render(write_still=True)
print("✅ Rendu propre terminé !")
