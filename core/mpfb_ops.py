#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module d'automatisation MPFB2 / MakeHuman pour Blender 5.2.
Permet d'extraire des géométries quads parfaites pour différentes pièces de vêtements
(Torso/Haut, Pantalon/Bas, Chaussures/Bottes), de compiler les fichiers .mhclo, .obj,
.mhmat, .thumb, et de créer une scène complète de personnage habillé (.blend + .png).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from PIL import Image

from core.blender_ops import trouver_blender
from core.config import DEFAULT_MPFB_DATA_DIR

DEFAULT_MPFB_CLOTHES_DIR = os.path.join(DEFAULT_MPFB_DATA_DIR, "clothes")


DEFAULT_MPFB_PACKS_DIR = os.path.join(DEFAULT_MPFB_DATA_DIR, "packs")


def enregistrer_asset_dans_pack_mpfb(
    asset_name: str,
    part_type: str,
    author: str = "Generator Assets AI",
    description: str = "",
    pack_name: str = "generator_assets"
) -> bool:
    """
    Enregistre automatiquement un vêtement dans le catalogue de pack JSON MPFB (packs/generator_assets.json).
    Permet l'affichage immédiat avec vignette dans l'interface Blender MPFB > Apply assets > Clothes library.
    """
    try:
        os.makedirs(DEFAULT_MPFB_PACKS_DIR, exist_ok=True)
        pack_file = os.path.join(DEFAULT_MPFB_PACKS_DIR, f"{pack_name}.json")
        pack_data = {}
        if os.path.exists(pack_file):
            try:
                with open(pack_file, "r", encoding="utf-8") as f:
                    pack_data = json.load(f)
            except Exception:
                pack_data = {}

        desc = description or f"Vêtement {asset_name} ({part_type}) généré par IA pour MakeHuman & MPFB"
        pack_data[asset_name] = {
            "author": author,
            "category": "Clothes",
            "changed": "2026-08-27",
            "created": "2026-08-27",
            "description": desc,
            "license": "CC0",
            "original_author": "Generator Assets",
            "original_source": "http://www.makehumancommunity.org",
            "source": "Generator-Assets",
            "thumbnail": f"{asset_name}.thumb",
            "type": "clothes"
        }

        with open(pack_file, "w", encoding="utf-8") as f:
            json.dump(pack_data, f, indent=4)
        return True
    except Exception as e:
        print(f"Avertissement : Impossible d'enregistrer l'asset {asset_name} dans le pack MPFB : {e}")
        return False


def verifier_mpfb_disponible() -> bool:
    """Vérifie si Blender et l'extension MPFB sont accessibles."""
    blender_bin = trouver_blender()
    if not blender_bin:
        return False
    return os.path.exists(DEFAULT_MPFB_DATA_DIR)


def generer_script_blender_makeclothes(
    asset_name: str,
    part_type: str,
    output_folder: str,
    diffuse_path: str,
    normal_path: Optional[str] = None,
    ao_path: Optional[str] = None,
    thickness: float = 0.007,
    author: str = "AI-Generator"
) -> str:
    """Génère le code Python interne exécuté par Blender en mode headless pour compiler un vêtement."""
    output_folder_esc = os.path.abspath(output_folder).replace("\\", "/")
    diffuse_esc = os.path.abspath(diffuse_path).replace("\\", "/") if diffuse_path else ""
    normal_esc = os.path.abspath(normal_path).replace("\\", "/") if normal_path else ""
    ao_esc = os.path.abspath(ao_path).replace("\\", "/") if ao_path else ""

    code = f"""
import bpy
import bmesh
import os
import shutil

try:
    from bl_ext.user_default.mpfb.services import HumanService, ObjectService, ClothesService
except ImportError:
    from mpfb.services import HumanService, ObjectService, ClothesService

asset_name = "{asset_name}"
part_type = "{part_type.lower()}"
output_folder = r"{output_folder_esc}"
os.makedirs(output_folder, exist_ok=True)

# 1. Création du corps humain neutre de référence
human = HumanService.create_human(mask_helpers=False, detailed_helpers=True)

bm = bmesh.new()
bm.from_mesh(human.data)
bm.verts.ensure_lookup_table()
bm.faces.ensure_lookup_table()
uv_human = bm.loops.layers.uv.verify()

selected_faces = []
selected_vert_indices = set()

# Définition des critères de sélection basés sur les helpers officiels MakeHuman
for f in bm.faces:
    cz = f.calc_center_median().z
    cx = abs(f.calc_center_median().x)

    if part_type in ["torso", "top", "tshirt", "jacket", "veste", "tunique", "haut"]:
        # Haut du corps (0.80 <= Z <= 1.38, manches s'arrêtant aux poignets cx <= 0.40) + bas évasé helper-skirt (18002..18721)
        is_upper = all(v.index < 13380 for v in f.verts) and (0.80 <= cz <= 1.38) and (cx <= 0.40)
        is_skirt = all(18002 <= v.index <= 18721 for v in f.verts) and (cz >= 0.70)
        if is_upper or is_skirt:
            selected_faces.append(f)
            for v in f.verts:
                selected_vert_indices.add(v.index)

    elif part_type in ["pants", "bottom", "pantalon", "trousers", "legs", "bas"]:
        # Pantalon officiel MakeHuman (helper-tights : 15328..18001)
        if all(15328 <= v.index <= 18001 for v in f.verts):
            selected_faces.append(f)
            for v in f.verts:
                selected_vert_indices.add(v.index)

    elif part_type in ["shoes", "boots", "chaussures", "bottes", "feet"]:
        # Chaussures / Bottes complètes (pieds et chevilles sous Z=0.22)
        if all(v.index < 13380 for v in f.verts) and cz <= 0.22:
            selected_faces.append(f)
            for v in f.verts:
                selected_vert_indices.add(v.index)

# 2. Construction du maillage de vêtement avec coordonnées UV exactes (100% quads)
cloth_mesh = bpy.data.meshes.new(f"{{asset_name}}_mesh")
cloth_bm = bmesh.new()
uv_cloth = cloth_bm.loops.layers.uv.new("UVMap")

v_map = {{}}
thickness_offset = {thickness}
for v_idx in selected_vert_indices:
    orig_v = bm.verts[v_idx]
    offset_co = orig_v.co + orig_v.normal * thickness_offset
    new_v = cloth_bm.verts.new(offset_co)
    v_map[v_idx] = new_v

cloth_bm.verts.ensure_lookup_table()

for f in selected_faces:
    face_verts = [v_map[v.index] for v in f.verts]
    try:
        new_f = cloth_bm.faces.new(face_verts)
        for i, loop in enumerate(new_f.loops):
            loop[uv_cloth].uv = f.loops[i][uv_human].uv
    except ValueError:
        pass

cloth_bm.to_mesh(cloth_mesh)
cloth_bm.free()
bm.free()

cloth_obj = bpy.data.objects.new(asset_name, cloth_mesh)
bpy.context.collection.objects.link(cloth_obj)

# 3. Assignation du groupe 'body' sur le vêtement pour validation MPFB stricte
body_vg = cloth_obj.vertex_groups.new(name="body")
body_vg.add(list(range(len(cloth_obj.data.vertices))), 1.0, "REPLACE")

# 4. Calcul morphologique MHCLO via MPFB sans masquer le corps
props = {{"name": asset_name, "author": "{author}", "category": "clothes"}}
mhclo = ClothesService.create_mhclo_from_clothes_matching(
    human,
    cloth_obj,
    properties_dict=props,
    delete_group=None
)

mhclo_path = os.path.join(output_folder, f"{{asset_name}}.mhclo")
ref_scale = ClothesService.get_reference_scale(human)
mhclo.write_mhclo(mhclo_path, reference_scale=ref_scale, also_export_obj=True, also_export_mhmat=True)

# 6. Copie des textures et création du .mhmat
diffuse_name = ""
normal_name = ""
ao_name = ""

if r"{diffuse_esc}" and os.path.exists(r"{diffuse_esc}"):
    diffuse_name = f"{{asset_name}}_diffuse.png"
    shutil.copyfile(r"{diffuse_esc}", os.path.join(output_folder, diffuse_name))

if r"{normal_esc}" and os.path.exists(r"{normal_esc}"):
    normal_name = f"{{asset_name}}_normal.png"
    shutil.copyfile(r"{normal_esc}", os.path.join(output_folder, normal_name))

if r"{ao_esc}" and os.path.exists(r"{ao_esc}"):
    ao_name = f"{{asset_name}}_ao.png"
    shutil.copyfile(r"{ao_esc}", os.path.join(output_folder, ao_name))

mhmat_lines = [
    "# Material MakeHuman / MPFB",
    f"name {{asset_name}}",
    "tag MakeHuman(TM)",
    "ambientColor 1.0 1.0 1.0",
    "diffuseColor 1.0 1.0 1.0",
    "specularColor 0.05 0.05 0.05",
    "shininess 0.2",
    "opacity 1.0",
    "transparent False",
    "castShadows True",
    "receiveShadows True",
]

if diffuse_name:
    mhmat_lines.append(f"diffuseTexture {{diffuse_name}}")
if normal_name:
    mhmat_lines.append(f"normalmapTexture {{normal_name}}")
    mhmat_lines.append("normalmapIntensity 1.0")
if ao_name:
    mhmat_lines.append(f"aomapTexture {{ao_name}}")
    mhmat_lines.append("aomapIntensity 1.0")

mhmat_lines.extend([
    "shader data/shaders/glsl/litsphere",
    "shaderConfig ambientOcclusion True",
    "shaderConfig normal True" if normal_name else "shaderConfig normal False",
    "shaderConfig bump False",
    "shaderConfig spec True",
    "shaderConfig diffuse True"
])

mhmat_path = os.path.join(output_folder, f"{{asset_name}}.mhmat")
with open(mhmat_path, "w", encoding="utf-8") as f_mhmat:
    f_mhmat.write("\\n".join(mhmat_lines) + "\\n")

print(f"SUCCESS: {{asset_name}} exported to {{output_folder}}")
"""
    return code


def compiler_vetement_mpfb(
    asset_name: str,
    part_type: str,
    output_folder: str,
    diffuse_path: str,
    normal_path: Optional[str] = None,
    ao_path: Optional[str] = None,
    thickness: float = 0.007,
    author: str = "AI-Generator"
) -> bool:
    """Exécute la compilation MakeClothes dans Blender headless."""
    blender_bin = trouver_blender()
    if not blender_bin:
        raise EnvironmentError("Blender 5.x n'est pas détecté.")

    script_content = generer_script_blender_makeclothes(
        asset_name=asset_name,
        part_type=part_type,
        output_folder=output_folder,
        diffuse_path=diffuse_path,
        normal_path=normal_path,
        ao_path=ao_path,
        thickness=thickness,
        author=author
    )

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as temp_f:
        temp_f.write(script_content)
        temp_script_path = temp_f.name

    try:
        cmd = [blender_bin, "--background", "--python", temp_script_path]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        if "SUCCESS:" in res.stdout:
            # Génération de la vignette .thumb (128x128) via Pillow côté hôte Python
            thumb_path = os.path.join(output_folder, f"{asset_name}.thumb")
            if diffuse_path and os.path.exists(diffuse_path):
                im = Image.open(diffuse_path).convert("RGB")
                im_thumb = im.resize((128, 128), Image.Resampling.LANCZOS)
                im_thumb.save(thumb_path, format="PNG")

            # Synchronisation dans les deux répertoires MPFB (data/data/clothes et data/clothes)
            alt_root = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\data\clothes"
            if os.path.exists(os.path.dirname(alt_root)) and output_folder != os.path.join(alt_root, asset_name):
                alt_dest = os.path.join(alt_root, asset_name)
                os.makedirs(alt_dest, exist_ok=True)
                for f in os.listdir(output_folder):
                    shutil.copy2(os.path.join(output_folder, f), os.path.join(alt_dest, f))

            # Enregistrement automatique dans le catalogue de pack MPFB
            enregistrer_asset_dans_pack_mpfb(asset_name, part_type, author=author)

            return True
        else:
            print(f"Erreur compilation MakeClothes : {res.stderr or res.stdout}")
            return False
    finally:
        if os.path.exists(temp_script_path):
            try:
                os.remove(temp_script_path)
            except Exception:
                pass


def creer_scene_personnage_habille(
    character_name: str,
    mhclo_files: List[str],
    output_blend_path: str,
    render_image_path: Optional[str] = None
) -> bool:
    """
    Crée une scène Blender (.blend) contenant un 'New Human' MPFB habillé de toutes les pièces générées,
    avec éclairage studio et caméra, et effectue un rendu de prévisualisation .PNG.
    """
    blender_bin = trouver_blender()
    if not blender_bin:
        raise EnvironmentError("Blender 5.x n'est pas détecté.")

    output_blend_esc = os.path.abspath(output_blend_path).replace("\\", "/")
    render_png_esc = os.path.abspath(render_image_path).replace("\\", "/") if render_image_path else ""

    mhclo_paths_json = json.dumps([os.path.abspath(p).replace("\\", "/") for p in mhclo_files])

    script = f"""
import bpy
import os
import json
from mathutils import Vector, Euler

try:
    from bl_ext.user_default.mpfb.services import HumanService, ObjectService, ClothesService, MaterialService
except ImportError:
    from mpfb.services import HumanService, ObjectService, ClothesService, MaterialService

bpy.ops.wm.read_factory_settings(use_empty=True)

# 1. Créer un New Human dans MPFB
human = HumanService.create_human(mask_helpers=True, detailed_helpers=False, feet_on_ground=True)

# 2. Charger et équiper chaque vêtement .mhclo
mhclo_list = {mhclo_paths_json}
equipped_objects = []

for mhclo_path in mhclo_list:
    if os.path.exists(mhclo_path):
        try:
            cl_obj = HumanService.add_mhclo_asset(mhclo_path, human, asset_type="Clothes", material_type="MAKESKIN")
            equipped_objects.append(cl_obj)
            print(f"EQUIPPED_SUCCESS: {{mhclo_path}} -> {{cl_obj.name}}")
            
            # 1. Épaisseur et volume 3D extérieur
            sol = cl_obj.modifiers.new("Solidify", 'SOLIDIFY')
            sol.offset = 1.0
            if "torso" in cl_obj.name:
                sol.thickness = 0.014
            elif "pants" in cl_obj.name:
                sol.thickness = 0.012
            else:
                sol.thickness = 0.016

            # 2. Assignation du Matériau PBR complet
            folder = os.path.dirname(mhclo_path)
            bn = os.path.basename(mhclo_path).replace(".mhclo", "")
            diffuse_p = os.path.join(folder, f"{{bn}}_diffuse.png")
            normal_p = os.path.join(folder, f"{{bn}}_normal.png")
            
            mat = bpy.data.materials.new(name=f"{{bn}}_PBR")
            mat.use_nodes = True
            nodes = mat.node_tree.nodes
            links = mat.node_tree.links
            bsdf = nodes.get("Principled BSDF")
            
            tex_coord = nodes.new('ShaderNodeTexCoord')
            mapping = nodes.new('ShaderNodeMapping')
            mapping.inputs['Scale'].default_value = (2.5, 2.5, 2.5)
            links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])
            
            if os.path.exists(diffuse_p):
                img_d = bpy.data.images.load(diffuse_p)
                t_node = nodes.new('ShaderNodeTexImage')
                t_node.image = img_d
                links.new(mapping.outputs['Vector'], t_node.inputs['Vector'])
                links.new(t_node.outputs['Color'], bsdf.inputs['Base Color'])
                
            if os.path.exists(normal_p):
                img_n = bpy.data.images.load(normal_p)
                img_n.colorspace_settings.name = 'Non-Color'
                n_tex = nodes.new('ShaderNodeTexImage')
                n_tex.image = img_n
                links.new(mapping.outputs['Vector'], n_tex.inputs['Vector'])
                
                n_node = nodes.new('ShaderNodeNormalMap')
                n_node.inputs['Strength'].default_value = 1.0
                links.new(n_tex.outputs['Color'], n_node.inputs['Color'])
                links.new(n_node.outputs['Normal'], bsdf.inputs['Normal'])
                
            bsdf.inputs['Roughness'].default_value = 0.55
            if cl_obj.data.materials:
                cl_obj.data.materials[0] = mat
            else:
                cl_obj.data.materials.append(mat)

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error equipping {{mhclo_path}}: {{e}}")

# Configuration peau humaine naturelle
skin_mat = bpy.data.materials.new(name="Human_Skin_Pro")
skin_mat.use_nodes = True
s_bsdf = skin_mat.node_tree.nodes.get("Principled BSDF")
s_bsdf.inputs['Base Color'].default_value = (0.82, 0.64, 0.52, 1.0)
s_bsdf.inputs['Roughness'].default_value = 0.45
if human.data.materials:
    human.data.materials[0] = skin_mat
else:
    human.data.materials.append(skin_mat)

# Nettoyer d'éventuels masques pour garantir que le corps reste 100% complet
for m in list(human.modifiers):
    if m.type == 'MASK' or "Delete" in m.name or "Mask" in m.name:
        human.modifiers.remove(m)

# 3. Setup de l'éclairage studio 3 points
key_light_data = bpy.data.lights.new(name="Key_Light", type='AREA')
key_light_data.energy = 250.0
key_light_data.size = 1.5
key_light = bpy.data.objects.new(name="Key_Light", object_data=key_light_data)
key_light.location = (1.5, -2.0, 2.2)
key_light.rotation_euler = Euler((1.1, 0.2, 0.6), 'XYZ')
bpy.context.collection.objects.link(key_light)

fill_light_data = bpy.data.lights.new(name="Fill_Light", type='AREA')
fill_light_data.energy = 90.0
fill_light_data.size = 2.0
fill_light = bpy.data.objects.new(name="Fill_Light", object_data=fill_light_data)
fill_light.location = (-2.0, -1.5, 1.6)
fill_light.rotation_euler = Euler((1.2, -0.3, -0.8), 'XYZ')
bpy.context.collection.objects.link(fill_light)

rim_light_data = bpy.data.lights.new(name="Rim_Light", type='SUN')
rim_light_data.energy = 3.0
rim_light = bpy.data.objects.new(name="Rim_Light", object_data=rim_light_data)
rim_light.location = (0.0, 2.5, 2.8)
rim_light.rotation_euler = Euler((-0.9, 0.0, 0.0), 'XYZ')
bpy.context.collection.objects.link(rim_light)

# 4. Setup Caméra (Plein pied centré)
cam_data = bpy.data.cameras.new(name="Camera")
cam_data.lens = 55
cam_obj = bpy.data.objects.new(name="Camera", object_data=cam_data)
cam_obj.location = (0.0, -3.2, 0.95)
cam_obj.rotation_euler = Euler((1.5708, 0.0, 0.0), 'XYZ')
bpy.context.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj

bpy.context.scene.render.resolution_x = 1024
bpy.context.scene.render.resolution_y = 1024
bpy.context.scene.render.film_transparent = True

os.makedirs(os.path.dirname(r"{output_blend_esc}"), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=r"{output_blend_esc}")
print("BLEND_SAVED_SUCCESS")

if r"{render_png_esc}":
    os.makedirs(os.path.dirname(r"{render_png_esc}"), exist_ok=True)
    bpy.context.scene.render.filepath = r"{render_png_esc}"
    bpy.ops.render.render(write_still=True)
    print("RENDER_PNG_SUCCESS")
"""

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as temp_f:
        temp_f.write(script)
        temp_script_path = temp_f.name

    try:
        cmd = [blender_bin, "--background", "--python", temp_script_path]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if "BLEND_SAVED_SUCCESS" in res.stdout:
            return True
        else:
            print(f"Erreur création personnage habillé : {res.stderr or res.stdout}")
            return False
    finally:
        if os.path.exists(temp_script_path):
            try:
                os.remove(temp_script_path)
            except Exception:
                pass
