#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de téléchargement automatique des modèles d'Upscaling (ESRGAN), ONNX (RMBG, DeepBump, RIFE) et LoRAs.
"""

import argparse
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

ONNX_URLS = {
    "rmbg-1.4.onnx": "https://huggingface.co/briaai/RMBG-1.4/resolve/main/onnx/model.onnx",
    "deepbump256.onnx": "https://huggingface.co/shiertier/deepbump/resolve/main/deepbump256.onnx",
    "rife_fp32.onnx": "https://huggingface.co/FuryTMP/RIFE_fp32/resolve/main/RIFE_fp32.onnx"
}

DOSSIER_UPSCALERS = r"C:\Modeles_LLM\upscalers"
DOSSIER_ONNX = r"C:\Modeles_LLM\onnx"
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
    parser = argparse.ArgumentParser(description="Gestionnaire de téléchargement des modèles IA pour generator-assets.")
    parser.add_argument("--pack", choices=["all", "onnx", "upscalers"], default="all", help="Pack de modèles à télécharger.")
    args = parser.parse_args()

    os.makedirs(DOSSIER_UPSCALERS, exist_ok=True)
    os.makedirs(DOSSIER_ONNX, exist_ok=True)
    os.makedirs(DOSSIER_LORAS, exist_ok=True)

    print("=" * 60)
    print(" 🚀 Gestionnaire de Modèles IA (ONNX, Upscalers & LoRAs)")
    print("=" * 60)

    if args.pack in ("all", "onnx"):
        print("\n--- 1. Modèles Neuronaux Légers ONNX (Détourage, PBR, Fluidité) ---")
        for nom, url in ONNX_URLS.items():
            dest = os.path.join(DOSSIER_ONNX, nom)
            telecharger_avec_progression(url, dest)

    if args.pack in ("all", "upscalers"):
        print("\n--- 2. Modèles d'Upscaling ESRGAN ---")
        for nom, url in UPSCALERS_URLS.items():
            dest = os.path.join(DOSSIER_UPSCALERS, nom)
            telecharger_avec_progression(url, dest)

    print("\n--- 3. Guide pour l'ajout de LoRAs SDXL / Flux.1 ---")
    print(f"Dossier cible pour vos LoRAs (.safetensors) :")
    print(f"👉 {DOSSIER_LORAS}")
    print("\nSources recommandées pour télécharger des LoRAs de styles 2D / Pixel Art / Icons :")
    print("• CivitAI : https://civitai.com/models")
    print("• HuggingFace : https://huggingface.co/models\n")


if __name__ == "__main__":
    main()
