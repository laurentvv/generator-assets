#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alpha QA Workflow: verdict PASS/FAIL on a transparent PNG asset
(stickers, sprites, detourer_fond_blanc outputs) with a holes overlay.

Ported from miles990/video-gif-studio (MIT) — detection gates only
(fake checkerboard transparency, coverage fraction, clipped border,
specks, enclosed holes, halo ΔE, black outer luma). The verdict is
purely local and deterministic (no LLM judge ported).

Uses the shared flag: -i/--input (source image, alpha expected).
Outputs (output_dir): <stem>_alpha-qa.json + <stem>_alpha-holes.png
when enclosed regions are detected.
"""

import json
from pathlib import Path
from typing import Any, Dict

from PIL import Image

from core.alpha_qa import alpha_qa_report
from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class AlphaQaWorkflow(BaseWorkflow):
    """Transparent-asset alpha QA gate (PASS/FAIL + holes overlay)."""

    name = "alpha_qa"
    description = ("Alpha QA verdict on a transparent PNG (fake checkerboard, coverage, border, "
                   "specks, holes, halo — deterministic, no LLM)")

    emoji = "🔬"

    PARAMETRES = []

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        source = params.get("input")
        if not source:
            raise ValueError("alpha_qa requires -i/--input (source image, alpha expected)")
        source_path = source if isinstance(source, Path) else Path(source)
        if not source_path.exists():
            raise FileNotFoundError(f"Input not found: {source_path}")
        output_dir = Path(params.get("output_dir", DEFAULT_OUTPUT_DIR))
        nom_base = params.get("output") or slugifier_texte(source_path.stem + " alpha qa")

        image = Image.open(source_path).convert("RGBA")
        overlay_path = output_dir / f"{nom_base}_alpha-holes.png"
        report = alpha_qa_report(image, overlay_path=overlay_path)
        report_path = output_dir / f"{nom_base}_alpha-qa.json"
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

        if report["status"] == "PASS":
            self.log(f"Alpha QA PASS ({report['transparent_fraction']:.0%} transparent, "
                     f"{report['fractional_alpha_pixels']} fractional-alpha px)", emoji="✅")
        else:
            # QA gate semantics (lesson 2026-10-30): a gate that cannot fail the
            # chain is not a gate — FAIL exits non-zero (report + overlay are
            # already written to disk for inspection).
            self.log(f"Alpha QA FAIL: {', '.join(report['issues'])} — report: {report_path}", emoji="⛔")
            raise RuntimeError(f"Alpha QA FAIL ({', '.join(report['issues'])}); report: {report_path}")
        if report["hole_regions"]:
            self.log(f"{len(report['hole_regions'])} enclosed region(s) marked in {overlay_path}",
                     emoji="🔍")

        return {
            "report": str(report_path),
            "overlay": str(overlay_path) if report["hole_regions"] else None,
            "status": report["status"],
            "issues": report["issues"],
            "metrics": {k: report[k] for k in (
                "transparent_fraction", "clear_border_fraction", "speck_ratio",
                "interior_hole_ratio", "halo_good_fraction", "black_outer_luma")},
        }
