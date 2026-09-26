#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exporte la chorégraphie OpenPose COCO 18 d'une action GLB Quaternius (prototype anim ControlNet).

Lancé via Blender headless : dump les coordonnées MONDE brutes des keypoints pour N frames
échantillonnées sur l'action (ici CharacterArmature|Punch du bunny). Le passage en coordonnées
normalisées (transformation FIXE sur toute la séquence, pour éviter tout saut d'échelle entre
frames) est fait côté Python par dessiner_squelettes_punch.py.
"""

import bpy
import json

GLB = r"C:\GIT\roblox\assets3d\bunny_quaternius.glb"
ACTION = "CharacterArmature|Run"
NB_FRAMES = 12
SORTIE = r"C:\GIT\generator-assets\output\test_anim_controlnet\points_run.json"

# Mapping os Quaternius (.L/.R = côté SUJET) -> keypoints COCO 18 (l_*/r_* = côté sujet).
# Pas d'os de main chez Quaternius : poignet = queue du LowerArm. Oreilles réelles via Ear1.
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
print(f"ACTION {action.name} : frames {f0}-{f1} -> échantillons {frames}")

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
print(f"OK : {len(poses)} frames -> {SORTIE}")
