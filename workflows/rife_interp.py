#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow RIFE Interp : Augmentation de la fluidité des animations 2D (60 FPS) via RIFE v4 ONNX.
"""

import os
from pathlib import Path
from typing import Any, Dict, List
from PIL import Image

from core.config import DEFAULT_OUTPUT_DIR
from core.interpolation import interpoler_sequence
from workflows.base import BaseWorkflow, WorkflowRegistry


def decouper_spritesheet_horizontal(image: Image.Image, nb_frames: int) -> List[Image.Image]:
    """Découpe une planche de sprites linéaire horizontale en liste d'images."""
    w, h = image.size
    frame_w = w // nb_frames
    frames = []
    for i in range(nb_frames):
        cadre = image.crop((i * frame_w, 0, (i + 1) * frame_w, h))
        frames.append(cadre)
    return frames


def assembler_spritesheet_horizontal(frames: List[Image.Image]) -> Image.Image:
    """Réassemble une liste de trames en une seule planche de sprites linéaire."""
    if not frames:
        return Image.new("RGBA", (1, 1))
    fw, fh = frames[0].size
    nb = len(frames)
    sheet = Image.new("RGBA", (fw * nb, fh), (0, 0, 0, 0))
    for idx, f in enumerate(frames):
        sheet.paste(f, (idx * fw, 0))
    return sheet


@WorkflowRegistry.register
class RifeInterpWorkflow(BaseWorkflow):
    """Workflow d'interpolation de trames IA pour fluidifier les spritesheets (60 FPS)."""

    name = "rife_interp"
    description = "Super-fluidité d'animation IA (RIFE v4 ONNX) : multiplie le nombre de trames (2x, 4x, 60 FPS)"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        input_image = params.get("input")
        if not input_image or not os.path.exists(input_image):
            raise ValueError("Le workflow rife_interp nécessite une spritesheet d'entrée valide (-i / --input).")

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        facteur = int(params.get("factor", 2))
        nb_colonnes = int(params.get("columns", 4))
        nom_base = params.get("output") or f"{Path(input_image).stem}_rife_{facteur}x"

        os.makedirs(output_dir, exist_ok=True)
        chemin_sortie = os.path.join(output_dir, f"{nom_base}.png")

        self.log(f"Chargement de la spritesheet source : {input_image} ({nb_colonnes} trames)...")
        img_src = Image.open(input_image).convert("RGBA")

        trames_initiales = decouper_spritesheet_horizontal(img_src, nb_colonnes)
        self.log(f"Découpage en {len(trames_initiales)} trames de {trames_initiales[0].size[0]}x{trames_initiales[0].size[1]}px.")

        self.log(f"Interpolation neuronale RIFE v4 (Facteur {facteur}x)...")
        trames_fluides = interpoler_sequence(trames_initiales, facteur=facteur, boucler=False)

        self.log(f"Nombre total de trames après interpolation : {len(trames_fluides)}")
        sheet_finale = assembler_spritesheet_horizontal(trames_fluides)
        sheet_finale.save(chemin_sortie, "PNG")

        self.log(f"Spritesheet ultra-fluide enregistrée dans '{output_dir}/' :", emoji="🎉")
        self.log(f"  • Spritesheet {facteur}x : {chemin_sortie} ({len(trames_fluides)} trames)", emoji="💎")

        return {
            "output_file": chemin_sortie,
            "frame_count": len(trames_fluides),
            "files": [chemin_sortie]
        }
