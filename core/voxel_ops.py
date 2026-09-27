#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
3D Voxel generation module (Extrusion, interior face culling and .GLB export for Godot 4).
"""

import json
import os
from typing import Tuple
import numpy as np
from PIL import Image

from core.blender_ops import trouver_blender
from core.process import run_engine


def image_vers_grille_voxels(
    image: Image.Image,
    grid_size: int = 32,
    epaisseur_max: int = 4,
    mode_relief: bool = True
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Transforms an RGBA image into a discrete 3D volume (occupancy and RGB colors).

    Returns:
        occupancy: 3D boolean array (H, W, D)
        colors: 4D float32 array (H, W, D, 3) in [0, 1]
    """
    img_rgba = image.convert("RGBA")
    # Resize to the grid resolution
    img_resized = img_rgba.resize((grid_size, grid_size), Image.Resampling.NEAREST)
    arr = np.array(img_resized)

    rgb = arr[:, :, :3].astype(np.float32) / 255.0
    alpha = arr[:, :, 3]

    h, w = grid_size, grid_size
    d = max(1, epaisseur_max)

    occupancy = np.zeros((h, w, d), dtype=bool)
    colors = np.zeros((h, w, d, 3), dtype=np.float32)

    lum = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]

    for y in range(h):
        for x in range(w):
            if alpha[y, x] > 30:
                if mode_relief:
                    # Variable thickness based on luminance
                    val_lum = lum[y, x]
                    demi_prof = max(1, int(round(val_lum * (d / 2.0))))
                    z_min = max(0, d // 2 - demi_prof)
                    z_max = min(d, d // 2 + demi_prof + 1)
                else:
                    z_min = 0
                    z_max = d

                for z in range(z_min, z_max):
                    occupancy[y, x, z] = True
                    colors[y, x, z] = rgb[y, x]

    return occupancy, colors


def exporter_voxel_glb(
    nom_base: str,
    output_dir: str,
    occupancy: np.ndarray,
    colors: np.ndarray,
    voxel_scale: float = 0.05
) -> str:
    """
    Generates an optimized .glb file with Vertex Colors via Blender Headless.
    Only the visible outer faces are created (interior faces culled).
    """
    os.makedirs(output_dir, exist_ok=True)
    chemin_glb = os.path.join(output_dir, f"{nom_base}.glb")
    blender_exe = trouver_blender()

    if not blender_exe:
        raise RuntimeError("Blender is required for exporting Voxel .glb 3D models.")

    # Extraction of the visible quads
    h, w, d = occupancy.shape

    # Definition of the 6 faces of a unit cube centered at (0,0,0)
    # Normal: (+X, -X, +Y, -Y, +Z, -Z)
    cube_faces = [
        # +X (right)
        {"dir": (0, 1, 0), "verts": [(0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (0.5, 0.5, 0.5), (0.5, -0.5, 0.5)]},
        # -X (left)
        {"dir": (0, -1, 0), "verts": [(-0.5, 0.5, -0.5), (-0.5, -0.5, -0.5), (-0.5, -0.5, 0.5), (-0.5, 0.5, 0.5)]},
        # +Y (bottom in image, +Y in 3D)
        {"dir": (1, 0, 0), "verts": [(-0.5, 0.5, -0.5), (0.5, 0.5, -0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5)]},
        # -Y (top in image)
        {"dir": (-1, 0, 0), "verts": [(0.5, -0.5, -0.5), (-0.5, -0.5, -0.5), (-0.5, -0.5, 0.5), (0.5, -0.5, 0.5)]},
        # +Z (front)
        {"dir": (0, 0, 1), "verts": [(-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5)]},
        # -Z (back)
        {"dir": (0, 0, -1), "verts": [(0.5, -0.5, -0.5), (-0.5, -0.5, -0.5), (-0.5, 0.5, -0.5), (0.5, 0.5, -0.5)]}
    ]

    all_verts = []
    all_faces = []
    all_colors = []
    vert_count = 0

    for y in range(h):
        for x in range(w):
            for z in range(d):
                if not occupancy[y, x, z]:
                    continue

                col = colors[y, x, z].tolist()
                # Centered 3D coordinates
                pos_x = (x - w / 2.0) * voxel_scale
                pos_y = -(y - h / 2.0) * voxel_scale
                pos_z = (z - d / 2.0) * voxel_scale

                # Test the 6 neighbors
                for f_info in cube_faces:
                    dy, dx_dir, dz = f_info["dir"]
                    ny, nx, nz = y + dy, x + dx_dir, z + dz
                    # If the neighbor is out of bounds or empty, the face is visible!
                    if ny < 0 or ny >= h or nx < 0 or nx >= w or nz < 0 or nz >= d or not occupancy[ny, nx, nz]:
                        # Add the 4 vertices
                        face_indices = []
                        for vx, vy, vz in f_info["verts"]:
                            all_verts.append((pos_x + vx * voxel_scale, pos_y + vy * voxel_scale, pos_z + vz * voxel_scale))
                            face_indices.append(vert_count)
                            vert_count += 1
                        all_faces.append(face_indices)
                        all_colors.append(col)

    data_payload = {
        "vertices": all_verts,
        "faces": all_faces,
        "colors": all_colors,
        "output_glb": os.path.abspath(chemin_glb)
    }

    json_temp = os.path.abspath(os.path.join(output_dir, f"{nom_base}_voxel_data.json"))
    with open(json_temp, "w", encoding="utf-8") as f:
        json.dump(data_payload, f)

    script_blender = f"""
import bpy
import json

bpy.ops.wm.read_factory_settings(use_empty=True)

with open(r'{json_temp}', 'r', encoding='utf-8') as f:
    data = json.load(f)

mesh = bpy.data.meshes.new(name="VoxelMesh")
obj = bpy.data.objects.new("VoxelObject", mesh)
bpy.context.scene.collection.objects.link(obj)

verts = data["vertices"]
faces = data["faces"]
colors = data["colors"]

mesh.from_pydata(verts, [], faces)
mesh.update()

# Add Vertex Colors
vcol = mesh.color_attributes.new(name="Color", type='FLOAT_COLOR', domain='CORNER')
for loop_idx, loop in enumerate(mesh.loops):
    face_idx = loop_idx // 4
    col = colors[face_idx]
    vcol.data[loop_idx].color = (col[0], col[1], col[2], 1.0)

# Material with Vertex Color for Godot
mat = bpy.data.materials.new(name="VoxelMaterial")
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links
nodes.clear()

node_attr = nodes.new(type="ShaderNodeAttribute")
node_attr.attribute_name = "Color"
node_bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
node_bsdf.inputs['Roughness'].default_value = 0.6
node_bsdf.inputs['Metallic'].default_value = 0.0
node_out = nodes.new(type="ShaderNodeOutputMaterial")

links.new(node_attr.outputs['Color'], node_bsdf.inputs['Base Color'])
links.new(node_bsdf.outputs['BSDF'], node_out.inputs['Surface'])

obj.data.materials.append(mat)

bpy.ops.export_scene.gltf(
    filepath=data["output_glb"],
    export_format='GLB',
    use_selection=False,
    export_apply=True,
    export_attributes=True
)
"""
    script_temp = os.path.abspath(os.path.join(output_dir, f"{nom_base}_voxel_script.py"))
    with open(script_temp, "w", encoding="utf-8") as f:
        f.write(script_blender)

    cmd = [blender_exe, "-b", "--python", script_temp]
    run_engine(cmd, check=True, timeout=600, etiquette="blender voxel")

    # Temporary file cleanup
    for temp in (json_temp, script_temp):
        if os.path.exists(temp):
            os.remove(temp)

    return chemin_glb
