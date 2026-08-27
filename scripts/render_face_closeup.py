# -*- coding: utf-8 -*-
"""
render_face_closeup.py
Rendu gros plan (Face Close-Up) pour valider la netteté des cicatrices et détails du visage.
"""

import bpy
import mathutils
import os

GLB_PATH = r"C:\GIT\generator-assets\godot_assets\marc_novice.glb"
OUT_PNG = r"C:\GIT\generator-assets\godot_assets\marc_novice_face_closeup.png"

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB_PATH)

all_objs = [o for o in bpy.data.objects if o.type == 'MESH']
all_verts = [o.matrix_world @ v.co for o in all_objs for v in o.data.vertices]
z_max = max(p.z for p in all_verts)
y_min = min(p.y for p in all_verts)
y_max = max(p.y for p in all_verts)
y_center = (y_min + y_max) / 2.0
head_z = z_max - 0.15

# World
if bpy.context.scene.world is None:
    bpy.context.scene.world = bpy.data.worlds.new("World")
bg = bpy.context.scene.world.node_tree.nodes.get("Background")
if bg:
    bg.inputs['Color'].default_value = (0.02, 0.025, 0.03, 1.0)

# Lumière Key
k_data = bpy.data.lights.new("Key", 'AREA')
k_data.energy = 35.0
k_data.size = 0.4
k_data.color = (1.0, 0.96, 0.90)
k = bpy.data.objects.new("Key", k_data)
bpy.context.collection.objects.link(k)
k.location = (0.25, y_center - 0.70, head_z + 0.15)

# Lumière Fill
f_data = bpy.data.lights.new("Fill", 'AREA')
f_data.energy = 12.0
f_data.size = 0.6
f_data.color = (0.80, 0.85, 0.95)
f = bpy.data.objects.new("Fill", f_data)
bpy.context.collection.objects.link(f)
f.location = (-0.30, y_center - 0.60, head_z - 0.05)

# Caméra Gros Plan (Portrait serré)
cam_data = bpy.data.cameras.new("CloseUpCam")
cam_data.lens = 85.0
cam = bpy.data.objects.new("CloseUpCam", cam_data)
bpy.context.collection.objects.link(cam)
cam.location = (0.0, y_center - 0.65, head_z - 0.02)
cam.rotation_euler = (1.5708, 0, 0)
bpy.context.scene.camera = cam

bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.samples = 64
bpy.context.scene.render.resolution_x = 1024
bpy.context.scene.render.resolution_y = 1024
bpy.context.scene.render.filepath = OUT_PNG
bpy.ops.render.render(write_still=True)
print(f"✅ Rendu gros plan enregistré : {OUT_PNG}")
