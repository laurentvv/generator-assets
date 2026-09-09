#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow SFX : Génération de Bruitages et Effets Sonores pour Assets de Jeu (Godot 4).
Produit :
- Fichier audio WAV (PCM 16-bit)
- Fichier audio OGG Vorbis (Stream optimisé Godot)

Moteurs (param `sfx_engine`) :
- `ia` (défaut) : Stable Audio 3 Small SFX via audio.cpp — validé utilisateur le
  2026-09-09 (4/5 « ok », normalisation de crête intégrée suite au rejet « faible
  volume » du sample pluie). N'importe quel prompt EN descriptif est possible.
- `procedural` : synthèse numpy historique (types figés : sword, coin, explosion…).
"""

import os
from pathlib import Path
from typing import Any, Dict
import numpy as np

from core.audio_ops import exporter_sfx_godot, synthetiser_sfx
from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.sfx_ia import generer_sfx_ia
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class SFXWorkflow(BaseWorkflow):
    """Génération d'effets sonores et bruitages (SFX) pour Godot 4."""

    name = "sfx"
    description = "Effets sonores & bruitages de jeux vidéo (.wav / .ogg) — moteur IA (SA3 small SFX) ou synthèse procédurale"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        prompt = params.get("prompt") or "sword_slash"
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        duree = float(params.get("duration", 1.5))
        graine = int(params.get("seed", 42))
        moteur = params.get("sfx_engine") or "ia"
        nom_base = params.get("output") or f"{slugifier_texte(prompt)}_sfx"

        os.makedirs(output_dir, exist_ok=True)

        if moteur == "ia":
            self.log(f"Synthèse IA (SA3 small SFX, graine {graine}) pour '{prompt}' (Durée: {duree:.1f}s, 44.1kHz stéréo)...")
            res = generer_sfx_ia(prompt, duree=duree, seed=graine)
            audio_data, sr = res["audio"], res["sr"]
            if res["niveau_mode"] == "nappe":
                self.log(f"Nappe détectée ({res['lufs_source']:.1f} LUFS) : +{res['gain_db']} dB vers −16 LUFS (crêtes plafonnées), texture intacte.")
            else:
                self.log(f"Génération OK (RTF {res['rtf']:.2f}, crête source {20 * np.log10(max(res['pic_source'], 1e-9)):.1f} dBFS → normalisée).")
            if res["rognage_pct"] > 0.01:
                self.log(f"Silences d'entrée/sortie rognés : −{res['rognage_pct']} % de durée.")
        else:
            self.log(f"Synthèse procédurale de l'effet sonore pour '{prompt}' (Durée: {duree:.1f}s, 44.1kHz)...")
            audio_data, sr = synthetiser_sfx(sfx_type=prompt, duree=duree, sr=44100), 44100

        self.log("Export des formats audio Godot 4 (.wav, .ogg)...")
        chemin_wav, chemin_ogg = exporter_sfx_godot(nom_base, output_dir, audio_data, sr)

        self.log(f"Effet sonore exporté avec succès dans '{output_dir}/' :", emoji="🎉")
        self.log(f"  • Format WAV : {chemin_wav} (PCM 16-bit)")
        self.log(f"  • Format OGG : {chemin_ogg} (AudioStreamPlayer Godot)", emoji="💎")

        return {
            "wav": chemin_wav,
            "ogg": chemin_ogg,
            "duration": duree,
            "engine": moteur,
            "files": [chemin_wav, chemin_ogg]
        }
