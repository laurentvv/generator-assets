#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Material 3D (PBR) workflow: complete PBR texture pack generation for Godot 3D.
Produces:
- Albedo (color texture)
- Normal Map (OpenGL tangent format)
- Roughness Map (micro-roughness)
- Height Map (displacement / relief)
- Ambient Occlusion (AO)
- ORM Pack (Occlusion R, Roughness G, Metallic B)
- Godot 4 StandardMaterial3D resource file (.tres)
- 3x3 tiling preview
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
from PIL import Image, ImageOps

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
    description = "Complete PBR 3D material pack (Albedo, Normal, Roughness, Height, AO, ORM + Godot .tres)"

    emoji = "🧱"

    # CLI declarations (audit §2.2, migration from the flat table of cli/parser.py:
    # help/defaults taken as-is, unchanged surface).
    PARAMETRES = [
        dict(flags=("--normal-strength",), type=float, default=3.5,
             help="Relief intensity for the PBR Normal Map (default: 3.5)."),
        dict(flags=("--pbr-engine",), default="auto", choices=["auto", "deep", "sobel"],
             help="PBR estimation engine (deep = DeepBump ONNX, sobel = 2D filters)."),
        dict(flags=("--delight",), action="store_true", default=False,
             help="material3d: remove baked directional lighting and specular hotspots from the albedo before PBR estimation."),
        dict(flags=("--from-lib",), dest="from_lib", default=None,
             help="material3d: resolve a curated PBR pack or albedo texture from C:\\GIT\\web-assets (NO_AI excluded)."),
        dict(flags=("--pbr-group",), dest="pbr_group", default=None,
             help="material3d: exact web-assets pbr_group key to import and complete missing Godot PBR maps."),
    ]

    def _charger_depuis_bibliotheque(
        self, params: Dict[str, Any]
    ) -> tuple[Optional[Image.Image], Dict[str, Image.Image], str, Optional[str]]:
        """Loads an existing curated PBR group or albedo image from C:\\GIT\\web-assets."""
        from core.web_assets import (
            charger_groupe_pbr,
            lister_groupes_pbr,
            resoudre_reference_web_assets,
        )

        pbr_group = (params.get("pbr_group") or "").strip()
        from_lib = (params.get("from_lib") or "").strip()
        curated: Dict[str, Image.Image] = {}

        if not pbr_group and from_lib:
            groupes = lister_groupes_pbr(query=from_lib, min_maps=2, exclude_no_ai=True, limit=1)
            if groupes:
                pbr_group = groupes[0]["pbr_group"]

        if pbr_group:
            pack = charger_groupe_pbr(pbr_group, exclude_no_ai=True)
            for role, meta in pack.items():
                abs_path = meta.get("abs_path")
                if abs_path and os.path.exists(abs_path):
                    mode = "RGB" if role in ("albedo", "normal", "orm") else "L"
                    with Image.open(abs_path) as im:
                        curated[role] = im.convert(mode)
            if not curated:
                raise FileNotFoundError(f"No readable PBR maps found for web-assets group '{pbr_group}'.")
            if "albedo" not in curated:
                raise ValueError(
                    f"Curated PBR group '{pbr_group}' has no albedo map ({sorted(curated.keys())}); "
                    "pass -i <albedo> explicitly."
                )
            if "roughness" not in curated and "gloss" in curated:
                curated["roughness"] = ImageOps.invert(curated["gloss"].convert("L"))
            base_img = curated["albedo"].convert("RGB")
            nom = params.get("output") or f"{slugifier_texte(pbr_group)}_pbr"
            self.log(f"Loaded web-assets PBR pack '{pbr_group}' ({sorted(curated.keys())}).")
            return base_img, curated, nom, pbr_group

        if from_lib:
            hit = resoudre_reference_web_assets(from_lib, asset_type="image")
            with Image.open(hit["abs_path"]) as im:
                base_img = im.convert("RGB")
            nom = params.get("output") or f"{Path(hit['abs_path']).stem}_pbr"
            self.log(f"Loaded web-assets image '{hit['rel_path']}' ({hit['licence']['licence']}).")
            return base_img, {}, nom, None

        return None, {}, "", None

    def _completer_pack_pbr(
        self,
        img_albedo: Image.Image,
        curated_maps: Dict[str, Image.Image],
        pbr_engine: str,
        strength_normal: float,
        delighted: bool,
    ) -> Dict[str, Image.Image]:
        """Reuses curated maps where valid and synthesizes any missing PBR channels."""
        target_size = img_albedo.size
        resized_curated: Dict[str, Image.Image] = {}
        for role, img in curated_maps.items():
            mode = "RGB" if role in ("albedo", "normal", "orm") else "L"
            converted = img.convert(mode)
            if converted.size != target_size:
                converted = converted.resize(target_size, Image.Resampling.LANCZOS)
            resized_curated[role] = converted

        # Recompute derived relief maps from delighted albedo when requested, or reuse curated maps
        need_synthesis = delighted or not ({"normal", "roughness", "height", "ao"} <= set(resized_curated))
        synth: Dict[str, Image.Image] = {}
        if need_synthesis:
            if pbr_engine != "sobel":
                try:
                    from core.pbr_deep import estimer_pbr_complet
                    self.log("PBR estimation via Deep Learning (DeepBump ONNX)...")
                    synth = estimer_pbr_complet(img_albedo, strength=strength_normal)
                except Exception as e:
                    self.log(f"⚠️ DeepPBR error ({e}), falling back to standard Sobel filters...")
                    synth = {}

            if not synth:
                self.log("Computing PBR maps (OpenGL Sobel gradients)...")
                synth = {
                    "normal": generer_normal_map(img_albedo, strength=strength_normal),
                    "roughness": generer_roughness_map(img_albedo),
                    "height": generer_height_map(img_albedo),
                    "ao": generer_ao_map(img_albedo),
                }
                synth["orm"] = generer_orm_pack(synth["ao"], synth["roughness"])

        img_normal = resized_curated["normal"] if (not delighted and "normal" in resized_curated) else synth["normal"]
        img_rough = resized_curated["roughness"] if (not delighted and "roughness" in resized_curated) else synth["roughness"]
        img_height = resized_curated["height"] if (not delighted and "height" in resized_curated) else synth["height"]
        img_ao = resized_curated["ao"] if (not delighted and "ao" in resized_curated) else synth["ao"]
        img_metal = resized_curated.get("metallic") or synth.get("metallic")
        if not delighted and "orm" in resized_curated:
            img_orm = resized_curated["orm"]
        elif img_metal is not None:
            img_orm = Image.merge("RGB", (img_ao.convert("L"), img_rough.convert("L"), img_metal.convert("L")))
        else:
            img_orm = generer_orm_pack(img_ao.convert("L"), img_rough.convert("L"))

        return {
            "albedo": img_albedo,
            "normal": img_normal,
            "roughness": img_rough,
            "height": img_height,
            "ao": img_ao,
            "orm": img_orm,
        }

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        concept = params.get("prompt")
        input_image = params.get("input")
        from_lib = params.get("from_lib")
        pbr_group = params.get("pbr_group")

        if not concept and not input_image and not from_lib and not pbr_group:
            raise ValueError(
                "One of 'prompt', '--input', '--from-lib', or '--pbr-group' is required for material3d."
            )

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        taille = params.get("size", 1024) or 1024
        strength_normal = float(params.get("normal_strength", 3.5))
        do_delight = bool(params.get("delight", False))

        os.makedirs(output_dir, exist_ok=True)
        curated_maps: Dict[str, Image.Image] = {}
        resolved_group: Optional[str] = None

        if input_image:
            if not os.path.exists(input_image):
                raise FileNotFoundError(f"Source texture not found: {input_image}")
            self.log(f"Loading the source texture: {input_image}...")
            with Image.open(input_image) as im:
                img_albedo = im.convert("RGB")
            nom_base = params.get("output") or f"{Path(input_image).stem}_pbr"
        elif from_lib or pbr_group:
            img_albedo, curated_maps, nom_base, resolved_group = self._charger_depuis_bibliotheque(params)
        else:
            self.log(f"Generating a PBR texture for '{concept}'...")
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

            # Render with circular padding
            img_brute = generer_image_vulkan(
                prompt=prompt_complet,
                sd_cli=self.config.get("sd_cli"),
                sd_model=self.config.get("sd_model"),
                clip_l=self.config.get("clip_l"),
                t5xxl=self.config.get("t5xxl"),
                vae=self.config.get("vae"),
                backend=self.config.get("backend"),
                threads=params.get("threads", self.config.get("threads")),
                circular=True,
                steps=params.get("steps", 25),
                guidance=params.get("guidance", 3.5),
                seed=params.get("seed", -1),
                loras=params.get("loras")
            )
            img_albedo = img_brute.convert("RGB")

        if taille and img_albedo.size != (taille, taille):
            img_albedo = img_albedo.resize((taille, taille), Image.Resampling.LANCZOS)

        if do_delight:
            from core.pbr_deep import delight_albedo
            self.log("Applying albedo delighting (flattening baked shadows & specular hotspots)...")
            img_albedo = delight_albedo(img_albedo)

        # 1. Computation / completion of the PBR maps (curated, Deep Learning, or Sobel)
        pbr_engine = params.get("pbr_engine", "auto")
        maps = self._completer_pack_pbr(
            img_albedo=img_albedo,
            curated_maps=curated_maps,
            pbr_engine=pbr_engine,
            strength_normal=strength_normal,
            delighted=do_delight,
        )
        img_normal = maps["normal"]
        img_roughness = maps["roughness"]
        img_height = maps["height"]
        img_ao = maps["ao"]
        img_orm = maps["orm"]

        # 2. Saving the files
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

        # 3. 3x3 preview
        img_preview = creer_apercu_tuilage(img_albedo, rep_x=3, rep_y=3)
        chemin_preview = os.path.join(output_dir, f"{nom_base}_preview3x3.png")
        img_preview.save(chemin_preview, "PNG")

        # 4. Godot material resource file (.tres)
        chemin_tres = exporter_fichier_materiau_godot(nom_base, output_dir)

        self.log(f"Complete PBR pack exported to '{output_dir}/':", emoji="🎉")
        self.log(f"  • Albedo    : {chemin_albedo}")
        self.log(f"  • Normal    : {chemin_normal}")
        self.log(f"  • ORM       : {chemin_orm} (R=AO, G=Roughness, B=Metallic)")
        self.log(f"  • Height    : {chemin_height}")
        self.log(f"  • Material  : {chemin_tres} (StandardMaterial3D Godot 4)", emoji="💎")

        return {
            "albedo": chemin_albedo,
            "normal": chemin_normal,
            "roughness": chemin_roughness,
            "height": chemin_height,
            "ao": chemin_ao,
            "orm": chemin_orm,
            "material_tres": chemin_tres,
            "preview": chemin_preview,
            "dimensions": img_albedo.size,
            "delighted": do_delight,
            "pbr_group": resolved_group,
        }
