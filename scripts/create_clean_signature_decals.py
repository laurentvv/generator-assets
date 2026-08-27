# -*- coding: utf-8 -*-
"""
create_clean_signature_decals.py
Création de décalques d'égratignures, cicatrice du front et cernes de fatigue
intégrés de manière fluide, nette et organique (sans aucun contour carré).
"""

import os
import sys
from PIL import Image, ImageFilter, ImageDraw
import numpy as np

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

BASE_SKIN_PATH = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\young_caucasian_male\young_lightskinned_male_diffuse.png"
OUT_MPFB_DIR = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\marc_novice"
OUT_LOCAL_DIR = r"C:\GIT\generator-assets\godot_assets\skins\marc_novice"

def main():
    print("=" * 65)
    print(" ⚔️ DÉCALQUES ORGANIQUES : CICATRICES & CERNES NATURELS DE MARC")
    print("=" * 65)

    base_skin = Image.open(BASE_SKIN_PATH).convert("RGBA")
    w, h = base_skin.size

    # Repères exacts MakeHuman UV (sur texture 2048x2048) :
    # Oeil Gauche (haut UV) : (X=1710, Y=973)
    # Oeil Droit (bas UV) : (X=1710, Y=1144)
    # Nez : (X=1743, Y=1074)
    # Front : (X=1600..1660, Y=1058)
    
    # 1. Calque de peinture pour les cernes sous les yeux
    cerne_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_cerne = ImageDraw.Draw(cerne_layer)
    
    # Croissant sous l'oeil gauche (haut) : centre ~ (1725, 965)
    # Couleur cerne violacé/brun (#422624) à opacité douce
    draw_cerne.ellipse([1700, 935, 1750, 995], fill=(66, 38, 36, 95))
    
    # Croissant sous l'oeil droit (bas) : centre ~ (1725, 1152)
    draw_cerne.ellipse([1700, 1120, 1750, 1180], fill=(66, 38, 36, 95))
    
    cerne_blurred = cerne_layer.filter(ImageFilter.GaussianBlur(radius=12))

    # 2. Calque de la cicatrice du front (au-dessus du sourcil droit, soit Y ~ 1160..1200, X ~ 1610..1640)
    scar_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw_scar = ImageDraw.Draw(scar_layer)

    # Entaille oblique nette (rouge sombre / croute)
    # Ligne de relief extérieur (bordure claire / chair irritée)
    draw_scar.line([(1615, 1180), (1638, 1205)], fill=(185, 95, 80, 180), width=6)
    # Coeur de la cicatrice (rouge sang séché / foncé)
    draw_scar.line([(1617, 1182), (1636, 1203)], fill=(90, 20, 18, 240), width=3)
    
    # Petite égratignure secondaire sur la tempe
    draw_scar.line([(1630, 1172), (1645, 1185)], fill=(110, 30, 25, 200), width=2)
    
    # Égratignure sur la joue gauche (X ~ 1775, Y ~ 915)
    draw_scar.line([(1765, 905), (1785, 925)], fill=(160, 75, 65, 160), width=4)
    draw_scar.line([(1767, 907), (1783, 923)], fill=(85, 22, 18, 220), width=2)

    scar_blurred = scar_layer.filter(ImageFilter.GaussianBlur(radius=1.0))

    # 3. Fusion des calques sur la peau MakeHuman
    final_diffuse = Image.alpha_composite(base_skin, cerne_blurred)
    final_diffuse = Image.alpha_composite(final_diffuse, scar_blurred)

    # 4. Sauvegarde des textures
    for d in [OUT_MPFB_DIR, OUT_LOCAL_DIR]:
        os.makedirs(d, exist_ok=True)

    diff_mpfb = os.path.join(OUT_MPFB_DIR, "marc_novice_diffuse.png")
    diff_local = os.path.join(OUT_LOCAL_DIR, "marc_novice_diffuse.png")
    final_diffuse.convert("RGB").save(diff_mpfb, "PNG", optimize=True)
    final_diffuse.convert("RGB").save(diff_local, "PNG", optimize=True)
    print(f"✅ Texture Diffuse organique enregistrée : {diff_mpfb}")

    # 5. Normal Map avec véritable rainure et biseau pour les cicatrices
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if racine not in sys.path:
        sys.path.insert(0, racine)
    from core.image_ops import generer_normal_map
    norm_img = generer_normal_map(final_diffuse.convert("RGB"), strength=3.0)
    norm_mpfb = os.path.join(OUT_MPFB_DIR, "marc_novice_normal.png")
    norm_local = os.path.join(OUT_LOCAL_DIR, "marc_novice_normal.png")
    norm_img.save(norm_mpfb, "PNG")
    norm_img.save(norm_local, "PNG")
    print(f"✅ Normal Map avec relief 3D enregistrée : {norm_mpfb}")

    # 6. .mhmat
    mhmat_path = os.path.join(OUT_MPFB_DIR, "marc_novice.mhmat")
    with open(mhmat_path, "w", encoding="utf-8") as f:
        f.write("""# Material file for MakeHuman / MPFB - Marc Novice (Cicatrices & Cernes Organiques)
name marc_novice
tag MPFB
diffuseTexture marc_novice_diffuse.png
normalTexture marc_novice_normal.png
roughness 0.60
metallic 0.0
alphaToCoverage False
shaderConfig transparency False
""")
    print("=" * 65)

if __name__ == "__main__":
    main()
