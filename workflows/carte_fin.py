#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
carte_fin workflow: YouTube end card / subscribe screen via PhotoCraft.

Builds a channel end card (default 1280x720): background image (optional,
recentered like the miniature workflow) or solid color, dark veil for
readability, then centered call-to-action typography through the headless
PhotoCraft engine. Final export: JPEG quality 90.
"""

import os
from pathlib import Path
from typing import Any, Dict

from PIL import Image

from core.config import DEFAULT_OUTPUT_DIR
from core.photocraft import SessionPhotocraft
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class CarteFinWorkflow(BaseWorkflow):
    """YouTube end card / subscribe screen (PhotoCraft headless typography)."""

    name = "carte_fin"
    description = (
        "YouTube end card via PhotoCraft headless: background image or color, "
        "dark veil, centered CTA typography (texte principal / secondaire)"
    )

    emoji = "📡"
    PARAMETRES = [
        dict(flags=("--fond",), default=None,
             help="Background image path (recentered); default solid #10131c"),
        dict(flags=("--texte-principal",), default="ABONNE-TOI",
             help="Main call-to-action text"),
        dict(flags=("--texte-secondaire",), default=None,
             help="Secondary line (channel name, tease…)"),
        dict(flags=("--couleur-principal",), default="#7fdcff", help="CTA color (#rrggbb)"),
        dict(flags=("--couleur-secondaire",), default="#ffffff", help="Secondary text color"),
        dict(flags=("--taille-principal",), type=int, default=120, help="CTA size in pt"),
        dict(flags=("--taille-secondaire",), type=int, default=40, help="Secondary size in pt"),
        dict(flags=("--voile",), type=float, default=0.45,
             help="Dark veil opacity over a background image (0..1)"),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        largeur = int(params.get("width") or 1280)
        hauteur = int(params.get("height") or 720)
        fond = params.get("fond")
        voile = max(0.0, min(1.0, float(params.get("voile", 0.45))))
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)
        nom_base = Path(fond).stem + "_carte_fin" if fond else "carte_fin"
        base_sortie = Path(output_dir) / nom_base

        # 1. Background (PIL): image recentered to the target frame, or solid.
        if fond:
            if not os.path.exists(fond):
                raise ValueError(f"--fond image not found: {fond}")
            source = Image.open(fond).convert("RGB")
            cible = largeur / hauteur
            if source.width / source.height > cible:
                cote = int(source.height * cible)
                boite = ((source.width - cote) // 2, 0, (source.width + cote) // 2, source.height)
            else:
                cote = int(source.width / cible)
                boite = (0, (source.height - cote) // 2, source.width, (source.height + cote) // 2)
            toile = source.crop(boite).resize((largeur, hauteur), Image.Resampling.LANCZOS)
            if voile > 0:
                voile_img = Image.new("RGBA", (largeur, hauteur), (6, 9, 16, int(255 * voile)))
                toile = Image.alpha_composite(toile.convert("RGBA"), voile_img)
            toile = toile.convert("RGB")
        else:
            toile = Image.new("RGB", (largeur, hauteur), "#10131c")
        temporaire = base_sortie.with_suffix(".tmp.png")
        toile.save(temporaire, "PNG")
        self.log(f"background composed ({largeur}x{hauteur}, "
                 f"{'image + veil ' + format(voile, '.2f') if fond else 'solid color'})")

        # 2. Centered CTA typography (PhotoCraft headless).
        principal = params.get("texte_principal", "ABONNE-TOI")
        secondaire = params.get("texte_secondaire")
        taille_p = int(params.get("taille_principal", 120))
        taille_s = int(params.get("taille_secondaire", 40))
        couleur_p = params.get("couleur_principal", "#7fdcff")
        couleur_s = params.get("couleur_secondaire", "#ffffff")
        with SessionPhotocraft(racine_lecture=Path(output_dir),
                               racine_ecriture=Path(output_dir)) as session:
            session.ouvrir_document(temporaire)
            if secondaire:
                session.ajouter_texte(principal, largeur // 2, int(hauteur * 0.52), taille_p,
                                      couleur_p, "center", interlettrage=80)
                session.ajouter_texte(secondaire, largeur // 2, int(hauteur * 0.68), taille_s,
                                      couleur_s, "center")
            else:
                session.ajouter_texte(principal, largeur // 2, int(hauteur * 0.55), taille_p,
                                      couleur_p, "center", interlettrage=80)
            session.enregistrer(temporaire)

        chemin_sortie = base_sortie.with_suffix(".jpg")
        finale = Image.open(temporaire).convert("RGB")
        finale.save(chemin_sortie, "JPEG", quality=90, optimize=True)
        temporaire.unlink(missing_ok=True)
        self.log(f"end card saved: {chemin_sortie} "
                 f"({finale.size[0]}x{finale.size[1]}, "
                 f"{chemin_sortie.stat().st_size / 1024:.0f} KB)", emoji="🎉")

        return {"output_file": str(chemin_sortie), "files": [str(chemin_sortie)]}
