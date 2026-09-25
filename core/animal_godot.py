#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export game-ready d'un animal packé (blend riggé, ex. Quaternius) → GLB Godot.

Recette VALIDÉE utilisateur le 2026-09-18 (campagne RIG IA, MEMORY_BANK §1.28) :
le mocap natif des packs rendu en boucle = qualité « parfait » ; ce module
encapsule la chaîne d'export : purge des parasites du fichier d'origine
(Camera/Cube/Light des blends 2.79), renommage des actions en `AN_*`
(convention clips du dépôt), export glTF un clip par action, puis vérification
par ré-import (os + clips).

Sortie : GLB glissable dans Godot (AnimationPlayer généré automatiquement).
"""

import json
import os
import tempfile
from typing import Dict, List, Optional

from core.blender_ops import trouver_blender
from core.process import run_engine

# objets parasites standards des fichiers pack (blend 2.79 : caméra/cube/lampe
# par défaut) — supprimés avant export (jamais de purge « au nom près » d'autre chose)
PARASITES_STANDARDS = ("Camera", "Cube", "Light", "Lamp")


def _script_export(chemin_blend: str, sortie_glb: str, prefixe: str) -> str:
    blend_ouvert = os.path.abspath(chemin_blend)
    return f"""
import bpy

# ouverture du blend pack (le workflow tourne sur une instance headless dediee)
bpy.ops.wm.open_mainfile(filepath=r"{blend_ouvert}")

# purge des parasites standards du fichier pack
for nom in {PARASITES_STANDARDS!r}:
    o = bpy.data.objects.get(nom)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)

# renommage des actions en clips AN_* (convention depot)
for a in bpy.data.actions:
    if not a.name.startswith({prefixe!r}):
        a.name = {prefixe!r} + a.name

# selection armatures + meshes uniquement (pas les vides/cameras residuelles)
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
    """Exporte un blend d'animal packé en GLB Godot (clips AN_*), vérifié.

    actions_filtre : liste optionnelle de noms d'actions à garder (ex.
    ['Gallop', 'Walk']) — les autres sont purgées avant export.
    Retour : dict {glb, os, clips, meshes} ou lève RuntimeError.
    """
    blender = trouver_blender()
    if not blender:
        raise RuntimeError("Blender introuvable (core/blender_ops.trouver_blender).")
    chemin_blend = os.path.abspath(chemin_blend)
    sortie_glb = os.path.abspath(sortie_glb)
    if not os.path.exists(chemin_blend):
        raise FileNotFoundError(f"Blend source introuvable : {chemin_blend}")
    os.makedirs(os.path.dirname(sortie_glb) or ".", exist_ok=True)

    # purge optionnelle d'actions (renommage fait dans le script d'export)
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
        extrait = [l for l in sortie.splitlines() if l.strip()][-5:]
        raise RuntimeError("Export GLB échoué : " + " | ".join(extrait))
    if not os.path.exists(sortie_glb):
        raise RuntimeError(f"GLB non produit : {sortie_glb}")

    verif = _run_blender(blender, _script_verif(sortie_glb))
    rapport = {}
    for ligne in verif.splitlines():
        if ligne.startswith("VERIF_JSON:"):
            rapport = json.loads(ligne[len("VERIF_JSON:"):])
            break
    if not rapport:
        raise RuntimeError("Vérification ré-import sans résultat (GLB illisible ?)")
    rapport.update({"glb": sortie_glb, "source": chemin_blend})
    return rapport
