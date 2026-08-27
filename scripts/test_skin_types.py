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

# Test 1: PROCEDURAL / MPFB_V2
HumanService.set_character_skin(skin_path, basemesh, skin_type="PROCEDURAL")

mat = basemesh.data.materials[0]
print("=" * 60)
print(f"Skin PROCEDURAL Matériau : {mat.name}")
print(f"Blend Mode : {getattr(mat, 'blend_method', None)}")
print(f"Surface Render Method : {getattr(mat, 'surface_render_method', None)}")

# Render preview image
cam_data = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.collection.objects.link(cam)
cam.location = (0, -0.8, 1.1)
cam.rotation_euler = (1.5708, 0, 0)
bpy.context.scene.camera = cam

light_data = bpy.data.lights.new("Sun", 'SUN')
light = bpy.data.objects.new("Sun", light_data)
bpy.context.collection.objects.link(light)

bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'
bpy.context.scene.render.filepath = r"C:\GIT\generator-assets\godot_assets\test_skin_procedural_eevee.png"
bpy.ops.render.render(write_still=True)
print("✅ Rendu EEVEE Next PROCEDURAL effectué")
