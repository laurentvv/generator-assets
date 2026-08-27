# -*- coding: utf-8 -*-
"""
inspect_makehuman_face_uvs.py
Extrait les coordonnées UV exactes des sommets clés du visage MakeHuman (yeux, nez, bouche, menton).
"""

import bpy
import bmesh
import importlib
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
basemesh = HumanService.create_human()

# Sommets clés MakeHuman dans l'espace 3D :
# On cherche les sommets aux positions caractéristiques de la face (Z > 1.3, Y < 0) :
mesh = basemesh.data
uv_layer = mesh.uv_layers[0]

# Trouver le sommet le plus en avant en Y (bout du nez)
nose_tip_idx = min(range(len(mesh.vertices)), key=lambda i: mesh.vertices[i].co.y if mesh.vertices[i].co.z > 1.4 and abs(mesh.vertices[i].co.x) < 0.05 else 999)

# Trouver la bouche (milieu des lèvres)
mouth_idx = min(range(len(mesh.vertices)), key=lambda i: mesh.vertices[i].co.y if 1.35 < mesh.vertices[i].co.z < 1.42 and abs(mesh.vertices[i].co.x) < 0.02 else 999)

# Trouver le menton
chin_idx = min(range(len(mesh.vertices)), key=lambda i: mesh.vertices[i].co.y if 1.28 < mesh.vertices[i].co.z < 1.35 and abs(mesh.vertices[i].co.x) < 0.02 else 999)

# Trouver les centres des yeux gauche et droit
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

print(f"Bout du nez 3D (v{nose_tip_idx}) : {mesh.vertices[nose_tip_idx].co} -> UV: {get_uv_for_vert(nose_tip_idx)}")
print(f"Bouche centre 3D (v{mouth_idx}) : {mesh.vertices[mouth_idx].co} -> UV: {get_uv_for_vert(mouth_idx)}")
print(f"Menton 3D (v{chin_idx}) : {mesh.vertices[chin_idx].co} -> UV: {get_uv_for_vert(chin_idx)}")
print(f"Oeil Droit 3D (v{eye_r_idx}) : {mesh.vertices[eye_r_idx].co} -> UV: {get_uv_for_vert(eye_r_idx)}")
print(f"Oeil Gauche 3D (v{eye_l_idx}) : {mesh.vertices[eye_l_idx].co} -> UV: {get_uv_for_vert(eye_l_idx)}")

# En pixels sur une texture 2048x2048 :
for name, idx in [("Nez", nose_tip_idx), ("Bouche", mouth_idx), ("Menton", chin_idx), ("Oeil Droit", eye_r_idx), ("Oeil Gauche", eye_l_idx)]:
    u, v = get_uv_for_vert(idx)
    # Dans PIL (Y=0 en haut) : px = u * 2048, py = (1.0 - v) * 2048
    px = u * 2048.0
    py = (1.0 - v) * 2048.0
    print(f"  Pixel PIL {name} : ({px:.1f}, {py:.1f})")
