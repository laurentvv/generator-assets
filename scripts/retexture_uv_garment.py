# -*- coding: utf-8 -*-
"""
retexture_uv_garment.py
AI transformation of existing MakeHuman UV patterns:
1. Starts from the real MakeHuman UV pattern (e.g. male_worksuit01_diffuse.png or shoes01_diffuse.png).
2. Keeps 100% of the placement of pockets, buttons, seams, straps and UV cuts.
3. Transforms the material (blue jeans -> burlap / medieval linen / aged leather).
4. Generates the associated PBR Normal Map.
5. Applies the new pattern directly in Blender and exports for Godot 4.
"""

import os
import sys
from PIL import Image
import numpy as np

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

WORKSUIT_UV_ORIG = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\data\clothes\male_worksuit01\male_worksuit01_diffuse.png"
SHOES_UV_ORIG = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\data\clothes\shoes01\shoes01_diffuse.png"

OUT_DIR = r"C:\GIT\generator-assets\godot_assets\textures\marc_novice"
BLEND_FILE = r"C:\GIT\generator-assets\godot_assets\marc_novice.blend"
GLB_FILE = r"C:\GIT\generator-assets\godot_assets\marc_novice.glb"
RENDER_FILE = r"C:\GIT\generator-assets\godot_assets\marc_novice_beauty_render.png"

def main():
    print("=" * 65)
    print(" 👗 AI TRANSFORMATION OF THE EXISTING MAKEHUMAN UV PATTERNS")
    print("=" * 65)
    os.makedirs(OUT_DIR, exist_ok=True)

    # 1. Transformation of the Overall / Tunic UV pattern (male_worksuit01)
    # Replacing the modern blue denim with a rustic medieval burlap / hemp cloth
    worksuit_img = Image.open(WORKSUIT_UV_ORIG).convert("RGBA")
    arr_ws = np.array(worksuit_img, dtype=np.float32)

    # Isolate the black background (the pixels where R=G=B=0)
    bg_mask = (arr_ws[:, :, 0] < 10) & (arr_ws[:, :, 1] < 10) & (arr_ws[:, :, 2] < 10)

    # Isolate the metal buckles and buttons at the top left / bottom
    # Buckle zone: Y: 0..400, X: 0..600
    is_buckle = np.zeros(bg_mask.shape, dtype=bool)
    is_buckle[0:450, 0:600] = True

    # Cloth color transformation: blue denim -> earthy beige/brown burlap
    # Base luminance
    lum = (arr_ws[:, :, 0] * 0.299 + arr_ws[:, :, 1] * 0.587 + arr_ws[:, :, 2] * 0.114) / 255.0

    # Rustic burlap tint: RGB = (185, 155, 120) * lum
    burlap_r = np.clip(lum * 195.0 + 15.0, 0, 255)
    burlap_g = np.clip(lum * 165.0 + 10.0, 0, 255)
    burlap_b = np.clip(lum * 125.0 + 5.0, 0, 255)

    # Apply on the cloth (except the black background and the metal buckles)
    cloth_mask = (~bg_mask) & (~is_buckle)
    arr_ws[cloth_mask, 0] = burlap_r[cloth_mask]
    arr_ws[cloth_mask, 1] = burlap_g[cloth_mask]
    arr_ws[cloth_mask, 2] = burlap_b[cloth_mask]

    # Metal buckles: dark wrought iron / medieval bronze instead of blue plastic
    buckle_mask = (~bg_mask) & is_buckle
    arr_ws[buckle_mask, 0] = np.clip(arr_ws[buckle_mask, 0] * 0.8 + 40.0, 0, 255)
    arr_ws[buckle_mask, 1] = np.clip(arr_ws[buckle_mask, 1] * 0.7 + 35.0, 0, 255)
    arr_ws[buckle_mask, 2] = np.clip(arr_ws[buckle_mask, 2] * 0.5 + 25.0, 0, 255)

    worksuit_peasant = Image.fromarray(arr_ws.astype(np.uint8))
    worksuit_out = os.path.join(OUT_DIR, "marc_peasant_worksuit_diffuse.png")
    worksuit_peasant.convert("RGB").save(worksuit_out, "PNG", optimize=True)
    print(f"✅ New Tunic/Overall UV pattern generated: {worksuit_out}")

    # Normal map
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if racine not in sys.path:
        sys.path.insert(0, racine)
    from core.image_ops import generer_normal_map
    ws_norm = generer_normal_map(worksuit_peasant.convert("RGB"), strength=3.0)
    ws_norm_out = os.path.join(OUT_DIR, "marc_peasant_worksuit_normal.png")
    ws_norm.save(ws_norm_out, "PNG")

    # 2. Transformation of the Shoes UV pattern (shoes01)
    shoes_img = Image.open(SHOES_UV_ORIG).convert("RGBA")
    arr_sh = np.array(shoes_img, dtype=np.float32)
    bg_sh = (arr_sh[:, :, 0] < 10) & (arr_sh[:, :, 1] < 10) & (arr_sh[:, :, 2] < 10)

    # Worn dark brown medieval leather
    lum_sh = (arr_sh[:, :, 0] * 0.299 + arr_sh[:, :, 1] * 0.587 + arr_sh[:, :, 2] * 0.114) / 255.0
    arr_sh[~bg_sh, 0] = np.clip(lum_sh[~bg_sh] * 120.0 + 20.0, 0, 255)
    arr_sh[~bg_sh, 1] = np.clip(lum_sh[~bg_sh] * 80.0 + 12.0, 0, 255)
    arr_sh[~bg_sh, 2] = np.clip(lum_sh[~bg_sh] * 55.0 + 8.0, 0, 255)

    shoes_peasant = Image.fromarray(arr_sh.astype(np.uint8))
    shoes_out = os.path.join(OUT_DIR, "marc_peasant_shoes_diffuse.png")
    shoes_peasant.convert("RGB").save(shoes_out, "PNG", optimize=True)
    print(f"✅ New Shoes UV pattern generated: {shoes_out}")

    sh_norm = generer_normal_map(shoes_peasant.convert("RGB"), strength=2.5)
    sh_norm_out = os.path.join(OUT_DIR, "marc_peasant_shoes_normal.png")
    sh_norm.save(sh_norm_out, "PNG")

    # 3. Applying the UV textures in Blender
    from core.blender_ops import trouver_blender
    blender_bin = trouver_blender()

    script_blender = f"""# -*- coding: utf-8 -*-
import bpy, os

blend_file = r"{BLEND_FILE}"
bpy.ops.wm.open_mainfile(filepath=blend_file)

def assign_uv_material(obj_name, diffuse_path, normal_path, roughness_val=0.85):
    obj = next((o for o in bpy.data.objects if obj_name.lower() in o.name.lower()), None)
    if not obj:
        print(f"⚠️ Object {{obj_name}} not found")
        return

    mat = bpy.data.materials.new(name=f"CustomUV_{{obj.name}}")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out_node = nodes.new('ShaderNodeOutputMaterial')
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = roughness_val
    links.new(bsdf.outputs['BSDF'], out_node.inputs['Surface'])

    if os.path.exists(diffuse_path):
        tex_diff = nodes.new('ShaderNodeTexImage')
        tex_diff.image = bpy.data.images.load(diffuse_path)
        links.new(tex_diff.outputs['Color'], bsdf.inputs['Base Color'])

    if os.path.exists(normal_path):
        tex_norm = nodes.new('ShaderNodeTexImage')
        tex_norm.image = bpy.data.images.load(normal_path)
        tex_norm.image.colorspace_settings.name = 'Non-Color'
        norm_node = nodes.new('ShaderNodeNormalMap')
        links.new(tex_norm.outputs['Color'], norm_node.inputs['Color'])
        links.new(norm_node.outputs['Normal'], bsdf.inputs['Normal'])

    obj.data.materials.clear()
    obj.data.materials.append(mat)
    print(f"✅ New UV pattern assigned to {{obj.name}}")

assign_uv_material("worksuit", r"{worksuit_out}", r"{ws_norm_out}", roughness_val=0.90)
assign_uv_material("shoes", r"{shoes_out}", r"{sh_norm_out}", roughness_val=0.75)

bpy.ops.wm.save_as_mainfile(filepath=blend_file)

bpy.ops.object.select_all(action='SELECT')
bpy.ops.export_scene.gltf(
    filepath=r"{GLB_FILE}",
    export_format='GLB',
    use_selection=True,
    export_apply=True,
    export_materials='EXPORT',
    export_yup=True
)
print("✅ GLB updated with the modified UV patterns.")
"""
    import subprocess
    res = subprocess.run([blender_bin, "--background", "--python-expr", script_blender], capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(res.stdout)

    # 4. Cycles validation render
    from scripts.character_pipeline import etape_3_rendre_validation
    etape_3_rendre_validation(blender_bin, GLB_FILE, RENDER_FILE)
    print("=" * 65)

if __name__ == "__main__":
    main()
