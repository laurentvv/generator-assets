#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests of the animated-icon pipeline (core.lottie_raster + workflows.icon_lottie).

Conventions: pure Python on synthetic inputs — the external binaries (node,
resvg) are mocked via monkeypatch here and validated by a separate real-path
leg (same policy as tests/test_media_export.py). The synthetic Lottie
animation is built with the python-lottie object API (no network, no files).
"""

import io
import json
import tarfile
from pathlib import Path

import pytest
from PIL import Image

from core.gif_export import encode_gif, verify_gif
from core.lottie_raster import (
    export_icon_data,
    fetch_useanimations,
    list_icons,
    load_animation,
    recolor_animation,
    render_frames,
)
from workflows.icon_lottie import IconLottieWorkflow, _parse_hex_rgb


def _synthetic_lottie_dict():
    """2-frame 32×32 red-circle Lottie built with the python-lottie object API."""
    from lottie import objects

    animation = objects.Animation()
    animation.width, animation.height, animation.frame_rate = 32, 32, 30
    animation.out_point = 4
    layer = objects.layers.ShapeLayer()
    layer.add_shape(objects.shapes.Ellipse([16, 16], [8, 8]))
    layer.add_shape(objects.shapes.Fill([1, 0, 0]))
    animation.add_layer(layer)
    return animation.to_dict()


# ============================================================================
# core.lottie_raster — extraction / loading / recoloring
# ============================================================================

def test_export_icon_data_parses_node_output(monkeypatch):
    captured = {}

    def fake_run_engine(commande, **kwargs):
        captured["commande"] = commande
        captured["stdin_script"] = commande[2]

        class Result:
            returncode = 0
            stdout = json.dumps(_synthetic_lottie_dict())
            stderr = ""

        return Result()

    monkeypatch.setattr("core.lottie_raster.run_engine", fake_run_engine)
    data = export_icon_data(Path("fake/lib/icon.js"), node="node")
    assert data["fr"] == 30
    assert data["w"] == 32
    assert "require(process.argv[1])" in captured["stdin_script"], \
        "extraction must require the module (native JS parsing)"


def test_load_animation_round_trip():
    animation = load_animation(_synthetic_lottie_dict())
    assert animation.width == 32
    assert animation.frame_rate == 30
    assert animation.out_point == 4


def test_recolor_animation_tints_all_colors_keeps_alpha():
    data = _synthetic_lottie_dict()
    recolored, skipped = recolor_animation(data, (224, 224, 224))
    assert recolored is not data, "recolor must not mutate the input"
    assert skipped == 0, "the synthetic corpus only carries flat colors"
    found = []

    def find_colors(node):
        if isinstance(node, dict):
            color = node.get("c")
            if isinstance(color, dict) and isinstance(color.get("k"), list):
                found.append(tuple(color["k"]))
            for value in node.values():
                find_colors(value)
        elif isinstance(node, list):
            for value in node:
                find_colors(value)

    find_colors(recolored)
    assert found, "at least one Lottie color must exist"
    assert all(k[:3] == pytest.approx([224 / 255, 224 / 255, 224 / 255]) for k in found)


def test_fetch_useanimations_extracts_cached_tarball(tmp_path, monkeypatch):
    """fetch is network-free when the tarball is pre-placed (mocked urlopen here)."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, payload in (("package/lib/anchor.js", "x"), ("package/lib/settings.js", "y"),
                              ("package/README.md", "skipped")):
            content = payload.encode()
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    payload = buffer.getvalue()

    import base64 as b64
    import hashlib
    fake_integrity = "sha512-" + b64.b64encode(hashlib.sha512(payload).digest()).decode()
    monkeypatch.setattr("core.lottie_raster.USEANIMATIONS_INTEGRITY", fake_integrity)

    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("core.lottie_raster.urllib.request.urlopen",
                        lambda url, timeout: FakeResponse(payload))
    lib_dir = fetch_useanimations(tmp_path / "cache")
    assert list_icons(lib_dir) == ["anchor", "settings"], "README.md must not leak into icons"
    # second call reuses the cache (no network)
    monkeypatch.setattr("core.lottie_raster.urllib.request.urlopen",
                        lambda url, timeout: (_ for _ in ()).throw(AssertionError("no network")))
    assert fetch_useanimations(tmp_path / "cache") == lib_dir


def test_fetch_useanimations_rejects_integrity_mismatch(tmp_path, monkeypatch):
    """A tampered tarball is refused before hitting the cache (sha512 gate)."""
    import base64 as b64
    import hashlib

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        content = b"x"
        info = tarfile.TarInfo("package/lib/anchor.js")
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))
    other_digest = "sha512-" + b64.b64encode(hashlib.sha512(b"not-the-tarball").digest()).decode()
    monkeypatch.setattr("core.lottie_raster.USEANIMATIONS_INTEGRITY", other_digest)

    class FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("core.lottie_raster.urllib.request.urlopen",
                        lambda url, timeout: FakeResponse(buffer.getvalue()))
    with pytest.raises(ValueError, match="integrity mismatch"):
        fetch_useanimations(tmp_path / "cache")
    assert not (tmp_path / "cache" / "pkg-3.1.1").exists(), "no cache entry on integrity failure"


def test_render_frames_uses_resvg_per_frame(monkeypatch, tmp_path):
    animation = load_animation(_synthetic_lottie_dict())
    calls = []

    def fake_run_engine(commande, **kwargs):
        calls.append(commande)
        # fake resvg: write a solid RGBA png at the output path
        Image.new("RGBA", (128, 128), (255, 0, 0, 200)).save(commande[-1])

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()

    monkeypatch.setattr("core.lottie_raster.run_engine", fake_run_engine)
    frames, fps, count = render_frames(animation, size=128, resvg_path="fake_resvg")
    assert fps == 30.0
    assert count == 5 and len(frames) == 5  # in_point 0..out_point 4
    assert len(calls) == 5
    assert calls[0][0] == "fake_resvg" and "--zoom" in calls[0]
    assert frames[0].mode == "RGBA"
    assert frames[0].size == (128, 128)


# ============================================================================
# workflows.icon_lottie
# ============================================================================

def test_parse_hex_rgb_valid_and_invalid():
    assert _parse_hex_rgb("E0E0E0") == (224, 224, 224)
    assert _parse_hex_rgb("#ff0000") == (255, 0, 0)
    assert _parse_hex_rgb(None) is None
    with pytest.raises(ValueError, match="six hexadecimal"):
        _parse_hex_rgb("red")
    with pytest.raises(ValueError, match="six hexadecimal"):
        _parse_hex_rgb("FFFF")


def _patch_pipeline(monkeypatch, tmp_path):
    """Patches the whole external-binary chain for a pure end-to-end run."""
    lib_dir = tmp_path / "lib"
    lib_dir.mkdir()
    (lib_dir / "anchor.js").write_text("stub", encoding="utf-8")
    (lib_dir / "settings.js").write_text("stub", encoding="utf-8")

    monkeypatch.setattr("workflows.icon_lottie.fetch_useanimations", lambda cache: lib_dir)
    monkeypatch.setattr("workflows.icon_lottie.export_icon_data",
                        lambda js: _synthetic_lottie_dict())

    def fake_render(animation, size=128, resvg_path=None, timeout=120.0):
        frames = [Image.new("RGBA", (size, size), (255, 0, 0, 255)) for _ in range(5)]
        return frames, 30.0, 5

    monkeypatch.setattr("workflows.icon_lottie.render_frames", fake_render)
    monkeypatch.setattr("workflows.icon_lottie.resolve_resvg", lambda: "fake_resvg")


def test_icon_lottie_workflow_end_to_end(tmp_path, monkeypatch):
    _patch_pipeline(monkeypatch, tmp_path)
    result = IconLottieWorkflow(config={}).run(dict(
        icon="anchor", size=128, output_dir=str(tmp_path)))
    done = result["icons_done"][0]
    run_dir = Path(done["run_dir"])
    assert Path(done["gif"]).exists()
    assert Path(done["apng"]).exists()
    assert Path(done["contact_sheet"]).exists()
    assert done["frames"] == 5 and done["duration_ms"] > 0
    assert done["qc"]["technical_pass"] is True
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["icon"] == "anchor"
    assert manifest["tint_rgb"] is None
    assert manifest["package"].startswith("react-useanimations@")


def test_icon_lottie_workflow_tint_and_multiple_icons(tmp_path, monkeypatch):
    _patch_pipeline(monkeypatch, tmp_path)
    result = IconLottieWorkflow(config={}).run(dict(
        icon="anchor,settings", size=64, lottie_color="E0E0E0", output_dir=str(tmp_path)))
    assert result["count"] == 2
    manifests = [Path(item["run_dir"]) / "manifest.json" for item in result["icons_done"]]
    parsed = [json.loads(m.read_text(encoding="utf-8")) for m in manifests]
    assert parsed[0]["tint_rgb"] == [224, 224, 224]
    assert parsed[1]["icon"] == "settings"


def test_icon_lottie_workflow_unknown_icon(tmp_path, monkeypatch):
    _patch_pipeline(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="Unknown icon"):
        IconLottieWorkflow(config={}).run(dict(icon="nope", output_dir=str(tmp_path)))


def test_icon_lottie_workflow_requires_icon(tmp_path, monkeypatch):
    _patch_pipeline(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="--icon"):
        IconLottieWorkflow(config={}).run(dict(output_dir=str(tmp_path)))


def test_icon_lottie_workflow_list_icons(tmp_path, monkeypatch):
    _patch_pipeline(monkeypatch, tmp_path)
    result = IconLottieWorkflow(config={}).run(dict(list_icons=True, output_dir=str(tmp_path)))
    assert result["icons"] == ["anchor", "settings"]


def test_gif_encode_from_rendered_frames(tmp_path):
    """Frames from render_frames feed the gif_export machinery unchanged."""
    frames = [Image.new("RGBA", (128, 128), (255, 0, 0, 255)) for _ in range(3)]
    durations = [100, 100, 100]
    target = tmp_path / "icon.gif"
    encode_gif(frames, durations, target)
    qc = verify_gif(target, frames, durations)
    assert qc["alpha_mismatch_pixels"] == 0
