#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module d'Upscaling et Super-Résolution pour Assets 2D.
Supporte :
1. ESRGAN / Real-ESRGAN sous GPU Vulkan (sd-cli -M upscale) avec préservation parfaite du canal Alpha RGBA
2. Super-résolution logicielle Smart Lanczos avec Unsharp Mask et préservation des contours
"""

import os
import subprocess
from pathlib import Path
from typing import Optional
from PIL import Image, ImageFilter, ImageOps
from core.config import (
    DEFAULT_BACKEND,
    DEFAULT_ESRGAN_MODEL,
    DEFAULT_SD_CLI,
    resoudre_upscaler,
    TEMP_IMAGE
)


def upscale_esrgan(
    image_entree: Image.Image,
    esrgan_model_path: str = DEFAULT_ESRGAN_MODEL,
    repeats: int = 1,
    sd_cli: str = DEFAULT_SD_CLI,
    backend: str = DEFAULT_BACKEND
) -> Image.Image:
    """
    Exécute le modèle ESRGAN via sd-cli sous Vulkan en préservant la transparence RGBA.
    """
    if not os.path.exists(esrgan_model_path):
        raise FileNotFoundError(f"Modèle ESRGAN introuvable : {esrgan_model_path}")

    a_alpha = image_entree.mode == "RGBA"
    
    # 1. Sauvegarder la composante RGB pour ESRGAN
    temp_in = "temp_esrgan_in.png"
    temp_out = "temp_esrgan_out.png"
    
    rgb_in = image_entree.convert("RGB")
    rgb_in.save(temp_in, "PNG")

    nom_modele = Path(esrgan_model_path).name
    print(f"[ESRGAN Vulkan] Upscaling IA avec '{nom_modele}'...")

    commande = [
        sd_cli,
        "-M", "upscale",
        "--upscale-model", esrgan_model_path,
        "-i", temp_in,
        "-o", temp_out,
        "--upscale-repeats", str(repeats),
        "--backend", backend,
        "-v"
    ]

    try:
        subprocess.run(commande, check=True)
        img_upscaled_rgb = Image.open(temp_out).convert("RGB")
        
        # 2. Si l'image source possédait de la transparence, ré-injecter l'Alpha agrandi
        if a_alpha:
            alpha_orig = image_entree.split()[-1]
            alpha_upscaled = alpha_orig.resize(img_upscaled_rgb.size, Image.Resampling.LANCZOS)
            r, g, b = img_upscaled_rgb.split()
            img_finale = Image.merge("RGBA", (r, g, b, alpha_upscaled))
            return img_finale
        else:
            return img_upscaled_rgb

    finally:
        for p in [temp_in, temp_out]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass


def upscale_smart_lanczos(
    image: Image.Image,
    target_width: int,
    target_height: int,
    unsharp_radius: float = 1.2,
    unsharp_percent: int = 130,
    unsharp_threshold: int = 3
) -> Image.Image:
    """
    Super-résolution logicielle multi-passes avec filtre Lanczos,
    masque de netteté (Unsharp Mask) et gestion propre du canal Alpha.
    """
    has_alpha = image.mode == "RGBA"
    
    if has_alpha:
        r, g, b, a = image.split()
        rgb = Image.merge("RGB", (r, g, b))
        
        rgb_upscaled = rgb.resize((target_width, target_height), Image.Resampling.LANCZOS)
        a_upscaled = a.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
        sharp_rgb = rgb_upscaled.filter(
            ImageFilter.UnsharpMask(radius=unsharp_radius, percent=unsharp_percent, threshold=unsharp_threshold)
        )
        
        r_u, g_u, b_u = sharp_rgb.split()
        return Image.merge("RGBA", (r_u, g_u, b_u, a_upscaled))
    else:
        upscaled = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        return upscaled.filter(
            ImageFilter.UnsharpMask(radius=unsharp_radius, percent=unsharp_percent, threshold=unsharp_threshold)
        )


def upscaler_asset(
    image_entree: Image.Image,
    facteur: float = 2.0,
    taille_cible: Optional[int] = None,
    mode: str = "auto",
    upscale_model: Optional[str] = None,
    sd_cli: str = DEFAULT_SD_CLI,
    backend: str = DEFAULT_BACKEND
) -> Image.Image:
    """
    Point d'entrée unifié pour l'upscaling d'assets 2D.
    Tente d'abord le modèle de super-résolution IA (ESRGAN) sur GPU Vulkan,
    avec repli automatique sur Smart Lanczos si aucun modèle n'est fourni.
    """
    largeur_init, hauteur_init = image_entree.size
    
    if taille_cible and taille_cible > 0:
        largeur_cible = taille_cible
        hauteur_cible = int(hauteur_init * (taille_cible / largeur_init))
    else:
        largeur_cible = int(largeur_init * facteur)
        hauteur_cible = int(hauteur_init * facteur)

    modele_resolu = resoudre_upscaler(upscale_model)

    # 1. Utilisation du modèle IA ESRGAN si disponible
    if mode in ["esrgan", "auto"] and modele_resolu and os.path.exists(modele_resolu) and os.path.exists(sd_cli):
        try:
            img_ia = upscale_esrgan(
                image_entree=image_entree,
                esrgan_model_path=modele_resolu,
                sd_cli=sd_cli,
                backend=backend
            )
            # Ajuster à la dimension exacte demandée si besoin
            if img_ia.size != (largeur_cible, hauteur_cible):
                img_ia = img_ia.resize((largeur_cible, hauteur_cible), Image.Resampling.LANCZOS)
            return img_ia
        except Exception as e:
            print(f"⚠️  Échec ESRGAN ({e}), basculement vers Smart Lanczos...")

    # 2. Repli vers Smart Lanczos
    print(f"🔍 [Smart Lanczos] Upscaling logiciel vers {largeur_cible}x{hauteur_cible}...")
    return upscale_smart_lanczos(image_entree, largeur_cible, hauteur_cible)
