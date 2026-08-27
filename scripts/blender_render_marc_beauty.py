# -*- coding: utf-8 -*-
"""
Rendu 3D Cinématique de Marc (Complet avec Cheveux, Yeux, Sourcils, Vêtements et Éclairage 3 Points).
"""

import bpy
import mathutils
import os

GLB_MARC = r"C:\test\L'HERITIER DU VIDE\poc_3d\exports\marc_mpfb2.glb"
SORTIE_RENDER = r"C:\GIT\generator-assets\godot_assets\marc_3d_beauty_render.png"

# 1. Scène vierge
bpy.ops.wm.read_factory_settings(use_empty=True)

# 2. Import du modèle GLB complet de Marc
if not os.path.exists(GLB_MARC):
    raise FileNotFoundError(f"GLB Marc introuvable : {GLB_MARC}")

bpy.ops.import_scene.gltf(filepath=GLB_MARC)
print("[MARC RENDER] Modèle 3D complet importé.")

# 3. Calcul du centre et hauteur de la tête
all_objs = [o for o in bpy.data.objects if o.type == 'MESH']
all_verts = []
for o in all_objs:
    mw = o.matrix_world
    for v in o.data.vertices:
        all_verts.append(mw @ v.co)

z_max = max(p.z for p in all_verts)
z_min = min(p.z for p in all_verts)
print(f"[MARC RENDER] Hauteur totale du modèle : {z_max - z_min:.3f} m (Sommet: {z_max:.3f} m)")

head_z = z_max - 0.12  # Hauteur du visage

# 4. Éclairage Studio Cinématique 3 Points (Vent-Gris)
# Key Light (Lumière principale douce)
key_data = bpy.data.lights.new(name="KeyLight", type='AREA')
key_data.energy = 75.0
key_data.size = 0.6
key_data.color = (0.95, 0.96, 1.0)  # Lumière nordique froide
key_obj = bpy.data.objects.new("KeyLight", key_data)
bpy.context.collection.objects.link(key_obj)
key_obj.location = mathutils.Vector((0.35, -0.65, head_z + 0.25))

# Fill Light (Lumière de débouchage douce)
fill_data = bpy.data.lights.new(name="FillLight", type='AREA')
fill_data.energy = 25.0
fill_data.size = 0.9
fill_data.color = (0.88, 0.85, 0.82)
fill_obj = bpy.data.objects.new("FillLight", fill_data)
bpy.context.collection.objects.link(fill_obj)
fill_obj.location = mathutils.Vector((-0.50, -0.55, head_z - 0.05))

# Rim / Hair Light (Lumière rasante arrière pour détacher les cheveux et les épaules)
rim_data = bpy.data.lights.new(name="RimLight", type='AREA')
rim_data.energy = 90.0
rim_data.size = 0.4
rim_data.color = (1.0, 0.92, 0.80)  # Lueur chaude de torche
rim_obj = bpy.data.objects.new("RimLight", rim_data)
bpy.context.collection.objects.link(rim_obj)
rim_obj.location = mathutils.Vector((0.25, 0.50, head_z + 0.35))

# 5. Caméra Portrait / Buste
cam_data = bpy.data.cameras.new("BustCamera")
cam_data.lens = 50.0  # Objectif polyvalent
cam_obj = bpy.data.objects.new("BustCamera", cam_data)
bpy.context.collection.objects.link(cam_obj)

# Cadrage Buste (tête + épaules + haut de la tenue)
cam_obj.location = mathutils.Vector((0.0, -1.35, head_z - 0.10))
cam_obj.rotation_euler = mathutils.Euler((1.5708, 0, 0), 'XYZ')
bpy.context.scene.camera = cam_obj

# 6. Configuration du Rendu Cycles
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.samples = 48
bpy.context.scene.render.resolution_x = 1024
bpy.context.scene.render.resolution_y = 1024
bpy.context.scene.render.filepath = SORTIE_RENDER
bpy.context.scene.render.image_settings.file_format = 'PNG'

# Fond sombre studio
if bpy.context.scene.world is None:
    bpy.context.scene.world = bpy.data.worlds.new("World")
bpy.context.scene.world.use_nodes = True
bg = bpy.context.scene.world.node_tree.nodes.get("Background")
if bg:
    bg.inputs['Color'].default_value = (0.04, 0.04, 0.05, 1.0)

print("[MARC RENDER] Rendu Cycles en cours...")
bpy.ops.render.render(write_still=True)
print(f"✅ [MARC RENDER] Rendu cinématique complet enregistré : {SORTIE_RENDER}")
