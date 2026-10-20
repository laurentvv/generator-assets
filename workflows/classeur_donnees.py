#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
classeur_donnees workflow: CSV/TSV/JSON to a real XLSX workbook via GridCraft.

Turns tabular exports (benchmarks, veille reports) into proper spreadsheets
through the headless GridCraft engine.
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
class ClasseurDonneesWorkflow(BaseWorkflow):
    """CSV/TSV/JSON to XLSX (GridCraft headless)."""

    name = "classeur_donnees"
    description = "CSV/TSV/JSON table to a real XLSX workbook via GridCraft headless"

    emoji = "📗"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        entree = params.get("image") or params.get("input")
        if not entree or not os.path.exists(entree):
            raise ValueError("The classeur_donnees workflow requires a valid input file (-i / --input).")
        if Path(entree).suffix.lower() not in {".csv", ".tsv", ".json"}:
            raise ValueError("classeur_donnees expects a .csv/.tsv/.json source")
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)
        chemin_xlsx = Path(output_dir) / f"{Path(entree).stem}.xlsx"

        self.log(f"converting {Path(entree).name} to XLSX")
        _executer([str(_cli("gridcraft", "GRIDCRAFT_CLI")), "convert", entree, str(chemin_xlsx)],
                  "gridcraft convert failed")
        if not chemin_xlsx.exists():
            raise RuntimeError("gridcraft produced no output")
        self.log(f"workbook saved: {chemin_xlsx} "
                 f"({chemin_xlsx.stat().st_size / 1024:.0f} KB)", emoji="🎉")
        return {"output_file": str(chemin_xlsx), "files": [str(chemin_xlsx)]}
