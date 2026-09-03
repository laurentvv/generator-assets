#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow MakeHuman Clothes : Génération automatisée de garde-robe complète
compatible MakeHuman & MPFB2 (Torso/Haut, Pantalon/Bas, Chaussures/Bottes).
Génère les textures PBR par IA, compile les fichiers .mhclo / .obj / .mhmat / .thumb
dans la bibliothèque MPFB, et crée une scène 3D Blender (.blend) d'un New Human
habillé avec rendu .png de prévisualisation.
"""

import os
from pathlib import Path
from typing import Any, Dict, List
from PIL import Image

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.diffusion import generer_image_vulkan
from core.image_ops import generer_ao_map, generer_normal_map, generer_roughness_map
from core.llm import construire_prompt_coherant
from core.mpfb_ops import (
    DEFAULT_MPFB_CLOTHES_DIR,
    compiler_vetement_mpfb,
    creer_scene_personnage_habille,
    verifier_mpfb_disponible
)
from core.upscaler import upscale_esrgan
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class MakeHumanClothesWorkflow(BaseWorkflow):
    name = "makehuman_clothes"
    description = "Garde-robe MakeHuman / MPFB (Torso, Pantalon, Chaussures) + Scène New Human .blend"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        theme = params.get("prompt")
        if not theme:
            raise ValueError("Le paramètre 'prompt' (thème de la tenue, ex: 'cuir médiéval aventurier') est requis.")

        output_dir = params.get("output_dir") or DEFAULT_OUTPUT_DIR
        mpfb_clothes_dir = params.get("mpfb_dir") or DEFAULT_MPFB_CLOTHES_DIR
        nom_base = params.get("output") or slugifier_texte(theme)

        parts_param = params.get("parts", "torso,pants,shoes")
        if isinstance(parts_param, str):
            parts_list = [p.strip().lower() for p in parts_param.split(",") if p.strip()]
        else:
            parts_list = parts_param

        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(mpfb_clothes_dir, exist_ok=True)

        self.log(f"Création de la garde-robe MakeHuman pour le thème : '{theme}'", "👗")
        self.log(f"Pièces à générer : {', '.join(parts_list)}", "🧵")

        mhclo_generated_paths: List[str] = []
        resultats_pieces = {}

        # Dictionnaires d'enrichissement par pièce (textures brutes de matière pure, sans motifs figuratifs pré-peints)
        part_prompts = {
            "torso": f"top-down macro photograph of rustic weathered leather armor material, fine authentic leather grain texture, natural creases, {theme}, 8k scan, flat neutral studio lighting, full frame surface",
            "pants": f"top-down macro photograph of dark medieval wool weave and heavy fabric textile, fine cloth texture, {theme}, 8k scan, flat neutral studio lighting, full frame surface",
            "shoes": f"top-down macro photograph of heavy dark boot leather hide, sturdy leather grain surface, {theme}, 8k scan, flat neutral studio lighting, full frame surface"
        }

        upscale_enabled = params.get("upscale", True)
        esrgan_model = params.get("esrgan_model") or self.config.get("esrgan_model")

        for part in parts_list:
            part_name = f"{nom_base}_{part}"
            self.log(f"--- [1/2] Génération de la texture PBR IA pour '{part}' ({part_name}) ---", "🎨")

            prompt_part = part_prompts.get(part, f"top-down macro photograph of authentic {part} material, {theme}, 8k scan, flat neutral studio lighting")
            prompt_complet = construire_prompt_coherant(
                concept=prompt_part,
                type_asset="tile",
                llama_cli=self.config.get("llama_cli"),
                llm_model=self.config.get("llm_model"),
                style_anchor="macro photographic PBR material texture, flat top-down surface, neutral lighting, 8k scan, full frame texture",
                custom_cadrage="macro surface texture map, no person, no mannequins, no borders, no pre-modeled objects",
                sans_llm=params.get("sans_llm", params.get("no_llm", True))
            )

            # 1. Génération Albedo
            img_brute = generer_image_vulkan(
                prompt=prompt_complet,
                sd_cli=self.config.get("sd_cli"),
                sd_model=self.config.get("sd_model"),
                clip_l=self.config.get("clip_l"),
                t5xxl=self.config.get("t5xxl"),
                vae=self.config.get("vae"),
                backend=self.config.get("backend"),
                threads=self.config.get("threads"),
                circular=False,
                steps=params.get("steps", 20),
                guidance=params.get("guidance", 3.5),
                seed=params.get("seed", -1),
                loras=params.get("loras")
            )
            img_albedo = img_brute.convert("RGB")

            # Upscaling de la texture brute si activé
            if upscale_enabled and esrgan_model and os.path.exists(esrgan_model):
                try:
                    self.log(f"Upscaling IA (ESRGAN 4x) de la texture {part}...", "🔍")
                    img_albedo = upscale_esrgan(
                        img_albedo,
                        esrgan_model_path=esrgan_model,
                        sd_cli=self.config.get("sd_cli"),
                        backend=self.config.get("backend")
                    )
                except Exception as e:
                    self.log(f"Upscaling ignoré pour {part} : {e}", "⚠️")

            # Chemins temporaires / locaux des textures
            diffuse_file = os.path.join(output_dir, f"{part_name}_diffuse.png")
            normal_file = os.path.join(output_dir, f"{part_name}_normal.png")
            ao_file = os.path.join(output_dir, f"{part_name}_ao.png")

            img_albedo.save(diffuse_file)
            img_normal = generer_normal_map(img_albedo, strength=2.0)
            img_normal.save(normal_file)
            img_ao = generer_ao_map(img_albedo)
            img_ao.save(ao_file)

            # 2. Compilation MakeClothes dans Blender
            self.log(f"--- [2/2] Découpe Quad & Compilation MakeClothes pour '{part}' ---", "⚙️")
            part_folder = os.path.join(mpfb_clothes_dir, part_name)
            os.makedirs(part_folder, exist_ok=True)

            success = compiler_vetement_mpfb(
                asset_name=part_name,
                part_type=part,
                output_folder=part_folder,
                diffuse_path=diffuse_file,
                normal_path=normal_file,
                ao_path=ao_file,
                thickness=0.012 if part != "shoes" else 0.016,
                author="AI-Generator"
            )

            if success:
                mhclo_file = os.path.join(part_folder, f"{part_name}.mhclo")
                mhclo_generated_paths.append(mhclo_file)
                resultats_pieces[part] = {
                    "folder": part_folder,
                    "mhclo": mhclo_file,
                    "obj": os.path.join(part_folder, f"{part_name}.obj"),
                    "mhmat": os.path.join(part_folder, f"{part_name}.mhmat"),
                    "thumb": os.path.join(part_folder, f"{part_name}.thumb")
                }
                self.log(f"Asset MPFB compilé avec succès dans : {part_folder}", "✅")
            else:
                self.log(f"Échec de compilation pour {part}", "❌")

        # 3. Création de la scène New Human habillé sous Blender
        blend_file = os.path.join(output_dir, f"{nom_base}_personnage_habille.blend")
        render_file = os.path.join(output_dir, f"{nom_base}_personnage_habille.png")

        self.log(f"Génération du 'New Human' habillé dans Blender : {blend_file}...", "🧍")
        scene_ok = creer_scene_personnage_habille(
            character_name=nom_base,
            mhclo_files=mhclo_generated_paths,
            output_blend_path=blend_file,
            render_image_path=render_file
        )

        if scene_ok:
            self.log(f"Scène Blender sauvegardée : {blend_file}", "💎")
            if os.path.exists(render_file):
                self.log(f"Rendu d'image sauvegardé : {render_file}", "🖼️")
                # Upscaling final du rendu preview si demandé
                if upscale_enabled and esrgan_model and os.path.exists(esrgan_model):
                    try:
                        img_prev = Image.open(render_file)
                        img_prev_up = upscale_esrgan(img_prev, esrgan_model_path=esrgan_model, sd_cli=self.config.get("sd_cli"))
                        upscaled_render_file = os.path.join(output_dir, f"{nom_base}_personnage_habille_upscaled.png")
                        img_prev_up.save(upscaled_render_file)
                        self.log(f"Aperçu haute résolution 4x sauvegardé : {upscaled_render_file}", "✨")
                    except Exception as e:
                        self.log(f"Upscaling aperçu ignoré : {e}", "⚠️")

        return {
            "theme": theme,
            "mpfb_assets": resultats_pieces,
            "blend_scene": blend_file if scene_ok else None,
            "render_preview": render_file if os.path.exists(render_file) else None
        }
