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
    raise ValueError(f"Module {absolute_package_str} introuvable")

bpy.ops.wm.read_factory_settings(use_empty=True)
try:
    bpy.ops.preferences.addon_enable(module="bl_ext.user_default.mpfb")
except Exception:
    pass

HumanService = dynamic_import("mpfb.services.humanservice", "HumanService")
TargetService = dynamic_import("mpfb.services.targetservice", "TargetService")

basemesh = HumanService.create_human()
print("Vertices avant suppression helpers :", len(basemesh.data.vertices))

# Supprimer les helpers
# Dans MPFB, le vertex group "HelperGeometry" contient tous les sommets d'aide
helper_vg = basemesh.vertex_groups.get("HelperGeometry")
if helper_vg:
    print("HelperGeometry trouvé avec des sommets.")

# Test de suppression des helpers
try:
    HumanService.delete_helpers(basemesh)
    print("Vertices après delete_helpers :", len(basemesh.data.vertices))
except Exception as e:
    print("delete_helpers non trouvé, test alternatif :", e)
