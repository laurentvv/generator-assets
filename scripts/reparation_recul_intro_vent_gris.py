#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/reparation_recul_intro_vent_gris.py — réparation du « recul » (2026-09-10 matin)
Les plans chaînés 2-4 démarrent par un léger tête-à-queue (le modèle reprend depuis
la trame gelée puis ré-enclenche le travelling) : saut de position à la coupe + glissement
arrière lent perçu à l'œil. Correctif :
  1. Régénération des plans 2-4 en 81 trames (au lieu de 65) avec prompt anti-recul
     explicite (« constant slow forward speed, framing never widens, never backward »).
  2. Assemblage avec SUPPRESSION des 12 premières trames (0,5 s) de chaque plan intérieur
     — la trame 12 est déjà repartie en avant, et elle repart de la position de coupe.
  3. 65 + 69×3 = 272 trames utiles = 11,33 s → master rogner à 10,000 s.
Réutilise les fonctions du lanceur de nuit (moteur LTX-2.5 I2V validé la nuit même).
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, r"C:\GIT\generator-assets")
from scripts.lancement_nuit_intro_vent_gris import (  # noqa: E402
    OUTPUT_DIR, FFMPEG, generer_ltx_i2v, extraire_derniere_trame,
    conformer_1080p, executer, verifier_charge, log,
)

ANTI_RECUL = (
    " The camera keeps gliding forward at the exact same constant slow speed as at "
    "the very first frame, one single continuous take; the framing never widens, "
    "the image never moves backward, no zoom out, no pause in the forward motion."
)
PROMPTS = {
    "plan2": (
        "Seamless continuation of the very slow dolly-in toward the medieval fortress "
        "on its cliff. The fortress grows steadily larger in frame as the camera glides "
        "forward through drifting salt mist. Storm clouds crawl overhead, waves keep "
        "crashing on the dark rocks below, the warm window lights flicker faintly. "
        "Desaturated cold palette, painterly dark fantasy, oppressive melancholic atmosphere."
        + ANTI_RECUL
    ),
    "plan3": (
        "Seamless continuation of the slow dolly-in: the fortress keep dominates the "
        "frame from its windswept cliff. The camera glides steadily forward through "
        "thinning salt mist, battlements and narrow windows growing continuously larger, "
        "storm clouds crawling overhead, waves crashing below. Desaturated cold palette, "
        "painterly dark fantasy, oppressive melancholic atmosphere." + ANTI_RECUL
    ),
    "plan4": (
        "Final continuation of the slow dolly-in, ending on a medium-close view of the "
        "fortress gate and the high narrow window above it. The camera glides forward "
        "and slowly settles, mist drifting across the battlements, warm window light "
        "flickering steadily as if someone waits inside. Desaturated cold palette, "
        "painterly dark fantasy, oppressive melancholic atmosphere, the shot comes to "
        "rest for a title card." + ANTI_RECUL
    ),
}
TETE_COUPPEE = 12  # trames retirées en tête des plans intérieurs (le tête-à-queue)
DUREE_TOTALE = 10.0


def conformer_avec_coupe(source: str, destination: str, couper_tete: int) -> bool:
    """Conform 1080p CAS avec retrait des trames de tête (tête-à-queue)."""
    vf = (f"trim=start_frame={couper_tete},setpts=PTS-STARTPTS,"
          "scale=1920:1080:flags=lanczos,cas=0.75") if couper_tete else \
         "scale=1920:1080:flags=lanczos,cas=0.75"
    return subprocess.run(
        [FFMPEG, "-y", "-i", source, "-vf", vf, "-an", "-pix_fmt", "yuv420p",
         "-c:v", "libx264", "-crf", "12", "-preset", "slow", destination],
        capture_output=True,
    ).returncode == 0


def main() -> None:
    chemins = {cle: os.path.join(OUTPUT_DIR, f"{cle}_brut.webm") for cle in
               ("plan1", "plan2", "plan3", "plan4")}
    amorces = {cle: os.path.join(OUTPUT_DIR, f"amorce_{cle}.png") for cle in
               ("plan2", "plan3", "plan4")}
    conformes = {cle: os.path.join(OUTPUT_DIR, f"{cle}_v3_1080p.mp4") for cle in
                 ("plan1", "plan2", "plan3", "plan4")}
    master = os.path.join(OUTPUT_DIR, "intro_vent_gris_10s_1080p_v3.mp4")

    if not os.path.exists(chemins["plan1"]):
        log("⛔ plan1 absent — lancez d'abord le lanceur de nuit.")
        sys.exit(2)

    # ── Régénération chaînée des plans 2-4 en 81 trames ──────────────────────
    precedent = "plan1"
    for cle in ("plan2", "plan3", "plan4"):
        if os.path.exists(chemins[cle]):
            log(f"⏭️ {cle} déjà régénéré.")
        else:
            if not os.path.exists(amorces[cle]):
                extraire_derniere_trame(chemins[precedent], amorces[cle])
            log(f"🎥 Régénération {cle} (81 trames, prompt anti-recul)…")
            t0 = time.time()
            ok = generer_ltx_i2v(amorces[cle], PROMPTS[cle], chemins[cle],
                                 os.path.join(OUTPUT_DIR, f"{cle}_v3.log"), frames=81)
            if not ok:
                log(f"⛔ {cle} impossible après réessais — arrêt.")
                sys.exit(3)
            log(f"  ✅ {cle} régénéré en {(time.time()-t0)/60:.1f} min")
        precedent = cle

    # ── Conform avec coupe de tête ───────────────────────────────────────────
    for cle in ("plan1", "plan2", "plan3", "plan4"):
        if not os.path.exists(conformes[cle]):
            coupe = 0 if cle == "plan1" else TETE_COUPPEE
            log(f"🎬 Conform {cle} (coupe tête={coupe})…")
            if not conformer_avec_coupe(chemins[cle], conformes[cle], coupe):
                log(f"⛔ conform {cle} échoué.")
                sys.exit(4)

    # ── Assemblage final 10,000 s ────────────────────────────────────────────
    liste = os.path.join(OUTPUT_DIR, "concat_v3.txt")
    with open(liste, "w", encoding="utf-8") as f:
        for cle in ("plan1", "plan2", "plan3", "plan4"):
            f.write(f"file '{conformes[cle].replace(os.sep, '/')}'\n")
    log("🎬 Assemblage master v3 (10,000 s)…")
    ok = subprocess.run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", liste,
         "-t", str(DUREE_TOTALE),
         "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", master],
        capture_output=True,
    ).returncode == 0
    log("✅ Master v3 : " + master if ok else "❌ assemblage v3 échoué")
    if ok:
        subprocess.run(
            [FFMPEG, "-y", "-i", master,
             "-i", os.path.join(OUTPUT_DIR, "ambiance_tempete_vent_gris.wav"),
             "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest",
             os.path.join(OUTPUT_DIR, "intro_vent_gris_10s_1080p_v3_avec_ambiance.mp4")],
            capture_output=True,
        )


if __name__ == "__main__":
    main()
