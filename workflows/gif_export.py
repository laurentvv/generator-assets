#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GIF Export Workflow: deterministic transparent GIF / APNG / RGBA frames from
a video or a PNG sequence (Pillow + FFmpeg, CPU-only).

Ported from miles990/video-gif-studio (MIT). Outputs (fresh run directory):
- frames/NNNNN.png (RGBA masters, soft alpha preserved)
- animation.gif (255-color shared palette, index 255 reserved for
  transparency, disposal=2 — upstream invariant intact)
- animation.apng (full-color master, fractional alpha)
- contact.png (alternating light/dark cells for visual review)
- alpha-qa.json (+ holes overlay when enclosed regions are found)
- optional sprite sheet + Godot 4 atlas manifest (--sprite-sheet)
- manifest.json (provenance: sha256, timings, key settings, QC record)
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from core.alpha_qa import alpha_qa_report
from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.gif_export import (
    _sha256,
    build_contact_sheet,
    compute_frame_timing,
    encode_apng,
    encode_gif,
    extract_video_frames,
    load_png_frames,
    verify_gif,
)
from core.image_ops import assembler_spritesheet
from workflows.base import BaseWorkflow, WorkflowRegistry


def _parse_key_hex(key: Optional[str]) -> Optional[Tuple[int, int, int]]:
    if not key:
        return None
    try:
        values = tuple(bytes.fromhex(key.lstrip("#")))
    except ValueError as exc:
        raise ValueError("Key must have six hexadecimal digits (e.g. FF00FF)") from exc
    if len(values) != 3:
        raise ValueError("Key must have six hexadecimal digits (e.g. FF00FF)")
    return values


@WorkflowRegistry.register
class GifExportWorkflow(BaseWorkflow):
    """Video / PNG-sequence → transparent GIF + APNG + RGBA frames with alpha QA gate."""

    name = "gif_export"
    description = ("Transparent GIF / APNG / RGBA frames from a video or PNG sequence "
                   "(255-color palette invariant, alpha QA gate, optional Godot sprite sheet)")

    emoji = "🎞️"

    # Uses the shared flags: -i/--input, --fps (conform rate or PNG-sequence
    # rate), --width (resize width, default 640), --columns (sprite sheet).
    PARAMETRES = [
        dict(flags=("--key",), default=None,
             help="gif_export: uniform background hex RGB (e.g. FF00FF) to chroma-key into transparency; omit to preserve existing alpha."),
        dict(flags=("--key-tolerance",), type=float, default=0.15,
             help="gif_export chroma-key: chroma distance where keying starts (default: 0.15)."),
        dict(flags=("--key-softness",), type=float, default=0.12,
             help="gif_export chroma-key: chroma distance over which alpha ramps 0→1 (default: 0.12)."),
        dict(flags=("--sprite-sheet",), action="store_true",
             help="gif_export: also pack the selected frames into a sprite sheet + Godot 4 atlas JSON (--columns sets the grid)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        source = params.get("input")
        if not source:
            raise ValueError("gif_export requires -i/--input (video file or PNG sequence directory)")
        source_path = source if isinstance(source, Path) else Path(source)
        if not source_path.exists():
            raise FileNotFoundError(f"Input not found: {source_path}")
        is_directory = source_path.is_dir()
        fps_conform = params.get("fps")
        resize_width = int(params.get("width") or 640)
        key = _parse_key_hex(params.get("key"))
        tolerance = float(params.get("key_tolerance") or 0.15)
        softness = float(params.get("key_softness") or 0.12)
        want_sprites = bool(params.get("sprite_sheet"))
        columns = int(params.get("columns") or 4)
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        nom_base = params.get("output") or slugifier_texte(source_path.stem + " gif")

        # Fresh run directory (upstream rule: never overwrite source assets);
        # auto-suffix -1, -2… when the natural name is taken.
        run_dir = Path(output_dir) / nom_base
        suffix = 0
        while run_dir.exists() and any(run_dir.iterdir()):
            suffix += 1
            run_dir = Path(output_dir) / f"{nom_base}_{suffix}"
        run_dir.mkdir(parents=True, exist_ok=True)

        self.log(f"Source: {source_path}", emoji="📥")
        if is_directory:
            if not fps_conform:
                raise ValueError("PNG-sequence input requires --fps (frame rate of the sequence)")
            frames = load_png_frames(source_path, resize_width=resize_width,
                                     key=key, tolerance=tolerance, softness=softness)
            fps = float(fps_conform)
        else:
            frames, fps = extract_video_frames(
                source_path, run_dir, fps_conform=fps_conform,
                resize_width=resize_width, key=key,
                tolerance=tolerance, softness=softness)

        indices, durations = compute_frame_timing(len(frames), fps)
        selected = [frames[i] for i in indices]
        self.log(f"{len(frames)} source frames @ {fps:.3f} fps → {len(selected)} GIF frames "
                 f"(total {sum(durations)} ms)", emoji="⏱️")

        frames_dir = run_dir / "frames"
        frames_dir.mkdir(exist_ok=True)
        for j, image in enumerate(selected):
            image.save(frames_dir / f"{j:05d}.png")

        gif_path = run_dir / "animation.gif"
        encode_gif(selected, durations, gif_path)
        qc = verify_gif(gif_path, selected, durations)
        self.log(f"GIF encoded + verified (alpha mismatch: {qc['alpha_mismatch_pixels']} px, "
                 f"mean RGB error: {qc['mean_visible_rgb_error']:.2f})", emoji="✅")
        apng_path = run_dir / "animation.apng"
        encode_apng(selected, durations, apng_path)
        contact_path = run_dir / "contact.png"
        build_contact_sheet(selected, contact_path)

        # Alpha QA gate on the first selected frame (sticker-style sources).
        qa = alpha_qa_report(selected[0], overlay_path=run_dir / "alpha-holes.png")
        (run_dir / "alpha-qa.json").write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
        if qa["status"] != "PASS":
            self.log(f"Alpha QA {qa['status']}: {', '.join(qa['issues'])} — review "
                     f"alpha-holes.png before delivery (artifacts written, verdict reported as-is).",
                     emoji="⚠️")
        else:
            self.log("Alpha QA PASS", emoji="🔬")

        result: Dict[str, Any] = {
            "run_dir": str(run_dir),
            "gif": str(gif_path),
            "apng": str(apng_path),
            "frames_dir": str(frames_dir),
            "contact_sheet": str(contact_path),
            "alpha_qa": qa,
            "qc": qc,
            "source_fps": fps,
            "selected_frames": len(selected),
        }

        if want_sprites:
            names = [f"frame_{i:04d}" for i in range(len(selected))]
            sheet, metadata = assembler_spritesheet(selected, names, colonnes=columns)
            sheet_path = run_dir / "spritesheet.png"
            sheet.save(sheet_path)
            atlas_path = run_dir / "spritesheet_godot4.json"
            atlas_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
            result["spritesheet"] = str(sheet_path)
            result["spritesheet_atlas"] = str(atlas_path)
            self.log(f"Sprite sheet {sheet.size} ({metadata['columns']}x{metadata['rows']})", emoji="🧩")

        # Provenance parents: sha256 per source file (each PNG when the input
        # is a sequence directory, the file itself otherwise).
        if is_directory:
            parent_files = sorted(source_path.glob("*.png"), key=lambda p: p.name)
        else:
            parent_files = [source_path]
        manifest = {
            "parents": [{"file": str(f.resolve()), "sha256": _sha256(f)} for f in parent_files],
            "source_fps": fps,
            "source_frames": len(frames),
            "selected_indices": indices,
            "durations_ms": durations,
            "key_rgb": list(key) if key else None,
            "key_tolerance": tolerance, "key_softness": softness,
            "size": list(selected[0].size),
            "transparency_index": 255,
            "script": "core/gif_export.py (ported from miles990/video-gif-studio, MIT)",
            "gif_sha256": _sha256(gif_path),
            "qc": qc,
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return result
