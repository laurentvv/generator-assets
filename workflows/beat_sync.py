#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Beat Sync Workflow: local beat/tempo analysis of a music file
(numpy-only "rms" engine) + suggested cut/schedule plan on the beat grid.

Ported from miles990/video-gif-studio (MIT) — scripts/music_sync.py
(rms engine) + scripts/audio_beat_sync.py. The neural `beat_this`
backend is NOT ported (PyTorch). Upstream caveat kept: the rms engine is
a periodicity heuristic — review the produced beats.json (BPM/offset
editable via flags) before using the cut plan.

Outputs (fresh run directory):
- beats.json (bpm, offset_ms, beats_ms, onsets_ms, waveform, candidates)
- waveform.svg (review artifact)
- schedule.json (animation cycles on the beat grid = suggested cut points)

Uses the shared flag: -i/--input (audio file: WAV PCM16 natively, other
formats decoded via FFmpeg at 8 kHz mono).
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from core.beat_grid import (
    analyze_beats,
    schedule_beat_cycles,
    write_beats_record,
)
from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class BeatSyncWorkflow(BaseWorkflow):
    """Music → beats.json (BPM/beat grid) + suggested cut plan (rms engine)."""

    name = "beat_sync"
    description = ("Local beat analysis of a music file (numpy rms engine, no PyTorch) + "
                   "beat-aligned cut/schedule plan for the video chain")

    emoji = "🥁"

    PARAMETRES = [
        dict(flags=("--bpm",), type=float, default=None,
             help="beat_sync: force the tempo (20..400) instead of the periodicity heuristic — e.g.: 120."),
        dict(flags=("--offset-ms",), type=float, default=None,
             help="beat_sync: force the first-beat offset in ms (nonnegative)."),
        dict(flags=("--beats-per-cycle",), type=int, default=2,
             help="beat_sync: beats spanned by one schedule cycle (default: 2)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        source = params.get("input")
        if not source:
            raise ValueError("beat_sync requires -i/--input (audio file)")
        source_path = source if isinstance(source, Path) else Path(source)
        if not source_path.exists():
            raise FileNotFoundError(f"Input not found: {source_path}")
        bpm: Optional[float] = params.get("bpm")
        offset_ms: Optional[float] = params.get("offset_ms")
        beats_per_cycle = int(params.get("beats_per_cycle") or 2)
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        nom_base = params.get("output") or slugifier_texte(source_path.stem + " beats")

        run_dir = Path(output_dir) / nom_base
        suffix = 0
        while (run_dir / "beats.json").exists():
            suffix += 1
            run_dir = Path(output_dir) / f"{nom_base}_{suffix}"

        self.log(f"Analyzing {source_path} (rms engine, no PyTorch)", emoji="🎧")
        record = analyze_beats(source_path, bpm=bpm, offset_ms=offset_ms)
        artifacts = write_beats_record(record, run_dir)
        if record["bpm"]:
            self.log(f"BPM {record['bpm']:.0f} (offset {record['offset_ms']:.0f} ms, "
                     f"{len(record['beats_ms'])} beats, {len(record['onsets_ms'])} onsets)", emoji="🥁")
        else:
            self.log("No confident tempo found — provide --bpm (review waveform.svg)", emoji="⚠️")
        self.log(f"Review before use: {record['review']}", emoji="📝")

        result: Dict[str, Any] = {
            "run_dir": str(run_dir),
            "beats_json": artifacts["beats_json"],
            "waveform_svg": artifacts["waveform_svg"],
            "bpm": record["bpm"],
            "offset_ms": record["offset_ms"],
            "duration_ms": record["duration_ms"],
            "beats_count": len(record["beats_ms"]),
            "engine": record["engine"],
        }

        if record["bpm"] and len(record["beats_ms"]) >= beats_per_cycle + 1:
            schedule = schedule_beat_cycles(record, beats_per_cycle=beats_per_cycle)
            schedule_path = run_dir / "schedule.json"
            schedule_path.write_text(json.dumps(schedule, indent=2) + "\n", encoding="utf-8")
            cuts = [cycle["start_ms"] for cycle in schedule["cycles"]]
            self.log(f"Suggested cut points ({len(cuts)}): {cuts[:8]}"
                     f"{'…' if len(cuts) > 8 else ''} ms", emoji="✂️")
            result["schedule"] = str(schedule_path)
            result["suggested_cuts_ms"] = cuts
        return result
