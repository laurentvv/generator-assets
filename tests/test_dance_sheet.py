#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests of the dance-sheet chain (core.dance_sheet + workflows.dance_sheet).

Conventions: pure Python on synthetic images; the sd-cli pose render and the
ffmpeg frame extraction are mocked via monkeypatch here (same policy as
tests/test_icon_lottie.py) and validated by the real-path night run
(2026-11-20, MEMORY_BANK §1.55).
"""

import os

import pytest
from PIL import Image

from core.config import DEFAULT_FFMPEG
from core.dance_sheet import (
    FRAMING_LOCK_NOTE,
    assemble_sheet,
    compose_seed_frame,
    identity_grid,
    missing_poses,
    render_pose_dualref,
)
from workflows.dance_sheet import DanceSheetWorkflow, _seed_param


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


def test_assemble_sheet_16_cells(tmp_path):
    for i in range(1, 17):
        _pose(tmp_path, i)
    sortie = tmp_path / "sheet.png"
    resultat = assemble_sheet(str(tmp_path), str(sortie))
    im = Image.open(resultat)
    assert im.size == (2048, 2048)


def test_assemble_sheet_refuses_missing_cell(tmp_path):
    for i in range(1, 16):  # pose16 missing
        _pose(tmp_path, i)
    with pytest.raises(FileNotFoundError):
        assemble_sheet(str(tmp_path), str(tmp_path / "sheet.png"))


def test_assemble_sheet_refuses_heterogeneous_cells(tmp_path):
    """Review P2: a stale larger cell (resume across resolutions) misaligns rows."""
    for i in range(1, 16):
        _pose(tmp_path, i)
    Image.new("RGB", (768, 768)).save(tmp_path / "pose16.png")
    with pytest.raises(ValueError):
        assemble_sheet(str(tmp_path), str(tmp_path / "sheet.png"))


def test_compose_seed_frame_geometry(tmp_path):
    """Validated v3 geometry: inset crop, figure at FIG_H, centered on 832×480 white."""
    _pose(tmp_path, 1)
    sortie = tmp_path / "amorce.png"
    resultat = compose_seed_frame(str(tmp_path / "pose01.png"), str(sortie))
    im = Image.open(resultat)
    assert im.size == (832, 480)
    # corners stay white (figure centered, generous margins)
    assert im.getpixel((2, 2)) == (255, 255, 255)
    assert im.getpixel((829, 477)) == (255, 255, 255)


def test_identity_grid_2x2(tmp_path):
    video = _make_video(tmp_path)
    sortie = str(tmp_path / "grid.png")
    resultat = identity_grid(video, sortie)
    im = Image.open(resultat)
    assert im.size == (320, 180)  # half-size 2×2 of 320x180 frames


def test_missing_poses_resume(tmp_path):
    for i in (1, 2, 16):
        _pose(tmp_path, i)
    manquantes = missing_poses(str(tmp_path))
    assert manquantes == [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]


def test_render_pose_dualref_wires_recipe(monkeypatch, tmp_path):
    """The sd-cli render carries the validated recipe: dual refs, 512², 8 steps,
    cfg 1.0, Lightning-8steps LoRA, and the framing-lock note is appended."""
    recus = {}

    def faux_generer(**kwargs):
        recus.update(kwargs)
        return Image.new("RGB", (512, 512))

    monkeypatch.setattr("core.dance_sheet.generer_image_qwen21", faux_generer)

    ref_body = str(tmp_path / "corps.png")
    ref_head = str(tmp_path / "tete.png")
    Image.new("RGB", (512, 512)).save(ref_body)
    Image.new("RGB", (512, 512)).save(ref_head)
    render_pose_dualref(
        "a pose prompt", str(tmp_path / "pose.png"), ref_body, ref_head, seed=42,
    )
    assert recus["width"] == 512 and recus["height"] == 512
    assert recus["steps"] == 8 and recus["cfg_scale"] == 1.0
    assert recus["ref_images"] == [ref_body, ref_head]
    assert recus["prompt"].startswith("a pose prompt")
    assert FRAMING_LOCK_NOTE in recus["prompt"]
    assert recus["loras"] and "Lightning-8steps" in recus["loras"][0][0]


def test_workflow_strips_file_lora_tag_single_tag_in_final_prompt(monkeypatch, tmp_path):
    """Review P0: pose prompt files carry the Lightning tag; the plumbing must
    keep exactly ONE tag in the final prompt (sd-cli ACCUMULATES duplicates ->
    strength 2.0 instead of 1.0)."""
    import re

    prompts_dir = tmp_path / "prompts16"
    prompts_dir.mkdir()
    for i in range(1, 17):
        (prompts_dir / f"pose{i:02d}.txt").write_text(
            "<lora:Qwen-Image-Edit-2511-Lightning-8steps-V1.0-bf16:1.0>\nUsing the man"
            " from the reference photo, standing pose.\n",
            encoding="utf-8",
        )
    recus = {}

    def faux_render(**kwargs):
        recus.update(kwargs)
        os.makedirs(os.path.dirname(kwargs["output_path"]) or ".", exist_ok=True)
        Image.new("RGB", (512, 512)).save(kwargs["output_path"])

    import subprocess

    # Patch at the workflow's import site (from-import binds the name there).
    monkeypatch.setattr("workflows.dance_sheet.render_pose_dualref", faux_render)
    # Hermetic test: the load gate must not depend on the machine state.
    monkeypatch.setattr(
        "workflows.dance_sheet.run_engine",
        lambda *a, **k: subprocess.CompletedProcess([], 0, stdout="", stderr=""),
    )
    ref = str(tmp_path / "ref.png")
    Image.new("RGB", (512, 512)).save(ref)

    workflow = DanceSheetWorkflow()
    workflow.run({
        "prompt": "dance sheet test",
        "dance_dir": str(tmp_path),
        "dance_ref": ref,
        "dance_ref_head": ref,
        "dance_prompts_dir": str(prompts_dir),
        "dance_no_clips": True,
        "seed": 42,
        "output_dir": str(tmp_path / "out"),
    })
    prompt_final = recus["prompt"]
    # Layer 1 (workflow): the file tag is stripped — zero tags in the text
    # handed to the renderer. Layer 2 (render_pose_dualref, tested in
    # test_render_pose_dualref_wires_recipe): the plumbing appends EXACTLY ONE
    # tag -> final prompt = 1 tag, not 2 (sd-cli accumulates duplicates).
    assert len(re.findall(r"<lora:", prompt_final)) == 0
    assert prompt_final.startswith("Using the man")


def test_seed_param_freezes_random_and_keeps_zero():
    """Review P1: the flat --seed flag defaults to -1 (sd-cli random); only
    None/negative fall back to 42 — explicit 0 stays 0."""
    assert _seed_param({"seed": None}) == 42
    assert _seed_param({}) == 42
    assert _seed_param({"seed": -1}) == 42
    assert _seed_param({"seed": 42}) == 42
    assert _seed_param({"seed": 0}) == 0


def test_workflow_flags_are_declared():
    """The audit §2.2 keystone: the 6 flags exist, --dance-* namespace is clean."""
    flags = {flag for p in DanceSheetWorkflow.PARAMETRES for flag in p["flags"]}
    assert flags == {
        "--dance-dir", "--dance-ref", "--dance-ref-head",
        "--dance-prompts-dir", "--dance-no-clips", "--dance-prompt",
    }
