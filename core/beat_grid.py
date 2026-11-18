#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local music beat/tempo analysis (numpy-only "rms" engine) + beat-to-frame
exposure scheduling.

Ported from miles990/video-gif-studio (MIT) — scripts/music_sync.py (rms
engine) and scripts/audio_beat_sync.py. The optional neural `beat_this`
backend is intentionally NOT ported: it requires PyTorch, which violates
the zero-PyTorch stack of this repository.

Upstream limitations kept verbatim: the rms engine is a 10 ms RMS-onset
periodicity heuristic — no downbeat/chord/phrase detection; half/double
-tempo and variable-tempo errors are possible, so `beats.json` output is
a reviewable candidate grid (editable via `bpm`/`offset_ms` overrides).
"""

import hashlib
import json
import math
import os
import tempfile
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from core.config import ffmpeg
from core.process import run_engine

BPM_MIN, BPM_MAX = 60, 200  # rms autocorrelation scan range (upstream)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def decode_mono(source: Path, rate: int = 8000) -> np.ndarray:
    """Decodes any audio to mono float32 at `rate`.

    A PCM16 WAV already at `rate` is decoded natively by the stdlib `wave`
    module (offline, no subprocess); anything else — other rates (e.g. the
    48 kHz stereo beds of music_bg), other bit depths, compressed formats —
    goes through FFmpeg, written to a temp raw f32 file in the system temp
    directory (run_engine captures text, so the binary payload must land on
    disk, not in stdout; tempfile avoids read-only library folders and
    concurrent-run collisions).
    """
    source = Path(source)
    if source.suffix.lower() == ".wav":
        try:
            with wave.open(str(source), "rb") as wav:
                if wav.getsampwidth() == 2 and wav.getframerate() == rate:
                    x = np.frombuffer(wav.readframes(wav.getnframes()), "<i2").astype(np.float32)
                    return x.reshape(-1, wav.getnchannels()).mean(axis=1) / 32768
        except wave.Error:
            pass  # not PCM16 / unreadable header — FFmpeg path below handles it
    fd, raw_name = tempfile.mkstemp(suffix=".f32")
    os.close(fd)
    raw_path = Path(raw_name)
    try:
        run_engine(
            [ffmpeg(), "-v", "error", "-i", str(source), "-vn", "-ac", "1",
             "-ar", str(rate), "-f", "f32le", "-y", str(raw_path)],
            timeout=300, etiquette="ffmpeg-decode",
        )
        x = np.fromfile(raw_path, "<f4")
    finally:
        raw_path.unlink(missing_ok=True)
    return x


def envelope_arrays(x: np.ndarray, rate: int) -> Dict[str, Any]:
    """10 ms linear RMS and positive RMS differences, normalized independently."""
    hop = round(rate * 0.01)
    count = len(x) // hop
    if not count:
        raise ValueError("Audio needs at least 10ms of samples")
    energy = np.sqrt(np.mean(x[: count * hop].reshape(count, hop) ** 2, axis=1))
    onset = np.maximum(energy - np.concatenate(([0], energy[:-1])), 0)
    peak = max(float(energy.max()), 1e-12)
    onset_peak = max(float(onset.max()), 1e-12)
    return {"times_ms": (np.arange(count) * 10).tolist(),
            "energy": (energy / peak).tolist(),
            "onset": (onset / onset_peak).tolist(),
            "hop_ms": 10}


def analyze_beats(source: Path, bpm: Optional[float] = None,
                  offset_ms: Optional[float] = None) -> Dict[str, Any]:
    """RMS-onset periodicity beat analysis (upstream `analyze`, rms engine).

    Returns the beats.json record: bpm, offset_ms, beats_ms, onsets_ms,
    waveform bins, tempo candidates. `bpm`/`offset_ms` override the
    heuristic (manual mode). No output directory side effects here.
    """
    source = Path(source).resolve()
    if bpm is not None and (not math.isfinite(bpm) or not 20 <= bpm <= 400):
        raise ValueError("BPM must be 20..400")
    if offset_ms is not None and (not math.isfinite(offset_ms) or offset_ms < 0):
        raise ValueError("Offset must be nonnegative")
    x = decode_mono(source)
    total_ms = len(x) / 8.0  # 8000 Hz decode
    if not len(x):
        raise ValueError("No decoded audio")
    hop = 80
    count = len(x) // hop
    energy = np.sqrt(np.mean(x[: count * hop].reshape(count, hop) ** 2, axis=1)) if count else np.zeros(1)
    onset = np.maximum(energy - np.concatenate(([0], energy[:-1])), 0)
    strength = float(np.dot(onset, onset))
    candidates: List[Dict[str, Any]] = []
    if total_ms >= 2000 and strength > 1e-10:
        for tempo in range(BPM_MIN, BPM_MAX + 1):
            lag = round(6000 / tempo)
            score = float(np.dot(onset[lag:], onset[:-lag]) / strength) if lag < len(onset) else 0.0
            candidates.append({"bpm": tempo, "periodicity": score})
        candidates.sort(key=lambda item: item["periodicity"], reverse=True)
    chosen = bpm if bpm is not None else (candidates[0]["bpm"] if candidates and candidates[0]["periodicity"] > 0.1 else None)
    offset = offset_ms
    if offset is None:
        window = max(1, min(len(onset), round(6000 / chosen))) if chosen else 1
        offset = float(np.argmax(onset[:window])) * 10 if chosen else 0
    beats = [] if chosen is None else np.arange(offset, total_ms, 60000 / chosen).tolist()
    bins = np.array_split(np.abs(x), min(1000, len(x)))
    waveform = [float(v.max()) for v in bins]
    onset_peak = max(float(onset.max()), 1e-6)
    peaks = []
    for i in range(1, len(onset) - 1):
        if onset[i] > max(onset_peak * 0.2, 1e-6) and onset[i] >= onset[i - 1] and onset[i] > onset[i + 1]:
            peaks.append(i * 10)
    return {"source": str(source), "source_sha256": _sha256(source),
            "duration_ms": total_ms, "bpm": chosen, "offset_ms": offset,
            "beats_ms": beats, "onsets_ms": peaks, "waveform": waveform,
            "tempo_candidates": candidates[:5], "envelopes": envelope_arrays(x, 8000),
            "method": "Manual BPM" if bpm is not None else "10ms RMS-onset periodicity heuristic",
            "review": "Unreviewed candidates. Not downbeat/chord/phrase detection; half/double-tempo "
                      "and variable-tempo errors possible. Edit beats_ms or override BPM/offset.",
            "engine": "rms"}


def write_beats_record(record: Dict[str, Any], out_dir: Path) -> Dict[str, Any]:
    """Writes beats.json (+ waveform.svg review artifact) into a new directory."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "beats.json"
    if target.exists():
        raise FileExistsError(f"beats.json already exists in {out_dir} (use a fresh directory)")
    target.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    wave_values = record["waveform"]
    beats: Sequence[float] = record["beats_ms"]
    total_ms = max(float(record["duration_ms"]), 1e-9)
    scale = max(max(wave_values), 1e-9)
    points = " ".join(
        f"{i * 1200 / max(1, len(wave_values) - 1):.2f},{120 - v / scale * 90:.2f}"
        for i, v in enumerate(wave_values)
    )
    lines = "".join(
        f'<path d="M {t / total_ms * 1200:.2f} 15 V 225" stroke="#ea9d2d" opacity=".6"/>'
        for t in beats[:1000]
    )
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="240">'
           f'<rect width="1200" height="240" fill="#19212b"/>{lines}'
           f'<polyline points="{points}" fill="none" stroke="#72dec8"/>'
           f'<text x="10" y="235" fill="white">Beat candidates — review BPM, offset and beat times before editing</text></svg>')
    (out_dir / "waveform.svg").write_text(svg, encoding="utf-8")
    return {"beats_json": str(target), "waveform_svg": str(out_dir / "waveform.svg")}


def allocate_exposures(weights: Sequence[float], duration_ms: float) -> List[int]:
    """Integer exposure allocation over a beat cycle (cumsum rounding).

    Every frame receives a strictly positive duration; a zero-duration
    frame means the cycle is too short for the frame count.
    """
    weights = list(weights)
    if not weights or min(weights) <= 0 or duration_ms <= 0:
        raise ValueError("Positive frame weights and cycle duration required")
    edges = np.rint(np.r_[0, np.cumsum(weights) / sum(weights) * duration_ms]).astype(int)
    durations = np.diff(edges).tolist()
    if min(durations) <= 0:
        raise ValueError("Beat interval would erase a frame; use more beats or fewer frames")
    return [int(d) for d in durations]


def schedule_beat_cycles(analysis: Dict[str, Any], beats_per_cycle: int = 2) -> Dict[str, Any]:
    """Schedules animation cycles on the measured beat grid (no events).

    Simplified port of upstream `schedule` without the hit-event
    anticipation machinery (tied to their animation manifest format): each
    cycle spans `beats_per_cycle` strictly increasing beats and carries the
    integer exposure allocation of one full frame set.
    """
    if not isinstance(beats_per_cycle, int) or beats_per_cycle < 1:
        raise ValueError("Integer beats per cycle required")
    beats = analysis["beats_ms"]
    if len(beats) < beats_per_cycle + 1 or any(b <= a for a, b in zip(beats, beats[1:])):
        raise ValueError("Strictly increasing measured beat times required")
    cycles: List[Dict[str, Any]] = []
    for i in range(0, len(beats) - beats_per_cycle, beats_per_cycle):
        start = round(beats[i])
        end = round(beats[i + beats_per_cycle])
        cycles.append(dict(start_ms=start, end_ms=end))
    return dict(status="experimental", clock="audio_playback",
                beats_per_cycle=beats_per_cycle, cycles=cycles,
                source_bpm=analysis.get("bpm"),
                runtime_av_sync="untested", motion_qa="required after retiming")


def drift_report(actual: Sequence[float], target: Sequence[float],
                 tolerance_ms: float = 5) -> Dict[str, Any]:
    """PASS/FAIL drift check pairing actual event times against targets."""
    if len(actual) != len(target):
        raise ValueError("Events and downbeats must pair one-to-one")
    errors = [abs(a - b) for a, b in zip(actual, target)]
    return dict(status="PASS" if errors and max(errors) <= tolerance_ms else "FAIL",
                max_error_ms=max(errors, default=None), errors_ms=errors)
