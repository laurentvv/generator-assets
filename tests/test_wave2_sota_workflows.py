#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit and workflow-contract tests for Wave 2 SOTA capabilities (2026-11-14)."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _creer_fausse_db_web_assets(tmp_path: Path) -> tuple[Path, Path]:
    lib_dir = tmp_path / "assets_lib"
    db_path = tmp_path / "app.db"

    # Curated CC0 PBR pair (albedo + normal + gloss, deliberately omitting height/ao)
    pbr_dir = lib_dir / "ambientcg" / "mossy_stone"
    pbr_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 64), (110, 130, 95)).save(pbr_dir / "stone_albedo.png")
    Image.new("RGB", (64, 64), (128, 128, 255)).save(pbr_dir / "stone_normal.png")
    Image.new("L", (64, 64), 200).save(pbr_dir / "stone_gloss.png")

    # Eligible curated SFX + voice clip + image, plus NO_AI item that must be excluded
    audio_dir = lib_dir / "kenney" / "sfx"
    audio_dir.mkdir(parents=True, exist_ok=True)
    wav_sfx = audio_dir / "sword_clang.wav"
    sr = 44100
    tone = 0.4 * np.sin(2 * np.pi * 440.0 * np.arange(sr * 2) / sr)
    sf.write(wav_sfx, tone, sr, subtype="PCM_16")

    img_ref = lib_dir / "kenney" / "ref_knight.png"
    Image.new("RGB", (64, 64), (90, 90, 140)).save(img_ref)

    no_ai_dir = lib_dir / "modeles_3d" / "fab" / "rogue_character_model"
    no_ai_dir.mkdir(parents=True, exist_ok=True)
    no_ai_wav = no_ai_dir / "sword_clang_forbidden.wav"
    sf.write(no_ai_wav, tone, sr, subtype="PCM_16")

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
    rows = [
        (1, "ambientcg/mossy_stone/stone_albedo.png", ".png", "image", 1200, "textures", "mossy stone albedo", "mossy stone albedo", "mossy,stone", "ambientcg::mossy_stone", "albedo", None),
        (2, "ambientcg/mossy_stone/stone_normal.png", ".png", "image", 1200, "textures", "mossy stone normal", "mossy stone normal", "mossy,stone", "ambientcg::mossy_stone", "normal", None),
        (3, "ambientcg/mossy_stone/stone_gloss.png", ".png", "image", 1200, "textures", "mossy stone gloss", "mossy stone gloss", "mossy,stone", "ambientcg::mossy_stone", "gloss", None),
        (4, "kenney/sfx/sword_clang.wav", ".wav", "audio", 88200, "sfx", "sword clang metal", "metallic sword clang", "sword,clang", None, None, 2000),
        (5, "modeles_3d/fab/rogue_character_model/sword_clang_forbidden.wav", ".wav", "audio", 88200, "sfx", "sword clang forbidden", "forbidden sfx", "sword,forbidden", None, None, 2000),
        (6, "kenney/ref_knight.png", ".png", "image", 1200, "characters", "armored knight ref", "knight armor", "knight,armor", None, None, None),
    ]
    for row in rows:
        con.execute(
            """
            INSERT INTO assets (
                id, rel_path, ext, type, size_bytes, category,
                title, description, keywords, pbr_group, pbr_role, duration_ms
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            row,
        )
        con.execute(
            "INSERT INTO assets_fts(rowid, title, description, keywords, path) VALUES (?,?,?,?,?)",
            (row[0], row[6], row[7], row[8], row[1]),
        )
    con.commit()
    con.close()
    return db_path, lib_dir


# ---------------------------------------------------------------------------
# 1. Albedo Delighting + material3d web-assets integration
# ---------------------------------------------------------------------------


def test_delight_albedo_reduces_directional_gradient_and_clamps():
    from core.pbr_deep import delight_albedo

    # Synthetic textured brick RGB with strong left-to-right lighting gradient + specular hotspot
    x = np.linspace(0.2, 1.0, 128, dtype=np.float32)[None, :]
    y = np.linspace(0.4, 0.9, 128, dtype=np.float32)[:, None]
    shade = np.clip(0.55 * x + 0.45 * y, 0.15, 1.0)
    rgb = np.stack([shade * 0.8, shade * 0.45, shade * 0.3], axis=-1)
    rgb[40:50, 80:90, :] = 0.98  # clipped white specular hotspot
    src = Image.fromarray((rgb * 255.0).round().astype(np.uint8), mode="RGB")

    unchanged = delight_albedo(src, strength=0.0)
    assert unchanged.size == src.size
    assert unchanged.mode == "RGB"

    out = delight_albedo(src, strength=0.8)
    assert out.size == src.size
    arr_in = np.asarray(src, dtype=np.float32).mean(axis=2)
    arr_out = np.asarray(out, dtype=np.float32).mean(axis=2)
    # Illumination gradient across columns is visibly flattened
    col_range_in = float(arr_in.mean(axis=0).max() - arr_in.mean(axis=0).min())
    col_range_out = float(arr_out.mean(axis=0).max() - arr_out.mean(axis=0).min())
    assert col_range_out < col_range_in * 0.6


def test_material3d_from_lib_reuses_pbr_pack_and_delights(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from workflows.material3d import Material3DWorkflow

    db_path, lib_dir = _creer_fausse_db_web_assets(tmp_path)
    monkeypatch.setenv("WEB_ASSETS_DB", str(db_path))
    monkeypatch.setenv("ASSET_LIBRARY_DIR", str(lib_dir))

    out_dir = tmp_path / "mat_out"
    wf = Material3DWorkflow({})
    res = wf.run({
        "from_lib": "mossy",
        "output": "mossy_pack",
        "output_dir": str(out_dir),
        "size": 64,
        "pbr_engine": "sobel",
        "delight": True,
    })
    assert res["delighted"] is True
    assert res["pbr_group"] == "ambientcg::mossy_stone"
    for key in ("albedo", "normal", "roughness", "height", "ao", "orm", "material_tres", "preview"):
        assert Path(res[key]).is_file(), f"Missing output {key}"


# ---------------------------------------------------------------------------
# 2. VACE structural control-map extraction & workflow wiring
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["canny", "edges_bold", "depth_proxy"])
def test_vace_control_modes_produce_rgb_uint8(mode: str):
    from core.vace_control import extraire_carte_controle_array

    rng = np.random.default_rng(42)
    img = (rng.random((64, 64, 3)) * 200 + 20).astype(np.uint8)
    img[16:48, 16:48] = 240
    ctrl = extraire_carte_controle_array(img, mode=mode)
    assert ctrl.shape == (64, 64, 3)
    assert ctrl.dtype == np.uint8


def test_video_vace_source_video_extracts_controls_automatically(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from workflows.video_vace import VideoVaceWorkflow

    src_vid = tmp_path / "driving.mp4"
    src_vid.write_bytes(b"mp4")
    ref_img = tmp_path / "ref.png"
    Image.new("RGB", (64, 64), (80, 100, 120)).save(ref_img)

    captured: list[dict] = []

    def fake_extract(video_path, output_dir, mode="canny", width=832, height=480, max_frames=None, fps=None):
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (width, height), (255, 255, 255)).save(Path(output_dir) / "frame_00001.png")
        return {"control_dir": output_dir, "frame_count": 1, "mode": mode, "resolution": f"{width}x{height}"}

    def fake_vid_vulkan(**kw):
        captured.append(kw)
        out = Path(kw["output_path"])
        out.write_bytes(b"webm")
        return str(out)

    monkeypatch.setattr("workflows.video_vace.extraire_frames_controle_video", fake_extract)
    monkeypatch.setattr("workflows.video_vace.generer_video_vulkan", fake_vid_vulkan)

    wf = VideoVaceWorkflow({})
    res = wf.run({
        "prompt": "smooth camera orbit",
        "input": str(ref_img),
        "source_video": str(src_vid),
        "control_extract": "edges_bold",
        "output_dir": str(tmp_path / "out"),
    })
    assert res["control_extract_mode"] == "edges_bold"
    assert len(captured) == 1
    assert captured[0]["control_video_dir"] == res["control_video_dir"]

    with pytest.raises(ValueError, match="control-video"):
        wf.run({"prompt": "orbit", "input": str(ref_img)})


# ---------------------------------------------------------------------------
# 3. Video QC gate + Upscale workflow protection
# ---------------------------------------------------------------------------


def test_video_qc_detects_solid_frozen_and_black_band(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from core import video_qc

    fake_mp4 = tmp_path / "clip.mp4"
    fake_mp4.write_bytes(b"mp4")

    monkeypatch.setattr(video_qc, "duree_video", lambda *_a, **_kw: 2.0)

    # Case 1: solid black/collapsed frames -> rejected
    def write_solid(_vid, _ts, dst, _ff):
        Image.new("RGB", (64, 64), (1, 1, 1)).save(dst)
        return True

    monkeypatch.setattr(video_qc, "_extraire_trame", write_solid)
    res_solid = video_qc.auditer_clip_video(str(fake_mp4))
    assert res_solid["ok"] is False
    assert any("collapsed" in msg for msg in res_solid["issues"])

    # Case 2: frozen identical high-contrast frames -> rejected
    pattern = np.zeros((64, 64, 3), dtype=np.uint8)
    pattern[:32, :32] = 220

    def write_frozen(_vid, _ts, dst, _ff):
        Image.fromarray(pattern).save(dst)
        return True

    monkeypatch.setattr(video_qc, "_extraire_trame", write_frozen)
    res_frozen = video_qc.auditer_clip_video(str(fake_mp4))
    assert res_frozen["ok"] is False
    assert any("frozen" in msg for msg in res_frozen["issues"])

    # Case 3: evolving sharp frames with bottom black band <= 16 px -> passes cleanly
    counter = {"n": 0}

    def write_motion(_vid, _ts, dst, _ff):
        idx = counter["n"]
        counter["n"] += 1
        arr = np.zeros((64, 64, 3), dtype=np.uint8)
        arr[8:30, 8 + idx * 10 : 28 + idx * 10] = 200
        Image.fromarray(arr).save(dst)
        return True

    monkeypatch.setattr(video_qc, "_extraire_trame", write_motion)
    res_bad_band = video_qc.auditer_clip_video(str(fake_mp4), max_black_band_px=16)
    assert res_bad_band["ok"] is False
    assert any("black band" in msg for msg in res_bad_band["issues"])

    counter["n"] = 0

    def write_good(_vid, _ts, dst, _ff):
        idx = counter["n"]
        counter["n"] += 1
        arr = np.full((64, 64, 3), 60, dtype=np.uint8)
        arr[10:40, 10 + idx * 10 : 30 + idx * 10] = 220
        Image.fromarray(arr).save(dst)
        return True

    monkeypatch.setattr(video_qc, "_extraire_trame", write_good)
    res_ok = video_qc.auditer_clip_video(str(fake_mp4))
    assert res_ok["ok"] is True
    assert res_ok["metrics"]["interframe_mean_diff"] > 5.0


def test_upscale_workflow_blocks_failed_qc_unless_skip_qc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from workflows.upscale import UpscaleWorkflow

    mp4 = tmp_path / "broken.mp4"
    mp4.write_bytes(b"mp4")

    monkeypatch.setattr(
        "workflows.upscale.auditer_clip_video",
        lambda *_a, **_kw: {"ok": False, "issues": ["frozen video frames detected"], "warnings": [], "metrics": {}},
    )
    called_upscale = []
    monkeypatch.setattr(
        "workflows.upscale.upscale_video",
        lambda **kw: called_upscale.append(kw) or str(tmp_path / "out.mp4"),
    )

    wf = UpscaleWorkflow({})
    with pytest.raises(RuntimeError, match="Pre-upscale video QC failed"):
        wf.run({"input": str(mp4), "output_dir": str(tmp_path)})
    assert len(called_upscale) == 0

    res = wf.run({"input": str(mp4), "output_dir": str(tmp_path), "skip_qc": True})
    assert len(called_upscale) == 1
    assert res["qc"] is None


# ---------------------------------------------------------------------------
# 4. --ref-lib routing (excluding NO_AI) + ControlNet control_type
# ---------------------------------------------------------------------------


def test_ref_lib_routes_to_sfx_voix_off_and_qwen_excluding_no_ai(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from core import web_assets
    from workflows.sfx import SFXWorkflow
    from workflows.voix_off import VoixOffWorkflow
    from workflows.qwen_image import QwenImageWorkflow

    db_path, lib_dir = _creer_fausse_db_web_assets(tmp_path)
    monkeypatch.setenv("WEB_ASSETS_DB", str(db_path))
    monkeypatch.setenv("ASSET_LIBRARY_DIR", str(lib_dir))

    # Strict NO_AI guard: sonniss asset is skipped cleanly
    with pytest.raises(FileNotFoundError, match="NO_AI excluded"):
        web_assets.resoudre_reference_web_assets("forbidden", asset_type="audio")

    # 1) sfx --ref-lib resolves kenney sword clang (no GPU)
    sfx_wf = SFXWorkflow({})
    res_sfx = sfx_wf.run({"ref_lib": "sword clang", "output_dir": str(tmp_path / "sfx_out")})
    assert res_sfx["engine"] == "web_assets"
    assert res_sfx["ref_lib_asset"] == "kenney/sfx/sword_clang.wav"
    assert Path(res_sfx["wav"]).is_file()

    # 2) voix_off --ref-lib auto-enables qwen3 cloning
    voix_calls = []
    monkeypatch.setattr(
        "workflows.voix_off.generer_voix_off",
        lambda **kw: voix_calls.append(kw) or {"wav": kw["sortie"]},
    )
    monkeypatch.setattr(
        "workflows.voix_off.finaliser_voix",
        lambda wav, **_kw: {"wav": wav, "mp3": wav.replace(".wav", ".mp3"), "lufs": -16.0},
    )
    voix_wf = VoixOffWorkflow({})
    voix_wf.run({"prompt": "Bonjour test", "ref_lib": "sword clang", "output_dir": str(tmp_path / "voix_out")})
    assert voix_calls[0]["moteur"] == "qwen3"
    assert voix_calls[0]["wav_ref"].endswith("sword_clang.wav")

    # 3) qwen_image --ref-lib injects reference image cleanly
    qwen_calls = []
    monkeypatch.setattr("workflows.qwen_image.SCRIPT_CHECK_CHARGE", SimpleNamespace(exists=lambda: False))
    monkeypatch.setattr(
        "workflows.qwen_image.generer_image_qwen21",
        lambda **kw: qwen_calls.append(kw) or kw["output_path"],
    )
    qwen_wf = QwenImageWorkflow({})
    qwen_wf.run({"prompt": "portrait", "ref_lib": "knight", "output_dir": str(tmp_path / "qwen_out")})
    assert len(qwen_calls) == 1
    assert any(p.endswith("ref_knight.png") for p in qwen_calls[0]["ref_images"])


def test_generer_image_vulkan_forwards_control_type(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from subprocess import CompletedProcess
    from core import diffusion, process
    from core.config import DEFAULT_CONTROLNET_UNION, DEFAULT_LTX_SPATIAL_UPSCALER

    assert "controlnet_union_sdxl_promax.safetensors" in DEFAULT_CONTROLNET_UNION
    assert "ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors" in DEFAULT_LTX_SPATIAL_UPSCALER

    cmds = []

    def fake_run(cmd, **_kw):
        cmds.append(list(cmd))
        out = cmd[cmd.index("-o") + 1]
        Image.new("RGB", (8, 8), (10, 20, 30)).save(out, "PNG")
        return CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(process.subprocess, "run", fake_run)
    ctrl_img = tmp_path / "canny.png"
    ctrl_img.write_bytes(b"png")

    diffusion.generer_image_vulkan(
        "ornate knight helm",
        sd_cli="fake-sd-cli",
        sd_model="juggernautXL_ragnarok.safetensors",
        control_image=str(ctrl_img),
        control_net="controlnet_union_sdxl_promax.safetensors",
        control_type="canny",
        control_strength=0.85,
    )
    assert "--control-type" in cmds[0]
    assert cmds[0][cmds[0].index("--control-type") + 1] == "canny"


def test_cinema_ltx_hires_builds_exact_validated_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from core import cinema

    fake_bin = tmp_path / "sd-cli.exe"
    fake_dit = tmp_path / "ltx.gguf"
    fake_vae = tmp_path / "ltx_vae.safetensors"
    fake_avae = tmp_path / "ltx_audio.safetensors"
    fake_llm = tmp_path / "gemma.gguf"
    upscalers_dir = tmp_path / "upscalers"
    upscalers_dir.mkdir()
    fake_upscaler = upscalers_dir / "ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors"
    for p in (fake_bin, fake_dit, fake_vae, fake_avae, fake_llm, fake_upscaler):
        p.write_bytes(b"ok")

    monkeypatch.setattr(cinema, "DEFAULT_SD_CLI_LTX", str(fake_bin))
    monkeypatch.setattr(cinema, "LTX_DIT", str(fake_dit))
    monkeypatch.setattr(cinema, "LTX_VAE", str(fake_vae))
    monkeypatch.setattr(cinema, "LTX_AUDIO_VAE", str(fake_avae))
    monkeypatch.setattr(cinema, "LTX_LLM", str(fake_llm))
    monkeypatch.setattr(cinema, "DEFAULT_LTX_SPATIAL_UPSCALER", str(fake_upscaler))

    captured = []

    def fake_run_engine(cmd, **_kw):
        captured.append(list(cmd))
        out = cmd[cmd.index("-o") + 1]
        Path(out).write_bytes(b"webm")
        return None

    monkeypatch.setattr(cinema, "run_engine", fake_run_engine)

    out_ms = str(tmp_path / "ms_hires.webm")
    cinema.generate_ltx_multishot("stormy lighthouse", out_ms, frames=33, hires=True, log_fn=lambda _m: None)
    c_ms = captured[0]
    assert c_ms[c_ms.index("-W") + 1] == "608"
    assert c_ms[c_ms.index("-H") + 1] == "352"
    assert "--hires" in c_ms
    assert c_ms[c_ms.index("--hires-upscalers-dir") + 1] == str(upscalers_dir)
    assert c_ms[c_ms.index("--hires-upscaler") + 1] == "ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0"
    assert c_ms[c_ms.index("--hires-steps") + 1] == "3"
    assert c_ms[c_ms.index("--hires-sigmas") + 1] == "0.85,0.725,0.4219,0.0"

    seed_img = tmp_path / "seed.png"
    seed_img.write_bytes(b"png")
    out_mp = str(tmp_path / "mp_base.webm")
    cinema.generer_monoplan_ltx(str(seed_img), "camera pan", out_mp, frames=65, hires=False, log_fn=lambda _m: None)
    c_mp = captured[1]
    assert "--hires" not in c_mp
    assert c_mp[c_mp.index("-W") + 1] == "832"
    assert c_mp[c_mp.index("-H") + 1] == "480"

    # Missing spatial upscaler must raise FileNotFoundError before launch
    fake_upscaler.unlink()
    with pytest.raises(FileNotFoundError):
        cinema.generate_ltx_multishot("stormy", str(tmp_path / "fail.webm"), frames=33, hires=True)


def test_video_multishot_and_monoplan_hires_workflow_routing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from workflows.monoplan_ia import MonoplanIaWorkflow
    from workflows.video_multishot import VideoMultishotWorkflow

    ms_calls = []
    monkeypatch.setattr(
        "workflows.video_multishot.generate_ltx_multishot",
        lambda **kw: ms_calls.append(kw) or kw["sortie"],
    )
    wf_ms = VideoMultishotWorkflow({})
    res_hires = wf_ms.run({"prompt": "lighthouse waves", "hires": True, "output_dir": str(tmp_path)})
    assert ms_calls[0]["frames"] == 33
    assert ms_calls[0]["hires"] is True
    assert res_hires["resolution"] == "1216x704"
    assert res_hires["hires"] is True

    res_std = wf_ms.run({"prompt": "lighthouse waves", "output_dir": str(tmp_path)})
    assert ms_calls[1]["frames"] == 65
    assert ms_calls[1]["hires"] is False
    assert res_std["resolution"] == "832x480"

    seed_img = tmp_path / "init.png"
    Image.new("RGB", (64, 64), (10, 40, 80)).save(seed_img)
    mp_calls = []

    def _fake_ltx(amorce, prompt, webm, **kw):
        mp_calls.append((amorce, kw))
        Path(webm).write_bytes(b"w")
        return webm

    def _fake_ralentir(src, dst, *_a, **_kw):
        Path(dst).write_bytes(b"m")
        return dst, 2.0

    def _fake_zoom(src, dst, *_a, **_kw):
        Path(dst).write_bytes(b"z")
        return dst

    monkeypatch.setattr("workflows.monoplan_ia.generer_monoplan_ltx", _fake_ltx)
    monkeypatch.setattr("workflows.monoplan_ia.ralentir_interp", _fake_ralentir)
    monkeypatch.setattr("workflows.monoplan_ia.zoom_pur", _fake_zoom)
    wf_mp = MonoplanIaWorkflow({})
    res_mp = wf_mp.run({
        "prompt": "slow push",
        "input": str(seed_img),
        "hires": True,
        "monoplan_frames": 33,
        "output_dir": str(tmp_path / "mp"),
    })
    assert res_mp["hires"] is True
    assert mp_calls[0][1]["hires"] is True
    with Image.open(mp_calls[0][0]) as amorce_im:
        assert amorce_im.size == (608, 352)


def test_generate_workflow_controlnet_union_promax(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from workflows.generate import GenerateWorkflow

    fake_sdxl = tmp_path / "juggernautXL_ragnarok.safetensors"
    fake_cn = tmp_path / "controlnet_union_sdxl_promax.safetensors"
    ctrl_img = tmp_path / "canny.png"
    fake_sdxl.write_bytes(b"sdxl")
    fake_cn.write_bytes(b"cn")
    Image.new("RGB", (32, 32), (255, 255, 255)).save(ctrl_img)

    calls = []
    monkeypatch.setattr(
        "workflows.generate.generer_image_vulkan",
        lambda **kw: calls.append(kw) or Image.new("RGB", (kw["width"], kw["height"]), (50, 60, 70)),
    )

    wf = GenerateWorkflow({
        "sd_model": "flux1-dev-Q6_K.gguf",
        "controlnet_sd_model": str(fake_sdxl),
        "controlnet_union": str(fake_cn),
        "style_anchor": "game art",
    })

    # Pair validation
    with pytest.raises(ValueError, match="control-image"):
        wf.run({"prompt": "helm", "control_type": "canny"})

    # Canny default strength 0.85, SDXL switch, segmenter none preserves 1024x1024
    res_canny = wf.run({
        "prompt": "paladin helm",
        "control_image": str(ctrl_img),
        "control_type": "canny",
        "segmenter": "none",
        "output_dir": str(tmp_path / "out"),
    })
    assert calls[0]["sd_model"] == str(fake_sdxl)
    assert calls[0]["control_net"] == str(fake_cn)
    assert calls[0]["control_type"] == "canny"
    assert calls[0]["control_strength"] == pytest.approx(0.85)
    assert res_canny["dimensions"] == (1024, 1024)
    assert res_canny["control_type"] == "canny"

    # Tile default strength 0.75
    wf.run({
        "prompt": "obsidian helm",
        "control_image": str(ctrl_img),
        "control_type": "tile",
        "segmenter": "none",
        "output_dir": str(tmp_path / "out"),
    })
    assert calls[1]["control_type"] == "tile"
    assert calls[1]["control_strength"] == pytest.approx(0.75)
