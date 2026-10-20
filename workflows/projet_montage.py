#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
projet_montage workflow: rough-cut bin via FilmCraft.

Creates a FilmCraft project, imports the given media files (or a whole
directory) into its bin and saves it - the editor opens a ready project
instead of a blank one.
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
class ProjetMontageWorkflow(BaseWorkflow):
    """Rough-cut media bin (FilmCraft headless)."""

    name = "projet_montage"
    description = "FilmCraft project with the given media imported (rough-cut bin), saved headless"

    emoji = "🎬"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        entree = params.get("image") or params.get("input")
        if not entree or not os.path.exists(entree):
            raise ValueError("The projet_montage workflow requires media file(s) or a directory (-i / --input).")
        chemin_entree = Path(entree)
        media = ([str(p) for p in sorted(chemin_entree.iterdir())
                  if p.suffix.lower() in {".mp4", ".mov", ".webm", ".mkv", ".png", ".jpg", ".wav", ".mp3"}]
                 if chemin_entree.is_dir() else [str(chemin_entree)])
        if not media:
            raise ValueError(f"no media file found in {chemin_entree}")
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)
        chemin_projet = Path(output_dir) / f"{chemin_entree.stem if chemin_entree.is_dir() else chemin_entree.stem}_montage.fcproj"

        script = Path(output_dir) / f"{chemin_projet.stem}.jsonl"
        lignes_script = [
            {"id": "file.newProject", "params": {}},
            {"id": "file.import", "params": {"paths": media}},
            {"id": "file.saveAs", "params": {"path": str(chemin_projet)}},
        ]
        script.write_text(chr(10).join(json.dumps(e) for e in lignes_script) + chr(10),
                          encoding="utf-8")
        self.log(f"building project bin with {len(media)} media item(s)")
        _executer([str(_cli("filmcraft", "FILMCRAFT_CLI")), "run", str(script)],
                  "filmcraft run failed", timeout=900)
        if not chemin_projet.exists():
            raise RuntimeError("filmcraft produced no project file")
        self.log(f"project saved: {chemin_projet} "
                 f"({chemin_projet.stat().st_size / 1024:.0f} KB)", emoji="🎉")
        return {"output_file": str(chemin_projet), "files": [str(chemin_projet)]}
