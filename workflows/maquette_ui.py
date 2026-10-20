#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
maquette_ui workflow: UI wireframe frame via FigCraft.

Builds a 1280x720 app-frame wireframe (header bar, two zones, labels) with
the headless FigCraft engine and exports a PNG - quick mockups for tool and
game UI discussions.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict

from core.config import DEFAULT_OUTPUT_DIR
from core.photocraft import ErreurPhotocraft, trouver_cli_craftapp
from workflows.base import BaseWorkflow, WorkflowRegistry


def _cli(nom: str, env: str) -> Path:
    try:
        return trouver_cli_craftapp(nom, env)
    except ErreurPhotocraft as e:
        raise ValueError(str(e)) from e


def _executer(commande: list, message_erreur: str, timeout: int = 300) -> None:
    r = subprocess.run(commande, capture_output=True, text=True, encoding="utf-8",
                       timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"{message_erreur}: {(r.stderr or r.stdout)[:300]}")




@WorkflowRegistry.register
class MaquetteUiWorkflow(BaseWorkflow):
    """UI wireframe PNG (FigCraft headless)."""

    name = "maquette_ui"
    description = "1280x720 UI wireframe (frame + zones + labels) exported as PNG via FigCraft headless"

    emoji = "🧭"
    PARAMETRES = [
        dict(flags=("--libelle",), default="Maquette", help="Wireframe header label"),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        libelle = params.get("libelle", "Maquette")
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)
        base = Path(output_dir) / f"maquette_{libelle[:16].strip().replace(' ', '_').lower()}"
        chemin_fig = base.with_suffix(".fig")
        chemin_png = base.with_suffix(".png")

        etapes = [
            {"command": "frame.create", "params": {"x": 0, "y": 0, "width": 1280, "height": 720,
                                              "name": libelle,
                                              "props": {"fills": ["#141821"]}}},
            {"command": "shape.rectangle", "params": {"x": 0, "y": 0, "width": 1280, "height": 72,
                                                 "props": {"fills": ["#1f2633"]}}},
            {"command": "text.create", "params": {"text": libelle, "x": 24, "y": 22,
                                             "props": {"fontSize": 28, "fills": ["#7fdcff"]}}},
            {"command": "shape.rectangle", "params": {"x": 24, "y": 104, "width": 760, "height": 560,
                                                 "props": {"fills": ["#232b3a"]}}},
            {"command": "text.create", "params": {"text": "Zone principale", "x": 48, "y": 128,
                                             "props": {"fontSize": 20, "fills": ["#aab4c4"]}}},
            {"command": "shape.rectangle", "params": {"x": 812, "y": 104, "width": 444, "height": 560,
                                                 "props": {"fills": ["#1b2230"]}}},
            {"command": "text.create", "params": {"text": "Panneau", "x": 836, "y": 128,
                                             "props": {"fontSize": 20, "fills": ["#aab4c4"]}}},
        ]
        script = base.with_suffix(".jsonl")
        script.write_text(chr(10).join(json.dumps(e, ensure_ascii=False) for e in etapes) + chr(10),
                          encoding="utf-8")
        _executer([str(_cli("figcraft", "FIGCRAFT_CLI")), "run", str(script),
                   "--out", str(chemin_fig)], "figcraft run failed")
        _executer([str(_cli("figcraft", "FIGCRAFT_CLI")), "export", str(chemin_fig),
                   "-o", str(chemin_png), "--scale", "1"], "figcraft export failed")
        if not chemin_png.exists():
            raise RuntimeError("figcraft produced no PNG")
        script.unlink(missing_ok=True)
        self.log(f"wireframe saved: {chemin_png} "
                 f"({chemin_png.stat().st_size / 1024:.0f} KB)", emoji="🎉")
        return {"output_file": str(chemin_png),
                "files": [str(chemin_png), str(chemin_fig)]}
