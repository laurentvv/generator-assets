#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/animate_ansible_nexus_wan22_i2v.py
Cinematic Image-to-Video animation with Wan 2.2 MoE Dual-DiT 28B:
- Validated starting image: output/ansible_nexus/ansible_nexus_wan22_raw.png (832x480)
- I2V MoE models: HighNoise + LowNoise Q4_K_M (8 combined steps 4+4)
- Conditioning: umt5-xxl + wan_2.1_vae + clip_vision_h
- 81 native frames sequence -> smooth interpolation to 165 frames (5.5s @ 30 FPS)
- 4K Ultra HD AI Super-Resolution (4x-UltraSharp Vulkan + AMD FidelityFX CAS 0.75 @ 50 Mbps)
"""

import os
import sys
import time
import subprocess
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

# Cinematics and movement prompt calibrated on the scene
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
    """Cleanly resizes the input image to 832x480 with a 16:9 Lanczos crop."""
    img = Image.open(input_path)
    w, h = img.size
    print(f"🖼️ Source input image: {input_path} ({w}x{h}, {os.path.getsize(input_path)/(1024*1024):.1f} MB)")

    if (w, h) == (832, 480):
        return input_path

    # Distortion-free 16:9 conform
    target_aspect = 16.0 / 9.0
    aspect = w / h
    if abs(aspect - target_aspect) > 0.01:
        new_w = int(h * target_aspect)
        offset_x = max(0, (w - new_w) // 2)
        crop_box = (offset_x, 0, offset_x + new_w, h)
        img = img.crop(crop_box)
        print(f"📐 Clean 16:9 crop: {img.size}")

    resized_path = os.path.join(OUTPUT_DIR, "scene_01_832x480_lanczos.png")
    img_832 = img.resize((832, 480), Image.Resampling.LANCZOS)
    img_832.save(resized_path, quality=100)
    print(f"✅ Wan 2.2 lead-in image prepared: {resized_path} (832x480)")
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
            raise FileNotFoundError(f"Missing required file: {r}")

def main():
    parser = argparse.ArgumentParser(description="Wan 2.2 MoE 28B I2V animation to 4K Master")
    parser.add_argument("-i", "--input", default=DEFAULT_INPUT, help="Source image (will be resized to 832x480)")
    parser.add_argument("--frames", type=int, default=81, help="Number of native Wan frames (e.g. 33, 49, 81)")
    parser.add_argument("--fps", type=int, default=16, help="Native diffusion FPS")
    parser.add_argument("--skip-upscale", action="store_true", help="Skip the 4K upscale (for a quick test)")
    args = parser.parse_args()

    print("=" * 85)
    print("🎬 [WAN 2.2 I2V MoE 28B CINEMATIC ANIMATION -> 5.5s 4K MASTER]")
    print(f"   Provided source image : {args.input}")
    print(f"   Native Wan frames     : {args.frames}")
    print(f"   Output folder         : {OUTPUT_DIR}")
    print("=" * 85)

    # Clean preparation and resizing of the image (16:9 Lanczos 832x480)
    init_image_ready = prepare_input_image(args.input)
    check_models(init_image_ready)

    # 1. Image-to-Video generation with Wan 2.2 MoE Dual-DiT (81 frames)
    print(f"\n🎥 1. Native Wan 2.2 MoE video generation ({args.frames} frames, 832x480)...")
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

    print(f"✅ Wan 2.2 raw video generated in {t_gen:.1f}s: {RAW_VIDEO_WEBM}")

    # 2. Exact temporal conform: 5.5 seconds (165 frames @ 30 FPS)
    print("\n⏱️ 2. Temporal conform and 30 FPS motion interpolation (165 frames)...")
    cmd_interp = [
        FFMPEG, "-y",
        "-i", RAW_VIDEO_WEBM,
        "-filter_complex", "minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,trim=duration=5.5",
        "-c:v", "libx264", "-crf", "14", "-preset", "slow", "-pix_fmt", "yuv420p",
        INTERP_VIDEO
    ]
    subprocess.run(cmd_interp, check=True)
    print(f"✅ Conforming 5.5s 30 FPS video: {INTERP_VIDEO}")

    if args.skip_upscale:
        print("⏩ 4K upscale skipped as requested.")
        return

    # 3. 4K Ultra HD AI Super-Resolution (4x-UltraSharp Vulkan + AMD CAS 0.75)
    print("\n🚀 3. 4K Ultra HD AI Super-Resolution (4x-UltraSharp + AMD FidelityFX CAS 0.75)...")
    cmd_upscale = [
        sys.executable,
        r"C:\GIT\generator-assets\scripts\upscale_video_ai.py",
        "--input", INTERP_VIDEO,
        "--output", MASTER_4K_VIDEO,
        "--cas", "0.75",
        "--bitrate", "50M"
    ]
    subprocess.run(cmd_upscale, check=True)
    print(f"👑 4K Ultra HD Master produced successfully: {MASTER_4K_VIDEO}")

    total_time = time.time() - t0
    print("\n" + "=" * 85)
    print(f"🏆 PIPELINE FINISHED IN {total_time:.1f}s ({total_time/60:.2f} min)!")
    print(f"   🎥 5.5s 4K UHD Master: {MASTER_4K_VIDEO}")
    print("=" * 85)

if __name__ == "__main__":
    main()
