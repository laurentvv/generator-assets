# -*- coding: utf-8 -*-
import bpy
import bmesh
import importlib
import os
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
print("Vertices initiaux :", len(basemesh.data.vertices))

# Suppression des sommets d'aide internes (HelperGeometry)
helper_vg = basemesh.vertex_groups.get("HelperGeometry")
if helper_vg:
    bm = bmesh.new()
    bm.from_mesh(basemesh.data)
    dlayer = bm.verts.layers.deform.verify()
    helper_idx = helper_vg.index
    verts_to_delete = [v for v in bm.verts if helper_idx in v[dlayer] and v[dlayer][helper_idx] > 0.5]
    print(f"Suppression de {len(verts_to_delete)} sommets d'aide internes...")
    bmesh.ops.delete(bm, geom=verts_to_delete, context='VERTS')
    bm.to_mesh(basemesh.data)
    bm.free()
    basemesh.data.update()

print("Vertices réels du corps propre :", len(basemesh.data.vertices))

# Test import armature KayKit et skinning
kaykit_p = r"C:\test\L'HERITIER DU VIDE\poc_3d\exports\elian_kaykit.glb"
bpy.ops.import_scene.gltf(filepath=kaykit_p)
kaykit_armature = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o is not basemesh:
        bpy.data.objects.remove(o, do_unlink=True)

bpy.ops.object.select_all(action='DESELECT')
basemesh.select_set(True)
kaykit_armature.select_set(True)
bpy.context.view_layer.objects.active = kaykit_armature
res = bpy.ops.object.parent_set(type='ARMATURE_AUTO')
print("Résultat parenting ARMATURE_AUTO :", res)
print("Groupes de sommets après parenting :", [vg.name for vg in basemesh.vertex_groups])
