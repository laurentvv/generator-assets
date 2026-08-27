#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Audio Ambience : Ambiances Sonores Immersives & Paysages Sonores Procéduraux pour Godot 4.
Produit :
- Fichier audio stéréo WAV (PCM 16-bit)
- Fichier audio OGG Vorbis en boucle continue sans couture (Seamless Loop)
- Ressource Godot 4 AudioBusLayout (.tres) avec Reverb et Filtres atmosphériques
- Scène Godot 4 AudioStreamPlayer (.tscn)
"""

import os
from pathlib import Path
from typing import Any, Dict
import numpy as np

from core.audio_ops import exporter_ambiance_godot, synthetiser_ambiance
from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from workflows.base import BaseWorkflow, WorkflowRegistry


def exporter_scene_ambiance_godot(
    nom_base: str,
    output_dir: str,
    chemin_rel_ogg: str
) -> str:
    """Génère une scène Godot 4 avec un AudioStreamPlayer configuré en boucle sur le bus Ambience."""
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
    """Génération de paysages sonores et ambiances immersives bouclables pour Godot 4."""

    name = "audio_ambience"
    description = "Ambiances sonores immersives & paysages sonores procéduraux en boucle continue pour Godot 4 (.wav / .ogg / .tres)"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        prompt = params.get("prompt") or "dungeon"
        ambience_type = params.get("flow_type") or params.get("vfx_type") or prompt
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        duree = float(params.get("duration", 8.0))
        nom_base = params.get("output") or f"{slugifier_texte(prompt)}_ambience"

        os.makedirs(output_dir, exist_ok=True)

        self.log(f"Synthèse de l'ambiance sonore stéréo pour '{prompt}' (Durée: {duree:.1f}s, boucle sans couture)...")

        # Synthèse stéréo multicouche en boucle
        audio_stereo = synthetiser_ambiance(ambience_type=ambience_type, duree=duree, sr=44100)

        # Export audio et bus Godot 4
        self.log("Exportation des formats audio et configuration du bus Godot 4...")
        chemin_wav, chemin_ogg, chemin_bus = exporter_ambiance_godot(nom_base, output_dir, audio_stereo, sr=44100)

        # Scène Godot 4
        chemin_tscn = exporter_scene_ambiance_godot(nom_base, output_dir, f"res://{nom_base}.ogg")

        self.log(f"Ambiance sonore exportée avec succès dans '{output_dir}/' :", emoji="🎉")
        self.log(f"  • Piste WAV 16-bit : {chemin_wav}")
        self.log(f"  • Piste OGG Loop   : {chemin_ogg}")
        self.log(f"  • AudioBusLayout   : {chemin_bus}")
        self.log(f"  • Scène Godot 4    : {chemin_tscn}", emoji="💎")

        return {
            "wav": chemin_wav,
            "ogg": chemin_ogg,
            "bus_layout": chemin_bus,
            "scene_tscn": chemin_tscn,
            "duration": duree,
            "files": [chemin_wav, chemin_ogg, chemin_bus, chemin_tscn]
        }
