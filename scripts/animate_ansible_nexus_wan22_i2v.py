#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/animate_ansible_nexus_wan22_i2v.py
Animation cinématique Image-to-Video avec Wan 2.2 MoE Dual-DiT 28B :
- Image de départ validée : output/ansible_nexus/ansible_nexus_wan22_raw.png (832x480)
- Modèles MoE I2V : HighNoise + LowNoise Q4_K_M (8 étapes combinées 4+4)
- Conditionnement : umt5-xxl + wan_2.1_vae + clip_vision_h
- Séquence 81 trames natives -> Interpolation fluide 165 trames (5,5s @ 30 FPS)
- Super-Résolution IA 4K Ultra HD (4x-UltraSharp Vulkan + AMD FidelityFX CAS 0.75 @ 50 Mbps)
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
import argparse

FFMPEG = r"C:\Program Files\Amuse\ffmpeg.exe"
MODELS_DIR = r"C:\Modeles_LLM"
OUTPUT_DIR = r"C:\GIT\generator-assets\output\ansible_nexus"
os.makedirs(OUTPUT_DIR, exist_ok=True)

DEFAULT_INPUT = r"C:\tmp\scene_01.png" if os.path.exists(r"C:\tmp\scene_01.png") else os.path.join(OUTPUT_DIR, "ansible_nexus_wan22_raw.png")

# Prompt de cinématique et de mouvement calibré sur la scène
PROMPT = (
    "Cinematic slow forward camera push-in and subtle tilt over the futuristic hybrid IT control center. "
    "Luminous cyan and amber fiber-optic streams pulsating with flowing light packets toward the glowing circular Ansible nexus. "
    "Holographic server racks glowing with active blue led activity. "
    "Floating glass Linux and Windows node badges gently hovering in isometric space. "
    "Dark mode cyberpunk aesthetics, deep obsidian background, pristine octane render, 8k resolution, clean composition, smooth fluid motion, no text, no typography."
)

NEGATIVE_PROMPT = (
    "human, person, woman, man, face, people, character, portrait, body, hands, "
    "text, typography, letters, words, logos, watermark, font, writing, labels, ui text, symbols, "
    "jitter, sudden cuts, glitch, blurry, low quality, noisy, distorted, cartoon, lowres"
)

RAW_VIDEO_WEBM = os.path.join(OUTPUT_DIR, "ansible_nexus_wan22_scene01_raw.webm")
INTERP_VIDEO = os.path.join(OUTPUT_DIR, "ansible_nexus_wan22_scene01_5.5s_30fps.mp4")
MASTER_4K_VIDEO = os.path.join(OUTPUT_DIR, "ansible_nexus_wan22_scene01_5.5s_4k_master.mp4")

def prepare_input_image(input_path: str) -> str:
    """Redimensionne proprement l'image d'entrée en 832x480 avec recadrage 16:9 Lanczos."""
    img = Image.open(input_path)
    w, h = img.size
    print(f"🖼️ Image d'entrée source : {input_path} ({w}x{h}, {os.path.getsize(input_path)/(1024*1024):.1f} Mo)")
    
    if (w, h) == (832, 480):
        return input_path

    # Conformation 16:9 sans déformation
    target_aspect = 16.0 / 9.0
    aspect = w / h
    if abs(aspect - target_aspect) > 0.01:
        new_w = int(h * target_aspect)
        offset_x = max(0, (w - new_w) // 2)
        crop_box = (offset_x, 0, offset_x + new_w, h)
        img = img.crop(crop_box)
        print(f"📐 Recadrage 16:9 propre : {img.size}")

    resized_path = os.path.join(OUTPUT_DIR, "scene_01_832x480_lanczos.png")
    img_832 = img.resize((832, 480), Image.Resampling.LANCZOS)
    img_832.save(resized_path, quality=100)
    print(f"✅ Image d'amorce Wan 2.2 préparée : {resized_path} (832x480)")
    return resized_path

def check_models(input_img: str):
    required = [
        os.path.join(MODELS_DIR, "Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf"),
        os.path.join(MODELS_DIR, "Wan2.2-I2V-A14B-LowNoise-Q4_K_M.gguf"),
        os.path.join(MODELS_DIR, "wan_2.1_vae.safetensors"),
        os.path.join(MODELS_DIR, "umt5-xxl-encoder-Q4_K_M.gguf"),
        os.path.join(MODELS_DIR, "clip_vision_h.safetensors"),
        input_img
    ]
    for r in required:
        if not os.path.exists(r):
            raise FileNotFoundError(f"Fichier requis manquant : {r}")

def main():
    parser = argparse.ArgumentParser(description="Animation I2V Wan 2.2 MoE 28B vers Master 4K")
    parser.add_argument("-i", "--input", default=DEFAULT_INPUT, help="Image source (sera redimensionnée en 832x480)")
    parser.add_argument("--frames", type=int, default=81, help="Nombre de trames natives Wan (ex: 33, 49, 81)")
    parser.add_argument("--fps", type=int, default=16, help="FPS natif de diffusion")
    parser.add_argument("--skip-upscale", action="store_true", help="Ne pas faire l'upscale 4K (pour test rapide)")
    args = parser.parse_args()

    print("=" * 85)
    print("🎬 [ANIMATION CINÉMATIQUE WAN 2.2 I2V MoE 28B -> MASTER 4K 5.5s]")
    print(f"   Image source fournie : {args.input}")
    print(f"   Trames natives Wan    : {args.frames}")
    print(f"   Dossier de sortie    : {OUTPUT_DIR}")
    print("=" * 85)

    # Préparation et redimensionnement propre de l'image (Lanczos 16:9 832x480)
    init_image_ready = prepare_input_image(args.input)
    check_models(init_image_ready)

    # 1. Génération Image-to-Video avec Wan 2.2 MoE Dual-DiT (81 frames)
    print(f"\n🎥 1. Génération vidéo native Wan 2.2 MoE ({args.frames} trames, 832x480)...")
    cmd_wan = [
        SD_CLI, "-M", "vid_gen",
        "--diffusion-model", os.path.join(MODELS_DIR, "Wan2.2-I2V-A14B-LowNoise-Q4_K_M.gguf"),
        "--high-noise-diffusion-model", os.path.join(MODELS_DIR, "Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf"),
        "--vae", os.path.join(MODELS_DIR, "wan_2.1_vae.safetensors"),
        "--t5xxl", os.path.join(MODELS_DIR, "umt5-xxl-encoder-Q4_K_M.gguf"),
        "--clip_vision", os.path.join(MODELS_DIR, "clip_vision_h.safetensors"),
        "-i", init_image_ready,
        "-p", PROMPT,
        "-n", NEGATIVE_PROMPT,
        "-W", "832", "-H", "480",
        "--video-frames", str(args.frames),
        "--fps", str(args.fps),
        "--steps", "4",
        "--high-noise-steps", "4",
        "--cfg-scale", "3.5",
        "--high-noise-cfg-scale", "3.5",
        "--sampling-method", "euler",
        "--high-noise-sampling-method", "euler",
        "--flow-shift", "3.0",
        "--vae-tiling",
        "--temporal-tiling",
        "--offload-to-cpu",
        "--backend", "diffusion=vulkan0,te=cpu",
        "-o", RAW_VIDEO_WEBM,
        "-v"
    ]

    t0 = time.time()
    subprocess.run(cmd_wan, check=True)
    t_gen = time.time() - t0

    if not os.path.exists(RAW_VIDEO_WEBM):
        for candidate in [RAW_VIDEO_WEBM.replace(".webm", "_0.webm"), RAW_VIDEO_WEBM.replace(".webm", ".avi")]:
            if os.path.exists(candidate):
                os.rename(candidate, RAW_VIDEO_WEBM)
                break

    print(f"✅ Vidéo brute Wan 2.2 générée en {t_gen:.1f}s : {RAW_VIDEO_WEBM}")

    # 2. Conformation temporelle exacte : 5,5 secondes (165 trames @ 30 FPS)
    print("\n⏱️ 2. Conformation temporelle et interpolation de mouvement 30 FPS (165 trames)...")
    cmd_interp = [
        FFMPEG, "-y",
        "-i", RAW_VIDEO_WEBM,
        "-filter_complex", "minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,trim=duration=5.5",
        "-c:v", "libx264", "-crf", "14", "-preset", "slow", "-pix_fmt", "yuv420p",
        INTERP_VIDEO
    ]
    subprocess.run(cmd_interp, check=True)
    print(f"✅ Vidéo 5.5s 30 FPS conforme : {INTERP_VIDEO}")

    if args.skip_upscale:
        print("⏩ Upscale 4K ignoré comme demandé.")
        return

    # 3. Super-Résolution IA 4K Ultra HD (4x-UltraSharp Vulkan + AMD CAS 0.75)
    print("\n🚀 3. Super-Résolution IA 4K Ultra HD (4x-UltraSharp + AMD FidelityFX CAS 0.75)...")
    cmd_upscale = [
        sys.executable,
        r"C:\GIT\generator-assets\scripts\upscale_video_ai.py",
        "--input", INTERP_VIDEO,
        "--output", MASTER_4K_VIDEO,
        "--cas", "0.75",
        "--bitrate", "50M"
    ]
    subprocess.run(cmd_upscale, check=True)
    print(f"👑 Master 4K Ultra HD produit avec succès : {MASTER_4K_VIDEO}")

    total_time = time.time() - t0
    print("\n" + "=" * 85)
    print(f"🏆 PIPELINE ACHEVÉ EN {total_time:.1f}s ({total_time/60:.2f} min) !")
    print(f"   🎥 Master 4K UHD 5.5s : {MASTER_4K_VIDEO}")
    print("=" * 85)

if __name__ == "__main__":
    main()
