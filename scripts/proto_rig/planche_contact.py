"""Planche de contact PIL : assemble des captures PNG en grille avec libellés.

Usage :
    uv run python scripts/proto_rig/planche_contact.py "output/test_rig/captures/*_phase1_*.png" output/test_rig/planche_phase1.png
"""

from __future__ import annotations

import argparse
import glob as globlib
import os

from PIL import Image, ImageDraw


def construire(motifs: list[str], sortie: str, par_ligne: int = 4, largeur_cell: int = 380) -> None:
    chemins: list[str] = []
    for motif in motifs:
        chemins.extend(sorted(globlib.glob(motif)))
    if not chemins:
        raise SystemExit(f"aucune capture pour {motifs}")
    # regroupe par sujet (prefixe commun avant la vue) -> lignes
    def sujet(chemin: str) -> str:
        return os.path.basename(chemin).rsplit("_", 1)[0]

    lignes: dict[str, list[str]] = {}
    for chemin in chemins:
        lignes.setdefault(sujet(chemin), []).append(chemin)

    police_h = 26
    cellules = []
    for nom, groupes in lignes.items():
        for chemin in groupes:
            img = Image.open(chemin)
            rapport = largeur_cell / img.width
            img = img.resize((largeur_cell, max(1, int(img.height * rapport))))
            cellules.append((nom, os.path.basename(chemin).rsplit("_", 1)[-1].replace(".png", ""), img))

    hauteur_cell = max(img.height for _, _, img in cellules) + police_h
    n_lignes = (len(cellules) + par_ligne - 1) // par_ligne
    planche = Image.new("RGB", (par_ligne * largeur_cell, n_lignes * hauteur_cell), (24, 24, 28))
    dessin = ImageDraw.Draw(planche)
    for i, (sujet_nom, vue, img) in enumerate(cellules):
        x = (i % par_ligne) * largeur_cell
        y = (i // par_ligne) * hauteur_cell
        planche.paste(img, (x, y + police_h))
        dessin.text((x + 6, y + 4), f"{sujet_nom} [{vue}]", fill=(235, 235, 240))
    os.makedirs(os.path.dirname(sortie) or ".", exist_ok=True)
    planche.save(sortie)
    print(f"PLANCHE:{os.path.abspath(sortie)} cellules={len(cellules)}")


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("motifs", nargs="+", help="glob(s) des captures")
    parseur.add_argument("sortie", help="fichier PNG de sortie")
    parseur.add_argument("--par-ligne", type=int, default=4)
    parseur.add_argument("--largeur", type=int, default=380)
    args = parseur.parse_args()
    construire(args.motifs, args.sortie, args.par_ligne, args.largeur)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
