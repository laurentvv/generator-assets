#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio Repaint / Inpaint Workflow: surgical time-span audio regeneration.

Supports two Wave 1 user-validated regimes (2026-11-14):
- ``acestep`` (default, MIT, CPU): ACE-Step 1.5 ``repaint`` (xl-turbo default),
  bit-exact PCM16 preservation outside ``[start, end]``.
- ``sa3`` (Stability AI Community License, Vulkan): Stable Audio 3 Medium
  ``inpaint_audio``, ~27x faster on GPU (re-encodes full mix).
"""

import os
from typing import Any, Dict

from core.config import (
    DEFAULT_OUTPUT_DIR,
    classifier_licence_workflow,
    slugifier_texte,
)
from core.music_ai import (
    convertir_mp3,
    inpaint_stable_audio,
    repaint_acestep,
)
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class AudioRepaintWorkflow(BaseWorkflow):
    """Surgical audio time-span repainting (ACE-Step 1.5 bit-exact or SA3 Medium Vulkan)."""

    name = "audio_repaint"
    description = (
        "Surgical audio repainting over a time span: ACE-Step 1.5 repaint "
        "(default, MIT, bit-exact outside mask) or Stable Audio 3 Medium "
        "inpaint_audio (--repaint-engine sa3, fast Vulkan, Stability AI Community License)"
    )
    emoji = "🩹"

    # Consumes --audio (declared once in acestep_cover) or -i as input source.
    PARAMETRES = [
        dict(
            flags=("--repaint-engine",),
            dest="repaint_engine",
            choices=["acestep", "sa3"],
            default="acestep",
            help="Repaint engine: acestep (MIT, CPU bit-exact outside mask, default) | "
                 "sa3 (Stable Audio 3 Medium Vulkan, fast, Stability AI Community License).",
        ),
        dict(
            flags=("--repaint-start",),
            dest="repaint_start",
            type=float,
            default=None,
            help="audio_repaint: repaint mask start time in seconds (>= 0).",
        ),
        dict(
            flags=("--repaint-end",),
            dest="repaint_end",
            type=float,
            default=None,
            help="audio_repaint: repaint mask end time in seconds (> --repaint-start).",
        ),
        dict(
            flags=("--repaint-mode",),
            dest="repaint_mode",
            choices=["balanced", "conservative", "aggressive"],
            default="balanced",
            help="audio_repaint (acestep): blend preset (default: balanced).",
        ),
        dict(
            flags=("--repaint-strength",),
            dest="repaint_strength",
            type=float,
            default=None,
            help="audio_repaint: optional blend / noise strength in [0, 1] "
                 "(maps to SA3 init_noise_level when using --repaint-engine sa3).",
        ),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        source = params.get("audio") or params.get("input")
        description = (params.get("prompt") or "").strip()
        if not source or not os.path.exists(source):
            raise ValueError("Audio source not found: pass --audio <path> or -i <path>.")
        if not description:
            raise ValueError("Missing prompt: pass -p \"<description of the repainted span>\".")

        start_raw = params.get("repaint_start")
        end_raw = params.get("repaint_end")
        if start_raw is None or end_raw is None:
            raise ValueError(
                "Missing repaint interval: pass --repaint-start <sec> and --repaint-end <sec>."
            )
        start_sec = float(start_raw)
        end_sec = float(end_raw)

        engine = (params.get("repaint_engine") or "acestep").lower()
        graine = int(params.get("seed", 42))
        output_dir = params.get("output_dir") or DEFAULT_OUTPUT_DIR
        nom = slugifier_texte(
            params.get("output")
            or f"{os.path.splitext(os.path.basename(source))[0]}_{engine}_repaint"
        )[:60]
        chemin_wav = os.path.join(output_dir, "audio_repaint", f"{nom}.wav")

        licence = classifier_licence_workflow("audio_repaint", moteur=engine)
        if engine == "sa3":
            strength = params.get("repaint_strength")
            strength_val = 1.0 if strength is None else float(strength)
            steps_raw = params.get("steps")
            steps = 8 if steps_raw in (None, 25) else int(steps_raw)
            raw_cfg = params.get("cfg_scale")
            guidance = 1.0 if raw_cfg is None else float(raw_cfg)
            backend = params.get("music_backend") or "vulkan"
            if backend == "auto":
                backend = "vulkan"
            self.log(
                f"Stable Audio 3 Medium inpaint [{start_sec:g}s..{end_sec:g}s] "
                f"(steps={steps}, noise={strength_val:g}, {licence['licence']})..."
            )
            wav, backend_used = inpaint_stable_audio(
                source,
                description,
                chemin_wav,
                start_sec=start_sec,
                end_sec=end_sec,
                strength=strength_val,
                steps=steps,
                guidance=guidance,
                graine=graine,
                backend=backend,
                log=self.log,
            )
        else:
            variante = params.get("variante") or "xl-turbo"
            repaint_mode = params.get("repaint_mode") or "balanced"
            strength = params.get("repaint_strength")
            threads = int(params.get("cover_threads") or 20)
            steps_raw = params.get("steps")
            steps = None if steps_raw in (None, 25) else int(steps_raw)
            lyrics = params.get("lyrics")
            if isinstance(lyrics, str):
                candidate = lyrics.strip()
                if os.path.isfile(candidate) and candidate.lower().endswith(".txt"):
                    with open(candidate, encoding="utf-8") as f:
                        lyrics = f.read().strip()
                if not lyrics or lyrics == "[Instrumental]":
                    lyrics = None
            langue = params.get("langue")
            self.log(
                f"ACE-Step 1.5 ({variante}) repaint [{start_sec:g}s..{end_sec:g}s] "
                f"(mode={repaint_mode}, bit-exact outside mask, CPU ×{threads})..."
            )
            wav, backend_used = repaint_acestep(
                source,
                description,
                chemin_wav,
                start_sec=start_sec,
                end_sec=end_sec,
                variante=variante,
                repaint_mode=repaint_mode,
                repaint_strength=float(strength) if strength is not None else None,
                lyrics=lyrics,
                langue=langue,
                steps=steps,
                graine=graine,
                threads=threads,
                log=self.log,
            )

        chemin_mp3 = convertir_mp3(wav, wav.replace(".wav", ".mp3"), 224)
        self.log(f"Repaint ready: {chemin_mp3} (engine={engine}, backend={backend_used})", emoji="🎧")
        return {
            "wav": wav,
            "mp3": chemin_mp3,
            "engine": engine,
            "backend": backend_used,
            "start": start_sec,
            "end": end_sec,
            "licence": licence,
        }
