#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
filigrane_batch workflow: batch watermark + format conversion via PhotoCraft.

Applies a corner text watermark to one image or every image of a directory
and exports to the requested format, optionally resampling the long side —
all through the headless PhotoCraft engine (real typography, alpha-aware
color #rrggbbaa). Nothing is written in place: results land in the output
directory.
"""

import os
from pathlib import Path
from typing import Any, Dict

from PIL import Image

from core.config import DEFAULT_OUTPUT_DIR
from core.photocraft import SessionPhotocraft
from workflows.base import BaseWorkflow, WorkflowRegistry

_POSITIONS = {
    "bas-droite": lambda w, h, bb: (int(w - bb["right"]), int(h - bb["bottom"])),
    "bas-gauche": lambda w, h, bb: (int(bb["left"]), int(h - bb["bottom"])),
    "haut-droite": lambda w, h, bb: (int(w - bb["right"]), int(bb["top"])),
    "haut-gauche": lambda w, h, bb: (int(bb["left"]), int(bb["top"])),
}


@WorkflowRegistry.register
class FiligraneBatchWorkflow(BaseWorkflow):
    """Corner text watermark + format conversion, batch (PhotoCraft headless)."""

    name = "filigrane_batch"
    description = (
        "Batch watermark via PhotoCraft headless: corner text layer (#rrggbb or "
        "#rrggbbaa), format conversion, optional long-side resample — file or directory"
    )

    emoji = "🏷️"
    PARAMETRES = [
        dict(flags=("--filigrane",), default="@ ai-doc2video",
             help="Watermark text"),
        dict(flags=("--position",), default="bas-droite",
             choices=sorted(_POSITIONS), help="Watermark corner"),
        dict(flags=("--couleur-filigrane",), default="#ffffffb0",
             help="Watermark color, #rrggbb or #rrggbb+alpha"),
        dict(flags=("--taille-filigrane",), type=int, default=28, help="Watermark size in pt"),
        dict(flags=("--marge",), type=int, default=24, help="Corner margin in px"),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        entree = params.get("image") or params.get("input")
        if not entree or not os.path.exists(entree):
            raise ValueError(
                "The filigrane_batch workflow requires a valid input image or directory "
                "(-i / --input)."
            )
        texte = params.get("filigrane", "@ ai-doc2video")
        position = params.get("position", "bas-droite")
        couleur = params.get("couleur_filigrane", "#ffffffb0")
        taille = int(params.get("taille_filigrane", 28))
        marge = int(params.get("marge", 24))
        format_sortie = params.get("format_sortie", "jpg")
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)

        long_cote = None
        if params.get("width") and params.get("height"):
            raise ValueError("filigrane_batch: at most one of --width/--height (long side)")
        if params.get("width"):
            long_cote = int(params["width"])
        elif params.get("height"):
            long_cote = int(params["height"])

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
                w, h = source.size
                cible = (long_cote, max(2, round(long_cote * h / w))) if (long_cote and w >= h) \
                    else (max(2, round(long_cote * w / h)), long_cote) if long_cote else (w, h)
                # Anchor computed on the TARGET frame (post-resample): the engine
                # anchors point text at the baseline, so bottom corners offset the
                # margin by one line; right corners anchor the aligned text's end.
                largeur_texte = int(len(texte) * taille * 0.55)
                boite = {
                    "left": marge, "right": marge + largeur_texte,
                    "top": marge, "bottom": marge + int(taille * 1.3),
                }
                x, y = _POSITIONS[position](cible[0], cible[1], boite)
                session.ouvrir_document(image)
                etapes = []
                if (cible[0], cible[1]) != (w, h):
                    etapes.append({
                        "command": "image.crop",
                        "params": {"x": 0, "y": 0, "width": w, "height": h,
                                   "targetWidth": cible[0], "targetHeight": cible[1],
                                   "resample": "lanczos"},
                    })
                etapes.append({
                    "command": "type.create",
                    "params": {"x": x, "y": y, "text": texte, "size": taille,
                               "color": couleur,
                               "align": "left" if "gauche" in position else "right"},
                })
                session.lot(etapes)
                chemin_sortie = Path(output_dir) / f"{image.stem}_filigrane.{format_sortie}"
                session.enregistrer(chemin_sortie)
                fichiers_sortie.append(str(chemin_sortie))
                self.log(f"{image.name} -> {chemin_sortie.name} ({cible[0]}x{cible[1]})")

        self.log(f"{len(fichiers_sortie)} image(s) watermarked", emoji="🎉")
        return {"output_file": fichiers_sortie[0] if fichiers_sortie else None,
                "files": fichiers_sortie}
