# -*- coding: utf-8 -*-
"""
Rendu 3D Closeup du Visage de Marc avec la Texture UV Projetée.
"""

import bpy
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

TEXTURE_DIFFUSE = r"C:\GIT\generator-assets\godot_assets\skins\marc_novice\marc_novice_diffuse.png"
SORTIE_RENDER = r"C:\GIT\generator-assets\godot_assets\marc_3d_projected_render.png"

bpy.ops.wm.read_factory_settings(use_empty=True)
try:
    bpy.ops.preferences.addon_enable(module="bl_ext.user_default.mpfb")
except Exception:
    pass

HumanService = dynamic_import("mpfb.services.humanservice", "HumanService")
AssetService = dynamic_import("mpfb.services.assetservice", "AssetService")
TargetService = dynamic_import("mpfb.services.targetservice", "TargetService")

macros_marc = {
    "gender": 1.0,
    "age": 0.17,
    "muscle": 0.3,
    "weight": 0.25,
    "proportions": 0.5,
    "height": 0.5,
    "race": {"caucasian": 1.0, "asian": 0.0, "african": 0.0}
}
basemesh = HumanService.create_human(macro_detail_dict=macros_marc)
TargetService.reapply_macro_details(basemesh)
bpy.context.view_layer.update()

# Bake shape keys
dg = bpy.context.evaluated_depsgraph_get()
ev = basemesh.evaluated_get(dg)
me = bpy.data.meshes.new_from_object(ev)
old_me = basemesh.data
basemesh.data = me
me.name = "marc_basemesh_mesh"
bpy.data.meshes.remove(old_me)
bpy.context.view_layer.update()

for m in list(basemesh.modifiers):
    if m.type == 'MASK':
        basemesh.modifiers.remove(m)

# Matériau avec la texture diffusée baktée
mat = bpy.data.materials.new(name="Marc_Skin_Baked_Render")
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links
nodes.clear()

out_node = nodes.new('ShaderNodeOutputMaterial')
bsdf = nodes.new('ShaderNodeBsdfPrincipled')
bsdf.inputs['Roughness'].default_value = 0.50

img = bpy.data.images.load(TEXTURE_DIFFUSE, check_existing=False)
tex_node = nodes.new('ShaderNodeTexImage')
tex_node.image = img

links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
links.new(bsdf.outputs['BSDF'], out_node.inputs['Surface'])

basemesh.data.materials.clear()
basemesh.data.materials.append(mat)

# Yeux
eyes_path = AssetService.find_asset_absolute_path("low-poly.mhclo", asset_subdir="eyes")
if eyes_path:
    HumanService.add_mhclo_asset(eyes_path, basemesh, asset_type="Eyes", material_type="GAMEENGINE")

# Calcul centre tête
head_verts = [v for v in basemesh.data.vertices if v.co.z > 0.85]
center_x = sum(v.co.x for v in head_verts) / len(head_verts)
center_y = sum(v.co.y for v in head_verts) / len(head_verts)
center_z = sum(v.co.z for v in head_verts) / len(head_verts)

# Lumière Studio
light_key = bpy.data.lights.new(name="KeyLight", type='AREA')
light_key.energy = 120.0
light_key.size = 0.8
obj_key = bpy.data.objects.new("KeyLight", light_key)
bpy.context.collection.objects.link(obj_key)
obj_key.location = mathutils.Vector((center_x + 0.35, center_y - 0.6, center_z + 0.25))

light_fill = bpy.data.lights.new(name="FillLight", type='AREA')
light_fill.energy = 40.0
light_fill.size = 1.0
obj_fill = bpy.data.objects.new("FillLight", light_fill)
bpy.context.collection.objects.link(obj_fill)
obj_fill.location = mathutils.Vector((center_x - 0.45, center_y - 0.5, center_z))

# Caméra Close-up Portrait
cam_data = bpy.data.cameras.new("PortraitCam")
cam_data.lens = 90.0
cam_obj = bpy.data.objects.new("PortraitCam", cam_data)
bpy.context.collection.objects.link(cam_obj)
cam_obj.location = mathutils.Vector((center_x, center_y - 0.52, center_z))
cam_obj.rotation_euler = mathutils.Euler((1.5708, 0, 0), 'XYZ')
bpy.context.scene.camera = cam_obj

# Rendu EEVEE Next / Cycles
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.samples = 32
bpy.context.scene.render.resolution_x = 1024
bpy.context.scene.render.resolution_y = 1024
bpy.context.scene.render.filepath = SORTIE_RENDER
bpy.context.scene.render.image_settings.file_format = 'PNG'

print("[MARC RENDER] Rendu du portrait 3D en cours...")
bpy.ops.render.render(write_still=True)
print(f"✅ [MARC RENDER] Rendu terminé : {SORTIE_RENDER}")
