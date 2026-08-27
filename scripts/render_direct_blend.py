# -*- coding: utf-8 -*-
"""
render_direct_blend.py
Rendu studio Cycles direct depuis la scène .blend native avec les shaders PBR.
"""

import bpy
import mathutils

BLEND_FILE = r"C:\GIT\generator-assets\godot_assets\marc_novice.blend"
OUT_PNG = r"C:\GIT\generator-assets\godot_assets\marc_novice_beauty_render.png"

bpy.ops.wm.open_mainfile(filepath=BLEND_FILE)

# Setup de studio
all_objs = [o for o in bpy.data.objects if o.type == 'MESH']
all_verts = [o.matrix_world @ v.co for o in all_objs for v in o.data.vertices]
z_max = max(p.z for p in all_verts)
y_min = min(p.y for p in all_verts)
y_max = max(p.y for p in all_verts)
y_center = (y_min + y_max) / 2.0
head_z = z_max - 0.15

if bpy.context.scene.world is None:
    bpy.context.scene.world = bpy.data.worlds.new("World")
bpy.context.scene.world.use_nodes = True
bg = bpy.context.scene.world.node_tree.nodes.get("Background")
if bg:
    bg.inputs['Color'].default_value = (0.02, 0.025, 0.03, 1.0)

# Lights
k_data = bpy.data.lights.new("Key", 'AREA')
k_data.energy = 45.0
k_data.size = 0.6
k_data.color = (1.0, 0.95, 0.88)
k = bpy.data.objects.new("Key", k_data)
bpy.context.collection.objects.link(k)
k.location = (0.35, y_center - 1.1, head_z + 0.25)

f_data = bpy.data.lights.new("Fill", 'AREA')
f_data.energy = 16.0
f_data.size = 0.8
f_data.color = (0.80, 0.85, 0.95)
f = bpy.data.objects.new("Fill", f_data)
bpy.context.collection.objects.link(f)
f.location = (-0.45, y_center - 0.95, head_z)

# Camera cadrant torse + tête
cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 50.0
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.collection.objects.link(cam)
cam.location = (0.0, y_center - 1.25, head_z - 0.12)
cam.rotation_euler = (1.5708, 0, 0)
bpy.context.scene.camera = cam

bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.samples = 64
bpy.context.scene.render.resolution_x = 1024
bpy.context.scene.render.resolution_y = 1024
bpy.context.scene.render.filepath = OUT_PNG
bpy.ops.render.render(write_still=True)
print(f"✅ Rendu studio direct terminé : {OUT_PNG}")
