#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Song Workflow: full song WITH LYRICS via ACE-Step 1.5 (audio.cpp
Vulkan). Capability validated on 2026-09-06 ("La Symphonie du Silence", "Le
Neuvième Fils" — Vent-Gris universe, FR lyrics, xl-turbo).

The lyrics come from the positional parameter (the text itself or the path of a
.txt file); the structure tags ([Intro], [Verse], [Chorus],
[Bridge], [Outro]) are honored by the planner.
⚠️ Clean out any quotation/annotation in the lyrics: otherwise it gets sung.
"""

import os
from typing import Any, Dict

from core.config import ACESTEP15_VARIANTES, slugifier_texte
from core.music_ai import convertir_mp3, generer_musique_acestep
from workflows.base import BaseWorkflow, WorkflowRegistry

# Default style: validated musical direction for the Vent-Gris universe
STYLE_DEFAUT = (
    "dark neoclassical folk and gothic orchestral in the style of Wardruna, "
    "haunting low solo cello, sparse metallic prepared piano, slow muffled "
    "heartbeat percussion, dark wooden flute, whispered choir in the "
    "background, deep male vocals, intimate and visceral, French lyrics, "
    "glacial desolate atmosphere, slow tempo, minor key"
)


@WorkflowRegistry.register
class ChansonWorkflow(BaseWorkflow):
    """Full song (lyrics + sung music) via ACE-Step 1.5 xl-turbo (Vulkan)."""

    name = "chanson"
    description = ("Full song WITH LYRICS (ACE-Step 1.5 xl-turbo, Vulkan) — "
                   "structure tags, FR language by default, ~15 min for 4 min of song")

    emoji = "🎵"

    # CLI declarations (audit §2.2, migration from cli/parser.py's flat table:
    # help/defaults kept as-is, unchanged surface). --variante (ACE-Step choice)
    # lives in music_bg; --langue is shared with musique_adn.
    PARAMETRES = [
        dict(flags=("--style-musique",), default=None,
             help="EN musical description for chanson (default: Vent-Gris dark folk)."),
        dict(flags=("--langue",), default=None,
             help="Lyrics language for chanson/musique_adn (default: fr)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        brut = (params.get("prompt") or "").strip()
        if not brut:
            raise ValueError("Provide the lyrics (positional parameter) or a .txt file.")
        if os.path.isfile(brut) and brut.lower().endswith(".txt"):
            with open(brut, encoding="utf-8") as f:
                paroles = f.read().strip()
            nom_defaut = os.path.splitext(os.path.basename(brut))[0]
            self.log(f"Lyrics loaded from {brut}", "📄")
        else:
            paroles = brut
            nom_defaut = "chanson"
        if not paroles:
            raise ValueError("The lyrics are empty.")

        style = params.get("style_musique") or STYLE_DEFAUT
        # The --duration CLI flag has a low default: any value < 30 s = not provided
        duree = float(params.get("duration") or 0) or 180.0
        if duree < 30.0:
            duree = 180.0
        variante = params.get("variante") or "xl-turbo"
        if variante not in ACESTEP15_VARIANTES:
            raise ValueError(f"Unknown variant: {variante} (choices: {', '.join(ACESTEP15_VARIANTES)})")
        langue = params.get("langue") or "fr"
        graine = params.get("seed")
        graine = int(graine) if graine is not None and int(graine) >= 0 else -1

        nb_lignes = len([ligne for ligne in paroles.splitlines() if ligne.strip() and not ligne.strip().startswith("[")])
        nom = slugifier_texte(params.get("output") or nom_defaut)[:60]
        sortie = os.path.join("output", "music_chanson", f"{nom}.wav")
        os.makedirs(os.path.dirname(sortie), exist_ok=True)

        self.log(f"{nb_lignes} sung lines • {duree:.0f} s • variant {variante} • language {langue}", "🎵")
        chemin, backend = generer_musique_acestep(
            description=style,
            chemin_sortie=sortie,
            duree=duree,
            etapes=8,
            backend="vulkan",
            lyrics=paroles,
            variante=variante,
            langue=langue,
            graine=graine,
            log=lambda m: self.log(m, "🎵"),
        )
        mp3 = convertir_mp3(chemin, chemin.replace(".wav", ".mp3"), 224)
        self.log(f"Song ready: {mp3} (backend {backend})", "🎧")
        return {"wav": chemin, "mp3": mp3, "backend": backend, "duree": duree}
