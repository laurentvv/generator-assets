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
import cv2
import numpy as np
from PIL import Image, ImageFilter, ImageDraw

from core.blender_ops import trouver_blender
from core.config import (
    DEFAULT_MPFB_DATA_DIR,
    DEFAULT_MPFB_INK_DIR,
    DEFAULT_MPFB_EYES_DIR,
    resoudre_yunet_model,
)

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
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        stdout_txt = res.stdout or ""
        if "BLEND_SAVED_SUCCESS" in stdout_txt:
            return True
        else:
            print(f"Erreur création personnage habillé : {res.stderr or stdout_txt}")
            return False
    finally:
        if os.path.exists(temp_script_path):
            try:
                os.remove(temp_script_path)
            except Exception:
                pass


# ==============================================================================
# Pipeline MakeUp & Ink Layer MPFB2 (MakeHuman hm08)
# ==============================================================================

# Coordonnées UV hm08 vérifiées (MakeHuman - visage sur l'îlot droit X:1450..2000, Y:800..1300)
HM08_Y_SYM = 1058  # Axe de symétrie vertical du visage en pixels (sur 2048x2048)


def detecter_reperes_visage(img_bgr: np.ndarray, yunet_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Détecte les repères faciaux avec YuNet ONNX (yeux, nez, coins de bouche, score).
    """
    modele_path = yunet_path or resoudre_yunet_model()
    if not os.path.exists(modele_path):
        raise FileNotFoundError(f"Modèle YuNet introuvable : {modele_path}")

    h, w = img_bgr.shape[:2]
    det = cv2.FaceDetectorYN.create(modele_path, "", (w, h), score_threshold=0.6)
    _, faces = det.detect(img_bgr)
    if faces is None or len(faces) == 0:
        raise RuntimeError("YuNet : aucun visage détecté dans l'image de portrait fournie.")

    f = faces[0]
    re = (float(f[4]), float(f[5]))
    le = (float(f[6]), float(f[7]))
    ipd = float(np.hypot(le[0] - re[0], le[1] - re[1]))

    return {
        "score": float(f[14]),
        "bbox": (float(f[0]), float(f[1]), float(f[2]), float(f[3])),
        "re": re,
        "le": le,
        "nose": (float(f[8]), float(f[9])),
        "rmouth": (float(f[10]), float(f[11])),
        "lmouth": (float(f[12]), float(f[13])),
        "ipd": ipd
    }


def echantillonner_zone(arr: np.ndarray, cx: float, cy: float, rx: float, ry: float):
    """Échantillonne une zone elliptique et renvoie la moyenne BGR et Lab."""
    h, w = arr.shape[:2]
    x0, x1 = max(0, int(cx - rx)), min(w, int(cx + rx))
    y0, y1 = max(0, int(cy - ry)), min(h, int(cy + ry))
    if x1 <= x0 or y1 <= y0:
        return np.array([128.0, 128.0, 128.0]), np.array([50.0, 0.0, 0.0])
    roi = arr[y0:y1, x0:x1].astype(np.float32)
    lab = cv2.cvtColor(arr[y0:y1, x0:x1], cv2.COLOR_BGR2Lab).astype(np.float32)
    return roi.mean(axis=(0, 1)), lab.mean(axis=(0, 1))


def analyser_metriques_portrait(portrait_path: str, yunet_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Extrait les caractéristiques colorimétriques du visage depuis un portrait 2D.
    Mesure le contraste sous les yeux (cernes/fatigue), les tempes, les joues et les lèvres.
    """
    if not os.path.exists(portrait_path):
        raise FileNotFoundError(f"Image de portrait introuvable : {portrait_path}")

    portrait = cv2.imread(portrait_path)
    if portrait is None:
        raise ValueError(f"Impossible de charger l'image : {portrait_path}")

    rep = detecter_reperes_visage(portrait, yunet_path=yunet_path)
    re, le = rep["re"], rep["le"]
    ipd = rep["ipd"]

    # Échantillonnage joues (référence de peau)
    joue_vl, l_jvl = echantillonner_zone(portrait, re[0] - 0.25 * ipd, re[1] + 0.65 * ipd, 0.15 * ipd, 0.15 * ipd)
    joue_vr, l_jvr = echantillonner_zone(portrait, le[0] + 0.25 * ipd, le[1] + 0.65 * ipd, 0.15 * ipd, 0.15 * ipd)
    joue_bgr = (joue_vl + joue_vr) / 2.0
    l_joue = (l_jvl[0] + l_jvr[0]) / 2.0

    # Échantillonnage cernes (creux sous les yeux)
    cerne_vl, l_cvl = echantillonner_zone(portrait, re[0], re[1] + 0.22 * ipd, 0.18 * ipd, 0.09 * ipd)
    cerne_vr, l_cvr = echantillonner_zone(portrait, le[0], le[1] + 0.22 * ipd, 0.18 * ipd, 0.09 * ipd)
    cerne_bgr = (cerne_vl + cerne_vr) / 2.0
    l_cerne = (l_cvl[0] + l_cvr[0]) / 2.0

    # Échantillonnage tempes
    temple_vl, _ = echantillonner_zone(portrait, re[0] - 0.55 * ipd, re[1] - 0.05 * ipd, 0.12 * ipd, 0.15 * ipd)
    temple_vr, _ = echantillonner_zone(portrait, le[0] + 0.55 * ipd, le[1] - 0.05 * ipd, 0.12 * ipd, 0.15 * ipd)
    temple_bgr = (temple_vl + temple_vr) / 2.0

    # Échantillonnage lèvres
    mouth_cx = (rep["rmouth"][0] + rep["lmouth"][0]) / 2.0
    mouth_cy = (rep["rmouth"][1] + rep["lmouth"][1]) / 2.0
    lips_bgr, _ = echantillonner_zone(portrait, mouth_cx, mouth_cy, 0.16 * ipd, 0.07 * ipd)

    delta_cerne = float(l_joue - l_cerne)
    ratio_cerne = cerne_bgr / np.maximum(joue_bgr, 1.0)
    ratio_temple = temple_bgr / np.maximum(joue_bgr, 1.0)
    ratio_lips = lips_bgr / np.maximum(joue_bgr, 1.0)

    return {
        "yunet": rep,
        "delta_cerne_l": delta_cerne,
        "joue_bgr": joue_bgr.tolist(),
        "cerne_bgr": cerne_bgr.tolist(),
        "temple_bgr": temple_bgr.tolist(),
        "lips_bgr": lips_bgr.tolist(),
        "ratio_cerne": ratio_cerne.tolist(),
        "ratio_temple": ratio_temple.tolist(),
        "ratio_lips": ratio_lips.tolist()
    }


def calculer_gamut_peau_3d(diffuse_skin_path: Optional[str], metriques: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transfère les ratios relatifs du portrait vers le gamut de texture 3D cible,
    en compensant la diffusion sous-surfacique (Subsurface Scattering / SSS) de Blender Cycles.
    """
    if diffuse_skin_path and os.path.exists(diffuse_skin_path):
        skin = cv2.imread(diffuse_skin_path)
        if skin is not None:
            # Échantillonne la joue sur la texture MakeHuman hm08
            joue_3d = skin[910:970, 1840:1900].astype(np.float32).mean(axis=(0, 1))
        else:
            joue_3d = np.array([150.0, 160.0, 175.0], dtype=np.float32)
    else:
        # Valeur par défaut teint Vent-Gris froid
        joue_3d = np.array([150.0, 160.0, 175.0], dtype=np.float32)

    ratio_cerne = np.array(metriques["ratio_cerne"], dtype=np.float32)
    ratio_temple = np.array(metriques["ratio_temple"], dtype=np.float32)
    ratio_lips = np.array(metriques["ratio_lips"], dtype=np.float32)

    # Cernes : ombre creuse froide assombrie (facteur 0.82) pour résister à la diffusion SSS
    c_arr = np.clip(joue_3d * ratio_cerne * 0.82, 0, 255)
    cernes_bgr = tuple(float(x) for x in c_arr)

    # Cœur du cerne : nuance violacée/anthracite subtile
    cernes_core_bgr = tuple(float(x) for x in np.clip(c_arr * np.array([1.02, 0.92, 1.02]), 0, 255))

    # Temples creuses
    temple_bgr = tuple(float(x) for x in np.clip(joue_3d * ratio_temple * 0.88, 0, 255))

    # Flush de fatigue / pommettes
    blush_bgr = tuple(float(x) for x in np.clip(joue_3d * np.array([0.88, 0.90, 1.08]), 0, 255))

    # Creux paupière supérieure
    crease_bgr = tuple(float(x) for x in np.clip(c_arr * 0.92, 0, 255))

    # Teinte lèvres naturelle
    lips_bgr = tuple(float(x) for x in np.clip(joue_3d * ratio_lips * 1.05, 0, 255))

    return {
        "joue_3d": tuple(float(x) for x in joue_3d),
        "cernes": cernes_bgr,
        "cernes_core": cernes_core_bgr,
        "temples": temple_bgr,
        "blush": blush_bgr,
        "crease": crease_bgr,
        "lips": lips_bgr
    }


def _dessiner_formes_adoucie(shapes: List[Any], blur_radius: int, canvas_size=(2048, 2048)) -> Image.Image:
    """Peint des formes vectorielles et applique un flou gaussien progressif."""
    coul = Image.new("RGB", canvas_size, (0, 0, 0))
    alpha = Image.new("L", canvas_size, 0)
    dc = ImageDraw.Draw(coul)
    da = ImageDraw.Draw(alpha)

    for item in shapes:
        stype = item[0]
        if stype == "ellipse":
            _, coords, rgb, a = item
            r, g, b = int(rgb[2]), int(rgb[1]), int(rgb[0])
            a_int = int(a * 255)
            dc.ellipse(coords, fill=(r, g, b))
            da.ellipse(coords, fill=a_int)
        elif stype == "line":
            _, xy, width, rgb, a = item
            r, g, b = int(rgb[2]), int(rgb[1]), int(rgb[0])
            a_int = int(a * 255)
            dc.line(xy, fill=(r, g, b), width=width)
            da.line(xy, fill=a_int, width=width)
        elif stype == "polygon":
            _, pts, rgb, a = item
            r, g, b = int(rgb[2]), int(rgb[1]), int(rgb[0])
            a_int = int(a * 255)
            dc.polygon(pts, fill=(r, g, b))
            da.polygon(pts, fill=a_int)

    if blur_radius > 0:
        alpha = alpha.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        coul = coul.filter(ImageFilter.GaussianBlur(radius=max(1, blur_radius // 2)))

    res = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    res.paste(coul, (0, 0))
    res.putalpha(alpha)
    return res


def dessiner_calque_encre_hm08(couleurs_3d: Dict[str, Any], canvas_size=(2048, 2048)) -> Image.Image:
    """
    Génère l'ink layer RGBA multi-calques anatomique sur la carte UV standard MakeHuman hm08.
    Comporte 5 calques étagés :
      1. Pénombre diffuse (orbite, tempes, joues, nez)
      2. Croissant orbitaire intermédiaire
      3. Sillon profond de fatigue (vallée des larmes & centre orbitaire)
      4. Creux palpébral supérieur
      5. Teinte douce des lèvres
    """
    cernes_bgr = couleurs_3d["cernes"]
    cernes_core_bgr = couleurs_3d["cernes_core"]
    temple_bgr = couleurs_3d["temples"]
    blush_bgr = couleurs_3d["blush"]
    crease_bgr = couleurs_3d["crease"]
    lips_bgr = couleurs_3d["lips"]

    # Trajectoire du creux sous-orbitaire (œil gauche et œil droit en miroir de Y_SYM=1058)
    pts_mid_L = [(1728, 1012), (1742, 1002), (1752, 985), (1748, 965), (1736, 950)]
    pts_mid_R = [(1728, 1104), (1742, 1114), (1752, 1131), (1748, 1151), (1736, 1166)]

    # Calque 1 : Pénombre diffuse
    wide_shapes = []
    for pts in [pts_mid_L, pts_mid_R]:
        for (x, y) in pts:
            wide_shapes.append(("ellipse", [x - 26, y - 25, x + 26, y + 25], cernes_bgr, 0.52))
    # Temples creuses
    wide_shapes.append(("ellipse", [1680 - 45, 860 - 35, 1680 + 45, 860 + 35], temple_bgr, 0.48))
    wide_shapes.append(("ellipse", [1680 - 45, 1256 - 35, 1680 + 45, 1256 + 35], temple_bgr, 0.48))
    # Pommettes / flush de fatigue
    wide_shapes.append(("ellipse", [1865 - 35, 940 - 28, 1865 + 35, 940 + 28], blush_bgr, 0.32))
    wide_shapes.append(("ellipse", [1865 - 35, 1176 - 28, 1865 + 35, 1176 + 28], blush_bgr, 0.32))
    # Arête du nez
    wide_shapes.append(("ellipse", [1745 - 20, 1058 - 14, 1745 + 20, 1058 + 14], temple_bgr, 0.28))
    layer_wide = _dessiner_formes_adoucie(wide_shapes, blur_radius=14, canvas_size=canvas_size)

    # Calque 2 : Croissant orbitaire intermédiaire
    med_shapes = []
    for pts in [pts_mid_L, pts_mid_R]:
        for i in range(len(pts) - 1):
            med_shapes.append(("line", [pts[i], pts[i+1]], 30, cernes_bgr, 0.68))
        for (x, y) in pts:
            med_shapes.append(("ellipse", [x - 17, y - 18, x + 17, y + 18], cernes_bgr, 0.70))
    layer_med = _dessiner_formes_adoucie(med_shapes, blur_radius=8, canvas_size=canvas_size)

    # Calque 3 : Sillon profond de fatigue
    core_shapes = []
    for pts in [pts_mid_L[:3], pts_mid_R[:3]]:
        for i in range(len(pts) - 1):
            core_shapes.append(("line", [pts[i], pts[i+1]], 16, cernes_core_bgr, 0.82))
    core_shapes.append(("ellipse", [1746 - 12, 988 - 16, 1746 + 12, 988 + 16], cernes_core_bgr, 0.85))
    core_shapes.append(("ellipse", [1746 - 12, 1128 - 16, 1746 + 12, 1128 + 16], cernes_core_bgr, 0.85))
    layer_core = _dessiner_formes_adoucie(core_shapes, blur_radius=5, canvas_size=canvas_size)

    # Calque 4 : Creux palpébral supérieur
    crease_shapes = []
    pts_crease_L = [(1705, 1005), (1702, 985), (1708, 965)]
    pts_crease_R = [(1705, 1111), (1702, 1131), (1708, 1151)]
    for i in range(2):
        crease_shapes.append(("line", [pts_crease_L[i], pts_crease_L[i+1]], 12, crease_bgr, 0.50))
        crease_shapes.append(("line", [pts_crease_R[i], pts_crease_R[i+1]], 12, crease_bgr, 0.50))
    layer_crease = _dessiner_formes_adoucie(crease_shapes, blur_radius=5, canvas_size=canvas_size)

    # Calque 5 : Teinte douce des lèvres
    lip_shapes = [
        ("ellipse", [1938 - 12, 1058 - 36, 1938 + 12, 1058 + 36], lips_bgr, 0.40)
    ]
    layer_lips = _dessiner_formes_adoucie(lip_shapes, blur_radius=6, canvas_size=canvas_size)

    # Composition alpha ordonnée
    final_ink = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    final_ink = Image.alpha_composite(final_ink, layer_wide)
    final_ink = Image.alpha_composite(final_ink, layer_med)
    final_ink = Image.alpha_composite(final_ink, layer_core)
    final_ink = Image.alpha_composite(final_ink, layer_crease)
    final_ink = Image.alpha_composite(final_ink, layer_lips)

    return final_ink


def creer_manifest_ink(nom_couche: str, nom_image: str, focus: str = "", extraction_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Génère la structure du manifeste officiel MPFB pour les calques d'encre (MakeUp)."""
    manifest = {
        "name": nom_couche,
        "focus": focus,
        "image_name": nom_image
    }
    if extraction_info:
        manifest["extraction"] = extraction_info
    return manifest


def personnaliser_yeux_mpfb(
    couleur: str = "cyan",
    src_eye_path: Optional[str] = None,
    dst_paths: Optional[List[str]] = None
) -> Optional[str]:
    """
    Personnalise la texture d'iris des yeux MPFB (ex: teinte cyan avec lueur interne).
    """
    src = src_eye_path or os.path.join(DEFAULT_MPFB_EYES_DIR, "lightblue_eye.png")
    if not os.path.exists(src):
        return None

    eye_img = cv2.imread(src, cv2.IMREAD_UNCHANGED)
    if eye_img is None:
        return None

    eye_hsv = cv2.cvtColor(eye_img[:, :, :3], cv2.COLOR_BGR2HSV).astype(np.float32)
    blue_mask = (eye_hsv[:, :, 1] > 40) & (eye_hsv[:, :, 0] >= 90) & (eye_hsv[:, :, 0] <= 135)

    if couleur.lower() == "cyan":
        eye_hsv[blue_mask, 0] = np.clip(eye_hsv[blue_mask, 0] - 16.0, 78, 105)
        eye_hsv[blue_mask, 2] = np.clip(eye_hsv[blue_mask, 2] * 1.15, 0, 255)
        eye_hsv[blue_mask, 1] = np.clip(eye_hsv[blue_mask, 1] * 1.05, 0, 255)
    elif couleur.lower() == "amber":
        eye_hsv[blue_mask, 0] = 20.0
        eye_hsv[blue_mask, 2] = np.clip(eye_hsv[blue_mask, 2] * 1.10, 0, 255)

    cyan_bgr = cv2.cvtColor(eye_hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    if eye_img.shape[2] == 4:
        out_img = np.dstack([cyan_bgr, eye_img[:, :, 3]])
    else:
        out_img = cyan_bgr

    cibles = dst_paths or [os.path.join(DEFAULT_MPFB_EYES_DIR, f"eye_{couleur}.png")]
    for p in cibles:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        cv2.imwrite(p, out_img)

    return cibles[0]


def rendre_personnage_blender(
    blend_path: str,
    output_prefix: str,
    modes: List[str] = None,
    samples: int = 48
) -> Dict[str, Any]:
    """
    Effectue les rendus de contrôle studio Cycles (tête et/ou corps complet)
    depuis un fichier .blend MPFB2 via Blender headless.
    Applique automatiquement les correctifs de production :
      - Désactivation des modificateurs de masque 'delete' sur les rendus tête sans vêtements
      - Contraintes TRACK_TO sur lumières Area Key/Fill/Rim
      - Calcul automatique du recul caméra portrait pour cadrage plein pied parfait
    """
    blender_bin = trouver_blender()
    if not blender_bin:
        raise RuntimeError("Exécutable Blender introuvable pour le rendu.")

    if not os.path.exists(blend_path):
        raise FileNotFoundError(f"Fichier Blender introuvable : {blend_path}")

    modes = modes or ["head", "body"]
    render_head = "head" in modes
    render_body = "body" in modes

    blend_path_esc = os.path.abspath(blend_path).replace("\\", "/")
    output_prefix_esc = os.path.abspath(output_prefix).replace("\\", "/")
    os.makedirs(os.path.dirname(output_prefix), exist_ok=True)

    script = f"""
import bpy
import mathutils
import math
import os
import json

BLEND = r"{blend_path_esc}"
OUT = r"{output_prefix_esc}"
SAMPLES = {samples}
RENDER_HEAD = {render_head}
RENDER_BODY = {render_body}

bpy.ops.wm.open_mainfile(filepath=BLEND)

# Monde studio neutre
monde = bpy.data.worlds.get("MondeStudio") or bpy.data.worlds.new("MondeStudio")
bpy.context.scene.world = monde
monde.use_nodes = True
bg = next(n for n in monde.node_tree.nodes if n.type == 'BACKGROUND')
bg.inputs[0].default_value = (0.06, 0.065, 0.08, 1.0)
bg.inputs[1].default_value = 1.0

scn = bpy.context.scene
col = scn.collection
scn.render.engine = 'CYCLES'
scn.cycles.device = 'CPU'
scn.cycles.samples = SAMPLES
scn.cycles.use_denoising = True
scn.render.image_settings.file_format = 'PNG'

resultats = {{}}

def nettoyer_objets(noms):
    for o in list(col.objects):
        if o.name in noms:
            bpy.data.objects.remove(o, do_unlink=True)

if RENDER_HEAD:
    # 1. Cacher vêtements
    for o in bpy.data.objects:
        if o.type == 'MESH' and any(k in o.name.lower() for k in ("robe", "shoes", "clothes", "work", "armor", "pants", "shirt")):
            o.hide_render = True
            o.hide_viewport = True

    # 2. Désactiver les masques de coupe pour ne pas tronquer la mâchoire et le cou
    for o in bpy.data.objects:
        if o.type == 'MESH':
            for m in o.modifiers:
                if "delete" in m.name.lower():
                    m.show_viewport = False
                    m.show_render = False

    dg = bpy.context.evaluated_depsgraph_get()
    corps = max((o for o in bpy.data.objects if o.type == 'MESH' and not o.hide_render),
                key=lambda o: len(o.data.vertices))
    ev = corps.evaluated_get(dg)
    pts = [corps.matrix_world @ v.co for v in ev.data.vertices]
    zs = sorted(p.z for p in pts)
    zmax = zs[-1]
    tete_pts = [p for p in pts if p.z > zmax - 0.16]
    cx = sum(p.x for p in tete_pts) / len(tete_pts)
    cy = sum(p.y for p in tete_pts) / len(tete_pts)
    cz = sum(p.z for p in tete_pts) / len(tete_pts)

    nettoyer_objets(["Key", "Fill", "Rim", "Portrait", "Cible"])
    cible = bpy.data.objects.new("Cible", None)
    col.objects.link(cible)
    cible.location = mathutils.Vector((cx, cy, cz))

    for nom, energie, taille, pos in [
            ("Key", 36.0, 0.6, (cx + 0.38, cy - 0.58, cz + 0.22)),
            ("Fill", 14.0, 0.9, (cx - 0.45, cy - 0.48, cz - 0.02)),
            ("Rim", 22.0, 0.4, (cx - 0.22, cy + 0.48, cz + 0.18))]:
        lum = bpy.data.lights.new(nom, type='AREA')
        lum.energy = energie
        lum.size = taille
        o = bpy.data.objects.new(nom, lum)
        col.objects.link(o)
        o.location = mathutils.Vector(pos)
        con = o.constraints.new('TRACK_TO')
        con.target = cible
        con.track_axis = 'TRACK_NEGATIVE_Z'
        con.up_axis = 'UP_Y'

    cam_d = bpy.data.cameras.new("Portrait")
    cam_d.lens = 85.0
    cam = bpy.data.objects.new("Portrait", cam_d)
    col.objects.link(cam)
    con = cam.constraints.new('TRACK_TO')
    con.target = cible
    con.track_axis = 'TRACK_NEGATIVE_Z'
    con.up_axis = 'UP_Y'
    scn.camera = cam

    scn.render.resolution_x = 1024
    scn.render.resolution_y = 1024

    vues = {{"face": (cx, cy - 0.58, cz + 0.02),
            "tiers": (cx + 0.33, cy - 0.48, cz + 0.05)}}
    for nom, (x, y, z) in vues.items():
        cam.location = mathutils.Vector((x, y, z))
        bpy.context.view_layer.update()
        chemin = f"{{OUT}}_tete_{{nom}}.png"
        scn.render.filepath = chemin
        bpy.ops.render.render(write_still=True)
        resultats[f"tete_{{nom}}"] = chemin

if RENDER_BODY:
    # 1. Réafficher tous les objets
    for o in bpy.data.objects:
        o.hide_render = False
        o.hide_viewport = False

    # 2. Réactiver les masques de coupe pour la tenue
    for o in bpy.data.objects:
        if o.type == 'MESH':
            for m in o.modifiers:
                if "delete" in m.name.lower():
                    m.show_viewport = True
                    m.show_render = True

    dg = bpy.context.evaluated_depsgraph_get()
    all_pts = []
    for o in bpy.data.objects:
        if o.type == 'MESH' and not o.hide_render:
            ev = o.evaluated_get(dg)
            all_pts.extend([o.matrix_world @ v.co for v in ev.data.vertices])

    min_z, max_z = min(p.z for p in all_pts), max(p.z for p in all_pts)
    min_x, max_x = min(p.x for p in all_pts), max(p.x for p in all_pts)
    min_y, max_y = min(p.y for p in all_pts), max(p.y for p in all_pts)

    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0
    cz = (min_z + max_z) / 2.0
    hauteur = max_z - min_z

    nettoyer_objets(["KeyP", "FillP", "RimP", "PortraitCorps", "CibleCorps", "Key", "Fill", "Rim", "Portrait", "Cible"])
    cible_corps = bpy.data.objects.new("CibleCorps", None)
    col.objects.link(cible_corps)
    cible_corps.location = mathutils.Vector((cx, cy, cz + 0.04 * hauteur))

    for nom, energie, taille, pos in [
            ("KeyP", 75.0, 1.2, (cx + 1.1, cy - 1.8, max_z - 0.15)),
            ("FillP", 30.0, 1.8, (cx - 1.3, cy - 1.5, cz)),
            ("RimP", 50.0, 0.8, (cx - 0.5, cy + 1.8, max_z - 0.1))]:
        lum = bpy.data.lights.new(nom, type='AREA')
        lum.energy = energie
        lum.size = taille
        o = bpy.data.objects.new(nom, lum)
        col.objects.link(o)
        o.location = mathutils.Vector(pos)
        con = o.constraints.new('TRACK_TO')
        con.target = cible_corps
        con.track_axis = 'TRACK_NEGATIVE_Z'
        con.up_axis = 'UP_Y'

    cam_d = bpy.data.cameras.new("PortraitCorps")
    cam_d.lens = 55.0
    cam = bpy.data.objects.new("PortraitCorps", cam_d)
    col.objects.link(cam)
    con = cam.constraints.new('TRACK_TO')
    con.target = cible_corps
    con.track_axis = 'TRACK_NEGATIVE_Z'
    con.up_axis = 'UP_Y'
    scn.camera = cam

    scn.render.resolution_x = 896
    scn.render.resolution_y = 1536

    v_fov_half = math.atan((36.0 / 2.0) / 55.0)
    dist = (hauteur * 1.28) / (2.0 * math.tan(v_fov_half))

    vues = {{"face": (cx, cy - dist, cz + 0.04 * hauteur),
            "tiers": (cx + dist * 0.52, cy - dist * 0.85, cz + 0.07 * hauteur)}}
    for nom, (x, y, z) in vues.items():
        cam.location = mathutils.Vector((x, y, z))
        bpy.context.view_layer.update()
        chemin = f"{{OUT}}_perso_{{nom}}.png"
        scn.render.filepath = chemin
        bpy.ops.render.render(write_still=True)
        resultats[f"perso_{{nom}}"] = chemin

print("RENDERS_RESULT_JSON:" + json.dumps(resultats))
"""

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tf:
        tf.write(script)
        temp_script = tf.name

    try:
        cmd = [blender_bin, "--background", "--python", temp_script]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        out_json = {}
        stdout_txt = res.stdout or ""
        for line in stdout_txt.splitlines():
            if line.startswith("RENDERS_RESULT_JSON:"):
                out_json = json.loads(line[len("RENDERS_RESULT_JSON:"):])
                break
        return out_json
    finally:
        if os.path.exists(temp_script):
            try:
                os.remove(temp_script)
            except Exception:
                pass


def creer_corps_personnage_mpfb(
    char_name: str,
    output_blend_path: str,
    output_glb_path: Optional[str] = None,
    ink_json_path: Optional[str] = None,
    eye_texture_path: Optional[str] = None,
    skin_mhmat_path: Optional[str] = None,
    gender: float = 0.0,
    age: float = 0.12,
    weight: float = 0.36,
    muscle: float = 0.12,
    height: float = 0.32,
    hair_asset: str = "short01.mhclo",
    hair_color: tuple = (0.015, 0.015, 0.018, 1.0),
    clothes_assets: Optional[List[tuple]] = None,
    rig: str = "mixamo"
) -> bool:
    """
    Crée automatiquement le corps 3D complet d'un personnage MakeHuman / MPFB2 dans Blender :
      - Création du basemesh humain MPFB avec les macro-détails (âge, genre, poids, muscle, taille)
      - Cibles morphologiques faciales
      - Application du skin (MAKESKIN)
      - Chargement du calque d'encre MakeUp (.json MPFB)
      - Ajout des yeux, sourcils, langue, dents, cheveux et vêtements (.mhclo)
      - Configuration des matériaux PBR (SSS peau, micro-relief bump, yeux luminescents, cheveux sombres)
      - Ajout de l'armature Mixamo compatible
      - Exportation de la scène .blend native éditable et du modèle de jeu .glb
    """
    blender_bin = trouver_blender()
    if not blender_bin:
        raise RuntimeError("Exécutable Blender introuvable.")

    out_blend_esc = os.path.abspath(output_blend_path).replace("\\", "/")
    out_glb_esc = os.path.abspath(output_glb_path).replace("\\", "/") if output_glb_path else ""
    ink_json_esc = os.path.abspath(ink_json_path).replace("\\", "/") if ink_json_path else ""
    eye_tex_esc = os.path.abspath(eye_texture_path).replace("\\", "/") if eye_texture_path else ""
    skin_mhmat_esc = os.path.abspath(skin_mhmat_path).replace("\\", "/") if skin_mhmat_path else ""

    os.makedirs(os.path.dirname(output_blend_path), exist_ok=True)
    if output_glb_path:
        os.makedirs(os.path.dirname(output_glb_path), exist_ok=True)

    default_clothes = [
        ("clothes", "donitz_monk_robe.mhclo", "Clothes"),
        ("clothes", "paysan_medieval_shoes.mhclo", "Clothes")
    ]
    selected_clothes = clothes_assets if clothes_assets is not None else default_clothes
    clothes_repr = json.dumps(selected_clothes)

    hair_asset_stem = Path(hair_asset).stem

    script = f"""
import bpy
import bmesh
import os
import sys
import json

def dynamic_import(absolute_package_str, key):
    for amod in sys.modules:
        if amod.endswith(absolute_package_str):
            mpfb_mod = __import__(amod, fromlist=[key])
            if hasattr(mpfb_mod, key):
                return getattr(mpfb_mod, key)
    raise ValueError(f"Module {{absolute_package_str}} introuvable")

bpy.ops.wm.read_factory_settings(use_empty=True)
try:
    bpy.ops.preferences.addon_enable(module="bl_ext.user_default.mpfb")
except Exception:
    pass

HumanService = dynamic_import("mpfb.services.humanservice", "HumanService")
AssetService = dynamic_import("mpfb.services.assetservice", "AssetService")
TargetService = dynamic_import("mpfb.services.targetservice", "TargetService")
from bl_ext.user_default.mpfb.entities.objectproperties import HumanObjectProperties

# 1. Scène vierge + création du corps
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

human = HumanService.create_human()
HumanObjectProperties.set_value("gender", {gender}, entity_reference=human)
HumanObjectProperties.set_value("age", {age}, entity_reference=human)
HumanObjectProperties.set_value("weight", {weight}, entity_reference=human)
HumanObjectProperties.set_value("muscle", {muscle}, entity_reference=human)
HumanObjectProperties.set_value("height", {height}, entity_reference=human)
TargetService.reapply_macro_details(human)
bpy.context.view_layer.update()

# Cibles faciales émotionnelles douces
for target, val in [("mouth-angles-down", 0.35), ("cheek-bones-incr", 0.30), ("chin-cleft-decr", 0.50)]:
    try:
        TargetService.has_target(human, target)
        HumanObjectProperties.set_value(target, val, entity_reference=human)
    except Exception:
        pass

# 2. Skin MakeHuman
skin_path = r"{skin_mhmat_esc}"
if not skin_path or not os.path.exists(skin_path):
    skin_path = AssetService.find_asset_absolute_path("{char_name}_enfant.mhmat", asset_subdir="skins")
if not skin_path or not os.path.exists(skin_path):
    skin_path = AssetService.find_asset_absolute_path("young_caucasian_male.mhmat", asset_subdir="skins")

if skin_path and os.path.exists(skin_path):
    HumanService.set_character_skin(skin_path, human, skin_type="MAKESKIN")

# 2.5 MakeUp ink layer
_MatService = dynamic_import("mpfb.services.materialservice", "MaterialService")
_type_mat = _MatService.identify_material(_MatService.get_material(human))
ink_json = r"{ink_json_esc}"
if ink_json and os.path.exists(ink_json) and _type_mat in ("makeskin", "layered_skin"):
    try:
        _MatService.load_ink_layer(human, ink_json)
        print("INK_LAYER_LOADED")
    except Exception as e:
        print("[MAKEUP] Erreur chargement ink layer:", e)

# 3. Rig Mixamo (doit être créé AVANT les vêtements pour que MPFB applique automatiquement le skinning)
if "{rig}":
    HumanService.add_builtin_rig(human, "{rig}")

# 4. Assets natifs (yeux, sourcils, langue, dents, cheveux, vêtements)
base_assets = [
    ("eyes", "low-poly.mhclo", "Eyes"),
    ("eyebrows", "eyebrow001.mhclo", "Eyebrows"),
    ("tongue", "tongue01.mhclo", "Tongue"),
    ("teeth", "teeth_base.mhclo", "Teeth"),
    ("hair", "{hair_asset}", "Hair"),
]
clothes_list = {clothes_repr}
all_assets = base_assets + clothes_list

for subdir, fname, atype in all_assets:
    p = AssetService.find_asset_absolute_path(fname, asset_subdir=subdir)
    if p:
        HumanService.add_mhclo_asset(p, human, asset_type=atype, material_type="GAMEENGINE")

bpy.context.view_layer.update()

# Shaders sourcils & cheveux
hair_col = {hair_color}
for kw, name, rough in [("eyebrow", f"{char_name}_Sourcils", 0.75), ("{hair_asset_stem}", f"{char_name}_Cheveux", 0.65)]:
    obj = next((o for o in bpy.data.objects if kw in o.name.lower()), None)
    if obj:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        b.inputs['Base Color'].default_value = hair_col
        b.inputs['Roughness'].default_value = rough
        obj.data.materials.clear()
        obj.data.materials.append(m)

# Shaders PBR peau (micro-relief)
corps = next((o for o in bpy.data.objects if o.type == 'MESH' and "base" in o.name.lower()), None) or \
        next((o for o in bpy.data.objects if o.type == 'MESH'), None)
if corps and corps.data.materials:
    mat = corps.data.materials[0]
    b = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Roughness'].default_value = 0.48
    nt = mat.node_tree
    bruit = nt.nodes.new('ShaderNodeTexNoise')
    bruit.inputs['Scale'].default_value = 180.0
    bosse = nt.nodes.new('ShaderNodeBump')
    bosse.inputs['Strength'].default_value = 0.15
    nt.links.new(bruit.outputs['Fac'], bosse.inputs['Height'])
    nt.links.new(bosse.outputs['Normal'], b.inputs['Normal'])

# Shaders yeux (texture cyan + lueur interne)
eye_path = r"{eye_tex_esc}"
for o in bpy.data.objects:
    if o.type != 'MESH' or 'low-poly' not in o.name.lower():
        continue
    for mat in o.data.materials:
        if not mat.use_nodes:
            continue
        tex = mat.node_tree.nodes.get("DiffuseTexture")
        if tex and eye_path and os.path.exists(eye_path):
            tex.image = bpy.data.images.load(eye_path, check_existing=True)
        b = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
        b.inputs['Roughness'].default_value = 0.03
        try:
            b.inputs['Emission Color'].default_value = (0.2, 0.75, 0.85, 1.0)
            b.inputs['Emission Strength'].default_value = 0.06
        except KeyError:
            pass

# 5. Export .blend et .glb
out_blend = r"{out_blend_esc}"
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
print("BLEND_SAVED_SUCCESS")

out_glb = r"{out_glb_esc}"
if out_glb:
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.export_scene.gltf(
        filepath=out_glb,
        export_format='GLB',
        use_selection=True,
        export_apply=True,
        export_materials='EXPORT',
        export_yup=True
    )
    print("GLB_EXPORT_SUCCESS")

print("BODY_CREATED_SUCCESS")
"""

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tf:
        tf.write(script)
        temp_script = tf.name

    try:
        cmd = [blender_bin, "--background", "--python", temp_script]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        stdout_txt = res.stdout or ""
        if "BODY_CREATED_SUCCESS" in stdout_txt:
            return True
        else:
            print(f"Erreur création corps MPFB : {res.stderr or stdout_txt}")
            return False
    finally:
        if os.path.exists(temp_script):
            try:
                os.remove(temp_script)
            except Exception:
                pass


