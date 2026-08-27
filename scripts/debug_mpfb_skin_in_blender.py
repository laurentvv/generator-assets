# -*- coding: utf-8 -*-
import bpy
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
AssetService = dynamic_import("mpfb.services.assetservice", "AssetService")

basemesh = HumanService.create_human()
skin_path = os.path.join(r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\marc_novice\marc_novice.mhmat")
HumanService.set_character_skin(skin_path, basemesh, skin_type="GAMEENGINE")

print("=" * 60)
print("=== INSPECTION DU MATÉRIAU SKIN CRÉÉ DANS BLENDER ===")
mat = basemesh.data.materials[0]
print(f"Nom : {mat.name}")
print(f"Blend Mode : {getattr(mat, 'blend_method', None)}")
print(f"Surface Render Method : {getattr(mat, 'surface_render_method', None)}")

if mat.use_nodes:
    for n in mat.node_tree.nodes:
        print(f"Node: {n.name} ({n.type})")
        for inp in n.inputs:
            if inp.is_linked:
                for l in inp.links:
                    print(f"  Input '{inp.name}' linked from {l.from_node.name}['{l.from_socket.name}']")
print("=" * 60)
