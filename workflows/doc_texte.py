#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
doc_texte workflow: text/Markdown file to a formatted PDF via WordCraft.

Converts a .md/.txt/.html source into a paginated, styled PDF document
through the headless WordCraft engine (scripts, show notes, dossiers).
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
class DocTexteWorkflow(BaseWorkflow):
    """Text/Markdown to PDF (WordCraft headless)."""

    name = "doc_texte"
    description = "Text/Markdown/HTML to a formatted PDF via WordCraft headless"

    emoji = "📝"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        entree = params.get("image") or params.get("input")
        if not entree or not os.path.exists(entree):
            raise ValueError("The doc_texte workflow requires a valid input file (-i / --input).")
        if Path(entree).suffix.lower() not in {".md", ".txt", ".html", ".tex", ".rtf"}:
            raise ValueError("doc_texte expects a .md/.txt/.html/.tex/.rtf source")
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)
        chemin_pdf = Path(output_dir) / f"{Path(entree).stem}_wordcraft.pdf"

        self.log(f"converting {Path(entree).name} to PDF")
        _executer([str(_cli("wordcraft", "WORDCRAFT_CLI")), "convert", entree, str(chemin_pdf)],
                  "wordcraft convert failed")
        if not chemin_pdf.exists():
            raise RuntimeError("wordcraft produced no output")
        self.log(f"document saved: {chemin_pdf} "
                 f"({chemin_pdf.stat().st_size / 1024:.0f} KB)", emoji="🎉")
        return {"output_file": str(chemin_pdf), "files": [str(chemin_pdf)]}
