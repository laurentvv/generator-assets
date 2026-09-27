#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TTS Dialogue Workflow: Emotional Voice Synthesis & Lip-Sync for RPG Dialogues in Godot 4.
Produces:
- .wav and .ogg audio files per line and emotion (Neutral, Joy, Anger, Sadness, Hurt)
- Phonetic viseme track for real-time Lip-Sync
- Complete JSON manifest ready for Dialogic or the Godot 4 DialogueManager
"""

import json
import os
from typing import Any, Dict

from core.audio_ops import exporter_sfx_godot, synthetiser_voix_emotionnelle
from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from workflows.base import BaseWorkflow, WorkflowRegistry

# Sample lines per emotion when not provided (French TTS content on purpose)
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
    """Generation of emotional NPC voices and Lip-Sync for Godot 4."""

    name = "tts_dialogue"
    description = "Emotional voice synthesis (TTS / Kokoro) synchronized with the RPG portraits and Godot lip-sync"

    emoji = "🎙️"

    # CLI declaration (audit §2.2, migration from cli/parser.py's flat table:
    # help/defaults kept as-is, unchanged surface). --emotions (shared with
    # rpg_portrait, 2D family) stays in cli/parser.py's flat table.
    PARAMETRES = [
        dict(flags=("--pitch",), type=float, default=None,
             help="Fundamental voice pitch for tts_dialogue (workflow default: 160 Hz)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        personnage = params.get("prompt") or "guerriere_sanctuaire"
        emotions_str = params.get("emotions", "neutral,happy,angry,sad,hurt")
        emotions_list = [e.strip().lower() for e in emotions_str.split(",") if e.strip()]
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        pitch = float(params.get("pitch", 160.0))

        nom_base = params.get("output") or slugifier_texte(personnage)
        dossier_voix = os.path.join(output_dir, f"{nom_base}_voice")
        os.makedirs(dossier_voix, exist_ok=True)

        self.log(f"Emotional voice synthesis for '{nom_base}' ({len(emotions_list)} lines)...")

        manifeste_dialogues = {
            "character_id": nom_base,
            "sample_rate": 44100,
            "dialogues": {}
        }

        fichiers_produits = []

        for emo in emotions_list:
            texte_replique = DEFAULT_LINES.get(emo, f"Parole de {personnage} en état {emo}.")
            self.log(f"  • Voice synthesis [{emo}]: \"{texte_replique[:40]}...\"")

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

        # Export of the complete JSON manifest
        chemin_json = os.path.join(dossier_voix, f"{nom_base}_dialogue_manifest.json")
        with open(chemin_json, "w", encoding="utf-8") as f:
            json.dump(manifeste_dialogues, f, indent=2, ensure_ascii=False)

        fichiers_produits.append(chemin_json)

        self.log(f"Dialogue & voice packs ready in '{dossier_voix}/':", emoji="🎉")
        self.log(f"  • Lip-Sync manifest : {chemin_json}")
        self.log(f"  • Audio lines       : {len(emotions_list)} .wav / .ogg files", emoji="💎")

        return {
            "manifest_json": chemin_json,
            "emotions": emotions_list,
            "voice_dir": dossier_voix,
            "files": fichiers_produits
        }
