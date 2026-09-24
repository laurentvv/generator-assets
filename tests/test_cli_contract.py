#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests du contrat consommateurs du CLI generator-assets (ai-doc2video, video-analys-ia).

Fige les garanties dont dépendent les dépôts consommateurs (appels subprocess check=True) :
1. les options CLI spécifiques à un workflow valent None par défaut — chaque workflow
   applique donc son propre défaut (bug historique : --duration 2.0 écrasait les
   180 s de chanson, les 24 fps de video, les 12 s de music_bg…) ;
2. `construire_params` ne transmet que les clés réellement renseignées ;
3. les gestionnaires de maintenance (update_*) sont hors registre — le menu
   interactif doit les traiter avant WorkflowRegistry.get() ;
4. le rendu sd-cli n'écrit plus de fichiers temporaires en chemin relatif
   (ex-temp_render.png) : fichier unique par appel, nettoyé, insensible aux
   exécutions parallèles des deux consommateurs ;
5. le workflow batch signale ses échecs : arrêt à la première erreur par défaut
   (exception → code retour ≠ 0), mode --continue-on-error = lot complet + échecs
   dans le résultat (code retour ≠ 0 côté CLI).

Les faux sd-cli sont des monkeypatch de subprocess.run : aucun moteur ni GPU requis.
"""

import inspect
import json
import os
from pathlib import Path

import pytest
from PIL import Image

import main
from core import diffusion, upscaler
from workflows.base import BaseWorkflow, WorkflowRegistry
from workflows.batch import BatchWorkflow


# ============================================================================
# 1 & 2. Contrat argparse / paramètres
# ============================================================================

CHAMPS_SPECIFIQUES = ("duration", "frames", "fps", "pitch", "lufs", "factor")


def test_defauts_workflow_specifiques_absents_du_cli():
    """Sans option explicite, les champs spécifiques valent None : le workflow garde son défaut."""
    args = main.construire_parseur().parse_args(["-w", "video"])
    for champ in CHAMPS_SPECIFIQUES:
        assert getattr(args, champ) is None, (
            f"--{champ} doit valoir None par défaut (sinon il écrase le défaut du workflow)"
        )


def test_params_ne_transmet_que_les_cles_renseignees():
    """construire_params filtre les clés None et transmet les défauts généraux (seed…)."""
    args = main.construire_parseur().parse_args(
        ["-w", "video", "cascade mystique", "--frames", "25", "--fps", "24"]
    )
    params = main.construire_params(args, "cascade mystique")
    assert "duration" not in params
    assert "pitch" not in params
    assert params["frames"] == 25
    assert params["fps"] == 24.0
    assert params["seed"] == -1  # défaut général toujours transmis
    assert params["prompt"] == "cascade mystique"


def test_param_explicite_reste_transmis():
    """Une valeur explicite (ex. --duration 45 pour chanson) traverse bien le filtre."""
    args = main.construire_parseur().parse_args(["-w", "chanson", "paroles", "--duration", "45"])
    params = main.construire_params(args, "paroles")
    assert params["duration"] == 45.0


# ============================================================================
# 3. Gestionnaires de maintenance hors registre
# ============================================================================

def test_gestionnaires_maintenance_hors_registre():
    """update_* ne sont pas des workflows : le menu interactif doit les router
    vers leur branche dédiée AVANT WorkflowRegistry.get (sinon ValueError)."""
    for nom in ("update_sd", "update_llama", "update_vulkan"):
        with pytest.raises(ValueError):
            WorkflowRegistry.get(nom)


def test_menu_interactif_couvre_le_registre():
    """Le menu interactif est généré du registre : tout workflow enregistré y
    apparaît (garde-fou anti-dérive — 4 workflows avaient disparu du menu)."""
    from cli.interactive import construire_menu

    menu = construire_menu()
    noms = {nom for nom, _ in menu.values()}
    maintenance = {"update_sd", "update_llama", "update_vulkan"}
    assert noms - maintenance == set(WorkflowRegistry.list_all())
    assert len(noms) == len(menu)  # aucun doublon
    assert sorted(int(k) for k in menu) == list(range(1, len(menu) + 1))
    # chaque workflow porte un emoji et une description de menu non vides
    for nom in WorkflowRegistry.list_all():
        cls = WorkflowRegistry.get(nom)
        assert getattr(cls, "emoji", ""), f"emoji manquant sur {nom}"


# ============================================================================
# 4. Fichiers temporaires du rendu sd-cli
# ============================================================================

@pytest.fixture
def faux_sd_cli(monkeypatch):
    """Remplace subprocess.run par un faux sd-cli qui écrit un PNG au chemin -o."""
    appels = []

    def faux_run(commande, check=True, **kwargs):
        appels.append(list(commande))
        sortie = commande[commande.index("-o") + 1]
        Image.new("RGB", (4, 4), (200, 30, 30)).save(sortie, "PNG")

    monkeypatch.setattr(diffusion.subprocess, "run", faux_run)
    monkeypatch.setattr(upscaler.subprocess, "run", faux_run)
    return appels


def test_generer_image_temporaire_unique_et_nettoye(tmp_path, monkeypatch, faux_sd_cli):
    """Sans output_path : rendu dans un fichier temporaire absolu, relu puis supprimé.
    Aucun temp_render.png n'apparaît dans le répertoire courant (exécutions parallèles)."""
    monkeypatch.chdir(tmp_path)
    img = diffusion.generer_image_vulkan(
        "unit test asset",
        sd_cli="faux-sd-cli",
        sd_model=diffusion.DEFAULT_SD_MODEL,
        width=64,
        height=64,
        steps=1,
    )
    assert isinstance(img, Image.Image)
    assert img.size == (4, 4)

    chemin_sortie = faux_sd_cli[0][faux_sd_cli[0].index("-o") + 1]
    assert Path(chemin_sortie).name != "temp_render.png"
    assert os.path.isabs(chemin_sortie)  # tempfile, pas le répertoire courant
    assert not Path(chemin_sortie).exists()  # nettoyé après lecture
    assert not (tmp_path / "temp_render.png").exists()


def test_generer_image_chemin_explicite_conserve(tmp_path, faux_sd_cli):
    """Avec output_path explicite : le fichier final est conservé (comportement historique)."""
    sortie = tmp_path / "final.png"
    img = diffusion.generer_image_vulkan(
        "unit test asset",
        sd_cli="faux-sd-cli",
        sd_model=diffusion.DEFAULT_SD_MODEL,
        output_path=str(sortie),
    )
    assert sortie.exists()
    assert img.size == (4, 4)


def test_upscale_esrgan_sans_temporaire_dans_cwd(tmp_path, monkeypatch, faux_sd_cli):
    """upscale_esrgan passe par un TemporaryDirectory : plus de temp_esrgan_*.png en cwd."""
    monkeypatch.chdir(tmp_path)
    modele = tmp_path / "4x-UltraSharp_faux.pth"
    modele.write_bytes(b"faux modele")

    source = Image.new("RGBA", (8, 8), (10, 200, 30, 255))
    img = upscaler.upscale_esrgan(
        source, esrgan_model_path=str(modele), sd_cli="faux-sd-cli"
    )

    assert isinstance(img, Image.Image)
    assert img.mode == "RGBA"  # alpha réinjecté
    assert img.size == (4, 4)
    assert sorted(p.name for p in tmp_path.iterdir()) == [modele.name]


def test_signature_generer_image_sans_defaut_relatif():
    """Garde-fou : le défaut de output_path ne doit plus être un chemin relatif."""
    defaut = inspect.signature(diffusion.generer_image_vulkan).parameters["output_path"].default
    assert defaut is None


# ============================================================================
# 5. Contrat du workflow batch
# ============================================================================

@WorkflowRegistry.register
class _WorkflowSpectacle(BaseWorkflow):
    """Faux workflow : échoue quand le prompt contient « echec » (aucun moteur requis)."""

    name = "spectacle_contrat"
    description = "Faux workflow réservé aux tests du contrat batch"
    emoji = "🧪"

    def run(self, params):
        if "echec" in (params.get("prompt") or ""):
            raise RuntimeError("panne moteur simulée")
        return {"ok": True, "prompt": params.get("prompt")}


@pytest.fixture
def recette_deux_assets(tmp_path):
    recette = tmp_path / "recette.json"
    recette.write_text(
        json.dumps([
            {"prompt": "asset ok 1", "workflow": "spectacle_contrat"},
            {"prompt": "asset echec", "workflow": "spectacle_contrat"},
            {"prompt": "asset jamais atteint", "workflow": "spectacle_contrat"},
        ]),
        encoding="utf-8",
    )
    return recette


def test_batch_strict_arrete_a_la_premiere_erreur(tmp_path, recette_deux_assets):
    """Défaut strict : l'échec d'un asset interrompt le lot avec une exception claire."""
    batch = BatchWorkflow({})
    with pytest.raises(RuntimeError, match="asset echec"):
        batch.run({"file": str(recette_deux_assets), "output_dir": str(tmp_path)})


def test_batch_tolerant_termine_et_signale_les_echecs(tmp_path, recette_deux_assets):
    """--continue-on-error : lot parcouru en entier, échecs listés dans le résultat."""
    batch = BatchWorkflow({})
    res = batch.run({
        "file": str(recette_deux_assets),
        "output_dir": str(tmp_path),
        "continue_on_error": True,
    })
    assert res["total_tasks"] == 3
    assert res["completed"] == 2
    assert len(res["echecs"]) == 1
    assert res["echecs"][0]["prompt"] == "asset echec"
    assert "panne moteur simulée" in res["echecs"][0]["erreur"]
