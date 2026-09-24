#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Animal Game-Ready : blend d'animal packé (riggé, ex. Quaternius CC0)
→ GLB Godot avec clips AN_* (recette VALIDÉE utilisateur le 2026-09-18 :
gallop natif « parfait », MEMORY_BANK §1.28).

La qualité vient des animations NATIVES du pack (mocap) — ne pas tenter un
retarget vers un autre rig sans besoin explicite (tenté, non retenu).
"""

import os
from typing import Any, Dict

from core.animal_godot import exporter_animal_godot
from core.config import slugifier_texte
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class AnimalGodotWorkflow(BaseWorkflow):
    """Animal packé → GLB Godot game-ready (clips AN_*, vérifié)."""

    name = "animal_godot"
    description = ("Animal packé riggé (.blend) → GLB Godot game-ready : purge "
                   "parasites, clips renommés AN_* (1 par action native), "
                   "vérifié par ré-import (recette validée 2026-09-18)")

    emoji = "🐺"
    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        source = params.get("input")
        if not source or not os.path.exists(source):
            raise ValueError(
                f"Blend d'animal riggé introuvable : {source} — passer un .blend "
                f"contenant armature + mesh skinné (ex. pack Quaternius) via -i."
            )

        sortie = params.get("output") or os.path.splitext(source)[0] + "_godot.glb"
        prefixe = params.get("animal_prefixe") or "AN_"
        actions = params.get("animal_actions") or None

        self.log(f"Export game-ready : {os.path.basename(source)} → {os.path.basename(sortie)}")
        rapport = exporter_animal_godot(
            source, sortie, prefixe=prefixe, actions_filtre=actions,
        )

        self.log(f"GLB vérifié : {rapport['os']} os, {len(rapport['clips'])} clips, "
                 f"{rapport['meshes']} meshes", "✅")
        self.log("Clips : " + ", ".join(rapport["clips"]), "🎬")
        return rapport
