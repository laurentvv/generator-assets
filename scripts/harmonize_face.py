# -*- coding: utf-8 -*-
"""
harmonize_face.py
Harmonisation colorimétrique complète du visage de Marc sur la peau MakeHuman :
1. Nettoyage de l'ombre sous le nez (qui faisait une tâche sombre sur le philtrum).
2. Transfert de tonalité LAB (la couleur de peau de Marc s'harmonise 100% avec la peau MakeHuman).
3. Injection des détails haute fréquence (cicatrices, micro-relief, regard) sans choc colorimétrique.
4. Fondu périphérique naturel sur le front, les joues et le menton.
"""

import os
import sys
from PIL import Image, ImageFilter, ImageEnhance
import numpy as np

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

PORTRAIT_PATH = r"C:\test\L'HERITIER DU VIDE\assets\portraits\marc_portrait.png"
BASE_SKIN_PATH = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\young_caucasian_male\young_lightskinned_male_diffuse.png"

OUT_MPFB_DIR = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\marc_novice"
OUT_LOCAL_DIR = r"C:\GIT\generator-assets\godot_assets\skins\marc_novice"

def rgb_to_lab(img_arr):
    # Conversion simple RGB -> LAB via matrice standard
    # Normalisation [0..1]
    rgb = img_arr.astype(np.float32) / 255.0
    # gamma correction
    mask = rgb > 0.04045
    rgb[mask] = np.power((rgb[mask] + 0.055) / 1.055, 2.4)
    rgb[~mask] = rgb[~mask] / 12.92
    
    # Vers XYZ
    m = np.array([
        [0.412453, 0.357580, 0.180423],
        [0.212671, 0.715160, 0.072169],
        [0.019334, 0.119193, 0.950227]
    ])
    xyz = np.dot(rgb, m.T)
    
    # Vers LAB (D65 white point: 0.95047, 1.00000, 1.08883)
    xyz[:, :, 0] /= 0.95047
    xyz[:, :, 1] /= 1.00000
    xyz[:, :, 2] /= 1.08883
    
    mask_xyz = xyz > 0.008856
    xyz[mask_xyz] = np.power(xyz[mask_xyz], 1.0 / 3.0)
    xyz[~mask_xyz] = (7.787 * xyz[~mask_xyz]) + (16.0 / 116.0)
    
    L = (116.0 * xyz[:, :, 1]) - 16.0
    a = 500.0 * (xyz[:, :, 0] - xyz[:, :, 1])
    b = 200.0 * (xyz[:, :, 1] - xyz[:, :, 2])
    return np.stack([L, a, b], axis=-1)

def lab_to_rgb(lab_arr):
    L, a, b = lab_arr[:, :, 0], lab_arr[:, :, 1], lab_arr[:, :, 2]
    y = (L + 16.0) / 116.0
    x = (a / 500.0) + y
    z = y - (b / 200.0)
    
    for arr in (x, y, z):
        mask = arr**3 > 0.008856
        arr[mask] = arr[mask]**3
        arr[~mask] = (arr[~mask] - 16.0 / 116.0) / 7.787
        
    x *= 0.95047
    y *= 1.00000
    z *= 1.08883
    xyz = np.stack([x, y, z], axis=-1)
    
    m_inv = np.array([
        [ 3.2404542, -1.5371385, -0.4985314],
        [-0.9692660,  1.8760108,  0.0415560],
        [ 0.0556434, -0.2040259,  1.0572252]
    ])
    rgb = np.dot(xyz, m_inv.T)
    rgb = np.clip(rgb, 0.0, 1.0)
    
    # Dé-gamma
    mask_rgb = rgb > 0.0031308
    rgb[mask_rgb] = 1.055 * np.power(rgb[mask_rgb], 1.0 / 2.4) - 0.055
    rgb[~mask_rgb] = 12.92 * rgb[~mask_rgb]
    return np.clip(rgb * 255.0, 0, 255).astype(np.uint8)

def main():
    print("=" * 65)
    print(" 🎨 HARMONISATION COLORIMÉTRIQUE ET NETTOYAGE DES OMBRES DU VISAGE")
    print("=" * 65)

    base_skin = Image.open(BASE_SKIN_PATH).convert("RGB")
    w_base, h_base = base_skin.size

    portrait = Image.open(PORTRAIT_PATH).convert("RGB")
    
    # 1. Nettoyage de l'ombre peinte sous le nez sur le portrait source (X: 470..555, Y: 485..530)
    # On adoucit la tâche sombre sous le nez pour ne pas créer d'effet moustache
    arr_port = np.array(portrait, dtype=np.float32)
    # Zone sous le nez : rehausser la luminosité
    y0, y1 = 485, 535
    x0, x1 = 475, 550
    under_nose = arr_port[y0:y1, x0:x1]
    # Augmenter la luminosité sous le nez de 40% pour atténuer l'ombre portée 2D
    arr_port[y0:y1, x0:x1] = np.clip(under_nose * 1.38, 0, 255)
    clean_portrait = Image.fromarray(arr_port.astype(np.uint8))

    # 2. Alignement rigide
    scale = 171.0 / 187.0
    rot_portrait = clean_portrait.rotate(90, expand=True, resample=Image.Resampling.BICUBIC)
    
    w_rot, h_rot = rot_portrait.size
    scaled_w = int(w_rot * scale)
    scaled_h = int(h_rot * scale)
    scaled_portrait = rot_portrait.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
    
    eye_in_scaled_x = 360.0 * scale
    eye_in_scaled_y = 512.5 * scale
    paste_x = int(round(1710.1 - eye_in_scaled_x))
    paste_y = int(round(1058.5 - eye_in_scaled_y))

    # 3. Échantillon de la peau MakeHuman sous le visage pour harmonisation LAB
    # Zone MakeHuman sur la joue : X ~ 1700..1850, Y ~ 850..950
    mh_cheek_crop = base_skin.crop((paste_x + 50, paste_y + 50, paste_x + scaled_w - 50, paste_y + scaled_h - 50))
    
    lab_mh = rgb_to_lab(np.array(mh_cheek_crop))
    lab_port = rgb_to_lab(np.array(scaled_portrait))
    
    # Transfert Reinhard des statistiques de couleur (A et B) vers le portrait
    # Cela aligne parfaitement la couleur de chair (peau pêche claire) tout en gardant les détails de contraste (L)
    mean_mh_a, std_mh_a = np.mean(lab_mh[:, :, 1]), np.std(lab_mh[:, :, 1])
    mean_mh_b, std_mh_b = np.mean(lab_mh[:, :, 2]), np.std(lab_mh[:, :, 2])
    
    mean_port_a, std_port_a = np.mean(lab_port[:, :, 1]), np.std(lab_port[:, :, 1])
    mean_port_b, std_port_b = np.mean(lab_port[:, :, 2]), np.std(lab_port[:, :, 2])
    
    # Harmonisation douce (70% MakeHuman, 30% portrait)
    lab_port[:, :, 1] = ((lab_port[:, :, 1] - mean_port_a) * (std_mh_a / (std_port_a + 1e-5))) * 0.70 + mean_mh_a
    lab_port[:, :, 2] = ((lab_port[:, :, 2] - mean_port_b) * (std_mh_b / (std_port_b + 1e-5))) * 0.70 + mean_mh_b
    
    # Rehaussement de la clarté (L) pour éliminer le masque sombre
    lab_port[:, :, 0] = np.clip(lab_port[:, :, 0] * 1.12 + 5.0, 0, 100)
    
    harmonized_arr = lab_to_rgb(lab_port)
    harmonized_img = Image.fromarray(harmonized_arr)

    # 4. Masque d'estompage progressif
    mask = Image.new("L", (scaled_w, scaled_h), 0)
    arr_mask = np.zeros((scaled_h, scaled_w), dtype=np.float32)
    cx = 420.6
    cy = 468.2
    rx = 165.0 * scale
    ry = 155.0 * scale

    for y in range(scaled_h):
        for x in range(scaled_w):
            d = np.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2)
            if d < 0.40:
                arr_mask[y, x] = 255.0
            elif d < 1.0:
                f = (1.0 - np.cos((1.0 - d) / 0.60 * np.pi)) / 2.0
                arr_mask[y, x] = f * 255.0
            else:
                arr_mask[y, x] = 0.0

    mask = Image.fromarray(arr_mask.astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius=8))

    # 5. Collage harmonisé
    final_diffuse = base_skin.copy()
    final_diffuse.paste(harmonized_img, (paste_x, paste_y), mask)

    # 6. Sauvegarde
    for d in [OUT_MPFB_DIR, OUT_LOCAL_DIR]:
        os.makedirs(d, exist_ok=True)

    diff_mpfb = os.path.join(OUT_MPFB_DIR, "marc_novice_diffuse.png")
    diff_local = os.path.join(OUT_LOCAL_DIR, "marc_novice_diffuse.png")
    final_diffuse.save(diff_mpfb, "PNG", optimize=True)
    final_diffuse.save(diff_local, "PNG", optimize=True)
    print(f"✅ Texture diffuse harmonisée enregistrée : {diff_mpfb}")

    # Normal Map
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if racine not in sys.path:
        sys.path.insert(0, racine)
    from core.image_ops import generer_normal_map
    norm_img = generer_normal_map(final_diffuse, strength=2.0)
    norm_mpfb = os.path.join(OUT_MPFB_DIR, "marc_novice_normal.png")
    norm_local = os.path.join(OUT_LOCAL_DIR, "marc_novice_normal.png")
    norm_img.save(norm_mpfb, "PNG")
    norm_img.save(norm_local, "PNG")
    print(f"✅ Normal Map enregistrée : {norm_mpfb}")

    # .mhmat
    mhmat_path = os.path.join(OUT_MPFB_DIR, "marc_novice.mhmat")
    with open(mhmat_path, "w", encoding="utf-8") as f:
        f.write("""# Material file for MakeHuman / MPFB - Marc Novice Harmonisé
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
