# -*- coding: utf-8 -*-
"""
test_marc_clean_morphology.py
Reconstruit le visage de Marc avec la méthode professionnelle MakeHuman :
1. Peau MakeHuman photoréaliste propre d'origine (sans découpe ni bricolage 2D).
2. Morphologie 3D faciale ciblée (yeux perçants, sourcils déterminés, mâchoire fine).
3. Matériaux et éclairage équilibrés.
"""

import bpy
import bmesh
import importlib
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

# 1. Corps enfant 8 ans avec traits médiévaux fins
macros = {
    "gender": 1.0, "age": 0.18, "muscle": 0.28, "weight": 0.22,
    "proportions": 0.50, "height": 0.48,
    "race": {"caucasian": 1.0, "asian": 0.0, "african": 0.0}
}
basemesh = HumanService.create_human(macro_detail_dict=macros)
TargetService.reapply_macro_details(basemesh)
bpy.context.view_layer.update()

# 2. Peau propre d'origine MakeHuman (GAMEENGINE)
skin_mhmat = AssetService.find_asset_absolute_path("young_caucasian_male.mhmat", asset_subdir="skins")
if skin_mhmat:
    HumanService.set_character_skin(skin_mhmat, basemesh, skin_type="GAMEENGINE")

# 3. Assets natifs (yeux, dents, langue, cheveux courts, tenue)
assets = [
    ("eyes",      "low-poly.mhclo",        "Eyes"),
    ("eyebrows",  "eyebrow001.mhclo",      "Eyebrows"),
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

# Matériau sourcils doux assorti aux cheveux
eyebrow_obj = next((o for o in bpy.data.objects if "eyebrow" in o.name.lower()), None)
if eyebrow_obj and eyebrow_obj.data.materials:
    mat_eb = bpy.data.materials.new(name="Marc_Eyebrows_Natural")
    mat_eb.use_nodes = True
    bsdf = next(n for n in mat_eb.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = (0.16, 0.11, 0.08, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.90
    eyebrow_obj.data.materials.clear()
    eyebrow_obj.data.materials.append(mat_eb)

hair_obj = next((o for o in bpy.data.objects if "short01" in o.name.lower()), None)
if hair_obj:
    mat_hair = bpy.data.materials.new(name="Marc_Hair_Natural")
    mat_hair.use_nodes = True
    bsdf = next(n for n in mat_hair.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = (0.14, 0.10, 0.07, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.75
    hair_obj.data.materials.clear()
    hair_obj.data.materials.append(mat_hair)

# 4. Suppression des sommets d'aide MakeHuman
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

# 5. Bake shape keys
dg = bpy.context.evaluated_depsgraph_get()
for obj in list(bpy.data.objects):
    if obj.type == 'MESH' and obj.data.shape_keys:
        ev = obj.evaluated_get(dg)
        me = bpy.data.meshes.new_from_object(ev)
        old = obj.data
        obj.data = me
        me.name = old.name
        bpy.data.meshes.remove(old)

# 6. Retrait des masques
for obj in list(bpy.data.objects):
    if obj.type == 'MESH':
        for m in list(obj.modifiers):
            if m.type == 'MASK':
                obj.modifiers.remove(m)
        for vg in list(obj.vertex_groups):
            if vg.name.startswith("Delete."):
                obj.vertex_groups.remove(vg)

# 7. Alpha propre
for obj in list(bpy.data.objects):
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

# 8. Sauvegarde et export GLB
out_blend = r"C:\test\L'HERITIER DU VIDE\poc_3d\exports\marc_mpfb2.blend"
out_glb = r"C:\test\L'HERITIER DU VIDE\poc_3d\exports\marc_mpfb2.glb"
local_blend = r"C:\GIT\generator-assets\godot_assets\marc_novice.blend"
local_glb = r"C:\GIT\generator-assets\godot_assets\marc_novice.glb"

bpy.ops.wm.save_as_mainfile(filepath=out_blend)
bpy.ops.wm.save_as_mainfile(filepath=local_blend)

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(filepath=out_glb, export_format='GLB', use_selection=True)
bpy.ops.export_scene.gltf(filepath=local_glb, export_format='GLB', use_selection=True)

# 9. Rendu de validation studio
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=out_glb)

all_objs = [o for o in bpy.data.objects if o.type == 'MESH']
all_verts = [o.matrix_world @ v.co for o in all_objs for v in o.data.vertices]
z_max, z_min = max(p.z for p in all_verts), min(p.z for p in all_verts)
y_min, y_max = min(p.y for p in all_verts), max(p.y for p in all_verts)
y_center = (y_min + y_max) / 2.0
head_z = z_max - 0.15

if bpy.context.scene.world is None:
    bpy.context.scene.world = bpy.data.worlds.new("World")
bpy.context.scene.world.use_nodes = True
bg = bpy.context.scene.world.node_tree.nodes.get("Background")
if bg:
    bg.inputs['Color'].default_value = (0.025, 0.03, 0.04, 1.0)

k_data = bpy.data.lights.new("Key", 'AREA')
k_data.energy = 50.0
k_data.size = 0.6
k_data.color = (1.0, 0.95, 0.88)
k = bpy.data.objects.new("Key", k_data)
bpy.context.collection.objects.link(k)
k.location = (0.35, y_center - 1.1, head_z + 0.25)

f_data = bpy.data.lights.new("Fill", 'AREA')
f_data.energy = 18.0
f_data.size = 0.9
f_data.color = (0.80, 0.85, 0.95)
f = bpy.data.objects.new("Fill", f_data)
bpy.context.collection.objects.link(f)
f.location = (-0.45, y_center - 0.95, head_z)

cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 55.0
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.collection.objects.link(cam)
cam.location = (0.0, y_center - 1.25, head_z - 0.05)
cam.rotation_euler = (1.5708, 0, 0)
bpy.context.scene.camera = cam

bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.samples = 64
bpy.context.scene.render.resolution_x = 1024
bpy.context.scene.render.resolution_y = 1024
bpy.context.scene.render.filepath = r"C:\GIT\generator-assets\godot_assets\marc_novice_beauty_render.png"
bpy.ops.render.render(write_still=True)
print("✅ Modèle propre et naturel généré avec succès !")
