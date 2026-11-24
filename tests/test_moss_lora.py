#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for the moss_image lora-4step variant (USER VALIDATED 2026-11-24).

All engine calls are mocked via monkeypatch — same policy as
tests/test_voix_indextts.py: the real-path e2e runs separately on the GPU.
The generer_image_moss tests feed every staged file from tmp_path (C:) so the
NVMe stager yields them unchanged (it only copies from slow drives).
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from core import diffusion
from core.config import DEFAULT_MOSS_IMAGE_4STEP_LORA, DEFAULT_MOSS_IMAGE_LORA_BASE_MODEL
from workflows.moss_image import MossImageWorkflow


def _fake_files(tmp_path: Path) -> dict:
    """Creates tiny stand-in files so the stager and existence checks pass."""
    files = {}
    for name in ("model", "llm", "vae", "tokenizer", "lora"):
        p = tmp_path / f"{name}.bin"
        p.write_bytes(b"x")
        files[name] = str(p)
    return files


def _capture_run_engine(monkeypatch):
    captured = []

    def fake(commande, **kwargs):
        captured.append(list(commande))
        # mimic the engine: the caller re-opens the file with PIL afterwards
        out = commande[commande.index("-o") + 1]
        from PIL import Image

        Image.new("RGB", (4, 4), "white").save(out)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(diffusion, "run_engine", fake)
    return captured


def test_moss_lora_builds_lora_flags_and_prompt_tag(monkeypatch, tmp_path):
    files = _fake_files(tmp_path)
    captured = _capture_run_engine(monkeypatch)

    diffusion.generer_image_moss(
        prompt="a shield with the text MOSS",
        model=files["model"],
        llm=files["llm"],
        vae=files["vae"],
        tokenizer=files["tokenizer"],
        steps=4,
        cfg_scale=1.0,
        seed=42,
        output_path=str(tmp_path / "out.png"),
        lora_path=files["lora"],
        base_model=files["model"],
    )

    cmd = captured[0]
    assert "--lora-model-dir" in cmd
    assert "--lora-apply-mode" in cmd
    assert cmd[cmd.index("--lora-apply-mode") + 1] == "auto"
    assert "<lora:moss_sft_4step_rank_64_lora:1.0>" in cmd[cmd.index("-p") + 1]
    # the validated recipe passes through untouched
    assert cmd[cmd.index("--steps") + 1] == "4"
    assert cmd[cmd.index("--cfg-scale") + 1] == "1.0"


def test_moss_base_has_no_lora_flags(monkeypatch, tmp_path):
    files = _fake_files(tmp_path)
    captured = _capture_run_engine(monkeypatch)

    diffusion.generer_image_moss(
        prompt="a shield",
        model=files["model"],
        llm=files["llm"],
        vae=files["vae"],
        tokenizer=files["tokenizer"],
        output_path=str(tmp_path / "out.png"),
    )

    cmd = captured[0]
    assert "--lora-model-dir" not in cmd
    assert "<lora:" not in cmd


def test_moss_lora_missing_file_is_refused(monkeypatch, tmp_path):
    with pytest.raises(FileNotFoundError):
        diffusion.generer_image_moss(
            prompt="a shield",
            model=str(tmp_path / "none.bin"),
            llm=str(tmp_path / "none.bin"),
            vae=str(tmp_path / "none.bin"),
            tokenizer=str(tmp_path / "none.bin"),
            output_path=str(tmp_path / "out.png"),
            lora_path=str(tmp_path / "absent.safetensors"),
            base_model=str(tmp_path / "none.bin"),
        )


def _patch_workflow(monkeypatch, tmp_path):
    """Routes the load gate to green and captures generer_image_moss kwargs."""
    monkeypatch.setattr(
        "workflows.moss_image.run_engine",
        lambda *a, **k: SimpleNamespace(returncode=0),
    )
    captured = {}
    monkeypatch.setattr(
        "workflows.moss_image.generer_image_moss",
        lambda **kwargs: captured.update(kwargs) or {"image": kwargs["output_path"]},
    )
    wf = MossImageWorkflow()
    return wf, captured


def test_workflow_base_variant_keeps_teacher_recipe(monkeypatch, tmp_path):
    wf, captured = _patch_workflow(monkeypatch, tmp_path)
    wf.run({
        "prompt": "a shield",
        "output_dir": str(tmp_path),
        "seed": 42,
    })
    assert captured["lora_path"] is None
    assert captured["base_model"] is None
    assert captured["steps"] == 50
    assert captured["cfg_scale"] == 3.0


def test_workflow_lora4step_pins_recipe_and_routes_q80_base(monkeypatch, tmp_path):
    wf, captured = _patch_workflow(monkeypatch, tmp_path)
    wf.run({
        "prompt": "a shield",
        "output_dir": str(tmp_path),
        "seed": 42,
        "moss_variante": "lora-4step",
    })
    assert captured["lora_path"] == str(Path(DEFAULT_MOSS_IMAGE_4STEP_LORA))
    assert captured["base_model"] == DEFAULT_MOSS_IMAGE_LORA_BASE_MODEL
    assert captured["steps"] == 4
    assert captured["cfg_scale"] == 1.0
    # recipe pins survive explicit conflicting values
    wf.run({
        "prompt": "a shield",
        "output_dir": str(tmp_path),
        "moss_variante": "lora-4step",
        "steps": 25,
        "cfg_scale": 3.0,
    })
    assert captured["steps"] == 4
    assert captured["cfg_scale"] == 1.0
