# -*- coding: utf-8 -*-
import bpy

blend_p = r"C:\test\L'HERITIER DU VIDE\poc_3d\exports\marc_mpfb2.blend"
bpy.ops.wm.open_mainfile(filepath=blend_p)

print("=" * 60)
for o in bpy.data.objects:
    if o.type == 'MESH':
        print(f"Mesh '{o.name}': Vertices={len(o.data.vertices)}, Materials={[m.name for m in o.data.materials if m]}")
        # Bounding box
        zs = [v.co.z for v in o.data.vertices]
        ys = [v.co.y for v in o.data.vertices]
        print(f"  Z: {min(zs):.3f} -> {max(zs):.3f}, Y: {min(ys):.3f} -> {max(ys):.3f}")
