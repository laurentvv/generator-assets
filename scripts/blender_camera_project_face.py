# -*- coding: utf-8 -*-
"""
Blender Headless Script: Camera Projection of Marc's 2D Portrait onto the MakeHuman 3D Mesh.
1. Generates Marc's child anatomical model (8 years old) with MPFB2.
2. Sets up a calibrated frontal camera on the face.
3. Projects the canonical high-definition 2D portrait onto the 3D head geometry.
4. Performs the Cycles UV baking onto the standard UV map (2048x2048).
5. Blends the seams with the body skin and exports the final texture.
6. Renders a 3D preview of the face under studio lighting.
"""

import bpy
import importlib
import mathutils
import os
import sys

# Add the local virtualenv to access PIL / numpy if necessary
venv_site = r"C:\GIT\generator-assets\.venv\Lib\site-packages"
if os.path.exists(venv_site) and venv_site not in sys.path:
    sys.path.insert(0, venv_site)

from PIL import Image, ImageFilter

def dynamic_import(absolute_package_str, key):
    for amod in sys.modules:
        if amod.endswith(absolute_package_str):
            mpfb_mod = importlib.import_module(amod)
            if hasattr(mpfb_mod, key):
                return getattr(mpfb_mod, key)
    raise ValueError(f"Module {absolute_package_str} not found")

PORTRAIT_2D = r"C:\test\L'HERITIER DU VIDE\poc_3d\renders\marc_v2_visage_closeup.png"
SKIN_BASE = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\young_caucasian_male\young_lightskinned_male_diffuse.png"
SORTIE_DIFFUSE_MPFB = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\marc_novice\marc_novice_diffuse.png"
SORTIE_DIFFUSE_LOCAL = r"C:\GIT\generator-assets\godot_assets\skins\marc_novice\marc_novice_diffuse.png"
SORTIE_DIFFUSE_POC = r"C:\test\L'HERITIER DU VIDE\poc_3d\exports\marc_mpfb2_young_lightskinned_male_diffuse.png"
SORTIE_RENDER_PREVIEW = r"C:\GIT\generator-assets\godot_assets\marc_3d_projected_render.png"

print("\n" + "=" * 65)
print(" 🚀 LAUNCHING THE BLENDER PIPELINE: 2D FACE CAMERA PROJECTION ➔ 3D ")
print("=" * 65)

# 1. Blank scene & MPFB2 activation
bpy.ops.wm.read_factory_settings(use_empty=True)
try:
    bpy.ops.preferences.addon_enable(module="bl_ext.user_default.mpfb")
except Exception as e:
    print(f"MPFB extension note: {e}")

HumanService = dynamic_import("mpfb.services.humanservice", "HumanService")
TargetService = dynamic_import("mpfb.services.targetservice", "TargetService")

# 2. Marc child body (8 years old)
macros_marc = {
    "gender": 1.0,
    "age": 0.17,
    "muscle": 0.3,
    "weight": 0.25,
    "proportions": 0.5,
    "height": 0.5,
    "race": {"caucasian": 1.0, "asian": 0.0, "african": 0.0}
}
basemesh = HumanService.create_human(macro_detail_dict=macros_marc)
TargetService.reapply_macro_details(basemesh)
bpy.context.view_layer.update()

# Bake the shape keys to freeze the child morphology
dg = bpy.context.evaluated_depsgraph_get()
ev = basemesh.evaluated_get(dg)
me = bpy.data.meshes.new_from_object(ev)
old_me = basemesh.data
basemesh.data = me
me.name = "marc_basemesh_mesh"
bpy.data.meshes.remove(old_me)
bpy.context.view_layer.update()

# Remove the fitting masks
for m in list(basemesh.modifiers):
    if m.type == 'MASK':
        basemesh.modifiers.remove(m)

# 3. Compute the head bounding box
head_verts = [v for v in basemesh.data.vertices if v.co.z > 0.85]
center_x = sum(v.co.x for v in head_verts) / len(head_verts)
center_y = sum(v.co.y for v in head_verts) / len(head_verts)
center_z = sum(v.co.z for v in head_verts) / len(head_verts)
head_center = mathutils.Vector((center_x, center_y, center_z))
print(f"[MARC 3D] Head center detected: {head_center}")

# 4. Create the Face Projection Camera
cam_data = bpy.data.cameras.new("FaceProjectionCamera")
cam_data.type = 'PERSP'
cam_data.lens = 110.0  # Long portrait focal length to minimize distortion
cam_data.sensor_width = 36.0

cam_obj = bpy.data.objects.new("FaceProjectionCamera", cam_data)
bpy.context.collection.objects.link(cam_obj)

# Position the camera in front of the face (negative Y looks toward +Y)
cam_obj.location = mathutils.Vector((center_x, center_y - 0.72, center_z + 0.02))
cam_obj.rotation_euler = mathutils.Euler((1.5708, 0, 0), 'XYZ')  # 90° toward the forehead
bpy.context.view_layer.update()
print(f"[MARC 3D] Projection camera positioned at: {cam_obj.location}")

# 5. Create the Bake Image
bake_res = 2048
img_bake = bpy.data.images.new("Marc_Projected_Bake", width=bake_res, height=bake_res, alpha=True, float_buffer=False)

# Load Marc's 2D portrait
if not os.path.exists(PORTRAIT_2D):
    raise FileNotFoundError(f"2D portrait not found: {PORTRAIT_2D}")
img_portrait = bpy.data.images.load(PORTRAIT_2D, check_existing=False)

# 6. Camera Projection Shader
mat_proj = bpy.data.materials.new(name="Marc_Projection_Material")
mat_proj.use_nodes = True
nodes = mat_proj.node_tree.nodes
links = mat_proj.node_tree.links
nodes.clear()

out_node = nodes.new('ShaderNodeOutputMaterial')
emit_node = nodes.new('ShaderNodeEmission')

# Camera coordinates to project the 2D image
tex_coord = nodes.new('ShaderNodeTexCoord')
tex_coord.object = cam_obj

# Vector Transform & Mapping to frame the portrait on the face
mapping = nodes.new('ShaderNodeMapping')
mapping.inputs['Location'].default_value = (0.5, 0.5, 0.0)
mapping.inputs['Scale'].default_value = (1.0, 1.0, 1.0)

tex_portrait = nodes.new('ShaderNodeTexImage')
tex_portrait.image = img_portrait
tex_portrait.extension = 'CLIP'

# Target image node for the Baking
tex_target = nodes.new('ShaderNodeTexImage')
tex_target.image = img_bake
tex_target.select = True
nodes.active = tex_target

# Connection for the projection: Window/Camera coords to Texture Image
links.new(tex_coord.outputs['Camera'], tex_portrait.inputs['Vector'])
links.new(tex_portrait.outputs['Color'], emit_node.inputs['Color'])
links.new(emit_node.outputs['Emission'], out_node.inputs['Surface'])

# Apply the material to the basemesh
basemesh.data.materials.clear()
basemesh.data.materials.append(mat_proj)

# 7. Cycles Baking configuration
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'  # CPU is ultra-stable for a single bake in headless
bpy.context.scene.cycles.samples = 1
bpy.context.scene.cycles.bake_type = 'EMIT'
bpy.context.scene.render.bake.margin = 16

# Select the basemesh
bpy.context.view_layer.objects.active = basemesh
basemesh.select_set(True)

print("[MARC 3D] Starting the UV projection Baking...")
temp_bake_file = "temp_marc_baked_projection.png"
bpy.ops.object.bake(type='EMIT')
img_bake.filepath_raw = temp_bake_file
img_bake.file_format = 'PNG'
img_bake.save()
print(f"[MARC 3D] Baking finished: {temp_bake_file}")

# 8. Post-Processing & Blending with the Body Skin in PIL
print("[MARC 3D] Seamless blending with the body skin map...")
baked_pil = Image.open(temp_bake_file).convert("RGBA")
skin_base_pil = Image.open(SKIN_BASE).convert("RGBA").resize((bake_res, bake_res))

# Selection mask of the face zone on the UV layout (top-center)
w, h = baked_pil.size
masque_visage = Image.new("L", (w, h), 0)
import PIL.ImageDraw as ImageDraw
draw = ImageDraw.Draw(masque_visage)

# UV zone of the front of the head
draw.ellipse([w * 0.35, h * 0.12, w * 0.65, h * 0.46], fill=255)
masque_flou = masque_visage.filter(ImageFilter.GaussianBlur(radius=28))

# Composite: base skin + Marc's projection on the face
baked_visage = baked_pil.copy()
baked_visage.putalpha(masque_flou)

skin_complete_marc = Image.alpha_composite(skin_base_pil, baked_visage).convert("RGB")

# Save the textures
for p in [SORTIE_DIFFUSE_MPFB, SORTIE_DIFFUSE_LOCAL, SORTIE_DIFFUSE_POC]:
    os.makedirs(os.path.dirname(p), exist_ok=True)
    skin_complete_marc.save(p, "PNG", optimize=True)
    print(f"✅ Official UV texture saved: {p}")

# Update the .thumb vignette
thumb_crop = skin_complete_marc.crop((int(w * 0.30), int(h * 0.10), int(w * 0.70), int(h * 0.48)))
thumb_img = thumb_crop.resize((256, 256), Image.Resampling.LANCZOS).convert("RGBA")
thumb_mpfb = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\marc_novice\marc_novice.thumb"
thumb_local = r"C:\GIT\generator-assets\godot_assets\skins\marc_novice\marc_novice.thumb"
thumb_img.save(thumb_mpfb, "PNG")
thumb_img.save(thumb_local, "PNG")

# 9. 3D Preview Render (Face Closeup)
print("[MARC 3D] Rendering a 3D studio preview of the face...")
# Put back a Principled BSDF with the new complete texture
mat_final = bpy.data.materials.new(name="Marc_Final_Skin")
mat_final.use_nodes = True
n_final = mat_final.node_tree.nodes
l_final = mat_final.node_tree.links
n_final.clear()

out_f = n_final.new('ShaderNodeOutputMaterial')
bsdf_f = n_final.new('ShaderNodeBsdfPrincipled')
bsdf_f.inputs['Roughness'].default_value = 0.55

img_final_b = bpy.data.images.load(SORTIE_DIFFUSE_LOCAL, check_existing=False)
tex_f = n_final.new('ShaderNodeTexImage')
tex_f.image = img_final_b

l_final.new(tex_f.outputs['Color'], bsdf_f.inputs['Base Color'])
l_final.new(bsdf_f.outputs['BSDF'], out_f.inputs['Surface'])

basemesh.data.materials.clear()
basemesh.data.materials.append(mat_final)

# Key + Fill lights
light_data = bpy.data.lights.new(name="KeyLight", type='AREA')
light_data.energy = 80.0
light_data.size = 0.5
light_obj = bpy.data.objects.new(name="KeyLight", object_data=light_data)
bpy.context.collection.objects.link(light_obj)
light_obj.location = mathutils.Vector((center_x + 0.4, center_y - 0.6, center_z + 0.3))

# Render camera framed on the 3D face
render_cam_data = bpy.data.cameras.new("RenderCamera")
render_cam_data.lens = 85.0
render_cam = bpy.data.objects.new("RenderCamera", render_cam_data)
bpy.context.collection.objects.link(render_cam)
render_cam.location = mathutils.Vector((center_x + 0.05, center_y - 0.48, center_z))
render_cam.rotation_euler = mathutils.Euler((1.5708, 0, 0.1), 'XYZ')
bpy.context.scene.camera = render_cam

bpy.context.scene.render.resolution_x = 1024
bpy.context.scene.render.resolution_y = 1024
bpy.context.scene.render.filepath = SORTIE_RENDER_PREVIEW
bpy.context.scene.render.image_settings.file_format = 'PNG'

bpy.ops.render.render(write_still=True)
print(f"🎉 3D face preview rendered successfully: {SORTIE_RENDER_PREVIEW}")

# Temporary file cleanup
if os.path.exists(temp_bake_file):
    os.remove(temp_bake_file)

print("\n" + "=" * 65)
print(" ✅ CAMERA PROJECTION PIPELINE COMPLETED SUCCESSFULLY! ")
print("=" * 65)
