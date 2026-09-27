# Multi-asset split: break a multi-mesh GLB into separate GLBs (one per mesh) —
# blender-skills pattern "scene-assembly/export-pipeline": extract props from a
# CC0 scene or a pack to make them individually usable in Godot.
# Usage: blender --background --python decoupe_assets.py -- <glb_in> <out_dir>
# Output: one <slug>.glb per mesh + DECOUPE_JSON:{...} (before/after, verts/faces).

import json
import os
import re
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
glb_in, out_dir = argv[0], argv[1]
os.makedirs(out_dir, exist_ok=True)


def slug(nom):
    s = re.sub(r"[^A-Za-z0-9]+", "_", nom).strip("_").lower() or "mesh"
    return s


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb_in)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
assert meshes, "no mesh in the GLB"
assert len(meshes) > 1, "single-mesh GLB: nothing to split"

sorties = []
for i, o in enumerate(meshes):
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    nom_fichier = f"{slug(o.name)}_{i:02d}.glb"
    chemin = os.path.join(out_dir, nom_fichier)
    bpy.ops.export_scene.gltf(filepath=chemin, export_format="GLB", use_selection=True)
    sorties.append({"source": o.name, "fichier": chemin,
                    "vertices": len(o.data.vertices),
                    "faces": len(o.data.polygons),
                    "matériaux": [m.name for m in o.data.materials if m]})

rapport = {"glb_source": glb_in, "nb_meshes": len(meshes), "decoupe": sorties}
with open(os.path.join(out_dir, "decoupe_rapport.json"), "w", encoding="utf-8") as f:
    json.dump(rapport, f, ensure_ascii=False, indent=2)
print("DECOUPE_JSON:" + json.dumps(rapport, ensure_ascii=False))
print("SUCCESS:")
