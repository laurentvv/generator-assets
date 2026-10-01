#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
monoplan_ia workflow: cut-free AI cinematic single take built from an image
(RECIPE USER-VALIDATED on 2026-09-10 on the Château du Vent-Gris intro).

A single LTX-2.5 I2V generation (65 frames by default = stable GPU ceiling),
slowed down to the target duration with motion-compensated interpolation, then a designed
pure zoom layered on top — no cut, no camera shake. Optional AI sound bed
(SA3 Small SFX). See MEMORY_BANK §1.17 for the rationale of each step.

4K path (`--4k`, ai-doc2video Hero Hooks spec 2026-09-12): the raw 480p master
first goes through the 4x-UltraSharp AI super-resolution (scripts/upscale_video_ai.py,
sd-cli Vulkan, ~7 min for 65 frames) → slow-down + zoom work at 3328×1920 @ 30 fps
→ final 3840×2160 conform in h264_amf 45 Mbps + FidelityFX CAS 0.75. Sharpness is
rebuilt BEFORE interpolation/zoom, where 480p→4K Lanczos crushed everything.
"""

import os
from typing import Any, Dict

from core.cinema import (
    FPS_SORTIE_4K,
    TAILLE_UPSCALE_4X,
    assembler_finale,
    conformer_amorce_16_9,
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
    """AI single-take shot (slowed monoplan + pure zoom): image → 1080p or 4K UHD master, silent or with sound."""

    name = "monoplan_ia"
    description = ("Cinematic single take WITHOUT cut: LTX-2.5 I2V from an image, "
                   "motion-compensated slow-down + designed pure zoom (validated 2026-09-10, §1.17); "
                   "--4k = UltraSharp AI upscale + 3840×2160 AMF master (Hero Hooks)")

    emoji = "🎞️"

    # Declaration of the workflow-specific CLI parameters (audit §2.2 keystone,
    # first family migrated from cli/parser.py's flat table — help/defaults kept
    # as-is, unchanged CLI surface).
    PARAMETRES = [
        dict(flags=("--monoplan-frames",), type=int, default=65,
             help="monoplan_ia: frames of the single LTX-2.5 generation (default: 65 = stable GPU ceiling, max ~81 beyond that device lost — MEMORY_BANK §1.17). Official LTX-2.5 rule: frame count must be 1 + a multiple of 8 (docs.ltx.io) — 65 = 1+64."),
        dict(flags=("--monoplan-duration",), type=float, default=10.0,
             help="monoplan_ia: target duration of the shot in seconds via motion-compensated slow-down (default: 10.0)."),
        dict(flags=("--zoom-debut",), type=float, default=1.10,
             help="monoplan_ia: initial zoom of the designed ramp (default: 1.10)."),
        dict(flags=("--zoom-fin",), type=float, default=1.32,
             help="monoplan_ia: final zoom of the designed ramp (default: 1.32)."),
        dict(flags=("--ambiance",),
             help="monoplan_ia: EN prompt of the optional AI sound bed (SA3 Small SFX, normalization included) muxed onto the master."),
        dict(flags=("--monoplan-source",),
             help="monoplan_ia: already-generated monoplan webm to reuse (resume, skips the GPU generation)."),
        dict(flags=("--carton-titre",),
             help="monoplan_ia: title of the end card (frozen frame + high-couture animated title). \"|\" separates the lines, e.g. \"L'HÉRITIER|DU VIDE\"."),
        dict(flags=("--carton-duree",), type=float, default=6.0,
             help="monoplan_ia: duration of the title card in seconds (default: 6.0)."),
        dict(flags=("--carton-zoom-fin",), type=float, default=1.36,
             help="monoplan_ia: final zoom of the card, continues the shot's ramp (default: 1.36)."),
        dict(flags=("--4k", "--upscale-ia"), dest="upscale_4k", action="store_true",
             help="monoplan_ia: native 4K UHD path — 4x-UltraSharp AI super-resolution of the raw 480p frames (sd-cli Vulkan, ~7 min/65 frames) BEFORE slow-down + zoom (3328×1920 @ 30 fps), conform 3840×2160 h264_amf 45M + FidelityFX CAS 0.75 (ai-doc2video Hero Hooks spec)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        prompt = params.get("prompt")
        if not prompt and not params.get("monoplan_source"):
            raise ValueError("The 'prompt' parameter is required (description of the camera movement and of the scene).")
        image = params.get("input")
        if not image and not params.get("monoplan_source"):
            raise ValueError("A seed image is required (-i image.png), or an existing monoplan (--monoplan-source plan.webm).")

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)
        nom_base = (params.get("output") or
                    (f"{slugifier_texte(prompt)[:40]}_monoplan" if prompt else "monoplan_repris"))

        duree = float(params.get("monoplan_duration") or 10.0)
        frames = int(params.get("monoplan_frames") or 65)
        fps = 24  # native LTX-2.5 cadence, not exposed (validated recipe)
        seed = int(params.get("seed", 42))
        zoom_debut = float(params.get("zoom_debut") or 1.10)
        zoom_fin = float(params.get("zoom_fin") or 1.32)
        ambiance = params.get("ambiance")  # EN prompt of the optional sound bed

        # 4K UHD path (--4k): AI upscale at the head of the chain + AMF master 30 fps
        mode_4k = bool(params.get("upscale_4k"))
        fps_sortie = FPS_SORTIE_4K if mode_4k else fps
        suffixe = "4k" if mode_4k else "1080p"

        amorce = os.path.join(output_dir, f"{nom_base}_amorce_832x480.png")
        webm = params.get("monoplan_source") or os.path.join(output_dir, f"{nom_base}_brut.webm")
        if params.get("monoplan_source") and not os.path.exists(webm):
            raise FileNotFoundError(f"Monoplan source not found: {webm}")
        brut_4k = os.path.join(output_dir, f"{nom_base}_brut_4k_ai.mp4")
        ralenti = os.path.join(output_dir, f"{nom_base}_{duree:.1f}s_{suffixe}_ralenti.mp4")
        master = os.path.join(output_dir, f"{nom_base}_{duree:.1f}s_{suffixe}.mp4")

        self.log(f"AI single take \"monoplan\" ({duree:.1f} s @ {fps_sortie} fps"
                 f"{', 4K UHD path' if mode_4k else ''}, zoom {zoom_debut:.2f}→{zoom_fin:.2f}, seed {seed})…")

        # 1. 16:9 seed frame (or reuse of an already-generated monoplan — resume)
        if not os.path.exists(webm):
            if not image or not os.path.exists(image):
                raise FileNotFoundError(f"Seed image not found: {image}")
            conformer_amorce_16_9(image, amorce)
            self.log("16:9 seed frame ready (Lanczos recrop 832×480).")
            generer_monoplan_ltx(amorce, prompt, webm, frames=frames, fps=fps,
                                 seed=seed, log_fn=lambda m: self.log(m.strip()))
            self.log("Monoplan generated (LTX-2.5 Distilled, 8 steps euler_a, cfg 1.0).")
        else:
            self.log(f"Monoplan already present, reused: {webm}")

        # 1bis. 4K path: AI super-resolution of the raw frames (§1.17 —
        # ALWAYS from the 480p, never from an interpolated master)
        source_ralenti = webm
        if mode_4k:
            if not os.path.exists(brut_4k):
                self.log(f"4x-UltraSharp AI super-resolution of the raw frames "
                         f"(sd-cli Vulkan, ~7 min for {frames} frames)…")
                master_brut_4k(webm, brut_4k, log_fn=lambda m: self.log(m.strip()))
                self.log("Raw 3328×1920 master ready (480p pixelation rebuilt at the source).")
            else:
                self.log(f"Raw 4K master already present: {brut_4k}")
            source_ralenti = brut_4k

        # 2. Slow-down + motion-compensated interpolation to the target duration
        if not os.path.exists(ralenti):
            _, facteur = ralentir_interp(
                source_ralenti, ralenti, duree, fps=fps_sortie,
                taille=None if mode_4k else (1920, 1080))
            self.log(f"Slow-down ×{facteur:.2f} applied (mci/aobmc/vsbmc interpolation, "
                     + ("3328×1920 @ 30 fps" if mode_4k else "1080p") + ").")
        else:
            self.log(f"Slow-down already present: {ralenti}")

        # 3. Designed pure zoom (no measurement in the warp → no shake possible)
        zoom_4k = None
        if not os.path.exists(master):
            if mode_4k:
                zoom_4k = os.path.join(output_dir, f"{nom_base}_{duree:.1f}s_4k_zoom.mp4")
                if not os.path.exists(zoom_4k):
                    zoom_pur(ralenti, zoom_4k, zoom_debut=zoom_debut, zoom_fin=zoom_fin,
                             taille=TAILLE_UPSCALE_4X, fps=fps_sortie, cas=0.0)
                    self.log("Pure zoom applied at 3328×1920 (smootherstep ramp, CAS deferred to the conform).")
                conformer_master_4k(zoom_4k, master, fps=fps_sortie)
                self.log(f"4K UHD master conform (3840×2160 lanczos + CAS, h264_amf {fps_sortie} fps).")
            else:
                zoom_pur(ralenti, master, zoom_debut=zoom_debut, zoom_fin=zoom_fin)
                self.log("Pure zoom applied (smootherstep ramp, CAS 0.75).")
        else:
            self.log(f"Master already present: {master}")

        # 4. Optional AI sound bed + listening version
        livrables = {"master": master, "monoplan_brut": webm, "ralenti": ralenti}
        if mode_4k:
            livrables["master_brut_4k"] = brut_4k
            if zoom_4k:
                livrables["zoom_4k"] = zoom_4k
        wav = None
        if ambiance:
            wav = os.path.join(output_dir, f"{nom_base}_ambiance.wav")
            if not os.path.exists(wav):
                self.log(f"AI sound bed synthesis (SA3 Small SFX): \"{ambiance[:60]}…\"")
                generer_lit_ambiance(ambiance, duree=duree, seed=seed, chemin_wav=wav)
            avec_son = os.path.splitext(master)[0] + "_avec_ambiance.mp4"
            if not os.path.exists(avec_son):
                muxer_audio(master, wav, avec_son)
            livrables["ambiance_wav"] = wav
            livrables["master_avec_ambiance"] = avec_son

        # 5. Optional title card (frozen frame + high-couture animated title)
        carton_titre = params.get("carton_titre")
        if carton_titre:
            lignes = carton_titre.split("|")  # "L'HÉRITIER|DU VIDE" = 2 lines
            carton_duree = float(params.get("carton_duree") or 6.0)
            carton_zoom_fin = float(params.get("carton_zoom_fin") or 1.36)
            trame = os.path.join(output_dir, f"{nom_base}_derniere_trame.png")
            carton = os.path.join(output_dir, f"{nom_base}_carton.mp4")
            finale = os.path.join(output_dir, f"{nom_base}_final_titre.mp4")

            if not os.path.exists(trame):
                extraire_derniere_trame(master, trame)
                self.log("Last frame extracted (card opener).")
            if not os.path.exists(carton):
                self.log(f"Composing the card \"{carton_titre}\" "
                         f"({carton_duree:.1f} s, zoom {zoom_fin:.2f}→{carton_zoom_fin:.2f})…")
                construire_carton_titre(
                    trame, lignes, carton,
                    duree=carton_duree, fps=fps_sortie,
                    zoom_abs_debut=zoom_fin, zoom_abs_fin=carton_zoom_fin,
                    log_fn=lambda m: self.log(m.strip()))
            self.log("Title card composed (cinema reveal, gold ornament).")

            if not os.path.exists(finale):
                if wav:
                    totale = duree + carton_duree
                    wav_etendu = os.path.join(output_dir, f"{nom_base}_ambiance_etendue.wav")
                    etendre_ambiance(wav, totale, wav_etendu)
                    assembler_finale(master, carton, wav_etendu, finale, fps=fps_sortie)
                else:
                    assembler_finale(master, carton, None, finale, fps=fps_sortie)
            self.log("Final assembled (monoplan + card, ambience all the way through).")
            livrables["carton"] = carton
            livrables["final_titre"] = finale

        self.log("Deliverables in " + output_dir + " :", emoji="🎉")
        for cle, chemin in livrables.items():
            self.log(f"  • {cle} : {os.path.basename(chemin)}")

        return {"status": "success", **livrables, "duree": duree, "frames": frames,
                "mode_4k": mode_4k}
