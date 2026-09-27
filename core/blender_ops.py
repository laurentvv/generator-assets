#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Blender Headless automation module for exporting 3D models (.glb / .gltf) to Godot 4.
Generates textured 3D meshes with full PBR materials (Albedo, Normal, ORM) and sculpted 3D contour cutout.
"""

import json
import os
import shutil
import tempfile
from typing import Optional
import numpy as np
from PIL import Image
from core.process import run_engine

BLENDER_CANDIDATES = [
    os.getenv("BLENDER_PATH", ""),
    "blender",
    r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.1\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
]


def trouver_blender() -> Optional[str]:
    """Finds the Blender executable binary on the system."""
    for cand in BLENDER_CANDIDATES:
        if not cand:
            continue
        if os.path.exists(cand):
            return cand
        if shutil.which(cand):
            return cand
    return None


def verifier_blender() -> bool:
    """Checks whether Blender is available."""
    return trouver_blender() is not None


def exporter_mesh_sculpte_contour(
    nom_base: str,
    output_dir: str,
    albedo_path: str,
    normal_path: Optional[str] = None,
    orm_path: Optional[str] = None,
    height_path: Optional[str] = None,
    resolution: int = 100,
    depth_scale: float = 0.45
) -> str:
    """
    Generates a true sculpted 3D mesh cut out along the image Alpha contour.
    The transparent background is removed from the mesh and the 3D relief is extruded along Z.
    """
    blender_bin = trouver_blender()
    if not blender_bin:
        raise EnvironmentError("Blender not detected. Please install Blender or set BLENDER_PATH.")

    os.makedirs(output_dir, exist_ok=True)
    fichier_glb = os.path.join(output_dir, f"{nom_base}.glb")
    fichier_glb_abs = os.path.abspath(fichier_glb).replace("\\", "/")

    # 1. Compute vertices, faces and UV coordinates from the Alpha contour and the Heightmap
    img = Image.open(albedo_path).convert("RGBA")
    img_small = img.resize((resolution, resolution), Image.Resampling.BILINEAR)
    arr = np.array(img_small)
    alpha = arr[:, :, 3] / 255.0

    if height_path and os.path.exists(height_path):
        img_h = Image.open(height_path).convert("L").resize((resolution, resolution), Image.Resampling.BILINEAR)
        gray = np.array(img_h) / 255.0
    else:
        gray = np.array(img_small.convert("L")) / 255.0

    height_data = gray * alpha

    verts = []
    faces = []
    uvs_list = []
    grid = np.full((resolution, resolution), -1, dtype=int)
    idx = 0

    for y in range(resolution):
        for x in range(resolution):
            if alpha[y, x] > 0.08:
                vx = round((x / (resolution - 1) - 0.5) * 2.0, 4)
                vy = round(-(y / (resolution - 1) - 0.5) * 2.0, 4)
                vz = round(float(height_data[y, x]) * depth_scale, 4)
                verts.append((vx, vy, vz))
                uvs_list.append((round(x / (resolution - 1), 4), round(1.0 - (y / (resolution - 1)), 4)))
                grid[y, x] = idx
                idx += 1

    for y in range(resolution - 1):
        for x in range(resolution - 1):
            v0 = grid[y, x]
            v1 = grid[y, x + 1]
            v2 = grid[y + 1, x + 1]
            v3 = grid[y + 1, x]
            if v0 != -1 and v1 != -1 and v2 != -1 and v3 != -1:
                faces.append((int(v0), int(v1), int(v2), int(v3)))

    data_json = json.dumps({"verts": verts, "faces": faces, "uvs": uvs_list})

    albedo_abs = os.path.abspath(albedo_path).replace("\\", "/")
    normal_abs = os.path.abspath(normal_path).replace("\\", "/") if normal_path and os.path.exists(normal_path) else ""
    orm_abs = os.path.abspath(orm_path).replace("\\", "/") if orm_path and os.path.exists(orm_path) else ""

    script_blender = f"""
import bpy
import os
import json

bpy.ops.wm.read_factory_settings(use_empty=True)

data = json.loads({json.dumps(data_json)})
verts = data['verts']
faces = data['faces']
uvs_list = data['uvs']

mesh = bpy.data.meshes.new("{nom_base}_Mesh3D")
mesh.from_pydata(verts, [], faces)
mesh.update()

uv_layer = mesh.uv_layers.new(name="UVMap")
for poly in mesh.polygons:
    for loop_idx in poly.loop_indices:
        vert_idx = mesh.loops[loop_idx].vertex_index
        uv_layer.data[loop_idx].uv = uvs_list[vert_idx]

obj = bpy.data.objects.new("{nom_base}_Mesh3D", mesh)
bpy.context.collection.objects.link(obj)

mat = bpy.data.materials.new(name="{nom_base}_Material")
if hasattr(mat, "use_nodes"):
    mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links
bsdf = nodes.get("Principled BSDF")

tex_node = nodes.new("ShaderNodeTexImage")
tex_node.image = bpy.data.images.load("{albedo_abs}")
links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])

normal_file = "{normal_abs}"
if normal_file and os.path.exists(normal_file):
    tex_norm = nodes.new("ShaderNodeTexImage")
    tex_norm.image = bpy.data.images.load(normal_file)
    tex_norm.image.colorspace_settings.name = "Non-Color"
    node_norm = nodes.new("ShaderNodeNormalMap")
    links.new(tex_norm.outputs["Color"], node_norm.inputs["Color"])
    links.new(node_norm.outputs["Normal"], bsdf.inputs["Normal"])

orm_file = "{orm_abs}"
if orm_file and os.path.exists(orm_file):
    tex_orm = nodes.new("ShaderNodeTexImage")
    tex_orm.image = bpy.data.images.load(orm_file)
    tex_orm.image.colorspace_settings.name = "Non-Color"
    node_sep = nodes.new("ShaderNodeSeparateColor")
    links.new(tex_orm.outputs["Color"], node_sep.inputs["Color"])
    links.new(node_sep.outputs["Green"], bsdf.inputs["Roughness"])

obj.data.materials.append(mat)

bpy.context.view_layer.objects.active = obj
obj.select_set(True)
bpy.ops.object.shade_smooth()

output_path = "{fichier_glb_abs}"
bpy.ops.export_scene.gltf(filepath=output_path, export_format="GLB")
print(f"✅ GLB export done: {{output_path}}")
"""

    descripteur, temp_script = tempfile.mkstemp(suffix=".py", prefix="ga_blender_sculpt_")
    os.close(descripteur)
    with open(temp_script, "w", encoding="utf-8") as f:
        f.write(script_blender)

    try:
        run_engine([blender_bin, "-b", "--python", temp_script], timeout=600, check=True, etiquette="blender")
        if not os.path.exists(fichier_glb):
            raise FileNotFoundError(f"The file {fichier_glb} was not generated by Blender.")
        return fichier_glb
    finally:
        if os.path.exists(temp_script):
            try:
                os.remove(temp_script)
            except Exception:
                pass


def exporter_mesh_pbr_glb(
    nom_base: str,
    output_dir: str,
    shape: str = "tile",
    albedo_path: Optional[str] = None,
    normal_path: Optional[str] = None,
    orm_path: Optional[str] = None,
    height_path: Optional[str] = None,
    epaisseur: float = 0.1
) -> str:
    """
    Generates a complete 3D mesh (.glb) with embedded PBR textures via Blender headless.
    Supported shapes:
    - 'sculpt' / 'cutout' / 'prop': True 3D cutout along the Alpha contour with relief
    - 'tile': 3D slab / floor with relief
    - 'cube': 3D block / chest / crate
    - 'pillar' / 'cylinder': 3D column / cylinder
    - 'sphere': 3D orb / sphere
    """
    if shape in ["sculpt", "cutout", "prop", "card"] and albedo_path and os.path.exists(albedo_path):
        return exporter_mesh_sculpte_contour(
            nom_base=nom_base,
            output_dir=output_dir,
            albedo_path=albedo_path,
            normal_path=normal_path,
            orm_path=orm_path,
            height_path=height_path
        )

    blender_bin = trouver_blender()
    if not blender_bin:
        raise EnvironmentError("Blender not detected. Please install Blender or set BLENDER_PATH.")

    os.makedirs(output_dir, exist_ok=True)
    fichier_glb = os.path.join(output_dir, f"{nom_base}.glb")
    fichier_glb_abs = os.path.abspath(fichier_glb).replace("\\", "/")

    albedo_abs = os.path.abspath(albedo_path).replace("\\", "/") if albedo_path and os.path.exists(albedo_path) else ""
    normal_abs = os.path.abspath(normal_path).replace("\\", "/") if normal_path and os.path.exists(normal_path) else ""
    orm_abs = os.path.abspath(orm_path).replace("\\", "/") if orm_path and os.path.exists(orm_path) else ""

    script_blender = f"""
import bpy
import os

bpy.ops.wm.read_factory_settings(use_empty=True)

shape = "{shape}".lower()
if shape == "cube":
    bpy.ops.mesh.primitive_cube_add(size=1.5, location=(0, 0, 0.75))
    obj = bpy.context.active_object
    obj.name = "{nom_base}_Cube3D"
elif shape in ["cylinder", "pillar"]:
    bpy.ops.mesh.primitive_cylinder_add(radius=0.75, depth=2.0, location=(0, 0, 1.0))
    obj = bpy.context.active_object
    obj.name = "{nom_base}_Pillar3D"
elif shape == "sphere":
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(0, 0, 1.0))
    obj = bpy.context.active_object
    obj.name = "{nom_base}_Sphere3D"
    bpy.ops.object.shade_smooth()
else:
    bpy.ops.mesh.primitive_plane_add(size=2.0, location=(0, 0, 0))
    obj = bpy.context.active_object
    obj.name = "{nom_base}_Tile3D"

mat = bpy.data.materials.new(name="{nom_base}_Material")
if hasattr(mat, "use_nodes"):
    mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links

bsdf = nodes.get("Principled BSDF")

albedo_file = "{albedo_abs}"
if albedo_file and os.path.exists(albedo_file):
    tex_albedo = nodes.new("ShaderNodeTexImage")
    tex_albedo.image = bpy.data.images.load(albedo_file)
    links.new(tex_albedo.outputs["Color"], bsdf.inputs["Base Color"])

normal_file = "{normal_abs}"
if normal_file and os.path.exists(normal_file):
    tex_norm = nodes.new("ShaderNodeTexImage")
    tex_norm.image = bpy.data.images.load(normal_file)
    tex_norm.image.colorspace_settings.name = "Non-Color"
    node_norm = nodes.new("ShaderNodeNormalMap")
    links.new(tex_norm.outputs["Color"], node_norm.inputs["Color"])
    links.new(node_norm.outputs["Normal"], bsdf.inputs["Normal"])

orm_file = "{orm_abs}"
if orm_file and os.path.exists(orm_file):
    tex_orm = nodes.new("ShaderNodeTexImage")
    tex_orm.image = bpy.data.images.load(orm_file)
    tex_orm.image.colorspace_settings.name = "Non-Color"
    node_sep = nodes.new("ShaderNodeSeparateColor")
    links.new(tex_orm.outputs["Color"], node_sep.inputs["Color"])
    links.new(node_sep.outputs["Green"], bsdf.inputs["Roughness"])

obj.data.materials.append(mat)

output_path = "{fichier_glb_abs}"
bpy.ops.export_scene.gltf(filepath=output_path, export_format="GLB")
print(f"✅ GLB export done: {{output_path}}")
"""

    descripteur, temp_script = tempfile.mkstemp(suffix=".py", prefix="ga_blender_gen_")
    os.close(descripteur)
    with open(temp_script, "w", encoding="utf-8") as f:
        f.write(script_blender)

    try:
        run_engine([blender_bin, "-b", "--python", temp_script], timeout=600, check=True, etiquette="blender")
        if not os.path.exists(fichier_glb):
            raise FileNotFoundError(f"The file {fichier_glb} was not generated by Blender.")
        return fichier_glb
    finally:
        if os.path.exists(temp_script):
            try:
                os.remove(temp_script)
            except Exception:
                pass
