"""Autostart Blender : active l'addon BlenderMCP (v1.5, socket localhost:9876)
puis lance son serveur. A passer a blender.exe via --python.

Usage :
    blender.exe --python scripts/proto_rig/demarrer_blender_mcp.py
"""

import bpy

MARQUEUR = "PROTO_RIG:"


def _demarrer_serveur():
    try:
        bpy.ops.blendermcp.start_server()
        print(f"{MARQUEUR} serveur socket 9876 demarre")
    except Exception as e:  # pragma: no cover - contexte GUI requis
        print(f"{MARQUEUR} ERREUR demarrage serveur : {e}")
    return None  # timer one-shot


try:
    import addon_utils

    addon_utils.enable("blender_mcp", default_set=True, persistent=True)
    print(f"{MARQUEUR} addon blender_mcp active")
except Exception as e:
    print(f"{MARQUEUR} ERREUR activation addon : {e}")

# Timer : laisse l'interface se construire avant d'appeler l'operateur
bpy.app.timers.register(_demarrer_serveur, first_interval=1.0)
