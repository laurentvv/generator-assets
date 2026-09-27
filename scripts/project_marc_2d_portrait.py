#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Transfer and Projection of Marc's Canonical 2D Portrait onto the MakeHuman/MPFB UV Texture.
Takes Marc's high-definition 2D facial features (hazel eyes, dark circles, pale complexion,
chapped lips, soot) and inlays them with a soft seamless fade onto the skin map.
"""

import os
import sys
from PIL import Image, ImageFilter

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

CHEMIN_PORTRAIT_MARC = r"C:\test\L'HERITIER DU VIDE\poc_3d\renders\marc_v2_visage_closeup.png"
CHEMIN_PORTRAIT_BEAUTY = r"C:\test\L'HERITIER DU VIDE\poc_3d\renders\marc_complete_beauty_portrait.png"
CHEMIN_SKIN_BASE = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\young_caucasian_male\young_lightskinned_male_diffuse.png"
DOSSIER_SORTIE_MPFB = r"C:\Users\laurent\AppData\Roaming\Blender Foundation\Blender\5.2\mpfb\data\skins\marc_novice"
DOSSIER_SORTIE_PROJET = r"C:\GIT\generator-assets\godot_assets\skins\marc_novice"
DOSSIER_EXPORTS_POC = r"C:\test\L'HERITIER DU VIDE\poc_3d\exports"


def transferer_portrait_2d_vers_skin_uv(
    chemin_portrait: str = CHEMIN_PORTRAIT_MARC,
    chemin_skin_base: str = CHEMIN_SKIN_BASE,
    dossier_mpfb: str = DOSSIER_SORTIE_MPFB
) -> dict:
    """
    Inlays Marc's real 2D face onto the MakeHuman UV skin texture.
    """
    if not os.path.exists(chemin_portrait):
        if os.path.exists(CHEMIN_PORTRAIT_BEAUTY):
            chemin_portrait = CHEMIN_PORTRAIT_BEAUTY
        else:
            raise FileNotFoundError(f"2D portrait not found: {chemin_portrait}")

    print(f"👤 Loading Marc's 2D portrait: {chemin_portrait}")
    portrait_img = Image.open(chemin_portrait).convert("RGBA")

    print(f"🗺️ Loading the base UV skin texture: {chemin_skin_base}")
    skin_img = Image.open(chemin_skin_base).convert("RGBA")
    w, h = skin_img.size  # 2048 x 2048

    # 1. Preparing Marc's face
    # The head in the MakeHuman hm08 UV unwrap is located at the top center:
    # Head center: X ~ 1024 (50%), Y ~ 550 (27%)
    largeur_visage_uv = int(w * 0.44)  # ~900 px
    hauteur_visage_uv = int(h * 0.44)  # ~900 px

    visage_redim = portrait_img.resize((largeur_visage_uv, hauteur_visage_uv), Image.Resampling.LANCZOS)

    # 2. Creating a soft elliptical feathered mask
    masque_alpha = Image.new("L", (largeur_visage_uv, hauteur_visage_uv), 0)
    import PIL.ImageDraw as ImageDraw
    draw = ImageDraw.Draw(masque_alpha)

    # Ellipse centered on the essential features (eyes, nose, mouth, cheeks, chin)
    marge_x = int(largeur_visage_uv * 0.08)
    marge_y = int(hauteur_visage_uv * 0.08)
    draw.ellipse(
        [marge_x, marge_y, largeur_visage_uv - marge_x, hauteur_visage_uv - marge_y],
        fill=255
    )
    # Pronounced Gaussian blur for an invisible, seamless transition with the skin
    masque_fondu = masque_alpha.filter(ImageFilter.GaussianBlur(radius=38))

    # Applying the alpha mask to Marc's face
    visage_rgba = visage_redim.copy()
    visage_rgba.putalpha(masque_fondu)

    # 3. Precise positioning on the MakeHuman head UV zone
    calque_positionne = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pos_x = int((w - largeur_visage_uv) // 2)
    pos_y = int(h * 0.08)  # Top-centered placement

    calque_positionne.paste(visage_rgba, (pos_x, pos_y), visage_rgba)

    # 4. Blending with the body skin
    skin_finale = Image.alpha_composite(skin_img, calque_positionne).convert("RGB")

    # 5. Saves into Blender MPFB and into the project
    os.makedirs(dossier_mpfb, exist_ok=True)
    os.makedirs(DOSSIER_SORTIE_PROJET, exist_ok=True)

    chemins_sauvegarde = [
        os.path.join(dossier_mpfb, "marc_novice_diffuse.png"),
        os.path.join(DOSSIER_SORTIE_PROJET, "marc_novice_diffuse.png"),
    ]

    if os.path.exists(DOSSIER_EXPORTS_POC):
        chemins_sauvegarde.append(os.path.join(DOSSIER_EXPORTS_POC, "marc_mpfb2_young_lightskinned_male_diffuse.png"))

    for chemin in chemins_sauvegarde:
        skin_finale.save(chemin, "PNG", optimize=True)
        print(f"✅ Diffuse texture with Marc's real 2D face exported: {chemin}")

    # 6. Updating the MPFB .thumb thumbnail
    thumb_crop = skin_finale.crop((int(w * 0.30), int(h * 0.08), int(w * 0.70), int(h * 0.48)))
    thumb_img = thumb_crop.resize((256, 256), Image.Resampling.LANCZOS).convert("RGBA")

    thumb_mpfb = os.path.join(dossier_mpfb, "marc_novice.thumb")
    thumb_proj = os.path.join(DOSSIER_SORTIE_PROJET, "marc_novice.thumb")
    thumb_img.save(thumb_mpfb, "PNG")
    thumb_img.save(thumb_proj, "PNG")
    print(f"✅ .thumb thumbnail updated: {thumb_mpfb}")

    return {
        "portrait_source": chemin_portrait,
        "diffuse_mpfb": chemins_sauvegarde[0],
        "thumb_mpfb": thumb_mpfb,
        "resolution": skin_finale.size
    }


if __name__ == "__main__":
    res = transferer_portrait_2d_vers_skin_uv()
    print("\n🎉 Marc's real 2D face successfully inlaid onto the UV skin texture!")
