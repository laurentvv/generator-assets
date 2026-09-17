# Normalisation du nommage moteur — pattern blender-skills "naming-conventions" :
# meshes → SM_<Base>_<n>, matériaux → MAT_<slug>, images → T_<Base>_<n>.
# Usage : blender --background --python renommer_conventions.py -- <glb_in> <out_glb>
# Sortie : RENAME_JSON:{...} (avant/après) + GLB ré-exporté.

import json
import os
import re
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
glb_in, out_glb = argv[0], argv[1]
base = re.sub(r"[^A-Za-z0-9]+", "_", os.path.splitext(os.path.basename(glb_in))[0]).strip("_").title()


def propre(nom):
    return re.sub(r"[^A-Za-z0-9]+", "_", nom).strip("_").title() or "SansNom"


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb_in)

avant = {"meshes": [], "matériaux": []}
for i, o in enumerate(sorted(o.name for o in bpy.context.scene.objects if o.type == "MESH")):
    avant["meshes"].append(o)
for m in sorted(bpy.data.materials, key=lambda m: m.name):
    avant["matériaux"].append(m.name)

for i, o in enumerate([o for o in bpy.context.scene.objects if o.type == "MESH"]):
    o.name = f"SM_{base}_{i + 1:02d}"
    o.data.name = o.name

for i, m in enumerate(bpy.data.materials):
    m.name = f"MAT_{base}_{propre(m.name)}" if not m.name.startswith("MAT_") else m.name

apres = {
    "meshes": [o.name for o in bpy.context.scene.objects if o.type == "MESH"],
    "matériaux": sorted(m.name for m in bpy.data.materials),
}

bpy.ops.object.select_all(action="DESELECT")
for o in bpy.context.scene.objects:
    o.select_set(o.type in ("MESH", "EMPTY", "ARMATURE"))
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB", use_selection=True)
print("RENAME_JSON:" + json.dumps({"avant": avant, "après": apres}, ensure_ascii=False))
print("SUCCESS:")
