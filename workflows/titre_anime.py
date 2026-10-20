#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
titre_anime workflow: motion-design title frame via EffectCraft.

Builds a 1920x1080 composition (background solid + centered text layer)
with the headless EffectCraft engine and renders one PNG frame - ready as
a title card or an overlay basis for the video factory.
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
class TitreAnimeWorkflow(BaseWorkflow):
    """Motion-design title frame (EffectCraft headless)."""

    name = "titre_anime"
    description = "1920x1080 title composition (bg + text) rendered as PNG via EffectCraft headless"

    emoji = "✨"
    PARAMETRES = [
        dict(flags=("--texte",), default="GENERATOR-ASSETS", help="Title text"),
        dict(flags=("--teinte",), default="#7fdcff", help="Text color (#hex)"),
        dict(flags=("--taille-texte",), type=int, default=120, help="Font size"),
        dict(flags=("--couleur-fond-ecran",), default="#10131c", help="Background color"),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        texte = params.get("texte", "GENERATOR-ASSETS")
        teinte = params.get("teinte", "#7fdcff")
        taille = int(params.get("taille_texte", 120))
        fond = params.get("couleur_fond_ecran", "#10131c")
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)
        base = Path(output_dir) / f"titre_{texte[:16].strip().replace(' ', '_').lower()}"
        chemin_png = base.with_suffix(".png")

        # EffectCraft keeps ONE session per MCP server process (unlike the
        # per-invocation `run` subcommand): the comp must still exist when
        # render_frame runs, so everything goes through the same stdio server.
        etapes = [
            {"id": "comp.new", "params": {"name": "titre", "width": 1920, "height": 1080,
                                          "frameRate": 30, "duration": 4.0,
                                          "background": fond, "open": True}},
            {"id": "layer.newText", "params": {"text": texte, "position": [960, 540],
                                               "size": taille, "fill": teinte,
                                               "justify": "center"}},
        ]
        proc = subprocess.Popen(
            [str(_cli("effectcraft", "EFFECTCRAFT_CLI")), "mcp"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8")

        def appel(identifiant: int, methode: str, arguments: dict) -> dict:
            proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": identifiant,
                                         "method": methode, "params": arguments}) + "\n")
            proc.stdin.flush()
            ligne = proc.stdout.readline()
            if not ligne.strip():
                raise RuntimeError(f"effectcraft MCP closed on {methode}: "
                                   f"{proc.stderr.read()[:200]}")
            return json.loads(ligne)

        try:
            appel(1, "initialize",
                  {"protocolVersion": "2024-11-05", "capabilities": {},
                   "clientInfo": {"name": "generator-assets", "version": "1.0"}})
            proc.stdin.write(json.dumps({"jsonrpc": "2.0",
                                         "method": "notifications/initialized"}) + "\n")
            proc.stdin.flush()
            r_batch = appel(2, "tools/call",
                            {"name": "command_batch", "arguments": {"steps": etapes}})
            r_render = appel(3, "tools/call",
                             {"name": "render_frame",
                              "arguments": {"comp": "titre", "path": str(chemin_png),
                                            "max_side": 1920, "inline": False}})
            for nom, r in (("command_batch", r_batch), ("render_frame", r_render)):
                if r.get("result", {}).get("isError") is not True:
                    continue
                contenu = r["result"].get("content", [])
                raise RuntimeError(f"effectcraft {nom}: "
                                   f"{contenu[0].get('text', '')[:250] if contenu else r}")
        finally:
            proc.stdin.close()
            proc.wait(timeout=30)
        if not chemin_png.exists():
            raise RuntimeError("effectcraft produced no PNG")
        self.log(f"title frame saved: {chemin_png} "
                 f"({chemin_png.stat().st_size / 1024:.0f} KB)", emoji="🎉")
        return {"output_file": str(chemin_png), "files": [str(chemin_png)]}
