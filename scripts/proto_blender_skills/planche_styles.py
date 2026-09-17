"""Assemble la planche de contact des rendus de style (vague 3) — chemins relatifs au dépôt.

Usage : uv run python scripts/proto_blender_skills/planche_styles.py
"""

import os

from PIL import Image, ImageDraw

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(RACINE, "output", "test_blender_skills")

TUILES = [
    ("style_toon.png", "toon/cel"),
    ("style_psx.png", "PS1 + fog"),
    ("style_wear.png", "usure arêtes"),
    ("style_rust.png", "rouille"),
    ("style_moss.png", "mousse"),
    ("style_water.png", "taches d'eau"),
    ("style_panel.png", "variation panneaux"),
    ("cloth_drap.png", "cloth sim"),
    ("beauty_casque_composite.png", "beauty + composite"),
]
RES, MARGE, BANDEAU, COLS = 560, 10, 30, 3


def main():
    lignes = (len(TUILES) + COLS - 1) // COLS
    planche = Image.new("RGB", (COLS * (RES + MARGE) + MARGE,
                                lignes * (RES + BANDEAU + MARGE) + MARGE), (20, 20, 24))
    dessin = ImageDraw.Draw(planche)
    for i, (fichier, label) in enumerate(TUILES):
        chemin = os.path.join(OUT, fichier)
        if not os.path.exists(chemin):
            print(f"manquant : {fichier}")
            continue
        im = Image.open(chemin).convert("RGB")
        im.thumbnail((RES, RES))
        x = MARGE + (i % COLS) * (RES + MARGE)
        y = MARGE + (i // COLS) * (RES + BANDEAU + MARGE)
        dessin.text((x + 4, y + 8), f"{i + 1}. {label}", fill=(235, 235, 240))
        planche.paste(im, (x, y + BANDEAU))
    sortie = os.path.join(OUT, "planche_styles.png")
    planche.save(sortie)
    print(f"planche OK : {sortie}")


if __name__ == "__main__":
    main()
