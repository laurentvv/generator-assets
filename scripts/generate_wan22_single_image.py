#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/generate_wan22_single_image.py
Génération d'une SEULE image de validation avec Wan 2.2 MoE (Dual-DiT 28B Photoréaliste)
suivie de la Super-Résolution IA 4K (4x-UltraSharp + AMD FidelityFX CAS 0.75).
Permet de valider l'esthétique exacte avant de lancer la cinématique vidéo.
"""

import os
import sys
import time
import subprocess
from pathlib import Path
from PIL import Image

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

SD_CLI = r"C:\SD\sd-cli.exe"
FFMPEG = r"C:\Program Files\Amuse\ffmpeg.exe"
MODELS_DIR = r"C:\Modeles_LLM"
OUTPUT_DIR = r"C:\GIT\generator-assets\output\ansible_nexus"
os.makedirs(OUTPUT_DIR, exist_ok=True)

PROMPT = (
    "A cinematic, futuristic control center visualization of a hybrid enterprise IT infrastructure. "
    "Glowing isometric holographic server racks connected by luminous cyan and amber fiber-optic data streams. "
    "Floating three-dimensional glass badges representing Linux, Windows, and lightweight appliance nodes converging into a centralized glowing Ansible control nexus. "
    "Dark mode cyberpunk aesthetics, deep navy and obsidian background, subtle grid lines, depth of field, octane render, eight-k resolution, clean composition, no text, no typography."
)

NEGATIVE_PROMPT = (
    "human, person, woman, man, face, people, character, portrait, body, hands, "
    "text, typography, letters, words, logos, watermark, font, writing, labels, ui text, symbols, "
    "blurry, soft, out of focus, low quality, noisy, distorted, glitch, cartoon, messy, lowres, oversaturated"
)

RAW_IMG = os.path.join(OUTPUT_DIR, "ansible_nexus_wan22_raw.png")
MASTER_4K_IMG = os.path.join(OUTPUT_DIR, "ansible_nexus_wan22_4k_master.png")
ZOOM_COMP = os.path.join(OUTPUT_DIR, "ansible_nexus_wan22_zoom_comparatif.png")

def main():
    print("=" * 85)
    print("👑 [VALIDATION IMAGE UNIQUE WAN 2.2 MoE 28B]")
    print(f"   Dossier de sortie : {OUTPUT_DIR}")
    print(f"   Prompt            : {PROMPT[:90]}...")
    print("=" * 85)

    # 1. Génération de l'image native avec Wan 2.2 MoE (1 seule trame)
    print("\n🎬 1. Génération Wan 2.2 MoE (Dual-DiT 4 High + 4 Low steps)...")
    cmd_wan22 = [
        SD_CLI, "-M", "vid_gen",
        "--diffusion-model", os.path.join(MODELS_DIR, "Wan2.2-T2V-A14B-LowNoise-Q4_K_M.gguf"),
        "--high-noise-diffusion-model", os.path.join(MODELS_DIR, "Wan2.2-T2V-A14B-HighNoise-Q4_K_M.gguf"),
        "--vae", os.path.join(MODELS_DIR, "wan_2.1_vae.safetensors"),
        "--t5xxl", os.path.join(MODELS_DIR, "umt5-xxl-encoder-Q4_K_M.gguf"),
        "-p", PROMPT,
        "-n", NEGATIVE_PROMPT,
        "-W", "832", "-H", "480",
        "--video-frames", "1",
        "--fps", "16",
        "--steps", "4",
        "--high-noise-steps", "4",
        "--cfg-scale", "3.5",
        "--high-noise-cfg-scale", "3.5",
        "--sampling-method", "euler",
        "--high-noise-sampling-method", "euler",
        "--flow-shift", "3.0",
        "--offload-to-cpu",
        "--backend", "diffusion=vulkan0,te=cpu",
        "-o", RAW_IMG,
        "-v"
    ]

    t0 = time.time()
    subprocess.run(cmd_wan22, check=True)
    t_gen = time.time() - t0
    
    # sd-cli peut nommer l'image avec un suffixe _0 ou l'extension directe
    if not os.path.exists(RAW_IMG):
        candidates = [
            os.path.join(OUTPUT_DIR, "ansible_nexus_wan22_raw_0.png"),
            os.path.join(OUTPUT_DIR, "ansible_nexus_wan22_raw_0.webm"),
            os.path.join(OUTPUT_DIR, "ansible_nexus_wan22_raw.webm")
        ]
        for c in candidates:
            if os.path.exists(c):
                if c.endswith(".webm"):
                    # Extraire la première trame
                    cmd_ext = [FFMPEG, "-y", "-i", c, "-vframes", "1", RAW_IMG]
                    subprocess.run(cmd_ext, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    os.rename(c, RAW_IMG)
                break

    if not os.path.exists(RAW_IMG):
        raise FileNotFoundError(f"Échec : impossible de trouver l'image brute générée {RAW_IMG}")

    print(f"✅ Image brute Wan 2.2 générée en {t_gen:.1f}s : {RAW_IMG}")

    # 2. Super-Résolution IA 4K (Real-ESRGAN 4x-UltraSharp Vulkan)
    print("\n🚀 2. Super-Résolution IA 4K (Real-ESRGAN Vulkan0)...")
    t1 = time.time()
    upscaler_model = os.path.join(MODELS_DIR, "upscalers", "4x-UltraSharp.pth")
    temp_4k = os.path.join(OUTPUT_DIR, "temp_esrgan_wan22_4k.png")
    cmd_up = [
        SD_CLI, "-M", "upscale",
        "--upscale-model", upscaler_model,
        "-i", RAW_IMG,
        "-o", temp_4k,
        "--backend", "vulkan0"
    ]
    subprocess.run(cmd_up, check=True)

    # 3. Conformation 4K Ultra HD (3840×2160) + AMD FidelityFX CAS 0.75
    print("\n✨ 3. Filtre de contraste adaptatif AMD FidelityFX CAS 0.75...")
    cmd_cas = [
        FFMPEG, "-y",
        "-i", temp_4k,
        "-vf", "scale=3840:2160:flags=lanczos,cas=0.75",
        MASTER_4K_IMG
    ]
    subprocess.run(cmd_cas, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    if os.path.exists(temp_4k):
        try: os.remove(temp_4k)
        except Exception: pass
    t_up = time.time() - t1
    print(f"✅ Master 4K Ultra HD produit en {t_up:.1f}s : {MASTER_4K_IMG}")

    # 4. Zoom comparatif 100% côte à côte (Natif vs 4K CAS 0.75)
    img_raw = Image.open(RAW_IMG).convert("RGB")
    img_up = Image.open(MASTER_4K_IMG).convert("RGB")
    img_raw_scaled = img_raw.resize(img_up.size, Image.Resampling.BICUBIC)

    w, h = img_up.size
    cx, cy = w // 2, h // 2
    crop_box = (cx - 600, cy - 450, cx + 600, cy + 450)
    crop_base = img_raw_scaled.crop(crop_box)
    crop_ai = img_up.crop(crop_box)

    comp = Image.new("RGB", (2400, 900), (0, 0, 0))
    comp.paste(crop_base, (0, 0))
    comp.paste(crop_ai, (1200, 0))
    comp.save(ZOOM_COMP, quality=95)
    print(f"🔍 Comparatif Zoom 100% créé : {ZOOM_COMP}")

    total_time = time.time() - t0
    print("\n" + "=" * 85)
    print(f"🏆 VALIDATION WAN 2.2 MoE ACHEVÉE EN {total_time:.1f}s ({total_time/60:.2f} min) !")
    print(f"   🖼️ Image Brute Native : {RAW_IMG}")
    print(f"   👑 Master 4K Ultra HD : {MASTER_4K_IMG}")
    print(f"   🔍 Zoom Comparatif 100%: {ZOOM_COMP}")
    print("=" * 85)

if __name__ == "__main__":
    main()
