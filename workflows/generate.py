#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Standard : Génération d'asset 2D unitaire pour Godot.
LLM (enrichissement) -> Flux.1 (Vulkan + LoRAs) -> Détourage Floodfill -> Centrage -> Export PNG.
"""

import os
from pathlib import Path
from typing import Any, Dict
from PIL import Image

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.diffusion import generer_image_vulkan
from core.image_ops import post_process_asset
from core.llm import construire_prompt_coherant
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class GenerateWorkflow(BaseWorkflow):
    name = "generate"
    description = "Génération d'un asset 2D isolé (LLM -> Diffusion -> Détourage -> Centrage Godot)"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        concept = params.get("prompt")
        if not concept:
            raise ValueError("Le paramètre 'prompt' est requis pour le workflow generate.")

        type_asset = params.get("type", "item")
        nom_sortie = params.get("output") or slugifier_texte(concept)
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        taille_sprite = params.get("size", 512)
        sans_llm = params.get("no_llm", False)
        tolerance = params.get("tolerance", 60)
        steps = params.get("steps", 25)
        guidance = params.get("guidance", 3.5)
        cfg_scale = params.get("cfg_scale", 1.0)
        seed = params.get("seed", -1)
        loras = params.get("loras")
        lora_dir = params.get("lora_dir") or self.config.get("lora_dir")

        os.makedirs(output_dir, exist_ok=True)

        # 1. Étape LLM
        if sans_llm:
            self.log("Mode direct : prompt brut sans LLM.")
            prompt_complet = f"{concept}, {self.config.get('style_anchor')}"
        else:
            self.log(f"Direction artistique pour '{concept}'...")
            prompt_complet = construire_prompt_coherant(
                concept=concept,
                type_asset=type_asset,
                llama_cli=self.config.get("llama_cli"),
                llm_model=self.config.get("llm_model"),
                style_anchor=self.config.get("style_anchor")
            )

        # 2. Étape Diffusion (Flux.1 + LoRAs)
        self.log(f"Rendu de diffusion Vulkan ({steps} étapes, guidance={guidance})...")
        img_brute = generer_image_vulkan(
            prompt=prompt_complet,
            sd_cli=self.config.get("sd_cli"),
            sd_model=self.config.get("sd_model"),
            clip_l=self.config.get("clip_l"),
            t5xxl=self.config.get("t5xxl"),
            vae=self.config.get("vae"),
            backend=self.config.get("backend"),
            threads=self.config.get("threads"),
            steps=steps,
            guidance=guidance,
            cfg_scale=cfg_scale,
            seed=seed,
            loras=loras,
            lora_dir=lora_dir
        )

        # 3. Post-Processing
        self.log("Détourage du fond blanc et centrage carré...")
        img_finale = post_process_asset(
            image=img_brute,
            tolerance=tolerance,
            redimensionner=taille_sprite
        )

        chemin_fichier = os.path.join(output_dir, f"{Path(nom_sortie).stem}.png")
        img_finale.save(chemin_fichier, "PNG")
        self.log(f"Asset exporté avec succès : {chemin_fichier}", emoji="✅")

        return {
            "output_path": chemin_fichier,
            "image": img_finale,
            "prompt_used": prompt_complet,
            "dimensions": img_finale.size
        }
