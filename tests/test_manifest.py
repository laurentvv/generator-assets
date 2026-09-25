#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests du manifeste des moteurs (audit §2.6) — schéma, sans réseau.

Vérifie que scripts/engines_manifest.json reste lisible par les deux
installateurs : clés attendues, empreintes sha256 au bon format, et
cohérence des fiches plateforme (une source de résolution par fiche).
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
    assert manifeste.get("moteurs"), "aucun moteur dans le manifeste"


def test_chaque_moteur_a_un_repo_ou_des_url_directes(manifeste):
    for nom, moteur in manifeste["moteurs"].items():
        has_url_directe = any(
            f.get("url") or f.get("gestionnaire")
            for f in moteur.get("plateformes", {}).values()
        )
        assert moteur.get("repo") or has_url_directe, (
            f"{nom} : ni 'repo' (releases GitHub) ni 'url'/'gestionnaire' direct"
        )


def test_sha256_bien_forme_si_present(manifeste):
    for nom, moteur in manifeste["moteurs"].items():
        for plat, fiche in moteur.get("plateformes", {}).items():
            if "sha256" in fiche:
                assert MOTIF_SHA256.match(fiche["sha256"]), (
                    f"{nom}/{plat} : sha256 mal formé (64 hex minuscules attendus) : {fiche['sha256']!r}"
                )


def test_asset_epingle_porte_sha256(manifeste):
    """Un asset 'epingle'+'asset' doit porter son empreinte (résolution déterministe)."""
    manquants = []
    for nom, moteur in manifeste["moteurs"].items():
        for plat, fiche in moteur.get("plateformes", {}).items():
            if fiche.get("epingle") and fiche.get("asset") and not fiche.get("sha256"):
                manquants.append(f"{nom}/{plat}")
    assert not manquants, f"assets épinglés sans sha256 : {', '.join(manquants)}"


def test_fiche_plateforme_resolvable(manifeste):
    """Chaque fiche plateforme expose au moins une source de résolution
    (url directe, gestionnaire, epingle+asset, release, scan_releases)."""
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
    assert not incompletes, f"fiches sans source de résolution : {', '.join(incompletes)}"
