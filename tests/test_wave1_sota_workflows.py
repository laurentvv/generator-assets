#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit and workflow-contract tests for Wave 1 SOTA capabilities (2026-11-14)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest
import soundfile as sf
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# 1. sd-cli master-1092-5d78740 pin
# ---------------------------------------------------------------------------


def test_manifest_pins_sdcli_master_1092():
    manifest = json.loads((REPO_ROOT / "scripts" / "engines_manifest.json").read_text(encoding="utf-8"))
    sd_cli = manifest["moteurs"]["sd-cli"]
    assert "master-1092-5d78740" in sd_cli["raison_epinglage"]
    for os_key in ("windows", "linux", "macos-arm64"):
        card = sd_cli["plateformes"][os_key]
        assert card["epingle"] == "master-1092-5d78740"
        assert len(card["sha256"]) == 64


# ---------------------------------------------------------------------------
# 2. Mel/BS-RoFormer + Apollo 44.1 kHz + -1.0 dBTP headroom guard
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sep_engine", "expected_family"),
    [
        ("mel_roformer", "mel_band_roformer"),
        ("bs_roformer", "bs_roformer"),
    ],
)
def test_separation_roformer_commands_and_apollo_polish(tmp_path, monkeypatch, sep_engine, expected_family):
    from core import separation

    src = tmp_path / "song.wav"
    sf.write(src, np.zeros((4410, 2), dtype=np.float32), 44100)
    fake_model = tmp_path / f"{sep_engine}.gguf"
    fake_model.write_bytes(b"gguf")

    spec_map = {
        sep_engine: (expected_family, lambda m=str(fake_model): m, sep_engine.upper()),
    }
    monkeypatch.setattr(separation, "_ROFORMER_SPECS", spec_map)
    monkeypatch.setattr(separation, "resoudre_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(separation, "resoudre_audiocpp", lambda: "audiocpp_cli")
    monkeypatch.setattr(separation, "convertir_mp3", lambda wav, mp3, *a, **kw: mp3)

    commands = []

    def fake_run_engine(cmd, **kwargs):
        commands.append(list(cmd))
        if cmd[0] == "ffmpeg":
            Path(cmd[-1]).write_bytes(b"RIFF")
        elif cmd[0] == "audiocpp_cli":
            out_dir = Path(cmd[cmd.index("--out-dir") + 1])
            for stem in ("vocals", "instrumental"):
                sf.write(out_dir / f"{stem}.wav", np.zeros((1000, 2), dtype=np.float32), 44100)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(separation, "run_engine", fake_run_engine)
    apollo_calls = []
    monkeypatch.setattr(
        "core.audio_restore.restaurer_apollo",
        lambda src_wav, dst_wav, **kw: (
            apollo_calls.append((src_wav, dst_wav, kw)),
            sf.write(dst_wav, np.zeros((1000, 2), dtype=np.float32), 44100),
            {"sortie": dst_wav},
        )[-1],
    )

    work_dir = tmp_path / f"work_{sep_engine}"
    res = separation.retirer_voix(str(src), str(work_dir), backend="vulkan", moteur=sep_engine, apollo=True)

    assert res["moteur"] == sep_engine
    assert res["apollo"] is True
    assert len(apollo_calls) == 1
    assert apollo_calls[0][0].endswith("instrumental_raw.wav")
    assert apollo_calls[0][1].endswith("instrumental.wav")

    sep_cmds = [c for c in commands if c[0] == "audiocpp_cli"]
    assert len(sep_cmds) == 1
    cmd = sep_cmds[0]
    assert "--task" in cmd and cmd[cmd.index("--task") + 1] == "sep"
    assert "--family" in cmd and cmd[cmd.index("--family") + 1] == expected_family
    assert "--model" in cmd and cmd[cmd.index("--model") + 1] == str(fake_model)


def test_retrait_voix_workflow_dispatch_and_error(tmp_path, monkeypatch):
    from core import separation
    from workflows.retrait_voix import RetraitVoixWorkflow

    with pytest.raises(ValueError, match="Unknown separation engine"):
        separation.retirer_voix("dummy.wav", str(tmp_path), moteur="invalid_engine")

    src = tmp_path / "mix.mp3"
    src.write_bytes(b"mp3")
    wf = RetraitVoixWorkflow(config={})

    sam_calls = []
    monkeypatch.setattr(
        "workflows.retrait_voix.separate_sam_audio",
        lambda s, d: (sam_calls.append((s, d)), {"instrumental_mp3": "out.mp3", "stems_dir": d})[-1],
    )
    res_sam = wf.run({"input": str(src), "output": "demo", "sep_engine": "sam"})
    assert len(sam_calls) == 1 and res_sam["instrumental_mp3"] == "out.mp3"

    roformer_calls = []
    monkeypatch.setattr(
        "workflows.retrait_voix.retirer_voix",
        lambda s, d, **kw: (roformer_calls.append(kw), {"instrumental_mp3": "ro.mp3", "stems_dir": d})[-1],
    )
    wf.run({"input": str(src), "output": "demo", "sep_engine": "mel_roformer", "apollo": True})
    assert roformer_calls == [{"backend": "vulkan", "moteur": "mel_roformer", "apollo": True}]


def test_apollo_restore_cmd_headroom_and_licenses(tmp_path, monkeypatch):
    from core import audio_restore
    from core.config import LICENCE_COMMERCIAL, classifier_licence_workflow
    from workflows.audio_restaure import AudioRestaureWorkflow

    fake_model = tmp_path / "apollo-orig.gguf"
    fake_model.write_bytes(b"apollo")
    src = tmp_path / "input.wav"
    sf.write(src, np.full((4410, 2), 0.25, dtype=np.float32), 44100)

    monkeypatch.setattr(audio_restore, "resoudre_audiocpp", lambda: "audiocpp_cli")
    monkeypatch.setattr(audio_restore, "resoudre_ffmpeg", lambda: "ffmpeg")

    cmd_opts = audio_restore.construire_cmd_apollo(
        str(fake_model), "in.wav", "out.wav", chunk=12.0, overlap=2.0, edge_pad=0.5,
    )
    assert cmd_opts[cmd_opts.index("--family") + 1] == "apollo"
    assert "apollo.audio_chunk_duration_sec=12" in cmd_opts
    assert "apollo.audio_chunk_overlap_sec=2" in cmd_opts
    assert "apollo.edge_pad_duration_sec=0.5" in cmd_opts

    def fake_run_engine(cmd, **kwargs):
        if cmd[0] == "ffmpeg":
            sf.write(cmd[-1], np.full((4410, 2), 0.5, dtype=np.float32), 44100)
        else:
            raw_out = Path(cmd[cmd.index("--out") + 1])
            # Simulate Apollo raw full-scale 1.0 peak that must be attenuated to -1.0 dBTP.
            sf.write(raw_out, np.full((4410, 2), 1.0, dtype=np.float32), 44100, subtype="FLOAT")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(audio_restore, "run_engine", fake_run_engine)
    out_wav = tmp_path / "out_apollo.wav"
    res = audio_restore.restaurer_apollo(str(src), str(out_wav), modele=str(fake_model))
    data, sr = sf.read(out_wav)
    assert sr == 44100
    assert res["moteur"] == "apollo"
    assert float(np.max(np.abs(data))) <= 10 ** (-1.0 / 20.0) + 1e-3

    # Workflow dispatch & license classification
    monkeypatch.setattr(
        "workflows.audio_restaure.restaurer_apollo",
        lambda s, w, **kw: {"sortie": w, "modele": str(fake_model), "chunk": kw.get("chunk", 0.0), "moteur": "apollo"},
    )
    monkeypatch.setattr("workflows.audio_restaure.convertir_mp3", lambda *a, **kw: None)
    wf = AudioRestaureWorkflow(config={})
    out_wf = wf.run({"input": str(src), "output_dir": str(tmp_path), "restore_engine": "apollo"})
    assert out_wf["wav"].endswith("_apollo.wav")

    lic_reuse = classifier_licence_workflow("audio_restaure", moteur="reuse")
    lic_apollo = classifier_licence_workflow("audio_restaure", moteur="apollo")
    assert lic_reuse["tier"] == LICENCE_COMMERCIAL and "OpenMDW" in lic_reuse["licence"]
    assert lic_apollo["tier"] == LICENCE_COMMERCIAL and "MIT" in lic_apollo["licence"]


# ---------------------------------------------------------------------------
# 3. VocalRender-Pro Wave 1 zh-only verdict check
# ---------------------------------------------------------------------------


def test_chant_score_documents_vocalrender_zh_only_verdict():
    from core import chant_score

    doc = chant_score.__doc__ or ""
    assert "VocalRender-Pro" in doc
    assert "Mandarin" in doc or "zh" in doc
    assert "ACE-Step 1.5" in doc


# ---------------------------------------------------------------------------
# 4. audio_repaint: ACE-Step 1.5 repaint & SA3 Medium inpaint_audio
# ---------------------------------------------------------------------------


def test_audio_repaint_engines_and_workflow(tmp_path, monkeypatch):
    from core import music_ai
    from core.config import LICENCE_COMMERCIAL, LICENCE_CONDITIONNELLE, classifier_licence_workflow
    from workflows.audio_repaint import AudioRepaintWorkflow

    src = tmp_path / "track.wav"
    t = np.linspace(0.0, 4.0, 44100 * 4, endpoint=False, dtype=np.float32)
    tone = np.column_stack([0.25 * np.sin(2.0 * np.pi * 440.0 * t)] * 2)
    sf.write(src, tone, 44100)
    fake_gguf = tmp_path / "model.gguf"
    fake_gguf.write_bytes(b"gguf")

    monkeypatch.setattr(music_ai, "resoudre_audiocpp", lambda: "audiocpp_cli")
    monkeypatch.setattr(music_ai, "resoudre_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(music_ai, "resoudre_gguf_acestep15", lambda var="xl-turbo": str(fake_gguf))

    captured = []

    def fake_run_engine(cmd, **kwargs):
        captured.append(list(cmd))
        if cmd[0] == "ffmpeg":
            sf.write(cmd[-1], tone, 44100)
        elif cmd[0] == "audiocpp_cli":
            out = Path(cmd[cmd.index("--out") + 1])
            out.parent.mkdir(parents=True, exist_ok=True)
            sf.write(out, tone, 44100)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(music_ai, "run_engine", fake_run_engine)

    with pytest.raises(ValueError, match="Invalid repaint span"):
        music_ai.repaint_acestep(str(src), "fill", str(tmp_path / "bad.wav"), start_sec=2.0, end_sec=1.0)

    out_ace = tmp_path / "ace_out.wav"
    _, backend_ace = music_ai.repaint_acestep(
        str(src), "warm brass break", str(out_ace),
        start_sec=1.0, end_sec=2.5, variante="xl-turbo", repaint_mode="conservative",
        repaint_strength=0.65,
    )
    assert backend_ace == "cpu"
    ace_cmd = [c for c in captured if c[0] == "audiocpp_cli"][-1]
    assert ace_cmd[ace_cmd.index("--family") + 1] == "ace_step"
    assert ace_cmd[ace_cmd.index("--task-route") + 1] == "repaint"
    assert "ace_step.mem_saver=true" in ace_cmd
    assert "ace_step.repainting_start=1" in ace_cmd
    assert "ace_step.repainting_end=2.5" in ace_cmd
    assert "ace_step.repaint_mode=conservative" in ace_cmd
    assert any(arg.startswith("ace_step.dit_model_path=") for arg in ace_cmd)

    out_sa3 = tmp_path / "sa3_out.wav"
    _, backend_sa3 = music_ai.inpaint_stable_audio(
        str(src), "drum fill", str(out_sa3),
        start_sec=1.0, end_sec=2.5, strength=0.8, steps=8, modele=str(fake_gguf),
    )
    assert backend_sa3 == "vulkan"
    sa3_cmd = [c for c in captured if c[0] == "audiocpp_cli"][-1]
    assert sa3_cmd[sa3_cmd.index("--family") + 1] == "stable_audio"
    assert "stable_audio.audio_input_kind=inpaint_audio" in sa3_cmd
    assert "stable_audio.inpaint_mask_start_sec=1" in sa3_cmd
    assert "stable_audio.inpaint_mask_end_sec=2.5" in sa3_cmd
    assert "stable_audio.init_noise_level=0.8" in sa3_cmd
    assert any(arg.startswith("stable_audio.duration_sec=4.") for arg in sa3_cmd)

    # Workflow validation & license classification
    wf = AudioRepaintWorkflow(config={})
    with pytest.raises(ValueError, match="Missing repaint interval"):
        wf.run({"audio": str(src), "prompt": "solo"})

    monkeypatch.setattr("workflows.audio_repaint.convertir_mp3", lambda w, m, *a: m)
    monkeypatch.setattr("workflows.audio_repaint.inpaint_stable_audio", lambda *a, **kw: (str(out_sa3), "vulkan"))
    res_wf = wf.run({
        "audio": str(src), "prompt": "guitar solo", "output_dir": str(tmp_path),
        "repaint_engine": "sa3", "repaint_start": 1.0, "repaint_end": 2.5,
    })
    assert res_wf["engine"] == "sa3"
    assert res_wf["licence"]["tier"] == LICENCE_CONDITIONNELLE
    assert classifier_licence_workflow("audio_repaint", moteur="acestep")["tier"] == LICENCE_COMMERCIAL


# ---------------------------------------------------------------------------
# 5. Qwen-Image-2.1: -r / --llm_vision / --flash-attn on & --multi-angles
# ---------------------------------------------------------------------------


def test_qwen21_ref_vision_and_multi_angles(tmp_path, monkeypatch):
    from core import diffusion
    from workflows.qwen_image import QwenImageWorkflow

    ref_img = tmp_path / "hero.png"
    Image.new("RGB", (64, 64), (10, 20, 30)).save(ref_img)
    fake_mmproj = tmp_path / "mmproj.gguf"
    fake_mmproj.write_bytes(b"mmproj")
    lora_dir = tmp_path / "loras"
    lora_dir.mkdir()

    captured = []

    def fake_run_engine(cmd, **kwargs):
        captured.append(list(cmd))
        out = Path(cmd[cmd.index("-o") + 1])
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (512, 512), (40, 50, 60)).save(out)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(diffusion, "run_engine", fake_run_engine)
    monkeypatch.setattr(diffusion, "DEFAULT_LORA_DIRS", [str(lora_dir)])

    diffusion.generer_image_qwen21(
        prompt="<mva> front view, ceramic vase",
        sd_cli="sd-cli",
        model="m.gguf",
        vae="v.safetensors",
        llm="l.gguf",
        width=512,
        height=512,
        steps=8,
        cfg_scale=1.0,
        output_path=str(tmp_path / "single.png"),
        ref_images=[str(ref_img)],
        llm_vision=str(fake_mmproj),
        loras=["qwen21_multiple_angles_v2:0.9"],
        lora_dir=str(lora_dir),
    )
    cmd = captured[-1]
    assert "--flash-attn" in cmd and cmd[cmd.index("--flash-attn") + 1] == "on"
    assert "--fa" not in cmd
    assert cmd[cmd.index("--llm_vision") + 1] == str(fake_mmproj)
    assert cmd[cmd.index("-r") + 1] == str(ref_img)
    assert "<lora:qwen21_multiple_angles_v2:0.9>" in cmd[cmd.index("-p") + 1]

    # Workflow --multi-angles orbit -> 4 calls, turbo, <mva>, auto LoRA, single load check
    wf_calls = []
    monkeypatch.setattr("workflows.qwen_image.SCRIPT_CHECK_CHARGE", tmp_path / "missing_check.py")
    monkeypatch.setattr(
        "workflows.qwen_image.generer_image_qwen21",
        lambda **kw: wf_calls.append(kw),
    )
    wf = QwenImageWorkflow(config={})
    with pytest.raises(ValueError, match="requires a reference image"):
        wf.run({"prompt": "teapot", "multi_angles": "orbit", "output_dir": str(tmp_path)})

    res = wf.run({
        "prompt": "ceramic vase",
        "input": str(ref_img),
        "multi_angles": "orbit",
        "output_dir": str(tmp_path),
        "output": "vase",
    })
    assert len(wf_calls) == 4
    assert len(res["images"]) == 4
    for call in wf_calls:
        assert call["steps"] == 8 and call["cfg_scale"] == 1.0
        assert call["ref_images"] == [str(ref_img)]
        assert call["prompt"].startswith("<mva> ")
        assert "qwen21_multiple_angles_v2:0.9" in call["loras"]


# ---------------------------------------------------------------------------
# 6. MiniMax-H3 FL2VA & H3Ref2VAWorkflow mutual exclusions
# ---------------------------------------------------------------------------


def test_h3_fl2va_dry_run_and_workflow_guards(tmp_path, monkeypatch):
    from core import diffusion
    from workflows.h3_ref2va import H3Ref2VAWorkflow

    init_img = tmp_path / "start.png"
    end_img = tmp_path / "end.png"
    for p in (init_img, end_img):
        Image.new("RGB", (64, 64), (0, 0, 0)).save(p)
    for attr in ("DEFAULT_H3_VIDEO_VAE", "DEFAULT_H3_AUDIO_VAE", "DEFAULT_H3_LLM"):
        f = tmp_path / f"{attr}.bin"
        f.write_bytes(b"h3")
        monkeypatch.setattr(diffusion, attr, str(f))
    fl2va_model = tmp_path / "h3_fl2va.gguf"
    fl2va_model.write_bytes(b"fl2va")
    monkeypatch.setattr(diffusion, "DEFAULT_H3_FL2VA_MODEL", str(fl2va_model))

    assert diffusion.arrondir_grille_h3(10) == 22
    logs = []
    out_webm = tmp_path / "clip.webm"
    diffusion.generer_video_fl2va_h3(
        prompt="slow camera dolly forward",
        init_image=str(init_img),
        end_image=str(end_img),
        sd_cli="sd-cli",
        video_frames=5,  # <22 -> triggers short-clip warning
        output_path=str(out_webm),
        dry_run=True,
        log_fn=logs.append,
    )
    joined = "\n".join(logs)
    assert "--init-img" in joined and "--end-img" in joined
    assert "--ref-video" not in joined
    assert "too short" in joined

    wf = H3Ref2VAWorkflow(config={})
    with pytest.raises(ValueError, match="mutually exclusive"):
        wf.run({"prompt": "morph", "init_img": str(init_img), "input": str(tmp_path), "dry_run": True})
    with pytest.raises(ValueError, match="Ref2VA --ref-audio"):
        wf.run({"prompt": "morph", "init_img": str(init_img), "ref_audio": "x.wav", "dry_run": True})

    res = wf.run({
        "prompt": "smooth morph",
        "init_img": str(init_img),
        "end_img": str(end_img),
        "frames": 22,
        "output_dir": str(tmp_path),
        "dry_run": True,
    })
    assert res["mode"] == "fl2va"
    assert res["dry_run"] is True


# ---------------------------------------------------------------------------
# 7. SeedVR2 3B int8_convrot (-M vid_upscale image & video + chunk validation)
# ---------------------------------------------------------------------------


def test_seedvr2_image_alpha_and_video_remux(tmp_path, monkeypatch):
    from core import upscaler
    from workflows.upscale import UpscaleWorkflow

    sv_model = tmp_path / "seedvr2_3b_int8_convrot.safetensors"
    sv_vae = tmp_path / "seedvr2_ema_vae_fp16.safetensors"
    sv_model.write_bytes(b"sv")
    sv_vae.write_bytes(b"vae")
    monkeypatch.setattr(upscaler, "DEFAULT_SEEDVR2_MODEL", str(sv_model))
    monkeypatch.setattr(upscaler, "DEFAULT_SEEDVR2_VAE", str(sv_vae))

    commands = []

    def fake_run_engine(cmd, **kwargs):
        commands.append(list(cmd))
        if cmd[0] == "sd-cli":
            out = Path(cmd[cmd.index("-o") + 1])
            if out.suffix.lower() == ".png":
                Image.new("RGB", (32, 32), (200, 100, 50)).save(out)
            else:
                out.write_bytes(b"webm")
        elif cmd[0] == "ffmpeg" and "-i" in cmd:
            last = Path(cmd[-1])
            if last.suffix in (".mp4", ".webm"):
                last.write_bytes(b"final_video")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(upscaler, "run_engine", fake_run_engine)

    # Image + RGBA alpha preservation
    rgba_in = Image.new("RGBA", (16, 16), (10, 20, 30, 128))
    out_rgba = upscaler.upscale_seedvr2(
        rgba_in, facteur=2,
        seedvr2_model_path=str(sv_model), seedvr2_vae_path=str(sv_vae),
        sd_cli="sd-cli", seed=42,
    )
    assert out_rgba.mode == "RGBA" and out_rgba.size == (32, 32)
    assert out_rgba.getpixel((4, 4))[3] == 128
    sd_img_cmd = [c for c in commands if c[0] == "sd-cli"][-1]
    assert sd_img_cmd[sd_img_cmd.index("-M") + 1] == "vid_upscale"

    # Video chunk validation (2 rejected, 5 accepted) + audio remux
    fake_vid = tmp_path / "clip.mp4"
    fake_vid.write_bytes(b"mp4")
    with pytest.raises(ValueError, match="1 or 4n\\+1"):
        upscaler.upscale_video_seedvr2(
            str(fake_vid), str(tmp_path / "bad.mp4"), temporal_chunk_size=2, sd_cli="sd-cli",
        )

    fake_cap = MagicMock()
    fake_cap.isOpened.return_value = True
    fake_cap.get.side_effect = lambda prop: 24.0 if prop == 5 else 640.0
    monkeypatch.setattr("cv2.VideoCapture", lambda _p: fake_cap)
    monkeypatch.setattr(upscaler, "_video_possede_audio", lambda *_a: True)

    out_vid = tmp_path / "clip_up.mp4"
    upscaler.upscale_video_seedvr2(
        str(fake_vid), str(out_vid),
        facteur=2.0, temporal_chunk_size=5, sd_cli="sd-cli", ffmpeg="ffmpeg",
    )
    assert out_vid.exists()
    sd_vid_cmd = [c for c in commands if c[0] == "sd-cli"][-1]
    assert "--input-frames" in sd_vid_cmd
    assert sd_vid_cmd[sd_vid_cmd.index("--vsr-temporal-chunk-size") + 1] == "5"
    remux_cmd = [c for c in commands if c[0] == "ffmpeg"][-1]
    assert "1:a:0" in remux_cmd and "-shortest" in remux_cmd

    # Workflow dispatch with --upscale-mode seedvr2 on image
    png_in = tmp_path / "sprite.png"
    rgba_in.save(png_in)
    wf = UpscaleWorkflow(config={"sd_cli": "sd-cli"})
    res_wf = wf.run({
        "input": str(png_in),
        "upscale_mode": "seedvr2",
        "factor": 2.0,
        "output_dir": str(tmp_path),
    })
    assert res_wf["dimensions"] == (32, 32)
    assert Path(res_wf["output_path"]).exists()
