# -*- coding: utf-8 -*-
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
TargetService = dynamic_import("mpfb.services.targetservice", "TargetService")

basemesh = HumanService.create_human()
print("Vertices before helper removal:", len(basemesh.data.vertices))

# Delete the helpers
# In MPFB, the "HelperGeometry" vertex group holds all the helper vertices
helper_vg = basemesh.vertex_groups.get("HelperGeometry")
if helper_vg:
    print("HelperGeometry found with vertices.")

# Helper removal test
try:
    HumanService.delete_helpers(basemesh)
    print("Vertices after delete_helpers:", len(basemesh.data.vertices))
except Exception as e:
    print("delete_helpers not found, alternative test:", e)
