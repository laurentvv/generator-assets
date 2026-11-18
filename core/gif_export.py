#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GIF / APNG / RGBA-frame export from videos or PNG sequences.

Ported from miles990/video-gif-studio (MIT) — scripts/gif_pipeline.py.
Core invariant kept intact: one shared 255-color MEDIANCUT palette trained
on visible pixels only, palette index 255 RESERVED for transparency
(binary alpha cutoff at 128), disposal=2 so frames never bleed into each
other. PNG/APNG stay the fidelity masters (soft fractional alpha is
preserved there); the GIF derivative only ever carries binary transparency.

Video decoding goes through FFmpeg via `core.process.run_engine`: OpenCV
`VideoCapture` silently drops alpha, so the source is conformed to a PNG
sequence first (alpha-capable for VP9 / ProRes-4444 inputs) before Pillow
loads it. PNG-sequence input skips FFmpeg entirely and is the primary path
for AI-generated still sequences.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageSequence

from core.config import ffmpeg
from core.process import run_engine

TRANSPARENCY_INDEX = 255
ALPHA_CUTOFF = 128


def _sha256(path: Path) -> str:
    """SHA-256 of a file (streamed, provenance manifests)."""
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _natural_key(path: Path) -> list:
    """Sort key handling frame numbers without zero padding ambiguity."""
    return [int(v) if v.isdigit() else v for v in re.split(r"(\d+)", path.name)]


def _apply_chroma_key(image: Image.Image, key_rgb: Tuple[int, int, int],
                      tolerance: float, softness: float) -> Image.Image:
    """Chromatic-distance keying of a uniform backing color into alpha.

    Distance ignores modest exposure shifts of a flat screen (upstream
    comment). The result is min'ed with the existing alpha channel, so a
    source that already carries alpha keeps it.
    """
    arr = np.array(image)
    rgb = arr[:, :, :3].astype(float) / 255
    color = np.array(key_rgb, dtype=float) / 255
    chroma = rgb - rgb.mean(axis=2, keepdims=True)
    color = color - color.mean()
    dist = np.linalg.norm(chroma - color, axis=2)
    alpha = np.clip((dist - tolerance) / softness, 0, 1)
    arr[:, :, 3] = np.minimum(arr[:, :, 3], np.round(alpha * 255).astype("uint8"))
    return Image.fromarray(arr)


def _load_image_sequence(directory: Path, resize_width: Optional[int],
                         key: Optional[Tuple[int, int, int]],
                         tolerance: float, softness: float) -> List[Image.Image]:
    paths = sorted(directory.glob("*.png"), key=_natural_key)
    if not paths:
        raise ValueError(f"No PNG frame found in {directory}")
    frames = []
    for path in paths:
        image = Image.open(path).convert("RGBA")
        if resize_width and image.width > resize_width:
            image = image.resize(
                (resize_width, round(image.height * resize_width / image.width)),
                Image.Resampling.LANCZOS,
            )
        if key:
            image = _apply_chroma_key(image, key, tolerance, softness)
        frames.append(image)
    if any(f.size != frames[0].size for f in frames):
        raise ValueError("Changing canvas size across frames")
    return frames


def load_png_frames(directory: Path, resize_width: Optional[int] = None,
                    key: Optional[Tuple[int, int, int]] = None,
                    tolerance: float = 0.15, softness: float = 0.12) -> List[Image.Image]:
    """Loads a PNG frame sequence (the alpha-preserving input path)."""
    return _load_image_sequence(directory, resize_width, key, tolerance, softness)


def _probe_fps(video: Path) -> float:
    """Native FPS of a video via ffprobe (r_frame_rate of stream 0)."""
    ffprobe = Path(ffmpeg()).with_name("ffprobe.exe")
    if not ffprobe.exists():
        raise FileNotFoundError(f"ffprobe not found next to ffmpeg ({ffmpeg()})")
    result = run_engine(
        [str(ffprobe), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=r_frame_rate", "-of", "json", str(video)],
        timeout=60, etiquette="ffprobe",
    )
    data = json.loads(result.stdout or "{}")
    streams = data.get("streams") or []
    if not streams:
        raise ValueError(f"No video stream in {video}")
    num, _, den = str(streams[0].get("r_frame_rate", "0/1")).partition("/")
    try:
        return float(num) / float(den or 1)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(f"Unreadable FPS metadata in {video}") from exc


def extract_video_frames(source: Path, out_dir: Path,
                         fps_conform: Optional[float] = None,
                         resize_width: Optional[int] = None,
                         key: Optional[Tuple[int, int, int]] = None,
                         tolerance: float = 0.15, softness: float = 0.12,
                         timeout: float = 900.0) -> Tuple[List[Image.Image], float]:
    """Conforms a video to a PNG sequence via FFmpeg, then loads it as RGBA.

    `fps_conform` re-times the source with `-vf fps=` (VFR sources); without
    it the native FPS is probed and kept. Alpha is preserved for sources
    that carry one (VP9 / ProRes-4444); opaque sources decode fully opaque.
    """
    fps = float(fps_conform) if fps_conform else _probe_fps(source)
    if not np.isfinite(fps) or fps <= 0:
        raise ValueError("Invalid source FPS")
    src_dir = Path(out_dir) / "frames_src"
    src_dir.mkdir(parents=True, exist_ok=True)
    if any(src_dir.iterdir()):
        raise ValueError(f"FFmpeg conform directory is not empty: {src_dir}")
    filters = [f"fps={fps}"] if fps_conform else []
    run_engine(
        [ffmpeg(), "-v", "error", "-i", str(source)]
        + (["-vf", ",".join(filters)] if filters else [])
        + [str(src_dir / "f_%06d.png")],
        timeout=timeout, etiquette="ffmpeg-conform",
    )
    frames = _load_image_sequence(src_dir, resize_width, key, tolerance, softness)
    return frames, fps


def compute_frame_timing(count: int, fps: float,
                         phases: Optional[Sequence[Dict[str, Any]]] = None
                         ) -> Tuple[List[int], List[int]]:
    """Frame selection + 10 ms-grid exposure durations (upstream timing()).

    `phases` = optional speed ramps (start/end in source seconds, speed>0,
    optional cosine ramp in seconds). Very short exposures are accumulated
    until they reach 20 ms — most GIF viewers clamp shorter frame times.
    """
    phases = list(phases or [])
    previous = 0.0
    for phase in phases:
        start, end, speed = (float(phase[k]) for k in ("start", "end", "speed"))
        ramp = float(phase.get("ramp", 0.25))
        if not all(np.isfinite(v) for v in (start, end, speed, ramp)):
            raise ValueError("Non-finite phase")
        if start < previous or end <= start or end > count / fps or speed <= 0 or ramp < 0:
            raise ValueError("Invalid/overlapping phase ranges")
        previous = end
    indices: List[int] = []
    durations: List[float] = []
    accumulated = 0.0
    for i in range(count):
        t = (i + 0.5) / fps
        rate = 1.0
        for phase in phases:
            if phase["start"] <= t < phase["end"]:
                ramp = float(phase.get("ramp", 0.25))
                blend = 1.0 if ramp == 0 else min(1.0, (t - phase["start"]) / ramp, (phase["end"] - t) / ramp)
                blend = 0.5 - 0.5 * np.cos(np.pi * blend)
                rate = 1 + (phase["speed"] - 1) * blend
                break
        accumulated += 1000 / fps / rate
        if accumulated >= 20:
            indices.append(i)
            durations.append(accumulated)
            accumulated = 0.0
    if accumulated:
        if not durations:
            raise ValueError("Output shorter than 20ms cannot be represented reliably")
        durations[-1] += accumulated
    edges = np.round(np.cumsum([0.0] + durations) / 10) * 10
    return indices, np.diff(edges).astype(int).tolist()


def merge_browser_gif_timing(frames: List[Image.Image], durations: Sequence[int]
                             ) -> Tuple[List[Image.Image], List[int]]:
    """Merges <=20 ms exposures into neighbours, preserving total time (>20 ms).

    Keeps the first image of a merged group so a short onset peak survives.
    Affects only the GIF derivative, never the PNG/APNG master timing.
    """
    images, times = [], []
    for frame, duration in zip(frames, durations):
        if times and times[-1] <= 20:
            times[-1] += duration
        else:
            images.append(frame)
            times.append(duration)
    if len(times) > 1 and times[-1] <= 20:
        tail = times.pop()
        times[-1] += tail
        images.pop()
    return images, times


def encode_gif(frames: List[Image.Image], durations: Sequence[int], target: Path) -> None:
    """Encodes the deterministic global-palette GIF (upstream invariant).

    255 visible colors trained on 96x96 thumbnails of pixels with alpha>=128,
    dither disabled, index 255 duplicated then reserved for transparency,
    disposal=2, no optimize (byte-deterministic).
    """
    frames, durations = merge_browser_gif_timing(frames, durations)
    samples = []
    for frame in frames:
        thumb = frame.copy()
        thumb.thumbnail((96, 96))
        arr = np.array(thumb)
        samples.append(arr[:, :, :3][arr[:, :, 3] >= ALPHA_CUTOFF])
    visible = np.concatenate(samples)
    if not len(visible):
        raise ValueError("No visible foreground")
    train = Image.fromarray(visible.reshape((-1, 1, 3)))
    palette = train.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    colors = (palette.getpalette() + [0] * 768)[:765]
    colors += colors[:3]  # final entry duplicated then RESERVED for transparency
    palette.putpalette(colors)
    result = []
    for frame in frames:
        arr = np.array(frame)
        quantized = np.array(frame.convert("RGB").quantize(palette=palette, dither=Image.Dither.NONE))
        quantized[quantized == TRANSPARENCY_INDEX] = 0  # remap index collision to background
        quantized[arr[:, :, 3] < ALPHA_CUTOFF] = TRANSPARENCY_INDEX
        image = Image.fromarray(quantized)
        image.putpalette(colors)
        result.append(image)
    result[0].save(target, format="GIF", save_all=True, append_images=result[1:],
                   duration=durations, loop=0, transparency=TRANSPARENCY_INDEX,
                   background=TRANSPARENCY_INDEX, disposal=2, optimize=False)


def encode_apng(frames: List[Image.Image], durations: Sequence[int], target: Path) -> None:
    """Encodes the full-color APNG master (soft fractional alpha preserved)."""
    frames[0].save(target, format="PNG", save_all=True, append_images=frames[1:],
                   duration=durations, loop=0, disposal=0, blend=0)


def verify_gif(target: Path, frames: List[Image.Image], durations: Sequence[int]) -> Dict[str, Any]:
    """Re-decodes the delivered GIF and checks it against the source timeline.

    Encoders may coalesce truly identical adjacent frames, so comparison
    walks the decoded timeline instead of pairing frames 1:1. Raises on any
    alpha mismatch (the invariant breach) and returns the QC record.
    """
    frames, durations = merge_browser_gif_timing(frames, durations)
    decoded: List[np.ndarray] = []
    actual_durations: List[int] = []
    with Image.open(target) as gif:
        for frame in ImageSequence.Iterator(gif):
            decoded.append(np.array(frame.convert("RGBA")))
            actual_durations.append(frame.info.get("duration", 0))
    if sum(actual_durations) != sum(durations):
        raise ValueError("Decoded GIF duration mismatch")
    mismatch, errors, index, elapsed, end = 0, [], 0, 0, actual_durations[0]
    for frame, duration in zip(frames, durations):
        while elapsed >= end and index + 1 < len(decoded):
            index += 1
            end += actual_durations[index]
        if elapsed + duration > end:
            raise ValueError("Unexpected decoded frame timing boundary")
        source, output = np.array(frame), decoded[index]
        if source.shape != output.shape:
            raise ValueError("Decoded canvas mismatch")
        visible = source[:, :, 3] >= ALPHA_CUTOFF
        mismatch += int(np.count_nonzero(visible != (output[:, :, 3] > 0)))
        if visible.any():
            errors.append(float(np.abs(source[:, :, :3].astype(float) - output[:, :, :3])[visible].mean()))
        elapsed += duration
    if mismatch:
        raise ValueError(f"Decoded GIF integrity failure: alpha={mismatch}")
    return {"decoded_frames": len(decoded), "source_output_frames": len(frames),
            "duration_ms": sum(actual_durations), "alpha_mismatch_pixels": mismatch,
            "mean_visible_rgb_error": float(np.mean(errors)) if errors else 0.0,
            "technical_pass": True}


def build_contact_sheet(frames: List[Image.Image], target: Path) -> None:
    """4-column contact sheet on alternating light/dark cells (visual review)."""
    count = min(12, len(frames))
    board = Image.new("RGB", (4 * 240, ((count + 3) // 4) * 270), "#dddddd")
    draw = ImageDraw.Draw(board)
    for j, idx in enumerate(np.linspace(0, len(frames) - 1, count).astype(int)):
        image = frames[idx].copy()
        image.thumbnail((232, 240))
        x, y = j % 4 * 240, j // 4 * 270
        draw.rectangle((x, y, x + 239, y + 245), fill="#171717" if j % 2 else "#eeeeee")
        board.paste(image, (x + (240 - image.width) // 2, y), image)
        draw.text((x + 6, y + 248), f"output frame {idx}", fill="black")
    board.save(target)
