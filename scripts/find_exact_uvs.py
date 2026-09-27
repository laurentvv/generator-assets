# -*- coding: utf-8 -*-
import bpy
import bmesh
import importlib
import mathutils
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

mesh = basemesh.data
uv_layer = mesh.uv_layers[0]

# Facial vertices on the clean basemesh
# We scan the head faces
for poly in mesh.polygons:
    face_verts = [mesh.vertices[vi] for vi in poly.vertices]
    avg_co = sum((v.co for v in face_verts), mathutils.Vector()) / len(face_verts)
    if avg_co.z > 1.48 and abs(avg_co.x) < 0.01 and avg_co.y < -0.15:
        # Nose
        loop_idx = poly.loop_indices[0]
        uv = uv_layer.data[loop_idx].uv
        print(f"Nose: 3D {avg_co} -> UV: ({uv.x:.4f}, {uv.y:.4f}) -> PIL px: ({uv.x*2048:.1f}, {(1-uv.y)*2048:.1f})")
        break

for poly in mesh.polygons:
    face_verts = [mesh.vertices[vi] for vi in poly.vertices]
    avg_co = sum((v.co for v in face_verts), mathutils.Vector()) / len(face_verts)
    if 1.37 < avg_co.z < 1.40 and abs(avg_co.x) < 0.01 and avg_co.y < -0.10:
        # Mouth
        loop_idx = poly.loop_indices[0]
        uv = uv_layer.data[loop_idx].uv
        print(f"Mouth: 3D {avg_co} -> UV: ({uv.x:.4f}, {uv.y:.4f}) -> PIL px: ({uv.x*2048:.1f}, {(1-uv.y)*2048:.1f})")
        break

for poly in mesh.polygons:
    face_verts = [mesh.vertices[vi] for vi in poly.vertices]
    avg_co = sum((v.co for v in face_verts), mathutils.Vector()) / len(face_verts)
    if 1.51 < avg_co.z < 1.55 and 0.02 < avg_co.x < 0.05 and avg_co.y < -0.10:
        # Left eye
        loop_idx = poly.loop_indices[0]
        uv = uv_layer.data[loop_idx].uv
        print(f"Left eye: 3D {avg_co} -> UV: ({uv.x:.4f}, {uv.y:.4f}) -> PIL px: ({uv.x*2048:.1f}, {(1-uv.y)*2048:.1f})")
        break

for poly in mesh.polygons:
    face_verts = [mesh.vertices[vi] for vi in poly.vertices]
    avg_co = sum((v.co for v in face_verts), mathutils.Vector()) / len(face_verts)
    if 1.51 < avg_co.z < 1.55 and -0.05 < avg_co.x < -0.02 and avg_co.y < -0.10:
        # Right eye
        loop_idx = poly.loop_indices[0]
        uv = uv_layer.data[loop_idx].uv
        print(f"Right eye: 3D {avg_co} -> UV: ({uv.x:.4f}, {uv.y:.4f}) -> PIL px: ({uv.x*2048:.1f}, {(1-uv.y)*2048:.1f})")
        break
