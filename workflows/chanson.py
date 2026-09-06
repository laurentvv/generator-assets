#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Chanson : chanson complète AVEC PAROLES via ACE-Step 1.5 (audio.cpp
Vulkan). Capacité validée le 2026-09-06 (« La Symphonie du Silence », « Le
Neuvième Fils » — univers Vent-Gris, paroles FR, xl-turbo).

Les paroles viennent du paramètre positionnel (texte lui-même ou chemin d'un
fichier .txt) ; les balises de structure ([Intro], [Verse], [Chorus],
[Bridge], [Outro]) sont respectées par le planner.
⚠️ Nettoyer toute citation/annotation dans les paroles : sinon elle est chantée.
"""

import os
from typing import Any, Dict

from core.config import ACESTEP15_VARIANTES, slugifier_texte
from core.music_ai import convertir_mp3, generer_musique_acestep
from workflows.base import BaseWorkflow, WorkflowRegistry

# Style par défaut : direction musicale validée pour l'univers Vent-Gris
STYLE_DEFAUT = (
    "dark neoclassical folk and gothic orchestral in the style of Wardruna, "
    "haunting low solo cello, sparse metallic prepared piano, slow muffled "
    "heartbeat percussion, dark wooden flute, whispered choir in the "
    "background, deep male vocals, intimate and visceral, French lyrics, "
    "glacial desolate atmosphere, slow tempo, minor key"
)


@WorkflowRegistry.register
class ChansonWorkflow(BaseWorkflow):
    """Chanson complète (paroles + musique chantée) via ACE-Step 1.5 xl-turbo (Vulkan)."""

    name = "chanson"
    description = ("Chanson complète AVEC PAROLES (ACE-Step 1.5 xl-turbo, Vulkan) — "
                   "balises de structure, langue FR par défaut, ~15 min pour 4 min de chanson")

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        brut = (params.get("prompt") or "").strip()
        if not brut:
            raise ValueError("Fournir les paroles (paramètre positionnel) ou un fichier .txt.")
        if os.path.isfile(brut) and brut.lower().endswith(".txt"):
            with open(brut, encoding="utf-8") as f:
                paroles = f.read().strip()
            nom_defaut = os.path.splitext(os.path.basename(brut))[0]
            self.log(f"Paroles chargées depuis {brut}", "📄")
        else:
            paroles = brut
            nom_defaut = "chanson"
        if not paroles:
            raise ValueError("Les paroles sont vides.")

        style = params.get("style_musique") or STYLE_DEFAUT
        # Le flag CLI --duration a un défaut bas : toute valeur < 30 s = non renseignée
        duree = float(params.get("duration") or 0) or 180.0
        if duree < 30.0:
            duree = 180.0
        variante = params.get("variante") or "xl-turbo"
        if variante not in ACESTEP15_VARIANTES:
            raise ValueError(f"Variante inconnue : {variante} (choix : {', '.join(ACESTEP15_VARIANTES)})")
        langue = params.get("langue") or "fr"
        graine = params.get("seed")
        graine = int(graine) if graine is not None and int(graine) >= 0 else -1

        nb_lignes = len([l for l in paroles.splitlines() if l.strip() and not l.strip().startswith("[")])
        nom = slugifier_texte(params.get("output") or nom_defaut)[:60]
        sortie = os.path.join("output", "music_chanson", f"{nom}.wav")
        os.makedirs(os.path.dirname(sortie), exist_ok=True)

        self.log(f"{nb_lignes} lignes chantées • {duree:.0f} s • variante {variante} • langue {langue}", "🎵")
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
        self.log(f"Chanson prête : {mp3} (backend {backend})", "🎧")
        return {"wav": chemin, "mp3": mp3, "backend": backend, "duree": duree}
