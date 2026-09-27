#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/generate_ansible_nexus.py
Full production pipeline for the generation of the IT infrastructure visual:
"Ansible Hybrid IT Infrastructure Control Nexus"

Complete process:
1. Native video generation (Wan 2.1 14B or LTX-2.5 15B)
2. 4K AI Super-Resolution (Real-ESRGAN / 4x-UltraSharp on Vulkan0)
3. AMD AMF 4K Ultra HD Master conform (3840x2160 @ 50 Mbps) + AMD FidelityFX CAS
4. Extraction of the key frames for visual inspection
"""

import os
import sys
import time
import argparse
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

def create_contact_sheet(frames_dir, output_sheet_path, num_frames=4):
    """Creates a contact sheet for quick inspection."""
    files = sorted([os.path.join(frames_dir, f) for f in os.listdir(frames_dir) if f.endswith(".png")])
    if not files:
        return
    step = max(1, len(files) // num_frames)
    selected = [files[i] for i in range(0, len(files), step)][:num_frames]

    images = [Image.open(f) for f in selected]
    w, h = images[0].size
    thumb_w, thumb_h = 960, int(960 * h / w)

    sheet = Image.new("RGB", (thumb_w * 2, thumb_h * 2), (10, 10, 15))
    positions = [(0, 0), (thumb_w, 0), (0, thumb_h), (thumb_w, thumb_h)]

    for idx, img in enumerate(images):
        resized = img.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        sheet.paste(resized, positions[idx])

    sheet.save(output_sheet_path, quality=95)
    print(f"🖼️ 4K contact sheet created: {output_sheet_path}")

def run_pipeline(model_choice="wan21"):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Import of the AI upscale module
    sys.path.insert(0, str(Path(__file__).parent))
    from upscale_video_ai import upscale_video_ai

    print("=" * 85)
    print("🚀 [ANSIBLE CONTROL NEXUS PIPELINE - 4K PRODUCTION]")
    print(f"   Chosen model    : {model_choice.upper()}")
    print(f"   Output folder   : {OUTPUT_DIR}")
    print(f"   Prompt          : {PROMPT[:90]}...")
    print("=" * 85)

    raw_video = None
    master_4k = None

    t_start = time.time()

    if model_choice == "wan22":
        raw_video = os.path.join(OUTPUT_DIR, "ansible_nexus_wan22_raw.webm")
        master_4k = os.path.join(OUTPUT_DIR, "ansible_nexus_wan22_4k_master.mp4")

        cmd_gen = [
            SD_CLI, "-M", "vid_gen",
            "--diffusion-model", os.path.join(MODELS_DIR, "Wan2.2-T2V-A14B-LowNoise-Q4_K_M.gguf"),
            "--high-noise-diffusion-model", os.path.join(MODELS_DIR, "Wan2.2-T2V-A14B-HighNoise-Q4_K_M.gguf"),
            "--vae", os.path.join(MODELS_DIR, "wan_2.1_vae.safetensors"),
            "--t5xxl", os.path.join(MODELS_DIR, "umt5-xxl-encoder-Q4_K_M.gguf"),
            "-p", PROMPT,
            "-n", NEGATIVE_PROMPT,
            "-W", "832", "-H", "480",
            "--video-frames", "17",
            "--fps", "16",
            "--steps", "4",
            "--high-noise-steps", "4",
            "--cfg-scale", "3.5",
            "--high-noise-cfg-scale", "3.5",
            "--sampling-method", "euler",
            "--high-noise-sampling-method", "euler",
            "--flow-shift", "3.0",
            "--offload-to-cpu",
            "--temporal-tiling",
            "--vae-tiling",
            "--backend", "diffusion=vulkan0,te=cpu",
            "-o", raw_video,
            "-v"
        ]

    elif model_choice == "wan21":
        raw_video = os.path.join(OUTPUT_DIR, "ansible_nexus_wan21_raw.webm")
        master_4k = os.path.join(OUTPUT_DIR, "ansible_nexus_wan21_4k_master.mp4")

        cmd_gen = [
            SD_CLI, "-M", "vid_gen",
            "--diffusion-model", os.path.join(MODELS_DIR, "wan2.1-t2v-14b-Q4_K_M.gguf"),
            "--vae", os.path.join(MODELS_DIR, "wan_2.1_vae.safetensors"),
            "--t5xxl", os.path.join(MODELS_DIR, "umt5-xxl-encoder-Q4_K_M.gguf"),
            "-p", PROMPT,
            "-n", NEGATIVE_PROMPT,
            "-W", "832", "-H", "480",
            "--video-frames", "17",
            "--fps", "16",
            "--steps", "10",
            "--sampling-method", "euler",
            "--cfg-scale", "6.0",
            "--flow-shift", "3.0",
            "--temporal-tiling",
            "--vae-tiling",
            "--backend", "diffusion=vulkan0,te=cpu",
            "-o", raw_video,
            "-v"
        ]

    elif model_choice == "ltx25":
        raw_video = os.path.join(OUTPUT_DIR, "ansible_nexus_ltx25_raw.webm")
        master_4k = os.path.join(OUTPUT_DIR, "ansible_nexus_ltx25_4k_master.mp4")

        cmd_gen = [
            SD_CLI, "-M", "vid_gen",
            "--diffusion-model", os.path.join(MODELS_DIR, "LTX-2.5-Distilled-Q4_K_M.gguf"),
            "--vae", os.path.join(MODELS_DIR, "ltx-2.5-video-vae-conv-bf16.safetensors"),
            "--audio-vae", os.path.join(MODELS_DIR, "ltx-2.5-audio-vae-bf16.safetensors"),
            "--llm", os.path.join(MODELS_DIR, "gemma4-12b-with-proj-ltx-2.5-Q5_K_M.gguf"),
            "-p", PROMPT,
            "-W", "768", "-H", "512",
            "--video-frames", "33",
            "--fps", "24",
            "--steps", "8",
            "--sigmas", "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0",
            "--sampling-method", "euler_a",
            "--cfg-scale", "1.0",
            "--backend", "diffusion=vulkan0,te=cpu,vae=cpu",
            "-o", raw_video,
            "-v"
        ]
    else:
        raise ValueError(f"Unknown model: {model_choice}")

    # Step 1: video generation
    print(f"\n🎬 1. Native video generation with {model_choice.upper()}...")
    t_gen_start = time.time()
    subprocess.run(cmd_gen, check=True)
    t_gen_end = time.time()
    print(f"✅ Raw video generated in {t_gen_end - t_gen_start:.1f}s: {raw_video}")

    # Step 2: 4K AI Super-Resolution
    print("\n🚀 2. 4K AI Super-Resolution (Real-ESRGAN Vulkan + FidelityFX CAS 0.75)...")
    upscale_video_ai(
        input_video=raw_video,
        output_video=master_4k,
        target_res="3840:2160",
        bitrate="50M",
        cas_strength=0.75
    )

    # Step 3: extraction of the 4K frames for inspection
    frames_dir = os.path.join(OUTPUT_DIR, f"frames_{model_choice}")
    os.makedirs(frames_dir, exist_ok=True)
    print("\n📸 3. Extraction of the 4K Master frames for quality control...")
    cmd_extract = [
        FFMPEG, "-y", "-i", master_4k,
        os.path.join(frames_dir, "frame_%03d.png")
    ]
    subprocess.run(cmd_extract, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    sheet_path = os.path.join(OUTPUT_DIR, f"planche_contact_{model_choice}_4k.png")
    create_contact_sheet(frames_dir, sheet_path)

    # Step 4: creation of the high-fidelity zoom comparison (Frame 10)
    zoom_comp_path = os.path.join(OUTPUT_DIR, f"comparatif_zoom_{model_choice}_4k_cas075.png")
    try:
        # Extract raw frame 10
        raw_trame = os.path.join(OUTPUT_DIR, f"trame_brute_{model_choice}.png")
        cmd_t = [FFMPEG, "-y", "-ss", "0.4", "-i", raw_video, "-vframes", "1", raw_trame]
        subprocess.run(cmd_t, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        up_trame = os.path.join(frames_dir, "frame_010.png")
        if not os.path.exists(up_trame):
            # Fallback first frame
            up_trame = sorted([os.path.join(frames_dir, f) for f in os.listdir(frames_dir) if f.endswith(".png")])[0]

        if os.path.exists(raw_trame) and os.path.exists(up_trame):
            img_raw = Image.open(raw_trame).convert("RGB")
            img_up = Image.open(up_trame).convert("RGB")

            # Bicubic upscale baseline for a direct comparison
            img_raw_scaled = img_raw.resize(img_up.size, Image.Resampling.BICUBIC)

            # Central 1200x900 crop for a surgical zoom
            w, h = img_up.size
            cx, cy = w // 2, h // 2
            crop_box = (cx - 600, cy - 450, cx + 600, cy + 450)

            crop_base = img_raw_scaled.crop(crop_box)
            crop_ai = img_up.crop(crop_box)

            # Side-by-side montage
            comp = Image.new("RGB", (2400, 900), (0, 0, 0))
            comp.paste(crop_base, (0, 0))
            comp.paste(crop_ai, (1200, 0))
            comp.save(zoom_comp_path, quality=95)
            print(f"🔍 100% Zoom Comparison created: {zoom_comp_path}")
    except Exception as e:
        print(f"⚠️ Error creating the zoom comparison: {e}")

    total_time = time.time() - t_start
    print("\n" + "=" * 85)
    print(f"🏆 PIPELINE COMPLETED SUCCESSFULLY IN {total_time:.1f}s ({total_time/60:.2f} min)!")
    print(f"   🎬 4K Ultra HD Master: {master_4k}")
    print(f"   🖼️ Inspection sheet: {sheet_path}")
    print("=" * 85)
    return master_4k, sheet_path

def main():
    parser = argparse.ArgumentParser(description="Ansible Control Nexus 4K generation")
    parser.add_argument("--model", choices=["wan22", "wan21", "ltx25"], default="wan22",
                        help="Render model (wan22 for ultimate MoE photorealism, wan21 for 3D geometry, ltx25 for native audio)")
    args = parser.parse_args()

    run_pipeline(args.model)

if __name__ == "__main__":
    main()
