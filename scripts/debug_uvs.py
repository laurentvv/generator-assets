# -*- coding: utf-8 -*-
import bpy
import importlib
import numpy as np
import sys

bpy.ops.wm.read_factory_settings(use_empty=True)
try:
    bpy.ops.preferences.addon_enable(module='bl_ext.user_default.mpfb')
except Exception:
    pass

for amod in sys.modules:
    if amod.endswith('mpfb.services.humanservice'):
        HumanService = getattr(importlib.import_module(amod), 'HumanService')
        break

basemesh = HumanService.create_human()
mesh = basemesh.data
uv_layer = mesh.uv_layers.active.data

# Vertices de la tête : front, yeux, nez, bouche, menton
head_v_indices = set(i for i, v in enumerate(mesh.vertices) if v.co.z > 1.35)
face_uvs = []
for poly in mesh.polygons:
    if any(vi in head_v_indices for vi in poly.vertices):
        for li in poly.loop_indices:
            face_uvs.append(uv_layer[li].uv)

face_uvs = np.array(face_uvs)
print("=" * 60)
print(f"Total UV loops head: {len(face_uvs)}")
u_min, u_max = np.min(face_uvs[:, 0]), np.max(face_uvs[:, 0])
v_min, v_max = np.min(face_uvs[:, 1]), np.max(face_uvs[:, 1])

# Dans les images 2D (PIL/PNG), Y=0 est en HAUT, donc Y_img = (1 - V) * 2048
print(f"UV U Range: [{u_min:.4f}, {u_max:.4f}] -> Pixels X (sur 2048): [{u_min*2048:.1f}, {u_max*2048:.1f}]")
print(f"UV V Range: [{v_min:.4f}, {v_max:.4f}] -> Pixels Y (sur 2048 depuis le haut): [{(1 - v_max)*2048:.1f}, {(1 - v_min)*2048:.1f}]")

# Localisation exacte des yeux (sommet nez vs yeux)
eye_v = [v for v in mesh.vertices if 1.55 < v.co.z < 1.63 and v.co.y > 0.05]
print(f"Yeux vertices count: {len(eye_v)}")
eye_uvs = []
for poly in mesh.polygons:
    if any(v in eye_v for v in [mesh.vertices[vi] for vi in poly.vertices]):
        for li in poly.loop_indices:
            eye_uvs.append(uv_layer[li].uv)
if eye_uvs:
    eye_uvs = np.array(eye_uvs)
    print(f"Yeux Pixels X (sur 2048): [{np.min(eye_uvs[:, 0])*2048:.1f}, {np.max(eye_uvs[:, 0])*2048:.1f}]")
    print(f"Yeux Pixels Y (sur 2048 depuis le haut): [{(1 - np.max(eye_uvs[:, 1]))*2048:.1f}, {(1 - np.min(eye_uvs[:, 1]))*2048:.1f}]")

# Localisation de la bouche
mouth_v = [v for v in mesh.vertices if 1.40 < v.co.z < 1.48 and v.co.y > 0.08]
mouth_uvs = []
for poly in mesh.polygons:
    if any(v in mouth_v for v in [mesh.vertices[vi] for vi in poly.vertices]):
        for li in poly.loop_indices:
            mouth_uvs.append(uv_layer[li].uv)
if mouth_uvs:
    mouth_uvs = np.array(mouth_uvs)
    print(f"Bouche Pixels X (sur 2048): [{np.min(mouth_uvs[:, 0])*2048:.1f}, {np.max(mouth_uvs[:, 0])*2048:.1f}]")
    print(f"Bouche Pixels Y (sur 2048 depuis le haut): [{(1 - np.max(mouth_uvs[:, 1]))*2048:.1f}, {(1 - np.min(mouth_uvs[:, 1]))*2048:.1f}]")
print("=" * 60)
