#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for the Wan2.2-S2V Speech-to-Video workflow (`video_s2v`)."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import diffusion
from core.config import DEFAULT_WAN_S2V_TURBO_LORA
from workflows import WorkflowRegistry
from workflows import video_s2v as wf_mod


def _creer_assets_s2v_factices(base: Path) -> dict[str, Path]:
    img = base / "portrait.png"
    wav = base / "speech.wav"
    model = base / "Wan2.2-S2V-14B-Q4_K_M.gguf"
    t5 = base / "umt5-xxl-encoder-Q4_K_M.gguf"
    vae = base / "wan_2.1_vae.safetensors"
    audio_enc = base / "wav2vec2_large_english_fp16.safetensors"
    lora_dir = base / "loras"
    lora_dir.mkdir(parents=True, exist_ok=True)
    for p, content in (
        (img, b"PNG"),
        (wav, b"RIFF"),
        (model, b"MODEL_BYTES"),
        (t5, b"T5_BYTES"),
        (vae, b"VAE_BYTES"),
        (audio_enc, b"WAV2VEC2_BYTES"),
    ):
        p.write_bytes(content)
    return {
        "img": img,
        "wav": wav,
        "model": model,
        "t5": t5,
        "vae": vae,
        "audio_encoder": audio_enc,
        "lora_dir": lora_dir,
    }


def _patch_virtual_slow_drive(monkeypatch: pytest.MonkeyPatch, cold_root: Path, nvme_root: Path) -> None:
    cold_prefix = str(cold_root.resolve()).lower()
    nvme_prefix = str(nvme_root.resolve()).lower()

    def _fake_splitdrive(path: str):
        p_norm = os.path.abspath(path).lower()
        if p_norm.startswith(cold_prefix):
            return ("D:", path[len(str(cold_root)):])
        if p_norm.startswith(nvme_prefix):
            return ("C:", path[len(str(nvme_root)):])
        return ("C:", path)

    monkeypatch.setattr(diffusion.os.path, "splitdrive", _fake_splitdrive)


def test_nvme_staging_copies_cold_files_and_cleans_up(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cold = tmp_path / "cold"
    nvme = tmp_path / "nvme"
    cold.mkdir()
    nvme.mkdir()
    cold_model = cold / "s2v.gguf"
    cold_enc = cold / "enc.safetensors"
    nvme_vae = nvme / "vae.safetensors"
    cold_model.write_bytes(b"A" * 4096)
    cold_enc.write_bytes(b"B" * 1024)
    nvme_vae.write_bytes(b"C" * 512)

    _patch_virtual_slow_drive(monkeypatch, cold, nvme)
    logs: list[str] = []
    staged_dir: Path | None = None

    with diffusion._stager_vers_nvme_temporaire(
        {
            "model": str(cold_model),
            "model_alias": str(cold_model),
            "audio_encoder": str(cold_enc),
            "vae": str(nvme_vae),
        },
        nvme_root=str(nvme),
        min_free_margin_bytes=1024,
        log_fn=logs.append,
    ) as staged:
        staged_model = Path(staged["model"])
        staged_dir = staged_model.parent
        assert staged_model.parent == nvme / staged_dir.name
        assert staged_dir.name.startswith("_tmp_s2v_")
        assert staged["model"] == staged["model_alias"]
        assert staged_model.read_bytes() == b"A" * 4096
        assert Path(staged["audio_encoder"]).read_bytes() == b"B" * 1024
        assert staged["vae"] == str(nvme_vae)

    assert staged_dir is not None and not staged_dir.exists()
    assert any("Temporary copy cleaned" in msg for msg in logs)


def test_nvme_staging_cleans_up_on_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cold = tmp_path / "cold"
    nvme = tmp_path / "nvme"
    cold.mkdir()
    nvme.mkdir()
    cold_file = cold / "model.gguf"
    cold_file.write_bytes(b"PAYLOAD")

    _patch_virtual_slow_drive(monkeypatch, cold, nvme)
    staged_dir: Path | None = None

    with pytest.raises(RuntimeError, match="boom"):
        with diffusion._stager_vers_nvme_temporaire(
            {"model": str(cold_file)},
            nvme_root=str(nvme),
            min_free_margin_bytes=1024,
            log_fn=lambda *_: None,
        ) as staged:
            staged_dir = Path(staged["model"]).parent
            assert staged_dir.exists()
            raise RuntimeError("boom")

    assert staged_dir is not None and not staged_dir.exists()


def test_nvme_staging_disabled_and_low_space(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cold = tmp_path / "cold"
    nvme = tmp_path / "nvme"
    cold.mkdir()
    nvme.mkdir()
    cold_file = cold / "model.gguf"
    cold_file.write_bytes(b"Z" * 2048)

    with diffusion._stager_vers_nvme_temporaire(
        {"model": str(cold_file)},
        nvme_root=str(nvme),
        enabled=False,
    ) as unchanged:
        assert unchanged == {"model": str(cold_file)}

    _patch_virtual_slow_drive(monkeypatch, cold, nvme)
    monkeypatch.setattr(diffusion.shutil, "disk_usage", lambda _p: SimpleNamespace(total=1000, used=900, free=100))

    with pytest.raises(OSError, match="Insufficient free space"):
        with diffusion._stager_vers_nvme_temporaire(
            {"model": str(cold_file)},
            nvme_root=str(nvme),
            min_free_margin_bytes=1024,
        ):
            pass


def test_preparer_wav_s2v_direct_and_transcode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wav = tmp_path / "voice.wav"
    wav.write_bytes(b"RIFF")
    called: list[list[str]] = []
    monkeypatch.setattr(diffusion, "run_engine", lambda cmd, **kw: called.append(cmd))

    with diffusion._preparer_wav_s2v(str(wav)) as effective_wav:
        assert effective_wav == str(wav)
    assert called == []

    mp3 = tmp_path / "voice.mp3"
    mp3.write_bytes(b"ID3")
    with diffusion._preparer_wav_s2v(str(mp3)) as converted_wav:
        assert converted_wav.endswith(".wav")
        assert os.path.exists(converted_wav)
        assert len(called) == 1
        assert "-ar" in called[0] and "24000" in called[0]
        assert "pcm_s16le" in called[0]
    assert not os.path.exists(converted_wav)


def test_generer_video_s2v_wan_dry_run_flags_and_token_warning(tmp_path: Path) -> None:
    assets = _creer_assets_s2v_factices(tmp_path)
    logs: list[str] = []

    out = diffusion.generer_video_s2v_wan(
        prompt="A monk speaking calmly",
        init_image=str(assets["img"]),
        audio_path=str(assets["wav"]),
        sd_cli="sd-cli.exe",
        model_path=str(assets["model"]),
        t5xxl_path=str(assets["t5"]),
        vae_path=str(assets["vae"]),
        audio_encoder_path=str(assets["audio_encoder"]),
        lora_dir=str(assets["lora_dir"]),
        width=832,
        height=480,
        video_frames=33,
        steps=4,
        output_path=str(tmp_path / "out.mp4"),
        dry_run=True,
        log_fn=logs.append,
    )

    assert out.endswith(".webm")
    joined = "\n".join(logs)
    assert "14040 tokens" in joined and "9,216" in joined
    assert "-M vid_gen" in joined
    assert "--sampling-method euler" in joined
    assert "--flow-shift 3.0" in joined
    assert "--backend diffusion=vulkan0,te=cpu,vae=cpu" in joined
    assert "--max-vram 10" in joined
    assert "--offload-to-cpu" in joined
    assert "--vae-tiling" in joined
    assert "--flash-attn off,diffusion=on" in joined
    assert "--rng cpu" in joined
    assert "--lora-apply-mode auto" in joined
    assert f"<lora:{DEFAULT_WAN_S2V_TURBO_LORA}:1.0>" in joined


def test_generer_video_s2v_wan_missing_models_raises(tmp_path: Path) -> None:
    assets = _creer_assets_s2v_factices(tmp_path)
    with pytest.raises(FileNotFoundError, match="Missing Wan2.2-S2V models"):
        diffusion.generer_video_s2v_wan(
            prompt="hello",
            init_image=str(assets["img"]),
            audio_path=str(assets["wav"]),
            model_path=str(tmp_path / "missing_s2v.gguf"),
            t5xxl_path=str(assets["t5"]),
            vae_path=str(assets["vae"]),
            audio_encoder_path=str(assets["audio_encoder"]),
            lora_dir=str(assets["lora_dir"]),
        )


def test_generer_video_s2v_wan_executes_sd_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assets = _creer_assets_s2v_factices(tmp_path)
    out_webm = tmp_path / "out" / "talk.webm"
    captured_cmds: list[list[str]] = []

    def _fake_run_engine(cmd, **kwargs):
        captured_cmds.append(cmd)
        out_webm.parent.mkdir(parents=True, exist_ok=True)
        out_webm.write_bytes(b"WEBM")
        assert kwargs.get("check") is True
        assert kwargs.get("timeout") == 7200
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(diffusion, "run_engine", _fake_run_engine)
    res = diffusion.generer_video_s2v_wan(
        prompt="speak clearly",
        init_image=str(assets["img"]),
        audio_path=str(assets["wav"]),
        sd_cli="sd-cli.exe",
        model_path=str(assets["model"]),
        t5xxl_path=str(assets["t5"]),
        vae_path=str(assets["vae"]),
        audio_encoder_path=str(assets["audio_encoder"]),
        lora_dir=str(assets["lora_dir"]),
        output_path=str(out_webm),
        stage_to_nvme=False,
    )

    assert res == str(out_webm)
    assert out_webm.exists()
    assert len(captured_cmds) == 1
    assert "--audio-encoder" in captured_cmds[0]


def test_video_s2v_workflow_registered_and_validates_inputs(tmp_path: Path) -> None:
    cls = WorkflowRegistry.get("video_s2v")
    assert cls is wf_mod.VideoS2VWorkflow
    wf = cls(config={})

    with pytest.raises(ValueError, match="portrait image"):
        wf.run({})

    with pytest.raises(FileNotFoundError, match="Portrait image"):
        wf.run({"input": str(tmp_path / "nope.png"), "audio": str(tmp_path / "a.wav")})

    img = tmp_path / "portrait.png"
    img.write_bytes(b"PNG")
    with pytest.raises(ValueError, match="driving speech"):
        wf.run({"input": str(img)})

    with pytest.raises(FileNotFoundError, match="Driving audio"):
        wf.run({"input": str(img), "audio": str(tmp_path / "missing.wav")})


def test_video_s2v_workflow_maps_global_defaults_and_lora_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assets = _creer_assets_s2v_factices(tmp_path)
    recorded: dict[str, object] = {}

    def _fake_gen(**kwargs):
        recorded.update(kwargs)
        return kwargs["output_path"]

    monkeypatch.setattr(wf_mod, "generer_video_s2v_wan", _fake_gen)
    wf = wf_mod.VideoS2VWorkflow(config={"sd_cli": "sd-cli.exe", "threads": 8})

    res = wf.run({
        "input": str(assets["img"]),
        "audio": str(assets["wav"]),
        "steps": 25,
        "lora": "none",
        "dry_run": True,
        "output_dir": str(tmp_path),
    })

    assert recorded["steps"] == 4
    assert recorded["loras"] == []
    assert recorded["width"] == 512
    assert recorded["height"] == 512
    assert recorded["video_frames"] == 33
    assert recorded["fps"] == 16
    assert recorded["threads"] == 8
    assert res["steps"] == 4
    assert res["dry_run"] is True
    assert res["mp4_path"] is None


def test_video_s2v_workflow_load_gate_and_live_remux_qc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assets = _creer_assets_s2v_factices(tmp_path)
    wf = wf_mod.VideoS2VWorkflow(config={"sd_cli": "sd-cli.exe"})

    # 1. Busy load gate aborts before invoking sd-cli.
    monkeypatch.setattr(wf_mod, "run_engine", lambda *a, **kw: SimpleNamespace(returncode=1))
    with pytest.raises(RuntimeError, match="Busy machine"):
        wf.run({
            "input": str(assets["img"]),
            "audio": str(assets["wav"]),
            "output_dir": str(tmp_path),
        })

    # 2. Clean load gate -> generate .webm -> remux .mp4 -> video QC.
    def _fake_gen(**kwargs):
        Path(kwargs["output_path"]).write_bytes(b"WEBM")
        return kwargs["output_path"]

    def _fake_run_engine(cmd, **kwargs):
        if Path(cmd[-1]).suffix == ".mp4":
            Path(cmd[-1]).write_bytes(b"MP4")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(wf_mod, "generer_video_s2v_wan", _fake_gen)
    monkeypatch.setattr(wf_mod, "run_engine", _fake_run_engine)
    monkeypatch.setattr(
        wf_mod,
        "auditer_clip_video",
        lambda path: {"ok": True, "metrics": {"max_bottom_black_px": 0}, "issues": []},
    )

    res = wf.run({
        "input": str(assets["img"]),
        "audio": str(assets["wav"]),
        "output": "monk_talk.mp4",
        "output_dir": str(tmp_path),
    })

    assert res["status"] == "success"
    assert res["webm_path"].endswith("monk_talk.webm")
    assert res["mp4_path"].endswith("monk_talk.mp4")
    assert res["video_path"] == res["mp4_path"]
    assert res["qc"] == {"ok": True, "metrics": {"max_bottom_black_px": 0}, "issues": []}
