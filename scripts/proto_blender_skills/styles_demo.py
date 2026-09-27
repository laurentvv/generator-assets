# Style recipes borrowed from blender-skills (anime/cel, lowpoly/PS1, materials/wear)
# — headless demo on our GLBs. Three modes:
#   toon : diffuse → constant ColorRamp 3 steps + rim band (cel-shading)
#   psx  : snap vertices to grid, flat shading, AA off, Mist fog + 640x480 render
#   wear : procedural Pointiness wear → bright metal edges (over the existing albedo)
# Usage: blender --background --python styles_demo.py -- <glb_in> <out_png> <mode>

import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
glb_in, out_png, mode = argv[0], argv[1], argv[2]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb_in)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
assert meshes, "no mesh in the GLB"

bpy.ops.object.select_all(action="DESELECT")
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
bpy.ops.object.origin_set(type="ORIGIN_CENTER_OF_MASS", center="BOUNDS")

pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
max_dim = max(max(p.x for p in pts) - min(p.x for p in pts),
              max(p.y for p in pts) - min(p.y for p in pts),
              max(p.z for p in pts) - min(p.z for p in pts))
scale = 2.0 / max(max_dim, 1e-9)
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

scn = bpy.context.scene
for moteur in ("BLENDER_EEVEE_NEXT_RENDER", "BLENDER_EEVEE_RENDER", "BLENDER_EEVEE"):
    try:
        scn.render.engine = moteur
        break
    except TypeError:
        continue


def eclairage_simple(energie_key=3.0):
    """Single key + clear world (cel rule: test early under a single key light)."""
    ld = bpy.data.lights.new("Soleil", type="SUN")
    ld.energy = energie_key
    lo = bpy.data.objects.new("Soleil", ld)
    lo.rotation_euler = (Vector((0, 0, 0)) - Vector((2, -2, 3))).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(lo)
    monde = bpy.data.worlds.new("Monde")
    monde.use_nodes = True
    monde.node_tree.nodes["Background"].inputs[0].default_value = (0.85, 0.86, 0.88, 1.0)
    monde.node_tree.nodes["Background"].inputs[1].default_value = 0.6
    bpy.context.scene.world = monde


def camera_studio(lens=50):
    # Distance on the CURRENT bbox (after normalization): the global max_dim
    # is computed BEFORE scaling → wrong framing otherwise.
    pts_actuel = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    md = max(max(p.x for p in pts_actuel) - min(p.x for p in pts_actuel),
             max(p.y for p in pts_actuel) - min(p.y for p in pts_actuel),
             max(p.z for p in pts_actuel) - min(p.z for p in pts_actuel))
    direction = Vector((1.6, -1.6, 0.9)).normalized()
    dist = md * 2.6 + 0.8
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = lens
    cam = bpy.data.objects.new("Cam", cam_data)
    cam.location = centre + direction * dist
    cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam


if mode == "toon":
    # Diffuse → CONSTANT ColorRamp 3 steps + rim band (Layer Weight → Emission).
    for o in meshes:
        o.data.materials.clear()
        mat = bpy.data.materials.new("MAT_Toon")
        mat.use_nodes = True
        nt = mat.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        diff = nt.nodes.new("ShaderNodeBsdfDiffuse")
        cr = nt.nodes.new("ShaderNodeValToRGB")
        cr.color_ramp.interpolation = "CONSTANT"
        e = cr.color_ramp.elements
        e[0].position, e[0].color = 0.0, (0.08, 0.05, 0.10, 1.0)
        e[1].position, e[1].color = 0.42, (0.45, 0.22, 0.50, 1.0)
        mid = e.new(0.68)
        mid.color = (0.72, 0.45, 0.78, 1.0)
        nt.links.new(diff.outputs["BSDF"], cr.inputs["Fac"])
        rim = nt.nodes.new("ShaderNodeLayerWeight")
        rim.inputs["Blend"].default_value = 0.35
        bande = nt.nodes.new("ShaderNodeValToRGB")
        bande.color_ramp.interpolation = "CONSTANT"
        bande.color_ramp.elements[0].position = 0.82
        bande.color_ramp.elements[1].position = 0.92
        emis = nt.nodes.new("ShaderNodeEmission")
        emis.inputs["Color"].default_value = (0.95, 0.9, 1.0, 1.0)
        emis.inputs["Strength"].default_value = 1.0
        add = nt.nodes.new("ShaderNodeAddShader")
        nt.links.new(rim.outputs["Facing"], bande.inputs["Fac"])
        nt.links.new(bande.outputs["Color"], emis.inputs["Color"])
        nt.links.new(cr.outputs["Color"], add.inputs[0])
        nt.links.new(emis.outputs["Emission"], add.inputs[1])
        nt.links.new(add.outputs["Shader"], out.inputs["Surface"])
        o.data.materials.append(mat)
    eclairage_simple(3.5)
    camera_studio()
    scn.render.resolution_x = scn.render.resolution_y = 700

elif mode == "psx":
    # Vertex snapping (world grid 0.01), flat shading, minimal AA, volumetric
    # blue-gray fog (the Mist pass is no longer exposed by 5.2 compositing),
    # 640×480 render.
    for o in meshes:
        for v in o.data.vertices:
            v.co.x = round(v.co.x, 2)
            v.co.y = round(v.co.y, 2)
            v.co.z = round(v.co.z, 2)
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.shade_flat()
        for m in o.data.materials:
            if m and m.use_nodes:
                b = m.node_tree.nodes.get("Principled BSDF")
                if b:
                    b.inputs["Metallic"].default_value = 0.0
                    b.inputs["Roughness"].default_value = 1.0
    try:
        scn.eevee.taa_render_samples = 8
    except AttributeError:
        pass
    scn.render.resolution_x = 640
    scn.render.resolution_y = 480
    eclairage_simple(2.5)
    camera_studio()
    bpy.context.scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.6, 0.68, 1.0)
    bpy.context.scene.world.node_tree.nodes["Background"].inputs[1].default_value = 1.0
    # Fog cube: transparent surface + tinted Volume Scatter.
    bpy.ops.mesh.primitive_cube_add(size=16, location=centre)
    cube = bpy.context.active_object
    fog = bpy.data.materials.new("MAT_Brouillard_PSX")
    fog.use_nodes = True
    fnt = fog.node_tree
    for n in list(fnt.nodes):
        fnt.nodes.remove(n)
    out_f = fnt.nodes.new("ShaderNodeOutputMaterial")
    transp = fnt.nodes.new("ShaderNodeBsdfTransparent")
    vol = fnt.nodes.new("ShaderNodeVolumeScatter")
    vol.inputs["Color"].default_value = (0.55, 0.62, 0.75, 1.0)
    vol.inputs["Density"].default_value = 0.055
    fnt.links.new(transp.outputs["BSDF"], out_f.inputs["Surface"])
    fnt.links.new(vol.outputs["Volume"], out_f.inputs["Volume"])
    cube.data.materials.append(fog)
    cube.display_type = "WIRE"  # not shown in render, volume still evaluated

elif mode == "wear":
    # Procedural wear: Pointiness → ramp → light metal mix on edges.
    for o in meshes:
        o.data.materials.clear()
        mat = bpy.data.materials.new("MAT_Wear")
        mat.use_nodes = True
        nt = mat.node_tree
        b = nt.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (0.35, 0.22, 0.12, 1.0)  # dark wood
        b.inputs["Roughness"].default_value = 0.85
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        cr = nt.nodes.new("ShaderNodeValToRGB")
        cr.color_ramp.elements[0].position = 0.48
        cr.color_ramp.elements[1].position = 0.62
        cr.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MIX"
        mix.inputs["A"].default_value = (0.35, 0.22, 0.12, 1.0)
        mix.inputs["B"].default_value = (0.62, 0.58, 0.52, 1.0)  # light worn wood
        nt.links.new(geo.outputs["Pointiness"], cr.inputs["Fac"])
        nt.links.new(cr.outputs["Color"], mix.inputs["Factor"])
        nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
        o.data.materials.append(mat)
    eclairage_simple(3.0)
    camera_studio()
    scn.render.resolution_x = scn.render.resolution_y = 700

elif mode == "rust":
    # Procedural rust: Noise (scale 8) → threshold ramp → orange-brown mix,
    # roughness ↑ and metallic ↓ in rusty areas.
    for o in meshes:
        o.data.materials.clear()
        mat = bpy.data.materials.new("MAT_Rust")
        mat.use_nodes = True
        nt = mat.node_tree
        b = nt.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (0.45, 0.44, 0.43, 1.0)
        b.inputs["Metallic"].default_value = 1.0
        b.inputs["Roughness"].default_value = 0.35
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 8.0
        cr = nt.nodes.new("ShaderNodeValToRGB")
        cr.color_ramp.elements[0].position = 0.52
        cr.color_ramp.elements[1].position = 0.66
        mixc = nt.nodes.new("ShaderNodeMix")
        mixc.data_type = "RGBA"
        mixc.blend_type = "MIX"
        mixc.inputs["A"].default_value = (0.45, 0.44, 0.43, 1.0)
        mixc.inputs["B"].default_value = (0.38, 0.16, 0.06, 1.0)  # orange-brown
        mixr = nt.nodes.new("ShaderNodeMix")
        mixr.data_type = "FLOAT"
        mixr.inputs["A"].default_value = 0.35
        mixr.inputs["B"].default_value = 0.95
        mixm = nt.nodes.new("ShaderNodeMix")
        mixm.data_type = "FLOAT"
        mixm.inputs["A"].default_value = 1.0
        mixm.inputs["B"].default_value = 0.0
        nt.links.new(noise.outputs["Fac"], cr.inputs["Fac"])
        nt.links.new(cr.outputs["Color"], mixc.inputs["Factor"])
        nt.links.new(cr.outputs["Color"], mixr.inputs["Factor"])
        nt.links.new(cr.outputs["Color"], mixm.inputs["Factor"])
        nt.links.new(mixc.outputs["Result"], b.inputs["Base Color"])
        nt.links.new(mixr.outputs["Result"], b.inputs["Roughness"])
        nt.links.new(mixm.outputs["Result"], b.inputs["Metallic"])
        o.data.materials.append(mat)
    eclairage_simple(3.0)
    camera_studio()
    scn.render.resolution_x = scn.render.resolution_y = 700

elif mode == "moss":
    # Moss: pointiness (crevices) + upward normal (Z+) → moss green,
    # roughness ↑ (moss increases roughness).
    for o in meshes:
        o.data.materials.clear()
        mat = bpy.data.materials.new("MAT_Moss")
        mat.use_nodes = True
        nt = mat.node_tree
        b = nt.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (0.30, 0.20, 0.12, 1.0)
        b.inputs["Roughness"].default_value = 0.8
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        up = nt.nodes.new("ShaderNodeMapRange")
        up.inputs["From Min"].default_value = 0.4
        up.inputs["From Max"].default_value = 1.0
        creux = nt.nodes.new("ShaderNodeMapRange")
        creux.inputs["From Min"].default_value = 0.45
        creux.inputs["From Max"].default_value = 0.52
        creux.clamp = True
        mult = nt.nodes.new("ShaderNodeMath")
        mult.operation = "MULTIPLY"
        mixc = nt.nodes.new("ShaderNodeMix")
        mixc.data_type = "RGBA"
        mixc.inputs["A"].default_value = (0.30, 0.20, 0.12, 1.0)
        mixc.inputs["B"].default_value = (0.10, 0.22, 0.05, 1.0)  # moss green
        mixr = nt.nodes.new("ShaderNodeMix")
        mixr.data_type = "FLOAT"
        mixr.inputs["A"].default_value = 0.8
        mixr.inputs["B"].default_value = 1.0
        nt.links.new(geo.outputs["Normal"], sep.inputs["Vector"])
        nt.links.new(sep.outputs["Z"], up.inputs["Value"])
        nt.links.new(geo.outputs["Pointiness"], creux.inputs["Value"])
        nt.links.new(up.outputs["Result"], mult.inputs[0])
        nt.links.new(creux.outputs["Result"], mult.inputs[1])
        nt.links.new(mult.outputs["Value"], mixc.inputs["Factor"])
        nt.links.new(mult.outputs["Value"], mixr.inputs["Factor"])
        nt.links.new(mixc.outputs["Result"], b.inputs["Base Color"])
        nt.links.new(mixr.outputs["Result"], b.inputs["Roughness"])
        o.data.materials.append(mat)
    eclairage_simple(3.0)
    camera_studio()
    scn.render.resolution_x = scn.render.resolution_y = 700

elif mode == "water":
    # Water stains: vertical gradient (inverted Generated Z) × noise → darkened
    # albedo + slightly increased roughness (top of wall/corners).
    for o in meshes:
        o.data.materials.clear()
        mat = bpy.data.materials.new("MAT_WaterStain")
        mat.use_nodes = True
        nt = mat.node_tree
        b = nt.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (0.55, 0.52, 0.48, 1.0)  # plaster
        b.inputs["Roughness"].default_value = 0.7
        texco = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        grad = nt.nodes.new("ShaderNodeMapRange")
        grad.inputs["From Min"].default_value = 0.9
        grad.inputs["From Max"].default_value = 0.4  # inverted: top = 1
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 5.0
        mult = nt.nodes.new("ShaderNodeMath")
        mult.operation = "MULTIPLY"
        mixc = nt.nodes.new("ShaderNodeMix")
        mixc.data_type = "RGBA"
        mixc.inputs["A"].default_value = (0.55, 0.52, 0.48, 1.0)
        mixc.inputs["B"].default_value = (0.22, 0.18, 0.14, 1.0)  # dark halo
        mixr = nt.nodes.new("ShaderNodeMix")
        mixr.data_type = "FLOAT"
        mixr.inputs["A"].default_value = 0.7
        mixr.inputs["B"].default_value = 0.95
        nt.links.new(texco.outputs["Generated"], sep.inputs["Vector"])
        nt.links.new(sep.outputs["Z"], grad.inputs["Value"])
        nt.links.new(noise.outputs["Fac"], mult.inputs[0])
        nt.links.new(grad.outputs["Result"], mult.inputs[1])
        nt.links.new(mult.outputs["Value"], mixc.inputs["Factor"])
        nt.links.new(mult.outputs["Value"], mixr.inputs["Factor"])
        nt.links.new(mixc.outputs["Result"], b.inputs["Base Color"])
        nt.links.new(mixr.outputs["Result"], b.inputs["Roughness"])
        o.data.materials.append(mat)
    eclairage_simple(3.0)
    camera_studio()
    scn.render.resolution_x = scn.render.resolution_y = 700

elif mode == "panel":
    # Per-material color variation (adapted "panel variation" pattern):
    # random Hue Shift seeded by material index, ±10 % max value.
    for i, o in enumerate(meshes):
        o.data.materials.clear()
        mat = bpy.data.materials.new(f"MAT_Panel_{i:02d}")
        mat.use_nodes = True
        nt = mat.node_tree
        b = nt.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (0.42, 0.44, 0.48, 1.0)
        hsv = nt.nodes.new("ShaderNodeHueSaturation")
        rgb = nt.nodes.new("ShaderNodeRGB")
        rgb.outputs[0].default_value = (0.42, 0.44, 0.48, 1.0)
        hsv.inputs["Hue"].default_value = 0.5 + ((i * 37 % 11) - 5) * 0.008  # seeded ±0.04
        hsv.inputs["Value"].default_value = 1.0 - (i * 23 % 9) * 0.015       # −0..12 %
        nt.links.new(rgb.outputs["Color"], hsv.inputs["Color"])
        nt.links.new(hsv.outputs["Color"], b.inputs["Base Color"])
        o.data.materials.append(mat)
    eclairage_simple(3.0)
    camera_studio()
    scn.render.resolution_x = scn.render.resolution_y = 700

scn.render.filepath = out_png
bpy.ops.render.render(write_still=True)
print(f"STYLE_OK: {mode} → {out_png}")
print("SUCCESS:")
