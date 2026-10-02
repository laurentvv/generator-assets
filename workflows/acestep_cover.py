#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ACE-Step Cover Workflow: re-styles an existing music track from a text prompt
while keeping its exact duration (audio → audio).

Engine: ACE-Step 1.5 turbo (2B, bf16 GGUF) via audio.cpp, CPU backend
(VAE-encoder buffer > AMD Vulkan 4 GiB limit on this machine, §1.34).
USER VALIDATED 2026-10-02: covers of the gothic reference llb_xl_adn.mp3
judged "correct" (3 strength probes) — first validated ACE-Step edit route;
the strength knobs are inert on turbo (proven by A/B) so none is exposed.

Output: WAV (48 kHz stereo, source-locked duration) + MP3 224k alongside.
"""

import os
from typing import Any, Dict

from core.config import DEFAULT_OUTPUT_DIR
from core.music_ai import convertir_mp3, generer_cover_acestep
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class AceStepCoverWorkflow(BaseWorkflow):
    """Re-style an existing track with ACE-Step 1.5 cover (duration locked)."""

    name = "acestep_cover"
    description = "ACE-Step 1.5 cover: re-style an existing track from a style prompt (duration locked to source, CPU backend)"
    emoji = "🎨"

    PARAMETRES = [
        # Not argparse-required: a global required flag would break every other
        # workflow (the parser is shared). run() validates with a clear error.
        dict(flags=("--audio",),
             help="Source track to re-style (wav/mp3/ogg — auto-converted to the engine's 48 kHz stereo input layout). Used by acestep_cover and voix_conversion."),
        dict(flags=("--cover-threads",), dest="cover_threads", type=int, default=20,
             help="CPU threads for the cover route (VAE encoder forces CPU; default 20 — the validated recipe)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        source = params.get("audio")
        style = (params.get("prompt") or "").strip()
        if not style:
            raise SystemExit("❌ The cover route needs a style prompt: pass -p \"<style description>\".")
        if not source:
            raise SystemExit("❌ No source track: pass --audio <path> (wav/mp3/ogg).")

        graine = int(params.get("seed", 42))
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        nom = params.get("output") or (
            os.path.splitext(os.path.basename(source))[0] + "_cover"
        )
        chemin_wav = os.path.join(output_dir, "music_cover", f"{nom}.wav")
        threads = int(params.get("cover_threads") or 20)

        self.log(f"ACE-Step 1.5 cover of '{os.path.basename(source)}' (style: '{style}', seed {graine}, CPU ×{threads})...")
        chemin, backend = generer_cover_acestep(
            source, style, chemin_wav, graine=graine, threads=threads,
            log=self.log,
        )

        chemin_mp3 = convertir_mp3(chemin, chemin.replace(".wav", ".mp3"), 224)
        self.log(f"Cover ready: {chemin_mp3} (backend {backend}, duration locked to source)", emoji="🎧")
        return {"wav": chemin, "mp3": chemin_mp3, "backend": backend, "source": source}
