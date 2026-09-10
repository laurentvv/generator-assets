#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/aligner_raccords_intro.py — chirurgie des raccords du chaînage I2V (2026-09-10)
Mesure par ECC (cv2) l'écart d'échelle/translation entre la dernière trame du plan N et
la trame de coupe du plan N+1 (après retrait du tête-à-queue), puis :
  • mode --mesurer : affiche les ratios par raccord ;
  • mode --appliquer : re-conforme les plans intérieurs avec zoom de compensation
    centré (l'échelle ramène la taille du château à l'identique à la coupe),
    ré-assemble le master et re-mesure le profil de saccades.
Le zoom compense uniquement ce que la coupe ne peut pas absorber ; il est borné (≤ 8 %).
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
TETE_COUPPEE = 12        # trames de tête retirées des plans intérieurs (cf. réparation)
ZOOM_MAX = 1.08          # garde-fou : au-delà, on signale plutôt qu'on zoome
SEUIL_SACCADE = 2.2      # pic de diff (× mouvement local) considéré comme saccade


def extraire_trame(video: str, index: int) -> np.ndarray:
    """Extrait une trame (0-based) en niveaux de gris, échelle de mesure 640 px."""
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
        raise RuntimeError(f"trame {index} illisible dans {video}")
    return img


def mesurer_raccord(fin_a: np.ndarray, debut_b: np.ndarray):
    """ECC affine A→B : renvoie (échelle du contenu de B relative à A, dx, dy)."""
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
    """Diff inter-trames du master ; renvoie la série et les pics aux raccords."""
    cmd = [FFMPEG, "-v", "error", "-i", video, "-vf", "scale=192:108",
           "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    f = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 108, 192).astype(np.float32)
    diffs = np.abs(np.diff(f, axis=0)).mean(axis=(1, 2))
    # positions des coupes : 65, 65+69, 65+69+69 trames (recul de 1 pour la diff)
    coupes = [65, 134, 203]
    pics = {t: float(diffs[t - 1]) for t in coupes if 0 < t - 1 < len(diffs)}
    return diffs, pics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mesurer", action="store_true", help="affiche les écarts par raccord")
    parser.add_argument("--appliquer", action="store_true",
                        help="re-conforme avec zoom de compensation et ré-assemble")
    parser.add_argument("--master", default=os.path.join(OUTPUT_DIR, "intro_vent_gris_10s_1080p_v3.mp4"))
    args = parser.parse_args()

    bruts = {p: os.path.join(OUTPUT_DIR, f"{p}_brut.webm") for p in PLANS}
    conformes = {p: os.path.join(OUTPUT_DIR, f"{p}_v3_1080p.mp4") for p in PLANS}
    zooms = {p: 1.0 for p in PLANS[1:]}

    if args.mesurer or args.appliquer:
        log("📏 Mesure ECC des raccords (fin plan N vs trame de coupe du plan N+1) :")
        for i, p in enumerate(PLANS[1:], start=1):
            nb_b = int(subprocess.run(
                ["C:/ffmpeg/dist/bin/ffprobe.exe", "-v", "error", "-select_streams", "v:0",
                 "-count_frames", "-show_entries", "stream=nb_read_frames",
                 "-of", "csv=p=0", bruts[p]], capture_output=True, text=True).stdout or 0)
            idx_b = min(TETE_COUPPEE, max(0, nb_b - 1))
            res = mesurer_raccord(extraire_trame(bruts[PLANS[i - 1]], 64),
                                  extraire_trame(bruts[p], idx_b))
            if res is None:
                log(f"  {p} : ECC non convergé — zoom 1,0 conservé")
                continue
            echelle, dx, dy = res
            # le contenu de B est 1/echelle fois celui de A (warp mappe A vers B) ;
            # pour ré-aligner, on zoome B par 1/echelle (borné)
            z = min(ZOOM_MAX, max(1.0, 1.0 / echelle))
            zooms[p] = z
            log(f"  {p} : échelle relative={echelle:.4f} → zoom compensation={z:.4f} "
                f"(dx={dx:.1f}px, dy={dy:.1f}px à l'échelle de mesure)")

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
        log("✅ Master ré-assemblé : " + args.master if ok else "❌ assemblage échoué")
        if ok:
            diffs, pics = profil_saccades(args.master)
            log(f"📊 Profil : diff moyenne={diffs.mean():.2f} max={diffs.max():.2f} "
                f"seuil saccade≈{diffs.mean()*SEUIL_SACCADE:.2f}")
            for t, v in pics.items():
                verdict = "OK" if v < diffs.mean() * SEUIL_SACCADE else "SACCADE RÉSIDUELLE"
                log(f"   coupe t={t/24:.2f}s : diff={v:.2f} → {verdict}")


if __name__ == "__main__":
    main()
