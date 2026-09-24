"""
Enregistrement des workflows 2D & 3D.

Chaque module `workflows/<nom>.py` déclare sa (ou ses) classe(s) via
`@WorkflowRegistry.register`. L'import est piloté par la liste ordonnée
`_MODULES_ORDONNES` : c'est elle qui fixe l'ordre du menu interactif et de
`--list-workflows`. Tout nouveau module non listé est découvert automatiquement
(pkgutil) et enregistré en fin de liste — un workflow ne peut plus être absent
du registre par oubli d'import.
"""

import importlib
import pkgutil

from workflows.base import BaseWorkflow, WorkflowRegistry

_MODULES_ORDONNES = [
    "generate", "upscale", "spritesheet", "variations", "tileable", "pixelart",
    "batch", "material3d", "skybox", "turnaround3d", "mesh3d", "mesh_ia", "rembg",
    "flowmap", "ui_9slice", "voxel3d", "autotile_pack", "rife_interp", "vfx_flipbook",
    "rpg_portrait", "sfx", "ip_adapter", "anim_loop", "pose_control", "tts_dialogue",
    "audio_ambience", "music_bg", "voix_off", "voix_robot", "chanson", "musique_adn",
    "musique_essence", "retrait_voix", "outfit", "video", "h3_ref2va", "monoplan_ia",
    "makehuman_clothes", "character_makeup", "asset_blendkit", "audio_upscale",
    "animal_godot",
]

_decouverts = sorted(
    m.name for m in pkgutil.iter_modules(__path__)
    if m.name not in _MODULES_ORDONNES and not m.name.startswith("_")
)
for _nom in _MODULES_ORDONNES + _decouverts:
    importlib.import_module(f"workflows.{_nom}")

# Exports nommés historiques : liste complète par construction (inclut les classes
# oubliées de l'ancien __all__, ex. AnimalGodotWorkflow).
__all__ = ["BaseWorkflow", "WorkflowRegistry"] + [
    cls.__name__ for cls in WorkflowRegistry._workflows.values()
]


def __getattr__(nom: str):
    """Résout les anciens imports `from workflows import XWorkflow` via le registre."""
    for cls in WorkflowRegistry._workflows.values():
        if cls.__name__ == nom:
            return cls
    raise AttributeError(f"module 'workflows' n'a pas d'attribut '{nom}'")
