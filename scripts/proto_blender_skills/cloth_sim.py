# Cloth sim headless — pattern blender-skills "cloth-sim" : un drap tombe sur une
# sphère (collision), simulation calculée en frames puis rendu du résultat.
# Usage : blender --background --python cloth_sim.py -- <out_png> [frames=40]

import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
out_png = argv[0]
frames = int(argv[1]) if len(argv) > 1 else 40

bpy.ops.wm.read_factory_settings(use_empty=True)

# Sphère de collision (le « objet » sous le tissu).
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.8, location=(0, 0, 0.8), segments=32, ring_count=16)
sphere = bpy.context.active_object
sphere.name = "COL_Forme"
mat = bpy.data.materials.new("MAT_Forme")
mat.use_nodes = True
mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.25, 0.22, 0.3, 1.0)
sphere.data.materials.append(mat)
# Blender 5.x : object.collision est dérivé — le modificateur COLLISION suffit
# (réglages par défaut ; thickness_* n'existe plus sur le modificateur 5.2).
sphere.modifiers.new("Collision", "COLLISION")

# Drap : plane subdivisé + modificateur Cloth (réglages « pin-and-collide » minimaux).
bpy.ops.mesh.primitive_plane_add(size=3.2, location=(0, 0, 2.6))
drap = bpy.context.active_object
drap.name = "COL_Drap"
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.subdivide(number_cuts=40)
bpy.ops.object.mode_set(mode="OBJECT")
mat_d = bpy.data.materials.new("MAT_Tissu")
mat_d.use_nodes = True
b = mat_d.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (0.65, 0.18, 0.2, 1.0)
b.inputs["Roughness"].default_value = 0.9
b.inputs["Sheen Weight"].default_value = 0.6
drap.data.materials.append(mat_d)
cloth = drap.modifiers.new("Cloth", "CLOTH")
cloth.settings.quality = 8
cloth.settings.mass = 0.3
cloth.settings.tension_stiffness = 12
cloth.collision_settings.distance_min = 0.005

# Lumière + monde + caméra (3/4 plongeant).
ld = bpy.data.lights.new("Soleil", type="SUN")
ld.energy = 3.5
lo = bpy.data.objects.new("Soleil", ld)
lo.rotation_euler = (Vector((0, 0, 0)) - Vector((2.5, -2, 3.5))).to_track_quat("-Z", "Y").to_euler()
bpy.context.scene.collection.objects.link(lo)
monde = bpy.data.worlds.new("Monde")
monde.use_nodes = True
monde.node_tree.nodes["Background"].inputs[0].default_value = (0.85, 0.86, 0.88, 1.0)
monde.node_tree.nodes["Background"].inputs[1].default_value = 0.5
bpy.context.scene.world = monde
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, -0.001))
sol = bpy.context.active_object
mat_s = bpy.data.materials.new("MAT_Sol")
mat_s.use_nodes = True
mat_s.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.75, 0.75, 0.76, 1.0)
sol.data.materials.append(mat_s)

cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 55
cam = bpy.data.objects.new("CAM_Cloth", cam_data)
cam.location = (3.2, -3.2, 2.6)
cam.rotation_euler = (Vector((0, 0, 0.8)) - cam.location).to_track_quat("-Z", "Y").to_euler()
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam

scn = bpy.context.scene
for moteur in ("BLENDER_EEVEE_NEXT_RENDER", "BLENDER_EEVEE_RENDER", "BLENDER_EEVEE"):
    try:
        scn.render.engine = moteur
        break
    except TypeError:
        continue
scn.frame_start = 1
scn.frame_end = frames
try:
    scn.eevee.taa_render_samples = 32
except AttributeError:
    pass
scn.render.resolution_x = scn.render.resolution_y = 700

# La simulation s'évalue frame par frame — avancer jusqu'à la dernière.
for f in range(1, frames + 1):
    scn.frame_set(f)
scn.render.filepath = out_png
bpy.ops.render.render(write_still=True)
print(f"CLOTH_OK: {frames} frames simulées → {out_png}")
print("SUCCESS:")
