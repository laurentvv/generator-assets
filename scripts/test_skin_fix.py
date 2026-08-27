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

# Nettoyage automatique immédiat du shader
for mat in basemesh.data.materials:
    if mat and mat.node_tree:
        bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if bsdf:
            alpha_sock = bsdf.inputs.get("Alpha")
            if alpha_sock:
                for link in list(alpha_sock.links):
                    mat.node_tree.links.remove(link)
                alpha_sock.default_value = 1.0
        alpha_node = mat.node_tree.nodes.get("AlphaMapTexture")
        if alpha_node:
            mat.node_tree.nodes.remove(alpha_node)

# Render EEVEE Next
cam_data = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.collection.objects.link(cam)
cam.location = (0, -1.2, 1.2)
cam.rotation_euler = (1.5708, 0, 0)
bpy.context.scene.camera = cam

light_data = bpy.data.lights.new("Sun", 'SUN')
light_data.energy = 3.0
light = bpy.data.objects.new("Sun", light_data)
bpy.context.collection.objects.link(light)

bpy.context.scene.render.engine = 'BLENDER_EEVEE'
bpy.context.scene.render.filepath = r"C:\GIT\generator-assets\godot_assets\test_skin_fixed_eevee.png"
bpy.ops.render.render(write_still=True)
print("✅ Rendu EEVEE avec skin OPAQUE réussi !")
