#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automatic model download script: image base (Flux.1 Dev,
CLIP-L/T5-XXL encoders, VAE, LFM2.5 LLM), Upscaling (ESRGAN), ONNX (RMBG,
DeepBump, RIFE) and DiT Video Models (Wan 2.1 1.3B / 14B).

The target paths match the default values of core/config.py
(MODEL_DIR root, overridable via the MODEL_DIR environment variable).
"""

import argparse
import os
import shutil
import subprocess
import sys
import urllib.request

# Windows console: force UTF-8 for emojis/accents
for flux in (sys.stdout, sys.stderr):
    if hasattr(flux, "reconfigure"):
        flux.reconfigure(encoding="utf-8", errors="replace")

DOSSIER_MODELES = os.getenv("MODEL_DIR", r"C:\Modeles_LLM")
DOSSIER_UPSCALERS = os.path.join(DOSSIER_MODELES, "upscalers")
DOSSIER_ONNX = os.path.join(DOSSIER_MODELES, "onnx")
DOSSIER_LORAS = os.path.join(DOSSIER_MODELES, "loras")

# 2D image base: default engine (Flux.1 Dev Q6_K) + encoders + VAE + art
# director LLM. The official BFL FLUX.1-dev repo is gated: we go through
# the usual non-gated mirrors (city96 / comfyanonymous) — ae.safetensors
# (VAE fp16, ~335 MB) is identical between FLUX.1-schnell and dev (Apache/MIT).
# SDXL Juggernaut (Civitai, login required) remains a manual download.
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
    """Downloads a remote file with resume (curl or python streaming)."""
    nom_fichier = os.path.basename(destination)
    if not force and os.path.exists(destination):
        taille_mo = os.path.getsize(destination) / (1024 * 1024)
        if taille_mo > 1:
            print(f"✅ Already present: {nom_fichier} ({taille_mo:.1f} MB)")
            return

    os.makedirs(os.path.dirname(os.path.abspath(destination)), exist_ok=True)
    print(f"⏳ Downloading {nom_fichier}...")
    print(f"   Source: {url}")
    print(f"   Target: {destination}")

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
                print(f"🎉 Successfully downloaded via curl: {nom_fichier} ({taille_mo:.1f} MB)\n")
                return
        except Exception as e:
            print(f"⚠️  curl failure ({e}), switching to urllib...")

    try:
        urllib.request.urlretrieve(url, destination)
        taille_mo = os.path.getsize(destination) / (1024 * 1024)
        print(f"🎉 Successfully downloaded: {nom_fichier} ({taille_mo:.1f} MB)\n")
    except Exception as e:
        print(f"❌ Error while downloading {nom_fichier}: {e}\n")


def main():
    parser = argparse.ArgumentParser(description="AI model download manager for generator-assets.")
    parser.add_argument(
        "--pack",
        choices=["all", "base", "onnx", "upscalers", "video", "video-1.3b", "video-14b", "video-vae"],
        default="base",
        help="Model pack to download (default: base / Flux.1 image base)."
    )
    parser.add_argument("--force", action="store_true", help="Forces the re-download even if the file exists.")
    args = parser.parse_args()

    os.makedirs(DOSSIER_MODELES, exist_ok=True)
    os.makedirs(DOSSIER_UPSCALERS, exist_ok=True)
    os.makedirs(DOSSIER_ONNX, exist_ok=True)
    os.makedirs(DOSSIER_LORAS, exist_ok=True)

    print("=" * 70)
    print(" 🚀 AI Model Manager (Flux.1, Wan 2.1 Videos, ONNX, Upscalers)")
    print(f" 📂 Target location: {DOSSIER_MODELES}")
    print("=" * 70)

    if args.pack in ("all", "base"):
        print("\n--- 2D Image Base: Flux.1 Dev Q6_K + encoders + VAE + LLM (~10 GB) ---")
        for nom, url in IMAGE_BASE_URLS.items():
            dest = os.path.join(DOSSIER_MODELES, nom)
            telecharger_avec_progression(url, dest, force=args.force)

    if args.pack in ("video", "video-1.3b", "all"):
        print("\n--- Wan 2.1 Video Pack (1.3B Fast & Light ~5.2 GB total) ---")
        for nom, url in VIDEO_1_3B_URLS.items():
            dest = os.path.join(DOSSIER_MODELES, nom)
            telecharger_avec_progression(url, dest, force=args.force)

    if args.pack in ("video-14b",):
        print("\n--- Wan 2.1 Video Pack (14B High-Definition Studio ~25 GB total) ---")
        for nom, url in VIDEO_14B_URLS.items():
            dest = os.path.join(DOSSIER_MODELES, nom)
            telecharger_avec_progression(url, dest, force=args.force)

    if args.pack in ("video-vae",):
        print("\n--- Wan 2.1 Video VAE Decoder (~242 MB) ---")
        for nom, url in VIDEO_VAE_URLS.items():
            dest = os.path.join(DOSSIER_MODELES, nom)
            telecharger_avec_progression(url, dest, force=args.force)

    if args.pack in ("all", "onnx"):
        print("\n--- Light ONNX Neural Models (Matting, PBR, Smoothness) ---")
        for nom, url in ONNX_URLS.items():
            dest = os.path.join(DOSSIER_ONNX, nom)
            telecharger_avec_progression(url, dest, force=args.force)

    if args.pack in ("all", "upscalers"):
        print("\n--- ESRGAN Upscaling Models ---")
        for nom, url in UPSCALERS_URLS.items():
            dest = os.path.join(DOSSIER_UPSCALERS, nom)
            telecharger_avec_progression(url, dest, force=args.force)

    print("\n" + "=" * 70)
    print("✨ Downloads finished or successfully verified!")
    print(f"👉 Models installed in: {DOSSIER_MODELES}")
    print("🎬 To test a video:")
    print('   uv run python main.py -w video "a flying dragon in a stormy sky" --frames 33 --fps 24')
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
