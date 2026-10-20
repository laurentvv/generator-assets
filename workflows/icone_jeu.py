#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
icone_jeu workflow: vector game icon via VectorCraft.

Builds a flat-design icon (background + centered geometric shape) with the
headless VectorCraft engine and exports it as **SVG** (crisp at any Godot
UI scale) plus a PNG rasterized at the requested size. Pure vector output,
no AI pass - for AI-generated icons keep the image workflows.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict

from core.config import DEFAULT_OUTPUT_DIR
from core.photocraft import ErreurPhotocraft, trouver_cli_craftapp
from workflows.base import BaseWorkflow, WorkflowRegistry


def _parametres_forme(forme: str, taille: int) -> tuple[str, Dict[str, Any]]:
    """Command id + params drawing the centered icon shape on a `taille` box."""
    fraction = 0.58
    cote = int(taille * fraction)
    centre = taille / 2
    if forme == "cercle":
        return "shape.ellipse", {"x": centre - cote / 2, "y": centre - cote / 2,
                                 "width": cote, "height": cote}
    if forme == "carre":
        return "shape.rectangle", {"x": centre - cote / 2, "y": centre - cote / 2,
                                   "width": cote, "height": cote,
                                   "radius": int(cote * 0.18)}
    if forme == "hexagone":
        return "shape.polygon", {"cx": centre, "cy": centre,
                                 "radius": cote / 2, "sides": 6}
    if forme == "etoile":
        return "shape.star", {"cx": centre, "cy": centre,
                              "radius1": cote / 2, "radius2": cote / 4, "points": 5}
    raise ValueError(f"unknown shape '{forme}' (cercle, carre, hexagone, etoile)")


@WorkflowRegistry.register
class IconeJeuWorkflow(BaseWorkflow):
    """Vector game icon (SVG + PNG) via the headless VectorCraft engine."""

    name = "icone_jeu"
    description = (
        "Vector game icon via VectorCraft headless: background + centered shape "
        "(cercle, carre, hexagone, etoile), exports SVG and PNG"
    )

    emoji = "🎮"
    PARAMETRES = [
        dict(flags=("--forme",), default="hexagone",
             choices=["cercle", "carre", "hexagone", "etoile"], help="Icon shape"),
        dict(flags=("--couleur-fond",), default="#1a1f2e", help="Background color"),
        dict(flags=("--couleur-forme",), default="#7fdcff", help="Shape color"),
        dict(flags=("--taille",), type=int, default=256,
             help="Icon size in px (artboard + PNG export)"),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        forme = params.get("forme", "hexagone")
        taille = int(params.get("taille", 256))
        couleur_fond = params.get("couleur_fond", "#1a1f2e")
        couleur_forme = params.get("couleur_forme", "#7fdcff")
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)

        try:
            cli = trouver_cli_craftapp("vectorcraft", "VECTORCRAFT_CLI")
        except ErreurPhotocraft as e:
            raise ValueError(str(e)) from e

        base_sortie = Path(output_dir) / f"icone_{forme}_{taille}"
        svg = base_sortie.with_suffix(".svg")
        png = base_sortie.with_suffix(".png")

        cmd_forme, params_forme = _parametres_forme(forme, taille)
        # --scale applies to raster exports (SVG is resolution-free); 1 px per
        # unit keeps the PNG at exactly `taille`.
        commande = [
            str(cli), "run",
            "--cmd", "artboard.new",
            "--params", json.dumps({"x": 0, "y": 0, "width": taille, "height": taille,
                                    "name": f"icone_{forme}"}),
            "--cmd", "shape.rectangle",
            "--params", json.dumps({"x": 0, "y": 0, "width": taille, "height": taille}),
            "--cmd", "paint.setFill", "--params", json.dumps({"color": couleur_fond}),
            "--cmd", cmd_forme, "--params", json.dumps(params_forme),
            "--cmd", "paint.setFill", "--params", json.dumps({"color": couleur_forme}),
            "--export", str(svg),
            "--export", str(png), "--scale", "1",
        ]
        self.log(f"drawing {forme} icon ({taille}px, {couleur_forme} on {couleur_fond})")
        r = subprocess.run(commande, capture_output=True, text=True,
                           encoding="utf-8", timeout=180)
        if r.returncode != 0 or not (svg.exists() and png.exists()):
            raise RuntimeError(f"vectorcraft run failed: {(r.stderr or r.stdout)[:300]}")

        self.log(f"icon saved: {svg.name} + {png.name}", emoji="🎉")
        return {"output_file": str(svg), "files": [str(svg), str(png)]}
