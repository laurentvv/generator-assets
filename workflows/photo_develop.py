#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
photo_develop workflow: one-command RAW/JPEG development via LightCraft.

Imports a photo into the headless LightCraft developer, optionally sets the
exposure, runs auto develop and exports a finished JPEG at the requested
long edge.
"""

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
class PhotoDevelopWorkflow(BaseWorkflow):
    """Photo auto-develop + export (LightCraft headless)."""

    name = "photo_develop"
    description = "Photo development via LightCraft headless: import, auto develop, JPEG export"

    emoji = "🏞️"
    PARAMETRES = [
        dict(flags=("--exposition",), type=float, default=None,
             help="Exposure adjustment in EV before the auto pass"),
        dict(flags=("--long-cote",), type=int, default=1600,
             help="Exported long edge in px"),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        entree = params.get("image") or params.get("input")
        if not entree or not os.path.exists(entree):
            raise ValueError("The photo_develop workflow requires a valid image (-i / --input).")
        exposition = params.get("exposition")
        long_cote = int(params.get("long_cote", 1600))
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)
        chemin_sortie = Path(output_dir) / f"{Path(entree).stem}_developpe.jpg"

        commande = [str(_cli("lightcraft", "LIGHTCRAFT_CLI")), "run",
                    "--import", entree]
        if exposition is not None:
            commande += ["develop.set", f"control=light.exposure value={float(exposition)}"]
        commande += ["develop.auto",
                     "app.export", f"path={chemin_sortie}", f"longEdge={long_cote}"]
        self.log(f"developing {Path(entree).name}"
                 f"{f' (exposure {exposition:+.1f} EV)' if exposition is not None else ''}")
        _executer(commande, "lightcraft run failed", timeout=900)
        if not chemin_sortie.exists():
            raise RuntimeError("lightcraft produced no output")
        self.log(f"photo saved: {chemin_sortie} "
                 f"({chemin_sortie.stat().st_size / 1024:.0f} KB)", emoji="🎉")
        return {"output_file": str(chemin_sortie), "files": [str(chemin_sortie)]}
