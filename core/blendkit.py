#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Blendkit module: search and download of CC0 assets on blendkit.com
(3D models for Godot, scenes/sets for the channel's compositing plates).

Pipeline validated on 2026-09-15 (MEMORY_BANK §1.23):
  1. ANONYMOUS search via the public REST API (no key required);
  2. Authenticated download INSIDE Blender headless: the logged-in account key
     is read from the addon preferences (never outside the Blender process);
  3. `GET /api/v1/downloads/<file_id>/?scene_uuid=<uuid>` + Bearer -> signed URL
     downloadable without auth (browser User-Agent required by the CDN);
  4. prop mode: append + GLB export + Workbench control render;
     plate mode: open + Cycles GPU (HIP) / EEVEE render.

The addon's local daemon is UNUSABLE in headless (missing handshake) —
do not try to go through it.
"""

import json
import os
import urllib.parse
import urllib.request

from core.blender_ops import trouver_blender
from core.process import run_engine

BLENDERKIT_API = "https://www.blenderkit.com/api/v1"
MODULE_ADDON = "bl_ext.user_default.blenderkit"

# fileType -> readable label; the resolution_* variants contain the same .blend
# with reduced textures (the base "blend" file embeds the max quality).
RESOLUTIONS = ["blend", "resolution_8K", "resolution_4K", "resolution_2K", "resolution_1K", "resolution_0_5K"]


def _requete_json(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as reponse:
        return json.load(reponse)


def rechercher_assets(query: str, asset_type: str = "model", licence: str = "cc_zero", page_size: int = 20) -> list:
    """Anonymous search on the Blendkit API. Returns a simplified list of results."""
    q = f"{query} asset_type:{asset_type},author"
    if licence and licence != "any":
        q += f" license:{licence}"
    url = (
        f"{BLENDERKIT_API}/search/?query={urllib.parse.quote_plus(q)}"
        f"+order:-score&page_size={page_size}&dict_parameters=1"
    )
    brute = _requete_json(url).get("results", [])
    assets = []
    for r in brute:
        fichiers = {f["fileType"]: f["id"] for f in r.get("files", []) if f.get("id")}
        assets.append(
            {
                "nom": r.get("displayName", "?"),
                "licence": r.get("license", "?"),
                "gratuit": bool(r.get("isFree")),
                "categorie": r.get("category", "?"),
                "base_id": r.get("assetBaseId", ""),
                "description": (r.get("description") or "").strip().split("\n")[0][:120],
                "fichiers": fichiers,
            }
        )
    return assets


def choisir_fichier_blend(asset: dict, resolution: str = "2K") -> str:
    """Returns the file_id of the requested .blend (falling-back resolution if absent)."""
    fichiers = asset["fichiers"]
    if "blend" not in fichiers:
        raise ValueError(f"asset '{asset['nom']}' has no downloadable .blend file")
    resolution = (resolution or "blend").lower().replace("0.5k", "0_5k")
    if resolution in ("blend", "original", "max"):
        return fichiers["blend"]
    cle = f"resolution_{resolution.replace('k', 'K')}"
    # progressively falls back to a lower resolution if the variant is missing
    ordre = [c for c in RESOLUTIONS if c.startswith("resolution_") and c <= cle] if cle in RESOLUTIONS else []
    for candidat in [cle] + list(reversed(ordre)):
        if candidat in fichiers:
            return fichiers[candidat]
    return fichiers["blend"]


def afficher_assets(assets: list) -> None:
    """Displays the results list with their index usable for --index."""
    if not assets:
        print("❌ No result (try other keywords, or --bk-licence any).")
        return
    print(f"\n🔎 {len(assets)} result(s) — pick with --index N:")
    for i, a in enumerate(assets):
        flag = "" if a["gratuit"] else "  ⚠️ probably paid plan"
        resos = sorted(f.replace("resolution_", "") for f in a["fichiers"] if f.startswith("resolution_"))
        extra = f" | resolutions={','.join(resos)}" if resos else ""
        print(f"  [{i}] {a['nom'][:48]:50} | {a['licence']}{flag} | {a['categorie']}{extra}")
        if a["description"]:
            print(f"       {a['description']}")


def executer_job_blender(job: dict, dossier_job: str) -> dict:
    """Writes job.json, launches Blender headless with the worker, returns resultat.json."""
    blender = trouver_blender()
    if not blender:
        raise EnvironmentError("Blender not found (core/blender_ops.trouver_blender).")
    chemin_job = os.path.join(dossier_job, "job.json")
    with open(chemin_job, "w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False, indent=1)
    chemin_worker = os.path.join("scripts", "blendkit_blender_job.py")
    commande = [blender, "--background", "--python", chemin_worker, "--", chemin_job]
    processus = run_engine(commande, check=False, timeout=3600, etiquette="blender blendkit")
    for ligne in (processus.stdout or "").splitlines():
        if "[blendkit_workflow]" in ligne:
            print(ligne.strip())
    chemin_resultat = os.path.join(dossier_job, "resultat.json")
    if not os.path.isfile(chemin_resultat):
        extraits = [ligne.strip() for ligne in (processus.stderr or "").splitlines() if ligne.strip()][-6:]
        raise RuntimeError(f"the Blender worker did not produce a result (exit {processus.returncode}): {' | '.join(extraits)}")
    with open(chemin_resultat, "r", encoding="utf-8") as f:
        resultat = json.load(f)
    if not resultat.get("ok"):
        raise RuntimeError(f"Blender worker failed: {resultat.get('erreur', 'unknown reason')}")
    return resultat


def verifier_prerequis_blendkit() -> tuple:
    """Checks Blender; the API key is checked by the worker (Blender side only)."""
    manquants = []
    if not trouver_blender():
        manquants.append("Blender (blender.exe binary not found)")
    return len(manquants) == 0, manquants
