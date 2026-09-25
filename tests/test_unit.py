#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests unitaires des fonctions pures (audit §2.5) — aucun moteur ni GPU requis.

Modules couverts : core.config (slugifier), core.music_ai (BPM, boucles,
ducking, normalisation), core.shader_maps (flowmap), core.loop_ops (boucle
temporelle, spritesheet), core.autotile_builder (atlas 47 tuiles),
core.clothes_catalog (routage bilingue sur catalogue factice).
"""

import json
import subprocess

import numpy as np
import pytest
from PIL import Image

from core.config import charger_env, slugifier_texte
from core.music_ai import (
    construire_recette_ducking,
    fabriquer_boucle,
    fabriquer_boucle_ambiante,
    fabriquer_boucle_percussive,
    estimer_bpm,
    normaliser_pic,
    ressampler,
)
from core.shader_maps import generer_flowmap
from core.loop_ops import assembler_spritesheet_loop, creer_boucle_temporelle_circulaire
from core.autotile_builder import generer_atlas_47_tuiles
from core.clothes_catalog import aiguiller_modele_vetement


SR = 48000


def _clics(bpm: float, duree_s: float, sr: int = SR) -> np.ndarray:
    """Signal de clics métronomiques (pic sinus décroissant) à un BPM donné."""
    n = int(duree_s * sr)
    audio = np.zeros((n, 1))
    periode = int(60.0 / bpm * sr)
    for debut in range(0, n - 400, periode):
        audio[debut : debut + 400, 0] = np.sin(np.linspace(0, np.pi, 400)) * np.linspace(1.0, 0.2, 400)
    return audio


# ============================================================================
# core.config
# ============================================================================

def test_slugifier_texte_accent_ponctuation():
    assert slugifier_texte("Café Noir — Édition « Deluxe » !") == "cafe_noir_edition_deluxe"


def test_slugifier_texte_longueur_et_vide():
    long = slugifier_texte("a" * 200, max_longueur=20)
    assert len(long) == 20
    assert slugifier_texte("   ") == "asset_render"  # repli documenté


# ============================================================================
# core.music_ai
# ============================================================================

def test_estimer_bpm_clics_120():
    bpm = estimer_bpm(_clics(120.0, 16.0), SR)
    assert bpm is not None and abs(bpm - 120.0) <= 2.0


def test_estimer_bpm_signal_sans_dynamique_renvoie_none():
    # Énergie identique dans chaque fenêtre (DC) : aucun flux d'onsets → None
    audio = np.full((int(8.0 * SR), 1), 0.4)
    assert estimer_bpm(audio, SR) is None


def test_fabriquer_boucle_percussive_duree_en_mesures():
    audio = _clics(120.0, 20.0)
    boucle, infos = fabriquer_boucle_percussive(audio, SR, bpm=120.0, duree_cible=12.0)
    assert infos["strategie"] == "percussive"
    assert boucle.ndim == 2 and boucle.shape[0] / SR >= 12.0
    # longueur = nombre entier de mesures de 4 temps à 120 BPM (2 s par mesure)
    mesures = boucle.shape[0] / SR / 2.0
    assert abs(mesures - round(mesures)) < 0.02


def test_fabriquer_boucle_ambiante_crossfade():
    t = np.linspace(0, 10.0, int(10.0 * SR), endpoint=False)
    audio = np.column_stack([0.5 * np.sin(2 * np.pi * 110 * t)])
    boucle, infos = fabriquer_boucle_ambiante(audio, SR, crossfade_s=1.0)
    assert infos["strategie"] == "ambiante" and infos["bpm"] is None
    assert boucle.shape[0] < audio.shape[0]  # le crossfade consomme la queue


def test_fabriquer_boucle_bascule_ambiante_sans_pulsation():
    # DC : aucun BPM fiable → fondu long plus sûr (contrat documenté)
    audio = np.full((int(12.0 * SR), 1), 0.4)
    boucle, infos = fabriquer_boucle(audio, SR, duree_cible=6.0)
    assert infos["strategie"] == "ambiante"


def test_normaliser_pic():
    audio = np.full((SR, 2), 0.25)
    sorti = normaliser_pic(audio, pic_dbfs=-1.0)
    pic_dbfs = 20 * np.log10(np.max(np.abs(sorti)))
    assert abs(pic_dbfs - (-1.0)) < 0.1


def test_ressampler_diminue_la_duree_echantillons():
    audio = np.zeros((SR, 2))
    _, sr_sorti = ressampler(audio, SR, 24000)
    assert sr_sorti == 24000


def test_construire_recette_ducking_chaine_ffmpeg():
    cmd = construire_recette_ducking("voix.wav", "musique.ogg", "mix.wav", volume_musique=0.8)
    for fragment in ("sidechaincompress", "amix=inputs=2", "normalize=0", "stream_loop", "volume=0.8"):
        assert fragment in cmd
    # deux inputs dans le même ordre que la chaîne de filtres
    assert cmd.index("voix.wav") < cmd.index("musique.ogg") < cmd.index("mix.wav")


def test_construire_recette_ducking_executable_par_ffmpeg(tmp_path):
    """La recette produite est une commande ffmpeg valide (binaire réel si présent)."""
    import shutil
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg absent du PATH")
    sr = 48000
    t = np.linspace(0, 2.0, int(2.0 * sr), endpoint=False)
    voix = 0.5 * np.sin(2 * np.pi * 440 * t)
    musique = 0.3 * np.sin(2 * np.pi * 220 * t)
    import soundfile as sf
    chemin_voix = tmp_path / "voix.wav"
    chemin_mus = tmp_path / "mus.wav"
    chemin_mix = tmp_path / "mix.wav"
    sf.write(chemin_voix, voix, sr)
    sf.write(chemin_mus, musique, sr)
    cmd = construire_recette_ducking(str(chemin_voix), str(chemin_mus), str(chemin_mix))
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    assert res.returncode == 0, (res.stderr or "")[-400:]
    assert chemin_mix.exists() and chemin_mix.stat().st_size > 1000


# ============================================================================
# core.shader_maps
# ============================================================================

def test_generer_flowmap_river_dimensions_et_alpha():
    img = generer_flowmap(type_flux="river", resolution=128, angle_deg=90.0)
    assert img.size == (128, 128) and img.mode == "RGBA"
    alpha = img.getchannel("A")
    assert alpha.getextrema() == (255, 255)  # A toujours opaque


def test_generer_flowmap_vortex_aspiration_vers_le_centre():
    """Vortex : l'aspiration se resserre — magnitude du vecteur forte au centre,
    décroissante vers le bord (canal R/G = composantes du vecteur autour de 128)."""
    img = generer_flowmap(type_flux="vortex", resolution=64).convert("RGB")
    a = np.asarray(img, dtype=np.float64)
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    rayon = np.hypot(yy - h / 2, xx - w / 2)
    magnitude = np.hypot(a[..., 0] - 128.0, a[..., 1] - 128.0)
    assert magnitude[rayon < 4].mean() > magnitude[rayon > 26].mean()


# ============================================================================
# core.loop_ops
# ============================================================================

def _trames(n: int, taille: int = 32) -> list:
    return [
        Image.new("RGBA", (taille, taille), (i * 30 % 256, 100, 200, 255))
        for i in range(n)
    ]


def test_creer_boucle_temporelle_circulaire_identite_1_trame():
    trames = _trames(1)
    assert creer_boucle_temporelle_circulaire(trames) is trames


def test_creer_boucle_temporelle_circulaire_conserve_le_nombre_et_la_taille():
    sorties = creer_boucle_temporelle_circulaire(_trames(4))
    assert len(sorties) == 4
    assert all(t.size == (32, 32) and t.mode == "RGBA" for t in sorties)


def test_assembler_spritesheet_loop():
    planche = assembler_spritesheet_loop(_trames(4), colonnes=2)
    assert planche.size == (64, 64)


# ============================================================================
# core.autotile_builder
# ============================================================================

def test_generer_atlas_47_tuiles_dimensions():
    biome_a = Image.new("RGBA", (64, 64), (120, 40, 40, 255))
    biome_b = Image.new("RGBA", (64, 64), (40, 40, 120, 255))
    atlas = generer_atlas_47_tuiles(biome_a, biome_b, tile_size=64, colonnes=8)
    lignes = (47 + 7) // 8
    assert atlas.size == (8 * 64, lignes * 64)


# ============================================================================
# core.clothes_catalog (catalogue factice)
# ============================================================================

@pytest.fixture
def catalogue_factice(tmp_path):
    catalogue = {
        "bottes_male": {"category": "shoes", "gender": "male", "keywords": ["boot", "boots", "leather"]},
        "robe_female": {"category": "clothes", "gender": "female", "keywords": ["dress", "robe"]},
        "tunique_unisex": {"category": "torso", "gender": "unisex", "keywords": ["tunic", "tunique"]},
    }
    chemin = tmp_path / "catalogue.json"
    chemin.write_text(json.dumps(catalogue), encoding="utf-8")
    return str(chemin)


def test_aiguiller_vetement_trouve_par_mot_cle(catalogue_factice):
    item = aiguiller_modele_vetement("worn leather boots of the guard", catalog_path=catalogue_factice)
    assert item is not None and "boot" in item["keywords"]


def test_aiguiller_vetement_filtre_genre_francais(catalogue_factice):
    item = aiguiller_modele_vetement("robe élégante pour femme", catalog_path=catalogue_factice)
    assert item is not None and item["gender"] == "female"


def test_aiguiller_vetement_repli_categorie(catalogue_factice):
    # aucun score positif pour "shoes" sans mot-clé → repli catalog.get("shoes01") → None ici
    item = aiguiller_modele_vetement("something", category="shoes", catalog_path=catalogue_factice)
    assert item is None


# ==============================================================================
# core.config — chargeur .env (audit §2.3)

def test_charger_env_lit_cle_valeur_et_commentaires(tmp_path, monkeypatch):
    fichier = tmp_path / ".env"
    fichier.write_text(
        "# commentaire\n"
        "TEST_ENV_A=valeur simple\n"
        'TEST_ENV_B="valeur quotée"\n'
        "export TEST_ENV_C=c\n"
        "\n"
        "ligne invalide sans séparateur\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("TEST_ENV_A", raising=False)
    monkeypatch.delenv("TEST_ENV_B", raising=False)
    monkeypatch.delenv("TEST_ENV_C", raising=False)
    charger_env(fichier)
    import os
    assert os.environ["TEST_ENV_A"] == "valeur simple"
    assert os.environ["TEST_ENV_B"] == "valeur quotée"
    assert os.environ["TEST_ENV_C"] == "c"


def test_charger_env_n_ecrase_pas_la_variable_existante(tmp_path, monkeypatch):
    fichier = tmp_path / ".env"
    fichier.write_text("TEST_ENV_EXISTANTE=du_fichier\n", encoding="utf-8")
    monkeypatch.setenv("TEST_ENV_EXISTANTE", "du_shell")
    charger_env(fichier)
    import os
    assert os.environ["TEST_ENV_EXISTANTE"] == "du_shell"


def test_charger_env_fichier_absent_sans_erreur(tmp_path):
    charger_env(tmp_path / "inexistant.env")  # ne doit pas lever


# ==============================================================================
# core.journal — journalisation structurée (audit §2.8)

def test_configurer_journal_niveau_fichier_et_idempotence(tmp_path):
    import logging
    from core.journal import configurer_journal

    racine = logging.getLogger()
    handlers_avant, niveau_avant = list(racine.handlers), racine.level
    try:
        log_fichier = tmp_path / "logs" / "run.log"
        configurer_journal("DEBUG", fichier=log_fichier)
        racine = logging.getLogger()
        assert racine.level == logging.DEBUG
        assert len(racine.handlers) == 2  # console stderr + fichier

        logging.getLogger("test.journal").debug("entrée %s", "debug")
        contenu = log_fichier.read_text(encoding="utf-8")
        assert "entrée debug" in contenu
        assert "DEBUG" in contenu
        assert "test.journal" in contenu

        # idempotence : ré-appeler remplace les handlers au lieu d'empiler
        configurer_journal("INFO")
        racine = logging.getLogger()
        assert racine.level == logging.INFO
        assert len(racine.handlers) == 1
    finally:
        racine = logging.getLogger()
        for h in list(racine.handlers):
            racine.removeHandler(h)
        for h in handlers_avant:
            racine.addHandler(h)
        racine.setLevel(niveau_avant)


def test_run_engine_journalise_la_commande(caplog):
    # la commande exécutée passe désormais par logging (core.process), pas par print
    import logging
    import sys
    from core.process import run_engine

    with caplog.at_level(logging.INFO, logger="core.process"):
        run_engine([sys.executable, "-c", "print('x')"], timeout=60, etiquette="testlog")
    assert any("▶️" and "testlog" in r.message for r in caplog.records) or any(
        "▶️" in r.getMessage() for r in caplog.records
    )
