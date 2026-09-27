#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Robot Voice Workflow: English synthesis by Kokoro-82M (audio.cpp Vulkan) + FFmpeg
"little robot" effect (+30 % pitch, 120 Hz ring modulation, laid-back pace, -4 dB gain).

RECIPE USER-VALIDATED on 2026-09-17 (attempt 17: "c'est bien") — details and
engine pitfall (espeak) in MEMORY_BANK §1.21 and the docstring of core/voix_robot.py.
Text in English (model prompts in English, repo conventions).
"""

import os
from typing import Any, Dict

from core.config import slugifier_texte
from core.voix_robot import RECIPE, generer_voix_robot
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class VoixRobotWorkflow(BaseWorkflow):
    """Robot voice in English (Kokoro + ring modulation, validated recipe)."""

    name = "voix_robot"
    description = ("Robot voice in English — Kokoro-82M TTS (Vulkan) + FFmpeg effect "
                   "pitch/ring modulation (validated recipe 2026-09-17) — .wav + .mp3")

    emoji = "🤖"

    # CLI declarations (audit §2.2, migration from cli/parser.py's flat table:
    # help/defaults kept as-is, unchanged surface).
    PARAMETRES = [
        dict(flags=("--robot-voice",), default="af_heart",
             help="Kokoro voice for voix_robot (default: af_heart, validated)."),
        dict(flags=("--robot-pitch",), type=float, default=1.30,
             help="voix_robot pitch factor (default: 1.30 = +30 %%, validated)."),
        dict(flags=("--robot-ringmod",), type=float, default=120.0,
             help="voix_robot ring modulation frequency in Hz (default: 120, validated)."),
        dict(flags=("--robot-tempo",), type=float, default=0.65,
             help="voix_robot post-pitch atempo (default: 0.65, validated \"relaxed\" pace)."),
        dict(flags=("--robot-gain",), type=float, default=-4.0,
             help="voix_robot final gain in dB (default: -4, validated \"calm\" voice)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        brut = (params.get("prompt") or "").strip()
        if not brut:
            raise ValueError("Provide the English text to read (positional parameter).")
        if os.path.isfile(brut) and brut.lower().endswith(".txt"):
            with open(brut, encoding="utf-8") as f:
                texte = f.read().strip()
            self.log(f"Text loaded from {brut} ({len(texte)} characters)", "📄")
        else:
            texte = brut
        if not texte:
            raise ValueError("The text to read is empty.")

        voice_id = params.get("robot_voice") or RECIPE["voice_id"]
        pitch = float(params.get("robot_pitch") or RECIPE["pitch"])
        ringmod_hz = float(params.get("robot_ringmod") or RECIPE["ringmod_hz"])
        tempo = float(params.get("robot_tempo") or RECIPE["tempo"])
        gain_db = float(params.get("robot_gain", RECIPE["gain_db"]))

        nom = slugifier_texte(params.get("output") or "voix_robot")[:60]
        output_dir = params.get("output_dir") or ""
        if not output_dir or output_dir == "godot_assets":
            output_dir = "output/voix_robot"
        dossier = os.path.join(output_dir, nom)
        os.makedirs(dossier, exist_ok=True)

        self.log(f"Validated recipe: voice {voice_id}, pitch +{int((pitch - 1) * 100)} %, "
                 f"ring mod {ringmod_hz:g} Hz, atempo {tempo}, gain {gain_db:+g} dB", "🤖")
        res = generer_voix_robot(
            texte=texte, dossier=dossier, nom=nom, voice_id=voice_id,
            pitch=pitch, ringmod_hz=ringmod_hz, tempo=tempo, gain_db=gain_db,
        )

        self.log("Robot voice generated:", emoji="🎉")
        self.log(f"  • WAV: {res['wav']} (PCM 16-bit, 24 kHz)")
        self.log(f"  • Listening MP3: {res['mp3']}", emoji="💎")

        return {"wav": res["wav"], "mp3": res["mp3"], "brut": res["brut"],
                "files": [res["wav"], res["mp3"]]}
