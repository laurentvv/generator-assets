# -*- coding: utf-8 -*-
"""
bake_portrait_projection.py
Projection de caméra frontale 3D et bake direct sur la carte UV MakeHuman.
Fini le découpage 2D approximatif : Blender projette lui-même les coordonnées 3D exactes !
"""

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

PORTRAIT_PATH = r"C:\test\L'HERITIER DU VIDE\assets\portraits\marc_portrait.png"
OUT_SKIN_DIFF = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\marc_novice\marc_novice_diffuse.png"
OUT_SKIN_NORM = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\marc_novice\marc_novice_normal.png"
BASE_SKIN_PATH = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\young_caucasian_male\young_lightskinned_male_diffuse.png"

# 1. Scène vierge
bpy.ops.wm.read_factory_settings(use_empty=True)
try:
    bpy.ops.preferences.addon_enable(module="bl_ext.user_default.mpfb")
except Exception:
    pass

HumanService = dynamic_import("mpfb.services.humanservice", "HumanService")
TargetService = dynamic_import("mpfb.services.targetservice", "TargetService")

# Création du corps enfant
macros = {
    "gender": 1.0, "age": 0.18, "muscle": 0.30, "weight": 0.25,
    "proportions": 0.50, "height": 0.50,
    "race": {"caucasian": 1.0, "asian": 0.0, "african": 0.0}
}
basemesh = HumanService.create_human(macro_detail_dict=macros)
TargetService.reapply_macro_details(basemesh)
bpy.context.view_layer.update()

# Suppression des sommets d'aide MakeHuman pour ne garder que la peau
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

# Bake shape keys pour figer la morphologie enfant
dg = bpy.context.evaluated_depsgraph_get()
ev = basemesh.evaluated_get(dg)
me = bpy.data.meshes.new_from_object(ev)
old = basemesh.data
basemesh.data = me
me.name = old.name
bpy.data.meshes.remove(old)

# 2. Calcul du centre de la tête
head_verts = [v.co for v in basemesh.data.vertices if v.co.z > 0.95]
head_z = sum(v.z for v in head_verts) / len(head_verts)
head_y = sum(v.y for v in head_verts) / len(head_verts)
head_x = sum(v.x for v in head_verts) / len(head_verts)
head_height = max(v.z for v in head_verts) - min(v.z for v in head_verts)

print(f"Centre tête : X={head_x:.3f}, Y={head_y:.3f}, Z={head_z:.3f}, Hauteur={head_height:.3f}m")

# 3. Caméra Orthographique frontale alignée précisément sur le visage
cam_data = bpy.data.cameras.new("ProjectCam")
cam_data.type = 'ORTHO'
cam_data.ortho_scale = head_height * 1.55  # Cadrage parfait du visage et du cou
cam_obj = bpy.data.objects.new("ProjectCam", cam_data)
bpy.context.collection.objects.link(cam_obj)
cam_obj.location = (head_x, head_y - 1.5, head_z - 0.02)
cam_obj.rotation_euler = (1.5708, 0, 0)
bpy.context.scene.camera = cam_obj
bpy.context.view_layer.update()

# 4. Projection UV mathématique directe depuis la vue caméra frontale
# Pour chaque face/sommet : on projette les coordonnées X et Z du monde dans l'espace caméra [0..1]
orig_uv = basemesh.data.uv_layers[0].name
proj_uv = basemesh.data.uv_layers.new(name="UV_Portrait_Front")

ortho_scale = head_height * 1.50
cam_min_x = head_x - ortho_scale / 2.0
cam_min_z = head_z - ortho_scale / 2.0

for loop in basemesh.data.loops:
    vert = basemesh.data.vertices[loop.vertex_index]
    u = (vert.co.x - cam_min_x) / ortho_scale
    v = (vert.co.z - cam_min_z) / ortho_scale
    proj_uv.data[loop.index].uv = (u, v)

basemesh.data.uv_layers.active = basemesh.data.uv_layers[orig_uv]
bpy.context.view_layer.update()

# 5. Shader de fusion et Bake sur la carte UV native
# Matériau de projection
mat_bake = bpy.data.materials.new(name="Mat_Bake_Portrait")
mat_bake.use_nodes = True
nodes = mat_bake.node_tree.nodes
links = mat_bake.node_tree.links
nodes.clear()

out = nodes.new('ShaderNodeOutputMaterial')
emit = nodes.new('ShaderNodeEmission')
links.new(emit.outputs['Emission'], out.inputs['Surface'])

# Image source : Portrait 2D de Marc
img_portrait = bpy.data.images.load(PORTRAIT_PATH, check_existing=False)
node_port = nodes.new('ShaderNodeTexImage')
node_port.image = img_portrait
node_port.extension = 'CLIP'

# Coordonnées UV de la projection frontale
node_uv_proj = nodes.new('ShaderNodeUVMap')
node_uv_proj.uv_map = "UV_Portrait_Front"
links.new(node_uv_proj.outputs['UV'], node_port.inputs['Vector'])

# Image de base MakeHuman (corps)
img_base = bpy.data.images.load(BASE_SKIN_PATH, check_existing=False)
node_base = nodes.new('ShaderNodeTexImage')
node_base.image = img_base
node_uv_orig = nodes.new('ShaderNodeUVMap')
node_uv_orig.uv_map = orig_uv
links.new(node_uv_orig.outputs['UV'], node_base.inputs['Vector'])

# Assombrir et patiner la peau de base (Vent-Gris)
node_curves = nodes.new('ShaderNodeRGBCurve')
node_curves.mapping.curves[3].points[0].location = (0.0, 0.0)
node_curves.mapping.curves[3].points[1].location = (1.0, 0.82)  # -18% de luminosité globale
links.new(node_base.outputs['Color'], node_curves.inputs['Color'])

# Mix : le portrait sur la face avant (Normale Y négative), la peau de base sur l'arrière et le corps
node_geom = nodes.new('ShaderNodeNewGeometry')
node_dot = nodes.new('ShaderNodeVectorMath')
node_dot.operation = 'DOT_PRODUCT'
node_dot.inputs[1].default_value = (0.0, -1.0, 0.0)  # Face vers l'avant (-Y)
links.new(node_geom.outputs['Normal'], node_dot.inputs[0])

# Masque de mixage adouci
node_ramp = nodes.new('ShaderNodeValToRGB')
node_ramp.color_ramp.elements[0].position = 0.25
node_ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
node_ramp.color_ramp.elements[1].position = 0.70
node_ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
links.new(node_dot.outputs['Value'], node_ramp.inputs['Fac'])

# Mix RGB
node_mix = nodes.new('ShaderNodeMix')
node_mix.data_type = 'RGBA'
links.new(node_ramp.outputs['Color'], node_mix.inputs['Factor'])
links.new(node_curves.outputs['Color'], node_mix.inputs['A'])
links.new(node_port.outputs['Color'], node_mix.inputs['B'])
links.new(node_mix.outputs['Result'], emit.inputs['Color'])

# Image de destination pour le BAKE (2048x2048)
img_baked = bpy.data.images.new(name="Marc_Baked_Diffuse", width=2048, height=2048, alpha=False)
node_bake_target = nodes.new('ShaderNodeTexImage')
node_bake_target.image = img_baked
nodes.active = node_bake_target

basemesh.data.materials.clear()
basemesh.data.materials.append(mat_bake)

# 6. Exécution du BAKE avec Cycles
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.samples = 1
bpy.context.scene.cycles.bake_type = 'EMIT'
bpy.context.scene.render.bake.use_selected_to_active = False
bpy.context.scene.render.bake.margin = 16

print("🔥 Lancement du Bake Cycles de la texture UV MakeHuman...")
bpy.ops.object.bake(type='EMIT')
print("✅ Bake terminé !")

# Sauvegarde de la texture Diffuse cuite
os.makedirs(os.path.dirname(OUT_SKIN_DIFF), exist_ok=True)
img_baked.filepath_raw = OUT_SKIN_DIFF
img_baked.file_format = 'PNG'
img_baked.save()

local_diff = r"C:\GIT\generator-assets\godot_assets\skins\marc_novice\marc_novice_diffuse.png"
os.makedirs(os.path.dirname(local_diff), exist_ok=True)
img_baked.filepath_raw = local_diff
img_baked.save()

print(f"✅ Texture UV MakeHuman parfaitement dépliée et enregistrée : {OUT_SKIN_DIFF}")
