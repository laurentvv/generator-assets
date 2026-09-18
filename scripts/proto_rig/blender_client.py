"""Client socket direct vers l'addon BlenderMCP (localhost:9876).

Permet de piloter Blender sans attendre le rechargement du serveur MCP ZCode :
le protocole est le meme JSON-sur-socket que le paquet uvx blender-mcp.
Utilisable aussi depuis tout script Python (prototypes, futur workflow).

Usage (depuis la racine du depot) :
    uv run python scripts/proto_rig/blender_client.py --ping
    uv run python scripts/proto_rig/blender_client.py --code "import bpy; print(len(bpy.data.objects))"
    uv run python scripts/proto_rig/blender_client.py --scene
    uv run python scripts/proto_rig/blender_client.py --screenshot output/test_rig/cap.png
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys

HOST = "localhost"
PORT = 9876
DELAI_CONNEXION = 10.0
DELAI_REPONSE = 180.0  # rendu EEVEE possible via execute_code


def envoyer(type_commande: str, params: dict | None = None, timeout: float = DELAI_REPONSE) -> dict:
    """Envoie une commande JSON a l'addon et renvoie la reponse decodee.

    Le protocole de l'addon : un document JSON par connexion, reponse en un
    seul flux (json.dumps sans delimiteur) — on accumule jusqu'a parse OK.
    """
    with socket.create_connection((HOST, PORT), timeout=DELAI_CONNEXION) as s:
        s.settimeout(timeout)
        s.sendall(json.dumps({"type": type_commande, "params": params or {}}).encode("utf-8"))
        morceaux: list[bytes] = []
        while True:
            morceau = s.recv(65536)
            if not morceau:
                break
            morceaux.append(morceau)
            try:
                return json.loads(b"".join(morceaux).decode("utf-8"))
            except json.JSONDecodeError:
                continue  # reponse incomplete
    raise RuntimeError("connexion fermee avant reponse complete")


def extraire_resultat(reponse: dict) -> dict:
    """Normalise {status, result} (ping/execute_code) ou resultat brut (screenshot)."""
    if isinstance(reponse, dict) and "result" in reponse:
        return reponse["result"]
    return reponse


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    groupe = parseur.add_mutually_exclusive_group(required=True)
    groupe.add_argument("--ping", action="store_true", help="test de vie du serveur")
    groupe.add_argument("--code", metavar="PY", help="execute du code bpy dans Blender")
    groupe.add_argument("--scene", action="store_true", help="infos de la scene courante")
    groupe.add_argument("--screenshot", metavar="CHEMIN", help="capture du viewport 3D (PNG)")
    parseur.add_argument("--taille-max", type=int, default=1400, help="taille max capture (px)")
    args = parseur.parse_args()

    try:
        if args.ping:
            reponse = envoyer("ping", timeout=15.0)
        elif args.code is not None:
            reponse = envoyer("execute_code", {"code": args.code})
        elif args.scene:
            reponse = envoyer("get_scene_info")
        else:
            chemin = os.path.abspath(args.screenshot)
            reponse = envoyer(
                "get_viewport_screenshot",
                {"filepath": chemin, "max_size": args.taille_max, "format": "png"},
            )
    except (ConnectionRefusedError, socket.timeout, OSError) as e:
        print(f"ERREUR : pas de serveur BlenderMCP sur {HOST}:{PORT} ({e})", file=sys.stderr)
        print("Verifier que Blender est lance avec scripts/proto_rig/demarrer_blender_mcp.py", file=sys.stderr)
        return 1

    print(json.dumps(reponse, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
