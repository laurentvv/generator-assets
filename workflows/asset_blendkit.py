#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Asset Blendkit : asset CC0 de blendkit.com -> prop Godot (.glb) ou
plaque de décor pour la chaîne YouTube (rendu Blender headless).

Deux modes VALIDÉS par l'utilisateur le 2026-09-15 (MEMORY_BANK §1.23) :
  - « prop »  : recherche -> téléchargement (compte Blendkit connecté, clé lue
    dans Blender) -> append -> export GLB + rendu de contrôle Workbench ;
  - « plate » : recherche de scène -> téléchargement -> rendu Cycles GPU (HIP)
    avec la caméra de la scène (AgX + exposure pour reproduire le look officiel).

La recherche est anonyme ; seul le téléchargement requiert le compte connecté
dans le GUI Blender (clé jamais logguée, cf. core/blendkit.py).
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
    """Recherche Blendkit CC0 -> prop .glb Godot (mode prop) ou plaque décor rendue (mode plate)."""

    name = "asset_blendkit"
    description = ("Asset CC0 blendkit.com : prop .glb prêt Godot (mode prop) ou plaque de décor "
                   "rendue Blender Cycles GPU pour la chaîne (mode plate) — compte Blendkit requis")

    emoji = "🧰"
    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        query = params.get("query")
        if not query:
            raise ValueError("Fournir --query \"<mots-clés>\" (ex: --query \"wooden barrel\").")

        ok, manquants = verifier_prerequis_blendkit()
        if not ok:
            raise EnvironmentError("Prérequis manquants : " + " ; ".join(manquants))

        mode = (params.get("mode") or "prop").lower()
        if mode not in ("prop", "plate"):
            raise ValueError(f"Mode '{mode}' invalide (prop ou plate).")
        asset_type = "scene" if mode == "plate" else (params.get("asset_type") or "model").lower()

        self.log(f"recherche Blendkit : « {query} » (type={asset_type}, licence={params.get('licence') or 'cc_zero'})…", "🔎")
        assets = rechercher_assets(query, asset_type=asset_type, licence=params.get("licence") or "cc_zero")
        afficher_assets(assets)

        if params.get("list_assets"):
            return {"ok": True, "mode": "liste", "resultats": [a["nom"] for a in assets]}

        index = int(params.get("index") or 0)
        if not assets or index >= len(assets):
            raise ValueError(f"--index {index} hors limites ({len(assets)} résultats).")
        asset = assets[index]
        if "blend" not in asset["fichiers"]:
            raise ValueError(f"l'asset « {asset['nom']} » n'a pas de fichier .blend téléchargeable.")
        if not asset["gratuit"]:
            self.log("⚠️ cet asset semble réservé à un plan payant — le téléchargement risque d'échouer.", "⚠️")

        # Chemins ABSOLUS obligatoires : read_factory_settings/open_mainfile côté
        # worker réinitialisent le répertoire courant de Blender.
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
            self.log(f"téléchargement + conversion GLB de « {asset['nom']} » (résolution {params.get('resolution') or '2K'})…", "🧱")
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
            self.log(f"téléchargement + rendu {job['plate']['engine']} de la scène « {asset['nom']} »…", "🎬")

        resultat = executer_job_blender(job, dossier)

        self.log("TERMINÉ ✅", "🏁")
        if mode == "prop":
            self.log(f"GLB Godot : {resultat['glb']} ({resultat['glb_mo']} Mo, {resultat['faces']} faces)", "📦")
            self.log(f"aperçu de contrôle : {resultat['apercu']}", "🖼️")
        else:
            self.log(f"plaque {resultat['resolution']} ({resultat['engine']}, {resultat['png_mo']} Mo) : {resultat['png']}", "🖼️")
        return resultat
