"""
Registration of the 2D & 3D workflows.

Each module `workflows/<name>.py` declares its class(es) via
`@WorkflowRegistry.register`. Imports are driven by the ordered list
`_MODULES_ORDONNES`: it sets the order of the interactive menu and of
`--list-workflows`. Any new unlisted module is discovered automatically
(pkgutil) and registered at the end of the list — a workflow can no longer
be missing from the registry due to a forgotten import.
"""

import importlib
import pkgutil

from workflows.base import BaseWorkflow, WorkflowRegistry

_MODULES_ORDONNES = [
    "generate", "upscale", "spritesheet", "variations", "tileable", "pixelart",
    "batch", "material3d", "skybox", "turnaround3d", "mesh3d", "mesh_ia", "rembg",
    "flowmap", "ui_9slice", "voxel3d", "autotile_pack", "rife_interp", "vfx_flipbook",
    "rpg_portrait", "sfx", "ip_adapter", "anim_loop", "pose_control", "tts_dialogue",
    "audio_ambience", "music_bg", "voix_off", "voix_robot", "voix_perso", "chanson", "musique_adn",
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

# Historical named exports: complete list by construction (includes classes
# forgotten from the old __all__, e.g. AnimalGodotWorkflow).
__all__ = ["BaseWorkflow", "WorkflowRegistry"] + [
    cls.__name__ for cls in WorkflowRegistry._workflows.values()
]


def __getattr__(nom: str):
    """Resolves the legacy `from workflows import XWorkflow` imports via the registry."""
    for cls in WorkflowRegistry._workflows.values():
        if cls.__name__ == nom:
            return cls
    raise AttributeError(f"module 'workflows' has no attribute '{nom}'")
