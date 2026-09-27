"""Prepares a test mesh in the Blender MCP session: soft purge of the scene,
OBJ/GLB import, renaming, scale normalization, .blend save, audit.

No read_factory_settings (it cuts the addon socket response — pitfall
observed on 2026-09-18): objects are deleted and orphan blocks purged instead.

Usage:
    uv run python scripts/proto_rig/importer_et_preparer.py <chemin_obj_ou_glb> <nom> [--rot-z 90] [--echelle 0.01]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blender_client import envoyer  # noqa: E402

CODE_PREPARER = r"""
import bpy, math, os, json

chemin = r"@CHEMIN@"
nom = "@NOM@"
rot_z = @ROTZ@   # degrees, applied before normalization
echelle = @ECHELLE@

# 1. Soft purge: deletion of the objects + orphan blocks (WITHOUT read_factory_settings)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
for blocs in (bpy.data.meshes, bpy.data.materials, bpy.data.images,
              bpy.data.armatures, bpy.data.actions, bpy.data.lights, bpy.data.cameras):
    for bloc in list(blocs):
        if bloc.users == 0:
            blocs.remove(bloc)

# 2. Import based on the extension
ext = os.path.splitext(chemin)[1].lower()
if ext == '.obj':
    bpy.ops.wm.obj_import(filepath=chemin)
elif ext in ('.glb', '.gltf'):
    bpy.ops.import_scene.gltf(filepath=chemin)
elif ext == '.fbx':
    bpy.ops.import_scene.fbx(filepath=chemin)
else:
    raise ValueError('unsupported extension: ' + ext)

# 3. Gathers the imported objects under a common root if needed, renames the main one
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
if not meshes:
    raise RuntimeError('no mesh imported')
principal = max(meshes, key=lambda o: len(o.data.vertices))
principal.name = nom

# 4. Rotation + normalization on the root objects (root objects recipe §1.26)
for o in bpy.context.scene.objects:
    if o.parent is None:
        o.rotation_euler.rotate_axis('Z', math.radians(rot_z))

bpy.context.view_layer.update()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

if echelle != 1.0:
    for o in bpy.context.scene.objects:
        o.scale *= echelle
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

bpy.context.view_layer.update()

# 5. Audit
d = principal.dimensions
tris = sum(len(p.loop_indices) for p in principal.data.polygons) // 3 if principal.data.polygons else 0
armatures = [o.name for o in bpy.context.scene.objects if o.type == 'ARMATURE']
sauvegarde = r"@SAUVEGARDE@"
if sauvegarde:
    os.makedirs(os.path.dirname(sauvegarde), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=sauvegarde)

print('PRET_AUDIT:' + json.dumps({
    'nom': nom,
    'objets': [o.name for o in bpy.context.scene.objects],
    'sommets': len(principal.data.vertices),
    'tris': tris,
    'dimensions': [round(v, 3) for v in (d.x, d.y, d.z)],
    'armatures': armatures,
    'sauvegarde': sauvegarde,
}))
"""


def preparer(chemin: str, nom: str, rot_z: float = 0.0, echelle: float = 1.0, sauvegarde: str = "") -> dict:
    code = (
        CODE_PREPARER.replace("@CHEFIN@", "")
        .replace("@CHEMIN@", os.path.abspath(chemin))
        .replace("@NOM@", nom)
        .replace("@ROTZ@", str(rot_z))
        .replace("@ECHELLE@", str(echelle))
        .replace("@SAUVEGARDE@", os.path.abspath(sauvegarde) if sauvegarde else "")
    )
    reponse = envoyer("execute_code", {"code": code})
    # double envelope: {status, result:{executed, result:<stdout>}}
    brut = reponse.get("result", "")
    texte = str(brut.get("result", "")) if isinstance(brut, dict) else str(brut)
    for ligne in texte.splitlines():
        if ligne.startswith("PRET_AUDIT:"):
            return json.loads(ligne[len("PRET_AUDIT:"):])
    raise RuntimeError(f"preparation failed: {texte!r}")


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("chemin", help=".obj/.glb/.fbb file to import")
    parseur.add_argument("nom", help="main object name")
    parseur.add_argument("--rot-z", type=float, default=0.0, help="Z rotation in degrees before normalization")
    parseur.add_argument("--echelle", type=float, default=1.0, help="scale factor before normalization")
    parseur.add_argument("--sauver", default="", help="optional .blend save path")
    args = parseur.parse_args()
    audit = preparer(args.chemin, args.nom, args.rot_z, args.echelle, args.sauver)
    print(json.dumps(audit, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
