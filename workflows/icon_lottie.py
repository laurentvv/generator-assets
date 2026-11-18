#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Icon Lottie Workflow: useAnimations animated icons → transparent GIF / APNG /
RGBA frames (overlays for video compositing or Godot UI).

Port of the useAnimations icon pipeline (MIT icons, 300 stroke icons 32×32
@ 30 fps). Chain: npm tarball cached once under `output/lottie_cache/` →
Node.js extracts the embedded Lottie `animationData` → python-lottie loads
it and exports per-frame SVG → resvg (static binary, C:\\resvg or RESVG_PATH)
rasterizes RGBA → `core.gif_export` delivery machinery (GIF invariant,
timeline verify, contact sheet) + `core.alpha_qa` gate report.

Requires: node (PATH) for extraction, resvg 0.50+ for rasterization
(v0.50.0 win-x64 official asset sha256 e4817e40… — upstream publishes the
digest via the GitHub release API only).
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from core.alpha_qa import alpha_qa_report
from core.config import DEFAULT_OUTPUT_DIR
from core.gif_export import (
    build_contact_sheet,
    compute_frame_timing,
    encode_apng,
    encode_gif,
    sha256_file,
    verify_gif,
)
from core.lottie_raster import (
    DEFAULT_CACHE_DIR,
    USEANIMATIONS_VERSION,
    export_icon_data,
    fetch_useanimations,
    list_icons,
    load_animation,
    recolor_animation,
    render_frames,
    resolve_resvg,
)
from workflows.base import BaseWorkflow, WorkflowRegistry


def _parse_hex_rgb(value: Optional[str]) -> Optional[Tuple[int, int, int]]:
    if not value:
        return None
    try:
        components = tuple(bytes.fromhex(value.lstrip("#")))
    except ValueError as exc:
        raise ValueError("Color must have six hexadecimal digits (e.g. E0E0E0)") from exc
    if len(components) != 3:
        raise ValueError("Color must have six hexadecimal digits (e.g. E0E0E0)")
    return components


@WorkflowRegistry.register
class IconLottieWorkflow(BaseWorkflow):
    """useAnimations icon → transparent GIF/APNG/frames (Lottie → resvg, CPU-only)."""

    name = "icon_lottie"
    description = ("Animated icons (useAnimations, 300 MIT Lottie icons) → transparent GIF / APNG / "
                   "RGBA frames via node + python-lottie + resvg — overlays for video compositing / Godot")

    emoji = "🎬"

    # Uses the shared flags: --size (render size, default 128), -o (name base).
    PARAMETRES = [
        dict(flags=("--icon",), default=None,
             help="icon_lottie: comma-separated useAnimations icon names (e.g. 'anchor,settings'); "
                  "run with --list-icons first. Source: cached npm tarball (output/lottie_cache/)."),
        dict(flags=("--list-icons",), action="store_true",
             help="icon_lottie: list the icon names available in the cached npm package and exit."),
        dict(flags=("--lottie-color",), default=None,
             help="icon_lottie: tint the icon (hex RGB, e.g. E0E0E0) — icons ship black; tinting "
                  "happens at the Lottie level (exact, alpha preserved)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # icon cache always lives at output/lottie_cache regardless of -d
        # (a custom delivery dir must not relocate/re-download the tarball)
        lib_dir = fetch_useanimations(DEFAULT_CACHE_DIR)
        available = list_icons(lib_dir)

        if params.get("list_icons"):
            self.log(f"{len(available)} icons available (useAnimations {USEANIMATIONS_VERSION}): "
                     f"{', '.join(available[:20])}{'…' if len(available) > 20 else ''}", emoji="📋")
            return {"icons": available, "count": len(available), "cache": str(lib_dir)}

        icon_param = params.get("icon")
        if not icon_param:
            raise ValueError("icon_lottie requires --icon (comma-separated names) or --list-icons")
        icons = [name.strip() for name in str(icon_param).split(",") if name.strip()]
        unknown = [name for name in icons if name not in available]
        if unknown:
            raise ValueError(f"Unknown icon(s): {', '.join(unknown)} — run with --list-icons")
        size = int(params.get("size") or 128)
        tint = _parse_hex_rgb(params.get("lottie_color"))
        output_dir = Path(params.get("output_dir", DEFAULT_OUTPUT_DIR))
        resvg = resolve_resvg()

        self.log(f"resvg: {resvg} | icons: {', '.join(icons)} | size {size}"
                 f"{' | tint ' + params['lottie_color'] if tint else ''}", emoji="🎬")
        results = []
        base_name = params.get("output")
        for icon in icons:
            # -o = exact run-dir name for a single icon, prefix for several
            # (multi-icon runs always suffix the icon name to stay distinct)
            if base_name and len(icons) == 1:
                run_dir = output_dir / base_name
            else:
                run_dir = output_dir / f"{base_name or 'icon'}_{icon}"
            suffix = 0
            while run_dir.exists() and any(run_dir.iterdir()):
                suffix += 1
                name = base_name if (base_name and len(icons) == 1) else f"{base_name or 'icon'}_{icon}"
                run_dir = output_dir / f"{name}_{suffix}"
            run_dir.mkdir(parents=True, exist_ok=True)

            data = export_icon_data(lib_dir / f"{icon}.js")
            if tint:
                data, skipped_colors = recolor_animation(data, tint)
                if skipped_colors:
                    self.log(f"{icon}: {skipped_colors} non-flat color(s) left untinted "
                             f"(keyframed/gradient) — inspect before delivery", emoji="⚠️")
            animation = load_animation(data)
            frames, fps, frame_count = render_frames(animation, size=size, resvg_path=resvg)
            indices, durations = compute_frame_timing(len(frames), fps)
            selected = [frames[i] for i in indices]

            frames_dir = run_dir / "frames"
            frames_dir.mkdir(exist_ok=True)
            for j, image in enumerate(selected):
                image.save(frames_dir / f"{j:05d}.png")

            gif_path = run_dir / "icon.gif"
            encode_gif(selected, durations, gif_path)
            qc = verify_gif(gif_path, selected, durations)
            apng_path = run_dir / "icon.apng"
            encode_apng(selected, durations, apng_path)
            contact_path = run_dir / "contact.png"
            build_contact_sheet(selected, contact_path)

            qa = alpha_qa_report(selected[0], overlay_path=run_dir / "alpha-holes.png")
            (run_dir / "alpha-qa.json").write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")

            manifest = {
                "icon": icon,
                "package": f"react-useanimations@{USEANIMATIONS_VERSION}",
                "size": size,
                "tint_rgb": list(tint) if tint else None,
                "fps": fps,
                "source_frames": len(frames),
                "selected_indices": indices,
                "durations_ms": durations,
                "gif_sha256": sha256_file(gif_path),
                "qc": qc,
                "alpha_qa": qa,
            }
            (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                                   encoding="utf-8")
            self.log(f"{icon}: {frame_count} frames @ {fps:.0f} fps → GIF verified "
                     f"(0 mismatch: {qc['alpha_mismatch_pixels'] == 0}), alpha QA {qa['status']}",
                     emoji="✅" if qc["technical_pass"] and qa["status"] == "PASS" else
                           ("⚠️" if qc["technical_pass"] else "⛔"))
            results.append({
                "icon": icon,
                "run_dir": str(run_dir),
                "gif": str(gif_path),
                "apng": str(apng_path),
                "frames_dir": str(frames_dir),
                "contact_sheet": str(contact_path),
                "alpha_qa": qa,
                "qc": qc,
                "frames": frame_count,
                "duration_ms": sum(durations),
            })
        return {"icons_done": results, "count": len(results)}
