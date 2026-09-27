#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vocal Removal Workflow: removal of the vocals from a track by HTDemucs source
separation (audio.cpp, Vulkan). User-validated on
2026-09-06 on a full 4 min 07 s track.

Produces the vocal-free instrumental (drums+bass+other mix at preserved
levels) + the 4 full stems (drums, bass, other, vocals).
"""

import os
from typing import Any, Dict

from core.config import slugifier_texte
from core.separation import retirer_voix
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class RetraitVoixWorkflow(BaseWorkflow):
    """Vocal removal from a track (HTDemucs GGUF, Vulkan) — instrumental + stems."""

    name = "retrait_voix"
    description = ("Removes the vocals from a track via HTDemucs (audio.cpp Vulkan): "
                   "voice-free instrumental + 4 stems (drums/bass/other/vocals), "
                   "automatic 44.1 kHz resampling")

    emoji = "🎧"
    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        source = params.get("input")
        if not source or not os.path.exists(source):
            raise ValueError("Audio source not found: pass it via -i <MP3/WAV>.")
        backend = params.get("music_backend") or "vulkan"
        if backend == "auto":
            backend = "vulkan"

        nom = slugifier_texte(params.get("output") or os.path.splitext(os.path.basename(source))[0])[:60]
        dossier = os.path.join("output", "retrait_voix", nom)

        self.log(f"HTDemucs separation of {source} (backend {backend})", "🎧")
        res = retirer_voix(source, dossier, backend=backend)
        self.log(f"Instrumental ready: {res['instrumental_mp3']} — listen to validate", "✅")
        self.log(f"Stems kept: {res['stems_dir']} (isolated vocals: vocals.wav)", "📦")
        return res
