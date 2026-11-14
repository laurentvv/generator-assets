#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lightweight CPU pre-upscale / post-generation video Quality Control (QC).

Checks duration, luminance spread (detects blank/solid/washed-out frames),
temporal motion delta across sampled timestamps (detects frozen clips), and
bottom black-band rows (detects aspect/pad drift) before expensive GPU upscales.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
from PIL import Image

from core.config import DEFAULT_FFMPEG

_RE_DURATION = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


def duree_video(video_path: str, ffmpeg_bin: Optional[str] = None) -> float:
    """Returns video duration in seconds by parsing FFmpeg stream metadata."""
    ff = ffmpeg_bin or DEFAULT_FFMPEG
    try:
        proc = subprocess.run(
            [ff, "-hide_banner", "-i", video_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return 0.0
    match = _RE_DURATION.search(proc.stderr or "")
    if not match:
        return 0.0
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _extraire_trame(video_path: str, timestamp_s: float, dst_png: str, ff: str) -> bool:
    """Extracts a single decoded RGB frame at `timestamp_s` into `dst_png`."""
    try:
        proc = subprocess.run(
            [
                ff, "-y", "-hide_banner", "-loglevel", "error",
                "-ss", f"{max(0.0, timestamp_s):.3f}",
                "-i", video_path,
                "-frames:v", "1",
                dst_png,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return False
    return proc.returncode == 0 and os.path.exists(dst_png) and os.path.getsize(dst_png) > 0


def mesurer_bande_noire_bas(img_rgb: np.ndarray, seuil_luma: float = 8.0) -> int:
    """Counts trailing bottom scanlines whose mean luminance stays <= `seuil_luma`."""
    luma_rows = img_rgb.astype(np.float32).mean(axis=(1, 2))
    rows = 0
    for val in reversed(luma_rows):
        if float(val) <= seuil_luma:
            rows += 1
        else:
            break
    return rows


def auditer_clip_video(
    video_path: str,
    sample_fractions: Iterable[float] = (0.15, 0.50, 0.85),
    bottom_black_threshold: float = 8.0,
    max_black_band_px: int = 16,
    min_luma_std: float = 4.0,
    min_motion_diff: float = 0.5,
    ffmpeg_bin: Optional[str] = None,
) -> Dict[str, Any]:
    """Audits a video clip for corruption, solid frames, frozen playback, or black bands."""
    if not video_path or not os.path.exists(video_path):
        return {
            "ok": False,
            "issues": [f"missing video file: {video_path}"],
            "warnings": [],
            "metrics": {},
        }
    if os.path.getsize(video_path) == 0:
        return {
            "ok": False,
            "issues": ["empty 0-byte video file"],
            "warnings": [],
            "metrics": {},
        }

    ff = ffmpeg_bin or DEFAULT_FFMPEG
    duration_s = duree_video(video_path, ffmpeg_bin=ff)
    issues: List[str] = []
    warnings: List[str] = []

    if duration_s <= 0.0:
        issues.append("unreadable or zero-duration video stream")
        return {
            "ok": False,
            "issues": issues,
            "warnings": warnings,
            "metrics": {"duration_s": 0.0},
        }

    fracs = [max(0.0, min(0.98, float(f))) for f in sample_fractions]
    frames: List[np.ndarray] = []

    with tempfile.TemporaryDirectory(prefix="ga_vqc_") as tmp_dir:
        for idx, frac in enumerate(fracs):
            ts = min(max(0.0, duration_s - 0.05), duration_s * frac)
            png_path = os.path.join(tmp_dir, f"qc_{idx}.png")
            if _extraire_trame(video_path, ts, png_path, ff):
                with Image.open(png_path) as im:
                    arr = np.asarray(im.convert("RGB"), dtype=np.uint8)
                frames.append(arr)

    if not frames:
        issues.append("ffmpeg failed to decode any frame from video")
        return {
            "ok": False,
            "issues": issues,
            "warnings": warnings,
            "metrics": {"duration_s": round(duration_s, 3), "sampled_frames": 0},
        }
    if len(fracs) >= 2 and len(frames) < 2:
        issues.append(
            f"incomplete or truncated video stream (decoded {len(frames)}/{len(fracs)} sampled frames)"
        )

    luma_stds = [float(f.astype(np.float32).std()) for f in frames]
    luma_means = [float(f.astype(np.float32).mean()) for f in frames]
    black_rows = [mesurer_bande_noire_bas(f, seuil_luma=bottom_black_threshold) for f in frames]

    min_std_seen = min(luma_stds)
    min_mean_seen = min(luma_means)
    max_mean_seen = max(luma_means)
    worst_black_px = max(black_rows)

    motion_diff = None
    if len(frames) >= 2 and frames[0].shape == frames[-1].shape:
        motion_diff = float(np.abs(frames[-1].astype(np.float32) - frames[0].astype(np.float32)).mean())

    if min_std_seen < min_luma_std or min_mean_seen < 2.5 or max_mean_seen > 252.5:
        issues.append(
            f"collapsed or solid frame detected (min_luma_std={min_std_seen:.2f}, "
            f"luma_mean_range=[{min_mean_seen:.1f}, {max_mean_seen:.1f}])"
        )

    if duration_s >= 0.4 and motion_diff is not None and motion_diff < min_motion_diff:
        issues.append(
            f"frozen video frames detected (interframe_mean_diff={motion_diff:.3f} < {min_motion_diff})"
        )

    if worst_black_px > max_black_band_px:
        issues.append(
            f"excessive bottom black band ({worst_black_px} px > {max_black_band_px} px)"
        )
    elif worst_black_px > 0:
        warnings.append(f"minor bottom dark band ({worst_black_px} px)")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "metrics": {
            "duration_s": round(duration_s, 3),
            "resolution": f"{frames[0].shape[1]}x{frames[0].shape[0]}",
            "sampled_frames": len(frames),
            "min_luma_std": round(min_std_seen, 3),
            "min_luma_mean": round(min_mean_seen, 2),
            "max_luma_mean": round(max_mean_seen, 2),
            "interframe_mean_diff": round(motion_diff, 3) if motion_diff is not None else None,
            "max_bottom_black_px": int(worst_black_px),
        },
    }
