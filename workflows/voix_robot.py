#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Voix de Robot : synthèse anglaise Kokoro-82M (audio.cpp Vulkan) + effet
« petit robot » FFmpeg (pitch +30 %, ring modulation 120 Hz, débit posé, gain -4 dB).

Recette VALIDÉE utilisateur le 2026-09-17 (essai 17 : « c'est bien ») — détails et
écueil moteur (espeak) dans MEMORY_BANK §1.21 et docstring de core/voix_robot.py.
Texte en anglais (prompts modèles en anglais, conventions dépôt).
"""

import os
from typing import Any, Dict

from core.config import slugifier_texte
from core.voix_robot import RECIPE, generer_voix_robot
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class VoixRobotWorkflow(BaseWorkflow):
    """Voix de robot en anglais (Kokoro + ring modulation, recette validée)."""

    name = "voix_robot"
    description = ("Voix de robot en anglais — TTS Kokoro-82M (Vulkan) + effet FFmpeg "
                   "pitch/ring modulation (recette validée 2026-09-17) — .wav + .mp3")

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        brut = (params.get("prompt") or "").strip()
        if not brut:
            raise ValueError("Fournir le texte anglais à lire (paramètre positionnel).")
        if os.path.isfile(brut) and brut.lower().endswith(".txt"):
            with open(brut, encoding="utf-8") as f:
                texte = f.read().strip()
            self.log(f"Texte chargé depuis {brut} ({len(texte)} caractères)", "📄")
        else:
            texte = brut
        if not texte:
            raise ValueError("Le texte à lire est vide.")

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

        self.log(f"Recette validée : voix {voice_id}, pitch +{int((pitch - 1) * 100)} %, "
                 f"ring mod {ringmod_hz:g} Hz, atempo {tempo}, gain {gain_db:+g} dB", "🤖")
        res = generer_voix_robot(
            texte=texte, dossier=dossier, nom=nom, voice_id=voice_id,
            pitch=pitch, ringmod_hz=ringmod_hz, tempo=tempo, gain_db=gain_db,
        )

        self.log("Voix de robot générée :", emoji="🎉")
        self.log(f"  • WAV : {res['wav']} (PCM 16-bit, 24 kHz)")
        self.log(f"  • MP3 d'écoute : {res['mp3']}", emoji="💎")

        return {"wav": res["wav"], "mp3": res["mp3"], "brut": res["brut"],
                "files": [res["wav"], res["mp3"]]}
