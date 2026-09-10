#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow monoplan_ia : plan-séquence cinématique IA sans coupe depuis une image
(RECETTE VALIDÉE utilisateur le 2026-09-10 sur l'intro du Château du Vent-Gris).

Une seule génération LTX-2.5 I2V (65 trames par défaut = plafond GPU stable),
ralentie vers la durée cible avec interpolation motion-compensée, puis zoom pur
conçu par-dessus — aucune coupe, aucune vibration de caméra. Lit sonore IA
optionnel (SA3 Small SFX). Cf. MEMORY_BANK §1.17 pour le pourquoi de chaque étape.
"""

import os
from typing import Any, Dict

from core.cinema import (
    conformer_amorce_16_9,
    generer_lit_ambiance,
    generer_monoplan_ltx,
    muxer_audio,
    ralentir_interp_1080p,
    zoom_pur,
)
from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class MonoplanIaWorkflow(BaseWorkflow):
    """Plan-séquence IA (monoplan ralenti + zoom pur) : image → master 1080p muet ou sonorisé."""

    name = "monoplan_ia"
    description = ("Plan-séquence cinématique SANS coupe : LTX-2.5 I2V depuis une image, "
                   "ralenti motion-compensé + zoom pur conçu (validé 2026-09-10, §1.17)")

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        prompt = params.get("prompt")
        if not prompt:
            raise ValueError("Le paramètre 'prompt' est requis (description du mouvement de caméra et de la scène).")
        image = params.get("input")
        if not image and not params.get("monoplan_source"):
            raise ValueError("Une image d'amorce est requise (-i image.png), ou un monoplan existant (--monoplan-source plan.webm).")

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)
        nom_base = params.get("output") or f"{slugifier_texte(prompt)[:40]}_monoplan"

        duree = float(params.get("monoplan_duration") or 10.0)
        frames = int(params.get("monoplan_frames") or 65)
        fps = 24  # cadence native LTX-2.5, non exposée (recette validée)
        seed = int(params.get("seed", 42))
        zoom_debut = float(params.get("zoom_debut") or 1.10)
        zoom_fin = float(params.get("zoom_fin") or 1.32)
        ambiance = params.get("ambiance")  # prompt EN du lit sonore optionnel

        amorce = os.path.join(output_dir, f"{nom_base}_amorce_832x480.png")
        webm = params.get("monoplan_source") or os.path.join(output_dir, f"{nom_base}_brut.webm")
        ralenti = os.path.join(output_dir, f"{nom_base}_{duree:.1f}s_1080p_ralenti.mp4")
        master = os.path.join(output_dir, f"{nom_base}_{duree:.1f}s_1080p.mp4")

        self.log(f"Plan-séquence IA « monoplan » ({duree:.1f} s @ {fps} fps, zoom {zoom_debut:.2f}→{zoom_fin:.2f}, seed {seed})…")

        # 1. Amorce 16:9 (ou réutilisation d'un monoplan déjà généré — reprise)
        if not os.path.exists(webm):
            if not image or not os.path.exists(image):
                raise FileNotFoundError(f"Image d'amorce introuvable : {image}")
            conformer_amorce_16_9(image, amorce)
            self.log("Amorce 16:9 prête (recadrage Lanczos 832×480).")
            generer_monoplan_ltx(amorce, prompt, webm, frames=frames, fps=fps,
                                 seed=seed, log_fn=lambda m: self.log(m.strip()))
            self.log("Monoplan généré (LTX-2.5 Distilled, 8 steps euler_a, cfg 1.0).")
        else:
            self.log(f"Monoplan déjà présent, réutilisé : {webm}")

        # 2. Ralenti + interpolation motion-compensée vers la durée cible
        if not os.path.exists(ralenti):
            _, facteur = ralentir_interp_1080p(webm, ralenti, duree, fps=fps)
            self.log(f"Ralenti ×{facteur:.2f} appliqué (interpolation mci/aobmc/vsbmc, 1080p).")
        else:
            self.log(f"Ralenti déjà présent : {ralenti}")

        # 3. Zoom pur conçu (aucune mesure dans le warp → aucune vibration possible)
        if not os.path.exists(master):
            zoom_pur(ralenti, master, zoom_debut=zoom_debut, zoom_fin=zoom_fin)
            self.log("Zoom pur appliqué (rampe smootherstep, CAS 0.75).")
        else:
            self.log(f"Master déjà présent : {master}")

        # 4. Lit sonore IA optionnel + version d'écoute
        livrables = {"master": master, "monoplan_brut": webm, "ralenti": ralenti}
        if ambiance:
            wav = os.path.join(output_dir, f"{nom_base}_ambiance.wav")
            if not os.path.exists(wav):
                self.log(f"Synthèse du lit sonore IA (SA3 Small SFX) : « {ambiance[:60]}… »")
                generer_lit_ambiance(ambiance, duree=duree, seed=seed, chemin_wav=wav)
            avec_son = os.path.splitext(master)[0] + "_avec_ambiance.mp4"
            if not os.path.exists(avec_son):
                muxer_audio(master, wav, avec_son)
            livrables["ambiance_wav"] = wav
            livrables["master_avec_ambiance"] = avec_son

        self.log("Livrables dans " + output_dir + " :", emoji="🎉")
        for cle, chemin in livrables.items():
            self.log(f"  • {cle} : {os.path.basename(chemin)}")

        return {"status": "success", **livrables, "duree": duree, "frames": frames}
