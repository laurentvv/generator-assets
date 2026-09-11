#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de téléchargement automatique des modèles : socle image (Flux.1 Dev,
encodeurs CLIP-L/T5-XXL, VAE, LLM LFM2.5), Upscaling (ESRGAN), ONNX (RMBG,
DeepBump, RIFE) et Modèles Vidéo DiT (Wan 2.1 1.3B / 14B).

Les chemins cibles correspondent aux valeurs par défaut de core/config.py
(racine de MODEL_DIR, surchargeable via la variable d'environnement MODEL_DIR).
"""

import argparse
import os
import shutil
import subprocess
import sys
import urllib.request

# Console Windows : force l'UTF-8 pour les emojis/accents
for flux in (sys.stdout, sys.stderr):
    if hasattr(flux, "reconfigure"):
        flux.reconfigure(encoding="utf-8", errors="replace")

DOSSIER_MODELES = os.getenv("MODEL_DIR", r"C:\Modeles_LLM")
DOSSIER_UPSCALERS = os.path.join(DOSSIER_MODELES, "upscalers")
DOSSIER_ONNX = os.path.join(DOSSIER_MODELES, "onnx")
DOSSIER_LORAS = os.path.join(DOSSIER_MODELES, "loras")

# Socle image 2D : moteur par défaut (Flux.1 Dev Q6_K) + encodeurs + VAE + LLM
# directeur artistique. Le dépôt officiel BFL FLUX.1-dev est gated : on passe
# par les miroirs non gated usuels (city96 / comfyanonymous) — ae.safetensors
# (VAE fp16, ~335 Mo) est identique entre FLUX.1-schnell et dev (Apache/MIT).
# SDXL Juggernaut (Civitai, login requis) reste un téléchargement manuel.
IMAGE_BASE_URLS = {
    "flux1-dev-Q6_K.gguf": "https://huggingface.co/city96/FLUX.1-dev-gguf/resolve/main/flux1-dev-Q6_K.gguf",
    "clip_l.safetensors": "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors",
    "t5xxl_fp16.safetensors": "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp16.safetensors",
    "ae.safetensors": "https://huggingface.co/alisher123/Flux1-dev-vae/resolve/main/ae.safetensors",
    "LFM2.5-8B-A1B-Q6_K.gguf": "https://huggingface.co/LiquidAI/LFM2.5-8B-A1B-GGUF/resolve/main/LFM2.5-8B-A1B-Q6_K.gguf",
}

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

VIDEO_VAE_URLS = {
    "wan_2.1_vae.safetensors": "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors"
}

VIDEO_1_3B_URLS = {
    "wan_2.1_vae.safetensors": "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors",
    "umt5-xxl-encoder-Q4_K_M.gguf": "https://huggingface.co/city96/umt5-xxl-encoder-gguf/resolve/main/umt5-xxl-encoder-Q4_K_M.gguf",
    "wan2.1_t2v_1.3b-q8_0.gguf": "https://huggingface.co/calcuis/wan-1.3b-gguf/resolve/main/wan2.1_t2v_1.3b-q8_0.gguf"
}

VIDEO_14B_URLS = {
    "wan_2.1_vae.safetensors": "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors",
    "umt5-xxl-encoder-Q8_0.gguf": "https://huggingface.co/city96/umt5-xxl-encoder-gguf/resolve/main/umt5-xxl-encoder-Q8_0.gguf",
    "wan2.1-i2v-14b-480p-Q4_K_M.gguf": "https://huggingface.co/city96/Wan2.1-I2V-14B-480P-gguf/resolve/main/wan2.1-i2v-14b-480p-Q4_K_M.gguf",
    "wan2.1-t2v-14b-Q4_K_M.gguf": "https://huggingface.co/city96/Wan2.1-T2V-14B-gguf/resolve/main/wan2.1-t2v-14b-Q4_K_M.gguf",
    "clip_vision_h.safetensors": "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors"
}


def telecharger_avec_progression(url: str, destination: str, force: bool = False):
    """Télécharge un fichier distant avec reprise (curl ou streaming python)."""
    nom_fichier = os.path.basename(destination)
    if not force and os.path.exists(destination):
        taille_mo = os.path.getsize(destination) / (1024 * 1024)
        if taille_mo > 1:
            print(f"✅ Déjà présent : {nom_fichier} ({taille_mo:.1f} Mo)")
            return

    os.makedirs(os.path.dirname(os.path.abspath(destination)), exist_ok=True)
    print(f"⏳ Téléchargement de {nom_fichier}...")
    print(f"   Source : {url}")
    print(f"   Cible  : {destination}")

    curl_path = shutil.which("curl.exe") or shutil.which("curl")
    if curl_path:
        commande = [
            curl_path,
            "-L",
            "-C", "-",
            "--progress-bar",
            "--fail",
            "-o", destination,
            url
        ]
        try:
            res = subprocess.run(commande)
            if res.returncode == 0 and os.path.exists(destination):
                taille_mo = os.path.getsize(destination) / (1024 * 1024)
                print(f"🎉 Téléchargé avec succès via curl : {nom_fichier} ({taille_mo:.1f} Mo)\n")
                return
        except Exception as e:
            print(f"⚠️  Échec curl ({e}), bascule sur urllib...")

    try:
        urllib.request.urlretrieve(url, destination)
        taille_mo = os.path.getsize(destination) / (1024 * 1024)
        print(f"🎉 Téléchargé avec succès : {nom_fichier} ({taille_mo:.1f} Mo)\n")
    except Exception as e:
        print(f"❌ Erreur lors du téléchargement de {nom_fichier} : {e}\n")


def main():
    parser = argparse.ArgumentParser(description="Gestionnaire de téléchargement des modèles IA pour generator-assets.")
    parser.add_argument(
        "--pack",
        choices=["all", "base", "onnx", "upscalers", "video", "video-1.3b", "video-14b", "video-vae"],
        default="base",
        help="Pack de modèles à télécharger (défaut : base / socle image Flux.1)."
    )
    parser.add_argument("--force", action="store_true", help="Force le re-téléchargement même si le fichier existe.")
    args = parser.parse_args()

    os.makedirs(DOSSIER_MODELES, exist_ok=True)
    os.makedirs(DOSSIER_UPSCALERS, exist_ok=True)
    os.makedirs(DOSSIER_ONNX, exist_ok=True)
    os.makedirs(DOSSIER_LORAS, exist_ok=True)

    print("=" * 70)
    print(" 🚀 Gestionnaire de Modèles IA (Flux.1, Vidéos Wan 2.1, ONNX, Upscalers)")
    print(f" 📂 Emplacement cible : {DOSSIER_MODELES}")
    print("=" * 70)

    if args.pack in ("all", "base"):
        print("\n--- Socle Image 2D : Flux.1 Dev Q6_K + encodeurs + VAE + LLM (~10 Go) ---")
        for nom, url in IMAGE_BASE_URLS.items():
            dest = os.path.join(DOSSIER_MODELES, nom)
            telecharger_avec_progression(url, dest, force=args.force)

    if args.pack in ("video", "video-1.3b", "all"):
        print("\n--- Pack Vidéo Wan 2.1 (1.3B Rapide & Léger ~5.2 Go total) ---")
        for nom, url in VIDEO_1_3B_URLS.items():
            dest = os.path.join(DOSSIER_MODELES, nom)
            telecharger_avec_progression(url, dest, force=args.force)

    if args.pack in ("video-14b",):
        print("\n--- Pack Vidéo Wan 2.1 (14B Haute Définition Studio ~25 Go total) ---")
        for nom, url in VIDEO_14B_URLS.items():
            dest = os.path.join(DOSSIER_MODELES, nom)
            telecharger_avec_progression(url, dest, force=args.force)

    if args.pack in ("video-vae",):
        print("\n--- Décodeur VAE Vidéo Wan 2.1 (~242 Mo) ---")
        for nom, url in VIDEO_VAE_URLS.items():
            dest = os.path.join(DOSSIER_MODELES, nom)
            telecharger_avec_progression(url, dest, force=args.force)

    if args.pack in ("all", "onnx"):
        print("\n--- Modèles Neuronaux Légers ONNX (Détourage, PBR, Fluidité) ---")
        for nom, url in ONNX_URLS.items():
            dest = os.path.join(DOSSIER_ONNX, nom)
            telecharger_avec_progression(url, dest, force=args.force)

    if args.pack in ("all", "upscalers"):
        print("\n--- Modèles d'Upscaling ESRGAN ---")
        for nom, url in UPSCALERS_URLS.items():
            dest = os.path.join(DOSSIER_UPSCALERS, nom)
            telecharger_avec_progression(url, dest, force=args.force)

    print("\n" + "=" * 70)
    print("✨ Téléchargements terminés ou vérifiés avec succès !")
    print(f"👉 Modèles installés dans : {DOSSIER_MODELES}")
    print("🎬 Pour tester une vidéo :")
    print('   uv run python main.py -w video "un dragon volant dans un ciel d orage" --frames 33 --fps 24')
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
