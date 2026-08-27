# -*- coding: utf-8 -*-
import bpy

blend_p = r"C:\test\L'HERITIER DU VIDE\poc_3d\exports\marc_mpfb2.blend"
bpy.ops.wm.open_mainfile(filepath=blend_p)

print("=" * 60)
print("=== OBJETS DANS LA SCÈNE BLENDER ===")
for o in bpy.data.objects:
    print(f"Objet: {o.name} (Type: {o.type}, Parent: {o.parent.name if o.parent else None})")
    print(f"  Loc: {o.location}, Rot: {o.rotation_euler}, Scale: {o.scale}")
    if o.type == 'MESH':
        print(f"  Modifiers: {[m.name + ' (' + m.type + ')' for m in o.modifiers]}")
        print(f"  Vertex Groups: {[vg.name for vg in o.vertex_groups][:5]}")

arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
if arm:
    print("\n=== OS DE L'ARMATURE ===")
    for b in arm.data.bones:
        print(f"  Bone '{b.name}': head={b.head_local}, tail={b.tail_local}")
print("=" * 60)
