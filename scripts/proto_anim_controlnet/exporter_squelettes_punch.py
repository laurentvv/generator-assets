#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exports the OpenPose COCO 18 choreography of a Quaternius GLB action (anim ControlNet prototype).

Run via Blender headless: dumps the raw WORLD coordinates of the keypoints for N frames
sampled across the action (here CharacterArmature|Punch of the bunny). The conversion to
normalized coordinates (FIXED transformation over the whole sequence, to avoid any scale
jump between frames) is done on the Python side by dessiner_squelettes_punch.py.
"""

import bpy
import json

GLB = r"C:\GIT\roblox\assets3d\bunny_quaternius.glb"
ACTION = "CharacterArmature|Run"
NB_FRAMES = 13
SORTIE = r"C:\GIT\generator-assets\output\test_anim_controlnet\points_run13.json"

# Mapping Quaternius bones (.L/.R = SUBJECT side) -> COCO 18 keypoints (l_*/r_* = subject side).
# No hand bones in Quaternius: wrist = tail of the LowerArm. Real ears via Ear1.
MAPPING_TETE = {"l_shoulder": "UpperArm.L", "r_shoulder": "UpperArm.R",
                "l_elbow": "LowerArm.L", "r_elbow": "LowerArm.R",
                "l_hip": "UpperLeg.L", "r_hip": "UpperLeg.R",
                "l_knee": "LowerLeg.L", "r_knee": "LowerLeg.R",
                "l_ankle": "Foot.L", "r_ankle": "Foot.R",
                "l_ear": "Ear1.L", "r_ear": "Ear1.R"}
POIGNETS = {"l_wrist": "LowerArm.L", "r_wrist": "LowerArm.R"}


def monde(pb, queue=False):
    p = pb.tail if queue else pb.head
    return arm.matrix_world @ p


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
action = bpy.data.actions[ACTION]
arm.animation_data_create()
arm.animation_data.action = action
f0, f1 = int(action.frame_range[0]), int(action.frame_range[1])
frames = [round(i * (f1 - f0 - 1) / (NB_FRAMES - 1)) for i in range(NB_FRAMES)]
print(f"ACTION {action.name}: frames {f0}-{f1} -> samples {frames}")

poses = {}
scene = bpy.context.scene
for idx, fr in enumerate(frames):
    scene.frame_set(fr)
    bpy.context.view_layer.update()
    pb = arm.pose.bones
    points = {}
    for cle, os_nom in MAPPING_TETE.items():
        v = monde(pb[os_nom])
        points[cle] = [v.x, v.y, v.z]
    for cle, os_nom in POIGNETS.items():
        v = monde(pb[os_nom], queue=True)
        points[cle] = [v.x, v.y, v.z]
    cou = monde(pb["Neck"])
    points["neck"] = [cou.x, cou.y, cou.z]
    tete = monde(pb["Head"])
    milieu_tete = [(tete.x + (arm.matrix_world @ pb["Head"].tail).x) / 2,
                   (tete.y + (arm.matrix_world @ pb["Head"].tail).y) / 2,
                   (tete.z + (arm.matrix_world @ pb["Head"].tail).z) / 2]
    points["nose"] = milieu_tete
    poses[f"{idx:02d}"] = points

with open(SORTIE, "w", encoding="utf-8") as f:
    json.dump({"frames": frames, "poses": poses}, f)
print(f"OK: {len(poses)} frames -> {SORTIE}")
