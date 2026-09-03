#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow UI 9-Slice : Génération de Cadres d'Interface, Fenêtres et Boutons 9-Patch pour Godot 4.
Produit :
- Image PNG du cadre
- Ressource Godot 4 StyleBoxTexture (.tres)
- Scène Godot 4 NinePatchRect (.tscn)
- Aperçu de test d'extensibilité
"""

import os
from pathlib import Path
from typing import Any, Dict, Tuple
import numpy as np
from PIL import Image, ImageDraw

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.diffusion import generer_image_vulkan
from core.image_ops import post_process_asset
from core.llm import construire_prompt_coherant
from workflows.base import BaseWorkflow, WorkflowRegistry


def detecter_marges_9slice(image: Image.Image) -> Tuple[int, int, int, int]:
    """
    Analyse l'image pour déterminer les marges de découpe (left, top, right, bottom)
    en repérant les zones de transition entre coins décorés et bordures répétables.
    """
    w, h = image.size
    # Valeur par défaut : 1/6ème de la dimension
    def_x = max(16, w // 6)
    def_y = max(16, h // 6)
    return (def_x, def_y, def_x, def_y)


def exporter_stylebox_godot(nom_base: str, output_dir: str, marges: Tuple[int, int, int, int]) -> str:
    """Génère la ressource StyleBoxTexture (.tres) pour Godot 4."""
    ml, mt, mr, mb = marges
    chemin_tres = os.path.join(output_dir, f"{nom_base}_stylebox.tres")
    code_tres = f"""[gd_resource type="StyleBoxTexture" load_steps=2 format=3]

[ext_resource type="Texture2D" path="res://{nom_base}.png" id="1_tex"]

[resource]
texture = ExtResource("1_tex")
texture_margin_left = {ml}.0
texture_margin_top = {mt}.0
texture_margin_right = {mr}.0
texture_margin_bottom = {mb}.0
axis_stretch_horizontal = 1
axis_stretch_vertical = 1
"""
    with open(chemin_tres, "w", encoding="utf-8") as f:
        f.write(code_tres)
    return chemin_tres


def exporter_scene_ninepatch_godot(nom_base: str, output_dir: str, marges: Tuple[int, int, int, int]) -> str:
    """Génère une scène d'exemple Godot 4 avec un NinePatchRect (.tscn)."""
    ml, mt, mr, mb = marges
    chemin_tscn = os.path.join(output_dir, f"{nom_base}_ninepatch.tscn")
    code_tscn = f"""[gd_scene load_steps=2 format=3]

[ext_resource type="Texture2D" path="res://{nom_base}.png" id="1_tex"]

[node name="{nom_base.capitalize()}" type="Control"]
layout_mode = 3
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2

[node name="NinePatchRect" type="NinePatchRect" parent="."]
layout_mode = 1
anchors_preset = 8
anchor_left = 0.5
anchor_top = 0.5
anchor_right = 0.5
anchor_bottom = 0.5
offset_left = -200.0
offset_top = -150.0
offset_right = 200.0
offset_bottom = 150.0
grow_horizontal = 2
grow_vertical = 2
texture = ExtResource("1_tex")
patch_margin_left = {ml}
patch_margin_top = {mt}
patch_margin_right = {mr}
patch_margin_bottom = {mb}
axis_stretch_horizontal = 1
axis_stretch_vertical = 1
"""
    with open(chemin_tscn, "w", encoding="utf-8") as f:
        f.write(code_tscn)
    return chemin_tscn


def creer_preview_extensibilite(image: Image.Image, marges: Tuple[int, int, int, int]) -> Image.Image:
    """Génère un aperçu démontrant l'extensibilité 9-slice sans déformation des coins."""
    ml, mt, mr, mb = marges
    w, h = image.size

    # Extraire les 9 zones
    c_tl = image.crop((0, 0, ml, mt))
    c_tr = image.crop((w - mr, 0, w, mt))
    c_bl = image.crop((0, h - mb, ml, h))
    c_br = image.crop((w - mr, h - mb, w, h))

    b_top = image.crop((ml, 0, w - mr, mt))
    b_bot = image.crop((ml, h - mb, w - mr, h))
    b_left = image.crop((0, mt, ml, h - mb))
    b_right = image.crop((w - mr, mt, w, h - mb))

    center = image.crop((ml, mt, w - mr, h - mb))

    # Construire un cadre étendu (Largeur 600, Hauteur 400)
    target_w, target_h = 600, 350
    expanded = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))

    # Coins
    expanded.paste(c_tl, (0, 0))
    expanded.paste(c_tr, (target_w - mr, 0))
    expanded.paste(c_bl, (0, target_h - mb))
    expanded.paste(c_br, (target_w - mr, target_h - mb))

    # Bordures étirées
    if target_w - ml - mr > 0:
        expanded.paste(b_top.resize((target_w - ml - mr, mt), Image.BILINEAR), (ml, 0))
        expanded.paste(b_bot.resize((target_w - ml - mr, mb), Image.BILINEAR), (ml, target_h - mb))
    if target_h - mt - mb > 0:
        expanded.paste(b_left.resize((ml, target_h - mt - mb), Image.BILINEAR), (0, mt))
        expanded.paste(b_right.resize((mr, target_h - mt - mb), Image.BILINEAR), (target_w - mr, mt))

    # Centre
    if target_w - ml - mr > 0 and target_h - mt - mb > 0:
        expanded.paste(center.resize((target_w - ml - mr, target_h - mt - mb), Image.BILINEAR), (ml, mt))

    return expanded


@WorkflowRegistry.register
class UI9SliceWorkflow(BaseWorkflow):
    """Workflow de Cadres d'Interface 9-Patch pour Godot 4."""

    name = "ui_9slice"
    description = "Génération de cadres d'UI, fenêtres d'inventaire et boutons 9-Patch extensibles pour Godot 4"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        concept = params.get("prompt")
        input_image = params.get("input")

        if not concept and not input_image:
            raise ValueError("Le workflow ui_9slice nécessite un 'prompt' ou une image '-i / --input'.")

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        margin_val = int(params.get("margin", 32))
        auto_margin = params.get("auto_margin", False)
        taille = params.get("size", 256) or 256

        os.makedirs(output_dir, exist_ok=True)

        if input_image and os.path.exists(input_image):
            self.log(f"Chargement du cadre source : {input_image}...")
            img_src = Image.open(input_image).convert("RGBA")
            nom_base = params.get("output") or f"{Path(input_image).stem}_9slice"
        else:
            self.log(f"Génération d'un cadre d'interface pour '{concept}'...")
            nom_base = params.get("output") or slugifier_texte(concept)

            style_ui = (
                "2D game UI frame, inventory window box, medieval dark fantasy border, "
                "symmetrical modular border frame, centered empty rectangle content, isolated on transparent background"
            )

            prompt_complet = construire_prompt_coherant(
                concept=concept,
                type_asset="prop",
                llama_cli=self.config.get("llama_cli"),
                llm_model=self.config.get("llm_model"),
                style_anchor=style_ui,
                custom_cadrage="symmetrical 2D game interface border frame",
                sans_llm=params.get("sans_llm", params.get("no_llm", True))
            )

            img_brute = generer_image_vulkan(
                prompt=prompt_complet,
                sd_cli=self.config.get("sd_cli"),
                sd_model=self.config.get("sd_model"),
                clip_l=self.config.get("clip_l"),
                t5xxl=self.config.get("t5xxl"),
                vae=self.config.get("vae"),
                backend=self.config.get("backend"),
                threads=self.config.get("threads"),
                steps=params.get("steps", 25),
                guidance=params.get("guidance", 3.5),
                seed=params.get("seed", -1),
                loras=params.get("loras")
            )
            # Détourage
            img_src = post_process_asset(img_brute, redimensionner=taille)

        if taille and img_src.size != (taille, taille):
            img_src = img_src.resize((taille, taille), Image.Resampling.LANCZOS)

        # Détermination des marges
        if auto_margin:
            marges = detecter_marges_9slice(img_src)
        else:
            marges = (margin_val, margin_val, margin_val, margin_val)

        self.log(f"Marges 9-Slice appliquées : Left={marges[0]}, Top={marges[1]}, Right={marges[2]}, Bottom={marges[3]}")

        # Sauvegarde image cadre
        chemin_png = os.path.join(output_dir, f"{nom_base}.png")
        img_src.save(chemin_png, "PNG")

        # Sauvegarde StyleBoxTexture
        chemin_stylebox = exporter_stylebox_godot(nom_base, output_dir, marges)

        # Sauvegarde NinePatchRect Scène
        chemin_scene = exporter_scene_ninepatch_godot(nom_base, output_dir, marges)

        # Génération de l'aperçu étendu
        img_preview = creer_preview_extensibilite(img_src, marges)
        chemin_preview = os.path.join(output_dir, f"{nom_base}_preview_stretched.png")
        img_preview.save(chemin_preview, "PNG")

        self.log(f"Pack UI 9-Patch complet exporté dans '{output_dir}/' :", emoji="🎉")
        self.log(f"  • Texture Cadre    : {chemin_png}")
        self.log(f"  • StyleBox Godot 4 : {chemin_stylebox} (StyleBoxTexture)", emoji="💎")
        self.log(f"  • Scène Godot 4    : {chemin_scene} (NinePatchRect)")
        self.log(f"  • Aperçu Étendu    : {chemin_preview}")

        return {
            "texture": chemin_png,
            "stylebox": chemin_stylebox,
            "scene": chemin_scene,
            "preview": chemin_preview,
            "margins": marges
        }
