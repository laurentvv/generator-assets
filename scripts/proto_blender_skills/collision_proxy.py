# Godot collision proxy — blender-skills pattern "collision-proxy", adapted:
# convex hull of the GLB named "<base>-convcolonly" → on Godot import,
# StaticBody3D + CollisionShape3D generated automatically, without a visible mesh.
# Usage: blender --background --python collision_proxy.py -- <glb_in> <out_glb> <out_png>
# Output: GLB (original + proxy) + control PNG (original + hull as magenta wireframe).

import os
import sys

import bmesh
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
glb_in, out_glb, out_png = argv[0], argv[1], argv[2]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb_in)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
assert meshes, "no mesh in the GLB"
base = os.path.splitext(os.path.basename(glb_in))[0]

# Merge the meshes (copies) into a single one, transforms applied → convex hull.
bpy.ops.object.select_all(action="DESELECT")
copies = []
for o in meshes:
    c = o.copy()
    c.data = o.data.copy()
    bpy.context.scene.collection.objects.link(c)
    c.select_set(True)
    copies.append(c)
bpy.context.view_layer.objects.active = copies[0]
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bpy.ops.object.join()
joint = bpy.context.view_layer.objects.active

bm = bmesh.new()
bm.from_mesh(joint.data)
hull = bmesh.ops.convex_hull(bm, input=list(bm.verts))
# geom_interior only contains verts/edges: keep only the envelope faces
# (hull["geom"]) and delete everything else from the original mesh.
faces_hull = {e for e in hull["geom"] if isinstance(e, bmesh.types.BMFace)}
bmesh.ops.delete(bm, geom=[f for f in bm.faces if f not in faces_hull], context="FACES")
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
coque_data = bpy.data.meshes.new(f"SM_{base}-convcolonly")
bm.to_mesh(coque_data)
bm.free()

coque = bpy.data.objects.new(f"SM_{base}-convcolonly", coque_data)
bpy.context.scene.collection.objects.link(coque)
# The hull lives in the applied world space of the original; give it its transform back.
coque.matrix_world = joint.matrix_world.copy()
bpy.data.objects.remove(joint, do_unlink=True)
for m in [m for m in bpy.data.meshes if m.users == 0 and m != coque_data]:
    bpy.data.meshes.remove(m)

# Control view: original + wireframe hull (dynamic framing on the real bbox).
pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
max_dim = max(max(p.x for p in pts) - min(p.x for p in pts),
              max(p.y for p in pts) - min(p.y for p in pts),
              max(p.z for p in pts) - min(p.z for p in pts))
centre = Vector((sum(p.x for p in pts) / len(pts),
                 sum(p.y for p in pts) / len(pts),
                 sum(p.z for p in pts) / len(pts)))
dist = max(max_dim * 2.2, 0.01)
for nom, energie, direction in (("Cle", 400, Vector((1.0, -1.0, 1.0))),
                                ("Fond", 250, Vector((0.0, 1.4, 1.1)))):
    ld = bpy.data.lights.new(nom, type="AREA")
    ld.energy = energie * max_dim * max_dim
    ld.size = max_dim * 1.5
    lo = bpy.data.objects.new(nom, ld)
    lo.location = centre + direction * max_dim * 1.75
    lo.rotation_euler = (centre - lo.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(lo)
monde = bpy.data.worlds.new("Monde")
monde.use_nodes = True
monde.node_tree.nodes["Background"].inputs[0].default_value = (0.32, 0.33, 0.36, 1.0)
monde.node_tree.nodes["Background"].inputs[1].default_value = 0.8
bpy.context.scene.world = monde

mat_filaire = bpy.data.materials.new("MAT_Debug_Collision")
mat_filaire.use_nodes = True
# EEVEE Next (5.x): transparency via surface_render_method='BLENDED'
# (blend_method/shadow_method are gone).
if hasattr(mat_filaire, "surface_render_method"):
    mat_filaire.surface_render_method = "BLENDED"
for attr, valeur in (("blend_method", "BLEND"), ("shadow_method", "NONE")):
    if hasattr(mat_filaire, attr):  # EEVEE legacy only
        setattr(mat_filaire, attr, valeur)
mat_filaire.use_backface_culling = False
bsdf = mat_filaire.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (1.0, 0.0, 0.8, 1.0)
bsdf.inputs["Alpha"].default_value = 0.35
bsdf.inputs["Emission Color"].default_value = (1.0, 0.0, 0.8, 1.0)
bsdf.inputs["Emission Strength"].default_value = 0.6
coque.data.materials.clear()
coque.data.materials.append(mat_filaire)
coque.show_wire = True
coque.show_all_edges = True
coque.display_type = "WIRE"

pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
max_dim = max(max(p.x for p in pts) - min(p.x for p in pts),
              max(p.y for p in pts) - min(p.y for p in pts),
              max(p.z for p in pts) - min(p.z for p in pts))
centre = Vector((sum(p.x for p in pts) / len(pts),
                 sum(p.y for p in pts) / len(pts),
                 sum(p.z for p in pts) / len(pts)))
dist = max(max_dim * 2.2, 0.01)
cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 50
cam = bpy.data.objects.new("Cam", cam_data)
cam.location = centre + Vector((0.62, -0.62, 0.5)) * dist
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
scn.render.resolution_x = scn.render.resolution_y = 700
scn.render.filepath = out_png
bpy.ops.render.render(write_still=True)

coque.show_wire = False
coque.show_all_edges = False
bpy.ops.object.select_all(action="DESELECT")
for o in bpy.context.scene.objects:
    o.select_set(o.type in ("MESH", "EMPTY"))
bpy.ops.export_scene.gltf(filepath=out_glb, export_format="GLB", use_selection=True)
print(f"COLLISION_OK: hull {len(coque_data.polygons)} faces → {out_glb}")
print("SUCCESS:")
