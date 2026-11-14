#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only bridge to the local web-assets catalog (C:\\AssetLibrary + SQLite FTS5 + CLIP/CLAP).

Provides fast local asset lookup (SFX, music, PBR texture packs, 3D references,
UI sprites) while strictly enforcing vendor AI restrictions from CREDITS.md
and distinguishing commercial-safe vs conditional packs.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

import numpy as np

from core.config import (
    DEFAULT_ASSET_LIBRARY_DIR,
    DEFAULT_WEB_ASSETS_DB,
    DEFAULT_WEB_ASSETS_URL,
    LICENCE_COMMERCIAL,
    LICENCE_CONDITIONNELLE,
)

# Packs marked "IA interdite sur cet asset" in C:\AssetLibrary\CREDITS.md
PREFIXES_NO_AI: tuple[str, ...] = (
    "modeles_3d/fab/rogue_character_model/",
    "modeles_3d/fab/orphans_of_the_great_war_props_for_characters_asset_pack/",
)

# Normalized prefix -> (tier, license label, ai_allowed, commercial_ok)
_REGLES_LICENCE_PACKS: tuple[tuple[str, str, str, bool, bool], ...] = (
    (
        "modeles_3d/fab/rogue_character_model/",
        LICENCE_COMMERCIAL,
        "Commercial pack with explicit AI prohibition (CREDITS.md)",
        False,
        True,
    ),
    (
        "modeles_3d/fab/orphans_of_the_great_war_props_for_characters_asset_pack/",
        LICENCE_COMMERCIAL,
        "Commercial pack with explicit AI prohibition (CREDITS.md)",
        False,
        True,
    ),
    (
        "audio/adobe_sound/",
        LICENCE_CONDITIONNELLE,
        "Adobe Royalty-Free SFX (commercial projects OK, no raw standalone redistribution)",
        True,
        True,
    ),
    (
        "audio/sonniss/",
        LICENCE_CONDITIONNELLE,
        "Sonniss GDC Royalty-Free (commercial projects OK, no raw standalone redistribution)",
        True,
        True,
    ),
    (
        "textures/megascans/",
        LICENCE_CONDITIONNELLE,
        "Fab/Megascans (commercial projects OK, no raw standalone redistribution)",
        True,
        True,
    ),
    (
        "ui/bloodlines_dark_ui/",
        LICENCE_CONDITIONNELLE,
        "Standard Asset License (commercial projects OK, no raw standalone redistribution)",
        True,
        True,
    ),
    (
        "images/ui/bloodlines_dark_ui/",
        LICENCE_CONDITIONNELLE,
        "Standard Asset License (commercial projects OK, no raw standalone redistribution)",
        True,
        True,
    ),
    (
        "textures/juliosillet/",
        LICENCE_COMMERCIAL,
        "CC-BY 4.0 (Julio Sillet — attribution required)",
        True,
        True,
    ),
    (
        "audio/musique/",
        LICENCE_COMMERCIAL,
        "CC-BY / Royalty-Free (check pack attribution in CREDITS.md)",
        True,
        True,
    ),
    ("audio/kenney/", LICENCE_COMMERCIAL, "CC0 1.0 (Kenney)", True, True),
    ("images/kenney_2d/", LICENCE_COMMERCIAL, "CC0 1.0 (Kenney)", True, True),
    ("modeles_3d/kenney/", LICENCE_COMMERCIAL, "CC0 1.0 (Kenney)", True, True),
    ("modeles_3d/kenney_3d/", LICENCE_COMMERCIAL, "CC0 1.0 (Kenney)", True, True),
    ("modeles_3d/kaykit/", LICENCE_COMMERCIAL, "CC0 1.0 (KayKit)", True, True),
    ("textures/ambientcg/", LICENCE_COMMERCIAL, "CC0 1.0 (ambientCG)", True, True),
    ("textures/polyhaven/", LICENCE_COMMERCIAL, "CC0 1.0 (Poly Haven)", True, True),
)


def normaliser_rel_path(rel_path: Optional[str]) -> str:
    """Normalizes a relative asset path to forward slashes for portable matching."""
    return (rel_path or "").replace("\\", "/").lstrip("/")


def est_exclu_ia(rel_path: str) -> bool:
    """Returns True if the asset belongs to a pack forbidden for AI workflows."""
    norm = normaliser_rel_path(rel_path).lower()
    return any(norm.startswith(prefix) for prefix in PREFIXES_NO_AI)


def classifier_licence_asset(rel_path: str) -> dict[str, Any]:
    """Classifies vendor license & AI eligibility for a local web-assets entry."""
    norm = normaliser_rel_path(rel_path).lower()
    for prefix, tier, label, ai_ok, commercial_ok in _REGLES_LICENCE_PACKS:
        if norm.startswith(prefix):
            return {
                "tier": tier,
                "licence": label,
                "ai_ok": ai_ok,
                "commercial_ok": commercial_ok,
            }
    return {
        "tier": LICENCE_CONDITIONNELLE,
        "licence": "Verify pack entry in CREDITS.md before distribution",
        "ai_ok": True,
        "commercial_ok": True,
    }


def _resoudre_db_path(db_path: Optional[str] = None) -> Path:
    return Path(db_path or os.getenv("WEB_ASSETS_DB", DEFAULT_WEB_ASSETS_DB))


def _resoudre_library_dir(library_dir: Optional[str] = None) -> str:
    return library_dir or os.getenv("ASSET_LIBRARY_DIR", DEFAULT_ASSET_LIBRARY_DIR)


def _resoudre_chemin_absolu(rel_path: str, library_dir: Optional[str] = None) -> str:
    racine = _resoudre_library_dir(library_dir)
    parts = [p for p in normaliser_rel_path(rel_path).split("/") if p]
    return os.path.join(racine, *parts)


def _connecter_ro(db_path: Optional[str] = None) -> sqlite3.Connection:
    chemin = _resoudre_db_path(db_path)
    if not chemin.is_file():
        raise FileNotFoundError(f"web-assets SQLite DB not found: {chemin}")
    uri = f"{chemin.resolve().as_uri()}?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=2.0)
    con.row_factory = sqlite3.Row
    return con


def est_disponible(db_path: Optional[str] = None) -> bool:
    """Returns True when the web-assets SQLite index is present and readable."""
    chemin = _resoudre_db_path(db_path)
    if not chemin.is_file():
        return False
    try:
        with _connecter_ro(str(chemin)) as con:
            con.execute("SELECT 1 FROM assets LIMIT 1").fetchone()
        return True
    except sqlite3.Error:
        return False


def _row_to_asset(
    row: sqlite3.Row,
    library_dir: Optional[str] = None,
    score: Optional[float] = None,
) -> dict[str, Any]:
    donnees = dict(row)
    rel_path = normaliser_rel_path(donnees.get("rel_path"))
    licence = classifier_licence_asset(rel_path)
    donnees["rel_path"] = rel_path
    donnees["abs_path"] = _resoudre_chemin_absolu(rel_path, library_dir)
    donnees["ai_interdit"] = not licence["ai_ok"]
    donnees["licence"] = licence
    if score is not None:
        donnees["score"] = round(float(score), 6)
    return donnees


def _filtrer_rows(
    rows: list[sqlite3.Row],
    *,
    exclude_no_ai: bool,
    commercial_only: bool,
    library_dir: Optional[str] = None,
    limit: Optional[int] = None,
    scores: Optional[dict[int, float]] = None,
) -> list[dict[str, Any]]:
    resultats: list[dict[str, Any]] = []
    for row in rows:
        rel_path = row["rel_path"] or ""
        licence = classifier_licence_asset(rel_path)
        if exclude_no_ai and not licence["ai_ok"]:
            continue
        if commercial_only and not licence["commercial_ok"]:
            continue
        score = scores.get(row["id"]) if scores else None
        resultats.append(_row_to_asset(row, library_dir=library_dir, score=score))
        if limit is not None and len(resultats) >= limit:
            break
    return resultats


def _construire_fts_query(query: str) -> str:
    tokens = re.findall(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ_+\-]+", query.strip())
    if not tokens:
        return ""
    return " AND ".join(f'"{tok}"*' for tok in tokens)


def _executer_requete_assets(
    con: sqlite3.Connection,
    query: str,
    clauses: list[str],
    params: list[Any],
    fetch_limit: int,
    offset: int = 0,
) -> list[sqlite3.Row]:
    fts_expr = _construire_fts_query(query)
    where_sql = " AND ".join(clauses)
    if fts_expr:
        sql_fts = (
            "SELECT a.* FROM assets a "
            "JOIN assets_fts f ON f.rowid = a.id "
            f"WHERE {where_sql} AND assets_fts MATCH ? "
            "ORDER BY bm25(assets_fts), a.id "
            "LIMIT ? OFFSET ?"
        )
        try:
            return con.execute(sql_fts, [*params, fts_expr, fetch_limit, offset]).fetchall()
        except sqlite3.OperationalError:
            pass

    if query.strip():
        like = f"%{query.strip()}%"
        like_clause = "(a.title LIKE ? OR a.description LIKE ? OR a.keywords LIKE ? OR a.rel_path LIKE ?)"
        sql_like = (
            "SELECT a.* FROM assets a "
            f"WHERE {where_sql} AND {like_clause} "
            "ORDER BY a.id LIMIT ? OFFSET ?"
        )
        return con.execute(sql_like, [*params, like, like, like, like, fetch_limit, offset]).fetchall()

    sql_plain = f"SELECT a.* FROM assets a WHERE {where_sql} ORDER BY a.id LIMIT ? OFFSET ?"
    return con.execute(sql_plain, [*params, fetch_limit, offset]).fetchall()


def rechercher_assets(
    query: str = "",
    *,
    asset_type: Optional[str] = None,
    category: Optional[str] = None,
    pbr_role: Optional[str] = None,
    ext: Optional[str] = None,
    min_duration_ms: Optional[int] = None,
    max_duration_ms: Optional[int] = None,
    exclude_no_ai: bool = True,
    commercial_only: bool = False,
    limit: int = 20,
    db_path: Optional[str] = None,
    library_dir: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Searches active assets via FTS5 with SQL fallback and AI/license guards."""
    if limit <= 0 or not _resoudre_db_path(db_path).is_file():
        return []

    clauses: list[str] = ["COALESCE(a.flag_delete, 0) = 0"]
    params: list[Any] = []
    if asset_type:
        clauses.append("a.type = ?")
        params.append(asset_type)
    if category:
        clauses.append("a.category = ?")
        params.append(category)
    if pbr_role:
        clauses.append("a.pbr_role = ?")
        params.append(pbr_role)
    if ext:
        clauses.append("LOWER(a.ext) = ?")
        params.append(ext.lower().lstrip("."))
    if min_duration_ms is not None:
        clauses.append("a.duration_ms >= ?")
        params.append(int(min_duration_ms))
    if max_duration_ms is not None:
        clauses.append("a.duration_ms <= ?")
        params.append(int(max_duration_ms))

    # Page until `limit` survivors or SQL exhaustion so heavy no-AI prefix blocks don't starve results.
    batch_size = max(limit * 4, limit + 32)
    offset = 0
    collected: list[dict[str, Any]] = []
    with _connecter_ro(db_path) as con:
        while len(collected) < limit:
            rows = _executer_requete_assets(con, query, clauses, params, batch_size, offset=offset)
            if not rows:
                break
            collected.extend(
                _filtrer_rows(
                    rows,
                    exclude_no_ai=exclude_no_ai,
                    commercial_only=commercial_only,
                    library_dir=library_dir,
                    limit=limit - len(collected),
                )
            )
            if len(rows) < batch_size:
                break
            offset += len(rows)
    return collected


def lister_groupes_pbr(
    *,
    query: str = "",
    min_maps: int = 2,
    exclude_no_ai: bool = True,
    limit: int = 50,
    db_path: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Lists grouped PBR material sets available in the local library."""
    if limit <= 0 or not _resoudre_db_path(db_path).is_file():
        return []

    clauses = ["pbr_group IS NOT NULL", "COALESCE(flag_delete, 0) = 0"]
    params: list[Any] = []
    if query.strip():
        clauses.append("pbr_group LIKE ?")
        params.append(f"%{query.strip()}%")

    sql = (
        "SELECT pbr_group, GROUP_CONCAT(DISTINCT pbr_role) AS roles, "
        "MIN(rel_path) AS sample_path, COUNT(*) AS map_count "
        f"FROM assets WHERE {' AND '.join(clauses)} "
        "GROUP BY pbr_group HAVING COUNT(*) >= ? "
        "ORDER BY map_count DESC, pbr_group ASC LIMIT ? OFFSET ?"
    )
    batch_size = max(limit * 3, limit + 20)
    offset = 0
    groupes: list[dict[str, Any]] = []
    with _connecter_ro(db_path) as con:
        while len(groupes) < limit:
            rows = con.execute(sql, [*params, int(min_maps), batch_size, offset]).fetchall()
            if not rows:
                break
            for row in rows:
                if exclude_no_ai and est_exclu_ia(row["sample_path"] or ""):
                    continue
                roles = sorted(r for r in (row["roles"] or "").split(",") if r)
                groupes.append(
                    {
                        "pbr_group": row["pbr_group"],
                        "map_count": int(row["map_count"]),
                        "roles": roles,
                        "sample_path": normaliser_rel_path(row["sample_path"] or ""),
                    }
                )
                if len(groupes) >= limit:
                    break
            if len(rows) < batch_size:
                break
            offset += len(rows)
    return groupes


def charger_groupe_pbr(
    pbr_group: str,
    *,
    exclude_no_ai: bool = True,
    db_path: Optional[str] = None,
    library_dir: Optional[str] = None,
) -> dict[str, dict[str, Any]]:
    """Loads all maps of a PBR group keyed by `pbr_role` (albedo, normal, roughness...)."""
    if not pbr_group or not _resoudre_db_path(db_path).is_file():
        return {}

    sql = (
        "SELECT * FROM assets WHERE pbr_group = ? AND COALESCE(flag_delete, 0) = 0 "
        "ORDER BY pbr_role, id"
    )
    with _connecter_ro(db_path) as con:
        rows = con.execute(sql, (pbr_group,)).fetchall()

    assets = _filtrer_rows(
        rows,
        exclude_no_ai=exclude_no_ai,
        commercial_only=False,
        library_dir=library_dir,
    )
    resultat: dict[str, dict[str, Any]] = {}
    for asset in assets:
        role = asset.get("pbr_role") or Path(asset["rel_path"]).stem
        resultat.setdefault(role, asset)
    return resultat


def rechercher_similaires(
    asset_id: int,
    *,
    model: Optional[str] = None,
    exclude_no_ai: bool = True,
    commercial_only: bool = False,
    limit: int = 10,
    db_path: Optional[str] = None,
    library_dir: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Finds nearest assets by cosine similarity using precomputed CLIP/CLAP embeddings."""
    if limit <= 0 or not _resoudre_db_path(db_path).is_file():
        return []

    with _connecter_ro(db_path) as con:
        if model:
            ref_row = con.execute(
                "SELECT model, vec FROM embeddings WHERE asset_id = ? AND model = ?",
                (int(asset_id), model),
            ).fetchone()
        else:
            ref_row = con.execute(
                "SELECT model, vec FROM embeddings WHERE asset_id = ? LIMIT 1",
                (int(asset_id),),
            ).fetchone()
        if ref_row is None or not ref_row["vec"]:
            return []

        ref_blob = ref_row["vec"]
        if len(ref_blob) % 4 != 0:
            return []
        modele_cible = ref_row["model"]
        ref_vec = np.frombuffer(ref_blob, dtype=np.float32).astype(np.float64)
        if not np.all(np.isfinite(ref_vec)):
            return []
        ref_norm = float(np.linalg.norm(ref_vec))
        if not np.isfinite(ref_norm) or ref_norm == 0.0:
            return []
        ref_unit = ref_vec / ref_norm

        cands = con.execute(
            "SELECT e.asset_id, e.vec FROM embeddings e "
            "JOIN assets a ON a.id = e.asset_id "
            "WHERE e.model = ? AND e.asset_id != ? AND COALESCE(a.flag_delete, 0) = 0",
            (modele_cible, int(asset_id)),
        ).fetchall()
        if not cands:
            return []

        ids: list[int] = []
        vecs: list[np.ndarray] = []
        dim = ref_unit.shape[0]
        for row in cands:
            blob = row["vec"]
            if not blob or len(blob) % 4 != 0:
                continue
            v = np.frombuffer(blob, dtype=np.float32)
            if v.shape[0] != dim:
                continue
            ids.append(int(row["asset_id"]))
            vecs.append(v)

        if not vecs:
            return []

        mat = np.vstack(vecs).astype(np.float64)
        norms = np.linalg.norm(mat, axis=1)
        valid = np.isfinite(norms) & (norms > 0.0) & np.all(np.isfinite(mat), axis=1)
        valid_indices = np.flatnonzero(valid)
        if valid_indices.size == 0:
            return []

        sims = np.full(len(ids), -2.0, dtype=np.float64)
        sims[valid_indices] = (mat[valid_indices] @ ref_unit) / norms[valid_indices]

        # Rank valid candidates descending and page asset rows until `limit` survivors.
        ordre_valid = valid_indices[np.argsort(-sims[valid_indices])]
        chunk_size = max(limit * 4, limit + 24)
        collected: list[dict[str, Any]] = []
        for start in range(0, len(ordre_valid), chunk_size):
            batch_idx = ordre_valid[start : start + chunk_size]
            batch_ids = [ids[i] for i in batch_idx]
            scores_map = {ids[i]: float(sims[i]) for i in batch_idx}
            placeholders = ",".join("?" for _ in batch_ids)
            rows = con.execute(
                f"SELECT * FROM assets WHERE id IN ({placeholders})",
                batch_ids,
            ).fetchall()
            row_by_id = {row["id"]: row for row in rows}
            ordered_rows = [row_by_id[aid] for aid in batch_ids if aid in row_by_id]
            collected.extend(
                _filtrer_rows(
                    ordered_rows,
                    exclude_no_ai=exclude_no_ai,
                    commercial_only=commercial_only,
                    library_dir=library_dir,
                    limit=limit - len(collected),
                    scores=scores_map,
                )
            )
            if len(collected) >= limit:
                break
        return collected


def choisir_reference_audio(
    query: str,
    *,
    category: Optional[str] = None,
    min_duration_ms: int = 1500,
    max_duration_ms: int = 15000,
    commercial_only: bool = False,
    db_path: Optional[str] = None,
    library_dir: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Picks the highest-ranked local audio reference matching duration constraints."""
    candidats = rechercher_assets(
        query,
        asset_type="audio",
        category=category,
        min_duration_ms=min_duration_ms,
        max_duration_ms=max_duration_ms,
        exclude_no_ai=True,
        commercial_only=commercial_only,
        limit=12,
        db_path=db_path,
        library_dir=library_dir,
    )
    if not candidats:
        return None
    for item in candidats:
        if os.path.exists(item["abs_path"]):
            return item
    return None


def statistiques(db_path: Optional[str] = None) -> dict[str, Any]:
    """Returns summary counts from the web-assets database without modifying it."""
    chemin = _resoudre_db_path(db_path)
    if not chemin.is_file():
        return {"disponible": False, "db_path": str(chemin)}

    try:
        with _connecter_ro(str(chemin)) as con:
            total = con.execute(
                "SELECT COUNT(*) FROM assets WHERE COALESCE(flag_delete, 0) = 0"
            ).fetchone()[0]
            by_type = {
                r[0] or "unknown": int(r[1])
                for r in con.execute(
                    "SELECT type, COUNT(*) FROM assets WHERE COALESCE(flag_delete, 0) = 0 GROUP BY type"
                ).fetchall()
            }
            embeddings = {
                r[0]: int(r[1])
                for r in con.execute(
                    "SELECT model, COUNT(*) FROM embeddings GROUP BY model"
                ).fetchall()
            }
            pbr_groups = con.execute(
                "SELECT COUNT(DISTINCT pbr_group) FROM assets "
                "WHERE pbr_group IS NOT NULL AND COALESCE(flag_delete, 0) = 0"
            ).fetchone()[0]
        return {
            "disponible": True,
            "db_path": str(chemin),
            "total": int(total),
            "by_type": by_type,
            "embeddings": embeddings,
            "pbr_groups": int(pbr_groups),
        }
    except sqlite3.Error as exc:
        return {"disponible": False, "db_path": str(chemin), "error": str(exc)}


def notifier_scan_web_assets(
    url: Optional[str] = None,
    timeout_s: float = 2.5,
) -> dict[str, Any]:
    """Triggers a non-blocking re-index scan on the local web-assets HTTP service."""
    base = (url or os.getenv("WEB_ASSETS_URL", DEFAULT_WEB_ASSETS_URL)).rstrip("/")
    endpoint = f"{base}/api/scan"
    req = urllib.request.Request(endpoint, data=b"{}", method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(body) if body else {}
            except json.JSONDecodeError:
                payload = {"raw": body}
            return {"ok": 200 <= resp.status < 300, "status": resp.status, "data": payload}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "error": str(exc), "endpoint": endpoint}


def resoudre_reference_web_assets(
    query: str,
    *,
    asset_type: str,
    min_duration_ms: Optional[int] = None,
    max_duration_ms: Optional[int] = None,
    commercial_only: bool = False,
    db_path: Optional[str] = None,
    library_dir: Optional[str] = None,
) -> dict[str, Any]:
    """Resolves a single verified asset from C:\\GIT\\web-assets with NO_AI filtering enforced."""
    q = (query or "").strip()
    if not q:
        raise ValueError("Empty --ref-lib query.")

    if asset_type == "audio" and min_duration_ms is not None and max_duration_ms is not None:
        hit = choisir_reference_audio(
            q,
            min_duration_ms=min_duration_ms,
            max_duration_ms=max_duration_ms,
            commercial_only=commercial_only,
            db_path=db_path,
            library_dir=library_dir,
        )
    else:
        hits = rechercher_assets(
            q,
            asset_type=asset_type,
            min_duration_ms=min_duration_ms,
            max_duration_ms=max_duration_ms,
            exclude_no_ai=True,
            commercial_only=commercial_only,
            limit=5 if asset_type == "image" else 1,
            db_path=db_path,
            library_dir=library_dir,
        )
        if asset_type == "image" and hits:
            visual_hits = [
                h for h in hits
                if h.get("pbr_role") in (None, "", "albedo")
                and h.get("abs_path") and os.path.exists(h["abs_path"])
            ]
            hit = visual_hits[0] if visual_hits else hits[0]
        else:
            hit = hits[0] if hits else None

    if not hit or not hit.get("abs_path") or not os.path.exists(hit["abs_path"]):
        raise FileNotFoundError(
            f"No eligible {asset_type} reference found in web-assets for '{q}' (NO_AI excluded)."
        )
    return hit
