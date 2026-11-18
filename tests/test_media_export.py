#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests of the media-export port (core.gif_export / core.alpha_qa /
core.beat_grid + the gif_export / alpha_qa / beat_sync workflows).

Conventions: pure Pillow/numpy on synthetic inputs, no engine subprocess
in pytest (the FFmpeg video path is validated by a separate real-path leg,
not here — same policy as test_wave2_sota_workflows.py). The metronome
helper mirrors tests/test_unit.py::_clics (8 kHz so the native WAV path of
core.beat_grid.decode_mono applies).
"""

import json
import wave
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageSequence

from core.alpha_qa import alpha_qa_report
from core.beat_grid import (
    allocate_exposures,
    analyze_beats,
    drift_report,
    envelope_arrays,
    schedule_beat_cycles,
)
from core.gif_export import (
    build_contact_sheet,
    compute_frame_timing,
    encode_apng,
    encode_gif,
    merge_browser_gif_timing,
    verify_gif,
)
from workflows.alpha_qa import AlphaQaWorkflow
from workflows.beat_sync import BeatSyncWorkflow
from workflows.gif_export import GifExportWorkflow

SR = 8000


# ============================================================================
# Synthetic input helpers
# ============================================================================

def _metronome(bpm: float, duree_s: float, sr: int = SR) -> np.ndarray:
    """Metronome clicks (decaying sine peak) at a given BPM (mono float32)."""
    n = int(duree_s * sr)
    audio = np.zeros(n)
    periode = int(60.0 / bpm * sr)
    for debut in range(0, n - 400, periode):
        audio[debut: debut + 400] = np.sin(np.linspace(0, np.pi, 400)) * np.linspace(1.0, 0.2, 400)
    return audio


def _write_wav_mono(path: Path, samples: np.ndarray, sr: int = SR) -> Path:
    data = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sr)
        wav.writeframes(data.tobytes())
    return path


def _moving_square(frame_index: int, size: int = 64) -> Image.Image:
    """RGBA frame with an opaque red square whose position advances per frame."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    offset = 6 + frame_index * 6
    for y in range(offset, offset + 20):
        for x in range(offset, offset + 20):
            image.putpixel((x, y), (220, 30, 30, 255))
    return image


def _disc(size: int, radius: float, color, alpha=255, fringe=None) -> Image.Image:
    """Soft-edged opaque disc on a transparent canvas (healthy sticker).

    `fringe` = optional (color, alpha) ring painted right outside the disc
    radius (to synthesize a halo defect).
    """
    yy, xx = np.mgrid[0:size, 0:size]
    dist = np.sqrt((xx - size / 2) ** 2 + (yy - size / 2) ** 2)
    arr = np.zeros((size, size, 4), np.uint8)
    core = dist <= radius
    soft = (dist > radius) & (dist <= radius + 1.5)
    arr[core, :3] = color
    arr[core, 3] = alpha
    if fringe:
        ring = (dist > radius + 1.5) & (dist <= radius + 5)
        arr[ring, :3] = fringe[0]
        arr[ring, 3] = fringe[1]
    arr[soft, :3] = color
    coverage = np.clip((radius + 1.5 - dist[soft]) / 1.5, 0, 1)
    arr[soft, 3] = (coverage * alpha).astype(np.uint8)
    return Image.fromarray(arr)


def _fake_checkerboard(size: int = 128, cell: int = 8) -> Image.Image:
    """Fully opaque gray checkerboard (the painted-fake-transparency pattern)."""
    yy, xx = np.mgrid[0:size, 0:size]
    parity = ((xx // cell) + (yy // cell)) % 2
    gray = np.where(parity == 0, 100, 150).astype(np.uint8)
    arr = np.stack([gray, gray, gray, np.full((size, size), 255, np.uint8)], axis=-1)
    return Image.fromarray(arr, "RGBA")


# ============================================================================
# core.gif_export — GIF invariant / timing / APNG
# ============================================================================

def test_encode_gif_transparency_invariant_round_trip(tmp_path):
    frames = [_moving_square(i) for i in range(4)]
    durations = [100, 100, 100, 100]
    target = tmp_path / "animation.gif"
    encode_gif(frames, durations, target)
    qc = verify_gif(target, frames, durations)
    assert qc["technical_pass"] is True
    assert qc["alpha_mismatch_pixels"] == 0
    with Image.open(target) as gif:
        first = next(ImageSequence.Iterator(gif)).convert("RGBA")
    background_alpha = np.array(first)[0, 0, 3]
    foreground_alpha = np.array(first)[16, 16, 3]
    assert background_alpha == 0, "GIF transparency index must decode to alpha 0"
    assert foreground_alpha > 0, "GIF foreground must stay visible"


def test_encode_gif_no_visible_foreground_raises():
    frames = [Image.new("RGBA", (32, 32), (0, 0, 0, 0)) for _ in range(2)]
    with pytest.raises(ValueError, match="No visible foreground"):
        encode_gif(frames, [100, 100], Path("unused.gif"))


def test_merge_browser_gif_timing_merges_short_exposures():
    frames = [_moving_square(i) for i in range(4)]
    images, times = merge_browser_gif_timing(frames, [10, 100, 10, 30])
    assert times == [110, 40]
    assert len(images) == 2, "first frame of each merged group is kept"


def test_compute_frame_timing_clamps_under_20ms():
    indices, durations = compute_frame_timing(4, 100.0)  # 10 ms per frame
    assert indices == [1, 3]
    assert durations == [20, 20]


def test_compute_frame_timing_rejects_invalid_phases():
    with pytest.raises(ValueError):
        compute_frame_timing(10, 10.0, phases=[{"start": 0.0, "end": 2.0, "speed": 2.0}])


def test_compute_frame_timing_speed_phase_compresses():
    # Source 24 frames @ 12 fps, 2x-speed phase over the first second:
    # 41.7 ms/frame >= 20 ms so every frame is kept, total = 0.5 s (fast
    # span) + 1 s (normal span) = 1500 ms.
    indices, durations = compute_frame_timing(
        24, 12.0, phases=[{"start": 0.0, "end": 1.0, "speed": 2.0, "ramp": 0.0}])
    assert len(indices) == 24
    assert sum(durations) == pytest.approx(1500, abs=40)
    # Aggressive 10x speed: 8.3 ms/frame < 20 ms → frames merged (~1100 ms).
    fast_indices, fast_durations = compute_frame_timing(
        24, 12.0, phases=[{"start": 0.0, "end": 1.0, "speed": 10.0, "ramp": 0.0}])
    assert len(fast_indices) < 24
    assert sum(fast_durations) == pytest.approx(1100, abs=40)


def test_encode_apng_preserves_soft_alpha(tmp_path):
    frames = [_disc(64, 24.0, (30, 120, 220), alpha=180) for _ in range(2)]
    target = tmp_path / "animation.apng"
    encode_apng(frames, [80, 80], target)
    decoded = [np.array(f.convert("RGBA")) for f in ImageSequence.Iterator(Image.open(target))]
    soft_pixel = decoded[0][32, 32 + 24 + 1, 3]  # 1 px past the core radius
    assert 0 < soft_pixel < 255, "APNG master must keep fractional alpha"
    assert int(decoded[0][32, 32, 3]) == 180, "APNG core alpha must be exact"


def test_build_contact_sheet_layout(tmp_path):
    frames = [_moving_square(i) for i in range(6)]
    target = tmp_path / "contact.png"
    build_contact_sheet(frames, target)
    sheet = Image.open(target)
    assert sheet.size == (4 * 240, ((6 + 3) // 4) * 270)  # 6 frames → 2 row bands


# ============================================================================
# core.alpha_qa — detection gates
# ============================================================================

def test_alpha_qa_healthy_sticker_passes():
    report = alpha_qa_report(_disc(128, 45.0, (200, 40, 40)))
    assert report["status"] == "PASS", report["issues"]
    assert not report["fake_transparency"]
    assert 0.15 <= report["transparent_fraction"] <= 0.90
    assert report["clear_border_fraction"] >= 0.99


def test_alpha_qa_fake_checkerboard_fails():
    report = alpha_qa_report(_fake_checkerboard())
    assert report["status"] == "FAIL"
    assert "fake_transparency" in report["issues"]


def test_alpha_qa_isolated_specks_fail():
    image = _disc(128, 45.0, (200, 40, 40))
    arr = np.array(image)
    for cx, cy in ((5, 5), (122, 5), (5, 122), (122, 122)):
        arr[cy - 1: cy + 2, cx - 1: cx + 2, 3] = 255
        arr[cy - 1: cy + 2, cx - 1: cx + 2, :3] = (200, 40, 40)
    report = alpha_qa_report(Image.fromarray(arr))
    assert "isolated_specks" in report["issues"]
    assert report["status"] == "FAIL"


def test_alpha_qa_black_fringe_halo_fails():
    # Red disc + semi-transparent black ring hugging the opaque edge = halo.
    image = _disc(128, 45.0, (220, 30, 30), fringe=((10, 10, 10), 128))
    report = alpha_qa_report(image)
    assert "halo" in report["issues"], report
    assert report["status"] == "FAIL"


def test_alpha_qa_fully_opaque_image_fails_coverage_and_border():
    image = Image.new("RGBA", (128, 128), (10, 10, 10, 255))
    report = alpha_qa_report(image)
    assert "transparent_fraction" in report["issues"]
    assert "clipped_border" in report["issues"]
    assert not report["fake_transparency"], "single flat color is not a checkerboard"


def test_alpha_qa_overlay_marks_regions(tmp_path):
    image = _disc(128, 45.0, (200, 40, 40))
    arr = np.array(image)
    # Enclosed zero-alpha hole punched in the middle of the disc (7x7 > 4 px).
    arr[60:68, 60:68, 3] = 0
    overlay = tmp_path / "holes.png"
    report = alpha_qa_report(Image.fromarray(arr), overlay_path=overlay)
    assert report["interior_hole_ratio"] > 0.005
    assert report["hole_regions"], "enclosed hole must be reported"
    assert overlay.exists(), "holes overlay must be written when regions exist"


# ============================================================================
# core.beat_grid — rms analysis + scheduling
# ============================================================================

def test_analyze_beats_metronome_120bpm(tmp_path):
    wav = _write_wav_mono(tmp_path / "metro120.wav", _metronome(120.0, 8.0))
    record = analyze_beats(wav)
    assert record["engine"] == "rms"
    assert record["bpm"] == pytest.approx(120, abs=3)
    assert record["offset_ms"] == pytest.approx(0, abs=15)
    spacing = np.diff(record["beats_ms"])
    assert np.allclose(spacing, 500.0, atol=15)
    assert record["review"], "upstream caveat text must stay in the record"


def test_analyze_beats_manual_bpm_override(tmp_path):
    wav = _write_wav_mono(tmp_path / "ambient.wav", np.random.default_rng(42).normal(0, 0.01, SR * 4))
    record = analyze_beats(wav, bpm=90.0)
    assert record["method"] == "Manual BPM"
    assert record["bpm"] == 90.0
    assert record["beats_ms"], "manual BPM must produce a grid"
    assert np.allclose(np.diff(record["beats_ms"]), 60000 / 90.0, atol=1)


def test_analyze_beats_rejects_out_of_range_bpm(tmp_path):
    wav = _write_wav_mono(tmp_path / "x.wav", _metronome(120.0, 2.0))
    with pytest.raises(ValueError, match="20..400"):
        analyze_beats(wav, bpm=500.0)


def test_envelope_arrays_shape_and_normalization():
    x = _metronome(120.0, 2.0)
    env = envelope_arrays(x, SR)
    assert env["hop_ms"] == 10
    assert len(env["energy"]) == len(x) // 80
    assert max(env["energy"]) == pytest.approx(1.0)
    assert max(env["onset"]) == pytest.approx(1.0)


def test_allocate_exposures_integer_partition():
    assert allocate_exposures([1, 1, 1, 1], 1000) == [250, 250, 250, 250]
    assert allocate_exposures([1, 3], 1000) == [250, 750]


def test_allocate_exposures_zero_duration_frame_raises():
    with pytest.raises(ValueError, match="erase a frame"):
        allocate_exposures([1, 1, 1], 1)  # 0.33 ms per frame → rounds to 0


def test_schedule_beat_cycles_pairs_and_validation():
    analysis = {"beats_ms": [0, 500, 1000, 1500, 2000, 2500, 3000], "bpm": 120}
    schedule = schedule_beat_cycles(analysis, beats_per_cycle=2)
    assert [(c["start_ms"], c["end_ms"]) for c in schedule["cycles"]] == [
        (0, 1000), (1000, 2000), (2000, 3000)]
    with pytest.raises(ValueError, match="Strictly increasing"):
        schedule_beat_cycles({"beats_ms": [500, 500, 1000]})


def test_drift_report_thresholds():
    assert drift_report([500, 1000], [498, 1002])["status"] == "PASS"
    failed = drift_report([506, 1000], [500, 1000])
    assert failed["status"] == "FAIL"
    assert failed["max_error_ms"] == 6
    with pytest.raises(ValueError, match="one-to-one"):
        drift_report([1, 2, 3], [1, 2])


# ============================================================================
# Workflows (Pillow/numpy only — the FFmpeg video path is validated apart)
# ============================================================================

def _write_png_sequence(tmp_path: Path, count: int = 5) -> Path:
    frames_dir = tmp_path / "seq"
    frames_dir.mkdir(exist_ok=True)
    for i in range(count):
        _moving_square(i, size=64).save(frames_dir / f"f_{i:05d}.png")
    return frames_dir


def test_gif_export_workflow_png_sequence_end_to_end(tmp_path):
    seq = _write_png_sequence(tmp_path)
    result = GifExportWorkflow(config={}).run(dict(
        input=str(seq), fps=12.0, output="test_gif", output_dir=str(tmp_path),
        sprite_sheet=True, columns=2))
    run_dir = Path(result["run_dir"])
    assert Path(result["gif"]).exists()
    assert Path(result["apng"]).exists()
    assert Path(result["contact_sheet"]).exists()
    assert Path(result["spritesheet"]).exists()
    assert Path(result["spritesheet_atlas"]).exists()
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["source_fps"] == 12.0
    assert manifest["transparency_index"] == 255
    assert manifest["qc"]["technical_pass"] is True
    atlas = json.loads(Path(result["spritesheet_atlas"]).read_text(encoding="utf-8"))
    assert atlas["columns"] == 2 and atlas["total_frames"] == result["selected_frames"]
    assert result["alpha_qa"]["status"] in ("PASS", "FAIL")  # gate verdict carried honestly


def test_gif_export_workflow_requires_fps_for_png_sequence(tmp_path):
    seq = _write_png_sequence(tmp_path)
    with pytest.raises(ValueError, match="requires --fps"):
        GifExportWorkflow(config={}).run(dict(input=str(seq), output_dir=str(tmp_path)))


def test_gif_export_workflow_run_dir_auto_suffix(tmp_path):
    seq = _write_png_sequence(tmp_path)
    params = dict(input=str(seq), fps=12.0, output="dup", output_dir=str(tmp_path))
    first = GifExportWorkflow(config={}).run(dict(params))
    second = GifExportWorkflow(config={}).run(dict(params))
    assert Path(first["run_dir"]) != Path(second["run_dir"])
    assert Path(second["run_dir"]).name == "dup_1"


def test_alpha_qa_workflow_verdicts(tmp_path):
    healthy = tmp_path / "sticker.png"
    _disc(128, 45.0, (200, 40, 40)).save(healthy)
    good = AlphaQaWorkflow(config={}).run(dict(input=str(healthy), output_dir=str(tmp_path)))
    assert good["status"] == "PASS"
    fake = tmp_path / "fake.png"
    _fake_checkerboard().save(fake)
    # Gate semantics: FAIL raises (exit 1 through main.py), report stays on disk.
    with pytest.raises(RuntimeError, match="fake_transparency"):
        AlphaQaWorkflow(config={}).run(dict(input=str(fake), output_dir=str(tmp_path)))
    report_path = tmp_path / "fake_alpha_qa_alpha-qa.json"
    assert report_path.exists(), "report must be written before the gate raises"
    verdict = json.loads(report_path.read_text(encoding="utf-8"))
    assert "fake_transparency" in verdict["issues"]


def test_beat_sync_workflow_metronome(tmp_path):
    wav = _write_wav_mono(tmp_path / "metro.wav", _metronome(120.0, 8.0))
    result = BeatSyncWorkflow(config={}).run(dict(
        input=str(wav), bpm=120.0, beats_per_cycle=2, output_dir=str(tmp_path)))
    beats = json.loads(Path(result["beats_json"]).read_text(encoding="utf-8"))
    assert beats["bpm"] == 120.0
    assert Path(result["waveform_svg"]).exists()
    schedule = json.loads(Path(result["schedule"]).read_text(encoding="utf-8"))
    assert schedule["cycles"], "120 BPM / 8 s must yield cut cycles"
    assert result["suggested_cuts_ms"][0] == pytest.approx(beats["beats_ms"][0], abs=1)
