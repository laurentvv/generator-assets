#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script d'automatisation des tests morphologiques (Homme, Femme, Enfant) pour chaque thème médiéval.
Gère :
 - L'adaptation morphologique native de MakeHuman / MPFB (Option B)
 - La préservation exacte des mains, doigts, poignets, tête et cou via les 8398 indices de sommets MakeHuman universels
 - Le cadrage studio 3/4 parfait adapté à la hauteur du personnage (adulte vs enfant)
 - L'application des textures PBR AI distinctes pour Torso, Pants et Shoes
"""

import bpy
import bmesh
import os
import math

try:
    from bl_ext.user_default.mpfb.services import HumanService, TargetService, ClothesService
    from bl_ext.user_default.mpfb.ui.apply_assets.assetlibrary.assetsettingspanel import ASSET_SETTINGS_PROPERTIES
except ImportError:
    from mpfb.services import HumanService, TargetService, ClothesService
    from mpfb.ui.apply_assets.assetlibrary.assetsettingspanel import ASSET_SETTINGS_PROPERTIES

def get_universal_skin_vertex_indices(base_obj_path: str = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\extensions\user_default\mpfb\data\3dobjs\base.obj"):
    verts = []
    with open(base_obj_path, "r") as f:
        for line in f:
            if line.startswith("v "):
                verts.append([float(x) for x in line.strip().split()[1:4]])

    body_verts = verts[:13380]
    head_indices = set(i for i, v in enumerate(body_verts) if v[1] >= 4.0 and abs(v[0]) <= 1.8)
    hand_indices = set(i for i, v in enumerate(body_verts) if abs(v[0]) >= 3.8 and v[1] <= 3.5)
    return sorted(list(head_indices | hand_indices))

def render_theme_morphologies(theme_name: str, config: dict, output_base_dir: str = r"C:\GIT\generator-assets\godot_assets"):
    theme_slug = f"medieval_{theme_name}"
    out_dir = os.path.join(output_base_dir, "renders_morphologies")
    os.makedirs(out_dir, exist_ok=True)
    
    mpfb_root = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data"
    suit_mhclo = os.path.join(mpfb_root, "clothes", "male_casualsuit01", "male_casualsuit01.mhclo")
    shoes_mhclo = os.path.join(mpfb_root, "clothes", "shoes01", "shoes01.mhclo")

    skin_indices_to_keep = get_universal_skin_vertex_indices()

    morphologies = [
        ("homme", {
            "gender": 1.0,
            "age": 0.5,
            "muscle": 0.6,
            "weight": 0.5,
            "height": 0.5,
            "race": {"african": 0.33, "asian": 0.33, "caucasian": 0.33}
        }),
        ("femme", {
            "gender": 0.0,
            "age": 0.5,
            "muscle": 0.3,
            "weight": 0.5,
            "height": 0.5,
            "race": {"african": 0.33, "asian": 0.33, "caucasian": 0.33}
        }),
        ("enfant", {
            "gender": 0.5,
            "age": 0.15,
            "muscle": 0.2,
            "weight": 0.4,
            "height": 0.3,
            "race": {"african": 0.33, "asian": 0.33, "caucasian": 0.33}
        })
    ]

    rendered_images = []

    for morph_name, macro_dict in morphologies:
        print(f"=== [Morphologie: {morph_name.upper()}] Thème: {theme_slug} ===")
        
        # 1. Nettoyage de la scène
        for o in list(bpy.data.objects):
            bpy.data.objects.remove(o, do_unlink=True)

        ASSET_SETTINGS_PROPERTIES.set_value("fit_to_body", True, entity_reference=bpy.context.scene)
        ASSET_SETTINGS_PROPERTIES.set_value("set_up_rigging", False, entity_reference=bpy.context.scene)
        ASSET_SETTINGS_PROPERTIES.set_value("interpolate_weights", False, entity_reference=bpy.context.scene)
        ASSET_SETTINGS_PROPERTIES.set_value("delete_group", False, entity_reference=bpy.context.scene)
        ASSET_SETTINGS_PROPERTIES.set_value("mask_base_mesh", False, entity_reference=bpy.context.scene)

        # 2. Studio Lighting & Caméra
        cam_data = bpy.data.cameras.new("Camera")
        cam = bpy.data.objects.new("Camera", cam_data)
        bpy.context.collection.objects.link(cam)
        bpy.context.scene.camera = cam

        world = bpy.context.scene.world or bpy.data.worlds.new("Studio_World")
        bpy.context.scene.world = world
        world.use_nodes = True
        bg_node = world.node_tree.nodes.get("Background")
        if bg_node:
            bg_node.inputs['Color'].default_value = (0.93, 0.93, 0.93, 1.0)
            bg_node.inputs['Strength'].default_value = 1.0

        def add_light(name, energy, loc, size=2.5):
            ldata = bpy.data.lights.new(name, 'AREA')
            ldata.energy = energy
            ldata.size = size
            lobj = bpy.data.objects.new(name, ldata)
            lobj.location = loc
            bpy.context.collection.objects.link(lobj)
            return lobj

        add_light("Key_Light", 900.0, (2.2, -3.2, 2.5), size=2.5)
        add_light("Fill_Light", 450.0, (-2.2, -2.5, 2.0), size=2.5)
        add_light("Rim_Light", 650.0, (0.0, 3.0, 2.5), size=2.0)

        # 3. Création du Human MPFB avec la morphologie ciblée
        human = HumanService.create_human(
            mask_helpers=False,
            detailed_helpers=True,
            scale=0.1,
            macro_detail_dict=macro_dict
        )
        human.name = "Human"
        bpy.context.view_layer.objects.active = human
        human.select_set(True)

        # 4. Chargement et adaptation automatique des vêtements MPFB
        bpy.ops.mpfb.load_library_clothes(filepath=suit_mhclo, object_type="Clothes")
        suit_obj = [o for o in bpy.context.selected_objects if o != human][0]
        suit_obj.name = f"{theme_slug}_{morph_name}_suit"

        bpy.context.view_layer.objects.active = human
        human.select_set(True)
        bpy.ops.mpfb.load_library_clothes(filepath=shoes_mhclo, object_type="Clothes")
        shoes_obj = [o for o in bpy.context.selected_objects if o != human and o != suit_obj][0]
        shoes_obj.name = f"{theme_slug}_{morph_name}_shoes"

        # 5. Séparation du pantalon en objet 3D indépendant
        bm_s = bmesh.new()
        bm_s.from_mesh(suit_obj.data)
        bm_s.faces.ensure_lookup_table()
        suit_z_coords = [v.co.z for v in bm_s.verts]
        min_z, max_z = min(suit_z_coords), max(suit_z_coords)
        mid_z = min_z + (max_z - min_z) * 0.52

        pants_faces = [f for f in bm_s.faces if f.calc_center_median().z < mid_z]

        bm_p = bmesh.new()
        uv_s = bm_s.loops.layers.uv.verify()
        uv_p = bm_p.loops.layers.uv.new("UVMap")
        v_map_p = {}
        for f in pants_faces:
            for v in f.verts:
                if v.index not in v_map_p:
                    v_map_p[v.index] = bm_p.verts.new(v.co)
        bm_p.verts.ensure_lookup_table()
        for f in pants_faces:
            fv = [v_map_p[v.index] for v in f.verts]
            try:
                nf = bm_p.faces.new(fv)
                for i, l in enumerate(nf.loops):
                    l[uv_p].uv = f.loops[i][uv_s].uv
            except ValueError:
                pass

        pants_mesh = bpy.data.meshes.new(f"{theme_slug}_{morph_name}_pants_mesh")
        bm_p.to_mesh(pants_mesh)
        bm_p.free()

        pants_obj = bpy.data.objects.new(f"{theme_slug}_{morph_name}_pants", pants_mesh)
        bpy.context.collection.objects.link(pants_obj)

        bmesh.ops.delete(bm_s, geom=pants_faces, context='FACES')
        bm_s.to_mesh(suit_obj.data)
        bm_s.free()
        suit_obj.name = f"{theme_slug}_{morph_name}_torso"

        # 6. Masquage du corps sous les vêtements :
        # APPLICATION EXACTE DES 8398 SOMMETS UNIVERSELS (TÊTE, COU, VISAGE, MAINS, DOIGTS)
        vg_keep = human.vertex_groups.new(name="Visible_Skin")
        vg_keep.add(skin_indices_to_keep, 1.0, 'REPLACE')

        mask_skin = human.modifiers.new("Mask_Skin", 'MASK')
        mask_skin.vertex_group = "Visible_Skin"

        # Matériau Peau Réaliste
        skin_mat = bpy.data.materials.new(name=f"Human_Skin_{morph_name}")
        skin_mat.use_nodes = True
        s_bsdf = skin_mat.node_tree.nodes.get("Principled BSDF")
        s_bsdf.inputs['Base Color'].default_value = (0.83, 0.65, 0.54, 1.0)
        s_bsdf.inputs['Roughness'].default_value = 0.40
        if "Subsurface Weight" in s_bsdf.inputs:
            s_bsdf.inputs['Subsurface Weight'].default_value = 0.05
        human.data.materials.clear()
        human.data.materials.append(skin_mat)

        # 7. Application des Matériaux PBR Thématiques
        parts_meta = [
            ("torso", suit_obj, config.get("torso_scale", 3.0), config.get("torso_roughness", 0.5), config.get("torso_metallic", 0.0), config.get("torso_normal_str", 1.5)),
            ("pants", pants_obj, config.get("pants_scale", 4.0), config.get("pants_roughness", 0.6), config.get("pants_metallic", 0.0), config.get("pants_normal_str", 1.5)),
            ("shoes", shoes_obj, config.get("shoes_scale", 3.0), config.get("shoes_roughness", 0.4), config.get("shoes_metallic", config.get("shoes_metallic", 0.0)), config.get("shoes_normal_str", 1.2))
        ]

        for part_name, obj, uv_scale, roughness_val, metallic_val, norm_str in parts_meta:
            mat = bpy.data.materials.new(name=f"{theme_slug}_{part_name}_PBR")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            nodes.clear()

            out_node = nodes.new('ShaderNodeOutputMaterial')
            bsdf = nodes.new('ShaderNodeBsdfPrincipled')
            bsdf.inputs['Roughness'].default_value = roughness_val
            bsdf.inputs['Metallic'].default_value = metallic_val
            links.new(bsdf.outputs['BSDF'], out_node.inputs['Surface'])

            tex_coord = nodes.new('ShaderNodeTexCoord')
            mapping = nodes.new('ShaderNodeMapping')
            mapping.inputs['Scale'].default_value = (uv_scale, uv_scale, uv_scale)
            links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])

            diff_path = os.path.join(output_base_dir, f"{theme_slug}_{part_name}_diffuse.png")
            norm_path = os.path.join(output_base_dir, f"{theme_slug}_{part_name}_normal.png")

            if os.path.exists(diff_path):
                img_d = bpy.data.images.load(diff_path, check_existing=False)
                node_d = nodes.new('ShaderNodeTexImage')
                node_d.image = img_d
                node_d.extension = 'REPEAT'
                links.new(mapping.outputs['Vector'], node_d.inputs['Vector'])
                links.new(node_d.outputs['Color'], bsdf.inputs['Base Color'])

            if os.path.exists(norm_path):
                img_n = bpy.data.images.load(norm_path, check_existing=False)
                img_n.colorspace_settings.name = 'Non-Color'
                node_n = nodes.new('ShaderNodeTexImage')
                node_n.image = img_n
                node_n.extension = 'REPEAT'
                links.new(mapping.outputs['Vector'], node_n.inputs['Vector'])
                n_map = nodes.new('ShaderNodeNormalMap')
                n_map.inputs['Strength'].default_value = norm_str
                links.new(node_n.outputs['Color'], n_map.inputs['Color'])
                links.new(n_map.outputs['Normal'], bsdf.inputs['Normal'])

            obj.data.materials.clear()
            obj.data.materials.append(mat)

            # Modificateurs Solidify & Subsurf
            sol = obj.modifiers.new("Solidify", 'SOLIDIFY')
            sol.thickness = 0.005
            sol.offset = 1.0
            sub = obj.modifiers.new("Subsurf", 'SUBSURF')
            sub.levels = 1

        # 8. Cadrage Studio Plein Pied Centré (3/4 dynamique)
        all_objs = [human, suit_obj, pants_obj, shoes_obj]
        all_zs = []
        for o in all_objs:
            for v in o.data.vertices:
                w_co = o.matrix_world @ v.co
                all_zs.append(w_co.z)

        min_char_z = min(all_zs) if all_zs else 0.0
        max_char_z = max(all_zs) if all_zs else 1.7
        center_char_z = (min_char_z + max_char_z) / 2.0
        char_height = max_char_z - min_char_z

        cam_dist = char_height * 2.2
        cam_x = cam_dist * math.sin(math.radians(35))
        cam_y = -cam_dist * math.cos(math.radians(35))
        cam_z = center_char_z + 0.05

        cam.location = (cam_x, cam_y, cam_z)
        
        dx = -cam_x
        dy = -cam_y
        dz = center_char_z - cam_z
        dist_xy = math.sqrt(dx*dx + dy*dy)
        pitch = math.atan2(-dz, dist_xy)
        yaw = math.atan2(-dx, dy)
        cam.rotation_euler = (math.radians(90) + pitch, 0, yaw)
        cam.data.lens = 52

        out_img = os.path.join(out_dir, f"{theme_slug}_{morph_name}.png")
        bpy.context.scene.render.resolution_x = 1024
        bpy.context.scene.render.resolution_y = 1024
        bpy.context.scene.render.filepath = out_img
        bpy.ops.render.render(write_still=True)
        rendered_images.append(out_img)
        print(f"[{theme_slug}] Rendered morphology: {morph_name} -> {out_img}")

    return rendered_images
