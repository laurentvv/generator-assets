#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/aligner_raccords_intro.py — surgery on the I2V chaining cuts (2026-09-10)
Measures via ECC (cv2) the scale/translation gap between the last frame of shot N and
the cut frame of shot N+1 (after removal of the head frames), then:
  • --mesurer mode: prints the ratios per cut;
  • --appliquer mode: re-conforms the inner shots with a centered compensation zoom
    (the scale brings the castle size back to identical at the cut),
    re-assembles the master and re-measures the jitter profile.
The zoom only compensates what the cut cannot absorb; it is bounded (≤ 8 %).
"""
import argparse
import os
import subprocess
import sys
import tempfile

import cv2
import numpy as np

sys.path.insert(0, r"C:\GIT\generator-assets")
from scripts.lancement_nuit_intro_vent_gris import OUTPUT_DIR, FFMPEG, log  # noqa: E402

PLANS = ["plan1", "plan2", "plan3", "plan4"]
TETE_COUPPEE = 12        # head frames removed from the inner shots (see repair)
ZOOM_MAX = 1.08          # guardrail: beyond that, report rather than zoom
SEUIL_SACCADE = 2.2      # diff peak (× local motion) considered a jitter


def extraire_trame(video: str, index: int) -> np.ndarray:
    """Extracts a (0-based) frame in grayscale, measurement scale 640 px."""
    out = os.path.join(tempfile.gettempdir(), f"trame_{index}.png")
    subprocess.run(
        [FFMPEG, "-y", "-i", video, "-vf",
         f"select='eq(n\\,{index})',scale=640:-1", "-fps_mode", "passthrough",
         "-vframes", "1", out],
        capture_output=True, check=True,
    )
    img = cv2.imread(out, cv2.IMREAD_GRAYSCALE)
    os.remove(out)
    if img is None:
        raise RuntimeError(f"frame {index} unreadable in {video}")
    return img


def mesurer_raccord(fin_a: np.ndarray, debut_b: np.ndarray):
    """ECC affine A→B: returns (scale of B's content relative to A, dx, dy)."""
    a = fin_a.astype(np.float32) / 255.0
    b = debut_b.astype(np.float32) / 255.0
    warp = np.eye(2, 3, dtype=np.float32)
    try:
        _, warp = cv2.findTransformECC(a, b, warp, cv2.MOTION_AFFINE,
                                       (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
                                        200, 1e-7), None, 5)
    except cv2.error:
        return None
    echelle = float(np.sqrt(np.abs(np.linalg.det(warp[:2, :2]))))
    return echelle, float(warp[0, 2]), float(warp[1, 2])


def profil_saccades(video: str):
    """Inter-frame diff of the master; returns the series and the peaks at the cuts."""
    cmd = [FFMPEG, "-v", "error", "-i", video, "-vf", "scale=192:108",
           "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    f = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 108, 192).astype(np.float32)
    diffs = np.abs(np.diff(f, axis=0)).mean(axis=(1, 2))
    # cut positions: 65, 65+69, 65+69+69 frames (shifted by 1 for the diff)
    coupes = [65, 134, 203]
    pics = {t: float(diffs[t - 1]) for t in coupes if 0 < t - 1 < len(diffs)}
    return diffs, pics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesurer", action="store_true", help="prints the gaps per cut")
    parser.add_argument("--appliquer", action="store_true",
                        help="re-conforms with compensation zoom and re-assembles")
    parser.add_argument("--master", default=os.path.join(OUTPUT_DIR, "intro_vent_gris_10s_1080p_v3.mp4"))
    args = parser.parse_args()

    bruts = {p: os.path.join(OUTPUT_DIR, f"{p}_brut.webm") for p in PLANS}
    conformes = {p: os.path.join(OUTPUT_DIR, f"{p}_v3_1080p.mp4") for p in PLANS}
    zooms = {p: 1.0 for p in PLANS[1:]}

    if args.mesurer or args.appliquer:
        log("📏 ECC measurement of the cuts (end of shot N vs cut frame of shot N+1):")
        for i, p in enumerate(PLANS[1:], start=1):
            nb_b = int(subprocess.run(
                ["C:/ffmpeg/dist/bin/ffprobe.exe", "-v", "error", "-select_streams", "v:0",
                 "-count_frames", "-show_entries", "stream=nb_read_frames",
                 "-of", "csv=p=0", bruts[p]], capture_output=True, text=True).stdout or 0)
            idx_b = min(TETE_COUPPEE, max(0, nb_b - 1))
            res = mesurer_raccord(extraire_trame(bruts[PLANS[i - 1]], 64),
                                  extraire_trame(bruts[p], idx_b))
            if res is None:
                log(f"  {p} : ECC not converged — zoom 1.0 kept")
                continue
            echelle, dx, dy = res
            # B's content is 1/echelle times A's (warp maps A to B);
            # to re-align, we zoom B by 1/echelle (bounded)
            z = min(ZOOM_MAX, max(1.0, 1.0 / echelle))
            zooms[p] = z
            log(f"  {p} : relative scale={echelle:.4f} → compensation zoom={z:.4f} "
                f"(dx={dx:.1f}px, dy={dy:.1f}px at measurement scale)")

    if args.appliquer:
        for p in PLANS[1:]:
            z = zooms[p]
            src = bruts[p]
            vf = (f"trim=start_frame={TETE_COUPPEE},setpts=PTS-STARTPTS,")
            if z > 1.001:
                vf += f"scale=trunc(iw*{z:.5f}/2)*2:-1,crop=832:480:(in_w-832)/2:(in_h-480)/2,"
            vf += "scale=1920:1080:flags=lanczos,cas=0.75"
            ok = subprocess.run(
                [FFMPEG, "-y", "-i", src, "-vf", vf, "-an", "-pix_fmt", "yuv420p",
                 "-c:v", "libx264", "-crf", "12", "-preset", "slow", conformes[p]],
                capture_output=True,
            ).returncode == 0
            log(f"  {'✅' if ok else '❌'} conform {p} (zoom {z:.4f})")
            if not ok:
                sys.exit(3)

        liste = os.path.join(OUTPUT_DIR, "concat_v3.txt")
        with open(liste, "w", encoding="utf-8") as f:
            for p in PLANS:
                f.write(f"file '{conformes[p].replace(os.sep, '/')}'\n")
        ok = subprocess.run(
            [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", liste,
             "-t", "10.0", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p",
             args.master],
            capture_output=True,
        ).returncode == 0
        log("✅ Master re-assembled: " + args.master if ok else "❌ assembly failed")
        if ok:
            diffs, pics = profil_saccades(args.master)
            log(f"📊 Profile: mean diff={diffs.mean():.2f} max={diffs.max():.2f} "
                f"jitter threshold≈{diffs.mean()*SEUIL_SACCADE:.2f}")
            for t, v in pics.items():
                verdict = "OK" if v < diffs.mean() * SEUIL_SACCADE else "RESIDUAL JITTER"
                log(f"   coupe t={t/24:.2f}s : diff={v:.2f} → {verdict}")


if __name__ == "__main__":
    main()
