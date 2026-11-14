#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Structural control-map extraction for VACE video guidance and SDXL ControlNet Union.

Generates deterministic, pure-CPU (OpenCV + NumPy) structural conditioning images
and frame sequences (Canny edges, dilated edges, depth proxy) from still images or
source videos via FFmpeg, with zero PyTorch dependency.
"""

from __future__ import annotations

import glob
import os
import tempfile
from typing import Any, Dict, Optional

import cv2
import numpy as np
from PIL import Image

from core.config import DEFAULT_FFMPEG
from core.process import run_engine

CONTROL_EXTRACT_MODES = ("canny", "edges_bold", "depth_proxy")


def _auto_canny_edges(gray: np.ndarray, sigma: float = 0.33) -> np.ndarray:
    """Computes adaptive Canny edges anchored on median image luminance."""
    blurred = cv2.GaussianBlur(gray, (5, 5), 1.0)
    median_val = float(np.median(blurred))
    low = int(max(10.0, (1.0 - sigma) * median_val))
    high = int(min(255.0, max(low + 20.0, (1.0 + sigma) * median_val)))
    return cv2.Canny(blurred, low, high)


def extraire_carte_controle_array(img_rgb: np.ndarray, mode: str = "canny") -> np.ndarray:
    """Extracts a 3-channel uint8 control map from an RGB uint8 numpy array."""
    mode_norm = (mode or "canny").strip().lower()
    if mode_norm not in CONTROL_EXTRACT_MODES:
        raise ValueError(
            f"Unsupported control extract mode '{mode}'; expected one of {CONTROL_EXTRACT_MODES}"
        )

    gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)

    if mode_norm == "canny":
        edges = _auto_canny_edges(gray)
        return np.stack([edges, edges, edges], axis=-1)

    if mode_norm == "edges_bold":
        edges = _auto_canny_edges(gray, sigma=0.35)
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        mag = cv2.magnitude(gx, gy)
        mag_u8 = np.clip((mag / (float(np.percentile(mag, 99.0)) + 1e-6)) * 255.0, 0, 255).astype(np.uint8)
        combined = np.maximum(edges, (mag_u8 > 140).astype(np.uint8) * 255)
        kernel = np.ones((3, 3), dtype=np.uint8)
        bold = cv2.dilate(combined, kernel, iterations=1)
        return np.stack([bold, bold, bold], axis=-1)

    # depth_proxy: smooth bilateral luminance + structural contrast + gentle vertical near-ground cue
    h, w = gray.shape
    smooth = cv2.bilateralFilter(gray, d=9, sigmaColor=50, sigmaSpace=50).astype(np.float32) / 255.0
    low_freq = cv2.GaussianBlur(smooth, (0, 0), sigmaX=max(8.0, min(h, w) / 14.0))
    edges_soft = cv2.GaussianBlur(_auto_canny_edges(gray).astype(np.float32) / 255.0, (7, 7), 2.0)
    vertical_prior = np.linspace(0.15, 0.85, h, dtype=np.float32)[:, None]
    depth = 0.55 * low_freq + 0.30 * vertical_prior - 0.15 * edges_soft
    d_min, d_max = float(depth.min()), float(depth.max())
    if d_max - d_min > 1e-6:
        depth_norm = (depth - d_min) / (d_max - d_min)
    else:
        depth_norm = np.full_like(depth, 0.5)
    depth_u8 = np.clip(depth_norm * 255.0, 0, 255).astype(np.uint8)
    return np.stack([depth_u8, depth_u8, depth_u8], axis=-1)


def extraire_carte_controle_image(
    source_path: str,
    output_path: str,
    mode: str = "canny",
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> str:
    """Extracts and saves a structural control map PNG from a source image."""
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source image not found for control extraction: {source_path}")
    with Image.open(source_path) as src_im:
        img = src_im.convert("RGB")
    if width and height and img.size != (width, height):
        img = img.resize((width, height), Image.Resampling.LANCZOS)
    ctrl_arr = extraire_carte_controle_array(np.asarray(img, dtype=np.uint8), mode=mode)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    Image.fromarray(ctrl_arr, mode="RGB").save(output_path, "PNG")
    return output_path


def extraire_frames_controle_video(
    video_path: str,
    output_dir: str,
    mode: str = "canny",
    width: int = 832,
    height: int = 480,
    max_frames: Optional[int] = None,
    fps: Optional[int] = None,
    ffmpeg_bin: Optional[str] = None,
) -> Dict[str, Any]:
    """Extracts a synchronized PNG folder of VACE control frames from a source video."""
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Source video not found: {video_path}")
    mode_norm = (mode or "canny").strip().lower()
    if mode_norm not in CONTROL_EXTRACT_MODES:
        raise ValueError(
            f"Unsupported control extract mode '{mode}'; expected one of {CONTROL_EXTRACT_MODES}"
        )

    os.makedirs(output_dir, exist_ok=True)
    for stale_png in glob.glob(os.path.join(output_dir, "frame_*.png")):
        os.remove(stale_png)
    ff = ffmpeg_bin or DEFAULT_FFMPEG

    vf_parts = []
    if fps and fps > 0:
        vf_parts.append(f"fps={int(fps)}")
    vf_parts.append(
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
    )

    with tempfile.TemporaryDirectory(prefix="ga_vace_ctrl_") as tmp_dir:
        raw_pattern = os.path.join(tmp_dir, "raw_%05d.png")
        cmd = [ff, "-y", "-i", video_path, "-vf", ",".join(vf_parts)]
        if max_frames and max_frames > 0:
            cmd.extend(["-frames:v", str(int(max_frames))])
        cmd.append(raw_pattern)
        run_engine(cmd, check=True, timeout=600, etiquette="ffmpeg vace control extract")

        raw_files = sorted(glob.glob(os.path.join(tmp_dir, "raw_*.png")))
        if not raw_files:
            raise RuntimeError(f"FFmpeg extracted zero frames from '{video_path}'")

        for idx, raw_file in enumerate(raw_files, start=1):
            with Image.open(raw_file) as raw_im:
                rgb = np.asarray(raw_im.convert("RGB"), dtype=np.uint8)
            ctrl_arr = extraire_carte_controle_array(rgb, mode=mode_norm)
            dst_file = os.path.join(output_dir, f"frame_{idx:05d}.png")
            Image.fromarray(ctrl_arr, mode="RGB").save(dst_file, "PNG")

    return {
        "control_dir": output_dir,
        "frame_count": len(raw_files),
        "mode": mode_norm,
        "resolution": f"{width}x{height}",
    }
