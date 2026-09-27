# -*- coding: utf-8 -*-
"""
inspect_makehuman_face_uvs.py
Extracts the exact UV coordinates of the key MakeHuman face vertices (eyes, nose, mouth, chin).
"""

import bpy
import importlib
import sys

def dynamic_import(absolute_package_str, key):
    for amod in sys.modules:
        if amod.endswith(absolute_package_str):
            mpfb_mod = importlib.import_module(amod)
            if hasattr(mpfb_mod, key):
                return getattr(mpfb_mod, key)
    raise ValueError(f"Module {absolute_package_str} not found")

bpy.ops.wm.read_factory_settings(use_empty=True)
try:
    bpy.ops.preferences.addon_enable(module="bl_ext.user_default.mpfb")
except Exception:
    pass

HumanService = dynamic_import("mpfb.services.humanservice", "HumanService")
basemesh = HumanService.create_human()

# Key MakeHuman vertices in 3D space:
# We look for vertices at characteristic face positions (Z > 1.3, Y < 0):
mesh = basemesh.data
uv_layer = mesh.uv_layers[0]

# Find the foremost vertex in Y (nose tip)
nose_tip_idx = min(range(len(mesh.vertices)), key=lambda i: mesh.vertices[i].co.y if mesh.vertices[i].co.z > 1.4 and abs(mesh.vertices[i].co.x) < 0.05 else 999)

# Find the mouth (middle of the lips)
mouth_idx = min(range(len(mesh.vertices)), key=lambda i: mesh.vertices[i].co.y if 1.35 < mesh.vertices[i].co.z < 1.42 and abs(mesh.vertices[i].co.x) < 0.02 else 999)

# Find the chin
chin_idx = min(range(len(mesh.vertices)), key=lambda i: mesh.vertices[i].co.y if 1.28 < mesh.vertices[i].co.z < 1.35 and abs(mesh.vertices[i].co.x) < 0.02 else 999)

# Find the left and right eye centers
eye_r_idx = min(range(len(mesh.vertices)), key=lambda i: mesh.vertices[i].co.y if 1.48 < mesh.vertices[i].co.z < 1.55 and -0.06 < mesh.vertices[i].co.x < -0.02 else 999)
eye_l_idx = min(range(len(mesh.vertices)), key=lambda i: mesh.vertices[i].co.y if 1.48 < mesh.vertices[i].co.z < 1.55 and 0.02 < mesh.vertices[i].co.x < 0.06 else 999)

def get_uv_for_vert(v_idx):
    uvs = []
    for poly in mesh.polygons:
        for loop_idx in poly.loop_indices:
            if mesh.loops[loop_idx].vertex_index == v_idx:
                uv = uv_layer.data[loop_idx].uv
                uvs.append((uv.x, uv.y))
    if uvs:
        return (sum(u[0] for u in uvs)/len(uvs), sum(u[1] for u in uvs)/len(uvs))
    return None

print(f"Nose tip 3D (v{nose_tip_idx}): {mesh.vertices[nose_tip_idx].co} -> UV: {get_uv_for_vert(nose_tip_idx)}")
print(f"Mouth center 3D (v{mouth_idx}): {mesh.vertices[mouth_idx].co} -> UV: {get_uv_for_vert(mouth_idx)}")
print(f"Chin 3D (v{chin_idx}): {mesh.vertices[chin_idx].co} -> UV: {get_uv_for_vert(chin_idx)}")
print(f"Right eye 3D (v{eye_r_idx}): {mesh.vertices[eye_r_idx].co} -> UV: {get_uv_for_vert(eye_r_idx)}")
print(f"Left eye 3D (v{eye_l_idx}): {mesh.vertices[eye_l_idx].co} -> UV: {get_uv_for_vert(eye_l_idx)}")

# In pixels on a 2048x2048 texture:
for name, idx in [("Nose", nose_tip_idx), ("Mouth", mouth_idx), ("Chin", chin_idx), ("Right eye", eye_r_idx), ("Left eye", eye_l_idx)]:
    u, v = get_uv_for_vert(idx)
    # In PIL (Y=0 at the top): px = u * 2048, py = (1.0 - v) * 2048
    px = u * 2048.0
    py = (1.0 - v) * 2048.0
    print(f"  PIL pixel {name}: ({px:.1f}, {py:.1f})")
