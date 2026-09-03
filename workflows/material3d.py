#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Material 3D (PBR) : Génération complète de pack de textures PBR pour Godot 3D.
Produit :
- Albedo (Texture de couleur)
- Normal Map (Format tangent OpenGL)
- Roughness Map (Micro-rugosité)
- Height Map (Déplacement / Relief)
- Ambient Occlusion (AO)
- ORM Pack (Occlusion R, Roughness G, Metallic B)
- Fichier ressource Godot 4 StandardMaterial3D (.tres)
- Aperçu de tuilage 3x3
"""

import os
from pathlib import Path
from typing import Any, Dict
from PIL import Image

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.diffusion import generer_image_vulkan
from core.image_ops import (
    creer_apercu_tuilage,
    exporter_fichier_materiau_godot,
    generer_ao_map,
    generer_height_map,
    generer_normal_map,
    generer_orm_pack,
    generer_roughness_map
)
from core.llm import construire_prompt_coherant
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class Material3DWorkflow(BaseWorkflow):
    name = "material3d"
    description = "Pack Matériau 3D PBR complet (Albedo, Normal, Roughness, Height, AO, ORM + .tres Godot)"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        concept = params.get("prompt")
        input_image = params.get("input")

        if not concept and not input_image:
            raise ValueError("Le paramètre 'prompt' ou 'input' (texture existante) est requis pour material3d.")

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        taille = params.get("size", 1024) or 1024
        strength_normal = float(params.get("normal_strength", 3.5))

        os.makedirs(output_dir, exist_ok=True)

        if input_image and os.path.exists(input_image):
            self.log(f"Chargement de la texture source : {input_image}...")
            img_albedo = Image.open(input_image).convert("RGB")
            nom_base = params.get("output") or f"{Path(input_image).stem}_pbr"
        else:
            self.log(f"Génération d'une texture PBR pour '{concept}'...")
            nom_base = params.get("output") or slugifier_texte(concept)

            style_pbr = (
                "photorealistic 3D PBR material texture, seamless tileable surface, top-down flat lighting, "
                "no directional shadows, ultra detailed physical material, 8k texture scan quality"
            )

            prompt_complet = construire_prompt_coherant(
                concept=concept,
                type_asset="tile",
                llama_cli=self.config.get("llama_cli"),
                llm_model=self.config.get("llm_model"),
                style_anchor=style_pbr,
                custom_cadrage="seamless repeatable tileable texture",
                sans_llm=params.get("sans_llm", params.get("no_llm", True))
            )

            # Rendu avec padding circulaire
            img_brute = generer_image_vulkan(
                prompt=prompt_complet,
                sd_cli=self.config.get("sd_cli"),
                sd_model=self.config.get("sd_model"),
                clip_l=self.config.get("clip_l"),
                t5xxl=self.config.get("t5xxl"),
                vae=self.config.get("vae"),
                backend=self.config.get("backend"),
                threads=self.config.get("threads"),
                circular=True,
                steps=params.get("steps", 25),
                guidance=params.get("guidance", 3.5),
                seed=params.get("seed", -1),
                loras=params.get("loras")
            )
            img_albedo = img_brute.convert("RGB")

        if taille and img_albedo.size != (taille, taille):
            img_albedo = img_albedo.resize((taille, taille), Image.Resampling.LANCZOS)

        # 1. Calcul des différentes maps PBR (Deep Learning ou Sobel)
        pbr_engine = params.get("pbr_engine", "auto")
        maps_pbr = None

        if pbr_engine != "sobel":
            try:
                from core.pbr_deep import estimer_pbr_complet
                self.log(f"Estimation PBR par Deep Learning (DeepBump ONNX)...")
                maps_pbr = estimer_pbr_complet(img_albedo, strength=strength_normal)
                img_normal = maps_pbr["normal"]
                img_roughness = maps_pbr["roughness"]
                img_height = maps_pbr["height"]
                img_ao = maps_pbr["ao"]
                img_orm = maps_pbr["orm"]
            except Exception as e:
                self.log(f"⚠️ Erreur DeepPBR ({e}), bascule sur filtres Sobel standard...")
                maps_pbr = None

        if maps_pbr is None:
            self.log("Calcul de la Normal Map (Gradients Sobel OpenGL)...")
            img_normal = generer_normal_map(img_albedo, strength=strength_normal)
            self.log("Calcul de la Roughness Map & Height Map...")
            img_roughness = generer_roughness_map(img_albedo)
            img_height = generer_height_map(img_albedo)
            self.log("Calcul de l'Ambient Occlusion & Pack ORM Godot...")
            img_ao = generer_ao_map(img_albedo)
            img_orm = generer_orm_pack(img_ao, img_roughness)

        # 2. Sauvegarde des fichiers
        chemin_albedo = os.path.join(output_dir, f"{nom_base}_albedo.png")
        chemin_normal = os.path.join(output_dir, f"{nom_base}_normal.png")
        chemin_roughness = os.path.join(output_dir, f"{nom_base}_roughness.png")
        chemin_height = os.path.join(output_dir, f"{nom_base}_height.png")
        chemin_ao = os.path.join(output_dir, f"{nom_base}_ao.png")
        chemin_orm = os.path.join(output_dir, f"{nom_base}_orm.png")

        img_albedo.save(chemin_albedo, "PNG")
        img_normal.save(chemin_normal, "PNG")
        img_roughness.save(chemin_roughness, "PNG")
        img_height.save(chemin_height, "PNG")
        img_ao.save(chemin_ao, "PNG")
        img_orm.save(chemin_orm, "PNG")

        # 3. Aperçu 3x3
        img_preview = creer_apercu_tuilage(img_albedo, rep_x=3, rep_y=3)
        chemin_preview = os.path.join(output_dir, f"{nom_base}_preview3x3.png")
        img_preview.save(chemin_preview, "PNG")

        # 4. Fichier ressource Matériau Godot (.tres)
        chemin_tres = exporter_fichier_materiau_godot(nom_base, output_dir)

        self.log(f"Pack PBR complet exporté dans '{output_dir}/' :", emoji="🎉")
        self.log(f"  • Albedo    : {chemin_albedo}")
        self.log(f"  • Normal    : {chemin_normal}")
        self.log(f"  • ORM       : {chemin_orm} (R=AO, G=Roughness, B=Metallic)")
        self.log(f"  • Height    : {chemin_height}")
        self.log(f"  • Matériau  : {chemin_tres} (StandardMaterial3D Godot 4)", emoji="💎")

        return {
            "albedo": chemin_albedo,
            "normal": chemin_normal,
            "roughness": chemin_roughness,
            "height": chemin_height,
            "ao": chemin_ao,
            "orm": chemin_orm,
            "material_tres": chemin_tres,
            "preview": chemin_preview,
            "dimensions": img_albedo.size
        }
