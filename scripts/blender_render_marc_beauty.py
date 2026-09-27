# -*- coding: utf-8 -*-
"""
Cinematic 3D render of Marc (complete with hair, eyes, eyebrows, clothing and 3-point lighting).
"""

import bpy
import mathutils
import os

GLB_MARC = r"C:\test\L'HERITIER DU VIDE\poc_3d\exports\marc_mpfb2.glb"
SORTIE_RENDER = r"C:\GIT\generator-assets\godot_assets\marc_3d_beauty_render.png"

# 1. Blank scene
bpy.ops.wm.read_factory_settings(use_empty=True)

# 2. Import of Marc's complete GLB model
if not os.path.exists(GLB_MARC):
    raise FileNotFoundError(f"Marc GLB not found: {GLB_MARC}")

bpy.ops.import_scene.gltf(filepath=GLB_MARC)
print("[MARC RENDER] Complete 3D model imported.")

# 3. Compute head center and height
all_objs = [o for o in bpy.data.objects if o.type == 'MESH']
all_verts = []
for o in all_objs:
    mw = o.matrix_world
    for v in o.data.vertices:
        all_verts.append(mw @ v.co)

z_max = max(p.z for p in all_verts)
z_min = min(p.z for p in all_verts)
print(f"[MARC RENDER] Total model height: {z_max - z_min:.3f} m (Top: {z_max:.3f} m)")

head_z = z_max - 0.12  # Face height

# 4. Cinematic studio 3-point lighting (Grey Wind)
# Key Light (soft main light)
key_data = bpy.data.lights.new(name="KeyLight", type='AREA')
key_data.energy = 75.0
key_data.size = 0.6
key_data.color = (0.95, 0.96, 1.0)  # Cold Nordic light
key_obj = bpy.data.objects.new("KeyLight", key_data)
bpy.context.collection.objects.link(key_obj)
key_obj.location = mathutils.Vector((0.35, -0.65, head_z + 0.25))

# Fill Light (soft fill light)
fill_data = bpy.data.lights.new(name="FillLight", type='AREA')
fill_data.energy = 25.0
fill_data.size = 0.9
fill_data.color = (0.88, 0.85, 0.82)
fill_obj = bpy.data.objects.new("FillLight", fill_data)
bpy.context.collection.objects.link(fill_obj)
fill_obj.location = mathutils.Vector((-0.50, -0.55, head_z - 0.05))

# Rim / Hair Light (rear grazing light to separate hair and shoulders)
rim_data = bpy.data.lights.new(name="RimLight", type='AREA')
rim_data.energy = 90.0
rim_data.size = 0.4
rim_data.color = (1.0, 0.92, 0.80)  # Warm torch glow
rim_obj = bpy.data.objects.new("RimLight", rim_data)
bpy.context.collection.objects.link(rim_obj)
rim_obj.location = mathutils.Vector((0.25, 0.50, head_z + 0.35))

# 5. Portrait / Bust camera
cam_data = bpy.data.cameras.new("BustCamera")
cam_data.lens = 50.0  # All-purpose lens
cam_obj = bpy.data.objects.new("BustCamera", cam_data)
bpy.context.collection.objects.link(cam_obj)

# Bust framing (head + shoulders + top of the outfit)
cam_obj.location = mathutils.Vector((0.0, -1.35, head_z - 0.10))
cam_obj.rotation_euler = mathutils.Euler((1.5708, 0, 0), 'XYZ')
bpy.context.scene.camera = cam_obj

# 6. Cycles render configuration
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.samples = 48
bpy.context.scene.render.resolution_x = 1024
bpy.context.scene.render.resolution_y = 1024
bpy.context.scene.render.filepath = SORTIE_RENDER
bpy.context.scene.render.image_settings.file_format = 'PNG'

# Dark studio background
if bpy.context.scene.world is None:
    bpy.context.scene.world = bpy.data.worlds.new("World")
bpy.context.scene.world.use_nodes = True
bg = bpy.context.scene.world.node_tree.nodes.get("Background")
if bg:
    bg.inputs['Color'].default_value = (0.04, 0.04, 0.05, 1.0)

print("[MARC RENDER] Cycles render in progress...")
bpy.ops.render.render(write_still=True)
print(f"✅ [MARC RENDER] Full cinematic render saved: {SORTIE_RENDER}")
