# Scatter d'instances par Geometry Nodes — pattern blender-skills "geometry-nodes" +
# "environment-artist/set-dressing" : distribution aléatoire d'un prop GLB sur un sol,
# rotation/scale aléatoires pilotés par graine (reproductible).
# Usage : blender --background --python scatter_props.py -- <glb_in> <out_png> [count=40] [seed=42] [densite=3.0]
# Sortie : PNG EEVEE + SCATTER_OK (chemin GN si réussi, sinon repli duplis manuels).

import math
import random
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
glb_in, out_png = argv[0], argv[1]
count = int(argv[2]) if len(argv) > 2 else 40
seed = int(argv[3]) if len(argv) > 3 else 42
densite = float(argv[4]) if len(argv) > 4 else 3.0

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb_in)
meshes_import = [o for o in bpy.context.scene.objects if o.type == "MESH"]
assert meshes_import, "aucun maillage dans le GLB"
# Le prop = TOUT le GLB fusionné (un GLB peut contenir plusieurs meshes, ex. baril + support).
bpy.ops.object.select_all(action="DESELECT")
for o in meshes_import:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes_import[0]
bpy.ops.object.join()
prop = bpy.context.view_layer.objects.active

# Normalisation du prop à ~0.8 m, base posée sur z=0.
bpy.context.view_layer.objects.active = prop
bpy.ops.object.origin_set(type="ORIGIN_CENTER_OF_MASS", center="BOUNDS")
dim = max(prop.dimensions)
prop.scale = prop.scale * (0.8 / max(dim, 1e-9))
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
prop.location.z -= min((prop.matrix_world @ Vector(c)).z for c in prop.bound_box)
prop.hide_render = True
prop.hide_viewport = True

# Sol
sol_data = bpy.data.meshes.new("Sol")
bpy.ops.mesh.primitive_plane_add(size=14, location=(0, 0, 0))
sol = bpy.context.active_object
sol.name = "COL_Sol"
mat_sol = bpy.data.materials.new("MAT_Sol_Studio")
mat_sol.use_nodes = True
mat_sol.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.23, 0.22, 0.21, 1.0)
mat_sol.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
sol.data.materials.append(mat_sol)

chemin = "geometry_nodes"
mod = None


def lier(n1, s1, n2, s2):
    nt.links.new(n1.outputs[s1], n2.inputs[s2])


try:
    mod = sol.modifiers.new("GN_Scatter", "NODES")
    nt = bpy.data.node_groups.new("GN_Scatter", "GeometryNodeTree")
    mod.node_group = nt
    nt.interface.new_socket("Géométrie", in_out="INPUT", socket_type="NodeSocketGeometry")
    nt.interface.new_socket("Géométrie", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n_in, n_out = nt.nodes.new("NodeGroupInput"), nt.nodes.new("NodeGroupOutput")
    n_in.location = n_out.location = (0, 0)
    dist = nt.nodes.new("GeometryNodeDistributePointsOnFaces")
    dist.distribute_method = "POISSON"
    # En mode POISSON, seul "Density Max" existe (le socket "Density" est propre au mode RANDOM).
    dist.inputs["Density Max"].default_value = densite * 20
    dist.inputs["Distance Min"].default_value = 0.9
    dist.inputs["Seed"].default_value = seed
    inst = nt.nodes.new("GeometryNodeInstanceOnPoints")
    info = nt.nodes.new("GeometryNodeObjectInfo")
    info.inputs["Object"].default_value = prop
    rot = nt.nodes.new("GeometryNodeRotateInstances")
    alea_rot = nt.nodes.new("FunctionNodeRandomValue")
    alea_rot.data_type = "FLOAT_VECTOR"
    alea_rot.inputs["Min"].default_value = (0.0, 0.0, 0.0)
    alea_rot.inputs["Max"].default_value = (0.0, 0.0, math.tau)
    alea_rot.inputs["Seed"].default_value = seed
    ech = nt.nodes.new("GeometryNodeScaleInstances")
    alea_ech = nt.nodes.new("FunctionNodeRandomValue")
    alea_ech.data_type = "FLOAT_VECTOR"
    alea_ech.inputs["Min"].default_value = (0.7, 0.7, 0.7)
    alea_ech.inputs["Max"].default_value = (1.4, 1.4, 1.4)
    alea_ech.inputs["Seed"].default_value = seed + 1
    join = nt.nodes.new("GeometryNodeJoinGeometry")
    lier(n_in, "Géométrie", dist, "Mesh")
    lier(dist, "Points", inst, "Points")
    lier(info, "Geometry", inst, "Instance")
    lier(inst, "Instances", rot, "Instances")
    lier(alea_rot, "Value", rot, "Rotation")
    lier(rot, "Instances", ech, "Instances")
    lier(alea_ech, "Value", ech, "Scale")
    lier(ech, "Instances", join, "Geometry")
    lier(n_in, "Géométrie", join, "Geometry")
    lier(join, "Geometry", n_out, "Géométrie")
except Exception as e:  # noqa: BLE001 — repli : placement manuel équivalent
    chemin = f"repli_manuel ({e})"
    if mod is not None:
        sol.modifiers.remove(mod)
    rng = random.Random(seed)
    prop.hide_render = False
    prop.hide_viewport = False
    for _ in range(count):
        c = prop.copy()
        c.data = prop.data
        bpy.context.scene.collection.objects.link(c)
        c.location = (rng.uniform(-6, 6), rng.uniform(-6, 6), 0)
        c.rotation_euler.z = rng.uniform(0, math.tau)
        s = rng.uniform(0.7, 1.4)
        c.scale = (s, s, s)

# Soleil + monde + caméra
ld = bpy.data.lights.new("Soleil", type="SUN")
ld.energy = 5.0
lo = bpy.data.objects.new("Soleil", ld)
lo.rotation_euler = (math.radians(55), 0, math.radians(30))
bpy.context.scene.collection.objects.link(lo)
monde = bpy.data.worlds.new("Monde")
monde.use_nodes = True
monde.node_tree.nodes["Background"].inputs[0].default_value = (0.45, 0.5, 0.6, 1.0)
monde.node_tree.nodes["Background"].inputs[1].default_value = 0.25
bpy.context.scene.world = monde
cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 42
cam = bpy.data.objects.new("CAM_Scatter_01", cam_data)
cam.location = (9, -9, 6.5)
cam.rotation_euler = (Vector((0, 0, 0)) - cam.location).to_track_quat("-Z", "Y").to_euler()
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
    scn.eevee.taa_render_samples = 48
except AttributeError:
    pass
scn.render.resolution_x = 1280
scn.render.resolution_y = 720
scn.render.filepath = out_png
bpy.ops.render.render(write_still=True)
print(f"SCATTER_OK: {chemin}")
print("SUCCESS:")
