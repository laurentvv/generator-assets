#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de téléchargement automatique des modèles d'Upscaling (ESRGAN) et LoRAs recommandés.
"""

import os
import sys
import urllib.request

# Console Windows : force l'UTF-8 pour les emojis/accents
for flux in (sys.stdout, sys.stderr):
    if hasattr(flux, "reconfigure"):
        flux.reconfigure(encoding="utf-8", errors="replace")

UPSCALERS_URLS = {
    "RealESRGAN_x4plus_anime_6B.pth": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth",
    "RealESRGAN_x4plus.pth": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
    "4x-UltraSharp.pth": "https://huggingface.co/uwg/upscaler/resolve/main/ESRGAN/4x-UltraSharp.pth"
}

DOSSIER_UPSCALERS = r"C:\Modeles_LLM\upscalers"
DOSSIER_LORAS = r"C:\Modeles_LLM\loras"


def telecharger_avec_progression(url: str, destination: str):
    """Télécharge un fichier distant avec affichage de la progression."""
    nom_fichier = os.path.basename(destination)
    if os.path.exists(destination):
        taille_mo = os.path.getsize(destination) / (1024 * 1024)
        print(f"✅ Déjà présent : {nom_fichier} ({taille_mo:.1f} Mo)")
        return

    print(f"⏳ Téléchargement de {nom_fichier} depuis {url}...")
    try:
        urllib.request.urlretrieve(url, destination)
        taille_mo = os.path.getsize(destination) / (1024 * 1024)
        print(f"🎉 Téléchargé avec succès : {nom_fichier} ({taille_mo:.1f} Mo)\n")
    except Exception as e:
        print(f"❌ Erreur lors du téléchargement de {nom_fichier} : {e}\n")


def main():
    os.makedirs(DOSSIER_UPSCALERS, exist_ok=True)
    os.makedirs(DOSSIER_LORAS, exist_ok=True)

    print("=" * 60)
    print(" 🚀 Gestionnaire de Modèles d'Upscaling & LoRAs")
    print("=" * 60)

    print("\n--- 1. Téléchargement des Modèles d'Upscaling ESRGAN ---")
    for nom, url in UPSCALERS_URLS.items():
        dest = os.path.join(DOSSIER_UPSCALERS, nom)
        telecharger_avec_progression(url, dest)

    print("--- 2. Guide pour l'ajout de LoRAs Flux.1 ---")
    print(f"Dossier cible pour vos LoRAs Flux.1 (.safetensors) :")
    print(f"👉 {DOSSIER_LORAS}")
    print("\nSources recommandées pour télécharger des LoRAs de styles 2D / Pixel Art / Icons :")
    print("• CivitAI (Filtrer par Modèle: Flux.1 D) : https://civitai.com/models?baseModel=Flux.1%20D")
    print("• HuggingFace Flux LoRAs : https://huggingface.co/models?other=flux&other=lora")
    print("\nExemple d'utilisation une fois le fichier placé dans le dossier :")
    print("  python main.py \"épée de givre\" -l \"mon_lora_style:0.8\"\n")


if __name__ == "__main__":
    main()
