# Bake AO headless — pattern blender-skills "texture-workflow/lookdev" : cuire une
# carte d'occlusion ambiante (Cycles bake) sur les UV existantes du GLB, puis la
# multiplier dans le shader et rendre l'après.
# Usage : blender --background --python bake_ao.py -- <glb_in> <ao_png> <apercu_png>
# Sortie : carte AO PNG + vue après mélange AO × albedo.

import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
glb_in, ao_png, apercu_png = argv[0], argv[1], argv[2]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb_in)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
assert meshes, "aucun maillage dans le GLB"
assert all(o.data.uv_layers for o in meshes), "UV manquantes — bake impossible"

bpy.ops.object.select_all(action="DESELECT")
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]

pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
max_dim = max(max(p.x for p in pts) - min(p.x for p in pts),
              max(p.y for p in pts) - min(p.y for p in pts),
              max(p.z for p in pts) - min(p.z for p in pts))
d0 = max(max_dim, 1e-6)
centre = Vector((sum(p.x for p in pts) / len(pts),
                 sum(p.y for p in pts) / len(pts),
                 sum(p.z for p in pts) / len(pts)))

# Bake AO (Cycles, sel→même objet).
scn = bpy.context.scene
scn.render.engine = "CYCLES"
scn.cycles.samples = 32
bake_img = bpy.data.images.new("T_Casque_AO", 1024, 1024)
for o in meshes:
    o.data.materials.clear()  # matériau simple dédié au bake (UV conservées)
    mat = bpy.data.materials.new("MAT_Bake_Temp")
    mat.use_nodes = True
    nt = mat.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bake_img
    tex.select = True
    nt.nodes.active = tex
    o.data.materials.append(mat)

bpy.ops.object.bake(type="AO", use_clear=True, margin=8,
                    use_selected_to_active=False)  # pass_filter sans 'AO' en 5.2
bake_img.filepath_raw = ao_png
bake_img.file_format = "PNG"
bake_img.save()
print(f"AO_BAKE_OK: {ao_png}")

# Rendu après : AO multipliée dans le Base Color d'un Principled.
for m in [m for m in bpy.data.materials if m.name.startswith("MAT_Bake_Temp")]:
    bpy.data.materials.remove(m)
mat = bpy.data.materials.new("MAT_Casque_AO")
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes["Principled BSDF"]
tex_ao = nt.nodes.new("ShaderNodeTexImage")
tex_ao.image = bake_img
mix = nt.nodes.new("ShaderNodeMix")
mix.data_type = "RGBA"
mix.blend_type = "MULTIPLY"
mix.inputs["Factor"].default_value = 1.0
alb = bpy.data.images.new("Albedo", 4, 4)
alb.generated_color = (0.55, 0.35, 0.6, 1.0)  # teinte violette de référence
tex_alb = nt.nodes.new("ShaderNodeTexImage")
tex_alb.image = alb
nt.links.new(tex_alb.outputs["Color"], mix.inputs["A"])
nt.links.new(tex_ao.outputs["Color"], mix.inputs["B"])
nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])

for nom, energie, direction in (("Cle", 500, Vector((1.0, -1.0, 1.0))),
                                ("Fond", 300, Vector((0.0, 1.4, 1.1)))):
    ld = bpy.data.lights.new(nom, type="AREA")
    ld.energy = energie * d0 * d0
    ld.size = d0 * 1.5
    lo = bpy.data.objects.new(nom, ld)
    lo.location = direction * d0 * 1.75
    lo.rotation_euler = (Vector((0, 0, 0.5)) - lo.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(lo)
monde = bpy.data.worlds.new("Monde")
monde.use_nodes = True
monde.node_tree.nodes["Background"].inputs[0].default_value = (0.32, 0.33, 0.36, 1.0)
monde.node_tree.nodes["Background"].inputs[1].default_value = 0.8
bpy.context.scene.world = monde

cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 50
cam = bpy.data.objects.new("Cam", cam_data)
cam.location = centre + Vector((0.62, -0.62, 0.45)) * d0 * 2.2
cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam
for moteur in ("BLENDER_EEVEE_NEXT_RENDER", "BLENDER_EEVEE_RENDER", "BLENDER_EEVEE"):
    try:
        scn.render.engine = moteur
        break
    except TypeError:
        continue
scn.render.resolution_x = scn.render.resolution_y = 700
scn.render.filepath = apercu_png
bpy.ops.render.render(write_still=True)
print("SUCCESS:")
