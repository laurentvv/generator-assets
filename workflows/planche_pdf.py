#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
planche_pdf workflow: A4 proof sheet via DesignCraft.

Lays one image on an A4 page (fit, margins kept) and exports a print-ready
PDF through the headless DesignCraft engine - quick proof sheets for
keyframes and textures.
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
class PlanchePdfWorkflow(BaseWorkflow):
    """A4 proof sheet around one image (DesignCraft headless)."""

    name = "planche_pdf"
    description = "A4 PDF proof sheet laying out one image via DesignCraft headless"

    emoji = "📃"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        entree = params.get("image") or params.get("input")
        if not entree or not os.path.exists(entree):
            raise ValueError("The planche_pdf workflow requires a valid image (-i / --input).")
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)
        chemin_pdf = Path(output_dir) / f"{Path(entree).stem}_planche.pdf"

        commande = [str(_cli("designcraft", "DESIGNCRAFT_CLI")), "run",
                    "--cmd", "file.new=" + json.dumps({"preset": "A4"}),
                    "--cmd", "file.place=" + json.dumps({"path": str(Path(entree).resolve()),
                                                         "x": 60, "y": 60, "width": 475}),
                    "--cmd", "file.exportPdf=" + json.dumps({"path": str(chemin_pdf)})]
        self.log(f"laying {Path(entree).name} on A4")
        _executer(commande, "designcraft run failed", timeout=600)
        if not chemin_pdf.exists():
            raise RuntimeError("designcraft produced no PDF")
        self.log(f"proof sheet saved: {chemin_pdf} "
                 f"({chemin_pdf.stat().st_size / 1024:.0f} KB)", emoji="🎉")
        return {"output_file": str(chemin_pdf), "files": [str(chemin_pdf)]}
