#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SFX Workflow: generation of sound effects and SFX for game assets (Godot 4).
Produces:
- WAV audio file (PCM 16-bit)
- OGG Vorbis audio file (Godot-optimized Stream)

Engines (param `sfx_engine`):
- `ia` (default): Stable Audio 3 Small SFX via audio.cpp — user-validated on
  2026-09-09 (4/5 "ok", peak normalization integrated after the "low volume"
  rejection of the rain sample). Any descriptive EN prompt is possible.
- `procedural`: historical numpy synthesis (frozen types: sword, coin, explosion…).
"""

import os
from typing import Any, Dict
import numpy as np

from core.audio_ops import exporter_sfx_godot, synthetiser_sfx
from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.sfx_ia import generer_sfx_ia
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class SFXWorkflow(BaseWorkflow):
    """Generation of sound effects and SFX for Godot 4."""

    name = "sfx"
    description = "Video game sound effects & SFX (.wav / .ogg) — AI engine (SA3 small SFX) or procedural synthesis"

    emoji = "🔊"

    # CLI declarations (audit §2.2, migration from cli/parser.py's flat table:
    # help/defaults kept as-is, unchanged surface). --duration serves the whole
    # audio family (sfx, audio_ambience, music_bg, chanson, musique_adn/essence):
    # it lives here, first user workflow of the family in the registry.
    PARAMETRES = [
        dict(flags=("--duration",), type=float, default=None,
             help="Duration in seconds (sfx, audio_ambience, music_bg, chanson, musique_adn/essence; default: workflow-specific — 1.5 sfx, 8.0 ambience, 12.0 music_bg, 180.0 chanson, 60.0 musique_adn, 30.0 musique_essence)."),
        dict(flags=("--sfx-engine",), dest="sfx_engine", choices=["ia", "procedural"], default="ia",
             help="Engine of the sfx workflow: ia = Stable Audio 3 Small SFX via audio.cpp (validated 2026-09-09, peak normalization included, free EN prompt) | procedural = numpy synthesis (frozen types sword/coin/explosion…)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        prompt = params.get("prompt") or "sword_slash"
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        duree = float(params.get("duration", 1.5))
        graine = int(params.get("seed", 42))
        moteur = params.get("sfx_engine") or "ia"
        nom_base = params.get("output") or f"{slugifier_texte(prompt)}_sfx"

        os.makedirs(output_dir, exist_ok=True)

        if moteur == "ia":
            self.log(f"AI synthesis (SA3 small SFX, seed {graine}) for '{prompt}' (Duration: {duree:.1f}s, 44.1kHz stereo)...")
            res = generer_sfx_ia(prompt, duree=duree, seed=graine)
            audio_data, sr = res["audio"], res["sr"]
            if res["niveau_mode"] == "nappe":
                self.log(f"Pad detected ({res['lufs_source']:.1f} LUFS): +{res['gain_db']} dB toward −16 LUFS (peaks capped), texture intact.")
            else:
                self.log(f"Generation OK (RTF {res['rtf']:.2f}, source peak {20 * np.log10(max(res['pic_source'], 1e-9)):.1f} dBFS → normalized).")
            if res["rognage_pct"] > 0.01:
                self.log(f"Lead-in/lead-out silences trimmed: −{res['rognage_pct']} % of duration.")
        else:
            self.log(f"Procedural synthesis of the sound effect for '{prompt}' (Duration: {duree:.1f}s, 44.1kHz)...")
            audio_data, sr = synthetiser_sfx(sfx_type=prompt, duree=duree, sr=44100), 44100

        self.log("Exporting the Godot 4 audio formats (.wav, .ogg)...")
        chemin_wav, chemin_ogg = exporter_sfx_godot(nom_base, output_dir, audio_data, sr)

        self.log(f"Sound effect exported successfully to '{output_dir}/':", emoji="🎉")
        self.log(f"  • WAV format: {chemin_wav} (PCM 16-bit)")
        self.log(f"  • OGG format: {chemin_ogg} (AudioStreamPlayer Godot)", emoji="💎")

        return {
            "wav": chemin_wav,
            "ogg": chemin_ogg,
            "duration": duree,
            "engine": moteur,
            "files": [chemin_wav, chemin_ogg]
        }
