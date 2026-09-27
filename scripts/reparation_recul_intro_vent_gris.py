#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/reparation_recul_intro_vent_gris.py — repair of the "push-back" (2026-09-10 morning)
Chained shots 2-4 start with a slight head-tail lag (the model resumes from the frozen
frame then re-engages the dolly): position jump at the cut + slow backward drift
perceived by the eye. Fix:
  1. Regenerate shots 2-4 in 81 frames (instead of 65) with an explicit anti-push-back
     prompt ("constant slow forward speed, framing never widens, never backward").
  2. Assembly with REMOVAL of the first 12 frames (0.5 s) of each inner shot
     — frame 12 is already moving forward again, and it restarts from the cut position.
  3. 65 + 69×3 = 272 usable frames = 11.33 s → master trimmed to 10.000 s.
Reuses the functions of the night launcher (LTX-2.5 I2V engine validated the same night).
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, r"C:\GIT\generator-assets")
from scripts.lancement_nuit_intro_vent_gris import (  # noqa: E402
    OUTPUT_DIR, FFMPEG, generer_ltx_i2v, extraire_derniere_trame,
    log,
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
TETE_COUPPEE = 12  # frames trimmed at the head of the inner shots (the head-tail lag)
DUREE_TOTALE = 10.0


def conformer_avec_coupe(source: str, destination: str, couper_tete: int) -> bool:
    """1080p CAS conform with removal of the head frames (head-tail lag)."""
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
        log("⛔ plan1 missing — run the night launcher first.")
        sys.exit(2)

    # ── Chained regeneration of shots 2-4 in 81 frames ───────────────────────
    precedent = "plan1"
    for cle in ("plan2", "plan3", "plan4"):
        if os.path.exists(chemins[cle]):
            log(f"⏭️ {cle} already regenerated.")
        else:
            if not os.path.exists(amorces[cle]):
                extraire_derniere_trame(chemins[precedent], amorces[cle])
            log(f"🎥 Regenerating {cle} (81 frames, anti-push-back prompt)…")
            t0 = time.time()
            ok = generer_ltx_i2v(amorces[cle], PROMPTS[cle], chemins[cle],
                                 os.path.join(OUTPUT_DIR, f"{cle}_v3.log"), frames=81)
            if not ok:
                log(f"⛔ {cle} failed after retries — stopping.")
                sys.exit(3)
            log(f"  ✅ {cle} regenerated in {(time.time()-t0)/60:.1f} min")
        precedent = cle

    # ── Conform with head trim ───────────────────────────────────────────────
    for cle in ("plan1", "plan2", "plan3", "plan4"):
        if not os.path.exists(conformes[cle]):
            coupe = 0 if cle == "plan1" else TETE_COUPPEE
            log(f"🎬 Conform {cle} (head trim={coupe})…")
            if not conformer_avec_coupe(chemins[cle], conformes[cle], coupe):
                log(f"⛔ conform {cle} failed.")
                sys.exit(4)

    # ── Final assembly 10.000 s ──────────────────────────────────────────────
    liste = os.path.join(OUTPUT_DIR, "concat_v3.txt")
    with open(liste, "w", encoding="utf-8") as f:
        for cle in ("plan1", "plan2", "plan3", "plan4"):
            f.write(f"file '{conformes[cle].replace(os.sep, '/')}'\n")
    log("🎬 Assembling master v3 (10.000 s)…")
    ok = subprocess.run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", liste,
         "-t", str(DUREE_TOTALE),
         "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", master],
        capture_output=True,
    ).returncode == 0
    log("✅ Master v3: " + master if ok else "❌ v3 assembly failed")
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
