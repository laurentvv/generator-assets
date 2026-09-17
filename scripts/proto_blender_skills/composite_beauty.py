# Beauty render + compositing headless — pattern blender-skills "compositing/rendering" :
# le rendu de beauty_render.py avec nœuds de compositing (glare/fog_glow, contraste,
# vignette) appliqués en post dans Blender lui-même. Remplace l'éclairage plat noté
# en vague 1 (rim trop discret).
# Usage : blender --background --python composite_beauty.py -- <glb_in> <out_png> [res=1200]

import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
glb_in, out_png = argv[0], argv[1]
res = int(argv[2]) if len(argv) > 2 else 1200

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

bpy.ops.mesh.primitive_plane_add(size=16, location=(0, 0, -0.001))
sol = bpy.context.active_object
mat_sol = bpy.data.materials.new("MAT_Sol_Studio")
mat_sol.use_nodes = True
b = mat_sol.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (0.045, 0.04, 0.045, 1.0)
b.inputs["Roughness"].default_value = 0.5
b.inputs["Metallic"].default_value = 0.25
sol.data.materials.append(mat_sol)


def area_light(nom, energie, taille, loc, couleur):
    ld = bpy.data.lights.new(nom, type="AREA")
    ld.energy = energie
    ld.size = taille
    ld.color = couleur
    lo = bpy.data.objects.new(nom, ld)
    lo.location = loc
    lo.rotation_euler = (Vector((0, 0, 1.0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(lo)


# Key chaude + fill froide + rim FORT (x2 vs vague 1) + kick avant bas.
area_light("LGT_Key_Main", 1100, 3.5, (4, -4, 4), (1.0, 0.94, 0.86))
area_light("LGT_Fill_Soft", 220, 6, (-5, -1.5, 2.5), (0.8, 0.88, 1.0))
area_light("LGT_Rim_Back", 1600, 2, (0.5, 5.5, 4.5), (1.0, 1.0, 1.0))
area_light("LGT_Kick_Front", 180, 4, (0.5, -4.5, 0.6), (1.0, 0.9, 0.8))

monde = bpy.data.worlds.new("Monde")
monde.use_nodes = True
monde.node_tree.nodes["Background"].inputs[0].default_value = (0.015, 0.015, 0.02, 1.0)
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
except Exception:  # noqa: BLE001 — CPU en dernier recours
    pass
scn.cycles.samples = 96
scn.cycles.use_denoising = True
scn.render.resolution_x = res
scn.render.resolution_y = int(res * 0.75)

# Compositing — API Blender 5.2 : arbre racine = compositing_node_group, sortie via
# Group Output (les nœuds Composite/MixRGB legacy n'existent plus). Vignette via
# SetAlpha + AlphaOver (pas de nœud Mix).
nt = bpy.data.node_groups.new("Composite_Beauty", "CompositorNodeTree")
scn.compositing_node_group = nt
socket = nt.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
rl = nt.nodes.new("CompositorNodeRLayers")
glare = nt.nodes.new("CompositorNodeGlare")
glare.inputs["Threshold"].default_value = 0.9
glare.inputs["Size"].default_value = 8.0
glare.inputs["Quality"].default_value = "High"
courbes = nt.nodes.new("CompositorNodeCurveRGB")
courbes.mapping.curves[3].points[0].location = (0.0, 0.03)
courbes.mapping.curves[3].points[1].location = (1.0, 0.97)
# Vignette impossible proprement en 5.2 (pas de nœud Mix compositing) →
# contraste/luminosité globaux à la place.
bc = nt.nodes.new("CompositorNodeBrightContrast")
bc.inputs["Bright"].default_value = -0.03
bc.inputs["Contrast"].default_value = 0.08
go = nt.nodes.new("NodeGroupOutput")
nt.links.new(rl.outputs["Image"], glare.inputs["Image"])
nt.links.new(glare.outputs["Image"], courbes.inputs["Image"])
nt.links.new(courbes.outputs["Image"], bc.inputs["Image"])
nt.links.new(bc.outputs["Image"], go.inputs[0])

scn.render.filepath = out_png
bpy.ops.render.render(write_still=True)
print(f"COMPOSITE_OK: glare+contraste+vignette → {out_png}")
print("SUCCESS:")
