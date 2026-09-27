#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Animal Game-Ready workflow: packed animal .blend (rigged, e.g. Quaternius CC0)
→ Godot GLB with AN_* clips (recipe VALIDATED by the user on 2026-09-18:
native gallop "perfect", MEMORY_BANK §1.28).

The quality comes from the pack's NATIVE animations (mocap) — do not attempt a
retarget to another rig without an explicit need (tried, not retained).
"""

import os
from typing import Any, Dict

from core.animal_godot import exporter_animal_godot
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class AnimalGodotWorkflow(BaseWorkflow):
    """Packed animal → Godot game-ready GLB (AN_* clips, verified)."""

    name = "animal_godot"
    description = ("Rigged packed animal (.blend) → Godot game-ready GLB: junk "
                   "purge, clips renamed AN_* (1 per native action), "
                   "verified by re-import (recipe validated 2026-09-18)")

    emoji = "🐺"

    # CLI declarations (audit §2.2, migration from the flat table of cli/parser.py:
    # help/defaults taken as-is, unchanged surface).
    PARAMETRES = [
        dict(flags=("--animal-prefixe",), dest="animal_prefixe", default="AN_",
             help="Animation clip prefix for animal_godot (default: AN_)."),
        dict(flags=("--animal-actions",), dest="animal_actions", nargs="*", default=None,
             help="Native actions to keep for animal_godot (default: all)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        source = params.get("input")
        if not source or not os.path.exists(source):
            raise ValueError(
                f"Rigged animal .blend not found: {source} — pass a .blend "
                f"containing armature + skinned mesh (e.g. Quaternius pack) via -i."
            )

        sortie = params.get("output") or os.path.splitext(source)[0] + "_godot.glb"
        prefixe = params.get("animal_prefixe") or "AN_"
        actions = params.get("animal_actions") or None

        self.log(f"Game-ready export: {os.path.basename(source)} → {os.path.basename(sortie)}")
        rapport = exporter_animal_godot(
            source, sortie, prefixe=prefixe, actions_filtre=actions,
        )

        self.log(f"GLB verified: {rapport['os']} bones, {len(rapport['clips'])} clips, "
                 f"{rapport['meshes']} meshes", "✅")
        self.log("Clips : " + ", ".join(rapport["clips"]), "🎬")
        return rapport
