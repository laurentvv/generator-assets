#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow SFX : Génération de Bruitages et Effets Sonores pour Assets de Jeu (Godot 4).
Produit :
- Fichier audio WAV (PCM 16-bit)
- Fichier audio OGG Vorbis (Stream optimisé Godot)
"""

import os
from pathlib import Path
from typing import Any, Dict
import numpy as np

from core.audio_ops import exporter_sfx_godot, synthetiser_sfx
from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class SFXWorkflow(BaseWorkflow):
    """Génération d'effets sonores et bruitages (SFX) pour Godot 4."""

    name = "sfx"
    description = "Effets sonores & bruitages de jeux vidéo (.wav / .ogg) pour Godot AudioStreamPlayer"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        prompt = params.get("prompt") or "sword_slash"
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        duree = float(params.get("duration", 1.5))
        nom_base = params.get("output") or f"{slugifier_texte(prompt)}_sfx"

        os.makedirs(output_dir, exist_ok=True)

        self.log(f"Synthèse de l'effet sonore pour '{prompt}' (Durée: {duree:.1f}s, 44.1kHz)...")

        audio_data = synthetiser_sfx(sfx_type=prompt, duree=duree, sr=44100)

        self.log("Export des formats audio Godot 4 (.wav, .ogg)...")
        chemin_wav, chemin_ogg = exporter_sfx_godot(nom_base, output_dir, audio_data, sr=44100)

        self.log(f"Effet sonore exporté avec succès dans '{output_dir}/' :", emoji="🎉")
        self.log(f"  • Format WAV : {chemin_wav} (PCM 16-bit)")
        self.log(f"  • Format OGG : {chemin_ogg} (AudioStreamPlayer Godot)", emoji="💎")

        return {
            "wav": chemin_wav,
            "ogg": chemin_ogg,
            "duration": duree,
            "files": [chemin_wav, chemin_ogg]
        }
