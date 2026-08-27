# -*- coding: utf-8 -*-
"""
Script Blender Headless : Projection Caméra du Portrait 2D de Marc sur le Mesh 3D MakeHuman.
1. Génère le modèle anatomique enfant de Marc (8 ans) avec MPFB2.
2. Configure une caméra frontale calibrée sur le visage.
3. Projette le portrait 2D canonique haute définition sur la géométrie 3D de la tête.
4. Effectue le baking UV Cycles sur la carte UV standard (2048x2048).
5. Fusionne les raccords avec la peau du corps et exporte la texture finale.
6. Rend un aperçu 3D du visage sous éclairage studio.
"""

import bpy
import bmesh
import importlib
import mathutils
import os
import sys

# Ajout du virtualenv local pour accéder à PIL / numpy si nécessaire
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
    raise ValueError(f"Module {absolute_package_str} introuvable")

PORTRAIT_2D = r"C:\test\L'HERITIER DU VIDE\poc_3d\renders\marc_v2_visage_closeup.png"
SKIN_BASE = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\young_caucasian_male\young_lightskinned_male_diffuse.png"
SORTIE_DIFFUSE_MPFB = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\marc_novice\marc_novice_diffuse.png"
SORTIE_DIFFUSE_LOCAL = r"C:\GIT\generator-assets\godot_assets\skins\marc_novice\marc_novice_diffuse.png"
SORTIE_DIFFUSE_POC = r"C:\test\L'HERITIER DU VIDE\poc_3d\exports\marc_mpfb2_young_lightskinned_male_diffuse.png"
SORTIE_RENDER_PREVIEW = r"C:\GIT\generator-assets\godot_assets\marc_3d_projected_render.png"

print("\n" + "=" * 65)
print(" 🚀 LANCEMENT DU PIPELINE BLENDER : PROJECTION CAMÉRA VISAGE 2D ➔ 3D ")
print("=" * 65)

# 1. Scène vierge & activation MPFB2
bpy.ops.wm.read_factory_settings(use_empty=True)
try:
    bpy.ops.preferences.addon_enable(module="bl_ext.user_default.mpfb")
except Exception as e:
    print(f"Note extension MPFB: {e}")

HumanService = dynamic_import("mpfb.services.humanservice", "HumanService")
TargetService = dynamic_import("mpfb.services.targetservice", "TargetService")

# 2. Corps enfant Marc (8 ans)
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

# Bake des shape keys pour figer la morphologie enfant
dg = bpy.context.evaluated_depsgraph_get()
ev = basemesh.evaluated_get(dg)
me = bpy.data.meshes.new_from_object(ev)
old_me = basemesh.data
basemesh.data = me
me.name = "marc_basemesh_mesh"
bpy.data.meshes.remove(old_me)
bpy.context.view_layer.update()

# Retrait des masques de fitting
for m in list(basemesh.modifiers):
    if m.type == 'MASK':
        basemesh.modifiers.remove(m)

# 3. Calcul de la boîte englobante de la tête
head_verts = [v for v in basemesh.data.vertices if v.co.z > 0.85]
center_x = sum(v.co.x for v in head_verts) / len(head_verts)
center_y = sum(v.co.y for v in head_verts) / len(head_verts)
center_z = sum(v.co.z for v in head_verts) / len(head_verts)
head_center = mathutils.Vector((center_x, center_y, center_z))
print(f"[MARC 3D] Centre de la tête détecté : {head_center}")

# 4. Création de la Caméra de Projection Face
cam_data = bpy.data.cameras.new("FaceProjectionCamera")
cam_data.type = 'PERSP'
cam_data.lens = 110.0  # Focale portrait longue pour minimiser la distorsion
cam_data.sensor_width = 36.0

cam_obj = bpy.data.objects.new("FaceProjectionCamera", cam_data)
bpy.context.collection.objects.link(cam_obj)

# Positionner la caméra face au visage (Y négatif regarde vers +Y)
cam_obj.location = mathutils.Vector((center_x, center_y - 0.72, center_z + 0.02))
cam_obj.rotation_euler = mathutils.Euler((1.5708, 0, 0), 'XYZ')  # 90° vers le front
bpy.context.view_layer.update()
print(f"[MARC 3D] Caméra de projection positionnée à : {cam_obj.location}")

# 5. Création de l'Image de Bake
bake_res = 2048
img_bake = bpy.data.images.new("Marc_Projected_Bake", width=bake_res, height=bake_res, alpha=True, float_buffer=False)

# Chargement du portrait 2D de Marc
if not os.path.exists(PORTRAIT_2D):
    raise FileNotFoundError(f"Portrait 2D introuvable : {PORTRAIT_2D}")
img_portrait = bpy.data.images.load(PORTRAIT_2D, check_existing=False)

# 6. Shader de Projection Caméra
mat_proj = bpy.data.materials.new(name="Marc_Projection_Material")
mat_proj.use_nodes = True
nodes = mat_proj.node_tree.nodes
links = mat_proj.node_tree.links
nodes.clear()

out_node = nodes.new('ShaderNodeOutputMaterial')
emit_node = nodes.new('ShaderNodeEmission')

# Coordonnées caméra pour projeter l'image 2D
tex_coord = nodes.new('ShaderNodeTexCoord')
tex_coord.object = cam_obj

# Vector Transform & Mapping pour cadrer le portrait sur le visage
mapping = nodes.new('ShaderNodeMapping')
mapping.inputs['Location'].default_value = (0.5, 0.5, 0.0)
mapping.inputs['Scale'].default_value = (1.0, 1.0, 1.0)

tex_portrait = nodes.new('ShaderNodeTexImage')
tex_portrait.image = img_portrait
tex_portrait.extension = 'CLIP'

# Nœud image cible pour le Baking
tex_target = nodes.new('ShaderNodeTexImage')
tex_target.image = img_bake
tex_target.select = True
nodes.active = tex_target

# Connexion pour la projection : Window/Camera coords vers Texture Image
links.new(tex_coord.outputs['Camera'], tex_portrait.inputs['Vector'])
links.new(tex_portrait.outputs['Color'], emit_node.inputs['Color'])
links.new(emit_node.outputs['Emission'], out_node.inputs['Surface'])

# Appliquer le matériau au basemesh
basemesh.data.materials.clear()
basemesh.data.materials.append(mat_proj)

# 7. Configuration du Baking Cycles
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'  # CPU est ultra-stable pour un bake unique en headless
bpy.context.scene.cycles.samples = 1
bpy.context.scene.cycles.bake_type = 'EMIT'
bpy.context.scene.render.bake.margin = 16

# Sélectionner basemesh
bpy.context.view_layer.objects.active = basemesh
basemesh.select_set(True)

print("[MARC 3D] Lancement du Baking UV de projection...")
temp_bake_file = "temp_marc_baked_projection.png"
bpy.ops.object.bake(type='EMIT')
img_bake.filepath_raw = temp_bake_file
img_bake.file_format = 'PNG'
img_bake.save()
print(f"[MARC 3D] Baking terminé : {temp_bake_file}")

# 8. Post-Processing & Fusion avec la Peau du Corps en PIL
print("[MARC 3D] Fusion sans couture avec la carte de peau corporelle...")
baked_pil = Image.open(temp_bake_file).convert("RGBA")
skin_base_pil = Image.open(SKIN_BASE).convert("RGBA").resize((bake_res, bake_res))

# Masque de sélection de la zone visage sur le patron UV (haut-centre)
w, h = baked_pil.size
masque_visage = Image.new("L", (w, h), 0)
import PIL.ImageDraw as ImageDraw
draw = ImageDraw.Draw(masque_visage)

# Zone UV de la face avant de la tête
draw.ellipse([w * 0.35, h * 0.12, w * 0.65, h * 0.46], fill=255)
masque_flou = masque_visage.filter(ImageFilter.GaussianBlur(radius=28))

# Composite : peau de base + projection de Marc sur la face
baked_visage = baked_pil.copy()
baked_visage.putalpha(masque_flou)

skin_complete_marc = Image.alpha_composite(skin_base_pil, baked_visage).convert("RGB")

# Sauvegarde des textures
for p in [SORTIE_DIFFUSE_MPFB, SORTIE_DIFFUSE_LOCAL, SORTIE_DIFFUSE_POC]:
    os.makedirs(os.path.dirname(p), exist_ok=True)
    skin_complete_marc.save(p, "PNG", optimize=True)
    print(f"✅ Texture UV officielle enregistrée : {p}")

# Mise à jour de la vignette .thumb
thumb_crop = skin_complete_marc.crop((int(w * 0.30), int(h * 0.10), int(w * 0.70), int(h * 0.48)))
thumb_img = thumb_crop.resize((256, 256), Image.Resampling.LANCZOS).convert("RGBA")
thumb_mpfb = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\marc_novice\marc_novice.thumb"
thumb_local = r"C:\GIT\generator-assets\godot_assets\skins\marc_novice\marc_novice.thumb"
thumb_img.save(thumb_mpfb, "PNG")
thumb_img.save(thumb_local, "PNG")

# 9. Rendu de Prévisualisation 3D (Closeup Visage)
print("[MARC 3D] Rendu d'un aperçu studio 3D du visage...")
# Remettre un Principled BSDF avec la nouvelle texture complète
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

# Lumière Key + Fill
light_data = bpy.data.lights.new(name="KeyLight", type='AREA')
light_data.energy = 80.0
light_data.size = 0.5
light_obj = bpy.data.objects.new(name="KeyLight", object_data=light_data)
bpy.context.collection.objects.link(light_obj)
light_obj.location = mathutils.Vector((center_x + 0.4, center_y - 0.6, center_z + 0.3))

# Caméra de rendu cadrée sur le visage 3D
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
print(f"🎉 Aperçu 3D du visage rendu avec succès : {SORTIE_RENDER_PREVIEW}")

# Nettoyage fichier temporaire
if os.path.exists(temp_bake_file):
    os.remove(temp_bake_file)

print("\n" + "=" * 65)
print(" ✅ PIPELINE DE PROJECTION CAMÉRA TERMINÉ AVEC SUCCÈS ! ")
print("=" * 65)
