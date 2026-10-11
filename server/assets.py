"""Output library: incremental indexer, thumbnails, audio waveforms, MIME map.

The factory writes to output/ without a central manifest; the UI discovers
artifacts by walking output/ (skipping the _webui runtime dir) and
godot_assets/ (validated inputs), keeping the result in the outputs table.
Walks run in a threadpool and are throttled (30 s).
"""

import asyncio
import hashlib
import logging
import time
import wave
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw

from server import db, paths

logger = logging.getLogger(__name__)

# kind -> extensions (lowercase, no dot)
EXTENSIONS: Dict[str, set] = {
    "image": {"png", "jpg", "jpeg", "webp", "gif", "bmp", "tga"},
    "video": {"webm", "mp4", "mkv", "mov", "avi"},
    "audio": {"wav", "mp3", "ogg", "oga", "flac", "m4a", "opus"},
    "model": {"glb", "gltf", "ply", "obj", "fbx", "blend"},
    "doc": {"md", "txt", "json", "tres", "tscn", "gdshader", "gd", "csv", "log"},
}

MIME: Dict[str, str] = {
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp",
    "gif": "image/gif", "bmp": "image/bmp", "tga": "image/x-tga",
    "webm": "video/webm", "mp4": "video/mp4", "mkv": "video/x-matroska",
    "mov": "video/quicktime", "avi": "video/x-msvideo",
    "wav": "audio/wav", "mp3": "audio/mpeg", "ogg": "audio/ogg", "oga": "audio/ogg",
    "flac": "audio/flac", "m4a": "audio/mp4", "opus": "audio/opus",
    "glb": "model/gltf-binary", "gltf": "model/gltf+json", "ply": "application/octet-stream",
    "json": "application/json", "md": "text/markdown; charset=utf-8",
    "txt": "text/plain; charset=utf-8", "log": "text/plain; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
    "tres": "text/plain; charset=utf-8", "tscn": "text/plain; charset=utf-8",
    "gdshader": "text/plain; charset=utf-8", "gd": "text/plain; charset=utf-8",
}


def classify(path: Path) -> Optional[str]:
    ext = path.suffix.lower().lstrip(".")
    for kind, exts in EXTENSIONS.items():
        if ext in exts:
            return kind
    return None


def mime_for(path: Path) -> str:
    return MIME.get(path.suffix.lower().lstrip("."), "application/octet-stream")


_last_refresh = 0.0
_refresh_lock = asyncio.Lock()


async def refresh(force: bool = False) -> None:
    """(Re)index the allowed roots; throttled to one walk per 30 s."""
    global _last_refresh
    if not force and time.time() - _last_refresh < 30:
        return
    async with _refresh_lock:
        if not force and time.time() - _last_refresh < 30:
            return
        await asyncio.to_thread(_walk_and_upsert)
        _last_refresh = time.time()


def _walk_and_upsert() -> None:
    seen: set = set()
    for root in paths.ALLOWED_ROOTS:
        if not root.exists():
            continue
        for file in root.rglob("*"):
            if not file.is_file():
                continue
            rel = file.relative_to(paths.REPO_ROOT).as_posix()
            if rel.startswith("output/_webui/"):
                continue
            kind = classify(file)
            if kind is None:
                continue
            try:
                stat = file.stat()
            except OSError:
                continue
            seen.add(rel)
            db.upsert_output(rel, kind, stat.st_mtime, stat.st_size)
    db.prune_outputs(seen)


# ------------------------------------------------------------- thumbnails --

def _cache_name(path: Path) -> str:
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:16]
    return f"{digest}_{int(path.stat().st_size >> 10)}.webp" if path.exists() else f"{digest}.webp"


def thumbnail(path: Path) -> Optional[str]:
    """WebP thumbnail URL for images, or None. Generated once, cached on disk."""
    kind = classify(path)
    if kind != "image":
        return None
    name = _cache_name(path)
    target = paths.THUMB_DIR / name
    if not target.exists():
        try:
            with Image.open(path) as img:
                img.thumbnail((480, 480))
                save = img if img.mode in ("RGB", "RGBA") else img.convert("RGB")
                save.save(target, "WEBP", quality=80)
        except (OSError, ValueError) as exc:
            logger.debug("webui: thumbnail failed for %s: %s", path, exc)
            return None
    return f"/thumbs/{name}"


def waveform(path: Path, bars: int = 180, width: int = 640, height: int = 120) -> Optional[str]:
    """Waveform PNG URL for PCM .wav files (stdlib wave + PIL), cached."""
    if path.suffix.lower() != ".wav":
        return None
    name = _cache_name(path).replace(".webp", "_wave.png")
    target = paths.THUMB_DIR / name
    if target.exists():
        return f"/thumbs/{target.name}"
    try:
        with wave.open(str(path), "rb") as handle:
            frames = handle.getnframes()
            channels = handle.getnchannels() or 1
            width_sample = handle.getsampwidth()
            if frames == 0 or width_sample not in (1, 2, 4) or frames > 30_000_000:
                return None
            data = handle.readframes(frames)
        step = max(1, len(data) // (bars * channels * width_sample))
        peaks: List[float] = []
        for index in range(bars):
            start = index * step
            chunk = data[start:start + step]
            if not chunk:
                break
            if width_sample == 1:
                vals = [abs(b - 128) for b in chunk]
            elif width_sample == 2:
                vals = [abs(chunk[i] | (chunk[i + 1] << 8)) for i in range(0, len(chunk) - 1, 2)]
            else:
                vals = [abs(int.from_bytes(chunk[i:i + 4], "little")) for i in range(0, len(chunk) - 3, 4)]
            peaks.append((max(vals) or 0) / (255 if width_sample == 1 else 32768 if width_sample == 2 else 2**31))
        if not peaks:
            return None
        norm = max(peaks) or 1.0
        img = Image.new("RGB", (width, height), (10, 11, 15))
        draw = ImageDraw.Draw(img)
        bar_w = max(2, width // len(peaks))
        midline = height // 2
        for index, peak in enumerate(peaks):
            length = max(2, int((peak / norm) * (height // 2 - 6)))
            x = index * bar_w
            draw.rectangle(
                (x, midline - length, x + max(1, bar_w - 2), midline + length),
                fill=(245, 165, 36),
            )
        img.save(target, "PNG")
    except (OSError, wave.Error, ValueError) as exc:
        logger.debug("webui: waveform failed for %s: %s", path, exc)
        return None
    return f"/thumbs/{target.name}"


def read_range(path: Path, start: int, end: int) -> bytes:
    """Read [start, end] inclusive — called from a threadpool."""
    with path.open("rb") as handle:
        handle.seek(start)
        return handle.read(end - start + 1)


def parse_range(header: str, size: int) -> Optional[Tuple[int, int]]:
    """'bytes=500-999' / 'bytes=-500' / 'bytes=500-' -> (start, end) or None."""
    if not header.startswith("bytes="):
        return None
    span = header[len("bytes="):].split(",")[0].strip()
    if "-" not in span:
        return None
    first, last = span.split("-", 1)
    try:
        if first == "":
            length = int(last)
            return (max(0, size - length), size - 1) if length else None
        start = int(first)
        end = int(last) if last else size - 1
    except ValueError:
        return None
    if start < 0 or start >= size or end < start:
        return None
    return (start, min(end, size - 1))
