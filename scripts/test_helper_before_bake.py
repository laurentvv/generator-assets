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
TargetService = dynamic_import("mpfb.services.targetservice", "TargetService")

macros = {
    "gender": 1.0, "age": 0.17, "muscle": 0.3, "weight": 0.25,
    "proportions": 0.5, "height": 0.5,
    "race": {"caucasian": 1.0, "asian": 0.0, "african": 0.0}
}
basemesh = HumanService.create_human(macro_detail_dict=macros)
TargetService.reapply_macro_details(basemesh)
bpy.context.view_layer.update()

print("1. Vertices basemesh :", len(basemesh.data.vertices))

# Suppression des sommets d'aide internes AVANT le bake
helper_vg = basemesh.vertex_groups.get("HelperGeometry")
if helper_vg:
    bm = bmesh.new()
    bm.from_mesh(basemesh.data)
    dlayer = bm.verts.layers.deform.verify()
    helper_idx = helper_vg.index
    verts_to_delete = [v for v in bm.verts if helper_idx in v[dlayer] and v[dlayer][helper_idx] > 0.5]
    print(f"2. Suppression de {len(verts_to_delete)} sommets d'aide...")
    bmesh.ops.delete(bm, geom=verts_to_delete, context='VERTS')
    bm.to_mesh(basemesh.data)
    bm.free()
    basemesh.data.update()

# Bake shape keys
dg = bpy.context.evaluated_depsgraph_get()
ev = basemesh.evaluated_get(dg)
me = bpy.data.meshes.new_from_object(ev)
old = basemesh.data
basemesh.data = me
me.name = old.name
bpy.data.meshes.remove(old)
print("3. Vertices après bake shape keys :", len(basemesh.data.vertices))

# Test skinning armature KayKit
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
print("4. Résultat ARMATURE_AUTO :", res)
print("5. Bones skinnés sur basemesh :", [vg.name for vg in basemesh.vertex_groups if vg.name in [b.name for b in kaykit_armature.data.bones]])
