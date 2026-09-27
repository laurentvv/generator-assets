#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Asset Blendkit workflow: CC0 asset from blendkit.com -> Godot prop (.glb) or
scenery plate for the YouTube channel (Blender headless render).

Two modes VALIDATED by the user on 2026-09-15 (MEMORY_BANK §1.23):
  - "prop"  : search -> download (connected Blendkit account, key read
    in Blender) -> append -> GLB export + Workbench control render;
  - "plate" : scene search -> download -> Cycles GPU render (HIP)
    with the scene camera (AgX + exposure to reproduce the official look).

Search is anonymous; only the download requires the connected account
in the Blender GUI (key never logged, see core/blendkit.py).
"""

import os
from typing import Any, Dict

from core.blendkit import (
    afficher_assets,
    choisir_fichier_blend,
    executer_job_blender,
    rechercher_assets,
    verifier_prerequis_blendkit,
)
from core.config import slugifier_texte
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class AssetBlendkitWorkflow(BaseWorkflow):
    """Blendkit CC0 search -> Godot .glb prop (prop mode) or rendered scenery plate (plate mode)."""

    name = "asset_blendkit"
    description = ("CC0 asset blendkit.com: Godot-ready .glb prop (prop mode) or scenery plate "
                   "rendered Blender Cycles GPU for the channel (plate mode) — Blendkit account required")

    emoji = "🧰"

    # CLI declarations (audit §2.2, migration from the flat table of cli/parser.py:
    # help/defaults taken as-is, unchanged surface). --mode stays in the flat
    # table (dest also read by upscale and video, cross-family).
    PARAMETRES = [
        dict(flags=("--query",),
             help="Blendkit search keywords (asset_blendkit workflow) — e.g.: 'wooden barrel'."),
        dict(flags=("--asset-type",), dest="asset_type", choices=["model", "scene", "material"], default="model",
             help="Blendkit asset type for asset_blendkit (default: model; plate mode uses scene)."),
        dict(flags=("--licence",), choices=["cc_zero", "any"], default="cc_zero",
             help="Blendkit licence filter (default: cc_zero — recommended for game + monetization)."),
        dict(flags=("--index",), type=int, default=0,
             help="Index of the Blendkit result to download (see --list-assets; default: 0)."),
        dict(flags=("--list-assets",), dest="list_assets", action="store_true",
             help="asset_blendkit: shows the search results then stops."),
        dict(flags=("--resolution",), choices=["blend", "8K", "4K", "2K", "1K", "0.5K"], default="2K",
             help="asset_blendkit prop mode: texture variant of the .blend (default: 2K, light for the game; blend = max quality)."),
        dict(flags=("--engine",), choices=["cycles", "eevee"], default="cycles",
             help="asset_blendkit plate mode: render engine (default: cycles, GPU HIP — EEVEE chokes on some scenes, MEMORY_BANK 1.23)."),
        dict(flags=("--camera",), default=None,
             help="asset_blendkit plate mode: name of the scene camera to use (default: scene camera)."),
        dict(flags=("--exposure",), type=float, default=-1.0,
             help="asset_blendkit plate mode: render exposure (default: -1.0, official look of the neon scenes)."),
        dict(flags=("--percentage",), type=int, default=100,
             help="asset_blendkit plate mode: Blender resolution percentage (default: 100; scene files sometimes force 300 = 6K, keep it under control)."),
        dict(flags=("--no-cache",), dest="no_cache", action="store_true",
             help="asset_blendkit: forces re-downloading the .blend (default: local cache)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        query = params.get("query")
        if not query:
            raise ValueError("Provide --query \"<keywords>\" (e.g.: --query \"wooden barrel\").")

        ok, manquants = verifier_prerequis_blendkit()
        if not ok:
            raise EnvironmentError("Missing prerequisites: " + " ; ".join(manquants))

        mode = (params.get("mode") or "prop").lower()
        if mode not in ("prop", "plate"):
            raise ValueError(f"Invalid mode '{mode}' (prop or plate).")
        asset_type = "scene" if mode == "plate" else (params.get("asset_type") or "model").lower()

        self.log(f"Blendkit search: \"{query}\" (type={asset_type}, licence={params.get('licence') or 'cc_zero'})…", "🔎")
        assets = rechercher_assets(query, asset_type=asset_type, licence=params.get("licence") or "cc_zero")
        afficher_assets(assets)

        if params.get("list_assets"):
            return {"ok": True, "mode": "liste", "resultats": [a["nom"] for a in assets]}

        index = int(params.get("index") or 0)
        if not assets or index >= len(assets):
            raise ValueError(f"--index {index} out of bounds ({len(assets)} results).")
        asset = assets[index]
        if "blend" not in asset["fichiers"]:
            raise ValueError(f"the asset \"{asset['nom']}\" has no downloadable .blend file.")
        if not asset["gratuit"]:
            self.log("⚠️ this asset seems reserved for a paid plan — the download may fail.", "⚠️")

        # ABSOLUTE paths mandatory: read_factory_settings/open_mainfile on the
        # worker side reset Blender's current directory.
        dossier = os.path.abspath(os.path.join("output", "blendkit", slugifier_texte(asset["nom"])[:50]))
        os.makedirs(dossier, exist_ok=True)
        nom_base = slugifier_texte(asset["nom"])[:40]

        job: Dict[str, Any] = {
            "mode": mode,
            "addon_module": "bl_ext.user_default.blenderkit",
            "download": {
                "file_id": asset["fichiers"]["blend"] if mode == "plate" else choisir_fichier_blend(
                    asset, params.get("resolution") or "2K"
                ),
                "cache": os.path.join(dossier, "source.blend"),
                "no_cache": bool(params.get("no_cache")),
            },
        }

        if mode == "prop":
            job["prop"] = {
                "glb": os.path.join(dossier, f"{nom_base}.glb"),
                "apercu": os.path.join(dossier, "apercu.png"),
            }
            self.log(f"download + GLB conversion of \"{asset['nom']}\" (resolution {params.get('resolution') or '2K'})…", "🧱")
        else:
            job["plate"] = {
                "png": os.path.join(dossier, "plaque.png"),
                "width": int(params.get("width") or 1920),
                "height": int(params.get("height") or 1080),
                "percentage": int(params.get("percentage") or 100),
                "engine": (params.get("engine") or "cycles").lower(),
                "samples": int(params.get("samples") or 48),
                "camera": params.get("camera"),
                "exposure": float(params.get("exposure") if params.get("exposure") is not None else -1.0),
                "view_transform": params.get("view_transform") or "AgX",
            }
            self.log(f"download + {job['plate']['engine']} render of the scene \"{asset['nom']}\"…", "🎬")

        resultat = executer_job_blender(job, dossier)

        self.log("DONE ✅", "🏁")
        if mode == "prop":
            self.log(f"Godot GLB: {resultat['glb']} ({resultat['glb_mo']} MB, {resultat['faces']} faces)", "📦")
            self.log(f"control preview: {resultat['apercu']}", "🖼️")
        else:
            self.log(f"plate {resultat['resolution']} ({resultat['engine']}, {resultat['png_mo']} MB): {resultat['png']}", "🖼️")
        return resultat
