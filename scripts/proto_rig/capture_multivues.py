"""Protocole « capture multi-vues » — socle de vérification visuelle de la campagne RIG.

Place la caméra viewport sur les vues standard (avant / 3-4 / profil / dos),
cadre automatiquement les objets visibles, puis capture le viewport via
l'addon BlenderMCP (rendu offscreen GPU, independant du focus fenetre).

Convention : le sujet regarde -Y (convention Blender/Mixamo). La camera se
place du cote oppose a la direction de visee ; azimut en DEGRES autour de Z.

Usage (depuis la racine du depot, Blender lance avec demarrer_blender_mcp.py) :
    uv run python scripts/proto_rig/capture_multivues.py suzanne
    uv run python scripts/proto_rig/capture_multivues.py loup -d output/test_rig/captures
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blender_client import envoyer  # noqa: E402

# Vues : (azimut deg de la DIRECTION DE VISEE, elevation deg). Avant = camera
# en -Y qui regarde +Y (le sujet fait face a -Y) -> on voit la face.
VUES = {
    "avant": (0.0, 6.0),
    "trois_quarts": (-45.0, 12.0),
    "profil": (-90.0, 5.0),
    "dos": (180.0, 8.0),
}

# Gabarit execute dans Blender. Jetons @AZ@ @EL@ @FACTEUR@ remplaces cote client.
CODE_ORIENTER = """
import bpy, math
from mathutils import Vector

az = math.radians(@AZ@)
el = math.radians(@EL@)

view_layer = bpy.context.view_layer
points = []
for obj in view_layer.objects:
    if obj.type in {'MESH', 'ARMATURE'} and not obj.hide_render and obj.visible_get():
        for coin in (obj.bound_box or []):
            points.append(obj.matrix_world @ Vector(coin))
if not points:
    points = [Vector((0, 0, 0)), Vector((1, 1, 1))]
centre = Vector((0, 0, 0))
for p in points:
    centre += p
centre /= len(points)
rayon = max((p - centre).length for p in points) or 1.0
distance = rayon * @FACTEUR@

# Direction de visee : azimut autour de Z, elevation positive = camera haute
direction = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), -math.sin(el))).normalized()

for aire in bpy.context.screen.areas:
    if aire.type == 'VIEW_3D':
        espace = aire.spaces.active
        r3d = espace.region_3d
        r3d.view_perspective = 'ORTHO'
        espace.overlay.show_floor = False
        espace.overlay.show_axis_x = False
        espace.overlay.show_axis_y = False
        espace.shading.type = 'SOLID'
        r3d.view_location = centre
        r3d.view_distance = distance
        r3d.view_rotation = direction.to_track_quat('-Z', 'Y')
        break
else:
    raise RuntimeError('aucune vue 3D trouvee')
view_layer.update()
dir_lue = r3d.view_rotation @ Vector((0, 0, -1))
print('CADRE_OK centre=(%.2f, %.2f, %.2f) rayon=%.2f dir=(%.2f, %.2f, %.2f)'
      % (centre.x, centre.y, centre.z, rayon, dir_lue.x, dir_lue.y, dir_lue.z))
"""


def capturer_multivues(nom: str, dossier: str, taille_max: int = 1400) -> list[str]:
    """Capture les 4 vues standard ; renvoie les chemins des PNG ecrits."""
    os.makedirs(dossier, exist_ok=True)
    chemins = []
    for vue, (azimut, elevation) in VUES.items():
        code = (
            CODE_ORIENTER.replace("@AZ@", str(azimut))
            .replace("@EL@", str(elevation))
            .replace("@FACTEUR@", "2.6")
        )
        reponse = envoyer("execute_code", {"code": code})
        resultat = str(reponse.get("result", ""))
        if "CADRE_OK" not in resultat:
            raise RuntimeError(f"orientation {vue} echouee : {resultat!r}")
        chemin = os.path.abspath(os.path.join(dossier, f"{nom}_{vue}.png"))
        capture = envoyer(
            "get_viewport_screenshot",
            {"filepath": chemin, "max_size": taille_max, "format": "png"},
        )
        corps = capture.get("result", capture)
        if not corps.get("success"):
            raise RuntimeError(f"capture {vue} echouee : {corps}")
        chemins.append(chemin)
        print(f"[OK] {vue}: {chemin}")
    return chemins


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("nom", help="prefixe des fichiers (ex. suzanne, loup_v1)")
    parseur.add_argument("-d", "--dossier", default="output/test_rig/captures")
    parseur.add_argument("-t", "--taille-max", type=int, default=1400)
    args = parseur.parse_args()
    chemins = capturer_multivues(args.nom, args.dossier, args.taille_max)
    print(json.dumps({"vues": len(chemins), "dossier": args.dossier}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
