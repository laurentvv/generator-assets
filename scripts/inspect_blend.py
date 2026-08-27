# -*- coding: utf-8 -*-
import bpy

blend_p = r"C:\test\L'HERITIER DU VIDE\poc_3d\exports\marc_mpfb2.blend"
bpy.ops.wm.open_mainfile(filepath=blend_p)

# Position de chaque objet dans le monde
print("=" * 60)
print("=== POSITIONS GLOBALES DES MESHES DANS LE BLEND ===")
for o in bpy.data.objects:
    if o.type == 'MESH':
        mw = o.matrix_world
        verts_z = [ (mw @ v.co).z for v in o.data.vertices ]
        verts_y = [ (mw @ v.co).y for v in o.data.vertices ]
        verts_x = [ (mw @ v.co).x for v in o.data.vertices ]
        print(f"Mesh '{o.name}':")
        print(f"  Z bounds: {min(verts_z):.3f} -> {max(verts_z):.3f} m")
        print(f"  Y bounds: {min(verts_y):.3f} -> {max(verts_y):.3f} m")
        print(f"  X bounds: {min(verts_x):.3f} -> {max(verts_x):.3f} m")
        print(f"  Modifiers: {[m.name + ' (' + m.type + ')' for m in o.modifiers]}")

# Évaluer les vertices AVEC les modificateurs appliqués (depsgraph)
dg = bpy.context.evaluated_depsgraph_get()
print("\n=== POSITIONS ÉVALUÉES (AVEC MODIFICATEURS/ARMATURE) ===")
for o in bpy.data.objects:
    if o.type == 'MESH':
        ev = o.evaluated_get(dg)
        mw = o.matrix_world
        eval_z = [ (mw @ v.co).z for v in ev.data.vertices ]
        eval_y = [ (mw @ v.co).y for v in ev.data.vertices ]
        print(f"Mesh '{o.name}' ÉVALUÉ :")
        print(f"  Z bounds: {min(eval_z):.3f} -> {max(eval_z):.3f} m")
        print(f"  Y bounds: {min(eval_y):.3f} -> {max(eval_y):.3f} m")

# Rendu de la vue 3D exacte du .blend
cam_data = bpy.data.cameras.new("InspectCam")
cam_obj = bpy.data.objects.new("InspectCam", cam_data)
bpy.context.collection.objects.link(cam_obj)
cam_obj.location = (0.0, -1.8, 0.7)
cam_obj.rotation_euler = (1.5708, 0, 0)
bpy.context.scene.camera = cam_obj

bpy.context.scene.render.engine = 'BLENDER_WORKBENCH'
bpy.context.scene.render.filepath = r"C:\GIT\generator-assets\godot_assets\inspect_viewport_blend.png"
bpy.ops.render.render(write_still=True)
print("✅ Capture viewport enregistrée : C:\GIT\generator-assets\godot_assets\inspect_viewport_blend.png")
