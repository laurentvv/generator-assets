# Beauty render Cycles GPU — pattern blender-skills "lighting/lookdev/rendering" :
# studio 3 points renforcé, sol sombre récepteur d'ombres, Cycles HIP (RX 6950 XT),
# débruitage activé. Adapté du worker scripts/blendkit_blender_job.py.
# Usage : blender --background --python beauty_render.py -- <glb_in> <out_png> [res=1200] [samples=96]

import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
glb_in, out_png = argv[0], argv[1]
res = int(argv[2]) if len(argv) > 2 else 1200
samples = int(argv[3]) if len(argv) > 3 else 96

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
scale = 2.2 / max(max_dim, 1e-9)
for o in meshes:
    o.scale = (o.scale.x * scale, o.scale.y * scale, o.scale.z * scale)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
for o in meshes:
    o.location.z -= min(p.z for p in pts)
bpy.context.view_layer.update()

# Sol sombre récepteur d'ombres
bpy.ops.mesh.primitive_plane_add(size=16, location=(0, 0, -0.001))
sol = bpy.context.active_object
sol.name = "COL_Sol"
mat_sol = bpy.data.materials.new("MAT_Sol_Studio")
mat_sol.use_nodes = True
bsdf_sol = mat_sol.node_tree.nodes["Principled BSDF"]
bsdf_sol.inputs["Base Color"].default_value = (0.055, 0.05, 0.05, 1.0)
bsdf_sol.inputs["Roughness"].default_value = 0.65
bsdf_sol.inputs["Metallic"].default_value = 0.1
sol.data.materials.append(mat_sol)

# Studio 3 points (key chaude, fill froide, rim fort) + rim arrière
def area_light(nom, energie, taille, loc, couleur):
    ld = bpy.data.lights.new(nom, type="AREA")
    ld.energy = energie
    ld.size = taille
    ld.color = couleur
    lo = bpy.data.objects.new(nom, ld)
    lo.location = loc
    lo.rotation_euler = (Vector((0, 0, 1.0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(lo)
    return lo


area_light("LGT_Key_Main", 900, 3.5, (4, -4, 4), (1.0, 0.96, 0.9))
area_light("LGT_Fill_Soft", 250, 6, (-5, -1.5, 2.5), (0.85, 0.9, 1.0))
area_light("LGT_Rim_Back", 700, 3, (0.5, 5.5, 4.5), (1.0, 1.0, 1.0))

monde = bpy.data.worlds.new("Monde")
monde.use_nodes = True
monde.node_tree.nodes["Background"].inputs[0].default_value = (0.02, 0.02, 0.025, 1.0)
monde.node_tree.nodes["Background"].inputs[1].default_value = 1.0
bpy.context.scene.world = monde

cam_data = bpy.data.cameras.new("CAM_Hero_Shot_01")
cam_data.lens = 58
cam = bpy.data.objects.new("CAM_Hero_Shot_01", cam_data)
cam.location = (2.7, -2.9, 1.35)
cam.rotation_euler = (Vector((0, 0, 1.0)) - cam.location).to_track_quat("-Z", "Y").to_euler()
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam

scn = bpy.context.scene
scn.render.engine = "CYCLES"
detail = "CPU"
try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for dtype in ("HIP", "VULKAN", "CUDA", "OPTIX", "NONE"):
        try:
            prefs.compute_device_type = dtype
            break
        except TypeError:
            continue
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type != "CPU"
    scn.cycles.device = "GPU"
    actifs = [d.name for d in prefs.devices if d.use]
    detail = ", ".join(actifs) or "CPU"
except Exception as e:  # noqa: BLE001 — CPU en dernier recours
    print(f"GPU indisponible ({e}), Cycles en CPU")
scn.cycles.samples = samples
scn.cycles.use_denoising = True
scn.render.resolution_x = res
scn.render.resolution_y = int(res * 0.75)
scn.render.filepath = out_png
bpy.ops.render.render(write_still=True)
print(f"BEAUTY_OK: Cycles [{detail}] {samples} échantillons → {out_png}")
print("SUCCESS:")
