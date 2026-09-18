"""Normalise un mesh de la session Blender MCP : échelle cible sur l'axe long,
origine au monde, pieds au sol (Z=0), centré X/Y, sauvegarde .blend.

Usage :
    uv run python scripts/proto_rig/normaliser_sol.py Wolf 1.32
    uv run python scripts/proto_rig/normaliser_sol.py Horse 2.2 --sauver output/test_rig/scenes/horse_mesh.blend
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blender_client import envoyer  # noqa: E402

CODE = r"""
import bpy, json, mathutils

nom = "@NOM@"
cible = @CIBLE@
sauver = r"@SAUVER@"

obj = bpy.data.objects[nom]
cos = [v.co.copy() for v in obj.data.vertices]
lx = max(c.x for c in cos) - min(c.x for c in cos)
ly = max(c.y for c in cos) - min(c.y for c in cos)
lz = max(c.z for c in cos) - min(c.z for c in cos)
# axe long attendu = Y (convention sujet face -Y)
facteur = cible / ly if ly >= max(lx, lz) else cible / max(lx, lz)
obj.data.transform(mathutils.Matrix.Scale(facteur, 4))
obj.scale = (1.0, 1.0, 1.0)

cos = [v.co.copy() for v in obj.data.vertices]
cx = (min(c.x for c in cos) + max(c.x for c in cos)) / 2
cy = (min(c.y for c in cos) + max(c.y for c in cos)) / 2
czmin = min(c.z for c in cos)
obj.data.transform(mathutils.Matrix.Translation((-cx, -cy, -czmin)))
obj.location = (0.0, 0.0, 0.0)
bpy.context.view_layer.update()

d = obj.dimensions
audit = {
    'nom': nom,
    'dimensions': [round(v, 3) for v in (d.x, d.y, d.z)],
    'facteur': round(facteur, 5),
    'zmin': round(min(v.co.z for v in obj.data.vertices), 4),
}
if sauver:
    bpy.ops.wm.save_as_mainfile(filepath=sauver)
print('NORMALISE:' + json.dumps(audit))
"""


def normaliser(nom: str, cible: float, sauver: str = "") -> dict:
    code = (
        CODE.replace("@NOM@", nom)
        .replace("@CIBLE@", str(cible))
        .replace("@SAUVER@", os.path.abspath(sauver) if sauver else "")
    )
    reponse = envoyer("execute_code", {"code": code})
    brut = reponse.get("result", "")
    texte = str(brut.get("result", "")) if isinstance(brut, dict) else str(brut)
    for ligne in texte.splitlines():
        if ligne.startswith("NORMALISE:"):
            return json.loads(ligne[len("NORMALISE:"):])
    raise RuntimeError(f"normalisation echouee : {texte!r}")


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("nom", help="nom de l'objet dans la scene")
    parseur.add_argument("cible", type=float, help="longueur cible en metres (axe long)")
    parseur.add_argument("--sauver", default="", help="chemin .blend de sauvegarde")
    args = parseur.parse_args()
    audit = normaliser(args.nom, args.cible, args.sauver)
    print(json.dumps(audit, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
