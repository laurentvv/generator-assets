#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/audit_bande_noire.py — "bottom black band" audit + loop joint.

Exit criterion of the video pipeline (2026-09-10 incident: a rising black bar
had contaminated the menu loop — stabilization warp sampling
out of frame + black fill). This script runs on ANY video of the pipeline.

Measurements:
  • bottom black band: for snapshots at given phases (default
    0.5 / 2 / 3.5 / 5 / 6.5 / 8 s), height in pixels of the black veil at the
    bottom of the image — lines whose MEAN brightness < threshold (8/255) going up
    from the bottom;
  • loop joint (--raccord): mean absolute difference (L scale,
    0-255) between frame 0 and the last frame; required ≤ ~6 for a
    seamless loop.

Verdict per video: ✅ 0 px everywhere (and joint ≤ threshold if requested) otherwise ⛔.
Global exit code: 0 if everything passes, 1 otherwise.

Usage:
  uv run python scripts/audit_bande_noire.py --zero video1.mp4 video2.mp4 \
      --zero --raccord boucle.mp4 [--phases 0.5,2,3.5,5,6.5,8] [--seuil 8] [--raccord-max 6]
"""

import argparse
import os
import subprocess
import sys
import tempfile

FFMPEG = os.environ.get("FFMPEG_PATH", "ffmpeg")


def duree_media(chemin: str) -> float:
    """Duration via ffprobe (independent of core/ for a standalone audit)."""
    info = subprocess.run(
        [FFMPEG, "-i", chemin], capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    ).stderr
    import re
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", info)
    if not m:
        raise RuntimeError(f"Unreadable duration: {chemin}")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def extraire_trame(video: str, t: float, png: str) -> None:
    subprocess.run(
        [FFMPEG, "-y", "-v", "error", "-ss", f"{max(0.0, t):.2f}", "-i", video,
         "-frames:v", "1", "-q:v", "1", png],
        capture_output=True, check=True,
    )
    if not os.path.exists(png):
        raise RuntimeError(f"Frame not extracted at t={t:.2f} s: {video}")


def bande_noire_bas(png: str, seuil: float = 8.0) -> int:
    """Height (px) of the black veil at the bottom: lines of mean brightness < threshold
    going up from the bottom. 0 = clean."""
    import numpy as np
    from PIL import Image

    lignes = np.asarray(Image.open(png).convert("L"), dtype=np.float64).mean(axis=1)
    hauteur = 0
    for moyenne in lignes[::-1]:
        if moyenne < seuil:
            hauteur += 1
        else:
            break
    return hauteur


def diff_raccord(video: str, tmp: str) -> float:
    """Mean absolute difference (L scale, 0-255) frame 0 vs last frame."""
    import numpy as np
    from PIL import Image

    duree = duree_media(video)
    debut = os.path.join(tmp, "rac_debut.png")
    fin = os.path.join(tmp, "rac_fin.png")
    extraire_trame(video, 0.0, debut)
    extraire_trame(video, duree - 0.08, fin)
    a = np.asarray(Image.open(debut).convert("L"), dtype=np.float64)
    b = np.asarray(Image.open(fin).convert("L"), dtype=np.float64)
    if a.shape != b.shape:
        raise RuntimeError(f"Inconsistent joint dimensions: {a.shape} vs {b.shape}")
    return float(np.abs(a - b).mean())


def auditer_video(video: str, phases, seuil: float, raccord: bool, raccord_max: float):
    """Returns (ok, multiline_report)."""
    from PIL import Image

    lignes_rapport = []
    ok = True
    duree = duree_media(video)
    pire = (0, None)
    with tempfile.TemporaryDirectory(prefix="audit_bande_") as tmp:
        for t in phases:
            t = min(t, duree - 0.2)
            png = os.path.join(tmp, f"phase_{t:.2f}s.png")
            extraire_trame(video, t, png)
            px = bande_noire_bas(png, seuil)
            if px > pire[0]:
                pire = (px, t)
            if px > 0:
                ok = False
            # safeguard: a fully black image gives height = full height
            largeur = Image.open(png).size[0]
            lignes_rapport.append(
                f"     t={t:5.2f} s : band {px:4d} px{'  ⛔' if px > 0 else ''}"
                + (f"  (image {largeur}px wide)" if px > 0 else ""))
        ligne_raccord = None
        if raccord:
            diff = diff_raccord(video, tmp)
            conforme = diff <= raccord_max
            ok = ok and conforme
            ligne_raccord = (f"     frame0↔end joint: L diff {diff:.2f} "
                             f"(≤ {raccord_max}){'  ✅' if conforme else '  ⛔'}")
    entete = f"   {'✅' if ok else '⛔'} {os.path.basename(video)} ({duree:.2f} s)"
    corps = lignes_rapport + ([ligne_raccord] if ligne_raccord else [])
    if pire[0] > 0:
        corps.append(f"     worst band: {pire[0]} px at t={pire[1]:.2f} s")
    return ok, entete + "\n" + "\n".join(corps)


def main():
    parseur = argparse.ArgumentParser(description="Black band + loop joint audit")
    parseur.add_argument("--zero", nargs="+", action="extend", default=[], metavar="VIDEO",
                         help="video(s) required to show 0 px of band at all phases (repeatable)")
    parseur.add_argument("--raccord", nargs="+", action="extend", default=[], metavar="VIDEO",
                         help="loop video(s): 0 px AND frame 0 vs end joint ≤ --raccord-max (repeatable)")
    parseur.add_argument("--phases", default="0.5,2,3.5,5,6.5,8",
                         help="sampling instants in seconds (default: 0.5,2,3.5,5,6.5,8)")
    parseur.add_argument("--seuil", type=float, default=8.0,
                         help="mean brightness of a line considered black (default: 8/255)")
    parseur.add_argument("--raccord-max", type=float, default=6.0,
                         help="max mean L diff frame 0 vs end (default: 6)")
    args = parseur.parse_args()

    if not args.zero:
        parseur.error("provide at least one video via --zero")

    phases = [float(x) for x in args.phases.split(",") if x.strip()]
    tout_ok = True
    # deduplication keeping the order (--zero then --raccord)
    videos = list(dict.fromkeys(args.zero + args.raccord))
    if not videos:
        parseur.error("provide at least one video via --zero or --raccord")
    for video in videos:
        if not os.path.exists(video):
            print(f"   ⛔ {video} : MISSING FILE")
            tout_ok = False
            continue
        ok, rapport = auditer_video(video, phases, args.seuil,
                                    raccord=video in args.raccord,
                                    raccord_max=args.raccord_max)
        print(rapport)
        tout_ok = tout_ok and ok

    print("BLACK BAND AUDIT: " + ("✅ CONFORMING" if tout_ok else "⛔ NON-CONFORMING"))
    sys.exit(0 if tout_ok else 1)


if __name__ == "__main__":
    main()
