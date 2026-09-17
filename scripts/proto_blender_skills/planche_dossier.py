"""Planche de contact générique : toutes les images d'un dossier en grille étiquetée.

Usage : uv run python scripts/proto_blender_skills/planche_dossier.py [dossier]
Défaut : output/test_blender_skills/multi/ (campagne multi-assets 2026-09-17).
"""

import os
import sys

from PIL import Image, ImageDraw

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DOSSIER = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RACINE, "output", "test_blender_skills", "multi")
RES, MARGE, BANDEAU, COLS = 460, 10, 26, 4


def main():
    pngs = sorted(f for f in os.listdir(DOSSIER) if f.endswith(".png") and not f.startswith("planche"))
    if not pngs:
        print(f"aucun PNG dans {DOSSIER}")
        sys.exit(1)
    lignes = (len(pngs) + COLS - 1) // COLS
    planche = Image.new("RGB", (COLS * (RES + MARGE) + MARGE,
                                lignes * (RES + BANDEAU + MARGE) + MARGE), (20, 20, 24))
    dessin = ImageDraw.Draw(planche)
    for i, fichier in enumerate(pngs):
        im = Image.open(os.path.join(DOSSIER, fichier)).convert("RGB")
        im.thumbnail((RES, RES))
        x = MARGE + (i % COLS) * (RES + MARGE)
        y = MARGE + (i // COLS) * (RES + BANDEAU + MARGE)
        label = os.path.splitext(fichier)[0].replace("_", " ")
        dessin.text((x + 4, y + 6), f"{i + 1}. {label}", fill=(235, 235, 240))
        planche.paste(im, (x, y + BANDEAU))
    sortie = os.path.join(DOSSIER, "planche_multi.png")
    planche.save(sortie)
    print(f"planche OK : {sortie} ({len(pngs)} tuiles)")


if __name__ == "__main__":
    main()
