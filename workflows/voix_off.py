#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Voix Off : lecture expressive d'un texte par TTS local (audio.cpp Vulkan),
avec clonage d'une voix de référence française si fournie.

Moteurs : qwen3-tts 1.7B (défaut si référence, Apache-2.0, expression --instruct),
VoxCPM2 (défaut sans référence, Apache-2.0, clonage sans transcript),
Fish S2-Pro (balises inline [whisper]/[excited], licence recherche).

Pipeline : contrôle/normalisation du niveau de la référence (écart ≤ 2026-09-06 :
enregistrement à -39 LUFS → normalisation -18 LUFS), transcription ASR auto si le
moteur l'exige, génération, normalisation finale -16 LUFS (standard dialogue
YouTube) + MP3 d'écoute.
"""

import os
from typing import Any, Dict

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.voix_off import MOTEURS, finaliser_voix, generer_voix_off
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class VoixOffWorkflow(BaseWorkflow):
    """Voix off clonée/expressive (qwen3-tts / VoxCPM2 / Fish S2-Pro GGUF, Vulkan) normalisée pour YouTube."""

    name = "voix_off"
    description = ("Lecture expressive d'un texte par TTS local (audio.cpp Vulkan) avec "
                   "clonage vocal optionnel — qwen3-tts/VoxCPM2 (Apache-2.0) ou Fish S2-Pro, "
                   "sortie normalisée -16 LUFS + MP3")

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Le texte : paramètre prompt (texte lui-même) OU chemin d'un fichier .txt
        brut = (params.get("prompt") or "").strip()
        if not brut:
            raise ValueError("Fournir le texte à lire (paramètre positionnel) ou un fichier .txt.")
        if os.path.isfile(brut) and brut.lower().endswith(".txt"):
            with open(brut, encoding="utf-8") as f:
                texte = f.read().strip()
            self.log(f"Texte chargé depuis {brut} ({len(texte)} caractères)", "📄")
        else:
            texte = brut
        if not texte:
            raise ValueError("Le texte à lire est vide.")

        # Moteur : --moteur est partagé avec music_bg (défaut 'acestep') → toute
        # valeur hors moteurs voix = choix automatique.
        moteur = params.get("moteur")
        if moteur not in MOTEURS:
            moteur = None
        voix_ref = params.get("voix_ref") or None
        if not moteur:
            moteur = "qwen3" if voix_ref else "voxcpm2"
            self.log(f"Moteur automatique : {moteur}", "🎚️")

        instruct = params.get("instruct") or None
        lufs = float(params.get("lufs_voix") or -16.0)
        backend = params.get("music_backend") or "vulkan"
        seed = params.get("seed")

        nom = slugifier_texte(params.get("output") or "voix_off")[:60]
        # Par convention (comme music_bg), les pistes de production vont dans output/
        output_dir = params.get("output_dir") or ""
        if not output_dir or output_dir == DEFAULT_OUTPUT_DIR:
            output_dir = "output/voix_off"
        dossier = os.path.join(output_dir, nom)
        os.makedirs(dossier, exist_ok=True)

        self.log(f"Moteur {moteur} ({MOTEURS[moteur]['licence']}) — "
                 f"clonage {'activé' if voix_ref else 'désactivé'}", "🎙️")
        brut_wav = os.path.join(dossier, "voix_off_brut.wav")
        res = generer_voix_off(
            texte=texte,
            moteur=moteur,
            wav_ref=voix_ref,
            instruct=instruct,
            sortie=brut_wav,
            backend=backend,
            seed=int(seed) if seed is not None and int(seed) >= 0 else None,
            dossier_travail=dossier,
        )
        finals = finaliser_voix(brut_wav, lufs_cible=lufs)
        self.log(f"Voix prête : {finals['wav']} ({finals['lufs']} LUFS) — écoute : {finals['mp3']}", "✅")
        return {**res, **finals}
