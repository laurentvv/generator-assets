#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Character MakeUp : Pipeline d'extraction et d'application de caractéristiques
faciales et de maquillage (cernes, fatigue, creux, lèvres, teint) depuis un portrait 2D
vers les modèles 3D MakeHuman / MPFB2 (carte UV hm08 standard).
Génère le calque d'encre officiel MPFB2 (.png + .json), personnalise les textures d'yeux,
et produit les rendus de validation studio Cycles (tête et plein pied).
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from PIL import Image

from core.config import (
    DEFAULT_MPFB_DATA_DIR,
    DEFAULT_MPFB_EYES_DIR,
    DEFAULT_MPFB_INK_DIR,
    DEFAULT_OUTPUT_DIR,
    resoudre_yunet_model,
    slugifier_texte,
)
from core.mpfb_ops import (
    analyser_metriques_portrait,
    calculer_gamut_peau_3d,
    creer_corps_personnage_mpfb,
    creer_manifest_ink,
    dessiner_calque_encre_hm08,
    personnaliser_yeux_mpfb,
    rendre_personnage_blender,
)
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class CharacterMakeupWorkflow(BaseWorkflow):
    name = "character_makeup"
    description = "MakeUp & features MPFB2 depuis portrait IA (YuNet + calque d'encre UV hm08 + rendus Cycles)"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        portrait_path = params.get("portrait") or params.get("input")
        if not portrait_path:
            raise ValueError("Le paramètre 'portrait' (ou -i / --input) vers l'image de portrait de référence est requis.")

        if not os.path.exists(portrait_path):
            raise FileNotFoundError(f"Fichier portrait introuvable : {portrait_path}")

        char_name = params.get("character") or params.get("name") or slugifier_texte(Path(portrait_path).stem)
        layer_slug = params.get("output") or f"{char_name}_fatigue_ventgris"

        base_out = params.get("output_dir")
        if not base_out or base_out == DEFAULT_OUTPUT_DIR:
            char_dir = os.path.join(DEFAULT_OUTPUT_DIR, "skins", char_name)
        else:
            char_dir = base_out

        makeup_dir = os.path.join(char_dir, "makeup")
        renders_dir = os.path.join(char_dir, "renders")
        os.makedirs(char_dir, exist_ok=True)
        os.makedirs(makeup_dir, exist_ok=True)
        os.makedirs(renders_dir, exist_ok=True)

        mpfb_ink_dir = params.get("mpfb_ink_dir") or DEFAULT_MPFB_INK_DIR
        os.makedirs(mpfb_ink_dir, exist_ok=True)

        self.log(f"Analyse du portrait : '{portrait_path}' pour le personnage '{char_name}'", "💄")

        # 1. Analyse anatomique et colorimétrique du portrait via YuNet
        yunet_model = params.get("yunet_model") or resoudre_yunet_model()
        self.log(f"Détection des repères faciaux via YuNet ({yunet_model})...", "🔍")
        metriques = analyser_metriques_portrait(portrait_path, yunet_path=yunet_model)

        score = metriques["yunet"]["score"]
        delta_l = metriques["delta_cerne_l"]
        self.log(f"Repères détectés (score={score:.2f}) | ΔL cernes/fatigue = {delta_l:.1f}", "📊")

        # 2. Résolution de la texture de peau diffuse 3D
        skin_path = params.get("skin")
        if not skin_path:
            candidats_skin = [
                os.path.join(DEFAULT_OUTPUT_DIR, "skins", char_name, f"{char_name}_diffuse.png"),
                os.path.join(DEFAULT_OUTPUT_DIR, "skins", f"{char_name}_diffuse.png"),
                os.path.join(r"C:\test", "L'HERITIER DU VIDE", "assets", "textures", f"{char_name}_diffuse.png")
            ]
            for c in candidats_skin:
                if os.path.exists(c):
                    skin_path = c
                    break

        self.log(f"Texture de peau 3D de référence : {skin_path or '(teint Vent-Gris standard)'}", "🎨")
        couleurs_3d = calculer_gamut_peau_3d(skin_path, metriques)

        c_rgb = tuple(int(x) for x in couleurs_3d["cernes"][::-1])
        core_rgb = tuple(int(x) for x in couleurs_3d["cernes_core"][::-1])
        self.log(f"Couleurs 3D avec compensation SSS : Cernes={c_rgb}, Cœur={core_rgb}", "🖌️")

        # 3. Peinture anatomique des calques étagés sur la carte UV hm08
        self.log("Génération du calque d'encre haute résolution (2048x2048 RGBA)...", "✨")
        calque_ink = dessiner_calque_encre_hm08(couleurs_3d)

        # 4. Génération du manifeste officiel MPFB2
        nom_png = f"{layer_slug}.png"
        nom_json = f"{layer_slug}.json"
        manifest = creer_manifest_ink(
            nom_couche=f"{char_name.capitalize()} MakeUp Vent-Gris",
            nom_image=nom_png,
            focus="fatigue_cernes",
            extraction_info={
                "portrait_source": os.path.abspath(portrait_path),
                "yunet_score": round(score, 3),
                "delta_l_cernes": round(delta_l, 1),
                "ratios_bgr": {
                    "cerne": [round(float(x), 3) for x in metriques["ratio_cerne"]],
                    "temple": [round(float(x), 3) for x in metriques["ratio_temple"]],
                    "lips": [round(float(x), 3) for x in metriques["ratio_lips"]],
                },
                "couleurs_3d_bgr": {
                    "cernes": [round(float(x), 1) for x in couleurs_3d["cernes"]],
                    "cernes_core": [round(float(x), 1) for x in couleurs_3d["cernes_core"]],
                    "temples": [round(float(x), 1) for x in couleurs_3d["temples"]],
                    "blush": [round(float(x), 1) for x in couleurs_3d["blush"]],
                    "lips": [round(float(x), 1) for x in couleurs_3d["lips"]],
                }
            }
        )

        # Sauvegarde dans le dossier de sortie du projet ET dans le dossier actif MPFB
        # Sauvegarde dans le dossier makeup du projet ET dans le dossier actif MPFB
        cibles_dossiers = [makeup_dir, mpfb_ink_dir]
        for d in cibles_dossiers:
            os.makedirs(d, exist_ok=True)
            calque_ink.save(os.path.join(d, nom_png), "PNG")
            with open(os.path.join(d, nom_json), "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)

        self.log(f"Calque d'encre MPFB enregistré dans : {os.path.join(makeup_dir, nom_png)}", "✅")
        self.log(f"Manifeste MPFB enregistré dans    : {os.path.join(makeup_dir, nom_json)}", "✅")

        # 5. Personnalisation optionnelle des yeux (ex: cyan / lueur intérieure)
        eye_color = params.get("eye_color", "cyan")
        eye_out = None
        dst_eye_mpfb = None
        if eye_color and eye_color.lower() != "none":
            dst_eye_depot = os.path.join(char_dir, f"{char_name}_{eye_color}_eye.png")
            dst_eye_mpfb = os.path.join(DEFAULT_MPFB_EYES_DIR, f"{char_name}_{eye_color}_eye.png")
            eye_out = personnaliser_yeux_mpfb(
                couleur=eye_color,
                dst_paths=[dst_eye_depot, dst_eye_mpfb]
            )
            if eye_out:
                self.log(f"Texture des yeux ({eye_color}) générée : {dst_eye_depot}", "👁️")

        # 6. Assemblage automatique du corps 3D MPFB2 dans Blender (.blend + .glb)
        build_body = params.get("build_body", True)
        makeup_only = params.get("makeup_only", False)
        blend_file = params.get("blend_file")
        glb_file = None

        if build_body and not makeup_only and not blend_file:
            blend_file = os.path.join(char_dir, f"{char_name}_mpfb2.blend")
            glb_file = os.path.join(char_dir, f"{char_name}_mpfb2.glb")
            self.log(f"Génération automatique du corps 3D MPFB2 ({blend_file})...", "🧍")

            gender_val = float(params.get("gender", 0.0))
            age_val = float(params.get("age", 0.12))
            weight_val = float(params.get("weight", 0.36))
            muscle_val = float(params.get("muscle", 0.12))
            height_val = float(params.get("height", 0.32))
            hair_asset_val = params.get("hair", "short01.mhclo")
            rig_val = params.get("rig", "mixamo")

            skin_mhmat = params.get("skin_mhmat")
            if not skin_mhmat:
                cands = [
                    os.path.join(DEFAULT_OUTPUT_DIR, "skins", char_name, f"{char_name}.mhmat"),
                    os.path.join(DEFAULT_OUTPUT_DIR, "skins", f"{char_name}_enfant", f"{char_name}_enfant.mhmat"),
                ]
                for c in cands:
                    if os.path.exists(c):
                        skin_mhmat = c
                        break

            ok_body = creer_corps_personnage_mpfb(
                char_name=char_name,
                output_blend_path=blend_file,
                output_glb_path=glb_file,
                ink_json_path=os.path.join(mpfb_ink_dir, nom_json),
                eye_texture_path=dst_eye_mpfb if eye_out else None,
                skin_mhmat_path=skin_mhmat,
                gender=gender_val,
                age=age_val,
                weight=weight_val,
                muscle=muscle_val,
                height=height_val,
                hair_asset=hair_asset_val,
                rig=rig_val
            )
            if ok_body:
                self.log(f"Scène .blend native générée : {blend_file}", "✅")
                self.log(f"Modèle .glb optimisé généré : {glb_file}", "✅")

        # 7. Rendu de contrôle studio Blender Cycles (tête et plein pied)
        rendus = {}
        if blend_file and os.path.exists(blend_file):
            self.log(f"Génération des rendus studio Cycles depuis : '{blend_file}'...", "🎬")
            render_prefix = os.path.join(renders_dir, f"{char_name}")
            samples = int(params.get("samples", 48))
            modes = params.get("render_modes", ["head", "body"])
            if isinstance(modes, str):
                modes = [m.strip().lower() for m in modes.split(",") if m.strip()]

            rendus = rendre_personnage_blender(
                blend_path=blend_file,
                output_prefix=render_prefix,
                modes=modes,
                samples=samples
            )
            for k, chemin in rendus.items():
                self.log(f"Rendu validé [{k}] : {chemin}", "📷")

        resultat = {
            "status": "success",
            "character": char_name,
            "ink_png": os.path.join(makeup_dir, nom_png),
            "ink_json": os.path.join(makeup_dir, nom_json),
            "blend": blend_file if (blend_file and os.path.exists(blend_file)) else None,
            "glb": glb_file if (glb_file and os.path.exists(glb_file)) else None,
            "eye_texture": eye_out,
            "metriques": metriques,
            "rendus": rendus
        }
        self.log(f"Workflow terminé avec succès pour '{char_name}'.", "🎉")
        return resultat


@WorkflowRegistry.register
class Character3DWorkflow(CharacterMakeupWorkflow):
    name = "character3d"
    description = "Pipeline universel Portrait IA -> Corps 3D MPFB2 (.blend, .glb, MakeUp, Yeux, Rendus Cycles)"

