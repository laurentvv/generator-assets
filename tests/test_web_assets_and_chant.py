#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline unit tests (0 GPU) for Web-Assets bridge, load gate, singing compiler, de-click, and licenses."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pytest
import soundfile

from core.chant_score import compiler_partition_chant, decouper_syllabes, note_vers_midi
from core.config import (
    LICENCE_COMMERCIAL,
    LICENCE_CONDITIONNELLE,
    LICENCE_NON_COMMERCIAL,
    classifier_licence_workflow,
)
from core.music_ai import declick_fichier_wav
from core.web_assets import (
    charger_groupe_pbr,
    choisir_reference_audio,
    est_disponible,
    est_exclu_ia,
    lister_groupes_pbr,
    notifier_scan_web_assets,
    rechercher_assets,
    rechercher_similaires,
    statistiques,
)
from scripts.check_charge_systeme import evaluer_seuils
from workflows.moss_image import MossImageWorkflow


def _creer_fausse_db(db_path: Path, lib_dir: Path) -> None:
    """Creates a realistic miniature SQLite catalog matching web-assets schema."""
    con = sqlite3.connect(db_path)
    con.executescript(
        """
        CREATE TABLE assets (
            id INTEGER PRIMARY KEY,
            rel_path TEXT,
            ext TEXT,
            type TEXT,
            size_bytes INTEGER,
            mtime REAL,
            width INTEGER,
            height INTEGER,
            duration_ms INTEGER,
            category TEXT,
            title TEXT,
            description TEXT,
            keywords TEXT,
            colors TEXT,
            ai_status TEXT,
            ai_attempts INTEGER,
            ai_analyzed_at REAL,
            thumb_status TEXT,
            thumb_ext TEXT,
            thumb_at REAL,
            flag_delete INTEGER DEFAULT 0,
            flagged_at REAL,
            flag_reason TEXT,
            pbr_role TEXT,
            pbr_group TEXT,
            note TEXT,
            sha256 TEXT,
            phash TEXT
        );
        CREATE VIRTUAL TABLE assets_fts USING fts5(title, description, keywords, path);
        CREATE TABLE embeddings (
            asset_id INTEGER PRIMARY KEY,
            model TEXT,
            vec BLOB
        );
        """
    )

    sfx_file = lib_dir / "audio/adobe_sound/door_creak.wav"
    sfx_file.parent.mkdir(parents=True, exist_ok=True)
    sfx_file.write_bytes(b"RIFF")

    rows = [
        (1, "audio/adobe_sound/door_creak.wav", "wav", "audio", 4200, "sfx", "Door Creak Heavy", "Wooden door creaking open", "door wood creak", 0, None, None),
        (2, "audio/kenney/ui_click.ogg", "ogg", "audio", 500, "sfx", "UI Click Crisp", "Short UI button sound", "click button ui", 0, None, None),
        (3, "modeles_3d/fab/rogue_character_model/rogue_all.fbx", "fbx", "model3d", None, "character", "Rogue Character", "Fantasy stealth character", "rogue character stealth", 0, None, None),
        (4, "modeles_3d/kaykit/rogue_texture.png", "png", "image", None, "character", "KayKit Rogue Texture", "CC0 rogue palette", "rogue texture kaykit", 0, None, None),
        (5, "modeles_3d/fab/orphans_of_the_great_war_props_for_characters_asset_pack/shovel.fbx", "fbx", "model3d", None, "object_3d", "Trench Shovel", "Military shovel prop", "shovel war prop", 0, None, None),
        (6, "textures/juliosillet/stone_albedo.png", "png", "image", None, "texture_pbr", "Stone Wall Albedo", "Mossy stone albedo", "stone wall albedo", 0, "albedo", "textures/juliosillet::stone_01"),
        (7, "textures/juliosillet/stone_normal.png", "png", "image", None, "texture_pbr", "Stone Wall Normal", "Mossy stone normal", "stone wall normal", 0, "normal", "textures/juliosillet::stone_01"),
        (8, "textures/juliosillet/stone_rough.png", "png", "image", None, "texture_pbr", "Stone Wall Roughness", "Mossy stone roughness", "stone wall roughness", 0, "roughness", "textures/juliosillet::stone_01"),
        (9, "audio/kenney/flagged_trash.ogg", "ogg", "audio", 3000, "sfx", "Deleted Sound", "Should never appear", "door wood", 1, None, None),
    ]
    for r in rows:
        con.execute(
            """
            INSERT INTO assets (
                id, rel_path, ext, type, duration_ms, category,
                title, description, keywords, flag_delete, pbr_role, pbr_group
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            r,
        )
        con.execute(
            "INSERT INTO assets_fts (rowid, title, description, keywords, path) VALUES (?, ?, ?, ?, ?)",
            (r[0], r[6], r[7], r[8], r[1]),
        )

    def _blob(vals: list[float]) -> bytes:
        return np.array(vals, dtype=np.float32).tobytes()

    con.execute("INSERT INTO embeddings VALUES (3, 'clip-vit-base-patch32', ?)", (_blob([1.0, 0.0, 0.0]),))
    con.execute("INSERT INTO embeddings VALUES (4, 'clip-vit-base-patch32', ?)", (_blob([0.9, 0.1, 0.0]),))
    con.execute("INSERT INTO embeddings VALUES (6, 'clip-vit-base-patch32', ?)", (_blob([0.95, 0.05, 0.0]),))
    con.execute("INSERT INTO embeddings VALUES (7, 'clip-vit-base-patch32', ?)", (_blob([0.0, 1.0, 0.0]),))
    con.commit()
    con.close()


def test_evaluer_seuils_includes_commit_charge():
    assert evaluer_seuils({"cpu": 10.0, "ram": 40.0, "commit": 30.0, "gpu": 5.0, "vram": 10.0}) == []
    assert evaluer_seuils({"cpu": 10.0, "ram": 40.0, "commit": 85.0, "gpu": 5.0, "vram": 10.0}) == ["commit"]
    assert evaluer_seuils({"cpu": None, "commit": 92.5, "gpu": 45.0}) == ["commit", "gpu"]


def test_license_classification_tiers():
    assert classifier_licence_workflow("qwen_image")["tier"] == LICENCE_NON_COMMERCIAL
    assert classifier_licence_workflow("moss_image")["tier"] == LICENCE_COMMERCIAL
    assert classifier_licence_workflow("generate")["commercial_ok"] is False
    assert classifier_licence_workflow("generate", sd_model="Chroma1-HD-Q8_0.gguf")["tier"] == LICENCE_COMMERCIAL
    assert classifier_licence_workflow("generate", sd_model="juggernautXL_ragnarok.safetensors")["commercial_ok"] is True
    assert classifier_licence_workflow("voix_off", moteur="qwen3")["tier"] == LICENCE_COMMERCIAL
    assert classifier_licence_workflow("voix_off", moteur="fish")["commercial_ok"] is False
    assert classifier_licence_workflow("voix_off", moteur="drama3")["tier"] == LICENCE_CONDITIONNELLE
    assert classifier_licence_workflow("music_bg", moteur="acestep")["tier"] == LICENCE_COMMERCIAL
    assert classifier_licence_workflow("music_bg", moteur="music3")["tier"] == LICENCE_CONDITIONNELLE
    assert classifier_licence_workflow("video", moteur="wan")["tier"] == LICENCE_COMMERCIAL
    assert classifier_licence_workflow("video", moteur="ltx")["tier"] == LICENCE_CONDITIONNELLE


def test_web_assets_no_ai_and_pbr_and_similarity(tmp_path: Path):
    db_path = tmp_path / "app.db"
    lib_dir = tmp_path / "AssetLibrary"
    _creer_fausse_db(db_path, lib_dir)

    assert est_disponible(str(db_path)) is True
    assert est_exclu_ia("modeles_3d\\fab\\rogue_character_model\\rogue_all.fbx") is True
    assert est_exclu_ia("modeles_3d/kaykit/rogue_texture.png") is False

    stats = statistiques(str(db_path))
    assert stats["disponible"] is True
    assert stats["total"] == 8  # flagged row #9 excluded
    assert stats["pbr_groups"] == 1

    # Query "rogue" with exclude_no_ai=True must return KayKit texture #4 and hide Fab pack #3
    rogues = rechercher_assets("rogue", exclude_no_ai=True, db_path=str(db_path), library_dir=str(lib_dir))
    assert [a["id"] for a in rogues] == [4]

    # Query "door" must return #1 and hide flagged-delete #9
    doors = rechercher_assets("door", db_path=str(db_path), library_dir=str(lib_dir))
    assert [a["id"] for a in doors] == [1]

    groupes = lister_groupes_pbr(min_maps=3, db_path=str(db_path))
    assert len(groupes) == 1
    assert groupes[0]["roles"] == ["albedo", "normal", "roughness"]

    pack = charger_groupe_pbr("textures/juliosillet::stone_01", db_path=str(db_path), library_dir=str(lib_dir))
    assert set(pack.keys()) == {"albedo", "normal", "roughness"}
    assert pack["albedo"]["abs_path"].endswith("stone_albedo.png")

    sims = rechercher_similaires(6, exclude_no_ai=True, db_path=str(db_path), library_dir=str(lib_dir))
    assert [s["id"] for s in sims] == [4, 7]
    assert sims[0]["score"] > sims[1]["score"]

    ref = choisir_reference_audio("door", min_duration_ms=1000, db_path=str(db_path), library_dir=str(lib_dir))
    assert ref is not None and ref["id"] == 1

    res = notifier_scan_web_assets(url="http://127.0.0.1:59999", timeout_s=0.3)
    assert res["ok"] is False


def test_chant_score_compiler():
    assert note_vers_midi("C4") == 60
    assert note_vers_midi("A3") == 57
    assert note_vers_midi("F#4") == 66
    assert decouper_syllabes("bonjour") == ["bon", "jour"]
    assert decouper_syllabes("light-ning") == ["light", "ning"]

    compilee = compiler_partition_chant("Ombres sur la mer.", bpm=84, gamme="a_minor")
    assert compilee.startswith("<BPM_84> ")
    assert "<P_" in compilee and "<NOTE_" in compilee

    explicite = compiler_partition_chant("la:A4:8 sol:G4", bpm=110)
    assert explicite == "<BPM_110> la<P_69><NOTE_8> sol<P_67><NOTE_4>"

    passthrough = compiler_partition_chant("la<P_60><NOTE_4>", bpm=95)
    assert passthrough == "<BPM_95> la<P_60><NOTE_4>"

    with pytest.raises(ValueError):
        compiler_partition_chant("   ")


def test_declick_fichier_wav(tmp_path: Path):
    sr = 48000
    t = np.linspace(0, 0.2, int(sr * 0.2), endpoint=False)
    # Non-zero cosine start creates a harsh sample-0 discontinuity
    stereo = np.column_stack([0.5 * np.cos(2 * np.pi * 220 * t), -0.4 * np.cos(2 * np.pi * 220 * t)])
    wav_path = tmp_path / "click.wav"
    soundfile.write(wav_path, stereo, sr, subtype="PCM_16")

    declick_fichier_wav(str(wav_path), fade_ms=10.0)
    out, out_sr = soundfile.read(wav_path)
    assert out_sr == sr
    assert abs(out[0]).max() == 0.0
    assert np.max(np.abs(out[3000:] - stereo[3000:])) < 1e-4


def test_moss_image_warns_on_size(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    wf = MossImageWorkflow()
    monkeypatch.setattr("workflows.moss_image.SCRIPT_CHECK_CHARGE", tmp_path / "missing_gate.py")
    monkeypatch.setattr("workflows.moss_image.generer_image_moss", lambda **kw: kw["output_path"])
    captured: list[str] = []
    monkeypatch.setattr(wf, "log", lambda msg, emoji="ℹ️": captured.append(msg))

    wf.run({"prompt": "stone lantern", "size": 42, "output_dir": str(tmp_path)})
    assert any("-s/--size" in msg and "--seed" in msg for msg in captured)


def test_web_assets_edge_cases_null_pagination_missing_audio_corrupt_blob(tmp_path: Path):
    from core.web_assets import normaliser_rel_path

    assert normaliser_rel_path(None) == ""
    db_path = tmp_path / "app.db"
    lib_dir = tmp_path / "lib"
    _creer_fausse_db(db_path, lib_dir)

    con = sqlite3.connect(db_path)
    # 45 blocked no-AI rows ahead of 1 valid commercial row (tests OFFSET pagination past limit*4=33)
    for idx in range(20, 65):
        rel_blocked = f"modeles_3d/fab/rogue_character_model/blocked_{idx}.wav"
        con.execute(
            "INSERT INTO assets (id, rel_path, ext, type, duration_ms, category, title, description, keywords, flag_delete) "
            "VALUES (?, ?, 'wav', 'audio', 2500, 'sfx', ?, 'blocked sfx', 'pagedtag', 0)",
            (idx, rel_blocked, f"Blocked {idx}"),
        )
        con.execute(
            "INSERT INTO assets_fts (rowid, title, description, keywords, path) VALUES (?, ?, 'blocked sfx', 'pagedtag', ?)",
            (idx, f"Blocked {idx}", rel_blocked),
        )
    con.execute(
        "INSERT INTO assets (id, rel_path, ext, type, duration_ms, category, title, description, keywords, flag_delete) "
        "VALUES (90, 'audio/kenney/ghost_only.wav', 'wav', 'audio', 3000, 'sfx', 'Ghost Missing', 'not on disk', 'pagedtag', 0)"
    )
    con.execute(
        "INSERT INTO assets_fts (rowid, title, description, keywords, path) VALUES (90, 'Ghost Missing', 'not on disk', 'pagedtag', 'audio/kenney/ghost_only.wav')"
    )
    con.execute(
        "INSERT INTO assets (id, rel_path, ext, type, duration_ms, category, title, description, keywords, flag_delete) "
        "VALUES (91, NULL, 'png', 'image', NULL, 'texture', 'Null Rel', 'null rel row', 'nullrow', 0)"
    )
    con.execute(
        "INSERT INTO assets_fts (rowid, title, description, keywords, path) VALUES (91, 'Null Rel', 'null rel row', 'nullrow', NULL)"
    )
    con.execute("DELETE FROM embeddings")
    con.execute("INSERT INTO embeddings VALUES (1, 'clip', ?)", (np.array([1.0, 0.0], dtype=np.float32).tobytes(),))
    con.execute("INSERT INTO embeddings VALUES (3, 'clip', ?)", (np.array([0.99, 0.1], dtype=np.float32).tobytes(),))
    con.execute("INSERT INTO embeddings VALUES (5, 'clip', ?)", (b"\x01\x02\x03",))
    con.execute("INSERT INTO embeddings VALUES (6, 'clip', ?)", (np.array([np.nan, 1.0], dtype=np.float32).tobytes(),))
    con.execute("INSERT INTO embeddings VALUES (4, 'clip', ?)", (np.array([0.8, 0.6], dtype=np.float32).tobytes(),))
    con.commit()
    con.close()

    # NULL rel_path does not crash search
    null_hits = rechercher_assets("Null Rel", db_path=str(db_path), library_dir=str(lib_dir))
    assert any(h["id"] == 91 and h["rel_path"] == "" for h in null_hits)

    # Pagination skips all 45 excluded rows and finds surviving id=90
    paged_hits = rechercher_assets("pagedtag", limit=1, exclude_no_ai=True, db_path=str(db_path), library_dir=str(lib_dir))
    assert len(paged_hits) == 1 and paged_hits[0]["id"] == 90

    # No candidate exists on disk for 'pagedtag' -> None instead of phantom path
    picked = choisir_reference_audio("pagedtag", db_path=str(db_path), library_dir=str(lib_dir))
    assert picked is None

    # Similarity skips corrupt blob (5), NaN vec (6), and no-AI id=3 -> returns valid id=4
    sims = rechercher_similaires(1, exclude_no_ai=True, limit=1, db_path=str(db_path), library_dir=str(lib_dir))
    assert [s["id"] for s in sims] == [4]


def test_licence_matrix_covers_all_registered_workflows_and_non_flux_3d():
    from workflows import WorkflowRegistry

    for wf_name in ("animal_godot", "asset_blendkit", "character_makeup", "character3d", "voix_conversion"):
        lic = classifier_licence_workflow(wf_name)
        assert lic["tier"] == LICENCE_COMMERCIAL, wf_name
        assert lic["commercial_ok"] is True

    up_lic = classifier_licence_workflow("audio_upscale")
    assert up_lic["tier"] == LICENCE_CONDITIONNELLE
    assert up_lic["commercial_ok"] is True
    assert "CC-BY-4.0" in up_lic["licence"]

    prod_workflows = [
        name for name in WorkflowRegistry.list_all()
        if WorkflowRegistry.get(name).__module__.startswith("workflows.")
    ]
    assert len(prod_workflows) >= 70
    for wf_name in prod_workflows:
        lic = classifier_licence_workflow(wf_name)
        assert "Verify upstream model weight license" not in lic["licence"], wf_name


def test_chant_score_bool_and_whole_note_cadence():
    with pytest.raises(ValueError):
        note_vers_midi(True)

    whole = compiler_partition_chant("fin.", duree_defaut=1, inscrire_bpm=False)
    assert whole == "fin<P_57><NOTE_1>"
