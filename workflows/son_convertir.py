#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
son_convertir workflow: audio conversion + normalize via SoundCraft.

Resamples / converts any audio file (WAV, FLAC, MP3...) with optional
normalization and bit-depth control through the headless SoundCraft engine -
handy to conform TTS beds and music loops before an AMF mux.
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
class SonConvertirWorkflow(BaseWorkflow):
    """Audio convert/normalize (SoundCraft headless)."""

    name = "son_convertir"
    description = "Audio conversion + optional normalize/resample via SoundCraft headless"

    emoji = "🔊"
    PARAMETRES = [
        dict(flags=("--normaliser",), action="store_true", help="Normalize peak level"),
        dict(flags=("--profondeur-bits",), default=None, choices=["16", "24", "32f"],
             help="Output bit depth"),
        dict(flags=("--frequence",), type=int, default=None, help="Sample rate in Hz (e.g. 48000)"),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        entree = params.get("image") or params.get("input")
        if not entree or not os.path.exists(entree):
            raise ValueError("The son_convertir workflow requires a valid audio file (-i / --input).")
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)
        chemin_sortie = Path(output_dir) / f"{Path(entree).stem}_conforme.wav"

        commande = [str(_cli("soundcraft", "SOUNDCRAFT_CLI")), "convert", entree, str(chemin_sortie)]
        if params.get("normaliser"):
            commande.append("--normalize")
        if params.get("profondeur_bits"):
            commande += ["--bit-depth", str(params["profondeur_bits"])]
        if params.get("frequence"):
            commande += ["--rate", str(int(params["frequence"]))]
        self.log(f"converting {Path(entree).name} -> WAV"
                 f"{' +normalize' if params.get('normaliser') else ''}")
        _executer(commande, "soundcraft convert failed", timeout=900)
        if not chemin_sortie.exists():
            raise RuntimeError("soundcraft produced no output")
        self.log(f"audio saved: {chemin_sortie} "
                 f"({chemin_sortie.stat().st_size / 1024:.0f} KB)", emoji="🎉")
        return {"output_file": str(chemin_sortie), "files": [str(chemin_sortie)]}
