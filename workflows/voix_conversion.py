#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Voice Conversion Workflow: renders an existing recording (speech/singing) in
the voice of a reference sample — Chatterbox (standard q8_0) via audio.cpp.

Engine: chatterbox `vc` task, Vulkan, fast. USER VALIDATED 2026-10-02
("voix anglaise bien") on the E01 narration A/B pair (qwen_expr → voxcpm).
⚠️ Output = 24 kHz mono WAV (speech-grade): for dialogue/voice lines — not
for musical beds. The Turbo variant is TTS-only and must not be used here.
"""

import os
from typing import Any, Dict

from core.config import DEFAULT_OUTPUT_DIR
from core.voix_conversion import generer_conversion_voix
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class VoixConversionWorkflow(BaseWorkflow):
    """Voice conversion (Chatterbox vc): re-voice a recording from a voice reference."""

    name = "voix_conversion"
    description = "Voice conversion via Chatterbox: re-voice an existing recording from a voice reference (24 kHz mono output)"
    emoji = "🎭"

    # ⚠️ --audio is declared ONCE (acestep_cover, registered first) and
    # consumed here too — argparse shared-group pitfall (§1.28). Neither flag
    # is argparse-required (shared parser): run() validates with clear errors.
    PARAMETRES = [
        dict(flags=("--voice-ref",), dest="voice_ref",
             help="Reference sample of the TARGET voice (a clean take of the desired speaker). Used by voix_conversion with --audio."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        source = params.get("audio")
        reference = params.get("voice_ref")
        if not source:
            raise SystemExit("❌ Voice conversion needs a source recording: pass --audio <path> (declared by the acestep_cover workflow, shared CLI flag).")
        if not reference:
            raise SystemExit("❌ Voice conversion needs a target voice: pass --voice-ref <clean take of the desired speaker>.")

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        nom = params.get("output") or (
            os.path.splitext(os.path.basename(source))[0]
            + "_vc_" + os.path.splitext(os.path.basename(reference))[0]
        )
        chemin_wav = os.path.join(output_dir, "voix_conversion", f"{nom}.wav")

        self.log(f"Voice conversion of '{os.path.basename(source)}' → voice of '{os.path.basename(reference)}' (Chatterbox, Vulkan)...")
        chemin = generer_conversion_voix(source, reference, chemin_wav)

        self.log(f"Converted voice ready: {chemin} (24 kHz mono — dialogue-grade)", emoji="🎧")
        return {"wav": chemin, "source": source, "voice_ref": reference}
