# -*- coding: utf-8 -*-
import bpy

blend_p = r"C:\test\L'HERITIER DU VIDE\poc_3d\exports\marc_mpfb2.blend"
bpy.ops.wm.open_mainfile(filepath=blend_p)

arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
print("Armature:", arm.name if arm else None)

if arm:
    print("Pose Mode Bones:")
    for pb in arm.pose.bones:
        if pb.location.length > 0.001 or pb.rotation_quaternion.w != 1.0 or pb.rotation_euler.to_quaternion().w != 1.0:
            print(f"  Pose bone '{pb.name}': loc={pb.location}, rot_eul={pb.rotation_euler}")

for obj in bpy.data.objects:
    if obj.type == 'MESH':
        print(f"\nMesh '{obj.name}' (Parent: {obj.parent.name if obj.parent else None}):")
        print(f"  Vertex groups: {[vg.name for vg in obj.vertex_groups]}")
