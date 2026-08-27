#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow rembg : Détourage IA haute résolution pour assets 2D (RMBG-1.4 / BiRefNet).
"""

import os
from pathlib import Path
from typing import Any, Dict
from PIL import Image

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.image_ops import centrer_et_recadrer
from core.segmentation import detourer_ia
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class RembgWorkflow(BaseWorkflow):
    """Détourage IA haute fidélité au pixel près pour assets 2D."""

    name = "rembg"
    description = "Détourage IA haute précision (RMBG-1.4 / BiRefNet) pour assets 2D sans frange blanche"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        image_entree = params.get("image") or params.get("input")
        if not image_entree or not os.path.exists(image_entree):
            raise ValueError("Le workflow rembg nécessite une image d'entrée valide (-i / --input).")

        nom_sortie = params.get("output") or f"{Path(image_entree).stem}_rembg"
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        model_path = params.get("segmenter_model")
        taille = params.get("size", 0)  # 0 = conserver dimensions
        recadrer = params.get("recenter", True)

        os.makedirs(output_dir, exist_ok=True)
        chemin_sortie = os.path.join(output_dir, f"{nom_sortie}.png")

        self.log(f"Détourage IA de l'image : {image_entree}...")
        img_src = Image.open(image_entree)

        # Inférence de segmentation
        img_transparente = detourer_ia(img_src, model_path=model_path)

        # Cadrage
        if recadrer:
            dim = taille if (taille and taille > 0) else max(img_src.size)
            img_finale = centrer_et_recadrer(img_transparente, redimensionner=dim)
        elif taille and taille > 0:
            img_finale = img_transparente.resize((taille, taille), Image.Resampling.LANCZOS)
        else:
            img_finale = img_transparente

        img_finale.save(chemin_sortie, "PNG")
        self.log(f"Image détourée enregistrée : {chemin_sortie} ({img_finale.size[0]}x{img_finale.size[1]})", emoji="🎉")

        return {
            "output_file": chemin_sortie,
            "files": [chemin_sortie]
        }
