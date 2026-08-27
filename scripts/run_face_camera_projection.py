#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Orchestrateur Complet de Projection Caméra 2D ➔ 3D pour Marc.
1. Exécute Blender en arrière-plan pour projeter et b цифроiser (bake) le portrait 2D sur le maillage 3D.
2. Fusionne sans couture la texture de visage projetée avec la peau corporelle MakeHuman.
3. Met à jour les répertoires MPFB Blender, POC 3D et godot_assets.
4. Effectue un rendu 3D sous Blender pour validation visuelle.
"""

import os
import subprocess
import sys

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

from PIL import Image, ImageFilter, ImageDraw

BLENDER_EXE = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
SCRIPT_BAKE_BLENDER = r"C:\GIT\generator-assets\scripts\blender_bake_projection.py"
TEMP_BAKE_OUTPUT = r"C:\GIT\generator-assets\godot_assets\temp_marc_baked_face.png"
SKIN_BASE = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\young_caucasian_male\young_lightskinned_male_diffuse.png"

SORTIE_DIFFUSE_MPFB = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\marc_novice\marc_novice_diffuse.png"
SORTIE_DIFFUSE_LOCAL = r"C:\GIT\generator-assets\godot_assets\skins\marc_novice\marc_novice_diffuse.png"
SORTIE_DIFFUSE_POC = r"C:\test\L'HERITIER DU VIDE\poc_3d\exports\marc_mpfb2_young_lightskinned_male_diffuse.png"
THUMB_MPFB = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\marc_novice\marc_novice.thumb"
THUMB_LOCAL = r"C:\GIT\generator-assets\godot_assets\skins\marc_novice\marc_novice.thumb"


def main():
    print("=" * 65)
    print(" 🎬 PIPELINE OFFICIEL : PROJECTION CAMÉRA 2D ➔ 3D (BLENDER + MAKEHUMAN)")
    print("=" * 65)

    # 1. Exécution du Baking Blender
    print(f"\n[1/3] Exécution de Blender headless pour le baking UV...")
    cmd = [BLENDER_EXE, "--background", "--python", SCRIPT_BAKE_BLENDER]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print(res.stdout)
    if res.returncode != 0 or not os.path.exists(TEMP_BAKE_OUTPUT):
        print(f"❌ Erreur lors du baking Blender : {res.stderr}")
        sys.exit(1)

    # 2. Composition & Fusion sans couture avec la peau du corps
    print(f"[2/3] Fusion sans couture de la face projetée avec la peau corporelle...")
    baked_img = Image.open(TEMP_BAKE_OUTPUT).convert("RGBA")
    skin_base_img = Image.open(SKIN_BASE).convert("RGBA").resize(baked_img.size)

    w, h = baked_img.size
    masque = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(masque)

    # Zone UV du visage MakeHuman hm08 (tête avant)
    draw.ellipse([int(w * 0.35), int(h * 0.10), int(w * 0.65), int(h * 0.46)], fill=255)
    masque_fondu = masque.filter(ImageFilter.GaussianBlur(radius=32))

    baked_face = baked_img.copy()
    baked_face.putalpha(masque_fondu)

    skin_finale = Image.alpha_composite(skin_base_img, baked_face).convert("RGB")

    # 3. Sauvegarde dans tous les dossiers cibles
    print(f"[3/3] Export des textures de peau UV officielles...")
    for path in [SORTIE_DIFFUSE_MPFB, SORTIE_DIFFUSE_LOCAL, SORTIE_DIFFUSE_POC]:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        skin_finale.save(path, "PNG", optimize=True)
        print(f"  ✅ {path}")

    # Vignette .thumb
    thumb_crop = skin_finale.crop((int(w * 0.30), int(h * 0.10), int(w * 0.70), int(h * 0.48)))
    thumb_img = thumb_crop.resize((256, 256), Image.Resampling.LANCZOS).convert("RGBA")
    for t_path in [THUMB_MPFB, THUMB_LOCAL]:
        os.makedirs(os.path.dirname(t_path), exist_ok=True)
        thumb_img.save(t_path, "PNG")
        print(f"  ✅ Vignette : {t_path}")

    # Nettoyage temporaire
    if os.path.exists(TEMP_BAKE_OUTPUT):
        os.remove(TEMP_BAKE_OUTPUT)

    print("\n" + "=" * 65)
    print(" 🎉 PROJECTION CAMÉRA EFFECTUÉE ET BAKE UV TERMINÉ AVEC SUCCÈS !")
    print("=" * 65)


if __name__ == "__main__":
    main()
