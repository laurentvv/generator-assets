#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Musique Essence : nouvelle musique à l'essence d'une référence audio
(Stable Audio 3 Medium, mode init_audio) puis retrait du chant (HTDemucs).

Validé par l'utilisateur le 2026-09-09 (« c bien ») sur la référence Love Like
Blood : échelle 0,40-0,45, graine fixe 42 → batterie/guitare de la référence
restituées, sans le biais pop du prompt texte seul. Le chant de la référence
« bave » dans la génération → HTDemucs le retire et livre un instrumental
exploitable (pas de clonage vocal = pas de risque contenu dérivatif).

Étapes :
1. Génération SA3 Medium init_audio (RTF ~0,8 sur RX 6950 XT)
2. (défaut) Retrait de voix HTDemucs → instrumental + stems
   (--keep-vocals pour conserver la version brute avec la bave de chant)
"""

import os
from typing import Any, Dict

from core.config import slugifier_texte
from core.music_essence import DEFAULT_SCALE, generer_essence_sa3
from core.separation import retirer_voix
from workflows.base import BaseWorkflow, WorkflowRegistry

SEED_VALIDEE = 42  # loterie de graine démontrée à 0,5 — la recette validée fixe la graine


@WorkflowRegistry.register
class MusiqueEssenceWorkflow(BaseWorkflow):
    """Musique à l'essence d'une référence (SA3 Medium init_audio + retrait voix HTDemucs)."""

    name = "musique_essence"
    description = ("Nouvelle musique gardant l'essence (groove/timbre) d'une référence : "
                   "SA3 Medium init_audio (Vulkan) puis retrait du chant HTDemucs — "
                   "échelle 0,40-0,45 et graine fixe validées ; --keep-vocals pour la version brute")

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        style = params.get("prompt")
        if not style:
            raise ValueError("Style attendu en argument : main.py -w musique_essence \"<style EN>\" -i <référence>")
        reference = params.get("input")
        if not reference or not os.path.exists(reference):
            raise ValueError("Référence audio introuvable : le passer via -i <MP3/WAV>.")

        scale = float(params.get("scale") or DEFAULT_SCALE)
        seed = params.get("seed")
        seed = int(seed) if seed is not None and int(seed) >= 0 else SEED_VALIDEE
        duree = float(params.get("duration") or 0) or 30.0
        backend = params.get("music_backend") or "vulkan"
        keep_vocals = bool(params.get("keep_vocals"))

        nom = slugifier_texte(params.get("output") or os.path.splitext(os.path.basename(reference))[0])[:60]
        dossier = os.path.join("output", "musique_essence", nom)
        os.makedirs(dossier, exist_ok=True)

        self.log(f"Génération SA3 Medium (essence {scale}, graine {seed}, {duree:.0f} s) "
                 f"depuis {reference} — backend {backend}", "🧬")
        gen = generer_essence_sa3(
            style=style, reference=reference, duree=duree, scale=scale,
            seed=seed, sortie_wav=os.path.join(dossier, "brut.wav"), backend=backend,
        )
        rtf_txt = f", RTF {gen['rtf']:.2f}" if gen["rtf"] else ""
        self.log(f"Version brute (avec bave de chant possible) : {gen['mp3']}{rtf_txt}", "✅")
        resultat: Dict[str, Any] = {"brut_wav": gen["wav"], "brut_mp3": gen["mp3"], "rtf": gen["rtf"]}

        if keep_vocals:
            self.log("--keep-vocals actif : retrait de voix sauté", "⏭️")
            return resultat

        self.log("Retrait du chant (HTDemucs) → instrumental", "🎧")
        sep = retirer_voix(gen["wav"], dossier, backend=backend)
        self.log(f"Instrumental prêt : {sep['instrumental_mp3']} — écoute pour valider", "✅")
        self.log(f"Stems conservés : {sep['stems_dir']} (chant isolé : vocals.wav)", "📦")
        resultat.update({
            "instrumental_wav": sep["instrumental_wav"],
            "instrumental_mp3": sep["instrumental_mp3"],
            "stems_dir": sep["stems_dir"],
        })
        return resultat
