#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rembg Workflow: high-resolution AI cutout for 2D assets (RMBG-1.4 / BiRefNet).
"""

import os
from pathlib import Path
from typing import Any, Dict
from PIL import Image

from core.config import DEFAULT_OUTPUT_DIR
from core.image_ops import centrer_et_recadrer
from core.segmentation import detourer_ia
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class RembgWorkflow(BaseWorkflow):
    """Pixel-perfect high-fidelity AI cutout for 2D assets."""

    name = "rembg"
    description = "High-precision AI cutout (RMBG-1.4 / BiRefNet) for 2D assets with no white fringe"

    emoji = "✂️"
    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        image_entree = params.get("image") or params.get("input")
        if not image_entree or not os.path.exists(image_entree):
            raise ValueError("The rembg workflow requires a valid input image (-i / --input).")

        nom_sortie = params.get("output") or f"{Path(image_entree).stem}_rembg"
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        model_path = params.get("segmenter_model")
        taille = params.get("size", 0)  # 0 = keep dimensions
        recadrer = params.get("recenter", True)

        os.makedirs(output_dir, exist_ok=True)
        chemin_sortie = os.path.join(output_dir, f"{nom_sortie}.png")

        self.log(f"AI cutout of the image: {image_entree}...")
        img_src = Image.open(image_entree)

        # Segmentation inference
        img_transparente = detourer_ia(img_src, model_path=model_path)

        # Framing
        if recadrer:
            dim = taille if (taille and taille > 0) else max(img_src.size)
            img_finale = centrer_et_recadrer(img_transparente, redimensionner=dim)
        elif taille and taille > 0:
            img_finale = img_transparente.resize((taille, taille), Image.Resampling.LANCZOS)
        else:
            img_finale = img_transparente

        img_finale.save(chemin_sortie, "PNG")
        self.log(f"Cut-out image saved: {chemin_sortie} ({img_finale.size[0]}x{img_finale.size[1]})", emoji="🎉")

        return {
            "output_file": chemin_sortie,
            "files": [chemin_sortie]
        }
