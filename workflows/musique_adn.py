#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Musique ADN : nouvelle musique avec l'ADN (BPM + tonalité) d'une
référence audio — détection automatique, contraintes IMPOSÉES au planner LM
d'ACE-Step 1.5 (xl-turbo par défaut). Méthode validée le 2026-09-06
(llb_xl_adn : BPM rendu 83,3 vs 83,3 source ; seule recette validée par
l'utilisateur — cf. MEMORY_BANK §1.11 pour la carte honnête des essais).

Le style se décrit en texte (EN, sobre) ; le workflow verrouille les nombres
(BPM/tonalité détectés sur la référence, ou forcés via --tonalite).
"""

import os
from typing import Any, Dict

from scripts.generer_depuis_reference import convertir_en_wav, detecter_tonalite
from core.config import ACESTEP15_VARIANTES, slugifier_texte
from core.music_ai import (
    charger_audio,
    convertir_mp3,
    estimer_bpm,
    generer_musique_acestep,
)
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class MusiqueAdnWorkflow(BaseWorkflow):
    """Nouvelle musique avec le BPM + la tonalité détectés d'une référence (ACE-Step 1.5, Vulkan)."""

    name = "musique_adn"
    description = ("Générer une NOUVELLE musique avec l'ADN d'une référence (BPM + tonalité "
                   "auto, imposés au planner ACE-Step 1.5 xl-turbo) — style décrit en texte")

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        reference = params.get("input")
        if not reference or not os.path.exists(reference):
            raise ValueError("Référence audio introuvable : la passer via -i <audio> (MP3/WAV).")
        style = (params.get("prompt") or "").strip()
        if not style:
            raise ValueError("Fournir la description du style EN (paramètre positionnel).")

        duree = float(params.get("duration") or 0) or 60.0
        if duree < 10.0:
            duree = 60.0
        variante = params.get("variante") or "xl-turbo"
        if variante not in ACESTEP15_VARIANTES:
            raise ValueError(f"Variante inconnue : {variante} (choix : {', '.join(ACESTEP15_VARIANTES)})")
        langue = params.get("langue") or "fr"
        negatif = params.get("negatif") or None
        graine = params.get("seed")
        graine = int(graine) if graine is not None and int(graine) >= 0 else -1

        # Paroles optionnelles : --lyrics pointant un fichier .txt
        paroles = "[Instrumental]"
        brut_lyrics = params.get("lyrics") or ""
        if brut_lyrics and os.path.isfile(brut_lyrics) and brut_lyrics.lower().endswith(".txt"):
            with open(brut_lyrics, encoding="utf-8") as f:
                paroles = f.read().strip() or paroles
            self.log(f"Paroles chargées depuis {brut_lyrics}", "📄")

        self.log(f"Analyse de la référence : {reference}", "🔍")
        chemin_wav = convertir_en_wav(reference)
        audio, sr = charger_audio(chemin_wav)
        bpm = estimer_bpm(audio, sr)
        if bpm is None:
            raise ValueError("Aucun tempo détecté dans la référence (audio non pulsatif ?).")
        bpm = int(round(bpm))
        tonalite = params.get("tonalite") or detecter_tonalite(audio, sr)
        self.log(f"ADN détecté : {bpm} BPM • {tonalite} • {len(audio) / sr:.0f} s analysées", "🧬")

        # Recette validée : description SOBRE + nombres imposés (le suffixe
        # « instrumental » seulement sans paroles — l'ajouter avec des paroles
        # contredit le planner).
        if paroles == "[Instrumental]":
            description = f"{style}, {bpm} BPM, {tonalite}, completely instrumental, no vocals"
        else:
            description = f"{style}, {bpm} BPM, {tonalite}"

        nom = slugifier_texte(params.get("output") or "musique_adn")[:60]
        sortie = os.path.join("output", "music_chanson", f"{nom}.wav")
        os.makedirs(os.path.dirname(sortie), exist_ok=True)

        self.log(f"Génération {duree:.0f} s • {variante} • BPM {bpm} + {tonalite} imposés au planner", "🎵")
        chemin, backend = generer_musique_acestep(
            description=description,
            chemin_sortie=sortie,
            duree=duree,
            etapes=8,
            backend="vulkan",
            lyrics=paroles,
            variante=variante,
            langue=langue,
            graine=graine,
            negatif=negatif,
            log=lambda m: self.log(m, "🎵"),
        )
        mp3 = convertir_mp3(chemin, chemin.replace(".wav", ".mp3"), 224)
        self.log(f"Musique prête : {mp3} (backend {backend}) — ADN : {bpm} BPM / {tonalite}", "🎧")
        return {"wav": chemin, "mp3": mp3, "bpm": bpm, "tonalite": tonalite, "backend": backend}
