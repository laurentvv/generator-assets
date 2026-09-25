#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module Blendkit : recherche et téléchargement d'assets CC0 sur blendkit.com
(modèles 3D pour Godot, scènes/décors pour plaques de compositing de la chaîne).

Pipeline validé le 2026-09-15 (MEMORY_BANK §1.23) :
  1. Recherche ANONYME via l'API REST publique (pas de clé requise) ;
  2. Téléchargement authentifié DANS Blender headless : la clé du compte connecté
     est lue depuis les préférences de l'addon (jamais hors du processus Blender) ;
  3. `GET /api/v1/downloads/<file_id>/?scene_uuid=<uuid>` + Bearer -> URL signée
     téléchargeable sans auth (User-Agent navigateur exigé par le CDN) ;
  4. mode prop : append + export GLB + rendu de contrôle Workbench ;
     mode plate : ouverture + rendu Cycles GPU (HIP) / EEVEE.

Le daemon local de l'addon est INUTILISABLE en headless (handshake absent) —
ne pas tenter de passer par lui.
"""

import json
import os
import urllib.parse
import urllib.request

from core.config import slugifier_texte
from core.blender_ops import trouver_blender
from core.process import run_engine

BLENDERKIT_API = "https://www.blenderkit.com/api/v1"
MODULE_ADDON = "bl_ext.user_default.blenderkit"

# fileType -> label lisible ; les variantes resolution_* contiennent le même .blend
# avec des textures réduites (le fichier « blend » de base embarque la qualité max).
RESOLUTIONS = ["blend", "resolution_8K", "resolution_4K", "resolution_2K", "resolution_1K", "resolution_0_5K"]


def _requete_json(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as reponse:
        return json.load(reponse)


def rechercher_assets(query: str, asset_type: str = "model", licence: str = "cc_zero", page_size: int = 20) -> list:
    """Recherche anonyme sur l'API Blendkit. Retourne une liste simplifiée de résultats."""
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
    """Retourne le file_id du .blend demandé (résolution retombante si absente)."""
    fichiers = asset["fichiers"]
    if "blend" not in fichiers:
        raise ValueError(f"l'asset « {asset['nom']} » n'a pas de fichier .blend téléchargeable")
    resolution = (resolution or "blend").lower().replace("0.5k", "0_5k")
    if resolution in ("blend", "original", "max"):
        return fichiers["blend"]
    cle = f"resolution_{resolution.replace('k', 'K')}"
    # retombe progressivement vers une résolution inférieure si la variante manque
    ordre = [c for c in RESOLUTIONS if c.startswith("resolution_") and c <= cle] if cle in RESOLUTIONS else []
    for candidat in [cle] + list(reversed(ordre)):
        if candidat in fichiers:
            return fichiers[candidat]
    return fichiers["blend"]


def afficher_assets(assets: list) -> None:
    """Affiche la liste des résultats avec leur index utilisable pour --index."""
    if not assets:
        print("❌ Aucun résultat (essaie d'autres mots-clés, ou --bk-licence any).")
        return
    print(f"\n🔎 {len(assets)} résultat(s) — choisir avec --index N :")
    for i, a in enumerate(assets):
        flag = "" if a["gratuit"] else "  ⚠️ plan payant probable"
        resos = sorted(f.replace("resolution_", "") for f in a["fichiers"] if f.startswith("resolution_"))
        extra = f" | résos={','.join(resos)}" if resos else ""
        print(f"  [{i}] {a['nom'][:48]:50} | {a['licence']}{flag} | {a['categorie']}{extra}")
        if a["description"]:
            print(f"       {a['description']}")


def executer_job_blender(job: dict, dossier_job: str) -> dict:
    """Écrit le job.json, lance Blender headless avec le worker, retourne resultat.json."""
    blender = trouver_blender()
    if not blender:
        raise EnvironmentError("Blender introuvable (core/blender_ops.trouver_blender).")
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
        extraits = [l.strip() for l in (processus.stderr or "").splitlines() if l.strip()][-6:]
        raise RuntimeError(f"le worker Blender n'a pas produit de résultat (exit {processus.returncode}) : {' | '.join(extraits)}")
    with open(chemin_resultat, "r", encoding="utf-8") as f:
        resultat = json.load(f)
    if not resultat.get("ok"):
        raise RuntimeError(f"worker Blender en échec : {resultat.get('erreur', 'raison inconnue')}")
    return resultat


def verifier_prerequis_blendkit() -> tuple:
    """Vérifie Blender ; la clé API est vérifiée par le worker (côté Blender uniquement)."""
    manquants = []
    if not trouver_blender():
        manquants.append("Blender (binaire blender.exe introuvable)")
    return len(manquants) == 0, manquants
