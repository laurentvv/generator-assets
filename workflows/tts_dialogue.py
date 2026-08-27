#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow TTS Dialogue : Synthèse Vocale Émotionnelle & Lip-Sync pour Dialogues RPG dans Godot 4.
Produit :
- Fichiers audio .wav et .ogg par réplique et émotion (Neutre, Joie, Colère, Tristesse, Blessé)
- Piste de visèmes phonétiques pour Lip-Sync en temps réel
- Manifeste JSON complet prêt pour Dialogic ou le DialogueManager de Godot 4
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List
import soundfile as sf

from core.audio_ops import exporter_sfx_godot, synthetiser_voix_emotionnelle
from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from workflows.base import BaseWorkflow, WorkflowRegistry

# Exemples de répliques par émotion si non fournies
DEFAULT_LINES = {
    "neutral": "Je veille sur ce sanctuaire depuis des siècles. Que cherchez-vous ?",
    "happy": "C'est un véritable honneur de voyager à vos côtés, noble allié !",
    "angry": "Reculez immédiatement avant que ma lame ne scelle votre destin !",
    "sad": "Tout ce que nous avions bâti a sombré dans les ténèbres...",
    "hurt": "Argh... cette blessure est profonde, mais je tiendrai bon !",
    "surprised": "Par les anciens dieux ! Comment avez-vous trouvé cette relique ?"
}


@WorkflowRegistry.register
class TTSDialogueWorkflow(BaseWorkflow):
    """Génération de voix de PNJ émotionnelles et synchronisation Lip-Sync pour Godot 4."""

    name = "tts_dialogue"
    description = "Synthèse vocale émotionnelle (TTS / Kokoro) synchronisée avec les portraits RPG et lip-sync Godot"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        personnage = params.get("prompt") or "guerriere_sanctuaire"
        emotions_str = params.get("emotions", "neutral,happy,angry,sad,hurt")
        emotions_list = [e.strip().lower() for e in emotions_str.split(",") if e.strip()]
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        pitch = float(params.get("pitch", 160.0))

        nom_base = params.get("output") or slugifier_texte(personnage)
        dossier_voix = os.path.join(output_dir, f"{nom_base}_voice")
        os.makedirs(dossier_voix, exist_ok=True)

        self.log(f"Synthèse vocale émotionnelle pour '{nom_base}' ({len(emotions_list)} répliques)...")

        manifeste_dialogues = {
            "character_id": nom_base,
            "sample_rate": 44100,
            "dialogues": {}
        }

        fichiers_produits = []

        for emo in emotions_list:
            texte_replique = DEFAULT_LINES.get(emo, f"Parole de {personnage} en état {emo}.")
            self.log(f"  • Synthèse de la voix [{emo}] : \"{texte_replique[:40]}...\"")

            audio_data, visemes = synthetiser_voix_emotionnelle(
                texte=texte_replique,
                emotion=emo,
                pitch_base=pitch,
                sr=44100
            )

            nom_audio = f"{nom_base}_{emo}"
            chemin_wav, chemin_ogg = exporter_sfx_godot(nom_audio, dossier_voix, audio_data, sr=44100)

            duree_sec = len(audio_data) / 44100.0

            manifeste_dialogues["dialogues"][emo] = {
                "text": texte_replique,
                "audio_wav": f"res://{dossier_voix}/{nom_audio}.wav".replace("\\", "/"),
                "audio_ogg": f"res://{dossier_voix}/{nom_audio}.ogg".replace("\\", "/"),
                "duration": round(duree_sec, 2),
                "portrait_path": f"res://{output_dir}/{nom_base}_dialogues/{nom_base}_{emo}.png".replace("\\", "/"),
                "visemes": visemes
            }

            fichiers_produits.extend([chemin_wav, chemin_ogg])

        # Exportation du manifeste complet JSON
        chemin_json = os.path.join(dossier_voix, f"{nom_base}_dialogue_manifest.json")
        with open(chemin_json, "w", encoding="utf-8") as f:
            json.dump(manifeste_dialogues, f, indent=2, ensure_ascii=False)

        fichiers_produits.append(chemin_json)

        self.log(f"Packs de dialogues & voix prêts dans '{dossier_voix}/' :", emoji="🎉")
        self.log(f"  • Manifeste Lip-Sync : {chemin_json}")
        self.log(f"  • Répliques audio   : {len(emotions_list)} fichiers .wav / .ogg", emoji="💎")

        return {
            "manifest_json": chemin_json,
            "emotions": emotions_list,
            "voice_dir": dossier_voix,
            "files": fichiers_produits
        }
