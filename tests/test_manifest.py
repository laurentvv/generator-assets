#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests of the engines manifest (audit §2.6) — schema, no network.

Checks that scripts/engines_manifest.json stays readable by both
installers: expected keys, well-formed sha256 fingerprints, and
consistency of the platform cards (one resolution source per card).
"""

import json
import re
from pathlib import Path

import pytest

CHEMIN_MANIFESTE = Path(__file__).resolve().parents[1] / "scripts" / "engines_manifest.json"
MOTIF_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@pytest.fixture(scope="module")
def manifeste():
    return json.loads(CHEMIN_MANIFESTE.read_text(encoding="utf-8"))


def test_manifeste_non_vide(manifeste):
    assert manifeste.get("moteurs"), "no engine in the manifest"


def test_chaque_moteur_a_un_repo_ou_des_url_directes(manifeste):
    for nom, moteur in manifeste["moteurs"].items():
        has_url_directe = any(
            f.get("url") or f.get("gestionnaire")
            for f in moteur.get("plateformes", {}).values()
        )
        assert moteur.get("repo") or has_url_directe, (
            f"{nom}: neither 'repo' (GitHub releases) nor direct 'url'/'gestionnaire'"
        )


def test_sha256_bien_forme_si_present(manifeste):
    for nom, moteur in manifeste["moteurs"].items():
        for plat, fiche in moteur.get("plateformes", {}).items():
            if "sha256" in fiche:
                assert MOTIF_SHA256.match(fiche["sha256"]), (
                    f"{nom}/{plat}: malformed sha256 (64 lowercase hex expected): {fiche['sha256']!r}"
                )


def test_asset_epingle_porte_sha256(manifeste):
    """An 'epingle'+'asset' card must carry its fingerprint (deterministic resolution)."""
    manquants = []
    for nom, moteur in manifeste["moteurs"].items():
        for plat, fiche in moteur.get("plateformes", {}).items():
            if fiche.get("epingle") and fiche.get("asset") and not fiche.get("sha256"):
                manquants.append(f"{nom}/{plat}")
    assert not manquants, f"pinned assets without sha256: {', '.join(manquants)}"


def test_fiche_plateforme_resolvable(manifeste):
    """Each platform card exposes at least one resolution source
    (direct url, manager, epingle+asset, release, scan_releases)."""
    incompletes = []
    for nom, moteur in manifeste["moteurs"].items():
        for plat, fiche in moteur.get("plateformes", {}).items():
            complete = (
                fiche.get("url")
                or fiche.get("gestionnaire")
                or (fiche.get("epingle") and fiche.get("asset"))
                or fiche.get("release")
                or fiche.get("scan_releases")
            )
            if not complete:
                incompletes.append(f"{nom}/{plat}")
    assert not incompletes, f"cards without a resolution source: {', '.join(incompletes)}"
