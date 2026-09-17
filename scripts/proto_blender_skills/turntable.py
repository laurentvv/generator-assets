# Turntable animé d'un GLB — pattern blender-skills "rendering/camera-cinematography",
# adapté headless (EEVEE, éclairage 3 points calqué sur core/mesh_ia.py).
# Usage : blender --background --python turntable.py -- <glb_in> <out_dir> [frames=48] [res=800]

import math
import os
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
glb_in, out_dir = argv[0], argv[1]
nb_frames = int(argv[2]) if len(argv) > 2 else 48
res = int(argv[3]) if len(argv) > 3 else 800
os.makedirs(out_dir, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb_in)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
assert meshes, "aucun maillage dans le GLB"

bpy.ops.object.select_all(action="DESELECT")
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
bpy.ops.object.origin_set(type="ORIGIN_CENTER_OF_MASS", center="BOUNDS")


def bbox_monde():
    pts = []
    for o in meshes:
        for c in o.bound_box:
            pts.append(o.matrix_world @ Vector(c))
    return pts


# Normalisation : dimension max ramenée à 2.0, base posée sur z=0 (identique mesh_ia).
pts = bbox_monde()
max_dim = max(max(p.x for p in pts) - min(p.x for p in pts),
              max(p.y for p in pts) - min(p.y for p in pts),
              max(p.z for p in pts) - min(p.z for p in pts))
scale = 2.0 / max(max_dim, 1e-9)
for o in meshes:
    o.scale = (o.scale.x * scale, o.scale.y * scale, o.scale.z * scale)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
pts = bbox_monde()
for o in meshes:
    o.location.z -= min(p.z for p in pts)
bpy.context.view_layer.update()

# Caméra orbitale : parentée à un empty qui tourne (keyframes 0 -> 360°).
pivot = bpy.data.objects.new("Pivot", None)
bpy.context.scene.collection.objects.link(pivot)
cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 50
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
cam.parent = pivot
cam.location = (3.1, 0, 1.15)
contrainte = cam.constraints.new("TRACK_TO")
cible = bpy.data.objects.new("Cible", None)
cible.location = (0, 0, 0.9)
bpy.context.scene.collection.objects.link(cible)
contrainte.target = cible
contrainte.track_axis = "TRACK_NEGATIVE_Z"
contrainte.up_axis = "UP_Y"
bpy.context.scene.camera = cam

pivot.rotation_euler.z = 0.0
pivot.keyframe_insert(data_path="rotation_euler", index=2, frame=1)
pivot.rotation_euler.z = math.radians(360.0)
pivot.keyframe_insert(data_path="rotation_euler", index=2, frame=nb_frames)


def area_light(nom, energie, taille, loc):
    ld = bpy.data.lights.new(nom, type="AREA")
    ld.energy = energie
    ld.size = taille
    lo = bpy.data.objects.new(nom, ld)
    lo.location = loc
    bpy.context.scene.collection.objects.link(lo)
    return lo


# Lumières FIXES (non parentées au pivot) : les reflets balayent l'objet au fil de l'orbite,
# comme un turntable classique où l'objet tourne sous un éclairage studio fixe.
for nom, energie, taille, loc in (("Cle", 400, 3, (3.5, -3.5, 3.5)),
                                  ("Contre", 150, 4, (-4, -1, 2)),
                                  ("Fond", 250, 3, (0, 5, 4))):
    lo = area_light(nom, energie, taille, loc)
    d = Vector((0, 0, 0.9)) - lo.location
    lo.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

monde = bpy.data.worlds.new("Monde")
monde.use_nodes = True
bg = monde.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.32, 0.33, 0.36, 1.0)
bg.inputs[1].default_value = 0.8
bpy.context.scene.world = monde

scn = bpy.context.scene
for moteur in ("BLENDER_EEVEE_NEXT_RENDER", "BLENDER_EEVEE_RENDER", "BLENDER_EEVEE"):
    try:
        scn.render.engine = moteur
        break
    except TypeError:
        continue
try:
    scn.eevee.taa_render_samples = 48
except AttributeError:
    pass
scn.render.resolution_x = res
scn.render.resolution_y = res
scn.frame_start = 1
scn.frame_end = nb_frames
scn.render.filepath = os.path.join(out_dir, "tt_####.png")
scn.render.image_settings.file_format = "PNG"

bpy.ops.render.render(animation=True)
pngs = [f for f in os.listdir(out_dir) if f.startswith("tt_") and f.endswith(".png")]
print(f"TURNTABLE_OK: {len(pngs)} frames dans {out_dir}")
print("SUCCESS:")
