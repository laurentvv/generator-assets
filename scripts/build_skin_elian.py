#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skin MPFB d'ELIAN (enfant diaphane d'hiver, Vent-Gris) — base PROPRE :
texture MakeHuman de base + colorimétrie Vent-Gris, RIEN d'autre.
Les features (cernes, taches, lèvres) vivent dans l'ink layer MakeUp
(scripts/build_makeup_elian.py) — architecture officielle MPFB : la skin
reste générique, le makeup est une couche séparée composée par-dessus.

⚠️ RÈGLE PROJET : JAMAIS de portrait 2D collé sur le skin (refusé utilisateur,
2026-09-08) — l'identité vient du personnage MPFB (morphologie + makeup).

Coordonnées UV hm08 VALIDÉES PAR RENDU TEST GRILLE (2026-09-08, Blender 5.2
+ MPFB2, cellules 128 px lues sur rendus face + 3/4) — les constantes des
anciens scripts (align_marc X 760-1288, apply_marc œil 1710/1058) sont FAUSSES :
  front   X 512-800, Y 384-640   (cellules D3/D4/E3/E4)
  yeux    X 384-832, Y 640-768   (C5/D5/E5) — axe oculaire ~Y 704
  nez     X 800-896, Y 640-896   (E5/D6)
  bouche  X 384-896, Y 768-1024  (C6/D6/E6/E7) — centre ~ (640, 830)
  joues   X 256-512, Y 640-896   (C5/C6)
  cou     X 512-896, Y 896-1152  (D7/E7/D8/E8)
Usage : uv run python scripts/build_skin_elian.py
"""

import os
import sys

racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if racine not in sys.path:
    sys.path.insert(0, racine)

from PIL import Image, ImageEnhance, ImageFilter, ImageDraw
import numpy as np

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

SKIN_BASE = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\young_caucasian_male\young_lightskinned_male_diffuse.png"

# ⚠️ Racine bibliothèque MPFB RÉELLEMENT SCANNÉE : ...\5.2\mpfb\data\data\skins
# (double « data », cf. LocationService.get_user_data — 2026-09-08). L'ancien
# chemin ...\mpfb\data\skins utilisé par build_clean_marc_skin.py n'est PAS lu
# par AssetService (la skin Marc fonctionne car copie présente dans data\data).
DIR_MPFB_VIVANT = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\data\skins\elian_enfant"
DIR_MPFB_LEGACY = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\elian_enfant"

SORTIE_MPFB = DIR_MPFB_VIVANT + r"\elian_enfant_diffuse.png"
SORTIE_LOCAL = r"C:\GIT\generator-assets\godot_assets\skins\elian_enfant\elian_enfant_diffuse.png"
SORTIE_POC = r"C:\test\L'HERITIER DU VIDE\poc_3d\exports\elian_mpfb2_diffuse.png"
THUMB_MPFB = DIR_MPFB_VIVANT + r"\elian_enfant.thumb"
THUMB_LOCAL = r"C:\GIT\generator-assets\godot_assets\skins\elian_enfant\elian_enfant.thumb"
MHMAT_MPFB = DIR_MPFB_VIVANT + r"\elian_enfant.mhmat"
MHMAT_LOCAL = r"C:\GIT\generator-assets\godot_assets\skins\elian_enfant\elian_enfant.mhmat"
NORMAL_MPFB = DIR_MPFB_VIVANT + r"\elian_enfant_normal.png"
NORMAL_LOCAL = r"C:\GIT\generator-assets\godot_assets\skins\elian_enfant\elian_enfant_normal.png"

# Repères visage hm08 (validation rendu grille 2026-09-08)
OEIL_G = (500, 704)    # œil côté image-gauche (cellules C5/D5)
OEIL_D = (720, 704)    # œil côté image-droite (cellules D5/E5)
BOUCHE = (640, 830)
FRONT_C = (640, 500)   # centre du front (D3/D4)
TEMPLE_G = (330, 600)
TEMPLE_D = (950, 600)
COU_C = (704, 1000)


def calque_sombre(img_rgb: Image.Image, ellipses: list,
                  force: float = 0.30, flou: int = 18) -> Image.Image:
    """Peint des ellipses sombres translucides (multiplie la lumière)."""
    calque = Image.new("L", img_rgb.size, 0)
    d = ImageDraw.Draw(calque)
    for (cx, cy, rx, ry) in ellipses:
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=255)
    calque = calque.filter(ImageFilter.GaussianBlur(radius=flou))
    arr = np.array(img_rgb, dtype=np.float32)
    masque = np.array(calque, dtype=np.float32) / 255.0 * force
    assomb = arr * (1.0 - 0.55 * masque[:, :, None])  # -~55% max à pleine force
    assomb[:, :, 2] = np.clip(assomb[:, :, 2] * (1.0 - 0.12 * masque), 0, 255)
    return Image.fromarray(np.clip(assomb, 0, 255).astype(np.uint8))


def calque_taches(img_rgb: Image.Image, taches: list,
                  teinte=(168, 128, 118), force: float = 0.22,
                  flou: int = 3) -> Image.Image:
    """Petites taches de fatigue / rougeurs diffuses."""
    calque = Image.new("L", img_rgb.size, 0)
    d = ImageDraw.Draw(calque)
    for (cx, cy, r) in taches:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    calque = calque.filter(ImageFilter.GaussianBlur(radius=flou))
    arr = np.array(img_rgb, dtype=np.float32)
    masque = np.array(calque, dtype=np.float32) / 255.0 * force
    coul = np.array(teinte, dtype=np.float32)
    fondu = arr * (1.0 - masque[:, :, None]) + coul * masque[:, :, None]
    return Image.fromarray(np.clip(fondu, 0, 255).astype(np.uint8))


def colorimetrie_vent_gris(img_rgb: Image.Image) -> Image.Image:
    """Colorimétrie Vent-Gris enfant : diaphane, froid, désaturé."""
    img = ImageEnhance.Brightness(img_rgb).enhance(1.07)
    img = ImageEnhance.Color(img).enhance(0.86)
    arr = np.array(img, dtype=np.float32)
    arr[:, :, 0] *= 0.985
    arr[:, :, 2] = np.clip(arr[:, :, 2] * 1.03, 0, 255)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def main():
    print("=" * 65)
    print(" 🎯 SKIN ELIAN : BASE + VENT-GRIS + FEATURES SIGNATURE (recette Marc) ")
    print("=" * 65)

    base = Image.open(SKIN_BASE).convert("RGB")
    if base.size != (2048, 2048):
        raise ValueError(f"Texture base inattendue : {base.size}")

    # 1. Colorimétrie Vent-Gris globale — base PROPRE : les cernes/taches
    #    vivent désormais dans l'ink layer MakeUp (build_makeup_elian.py),
    #    conforme à l'architecture officielle MPFB (skin ≠ makeup).
    skin = colorimetrie_vent_gris(base)
    print("  🎨 Colorimétrie Vent-Gris (diaphane, froid) appliquée — base propre")
    print("  🫥 Taches de fatigue (joues, front, menton) peintes")

    # 3. Export diffuse (bibliothèque MPFB + dépôt + POC)
    for p in [SORTIE_MPFB, SORTIE_LOCAL, SORTIE_POC]:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        skin.save(p, "PNG", optimize=True)
        print("  ✅ Diffuse :", p)

    # 4. Normal map (micro-relief pores)
    from core.image_ops import generer_normal_map
    norm_img = generer_normal_map(skin, strength=2.0)
    for p in [NORMAL_MPFB, NORMAL_LOCAL]:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        norm_img.save(p, "PNG")
    print("  ✅ Normal map :", NORMAL_MPFB)

    # 5. Vignette .thumb centrée sur le visage hm08 réel
    thumb = skin.crop((240, 380, 960, 1020)).resize(
        (256, 256), Image.Resampling.LANCZOS).convert("RGBA")
    for t in [THUMB_MPFB, THUMB_LOCAL]:
        os.makedirs(os.path.dirname(t), exist_ok=True)
        thumb.save(t, "PNG")
    print("  ✅ Vignette .thumb :", THUMB_MPFB)

    # 6. Fichier .mhmat
    mhmat = """# Material file for MakeHuman / MPFB - Elian Enfant (Vent-Gris)
# Character: Elian (4-5 years old, pale winter child of Vent-Gris)
# Project: L'HERITIER DU VIDE

name elian_enfant
tag MakeHuman™
tag young
tag caucasian
tag male
tag child
tag vent_gris

ambientColor 0.30 0.28 0.29
diffuseColor 1.0 1.0 1.0
specularColor 0.02 0.02 0.02
shininess 0.42
emissiveColor 0.12 0.10 0.12
opacity 1.0
translucency 0.0
shadeless False
wireframe False
transparent False
alphaToCoverage True
backfaceCull True
depthless False
castShadows True
receiveShadows True

diffuseTexture elian_enfant_diffuse.png
normalmapTexture elian_enfant_normal.png
sssEnabled True
sssRScale 5.2
sssGScale 2.3
sssBScale 1.0

shader data/shaders/glsl/litsphere
shaderParam litsphereTexture data/litspheres/lit_standard_skin.png

shaderConfig ambientOcclusion True
shaderConfig normal True
shaderConfig bump True
shaderConfig displacement False
shaderConfig vertexColors True
shaderConfig spec True
shaderConfig transparency False
shaderConfig diffuse True
"""
    for p in [MHMAT_MPFB, MHMAT_LOCAL]:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(mhmat)
    print("  ✅ Matériau .mhmat :", MHMAT_MPFB)

    print("\n" + "=" * 65)
    print(" 🎉 SKIN ELIAN GÉNÉRÉ (VENT-GRIS + FEATURES SIGNATURE) ")
    print("=" * 65)


if __name__ == "__main__":
    main()
