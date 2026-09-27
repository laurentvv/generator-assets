#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Musique ADN Workflow: new music with the DNA (BPM + key) of an
audio reference — automatic detection, constraints ENFORCED on the LM planner
of ACE-Step 1.5 (xl-turbo by default). Method validated on 2026-09-06
(llb_xl_adn: rendered BPM 83.3 vs 83.3 source; the only recipe validated by the
user — see MEMORY_BANK §1.11 for the honest map of the attempts).

The style is described in text (EN, sober); the workflow locks the numbers
(BPM/key detected on the reference, or forced via --tonalite).
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
    """New music with the BPM + key detected from a reference (ACE-Step 1.5, Vulkan)."""

    name = "musique_adn"
    description = ("Generate NEW music with the DNA of a reference (BPM + key "
                   "auto, enforced on the ACE-Step 1.5 xl-turbo planner) — style described in text")

    emoji = "🧬"

    # CLI declaration (audit §2.2, migration from cli/parser.py's flat table:
    # help/defaults kept as-is, unchanged surface). --variante lives in
    # music_bg; --langue in chanson; --tonalite and --lyrics (shared) in
    # music_bg.
    PARAMETRES = [
        dict(flags=("--negatif",), default=None,
             help="EN negative prompt for musique_adn — e.g.: 'pop, soft, mellow, gentle'."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        reference = params.get("input")
        if not reference or not os.path.exists(reference):
            raise ValueError("Audio reference not found: pass it via -i <audio> (MP3/WAV).")
        style = (params.get("prompt") or "").strip()
        if not style:
            raise ValueError("Provide the EN style description (positional parameter).")

        duree = float(params.get("duration") or 0) or 60.0
        if duree < 10.0:
            duree = 60.0
        variante = params.get("variante") or "xl-turbo"
        if variante not in ACESTEP15_VARIANTES:
            raise ValueError(f"Unknown variant: {variante} (choices: {', '.join(ACESTEP15_VARIANTES)})")
        langue = params.get("langue") or "fr"
        negatif = params.get("negatif") or None
        graine = params.get("seed")
        graine = int(graine) if graine is not None and int(graine) >= 0 else -1

        # Optional lyrics: --lyrics pointing to a .txt file
        paroles = "[Instrumental]"
        brut_lyrics = params.get("lyrics") or ""
        if brut_lyrics and os.path.isfile(brut_lyrics) and brut_lyrics.lower().endswith(".txt"):
            with open(brut_lyrics, encoding="utf-8") as f:
                paroles = f.read().strip() or paroles
            self.log(f"Lyrics loaded from {brut_lyrics}", "📄")

        self.log(f"Reference analysis: {reference}", "🔍")
        chemin_wav = convertir_en_wav(reference)
        audio, sr = charger_audio(chemin_wav)
        bpm = estimer_bpm(audio, sr)
        if bpm is None:
            raise ValueError("No tempo detected in the reference (non-pulsative audio?).")
        bpm = int(round(bpm))
        tonalite = params.get("tonalite") or detecter_tonalite(audio, sr)
        self.log(f"DNA detected: {bpm} BPM • {tonalite} • {len(audio) / sr:.0f} s analyzed", "🧬")

        # Validated recipe: SOBER description + enforced numbers (the
        # "instrumental" suffix only without lyrics — adding it with lyrics
        # contradicts the planner).
        if paroles == "[Instrumental]":
            description = f"{style}, {bpm} BPM, {tonalite}, completely instrumental, no vocals"
        else:
            description = f"{style}, {bpm} BPM, {tonalite}"

        nom = slugifier_texte(params.get("output") or "musique_adn")[:60]
        sortie = os.path.join("output", "music_chanson", f"{nom}.wav")
        os.makedirs(os.path.dirname(sortie), exist_ok=True)

        self.log(f"Generating {duree:.0f} s • {variante} • BPM {bpm} + {tonalite} enforced on the planner", "🎵")
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
        self.log(f"Music ready: {mp3} (backend {backend}) — DNA: {bpm} BPM / {tonalite}", "🎧")
        return {"wav": chemin, "mp3": mp3, "bpm": bpm, "tonalite": tonalite, "backend": backend}
