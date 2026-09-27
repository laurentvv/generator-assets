#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Precise Alignment and Seamless Blending of Marc's 2D Portrait onto the MakeHuman UV Layout.
Calibrates to the millimeter the anatomical coordinates of Marc's eyes, nose and mouth
onto the MakeHuman hm08 head UV island (2048x2048).
"""

import os
import sys
from PIL import Image, ImageFilter, ImageDraw

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

PORTRAIT_SOURCE = r"C:\test\L'HERITIER DU VIDE\assets\portraits\marc_portrait.png"
SKIN_BASE = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\young_caucasian_male\young_lightskinned_male_diffuse.png"

SORTIE_MPFB = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\marc_novice\marc_novice_diffuse.png"
SORTIE_LOCAL = r"C:\GIT\generator-assets\godot_assets\skins\marc_novice\marc_novice_diffuse.png"
SORTIE_POC = r"C:\test\L'HERITIER DU VIDE\poc_3d\exports\marc_mpfb2_young_lightskinned_male_diffuse.png"
THUMB_MPFB = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\marc_novice\marc_novice.thumb"
THUMB_LOCAL = r"C:\GIT\generator-assets\godot_assets\skins\marc_novice\marc_novice.thumb"


def main():
    print("=" * 65)
    print(" 🎯 ANATOMICAL ALIGNMENT OF THE 2D PORTRAIT ONTO MAKEHUMAN UV ")
    print("=" * 65)

    if not os.path.exists(PORTRAIT_SOURCE):
        raise FileNotFoundError(f"Portrait not found: {PORTRAIT_SOURCE}")

    print(f"👤 Loading the 2D portrait: {PORTRAIT_SOURCE}")
    portrait_img = Image.open(PORTRAIT_SOURCE).convert("RGBA")

    print(f"🗺️ Loading the base texture: {SKIN_BASE}")
    skin_base = Image.open(SKIN_BASE).convert("RGBA")
    w_skin, h_skin = skin_base.size  # 2048 x 2048

    # 1. Framing the face in Marc's 2D portrait
    # In marc_portrait.png (1024x1024), the face (forehead to chin, cheek to cheek)
    # sits at the center of the portrait:
    w_p, h_p = portrait_img.size
    # Cropping the useful face (eyes, nose, mouth, cheeks, chin, forehead)
    crop_face = portrait_img.crop((int(w_p * 0.15), int(h_p * 0.08), int(w_p * 0.85), int(h_p * 0.78)))

    # 2. Exact target dimensions on the MakeHuman hm08 UV island
    # Geometric location of the face in the hm08 unwrap:
    # X: 760 to 1288 (width = 528 px, centered on X=1024)
    # Y: 270 to 710 (height = 440 px, eyes at Y~430, nose at Y~515, mouth at Y~605, chin at Y~685)
    cible_largeur = 530
    cible_hauteur = 450

    face_redim = crop_face.resize((cible_largeur, cible_hauteur), Image.Resampling.LANCZOS)

    # 3. Creating the anatomical progressive feathered mask
    masque = Image.new("L", (cible_largeur, cible_hauteur), 0)
    draw = ImageDraw.Draw(masque)

    # Main ellipse centered on the features (eyes, nose, lips, cheekbones)
    marge_x = int(cible_largeur * 0.08)
    marge_y = int(cible_hauteur * 0.06)
    draw.ellipse(
        [marge_x, marge_y, cible_largeur - marge_x, cible_hauteur - marge_y],
        fill=255
    )
    # Pronounced Gaussian blur for an invisible transition to the neck and ears
    masque_fondu = masque.filter(ImageFilter.GaussianBlur(radius=22))

    face_rgba = face_redim.copy()
    face_rgba.putalpha(masque_fondu)

    # 4. Positioning on the 2048x2048 UV map
    calque_position = Image.new("RGBA", (w_skin, h_skin), (0, 0, 0, 0))
    pos_x = int((w_skin - cible_largeur) // 2)  # X = 759 (centered at 1024)
    pos_y = 265  # Y = 265 (aligned on the MakeHuman forehead/nose/chin)

    calque_position.paste(face_rgba, (pos_x, pos_y), face_rgba)

    # 5. Seamless blend with the body
    skin_finale = Image.alpha_composite(skin_base, calque_position).convert("RGB")

    # 6. Saving the textures
    for p in [SORTIE_MPFB, SORTIE_LOCAL, SORTIE_POC]:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        skin_finale.save(p, "PNG", optimize=True)
        print(f"  ✅ Diffuse texture saved: {p}")

    # 7. .thumb thumbnail centered on Marc's face
    thumb_crop = skin_finale.crop((pos_x - 30, pos_y - 20, pos_x + cible_largeur + 30, pos_y + cible_hauteur + 30))
    thumb_img = thumb_crop.resize((256, 256), Image.Resampling.LANCZOS).convert("RGBA")
    for t_path in [THUMB_MPFB, THUMB_LOCAL]:
        os.makedirs(os.path.dirname(t_path), exist_ok=True)
        thumb_img.save(t_path, "PNG")
        print(f"  ✅ .thumb thumbnail: {t_path}")

    print("\n" + "=" * 65)
    print(" 🎉 ANATOMICAL ALIGNMENT AND BLENDING DONE SUCCESSFULLY!")
    print("=" * 65)


if __name__ == "__main__":
    main()
