# Audit de scène GLB — pattern blender-skills "asset-optimization/qa-review", adapté headless.
# Usage : blender --background --python audit_scene.py -- <glb_in> <json_out>
# Sortie : AUDIT_JSON:{...} sur stdout + fichier JSON.

import json
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
glb_in, json_out = argv[0], argv[1]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb_in)
bpy.context.view_layer.update()

objets = []
for o in bpy.context.scene.objects:
    entree = {"nom": o.name, "type": o.type}
    if o.type == "MESH":
        tris = sum(max(len(p.vertices) - 2, 0) for p in o.data.polygons)
        entree.update({
            "triangles": tris,
            "matériaux": [m.name for m in o.data.materials if m],
            "couches_uv": [uv.name for uv in o.data.uv_layers],
            "modificateurs": [m.name for m in o.modifiers],
            "verticies": len(o.data.vertices),
        })
    if o.type == "ARMATURE":
        entree["os"] = len(o.data.bones)
    objets.append(entree)

pts = []
for o in bpy.context.scene.objects:
    if o.type == "MESH":
        for c in o.bound_box:
            pts.append(o.matrix_world @ Vector(c))
dimensions = [round(max(p.x for p in pts) - min(p.x for p in pts), 3),
              round(max(p.y for p in pts) - min(p.y for p in pts), 3),
              round(max(p.z for p in pts) - min(p.z for p in pts), 3)] if pts else []

images = {img.name for img in bpy.data.images}
rapport = {
    "fichier": glb_in,
    "objets": len(objets),
    "triangles_total": sum(o.get("triangles", 0) for o in objets),
    "matériaux_uniques": sorted({m for o in objets for m in o.get("matériaux", [])}),
    "images_embarquées": sorted(images),
    "dimensions_m": dimensions,
    "détail": objets,
}
with open(json_out, "w", encoding="utf-8") as f:
    json.dump(rapport, f, ensure_ascii=False, indent=2)
print("AUDIT_JSON:" + json.dumps({k: rapport[k] for k in
                                  ("fichier", "objets", "triangles_total", "dimensions_m")},
                                 ensure_ascii=False))
print("SUCCESS:")
