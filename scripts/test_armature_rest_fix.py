# -*- coding: utf-8 -*-
import bpy

bpy.ops.wm.read_factory_settings(use_empty=True)
kaykit_p = r"C:\test\L'HERITIER DU VIDE\poc_3d\exports\elian_kaykit.glb"
bpy.ops.import_scene.gltf(filepath=kaykit_p)

arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
for o in list(bpy.data.objects):
    if o.type == 'MESH':
        bpy.data.objects.remove(o, do_unlink=True)

print("Armature chargée :", arm.name)

# Clear pose transforms & apply rest pose
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='POSE')
bpy.ops.pose.transforms_clear()
bpy.ops.pose.armature_apply(selected=False)
bpy.ops.object.mode_set(mode='OBJECT')

print("✅ Rest pose de l'armature réinitialisée et appliquée parfaitement")
