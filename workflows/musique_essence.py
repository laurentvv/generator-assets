#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Musique Essence Workflow: new music with the essence of an audio reference
(Stable Audio 3 Medium, init_audio mode) then vocal removal (HTDemucs).

User-validated on 2026-09-09 ("c bien") on the Love Like
Blood reference: scale 0.40-0.45, fixed seed 42 → the drums/guitar of the
reference restored, without the pop bias of the text prompt alone. The vocals of the
reference "smear" into the generation → HTDemucs removes them and delivers a usable
instrumental (no voice cloning = no derivative-content risk).

Steps:
1. SA3 Medium init_audio generation (RTF ~0.8 on RX 6950 XT)
2. (default) HTDemucs vocal removal → instrumental + stems
   (--keep-vocals to keep the raw version with the vocal smear)
"""

import os
from typing import Any, Dict

from core.config import slugifier_texte
from core.music_essence import DEFAULT_SCALE, generer_essence_sa3
from core.separation import retirer_voix
from workflows.base import BaseWorkflow, WorkflowRegistry

VALIDATED_SEED = 42  # seed lottery demonstrated at 0.5 — the validated recipe fixes the seed


@WorkflowRegistry.register
class MusiqueEssenceWorkflow(BaseWorkflow):
    """Music with the essence of a reference (SA3 Medium init_audio + HTDemucs vocal removal)."""

    name = "musique_essence"
    description = ("New music keeping the essence (groove/timbre) of a reference: "
                   "SA3 Medium init_audio (Vulkan) then HTDemucs vocal removal — "
                   "validated scale 0.40-0.45 and fixed seed; --keep-vocals for the raw version")

    emoji = "🧬"

    # CLI declarations (audit §2.2, migration from cli/parser.py's flat table:
    # help/defaults kept as-is, unchanged surface). --duration lives in sfx,
    # --music-backend (shared) in music_bg.
    PARAMETRES = [
        dict(flags=("--scale",), type=float, default=0.45,
             help="init_audio essence scale for musique_essence (default: 0.45; validated plateau 0.40-0.45, >=0.5 = seed lottery, <=0.35 = near-copy with vocal smear)."),
        dict(flags=("--keep-vocals",), action="store_true",
             help="musique_essence: skips the HTDemucs vocal removal (keeps the raw version with the smear of the reference vocals)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        style = params.get("prompt")
        if not style:
            raise ValueError("Style expected as argument: main.py -w musique_essence \"<style EN>\" -i <reference>")
        reference = params.get("input")
        if not reference or not os.path.exists(reference):
            raise ValueError("Audio reference not found: pass it via -i <MP3/WAV>.")

        scale = float(params.get("scale") or DEFAULT_SCALE)
        seed = params.get("seed")
        seed = int(seed) if seed is not None and int(seed) >= 0 else VALIDATED_SEED
        duree = float(params.get("duration") or 0) or 30.0
        backend = params.get("music_backend") or "vulkan"
        keep_vocals = bool(params.get("keep_vocals"))

        nom = slugifier_texte(params.get("output") or os.path.splitext(os.path.basename(reference))[0])[:60]
        dossier = os.path.join("output", "musique_essence", nom)
        os.makedirs(dossier, exist_ok=True)

        self.log(f"SA3 Medium generation (essence {scale}, seed {seed}, {duree:.0f} s) "
                 f"from {reference} — backend {backend}", "🧬")
        gen = generer_essence_sa3(
            style=style, reference=reference, duree=duree, scale=scale,
            seed=seed, sortie_wav=os.path.join(dossier, "brut.wav"), backend=backend,
        )
        rtf_txt = f", RTF {gen['rtf']:.2f}" if gen["rtf"] else ""
        self.log(f"Raw version (possible vocal smear): {gen['mp3']}{rtf_txt}", "✅")
        resultat: Dict[str, Any] = {"brut_wav": gen["wav"], "brut_mp3": gen["mp3"], "rtf": gen["rtf"]}

        if keep_vocals:
            self.log("--keep-vocals active: vocal removal skipped", "⏭️")
            return resultat

        self.log("Vocal removal (HTDemucs) → instrumental", "🎧")
        sep = retirer_voix(gen["wav"], dossier, backend=backend)
        self.log(f"Instrumental ready: {sep['instrumental_mp3']} — listen to validate", "✅")
        self.log(f"Stems kept: {sep['stems_dir']} (isolated vocals: vocals.wav)", "📦")
        resultat.update({
            "instrumental_wav": sep["instrumental_wav"],
            "instrumental_mp3": sep["instrumental_mp3"],
            "stems_dir": sep["stems_dir"],
        })
        return resultat
