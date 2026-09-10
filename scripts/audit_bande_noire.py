#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/audit_bande_noire.py — audit « bande noire basse » + raccord de boucle.

Critère de sortie du pipeline vidéo (incident 2026-09-10 : une barre noire
montante avait contaminé la boucle du menu — warp de stabilisation échantillonnant
hors cadre + remplissage noir). Ce script tourne sur TOUTE vidéo du pipeline.

Mesures :
  • bande noire basse : pour des instantanés à phases données (défaut
    0,5 / 2 / 3,5 / 5 / 6,5 / 8 s), hauteur en pixels du voile noir en bas de
    l'image — lignes dont la luminosité MOYENNE < seuil (8/255) en remontant
    depuis le bas ;
  • raccord de boucle (--raccord) : différence absolue moyenne (échelle L,
    0-255) entre la trame 0 et la dernière trame ; exigé ≤ ~6 pour une boucle
    sans couture.

Verdict par vidéo : ✅ 0 px partout (et raccord ≤ seuil si demandé) sinon ⛔.
Code de sortie global : 0 si tout passe, 1 sinon.

Usage :
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
    """Durée via ffprobe (indépendante de core/ pour un audit autonome)."""
    info = subprocess.run(
        [FFMPEG, "-i", chemin], capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    ).stderr
    import re
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", info)
    if not m:
        raise RuntimeError(f"Durée illisible : {chemin}")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def extraire_trame(video: str, t: float, png: str) -> None:
    subprocess.run(
        [FFMPEG, "-y", "-v", "error", "-ss", f"{max(0.0, t):.2f}", "-i", video,
         "-frames:v", "1", "-q:v", "1", png],
        capture_output=True, check=True,
    )
    if not os.path.exists(png):
        raise RuntimeError(f"Trame non extraite à t={t:.2f} s : {video}")


def bande_noire_bas(png: str, seuil: float = 8.0) -> int:
    """Hauteur (px) du voile noir en bas : lignes de luminosité moyenne < seuil
    en remontant depuis le bas. 0 = propre."""
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
    """Différence absolue moyenne (échelle L, 0-255) trame 0 vs dernière trame."""
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
        raise RuntimeError(f"Dimensions de raccord incohérentes : {a.shape} vs {b.shape}")
    return float(np.abs(a - b).mean())


def auditer_video(video: str, phases, seuil: float, raccord: bool, raccord_max: float):
    """Retourne (ok, rapport_multiligne)."""
    import numpy as np
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
            # garde-fou : une image entièrement noire donne hauteur = pleine hauteur
            largeur = Image.open(png).size[0]
            lignes_rapport.append(
                f"     t={t:5.2f} s : bande {px:4d} px{'  ⛔' if px > 0 else ''}"
                + (f"  (image {largeur}px de large)" if px > 0 else ""))
        ligne_raccord = None
        if raccord:
            diff = diff_raccord(video, tmp)
            conforme = diff <= raccord_max
            ok = ok and conforme
            ligne_raccord = (f"     raccord trame0↔fin : diff L {diff:.2f} "
                             f"(≤ {raccord_max}){'  ✅' if conforme else '  ⛔'}")
    entete = f"   {'✅' if ok else '⛔'} {os.path.basename(video)} ({duree:.2f} s)"
    corps = lignes_rapport + ([ligne_raccord] if ligne_raccord else [])
    if pire[0] > 0:
        corps.append(f"     pire bande : {pire[0]} px à t={pire[1]:.2f} s")
    return ok, entete + "\n" + "\n".join(corps)


def main():
    parseur = argparse.ArgumentParser(description="Audit bande noire + raccord de boucle")
    parseur.add_argument("--zero", nargs="+", action="extend", default=[], metavar="VIDEO",
                         help="vidéo(s) devant afficher 0 px de bande à toutes les phases (répétable)")
    parseur.add_argument("--raccord", nargs="+", action="extend", default=[], metavar="VIDEO",
                         help="vidéo(s) de boucle : 0 px ET raccord trame 0 vs fin ≤ --raccord-max (répétable)")
    parseur.add_argument("--phases", default="0.5,2,3.5,5,6.5,8",
                         help="instants d'échantillonnage en secondes (défaut: 0.5,2,3.5,5,6.5,8)")
    parseur.add_argument("--seuil", type=float, default=8.0,
                         help="luminosité moyenne d'une ligne considérée noire (défaut: 8/255)")
    parseur.add_argument("--raccord-max", type=float, default=6.0,
                         help="diff L moyenne max trame 0 vs fin (défaut: 6)")
    args = parseur.parse_args()

    if not args.zero:
        parseur.error("fournir au moins une vidéo via --zero")

    phases = [float(x) for x in args.phases.split(",") if x.strip()]
    tout_ok = True
    # dédoublonnage en conservant l'ordre (--zero puis --raccord)
    videos = list(dict.fromkeys(args.zero + args.raccord))
    if not videos:
        parseur.error("fournir au moins une vidéo via --zero ou --raccord")
    for video in videos:
        if not os.path.exists(video):
            print(f"   ⛔ {video} : FICHIER MANQUANT")
            tout_ok = False
            continue
        ok, rapport = auditer_video(video, phases, args.seuil,
                                    raccord=video in args.raccord,
                                    raccord_max=args.raccord_max)
        print(rapport)
        tout_ok = tout_ok and ok

    print("AUDIT BANDE NOIRE : " + ("✅ CONFORME" if tout_ok else "⛔ NON CONFORME"))
    sys.exit(0 if tout_ok else 1)


if __name__ == "__main__":
    main()
