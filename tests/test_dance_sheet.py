#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests of the dance-sheet chain (core.dance_sheet + workflows.dance_sheet).

Conventions: pure Python on synthetic images; the sd-cli pose render and the
ffmpeg frame extraction are mocked via monkeypatch here (same policy as
tests/test_icon_lottie.py) and validated by the real-path night run
(2026-11-20, MEMORY_BANK §1.55).
"""

import pytest
from PIL import Image

from core.config import DEFAULT_FFMPEG
from core.dance_sheet import (
    FRAMING_LOCK_NOTE,
    assembler_planche,
    composer_amorce,
    grille_identite,
    poses_manquantes,
)
from workflows.dance_sheet import DanceSheetWorkflow


def _pose(tmp_path, index, size=512):
    """A synthetic pose cell (distinct shade per index)."""
    chemin = tmp_path / f"pose{index:02d}.png"
    Image.new("RGB", (size, size), (200, index * 12 % 255, 100)).save(chemin)
    return chemin


def _make_video(tmp_path):
    """A tiny 5 s 320x180 mp4 via the repo ffmpeg (covers the 3.9 s seek)."""
    import subprocess

    video = tmp_path / "clip.mp4"
    subprocess.run(
        [DEFAULT_FFMPEG, "-y", "-v", "error", "-f", "lavfi",
         "-i", "testsrc=size=320x180:rate=4:duration=5",
         "-pix_fmt", "yuv420p", str(video)],
        check=True,
    )
    assert video.exists()
    return str(video)


def test_assembler_planche_16_cells(tmp_path):
    for i in range(1, 17):
        _pose(tmp_path, i)
    sortie = tmp_path / "sheet.png"
    resultat = assembler_planche(str(tmp_path), str(sortie))
    im = Image.open(resultat)
    assert im.size == (2048, 2048)


def test_assembler_planche_refuse_missing_cell(tmp_path):
    for i in range(1, 16):  # pose16 missing
        _pose(tmp_path, i)
    with pytest.raises(FileNotFoundError):
        assembler_planche(str(tmp_path), str(tmp_path / "sheet.png"))


def test_composer_amorce_geometry(tmp_path):
    """Validated v3 geometry: inset crop, figure at FIG_H, centered on 832×480 white."""
    _pose(tmp_path, 1)
    sortie = tmp_path / "amorce.png"
    resultat = composer_amorce(str(tmp_path / "pose01.png"), str(sortie))
    im = Image.open(resultat)
    assert im.size == (832, 480)
    # corners stay white (figure centered, generous margins)
    assert im.getpixel((2, 2)) == (255, 255, 255)
    assert im.getpixel((829, 477)) == (255, 255, 255)


def test_grille_identite_2x2(tmp_path):
    video = _make_video(tmp_path)
    sortie = str(tmp_path / "grid.png")
    resultat = grille_identite(video, sortie)
    im = Image.open(resultat)
    assert im.size == (320, 180)  # half-size 2×2 of 320x180 frames


def test_poses_manquantes_resume(tmp_path):
    for i in (1, 2, 16):
        _pose(tmp_path, i)
    manquantes = poses_manquantes(str(tmp_path))
    assert manquantes == [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]


def test_generer_pose_dualref_wires_recipe(monkeypatch, tmp_path):
    """The sd-cli render carries the validated recipe: dual refs, 512², 8 steps,
    cfg 1.0, Lightning-8steps LoRA, and the framing-lock note is appended."""
    recus = {}

    def faux_generer(**kwargs):
        recus.update(kwargs)
        return Image.new("RGB", (512, 512))

    monkeypatch.setattr("core.dance_sheet.generer_image_qwen21", faux_generer)
    from core.dance_sheet import generer_pose_dualref

    ref_corps = str(tmp_path / "corps.png")
    ref_tete = str(tmp_path / "tete.png")
    Image.new("RGB", (512, 512)).save(ref_corps)
    Image.new("RGB", (512, 512)).save(ref_tete)
    generer_pose_dualref(
        "a pose prompt", str(tmp_path / "pose.png"), ref_corps, ref_tete, graine=42,
    )
    assert recus["width"] == 512 and recus["height"] == 512
    assert recus["steps"] == 8 and recus["cfg_scale"] == 1.0
    assert recus["ref_images"] == [ref_corps, ref_tete]
    assert recus["prompt"].startswith("a pose prompt")
    assert FRAMING_LOCK_NOTE in recus["prompt"]
    assert recus["loras"] and "Lightning-8steps" in recus["loras"][0][0]


def test_workflow_flags_are_declared():
    """The audit §2.2 keystone: the 6 flags exist, --dance-* namespace is clean."""
    flags = {flag for p in DanceSheetWorkflow.PARAMETRES for flag in p["flags"]}
    assert flags == {
        "--dance-dir", "--dance-ref", "--dance-ref-head",
        "--dance-prompts-dir", "--dance-no-clips", "--dance-prompt",
    }
