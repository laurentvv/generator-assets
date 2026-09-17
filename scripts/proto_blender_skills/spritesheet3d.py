# Spritesheet 3D → 2D : 8 directions orthographiques, fond transparent — pattern
# blender-skills "isometric-style/hd-2d" adapté : transformer un asset 3D en sprites Godot.
# Usage : blender --background --python spritesheet3d.py -- <glb_in> <out_dir> [res=512] [ndirs=8]
# Sortie : sprite_00..NN.png (RGBA, caméra ortho, directions réparties sur 360°).

import math
import os
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
glb_in, out_dir = argv[0], argv[1]
res = int(argv[2]) if len(argv) > 2 else 512
ndirs = int(argv[3]) if len(argv) > 3 else 8
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

pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
max_dim = max(max(p.x for p in pts) - min(p.x for p in pts),
              max(p.y for p in pts) - min(p.y for p in pts),
              max(p.z for p in pts) - min(p.z for p in pts))
scale = 1.0 / max(max_dim, 1e-9)
for o in meshes:
    o.scale = (o.scale.x * scale, o.scale.y * scale, o.scale.z * scale)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
centre = Vector((sum(p.x for p in pts) / len(pts),
                 sum(p.y for p in pts) / len(pts),
                 sum(p.z for p in pts) / len(pts)))
for o in meshes:
    o.location.z -= min(p.z for p in pts)
bpy.context.view_layer.update()

# Caméra ORTHO en orbite, fond transparent → sprites Godot prêts à l'emploi.
cam_data = bpy.data.cameras.new("Cam_Sprite")
cam_data.type = "ORTHO"
cam_data.ortho_scale = 1.25
cam = bpy.data.objects.new("CAM_Spritesheet", cam_data)
bpy.context.scene.collection.objects.link(cam)
cible = bpy.data.objects.new("Cible", None)
cible.location = centre
bpy.context.scene.collection.objects.link(cible)
tk = cam.constraints.new("TRACK_TO")
tk.target = cible
tk.track_axis = "TRACK_NEGATIVE_Z"
tk.up_axis = "UP_Y"
bpy.context.scene.camera = cam

for nom, energie, direction in (("Cle", 400, Vector((1.0, -1.0, 1.2))),
                                ("Contre", 150, Vector((-1.2, -0.3, 0.8))),
                                ("Fond", 250, Vector((0.0, 1.4, 1.1)))):
    ld = bpy.data.lights.new(nom, type="AREA")
    ld.energy = energie
    ld.size = 3
    lo = bpy.data.objects.new(nom, ld)
    lo.location = centre + direction
    lo.rotation_euler = (centre - lo.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(lo)
monde = bpy.data.worlds.new("Monde")
monde.use_nodes = True
bpy.context.scene.world = monde  # fond noir masqué par film_transparent

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
scn.render.film_transparent = True
scn.render.image_settings.color_mode = "RGBA"
scn.render.resolution_x = scn.render.resolution_y = res

angles = []
for i in range(ndirs):
    theta = math.tau * i / ndirs
    cam.location = centre + Vector((math.cos(theta), math.sin(theta), 0.0)) * 10.0
    bpy.context.view_layer.update()
    scn.render.filepath = os.path.join(out_dir, f"sprite_{i:02d}.png")
    bpy.ops.render.render(write_still=True)
    angles.append(round(math.degrees(theta), 1))

with open(os.path.join(out_dir, "spritesheet_infos.json"), "w", encoding="utf-8") as f:
    import json
    json.dump({"directions_deg": angles, "res": res,
               "note": "sprite_00 = face +X, sens anti-horaire vu de dessus"}, f, ensure_ascii=False, indent=2)
print(f"SPRITESHEET_OK: {ndirs} directions de {res}px → {out_dir}")
print("SUCCESS:")
