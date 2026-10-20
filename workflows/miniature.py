#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
miniature workflow: YouTube thumbnail with real typography via PhotoCraft.

Takes a keyframe (any sd-cli output), centers-crops it to the thumbnail
format (default 1280x720), composites a bottom gradient band for readability,
then adds the title (and optional subtitle) as real text layers through the
headless PhotoCraft engine - selectable size, color, tracking, centered
baseline anchor. Final export: JPEG quality 90 (YouTube-friendly size).
"""

import os
from pathlib import Path
from typing import Any, Dict

from PIL import Image, ImageDraw

from core.config import DEFAULT_OUTPUT_DIR
from core.photocraft import SessionPhotocraft
from workflows.base import BaseWorkflow, WorkflowRegistry


def _bande_degrade(largeur: int, hauteur: int, opacite: float, part: float = 0.42) -> Image.Image:
    """Bottom gradient band (transparent at its top edge, `opacite` at bottom)."""
    bande = Image.new("L", (1, hauteur), 0)
    depart = int(hauteur * (1.0 - part))
    for y in range(depart, hauteur):
        progression = (y - depart) / max(1, (hauteur - depart))
        bande.putpixel((0, y), int(255 * opacite * progression))
    bande = bande.resize((largeur, hauteur))
    voile = Image.new("RGBA", (largeur, hauteur), (8, 12, 20, 0))
    voile.putalpha(bande)
    return voile


@WorkflowRegistry.register
class MiniatureWorkflow(BaseWorkflow):
    """YouTube thumbnail: keyframe + gradient band + PhotoCraft typography."""

    name = "miniature"
    description = (
        "YouTube thumbnail via PhotoCraft headless: crop to 1280x720, bottom "
        "gradient band, title/subtitle text layers (size, color, tracking)"
    )

    emoji = "🖼️"
    PARAMETRES = [
        dict(flags=("--titre",), default=None, help="Title text displayed on the thumbnail"),
        dict(flags=("--sous-titre",), default=None, help="Optional subtitle under the title"),
        dict(flags=("--couleur-titre",), default="#ffe066", help="Title color (#rrggbb)"),
        dict(flags=("--couleur-sous-titre",), default="#ffffff", help="Subtitle color (#rrggbb)"),
        dict(flags=("--taille-titre",), type=int, default=88, help="Title size in pt"),
        dict(flags=("--taille-sous-titre",), type=int, default=34, help="Subtitle size in pt"),
        dict(flags=("--bandeau",), type=float, default=0.55,
             help="Bottom band max opacity 0..1 (0 = no band)"),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        image_entree = params.get("image") or params.get("input")
        if not image_entree or not os.path.exists(image_entree):
            raise ValueError("The miniature workflow requires a valid input image (-i / --input).")
        titre = params.get("titre")
        if not titre:
            raise ValueError("The miniature workflow requires --titre.")

        largeur = int(params.get("width") or 1280)
        hauteur = int(params.get("height") or 720)
        sous_titre = params.get("sous_titre")
        opacite_bande = max(0.0, min(1.0, float(params.get("bandeau", 0.55))))
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)

        base_sortie = Path(output_dir) / f"{Path(image_entree).stem}_miniature"

        # 1. Geometry + readability band (PIL): center-crop to the target
        #    aspect, resize, composite the gradient, save a lossless temp.
        source = Image.open(image_entree).convert("RGB")
        rapport_cible = largeur / hauteur
        rapport_source = source.width / source.height
        if rapport_source > rapport_cible:
            cote = int(source.height * rapport_cible)
            boite = ((source.width - cote) // 2, 0, (source.width + cote) // 2, source.height)
        else:
            cote = int(source.width / rapport_cible)
            boite = (0, (source.height - cote) // 2, source.width, (source.height + cote) // 2)
        toile = source.crop(boite).resize((largeur, hauteur), Image.Resampling.LANCZOS)
        if opacite_bande > 0:
            toile = Image.alpha_composite(
                toile.convert("RGBA"), _bande_degrade(largeur, hauteur, opacite_bande)
            )
        temporaire = base_sortie.with_suffix(".tmp.png")
        toile.convert("RGB").save(temporaire, "PNG")
        self.log(f"base composed ({largeur}x{hauteur}, band opacity {opacite_bande:.2f})")

        # 2. Typography (PhotoCraft headless): title + optional subtitle as
        #    real text layers on the temp image, saved back losslessly.
        taille_titre = int(params.get("taille_titre", 88))
        taille_sous = int(params.get("taille_sous_titre", 34))
        couleur_titre = params.get("couleur_titre", "#ffe066")
        couleur_sous = params.get("couleur_sous_titre", "#ffffff")
        with SessionPhotocraft(racine_lecture=Path(output_dir),
                               racine_ecriture=Path(output_dir)) as session:
            session.ouvrir_document(temporaire)
            if sous_titre:
                y_titre = int(hauteur * 0.80) - int(taille_sous * 1.6)
                session.ajouter_texte(titre, largeur // 2, y_titre, taille_titre,
                                      couleur_titre, "center", interlettrage=20)
                session.ajouter_texte(sous_titre, largeur // 2, int(hauteur * 0.90),
                                      taille_sous, couleur_sous, "center")
            else:
                session.ajouter_texte(titre, largeur // 2, int(hauteur * 0.84), taille_titre,
                                      couleur_titre, "center", interlettrage=20)
            session.enregistrer(temporaire)

        # 3. Final YouTube-friendly JPEG.
        chemin_sortie = base_sortie.with_suffix(".jpg")
        finale = Image.open(temporaire).convert("RGB")
        finale.save(chemin_sortie, "JPEG", quality=90, optimize=True)
        temporaire.unlink(missing_ok=True)
        taille_ko = chemin_sortie.stat().st_size / 1024
        self.log(f"thumbnail saved: {chemin_sortie} "
                 f"({finale.size[0]}x{finale.size[1]}, {taille_ko:.0f} KB)", emoji="🎉")

        return {"output_file": str(chemin_sortie), "files": [str(chemin_sortie)]}
