# -*- coding: utf-8 -*-
import bpy
import bmesh
import importlib
import mathutils
import os
import sys

def dynamic_import(absolute_package_str, key):
    for amod in sys.modules:
        if amod.endswith(absolute_package_str):
            mpfb_mod = importlib.import_module(amod)
            if hasattr(mpfb_mod, key):
                return getattr(mpfb_mod, key)
    raise ValueError(f"Module {absolute_package_str} introuvable")

bpy.ops.wm.read_factory_settings(use_empty=True)
try:
    bpy.ops.preferences.addon_enable(module="bl_ext.user_default.mpfb")
except Exception:
    pass

HumanService = dynamic_import("mpfb.services.humanservice", "HumanService")
AssetService = dynamic_import("mpfb.services.assetservice", "AssetService")
TargetService = dynamic_import("mpfb.services.targetservice", "TargetService")

# 1. Création du corps enfant 8 ans
macros = {
    "gender": 1.0, "age": 0.17, "muscle": 0.3, "weight": 0.25,
    "proportions": 0.5, "height": 0.5,
    "race": {"caucasian": 1.0, "asian": 0.0, "african": 0.0}
}
basemesh = HumanService.create_human(macro_detail_dict=macros)
TargetService.reapply_macro_details(basemesh)
bpy.context.view_layer.update()

# 2. Application du skin Marc
skin_path = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\marc_novice\marc_novice.mhmat"
HumanService.set_character_skin(skin_path, basemesh, skin_type="GAMEENGINE")

# Déconnexion alpha skin
for mat in basemesh.data.materials:
    if mat and mat.node_tree:
        bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if bsdf and bsdf.inputs.get("Alpha"):
            for lk in list(bsdf.inputs["Alpha"].links):
                mat.node_tree.links.remove(lk)
            bsdf.inputs["Alpha"].default_value = 1.0
        an = mat.node_tree.nodes.get("AlphaMapTexture")
        if an:
            mat.node_tree.nodes.remove(an)

# 3. Ajout des assets tête
for subdir, fname, atype in [
    ("eyes",      "low-poly.mhclo",     "Eyes"),
    ("eyebrows",  "eyebrow001.mhclo",   "Eyebrows"),
    ("eyelashes", "eyelashes01.mhclo",  "Eyelashes"),
    ("tongue",    "tongue01.mhclo",     "Tongue"),
    ("teeth",     "teeth_base.mhclo",   "Teeth"),
    ("hair",      "short01.mhclo",      "Hair"),
]:
    p = AssetService.find_asset_absolute_path(fname, asset_subdir=subdir)
    if p:
        HumanService.add_mhclo_asset(p, basemesh, asset_type=atype, material_type="GAMEENGINE")

# 4. Ajout des vêtements SANS supprimer le corps
suit_p = AssetService.find_asset_absolute_path("male_worksuit01.mhclo", asset_subdir="clothes")
shoes_p = AssetService.find_asset_absolute_path("shoes01.mhclo", asset_subdir="clothes")
if suit_p:
    HumanService.add_mhclo_asset(suit_p, basemesh, asset_type="Clothes", material_type="GAMEENGINE")
if shoes_p:
    HumanService.add_mhclo_asset(shoes_p, basemesh, asset_type="Clothes", material_type="GAMEENGINE")

# Retirer tous les modificateurs MASK sur basemesh
for m in list(basemesh.modifiers):
    if m.type == 'MASK':
        basemesh.modifiers.remove(m)

# 5. Bake shape keys de TOUS les objets ensemble
dg = bpy.context.evaluated_depsgraph_get()
for obj in [o for o in bpy.data.objects if o.type == 'MESH']:
    if obj.data.shape_keys:
        ev = obj.evaluated_get(dg)
        me = bpy.data.meshes.new_from_object(ev)
        old_me = obj.data
        obj.data = me
        me.name = old_me.name
        bpy.data.meshes.remove(old_me)

# 6. Calibrage à 1.18m : on applique le scale et le translate globalement sur tous les meshes
all_mesh_objs = [o for o in bpy.data.objects if o.type == 'MESH']
all_verts = [o.matrix_world @ v.co for o in all_mesh_objs for v in o.data.vertices]
z_min, z_max = min(p.z for p in all_verts), max(p.z for p in all_verts)
y_min, y_max = min(p.y for p in all_verts), max(p.y for p in all_verts)
x_min, x_max = min(p.x for p in all_verts), max(p.x for p in all_verts)

h_reelle = z_max - z_min
target_h = 1.18
scale_f = target_h / h_reelle

# Mise à l'échelle uniforme
for o in all_mesh_objs:
    o.scale *= scale_f

bpy.context.view_layer.update()
bpy.ops.object.select_all(action='DESELECT')
for o in all_mesh_objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = basemesh
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
bpy.context.view_layer.update()

# Recalage Z=0 et centrage X=0, Y=0
all_verts2 = [o.matrix_world @ v.co for o in all_mesh_objs for v in o.data.vertices]
z_min2 = min(p.z for p in all_verts2)
y_center2 = (min(p.y for p in all_verts2) + max(p.y for p in all_verts2)) / 2.0
x_center2 = (min(p.x for p in all_verts2) + max(p.x for p in all_verts2)) / 2.0

for o in all_mesh_objs:
    o.location.z -= z_min2
    o.location.y -= y_center2
    o.location.x -= x_center2

bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
bpy.context.view_layer.update()

# Application des textures PBR Paysan sur les vêtements
GA_ASSETS = r"C:\GIT\generator-assets\godot_assets"
PEASANT_CFG = {
    "torso_scale": 3.5, "torso_roughness": 0.85, "torso_normal_str": 1.4,
    "shoes_scale": 3.0, "shoes_roughness": 0.65, "shoes_normal_str": 1.2,
}

def pbr_material(part, uv_scale, roughness, normal_str):
    mat = bpy.data.materials.new(name=f"peasant_{part}_PBR")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out_node = nodes.new('ShaderNodeOutputMaterial')
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = roughness
    links.new(bsdf.outputs['BSDF'], out_node.inputs['Surface'])
    diff = os.path.join(GA_ASSETS, f"medieval_peasant_{part}_diffuse.png")
    norm = os.path.join(GA_ASSETS, f"medieval_peasant_{part}_normal.png")
    if os.path.exists(diff):
        node_d = nodes.new('ShaderNodeTexImage')
        node_d.image = bpy.data.images.load(diff, check_existing=False)
        node_d.extension = 'REPEAT'
        links.new(node_d.outputs['Color'], bsdf.inputs['Base Color'])
    if os.path.exists(norm):
        img_n = bpy.data.images.load(norm, check_existing=False)
        img_n.colorspace_settings.name = 'Non-Color'
        node_n = nodes.new('ShaderNodeTexImage')
        node_n.image = img_n
        node_n.extension = 'REPEAT'
        n_map = nodes.new('ShaderNodeNormalMap')
        n_map.inputs['Strength'].default_value = normal_str
        links.new(node_n.outputs['Color'], n_map.inputs['Color'])
        links.new(n_map.outputs['Normal'], bsdf.inputs['Normal'])
    return mat

suit_obj = next((o for o in bpy.data.objects if "worksuit" in o.name.lower() or "peasant_torso" in o.name.lower()), None)
shoes_obj = next((o for o in bpy.data.objects if "shoes" in o.name.lower()), None)
if suit_obj:
    suit_obj.data.materials.clear()
    suit_obj.data.materials.append(pbr_material("torso", 3.5, 0.85, 1.4))
if shoes_obj:
    shoes_obj.data.materials.clear()
    shoes_obj.data.materials.append(pbr_material("shoes", 3.0, 0.65, 1.2))

# Sauvegarde des .blend
bpy.ops.wm.save_as_mainfile(filepath=r"C:\test\L'HERITIER DU VIDE\poc_3d\exports\marc_mpfb2.blend")
bpy.ops.wm.save_as_mainfile(filepath=r"C:\GIT\generator-assets\godot_assets\marc_novice.blend")

# Render validation plein pied
cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 45.0
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.collection.objects.link(cam)
cam.location = (0, -2.8, 0.70)
cam.rotation_euler = (1.5708, 0, 0)
bpy.context.scene.camera = cam

light_data = bpy.data.lights.new("Sun", 'SUN')
light_data.energy = 4.0
light = bpy.data.objects.new("Sun", light_data)
bpy.context.collection.objects.link(light)

bpy.context.scene.render.engine = 'BLENDER_WORKBENCH'
bpy.context.scene.render.filepath = r"C:\GIT\generator-assets\godot_assets\inspect_viewport_blend_fixed.png"
bpy.ops.render.render(write_still=True)
print("✅ Modèle complet généré sans décapitation ni découpe !")
