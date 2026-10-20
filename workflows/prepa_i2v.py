#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prepa_i2v workflow: prepare keyframes for image-to-video pipelines.

Normalizes one image (or every image of a directory) before feeding Wan/LTX
style I2V chains: centered crop to the target aspect ratio, optional resample
to an exact resolution, headless export through the PhotoCraft engine
(lanczos). Keeps the long side of the source when no explicit size is given
(no invented upscaling).
"""

import os
from pathlib import Path
from typing import Any, Dict

from PIL import Image

from core.config import DEFAULT_OUTPUT_DIR
from core.photocraft import SessionPhotocraft
from workflows.base import BaseWorkflow, WorkflowRegistry

_RATIOS = {
    "16:9": (16, 9),
    "9:16": (9, 16),
    "1:1": (1, 1),
    "4:3": (4, 3),
    "3:4": (3, 4),
    "21:9": (21, 9),
}


def _dimensions_cibles(ratio: str, source: Image.Image, cote_long: int | None):
    """Target (w, h) for the requested aspect, long side `cote_long` (or source's)."""
    if ratio not in _RATIOS:
        raise ValueError(f"unknown ratio '{ratio}' (expected one of {sorted(_RATIOS)})")
    rw, rh = _RATIOS[ratio]
    longueur = cote_long or max(source.size)
    if rw >= rh:
        return longueur, max(2, round(longueur * rh / rw))
    return max(2, round(longueur * rw / rh)), longueur


@WorkflowRegistry.register
class PrepaI2VWorkflow(BaseWorkflow):
    """Center-crop / resample keyframes for I2V pipelines (PhotoCraft headless)."""

    name = "prepa_i2v"
    description = (
        "I2V keyframe preparation via PhotoCraft headless: centered crop to a "
        "target ratio (16:9, 9:16, 1:1, 4:3, 3:4, 21:9), optional exact size "
        "(--width/--height as long side), lanczos resample"
    )

    emoji = "🎬"
    PARAMETRES = [
        dict(flags=("--ratio",), default="16:9",
             choices=sorted(_RATIOS), help="Target aspect ratio"),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        entree = params.get("image") or params.get("input")
        if not entree or not os.path.exists(entree):
            raise ValueError(
                "The prepa_i2v workflow requires a valid input image or directory (-i / --input)."
            )
        ratio = params.get("ratio", "16:9")
        format_sortie = params.get("format_sortie", "png")
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)

        cote_long = None
        if params.get("width") and params.get("height"):
            raise ValueError(
                "prepa_i2v: give at most one of --width/--height (the long side), not both"
            )
        if params.get("width"):
            cote_long = int(params["width"])
        elif params.get("height"):
            cote_long = int(params["height"])

        chemin_entree = Path(entree)
        images = (
            sorted(p for p in chemin_entree.iterdir()
                   if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})
            if chemin_entree.is_dir() else [chemin_entree]
        )
        if not images:
            raise ValueError(f"no image found in {chemin_entree}")

        fichiers_sortie: list[str] = []
        with SessionPhotocraft(racine_lecture=images[0].parent if len(images) == 1 else chemin_entree,
                               racine_ecriture=Path(output_dir)) as session:
            for image in images:
                source = Image.open(image)
                cible_w, cible_h = _dimensions_cibles(ratio, source, cote_long)
                # Centered crop rectangle in source pixels, covering the ratio.
                rapport_cible = cible_w / cible_h
                if source.width / source.height > rapport_cible:
                    hauteur_boite = source.height
                    largeur_boite = round(hauteur_boite * rapport_cible)
                else:
                    largeur_boite = source.width
                    hauteur_boite = round(largeur_boite / rapport_cible)
                x = (source.width - largeur_boite) // 2
                y = (source.height - hauteur_boite) // 2
                session.ouvrir_document(image)
                session.recadrer(x, y, largeur_boite, hauteur_boite, cible_w, cible_h)
                chemin_sortie = Path(output_dir) / f"{image.stem}_i2v.{format_sortie}"
                session.enregistrer(chemin_sortie)
                fichiers_sortie.append(str(chemin_sortie))
                self.log(f"{image.name} -> {chemin_sortie.name} ({cible_w}x{cible_h})")

        self.log(f"{len(fichiers_sortie)} keyframe(s) prepared for I2V", emoji="🎉")
        return {"output_file": fichiers_sortie[0] if fichiers_sortie else None,
                "files": fichiers_sortie}
