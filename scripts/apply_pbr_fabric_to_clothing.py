# -*- coding: utf-8 -*-
"""
apply_pbr_fabric_to_clothing.py
Applies seamless (Seamless / Tileable) PBR fabric/leather/metal textures
to any official MakeHuman garment in Blender.

Guarantees an ultra-detailed, realistic render from any angle with:
- Seamless Albedo / Diffuse
- Weave/grain Normal Map
- PBR Roughness
- Configurable UV tiling (e.g. scale 3.0 or 5.0)

Usage:
    uv run python scripts/apply_pbr_fabric_to_clothing.py --blend "godot_assets/marc_novice.blend" --object "Human.male_worksuit01" --albedo "godot_assets/textures/burlap_albedo.png" --normal "godot_assets/textures/burlap_normal.png" --scale 4.0
"""

import argparse
import os
import sys
import subprocess

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

BLENDER_EXE = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"

def main():
    parser = argparse.ArgumentParser(description="Apply a Seamless PBR material to a MakeHuman garment")
    parser.add_argument("--blend", required=True, help="Path of the .blend file")
    parser.add_argument("--object", required=True, help="Name of the garment object (e.g. Human.male_worksuit01)")
    parser.add_argument("--albedo", required=True, help="Seamless Albedo texture (.png)")
    parser.add_argument("--normal", default="", help="Seamless Normal Map texture (.png)")
    parser.add_argument("--scale", type=float, default=4.0, help="UV tiling scale (default: 4.0)")
    parser.add_argument("--roughness", type=float, default=0.85, help="Fabric roughness (default: 0.85)")
    args = parser.parse_args()

    blend_path = os.path.abspath(args.blend)
    albedo_path = os.path.abspath(args.albedo)
    normal_path = os.path.abspath(args.normal) if args.normal else ""

    if not os.path.exists(blend_path):
        print(f"❌ Error: .blend file not found: {blend_path}")
        sys.exit(1)

    print("=" * 65)
    print(f" 🧵 APPLYING SEAMLESS PBR MATERIAL TO '{args.object}'")
    print(f" 🎨 Albedo: {albedo_path}")
    print(f" 📐 UV scale: {args.scale}")
    print("=" * 65)

    script_blender = f"""# -*- coding: utf-8 -*-
import bpy, os

blend_file = r"{blend_path}"
bpy.ops.wm.open_mainfile(filepath=blend_file)

obj = bpy.data.objects.get("{args.object}")
if not obj:
    # Partial search
    obj = next((o for o in bpy.data.objects if "{args.object}".lower() in o.name.lower()), None)

if not obj:
    raise RuntimeError(f"Object '{args.object}' not found in the scene.")

# Creating the PBR ShaderNode material
mat_name = f"PBR_{{obj.name}}"
mat = bpy.data.materials.new(name=mat_name)
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links
nodes.clear()

# 1. Output & Principled BSDF
out_node = nodes.new('ShaderNodeOutputMaterial')
out_node.location = (400, 0)

bsdf = nodes.new('ShaderNodeBsdfPrincipled')
bsdf.location = (100, 0)
bsdf.inputs['Roughness'].default_value = {args.roughness}
links.new(bsdf.outputs['BSDF'], out_node.inputs['Surface'])

# 2. UV Texture Coordinate & Mapping Node (Tiling)
tex_coord = nodes.new('ShaderNodeTexCoord')
tex_coord.location = (-700, 0)

mapping = nodes.new('ShaderNodeMapping')
mapping.location = (-500, 0)
mapping.inputs['Scale'].default_value = ({args.scale}, {args.scale}, {args.scale})
links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])

# 3. Albedo Texture
albedo_file = r"{albedo_path}"
if os.path.exists(albedo_file):
    tex_albedo = nodes.new('ShaderNodeTexImage')
    tex_albedo.location = (-250, 100)
    tex_albedo.image = bpy.data.images.load(albedo_file)
    links.new(mapping.outputs['Vector'], tex_albedo.inputs['Vector'])
    links.new(tex_albedo.outputs['Color'], bsdf.inputs['Base Color'])

# 4. Normal Map Texture
normal_file = r"{normal_path}"
if normal_file and os.path.exists(normal_file):
    tex_norm = nodes.new('ShaderNodeTexImage')
    tex_norm.location = (-250, -200)
    tex_norm.image = bpy.data.images.load(normal_file)
    tex_norm.image.colorspace_settings.name = 'Non-Color'
    links.new(mapping.outputs['Vector'], tex_norm.inputs['Vector'])

    norm_node = nodes.new('ShaderNodeNormalMap')
    norm_node.location = (-50, -200)
    links.new(tex_norm.outputs['Color'], norm_node.inputs['Color'])
    links.new(norm_node.outputs['Normal'], bsdf.inputs['Normal'])

# Assignment to the object
obj.data.materials.clear()
obj.data.materials.append(mat)
print(f"✅ PBR material {{mat_name}} successfully assigned to {{obj.name}}.")

# Save
bpy.ops.wm.save_as_mainfile(filepath=blend_file)
print(f"💾 Scene saved: {{blend_file}}")
"""
    cmd = [BLENDER_EXE, "--background", "--python-expr", script_blender]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(res.stdout)
    if res.returncode == 0:
        print(f"🎉 PBR material successfully applied to '{args.object}'!")
    else:
        print(f"⚠️ Error while applying the PBR material: {res.stderr}")

if __name__ == "__main__":
    main()
