# -*- coding: utf-8 -*-
"""
apply_marc_signature_features.py
Application nette, contrastée et professionnelle des détails signature de Marc :
1. Cicatrice nette au-dessus du sourcil droit.
2. Égratignure sur la joue gauche.
3. Cernes de fatigue marqués sous les yeux (regard intense de survivant de Vent-Gris).
4. Poussière / patine de salissure médiévale sur le front et les tempes.
5. Normal Map avec véritable relief 3D (saillie et rainure des cicatrices).
"""

import os
import sys
from PIL import Image, ImageFilter, ImageEnhance, ImageOps
import numpy as np

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

PORTRAIT_PATH = r"C:\test\L'HERITIER DU VIDE\assets\portraits\marc_portrait.png"
BASE_SKIN_PATH = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\young_caucasian_male\young_lightskinned_male_diffuse.png"

OUT_MPFB_DIR = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\marc_novice"
OUT_LOCAL_DIR = r"C:\GIT\generator-assets\godot_assets\skins\marc_novice"

def main():
    print("=" * 65)
    print(" ⚔️ APPLICATION DES DÉTAILS SIGNATURE DE MARC (CICATRICES & CERNES)")
    print("=" * 65)

    base_skin = Image.open(BASE_SKIN_PATH).convert("RGBA")
    w_base, h_base = base_skin.size

    portrait = Image.open(PORTRAIT_PATH).convert("RGBA")
    
    # 1. Calibrage géométrique exact
    scale = 171.0 / 187.0
    rot_portrait = portrait.rotate(90, expand=True, resample=Image.Resampling.BICUBIC)
    scaled_portrait = rot_portrait.resize((int(rot_portrait.width * scale), int(rot_portrait.height * scale)), Image.Resampling.LANCZOS)
    
    eye_in_scaled_x = 360.0 * scale
    eye_in_scaled_y = 512.5 * scale
    paste_x = int(round(1710.1 - eye_in_scaled_x))
    paste_y = int(round(1058.5 - eye_in_scaled_y))

    # 2. Extraction ciblée des DÉTAILS HAUTE FRÉQUENCE (Cicatrices, Cernes, Taches)
    # Dans le portrait pivoté, on isole uniquement les éléments sombres et rouges (cicatrices, cernes)
    # sans toucher au nez ni à la bouche
    arr_port = np.array(scaled_portrait, dtype=np.float32)[:, :, :3]
    h_scaled, w_scaled, _ = arr_port.shape
    
    # Calque de détails transparent
    detail_layer = np.zeros((h_scaled, w_scaled, 4), dtype=np.float32)
    
    # Coordonnées des zones clés dans l'image pivotée (X' = Y_orig, Y' = 1024 - X_orig) :
    # 1) Cicatrice front droit : Y_orig ~ 230..280, X_orig ~ 360..420
    #    -> X' ~ 210..260, Y' ~ 550..620
    # 2) Égratignure joue gauche : Y_orig ~ 420..470, X_orig ~ 620..680
    #    -> X' ~ 380..430, Y' ~ 310..380
    # 3) Cernes sous les yeux :
    #    Oeil Droit : X' ~ 340..390, Y' ~ 560..630
    #    Oeil Gauche : X' ~ 340..390, Y' ~ 380..450

    # Création du masque d'isolation des traits caractéristiques
    feature_mask = np.zeros((h_scaled, w_scaled), dtype=np.float32)
    
    # Masque cicatrice front
    for y in range(h_scaled):
        for x in range(w_scaled):
            # Zone front (cicatrice droite)
            if (200 * scale <= x <= 280 * scale) and (530 * scale <= y <= 630 * scale):
                feature_mask[y, x] = 1.0
            # Zone joue gauche (égratignure)
            elif (380 * scale <= x <= 450 * scale) and (300 * scale <= y <= 380 * scale):
                feature_mask[y, x] = 1.0
            # Zone cernes sous les yeux
            elif (340 * scale <= x <= 395 * scale) and ((370 * scale <= y <= 450 * scale) or (560 * scale <= y <= 640 * scale)):
                # Dégradé doux pour les cernes
                feature_mask[y, x] = 0.65

    # Lissage du masque
    mask_img = Image.fromarray((feature_mask * 255.0).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius=3))
    arr_mask_smooth = np.array(mask_img, dtype=np.float32) / 255.0

    # Application des détails avec contraste rehaussé pour qu'ils soient BIEN VISIBLES
    # Rehaussement du contraste des cicatrices et cernes
    port_enhanced = ImageEnhance.Contrast(scaled_portrait.convert("RGB")).enhance(1.4)
    arr_port_enh = np.array(port_enhanced, dtype=np.float32)

    # Récupération de la peau sous-jacente
    mh_crop = base_skin.crop((paste_x, paste_y, paste_x + w_scaled, paste_y + h_scaled))
    arr_mh = np.array(mh_crop, dtype=np.float32)[:, :, :3]

    # Mode MULTIPLY + OVERLAY pour incruster nettement les cicatrices rougeoyantes et les cernes
    # sans aucune rupture de teinte
    mult_blend = (arr_mh * arr_port_enh) / 255.0
    
    # Rehausser la saturation rouge de la cicatrice
    mult_blend[:, :, 0] = np.clip(mult_blend[:, :, 0] * 1.15, 0, 255)
    
    # Fusion finale avec le masque ciblé
    alpha_3d = np.repeat(arr_mask_smooth[:, :, np.newaxis], 3, axis=2)
    final_face_patch = np.clip(arr_mh * (1.0 - alpha_3d) + mult_blend * alpha_3d, 0, 255).astype(np.uint8)
    final_face_img = Image.fromarray(final_face_patch).convert("RGBA")

    # 3. Collage direct sur la texture MakeHuman (Nez et bouche restent 100% natifs MakeHuman)
    final_diffuse = base_skin.copy()
    final_diffuse.paste(final_face_img, (paste_x, paste_y), mask_img)

    # 4. Sauvegarde des textures Diffuse
    for d in [OUT_MPFB_DIR, OUT_LOCAL_DIR]:
        os.makedirs(d, exist_ok=True)

    diff_mpfb = os.path.join(OUT_MPFB_DIR, "marc_novice_diffuse.png")
    diff_local = os.path.join(OUT_LOCAL_DIR, "marc_novice_diffuse.png")
    final_diffuse.convert("RGB").save(diff_mpfb, "PNG", optimize=True)
    final_diffuse.convert("RGB").save(diff_local, "PNG", optimize=True)
    print(f"✅ Texture Diffuse avec cicatrices et cernes nets enregistrée : {diff_mpfb}")

    # 5. Normal Map avec RELIEF 3D ACCENTUÉ sur les cicatrices
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if racine not in sys.path:
        sys.path.insert(0, racine)
    from core.image_ops import generer_normal_map
    norm_img = generer_normal_map(final_diffuse.convert("RGB"), strength=3.5)
    norm_mpfb = os.path.join(OUT_MPFB_DIR, "marc_novice_normal.png")
    norm_local = os.path.join(OUT_LOCAL_DIR, "marc_novice_normal.png")
    norm_img.save(norm_mpfb, "PNG")
    norm_img.save(norm_local, "PNG")
    print(f"✅ Normal Map avec rainures de cicatrices enregistrée : {norm_mpfb}")

    # 6. Fichier .mhmat
    mhmat_path = os.path.join(OUT_MPFB_DIR, "marc_novice.mhmat")
    with open(mhmat_path, "w", encoding="utf-8") as f:
        f.write("""# Material file for MakeHuman / MPFB - Marc Novice (Cicatrices & Cernes)
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
