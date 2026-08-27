# -*- coding: utf-8 -*-
import bpy

glb_p = r"C:\test\L'HERITIER DU VIDE\poc_3d\exports\marc_mpfb2.glb"
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb_p)

print("=" * 60)
print("=== INSPECTION DES MATÉRIAUX DU GLB ===")
for mat in bpy.data.materials:
    print(f"Matériau : {mat.name}")
    if hasattr(mat, "blend_method"):
        print(f"  blend_method : {mat.blend_method}")
    if hasattr(mat, "surface_render_method"):
        print(f"  surface_render_method : {mat.surface_render_method}")
    if mat.use_nodes:
        bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if bsdf:
            alpha_sock = bsdf.inputs.get('Alpha')
            is_linked = alpha_sock.is_linked if alpha_sock else False
            val = alpha_sock.default_value if (alpha_sock and not is_linked) else "LINKED"
            print(f"  Alpha socket : {val} (linked={is_linked})")
print("=" * 60)
