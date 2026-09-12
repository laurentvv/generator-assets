#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow monoplan_ia : plan-séquence cinématique IA sans coupe depuis une image
(RECETTE VALIDÉE utilisateur le 2026-09-10 sur l'intro du Château du Vent-Gris).

Une seule génération LTX-2.5 I2V (65 trames par défaut = plafond GPU stable),
ralentie vers la durée cible avec interpolation motion-compensée, puis zoom pur
conçu par-dessus — aucune coupe, aucune vibration de caméra. Lit sonore IA
optionnel (SA3 Small SFX). Cf. MEMORY_BANK §1.17 pour le pourquoi de chaque étape.

Chemin 4K (`--4k`, spéc Hero Hooks ai-doc2video 2026-09-12) : le master brut 480p
passe d'abord dans la super-résolution IA 4x-UltraSharp (scripts/upscale_video_ai.py,
sd-cli Vulkan, ~7 min pour 65 trames) → ralenti + zoom travaillent en 3328×1920 @ 30 fps
→ conform finale 3840×2160 en h264_amf 45 Mbps + FidelityFX CAS 0.75. Le piqué est
reconstruit AVANT interpolation/zoom, là où le Lanczos 480p→4K écrasait tout.
"""

import os
from typing import Any, Dict

from core.cinema import (
    FPS_SORTIE_4K,
    TAILLE_UPSCALE_4X,
    assembler_finale,
    conformer_master_4k,
    construire_carton_titre,
    etendre_ambiance,
    extraire_derniere_trame,
    generer_lit_ambiance,
    generer_monoplan_ltx,
    master_brut_4k,
    muxer_audio,
    ralentir_interp,
    zoom_pur,
)
from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class MonoplanIaWorkflow(BaseWorkflow):
    """Plan-séquence IA (monoplan ralenti + zoom pur) : image → master 1080p ou 4K UHD, muet ou sonorisé."""

    name = "monoplan_ia"
    description = ("Plan-séquence cinématique SANS coupe : LTX-2.5 I2V depuis une image, "
                   "ralenti motion-compensé + zoom pur conçu (validé 2026-09-10, §1.17) ; "
                   "--4k = upscale IA UltraSharp + master 3840×2160 AMF (Hero Hooks)")

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        prompt = params.get("prompt")
        if not prompt and not params.get("monoplan_source"):
            raise ValueError("Le paramètre 'prompt' est requis (description du mouvement de caméra et de la scène).")
        image = params.get("input")
        if not image and not params.get("monoplan_source"):
            raise ValueError("Une image d'amorce est requise (-i image.png), ou un monoplan existant (--monoplan-source plan.webm).")

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)
        nom_base = (params.get("output") or
                    (f"{slugifier_texte(prompt)[:40]}_monoplan" if prompt else "monoplan_repris"))

        duree = float(params.get("monoplan_duration") or 10.0)
        frames = int(params.get("monoplan_frames") or 65)
        fps = 24  # cadence native LTX-2.5, non exposée (recette validée)
        seed = int(params.get("seed", 42))
        zoom_debut = float(params.get("zoom_debut") or 1.10)
        zoom_fin = float(params.get("zoom_fin") or 1.32)
        ambiance = params.get("ambiance")  # prompt EN du lit sonore optionnel

        # Chemin 4K UHD (--4k) : upscale IA en tête de chaîne + master AMF 30 fps
        mode_4k = bool(params.get("upscale_4k"))
        fps_sortie = FPS_SORTIE_4K if mode_4k else fps
        suffixe = "4k" if mode_4k else "1080p"

        amorce = os.path.join(output_dir, f"{nom_base}_amorce_832x480.png")
        webm = params.get("monoplan_source") or os.path.join(output_dir, f"{nom_base}_brut.webm")
        if params.get("monoplan_source") and not os.path.exists(webm):
            raise FileNotFoundError(f"Monoplan source introuvable : {webm}")
        brut_4k = os.path.join(output_dir, f"{nom_base}_brut_4k_ai.mp4")
        ralenti = os.path.join(output_dir, f"{nom_base}_{duree:.1f}s_{suffixe}_ralenti.mp4")
        master = os.path.join(output_dir, f"{nom_base}_{duree:.1f}s_{suffixe}.mp4")

        self.log(f"Plan-séquence IA « monoplan » ({duree:.1f} s @ {fps_sortie} fps"
                 f"{', chemin 4K UHD' if mode_4k else ''}, zoom {zoom_debut:.2f}→{zoom_fin:.2f}, seed {seed})…")

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

        # 1bis. Chemin 4K : super-résolution IA des trames brutes (§1.17 —
        # TOUJOURS depuis le 480p, jamais depuis un master interpolé)
        source_ralenti = webm
        if mode_4k:
            if not os.path.exists(brut_4k):
                self.log(f"Super-résolution IA 4x-UltraSharp des trames brutes "
                         f"(sd-cli Vulkan, ~7 min pour {frames} trames)…")
                master_brut_4k(webm, brut_4k, log_fn=lambda m: self.log(m.strip()))
                self.log("Master brut 3328×1920 prêt (pixellisation 480p reconstruite à la source).")
            else:
                self.log(f"Master brut 4K déjà présent : {brut_4k}")
            source_ralenti = brut_4k

        # 2. Ralenti + interpolation motion-compensée vers la durée cible
        if not os.path.exists(ralenti):
            _, facteur = ralentir_interp(
                source_ralenti, ralenti, duree, fps=fps_sortie,
                taille=None if mode_4k else (1920, 1080))
            self.log(f"Ralenti ×{facteur:.2f} appliqué (interpolation mci/aobmc/vsbmc, "
                     + ("3328×1920 @ 30 fps" if mode_4k else "1080p") + ").")
        else:
            self.log(f"Ralenti déjà présent : {ralenti}")

        # 3. Zoom pur conçu (aucune mesure dans le warp → aucune vibration possible)
        zoom_4k = None
        if not os.path.exists(master):
            if mode_4k:
                zoom_4k = os.path.join(output_dir, f"{nom_base}_{duree:.1f}s_4k_zoom.mp4")
                if not os.path.exists(zoom_4k):
                    zoom_pur(ralenti, zoom_4k, zoom_debut=zoom_debut, zoom_fin=zoom_fin,
                             taille=TAILLE_UPSCALE_4X, fps=fps_sortie, cas=0.0)
                    self.log("Zoom pur appliqué en 3328×1920 (rampe smootherstep, CAS reporté à la conform).")
                conformer_master_4k(zoom_4k, master, fps=fps_sortie)
                self.log(f"Conform master 4K UHD (3840×2160 lanczos + CAS, h264_amf {fps_sortie} fps).")
            else:
                zoom_pur(ralenti, master, zoom_debut=zoom_debut, zoom_fin=zoom_fin)
                self.log("Zoom pur appliqué (rampe smootherstep, CAS 0.75).")
        else:
            self.log(f"Master déjà présent : {master}")

        # 4. Lit sonore IA optionnel + version d'écoute
        livrables = {"master": master, "monoplan_brut": webm, "ralenti": ralenti}
        if mode_4k:
            livrables["master_brut_4k"] = brut_4k
            if zoom_4k:
                livrables["zoom_4k"] = zoom_4k
        wav = None
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

        # 5. Carton de titre optionnel (image figée + titre haute couture animé)
        carton_titre = params.get("carton_titre")
        if carton_titre:
            lignes = carton_titre.split("|")  # « L'HÉRITIER|DU VIDE » = 2 lignes
            carton_duree = float(params.get("carton_duree") or 6.0)
            carton_zoom_fin = float(params.get("carton_zoom_fin") or 1.36)
            trame = os.path.join(output_dir, f"{nom_base}_derniere_trame.png")
            carton = os.path.join(output_dir, f"{nom_base}_carton.mp4")
            finale = os.path.join(output_dir, f"{nom_base}_final_titre.mp4")

            if not os.path.exists(trame):
                extraire_derniere_trame(master, trame)
                self.log("Dernière trame extraite (amorce du carton).")
            if not os.path.exists(carton):
                self.log(f"Composition du carton « {carton_titre} » "
                         f"({carton_duree:.1f} s, zoom {zoom_fin:.2f}→{carton_zoom_fin:.2f})…")
                construire_carton_titre(
                    trame, lignes, carton,
                    duree=carton_duree, fps=fps_sortie,
                    zoom_abs_debut=zoom_fin, zoom_abs_fin=carton_zoom_fin,
                    log_fn=lambda m: self.log(m.strip()))
            self.log("Carton de titre composé (révélation cinéma, ornement or).")

            if not os.path.exists(finale):
                if wav:
                    totale = duree + carton_duree
                    wav_etendu = os.path.join(output_dir, f"{nom_base}_ambiance_etendue.wav")
                    etendre_ambiance(wav, totale, wav_etendu)
                    assembler_finale(master, carton, wav_etendu, finale, fps=fps_sortie)
                else:
                    assembler_finale(master, carton, None, finale, fps=fps_sortie)
            self.log("Finale assemblée (monoplan + carton, ambiance jusqu'au bout).")
            livrables["carton"] = carton
            livrables["final_titre"] = finale

        self.log("Livrables dans " + output_dir + " :", emoji="🎉")
        for cle, chemin in livrables.items():
            self.log(f"  • {cle} : {os.path.basename(chemin)}")

        return {"status": "success", **livrables, "duree": duree, "frames": frames,
                "mode_4k": mode_4k}
