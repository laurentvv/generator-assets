# Chaîne LOD d'un GLB — pattern blender-skills "lod-pipeline" (ratios 100/50/25/10),
# décimation identique à core/mesh_ia.py (COLLAPSE, delimit SHARP/UV, UV préservées).
# Échelle et transforms du GLB source NON modifiés (les LOD doivent rester superposables).
# Usage : blender --background --python lod_chain.py -- <glb_in> <out_dir> <base_name>
# Sortie : <base>_LOD0..3.glb + une vue 3/4 PNG par LOD + LOD_JSON:{...}

import json
import math
import os
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
glb_in, out_dir, base = argv[0], argv[1], argv[2]
os.makedirs(out_dir, exist_ok=True)
RATIOS = [1.0, 0.5, 0.5, 0.5]  # LOD0 = original, puis -50 % relatif à chaque étage


def tris_meshes(meshes):
    return sum(max(len(p.vertices) - 2, 0) for o in meshes for p in o.data.polygons)


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb_in)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
assert meshes, "aucun maillage dans le GLB"


def exporter(niveau):
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    chemin = os.path.join(out_dir, f"{base}_LOD{niveau}.glb")
    bpy.ops.export_scene.gltf(filepath=chemin, export_format="GLB", use_selection=True)
    return chemin


def vue_controle(niveau):
    # Cadrage dynamique sur la bbox réelle (pas de normalisation : le GLB source
    # garde son échelle d'origine dans les exports).
    pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    max_dim = max(max(p.x for p in pts) - min(p.x for p in pts),
                  max(p.y for p in pts) - min(p.y for p in pts),
                  max(p.z for p in pts) - min(p.z for p in pts))
    centre = Vector((sum(p.x for p in pts) / len(pts),
                     sum(p.y for p in pts) / len(pts),
                     sum(p.z for p in pts) / len(pts)))
    dist = max(max_dim * 2.2, 0.01)
    cam_data = bpy.data.cameras.new(f"Cam_LOD{niveau}")
    cam_data.lens = 50
    cam = bpy.data.objects.new(f"Cam_LOD{niveau}", cam_data)
    cam.location = centre + Vector((0.62, -0.62, 0.45)) * dist
    cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    scn = bpy.context.scene
    for moteur in ("BLENDER_EEVEE_NEXT_RENDER", "BLENDER_EEVEE_RENDER", "BLENDER_EEVEE"):
        try:
            scn.render.engine = moteur
            break
        except TypeError:
            continue
    try:
        scn.eevee.taa_render_samples = 32
    except AttributeError:
        pass
    scn.render.resolution_x = scn.render.resolution_y = 560
    scn.render.filepath = os.path.join(out_dir, f"vue_LOD{niveau}.png")
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam, do_unlink=True)
    bpy.data.cameras.remove(cam_data)


# Éclairage + monde minimaux pour les vues (une seule fois) — proportionnels à la bbox.
pts0 = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
max_dim0 = max(max(p.x for p in pts0) - min(p.x for p in pts0),
               max(p.y for p in pts0) - min(p.y for p in pts0),
               max(p.z for p in pts0) - min(p.z for p in pts0))
centre0 = Vector((sum(p.x for p in pts0) / len(pts0),
                  sum(p.y for p in pts0) / len(pts0),
                  sum(p.z for p in pts0) / len(pts0)))
d0 = max(max_dim0, 1e-6)
for nom, energie, direction in (("Cle", 400, Vector((1.0, -1.0, 1.0))),
                                ("Fond", 250, Vector((0.0, 1.4, 1.1)))):
    ld = bpy.data.lights.new(nom, type="AREA")
    ld.energy = energie * d0 * d0
    ld.size = d0 * 1.5
    lo = bpy.data.objects.new(nom, ld)
    lo.location = centre0 + direction * d0 * 1.75
    lo.rotation_euler = (centre0 - lo.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(lo)
monde = bpy.data.worlds.new("Monde")
monde.use_nodes = True
monde.node_tree.nodes["Background"].inputs[0].default_value = (0.32, 0.33, 0.36, 1.0)
monde.node_tree.nodes["Background"].inputs[1].default_value = 0.8
bpy.context.scene.world = monde

rapport = []
for niveau, ratio in enumerate(RATIOS):
    if niveau > 0:
        for o in meshes:
            mod = o.modifiers.new(f"LOD{niveau}", "DECIMATE")
            mod.decimate_type = "COLLAPSE"
            mod.ratio = ratio
            mod.delimit = {"SHARP", "UV"}
            with bpy.context.temp_override(object=o, active_object=o):
                bpy.ops.object.modifier_apply(modifier=mod.name)
    chemin = exporter(niveau)
    vue_controle(niveau)
    rapport.append({"lod": niveau, "ratio_cumulé": round(math.prod(RATIOS[:niveau + 1]), 3),
                    "triangles": tris_meshes(meshes), "fichier": chemin})

with open(os.path.join(out_dir, "lod_rapport.json"), "w", encoding="utf-8") as f:
    json.dump(rapport, f, ensure_ascii=False, indent=2)
print("LOD_JSON:" + json.dumps(rapport, ensure_ascii=False))
print("SUCCESS:")
