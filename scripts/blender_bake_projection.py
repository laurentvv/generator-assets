# -*- coding: utf-8 -*-
"""
Blender Headless script (pure bpy): Camera Projection with Marc's real 2D portrait.
Uses the UV_PROJECT modifier for a mathematically exact perspective/orthographic projection.
"""

import bpy
import importlib
import math
import mathutils
import os
import sys

def dynamic_import(absolute_package_str, key):
    for amod in sys.modules:
        if amod.endswith(absolute_package_str):
            mpfb_mod = importlib.import_module(amod)
            if hasattr(mpfb_mod, key):
                return getattr(mpfb_mod, key)
    raise ValueError(f"Module {absolute_package_str} not found")

PORTRAIT_2D_ENHANCED = r"C:\test\L'HERITIER DU VIDE\assets\characters\marc_canonical_enhanced.png"
PORTRAIT_2D_PORTRAIT = r"C:\test\L'HERITIER DU VIDE\assets\portraits\marc_portrait.png"

PORTRAIT_2D = PORTRAIT_2D_ENHANCED if os.path.exists(PORTRAIT_2D_ENHANCED) else PORTRAIT_2D_PORTRAIT
TEMP_BAKE_OUTPUT = r"C:\GIT\generator-assets\godot_assets\temp_marc_baked_face.png"

print("\n" + "=" * 65)
print(" 🚀 BLENDER CAMERA PROJECTION: MARC'S REAL CANONICAL 2D PORTRAIT ")
print(f" 👤 Authentic 2D source: {PORTRAIT_2D}")
print("=" * 65)

# 1. Blank scene & MPFB2 activation
bpy.ops.wm.read_factory_settings(use_empty=True)
try:
    bpy.ops.preferences.addon_enable(module="bl_ext.user_default.mpfb")
except Exception as e:
    print(f"Note MPFB: {e}")

HumanService = dynamic_import("mpfb.services.humanservice", "HumanService")
TargetService = dynamic_import("mpfb.services.targetservice", "TargetService")

# 2. Child Marc morphology (8 years old, 1.18m)
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

# Bake of the shape keys
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

# 3. Precise computation of the facial landmarks
head_verts = [v for v in basemesh.data.vertices if v.co.z > 0.85]
center_x = sum(v.co.x for v in head_verts) / len(head_verts)
center_y = sum(v.co.y for v in head_verts) / len(head_verts)
center_z = sum(v.co.z for v in head_verts) / len(head_verts)

# Measure the head height
z_min_head = min(v.co.z for v in head_verts)
z_max_head = max(v.co.z for v in head_verts)
head_height = z_max_head - z_min_head
print(f"[MARC] Head detected: X={center_x:.3f}, Y={center_y:.3f}, Z={center_z:.3f}, Height={head_height:.3f}m")

# 4. Orthographic/portrait projection camera perfectly framed
cam_data = bpy.data.cameras.new("FaceProjectionCamera")
cam_data.type = 'ORTHO'
cam_data.ortho_scale = head_height * 1.35  # Frames exactly from chin to top of skull

cam_obj = bpy.data.objects.new("FaceProjectionCamera", cam_data)
bpy.context.collection.objects.link(cam_obj)
# Placed right in front of the nose
cam_obj.location = mathutils.Vector((center_x, center_y - 0.80, center_z - 0.02))
cam_obj.rotation_euler = mathutils.Euler((math.radians(90), 0, 0), 'XYZ')
bpy.context.view_layer.update()

# 5. Creation of the projected UV layer
if "UVMap_Projected" in basemesh.data.uv_layers:
    basemesh.data.uv_layers.remove(basemesh.data.uv_layers["UVMap_Projected"])
uv_proj = basemesh.data.uv_layers.new(name="UVMap_Projected")

# 6. UV Project modifier (exact projection without distortion)
mod_uv = basemesh.modifiers.new(name="UVProject", type='UV_PROJECT')
mod_uv.uv_layer = "UVMap_Projected"
mod_uv.projectors[0].object = cam_obj
mod_uv.aspect_x = 1.0
mod_uv.aspect_y = 1.0
mod_uv.scale_x = 1.0
mod_uv.scale_y = 1.0
bpy.context.view_layer.update()

# 7. Target image for the Bake (2048x2048)
bake_res = 2048
img_bake = bpy.data.images.new("Marc_Bake_Target", width=bake_res, height=bake_res, alpha=True)
img_portrait = bpy.data.images.load(PORTRAIT_2D, check_existing=False)

# 8. Bake material
mat_proj = bpy.data.materials.new(name="Marc_Projection_Material")
mat_proj.use_nodes = True
nodes = mat_proj.node_tree.nodes
links = mat_proj.node_tree.links
nodes.clear()

out_node = nodes.new('ShaderNodeOutputMaterial')
emit_node = nodes.new('ShaderNodeEmission')

uv_node = nodes.new('ShaderNodeUVMap')
uv_node.uv_map = "UVMap_Projected"

tex_portrait = nodes.new('ShaderNodeTexImage')
tex_portrait.image = img_portrait
tex_portrait.extension = 'CLIP'

tex_target = nodes.new('ShaderNodeTexImage')
tex_target.image = img_bake
tex_target.select = True
nodes.active = tex_target

links.new(uv_node.outputs['UV'], tex_portrait.inputs['Vector'])
links.new(tex_portrait.outputs['Color'], emit_node.inputs['Color'])
links.new(emit_node.outputs['Emission'], out_node.inputs['Surface'])

basemesh.data.materials.clear()
basemesh.data.materials.append(mat_proj)

# Ensure the first UVMap (base hm08) stays the active render one
basemesh.data.uv_layers[0].active = True
basemesh.data.uv_layers[0].active_render = True

# 9. Launch of the Cycles EMIT bake
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.samples = 1
bpy.context.scene.cycles.bake_type = 'EMIT'
bpy.context.scene.render.bake.margin = 16

bpy.context.view_layer.objects.active = basemesh
basemesh.select_set(True)

print("[MARC BAKE] Starting exact UV baking...")
bpy.ops.object.bake(type='EMIT')

os.makedirs(os.path.dirname(TEMP_BAKE_OUTPUT), exist_ok=True)
img_bake.filepath_raw = TEMP_BAKE_OUTPUT
img_bake.file_format = 'PNG'
img_bake.save()
print(f"✅ [MARC BAKE] Projected texture saved: {TEMP_BAKE_OUTPUT}")
