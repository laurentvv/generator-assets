#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Super-Résolution Audio : restauration → 48 kHz via UniverSR
(audio.cpp, backend CPU — Vulkan cassé sur cette famille, cf. docstring
de core/audio_upscale.py).

Recette VALIDÉE utilisateur le 2026-09-18 : voix 16 kHz « copie sans bug,
parfait même », musique 24 kHz « très bien » (MEMORY_BANK §1.27).
Sortie WAV 48 kHz mono + MP3 d'écoute.
"""

import os
from typing import Any, Dict

from core.audio_upscale import RECIPE, restaurer_universr
from core.config import slugifier_texte
from core.music_ai import convertir_mp3
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class AudioUpscaleWorkflow(BaseWorkflow):
    """Super-résolution audio → 48 kHz (UniverSR CPU, recette validée)."""

    name = "audio_upscale"
    description = ("Super-résolution audio → 48 kHz via UniverSR (CPU) : voix 16 kHz "
                   "ou musique 24 kHz restaurées (recette validée 2026-09-18) — "
                   "WAV 48 kHz mono + MP3, RTF ~13")

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        source = params.get("input")
        if not source or not os.path.exists(source):
            raise ValueError(
                f"Fichier audio source introuvable : {source} — "
                f"passer un WAV/MP3 à bande réduite (8/12/16/24 kHz) via -i."
            )

        variante = params.get("upsr_variante") or RECIPE["variante"]
        bande = int(params.get("upsr_rate") or 0)
        # --seed global du CLI vaut -1 (« aléatoire ») par défaut : universr exige
        # un entier non signé → graine négative = défaut de la recette (42).
        seed = int(params.get("seed") or 0)
        if seed < 0:
            seed = RECIPE["seed"]

        nom = slugifier_texte(
            params.get("output")
            or os.path.splitext(os.path.basename(source))[0]
        )[:60]
        output_dir = params.get("output_dir") or ""
        if not output_dir or output_dir == "godot_assets":
            output_dir = "output/audio_upscale"
        dossier = os.path.join(output_dir, nom)
        os.makedirs(dossier, exist_ok=True)

        wav = os.path.join(dossier, f"{nom}_48k.wav")
        mp3 = os.path.join(dossier, f"{nom}_48k.mp3")

        res = restaurer_universr(source, wav, variante=variante,
                                 bande=bande, seed=seed)
        convertir_mp3(wav, mp3)

        self.log(
            f"Restauration {res['frequence_source']} → 48 kHz "
            f"(variante {res['variante']}, bande déclarée {res['bande']} Hz) :",
            emoji="🎉",
        )
        self.log(f"  • WAV : {wav} (48 kHz mono)", "💾")
        self.log(f"  • MP3 d'écoute : {mp3}", "💎")

        return {"wav": wav, "mp3": mp3, "files": [wav, mp3]}
