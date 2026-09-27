#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio Ambience Workflow: immersive sound ambiences & procedural soundscapes for Godot 4.
Produces:
- Stereo WAV audio file (PCM 16-bit)
- Seamless continuous loop OGG Vorbis audio file (Seamless Loop)
- Godot 4 AudioBusLayout resource (.tres) with atmospheric Reverb and Filters
- Godot 4 AudioStreamPlayer scene (.tscn)
"""

import os
from typing import Any, Dict

from core.audio_ops import exporter_ambiance_godot, synthetiser_ambiance
from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from workflows.base import BaseWorkflow, WorkflowRegistry


def exporter_scene_ambiance_godot(
    nom_base: str,
    output_dir: str,
    chemin_rel_ogg: str
) -> str:
    """Generates a Godot 4 scene with an AudioStreamPlayer set to loop on the Ambience bus."""
    chemin_tscn = os.path.join(output_dir, f"{nom_base}_player.tscn")
    code_tscn = f"""[gd_scene load_steps=2 format=3]

[ext_resource type="AudioStream" path="{chemin_rel_ogg}" id="1_ogg"]

[node name="{nom_base}_AmbiencePlayer" type="AudioStreamPlayer"]
stream = ExtResource("1_ogg")
autoplay = true
bus = &"Ambience"
"""
    with open(chemin_tscn, "w", encoding="utf-8") as f:
        f.write(code_tscn)

    return chemin_tscn


@WorkflowRegistry.register
class AudioAmbienceWorkflow(BaseWorkflow):
    """Generation of loopable soundscapes and immersive ambiences for Godot 4."""

    name = "audio_ambience"
    description = "Immersive sound ambiences & procedural soundscapes in seamless loops for Godot 4 (.wav / .ogg / .tres)"

    emoji = "🌌"

    # CLI declaration (audit §2.2, migration from cli/parser.py's flat table:
    # help/defaults kept as-is, unchanged surface). Flag kept for the
    # surface: the run reads flow_type then vfx_type first (ambience_type
    # is currently read nowhere — do not wire it without validation).
    PARAMETRES = [
        dict(flags=("--ambience-type",), choices=["dungeon", "forest", "storm", "space", "campfire", "tavern"],
             help="Ambience type for audio_ambience."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        prompt = params.get("prompt") or "dungeon"
        ambience_type = params.get("flow_type") or params.get("vfx_type") or prompt
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        duree = float(params.get("duration", 8.0))
        nom_base = params.get("output") or f"{slugifier_texte(prompt)}_ambience"

        os.makedirs(output_dir, exist_ok=True)

        self.log(f"Stereo sound ambience synthesis for '{prompt}' (Duration: {duree:.1f}s, seamless loop)...")

        # Multilayer stereo looped synthesis
        audio_stereo = synthetiser_ambiance(ambience_type=ambience_type, duree=duree, sr=44100)

        # Audio export and Godot 4 bus
        self.log("Exporting the audio formats and configuring the Godot 4 bus...")
        chemin_wav, chemin_ogg, chemin_bus = exporter_ambiance_godot(nom_base, output_dir, audio_stereo, sr=44100)

        # Godot 4 scene
        chemin_tscn = exporter_scene_ambiance_godot(nom_base, output_dir, f"res://{nom_base}.ogg")

        self.log(f"Sound ambience exported successfully to '{output_dir}/':", emoji="🎉")
        self.log(f"  • 16-bit WAV track : {chemin_wav}")
        self.log(f"  • OGG Loop track   : {chemin_ogg}")
        self.log(f"  • AudioBusLayout   : {chemin_bus}")
        self.log(f"  • Godot 4 scene    : {chemin_tscn}", emoji="💎")

        return {
            "wav": chemin_wav,
            "ogg": chemin_ogg,
            "bus_layout": chemin_bus,
            "scene_tscn": chemin_tscn,
            "duration": duree,
            "files": [chemin_wav, chemin_ogg, chemin_bus, chemin_tscn]
        }
