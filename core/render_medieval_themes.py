#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script d'habillage et de rendu multi-angles des thèmes médiévaux (Option B) sous Blender.
Gère les 3 objets de vêtements 100% indépendants :
 - medieval_<theme>_torso (Tunique / Plastron / Veste)
 - medieval_<theme>_pants (Braies / Chausses / Grèves)
 - medieval_<theme>_shoes (Sabots / Bottes / Solerets)
Et affiche parfaitement les mains, poignets, cou et tête du modèle Human.
"""

import bpy
import bmesh
import os
import math

def render_outfit_theme(theme_name: str, config: dict, output_base_dir: str = r"C:\GIT\generator-assets\godot_assets"):
    godot_dir = output_base_dir
    theme_slug = f"medieval_{theme_name}"
    out_dir = os.path.join(godot_dir, f"renders_{theme_slug}")
    os.makedirs(out_dir, exist_ok=True)
    
    mpfb_root = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data"
    objsdir = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\extensions\user_default\mpfb\data\3dobjs"
    base_obj_path = os.path.join(objsdir, "base.obj")
    suit_obj_path = os.path.join(mpfb_root, "clothes", "male_casualsuit01", "male_casualsuit01.obj")
    shoes_obj_path = os.path.join(mpfb_root, "clothes", "shoes01", "shoes01.obj")

    # Nettoyage de la scène
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)

    # 1. Caméra et éclairage studio 3 points
    cam_data = bpy.data.cameras.new("Camera")
    cam = bpy.data.objects.new("Camera", cam_data)
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    # Fond de scène studio neutre
    world = bpy.context.scene.world or bpy.data.worlds.new("Studio_World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get("Background")
    if bg_node:
        bg_node.inputs['Color'].default_value = (0.92, 0.92, 0.92, 1.0)
        bg_node.inputs['Strength'].default_value = 1.0

    def add_studio_light(name, energy, loc, size=2.5):
        ldata = bpy.data.lights.new(name, 'AREA')
        ldata.energy = energy
        ldata.size = size
        lobj = bpy.data.objects.new(name, ldata)
        lobj.location = loc
        bpy.context.collection.objects.link(lobj)
        return lobj

    add_studio_light("Key_Light", 800.0, (2.5, -3.2, 2.5), size=2.5)
    add_studio_light("Fill_Light", 400.0, (-2.5, -2.5, 2.0), size=2.5)
    add_studio_light("Rim_Light", 600.0, (0.0, 3.2, 2.5), size=2.0)

    # 2. Import Base Human MakeHuman
    bpy.ops.wm.obj_import(filepath=base_obj_path)
    human = bpy.context.selected_objects[0]
    human.name = "Human"

    # Import Vêtements Option B
    bpy.ops.wm.obj_import(filepath=suit_obj_path)
    suit = bpy.context.selected_objects[0]
    suit.name = f"{theme_slug}_torso"

    bpy.ops.wm.obj_import(filepath=shoes_obj_path)
    shoes = bpy.context.selected_objects[0]
    shoes.name = f"{theme_slug}_shoes"

    # Mise à l'échelle métrique (0.1)
    for o in [human, suit, shoes]:
        o.scale = (0.1, 0.1, 0.1)
        bpy.context.view_layer.objects.active = o
        o.select_set(True)
    bpy.ops.object.transform_apply(scale=True)

    # 3. Masquage propre du corps sous les vêtements :
    # AFFICHE CLAIREMENT :
    #  - La tête et le cou (z >= 0.44 et |x| <= 0.16)
    #  - Les mains, paumes, doigts et poignets complets (|x| >= 0.39 et z <= 0.35)
    vg_keep = human.vertex_groups.new(name="Visible_Skin")
    skin_verts = [v.index for v in human.data.vertices if (
        v.index < 13380 and (
            (v.co.z >= 0.44 and abs(v.co.x) <= 0.16) or # Tête et cou complets
            (abs(v.co.x) >= 0.39 and v.co.z <= 0.35)     # Mains, doigts et poignets complets
        )
    )]
    vg_keep.add(skin_verts, 1.0, 'REPLACE')

    mask_skin = human.modifiers.new("Mask_Skin", 'MASK')
    mask_skin.vertex_group = "Visible_Skin"

    skin_mat = bpy.data.materials.new(name="Human_Skin")
    skin_mat.use_nodes = True
    s_bsdf = skin_mat.node_tree.nodes.get("Principled BSDF")
    s_bsdf.inputs['Base Color'].default_value = (0.85, 0.68, 0.58, 1.0)
    s_bsdf.inputs['Roughness'].default_value = 0.45
    human.data.materials.clear()
    human.data.materials.append(skin_mat)

    # 4. Séparation du pantalon en OBJET INDÉPENDANT
    bm_s = bmesh.new()
    bm_s.from_mesh(suit.data)
    bm_s.faces.ensure_lookup_table()
    pants_faces = [f for f in bm_s.faces if f.calc_center_median().z < 0.05]

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

    pants_mesh = bpy.data.meshes.new(f"{theme_slug}_pants_mesh")
    bm_p.to_mesh(pants_mesh)
    bm_p.free()

    pants_obj = bpy.data.objects.new(f"{theme_slug}_pants", pants_mesh)
    bpy.context.collection.objects.link(pants_obj)

    # Supprimer les faces du pantalon du Torso
    bmesh.ops.delete(bm_s, geom=pants_faces, context='FACES')
    bm_s.to_mesh(suit.data)
    bm_s.free()
    suit.name = f"{theme_slug}_torso"

    # 5. Création des Matériaux PBR Thématiques pour chaque pièce indépendante
    parts_meta = [
        ("torso", suit, config.get("torso_scale", 3.0), config.get("torso_roughness", 0.5), config.get("torso_metallic", 0.0), config.get("torso_normal_str", 1.5)),
        ("pants", pants_obj, config.get("pants_scale", 4.0), config.get("pants_roughness", 0.6), config.get("pants_metallic", 0.0), config.get("pants_normal_str", 1.5)),
        ("shoes", shoes, config.get("shoes_scale", 3.0), config.get("shoes_roughness", 0.4), config.get("shoes_metallic", config.get("shoes_metallic", 0.0)), config.get("shoes_normal_str", 1.2))
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

        diff_path = os.path.join(godot_dir, f"{theme_slug}_{part_name}_diffuse.png")
        norm_path = os.path.join(godot_dir, f"{theme_slug}_{part_name}_normal.png")

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

    # 6. Modificateurs Solidify & Subsurf sur chaque vêtement indépendant
    for o in [suit, pants_obj, shoes]:
        sol = o.modifiers.new("Solidify", 'SOLIDIFY')
        sol.thickness = 0.005
        sol.offset = 1.0
        sub = o.modifiers.new("Subsurf", 'SUBSURF')
        sub.levels = 1

    # 7. Cadrage Studio 4 Vues (plein pied complet avec marge)
    views = [
        (f"{theme_slug}_front", (0.0, -4.0, 0.0), (math.radians(90), 0, 0), 45),
        (f"{theme_slug}_three_quarter", (2.8, -3.0, 0.0), (math.radians(90), 0, math.radians(43)), 45),
        (f"{theme_slug}_back", (0.0, 4.0, 0.0), (math.radians(90), 0, math.radians(180)), 45),
        (f"{theme_slug}_profile", (4.0, 0.0, 0.0), (math.radians(90), 0, math.radians(90)), 45),
    ]

    rendered_files = []
    for name, loc, rot, lens in views:
        cam.location = loc
        cam.rotation_euler = rot
        cam.data.lens = lens
        out_file = os.path.join(out_dir, f"{name}.png")
        bpy.context.scene.render.filepath = out_file
        bpy.ops.render.render(write_still=True)
        rendered_files.append(out_file)
        print(f"[{theme_slug}] Rendered: {name}")

    blend_file = os.path.join(out_dir, f"{theme_slug}_personnage_habille.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_file)
    print(f"Saved independent scene: {blend_file}")
    return rendered_files
