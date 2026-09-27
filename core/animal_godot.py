#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Game-ready export of a packed animal (rigged blend, e.g. Quaternius) → Godot GLB.

Recipe VALIDATED by the user on 2026-09-18 (AI RIG campaign, MEMORY_BANK §1.28):
the packs' native mocap rendered in a loop = "perfect" quality; this module
encapsulates the export chain: purging the parasites of the original file
(Camera/Cube/Light from the 2.79 blends), renaming the actions to `AN_*`
(repository clip convention), glTF export one clip per action, then verification
by re-import (bones + clips).

Output: GLB drop-in ready for Godot (AnimationPlayer generated automatically).
"""

import json
import os
import tempfile
from typing import Dict, List, Optional

from core.blender_ops import trouver_blender
from core.process import run_engine

# standard parasite objects of pack files (blend 2.79: default camera/cube/lamp
# objects) — removed before export (never purge anything else by name)
PARASITES_STANDARDS = ("Camera", "Cube", "Light", "Lamp")


def _script_export(chemin_blend: str, sortie_glb: str, prefixe: str) -> str:
    blend_ouvert = os.path.abspath(chemin_blend)
    return f"""
import bpy

# open the pack blend (the workflow runs on a dedicated headless instance)
bpy.ops.wm.open_mainfile(filepath=r"{blend_ouvert}")

# purge the standard parasites of the pack file
for nom in {PARASITES_STANDARDS!r}:
    o = bpy.data.objects.get(nom)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)

# rename the actions to AN_* clips (repository convention)
for a in bpy.data.actions:
    if not a.name.startswith({prefixe!r}):
        a.name = {prefixe!r} + a.name

# select armatures + meshes only (no residual empties/cameras)
for o in bpy.context.scene.objects:
    o.select_set(o.type in {{'ARMATURE', 'MESH'}})
bpy.context.view_layer.objects.active = next(
    (o for o in bpy.context.scene.objects if o.type == 'ARMATURE'), None)

bpy.ops.export_scene.gltf(
    filepath=r"{sortie_glb}",
    export_format='GLB',
    use_selection=True,
    export_apply=False,
    export_animation_mode='ACTIONS',
    export_yup=True,
)
print("EXPORT_OK")
"""


def _script_verif(chemin_glb: str) -> str:
    return f"""
import bpy
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=r"{chemin_glb}")
arms = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
os_count = len(arms[0].data.bones) if arms else 0
clips = sorted(a.name for a in bpy.data.actions)
meshes = len([o for o in bpy.context.scene.objects if o.type == 'MESH'])
print("VERIF_JSON:" + __import__('json').dumps({{
    'os': os_count, 'clips': clips, 'meshes': meshes}}))
"""


def _run_blender(blender: str, script: str) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tf:
        tf.write(script)
        temp = tf.name
    try:
        res = run_engine([blender, "-b", "--python", temp],
                         check=False, timeout=600, etiquette="blender animal")
        return res.stdout or ""
    finally:
        if os.path.exists(temp):
            os.remove(temp)


def exporter_animal_godot(chemin_blend: str, sortie_glb: str,
                          prefixe: str = "AN_",
                          actions_filtre: Optional[List[str]] = None) -> Dict:
    """Exports a packed animal blend to a verified Godot GLB (AN_* clips).

    actions_filtre: optional list of action names to keep (e.g.
    ['Gallop', 'Walk']) — the others are purged before export.
    Returns: dict {glb, os, clips, meshes} or raises RuntimeError.
    """
    blender = trouver_blender()
    if not blender:
        raise RuntimeError("Blender not found (core/blender_ops.trouver_blender).")
    chemin_blend = os.path.abspath(chemin_blend)
    sortie_glb = os.path.abspath(sortie_glb)
    if not os.path.exists(chemin_blend):
        raise FileNotFoundError(f"Source blend not found: {chemin_blend}")
    os.makedirs(os.path.dirname(sortie_glb) or ".", exist_ok=True)

    # optional action purge (renaming done in the export script)
    if actions_filtre:
        purge = f"""
import bpy
garde = {actions_filtre!r}
for a in list(bpy.data.actions):
    if a.name not in garde:
        bpy.data.actions.remove(a)
print("PURGE_ACTIONS_OK")
"""
        _run_blender(blender, purge)

    sortie = _run_blender(blender, _script_export(chemin_blend, sortie_glb, prefixe))
    if "EXPORT_OK" not in sortie:
        extrait = [ligne for ligne in sortie.splitlines() if ligne.strip()][-5:]
        raise RuntimeError("GLB export failed: " + " | ".join(extrait))
    if not os.path.exists(sortie_glb):
        raise RuntimeError(f"GLB not produced: {sortie_glb}")

    verif = _run_blender(blender, _script_verif(sortie_glb))
    rapport = {}
    for ligne in verif.splitlines():
        if ligne.startswith("VERIF_JSON:"):
            rapport = json.loads(ligne[len("VERIF_JSON:"):])
            break
    if not rapport:
        raise RuntimeError("Re-import verification returned no result (unreadable GLB?)")
    rapport.update({"glb": sortie_glb, "source": chemin_blend})
    return rapport
