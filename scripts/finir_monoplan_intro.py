#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/finir_monoplan_intro.py — v6 "single shot" of the Grey-Wind intro (2026-09-10)
Fix for the missed cuts: ONE SINGLE shot generated in a take (65 frames, the most
proven value on this GPU), slowed ×3.69 to 10.0 s, then a designed pure zoom
(validated v5 recipe) on top — no cut, no camera breathing. To be run AFTER a
machine restart (the GPU driver degrades after cascading device-losts — pitfall
§1.10; at 13:45 the 65f run failed, overnight it passed).

Steps:
  1. 65-frame LTX-2.5 I2V single shot from the reference image (overnight recipe);
  2. Slowdown 65f → 10.0 s: setpts ×3.6923 + 24 fps motion-compensated interpolation;
  3. Pure zoom 1.10→1.32 (smootherstep) around the keep anchor — a render that
     cannot shake by construction (no measurement in the warp loop);
  4. 1080p conform (lanczos + CAS 0.75) + storm ambience muxed + 48 fps variant.
"""
import os
import shutil
import subprocess
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, r"C:\GIT\generator-assets")
from scripts.lancement_nuit_intro_vent_gris import (  # noqa: E402
    OUTPUT_DIR, FFMPEG, generer_ltx_i2v, log,
)

ES = OUTPUT_DIR
MONOPLAN = os.path.join(ES, "monoplan_65f.webm")
RALENTI = os.path.join(ES, "monoplan_10s_24fps.mp4")
V6_24 = os.path.join(ES, "intro_vent_gris_10s_1080p_v6_monoplan.mp4")
V6_48 = os.path.join(ES, "intro_vent_gris_10s_v6_48fps.mp4")
AMBIANCE = os.path.join(ES, "ambiance_tempete_vent_gris.wav")

FACTEUR_LENT = 3.6923          # 65/24 s × 3.6923 = 10.000 s
PATCH = (300, 40, 540, 300)    # keep anchor (640×360 coords)
ZOOM_DEBUT, ZOOM_FIN = 1.10, 1.32

PROMPT_MONOPLAN = (
    "Slow cinematic dolly-in toward a gaunt medieval fortress clinging to a "
    "windswept cliff above a storm-gray sea. Heavy lead-gray storm clouds drift "
    "slowly overhead, salt mist sweeps horizontally across the battlements, storm "
    "waves crash and foam against the dark rocks below, a distant sailing ship "
    "bobs gently on the swell, faint warm window lights flicker in the keep. "
    "Desaturated cold palette, painterly dark fantasy, oppressive melancholic "
    "atmosphere."
)


def etape_1_monoplan() -> None:
    if os.path.exists(MONOPLAN):
        log(f"⏭️ 1. single shot already present: {MONOPLAN}")
        return
    log("🎥 1/4 Generating the single shot (65 frames LTX-2.5 I2V)…")
    t0 = time.time()
    ok = generer_ltx_i2v(os.path.join(ES, "amorce_832x480.png"), PROMPT_MONOPLAN,
                         MONOPLAN, os.path.join(ES, "monoplan_65f.log"), frames=65)
    if not ok:
        log("⛔ Single shot failed (GPU driver to reset? machine restart).")
        sys.exit(3)
    log(f"  ✅ single shot in {(time.time()-t0)/60:.1f} min")


def etape_2_ralenti() -> None:
    if os.path.exists(RALENTI):
        log(f"⏭️ 2. slowdown already present: {RALENTI}")
        return
    log(f"⏱️ 2/4 Slowdown ×{FACTEUR_LENT} + 24 fps interpolation → 10.0 s…")
    t0 = time.time()
    # 1080p from step 2: step 3 (pure zoom) works in 1920×1080 coordinates
    ok = subprocess.run(
        [FFMPEG, "-y", "-v", "error", "-i", MONOPLAN, "-vf",
         f"setpts={FACTEUR_LENT}*PTS,"
         "minterpolate=fps=24:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"
         "scale=1920:1080:flags=lanczos",
         "-an", "-c:v", "libx264", "-crf", "12", "-preset", "slow",
         "-pix_fmt", "yuv420p", RALENTI],
        capture_output=True,
    ).returncode == 0
    if not ok:
        log("⛔ slowdown/interpolation failed")
        sys.exit(4)
    log(f"  ✅ slowdown in {(time.time()-t0)/60:.1f} min")


def etape_3_zoom_pur() -> None:
    if os.path.exists(V6_24):
        log(f"⏭️ 3. v6 already present: {V6_24}")
        return
    log("🎨 3/4 Pure zoom 1.10→1.32 (no measurement → no vibration possible)…")
    t0 = time.time()
    tmp = os.path.join(ES, "temp_v6")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    subprocess.run([FFMPEG, "-y", "-v", "error", "-i", RALENTI, "-fps_mode", "passthrough",
                    "-q:v", "2", os.path.join(tmp, "f_%04d.png")], capture_output=True)
    pngs = sorted(f for f in os.listdir(tmp) if f.startswith("f_"))
    n = len(pngs)
    ancre = np.array([(PATCH[0] + PATCH[2]) / 2.0, (PATCH[1] + PATCH[3]) / 2.0]) * 3.0
    W, H = 1920, 1080
    u = np.linspace(0.0, 1.0, n)
    ease = u * u * u * (u * (u * 6.0 - 15.0) + 10.0)
    for i, nom in enumerate(pngs):
        img = cv2.imread(os.path.join(tmp, nom))
        k = 1.0 / (ZOOM_DEBUT + (ZOOM_FIN - ZOOM_DEBUT) * ease[i])
        tx = ancre[0] * (1.0 - k)
        ty = ancre[1] * (1.0 - k)
        tx = min(max(tx, min(0.0, W * (1 - k))), max(0.0, W * (1 - k)))
        ty = min(max(ty, min(0.0, H * (1 - k))), max(0.0, H * (1 - k)))
        M = np.array([[k, 0.0, tx], [0.0, k, ty]], dtype=np.float64)
        corr = cv2.warpAffine(img, M, (W, H),
                              flags=cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP)
        cv2.imwrite(os.path.join(tmp, f"s_{i+1:04d}.png"), corr,
                    [cv2.IMWRITE_PNG_COMPRESSION, 3])
    subprocess.run([FFMPEG, "-y", "-v", "error", "-framerate", "24", "-start_number", "1",
                    "-i", os.path.join(tmp, "s_%04d.png"), "-frames:v", str(n),
                    "-vf", "cas=0.75",
                    "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", V6_24],
                   capture_output=True)
    nb = subprocess.run(["C:/ffmpeg/dist/bin/ffprobe.exe", "-v", "error", "-count_frames",
                         "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
                         "-of", "csv=p=0", V6_24], capture_output=True, text=True).stdout.strip()
    if nb != str(n):
        log(f"⛔ incomplete v6 encode ({nb}/{n})")
        sys.exit(5)
    shutil.rmtree(tmp, ignore_errors=True)
    log(f"  ✅ v6 ({n} frames) in {(time.time()-t0)/60:.1f} min")


def etape_4_livrables() -> None:
    log("🔊 4/4 Ambience + 48 fps variant…")
    if os.path.exists(AMBIANCE):
        subprocess.run(
            [FFMPEG, "-y", "-v", "error", "-i", V6_24, "-i", AMBIANCE,
             "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest",
             os.path.join(ES, "intro_vent_gris_10s_v6_avec_ambiance.mp4")],
            capture_output=True,
        )
    if not os.path.exists(V6_48):
        subprocess.run(
            [FFMPEG, "-y", "-v", "error", "-i", V6_24,
             "-vf", "minterpolate=fps=48:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1",
             "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", V6_48],
            capture_output=True,
        )
    log(f"🌅 V6 READY: {V6_24}")
    log("   + ambience: intro_vent_gris_10s_v6_avec_ambiance.mp4")
    log(f"   + 48 fps   : {os.path.basename(V6_48)}")


if __name__ == "__main__":
    etape_1_monoplan()
    etape_2_ralenti()
    etape_3_zoom_pur()
    etape_4_livrables()
