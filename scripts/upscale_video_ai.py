#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/upscale_video_ai.py
Module and CLI of 4K / 1080p AI Video Super-Resolution for generator-assets.
Runs Real-ESRGAN / 4x-UltraSharp frame by frame on AMD Radeon RX 6950 XT (Vulkan),
preserves the native audio track, and encodes in AMD AMF Hardware Ultra HD.
"""

import os
import sys
import time
import argparse
import subprocess
import shutil
from pathlib import Path

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

SD_CLI = r"C:\SD\sd-cli.exe"
# custom ffmpeg 9.0.1 takes priority (rule §1.10 MEMORY_BANK); the old
# Amuse 7.1.1 build disappeared with the MSYS2 migration of 2026-09-09.
FFMPEG = r"C:\ffmpeg\dist\bin\ffmpeg.exe"
if not os.path.exists(FFMPEG):
    FFMPEG = r"C:\Program Files\Amuse\ffmpeg.exe"
DEFAULT_MODEL = r"C:\Modeles_LLM\upscalers\4x-UltraSharp.pth"

def get_video_info(video_path):
    """Extracts the framerate, the duration and the audio presence via ffprobe/ffmpeg."""
    cmd = [FFMPEG, "-i", video_path]
    res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace")
    err = res.stderr

    fps = 24.0
    for line in err.splitlines():
        if "Stream #0:0" in line and "fps" in line:
            parts = line.split(",")
            for p in parts:
                if "fps" in p:
                    try:
                        fps = float(p.strip().split()[0])
                    except Exception:
                        pass
    has_audio = "Stream #0:1" in err or "Audio:" in err
    return fps, has_audio

def upscale_video_ai(
    input_video: str,
    output_video: str = None,
    upscaler_model: str = DEFAULT_MODEL,
    target_res: str = "3840:2160",
    bitrate: str = "50M",
    cas_strength: float = 0.3,
    work_dir: str = None
) -> str:
    if not os.path.exists(input_video):
        raise FileNotFoundError(f"Source video not found: {input_video}")
    if not os.path.exists(upscaler_model):
        raise FileNotFoundError(f"Upscaler model not found: {upscaler_model}")

    base_name = Path(input_video).stem
    if not output_video:
        output_video = os.path.join(os.path.dirname(os.path.abspath(input_video)), f"{base_name}_4k_ai.mp4")

    if not work_dir:
        work_dir = os.path.join(os.path.dirname(os.path.abspath(output_video)), f"temp_upscale_{base_name}")

    raw_frames = os.path.join(work_dir, "raw")
    up_frames = os.path.join(work_dir, "upscaled")
    os.makedirs(raw_frames, exist_ok=True)
    os.makedirs(up_frames, exist_ok=True)

    fps, has_audio = get_video_info(input_video)

    print("=" * 80)
    print(f"🚀 [4K AI VIDEO SUPER-RESOLUTION]: {Path(input_video).name}")
    print(f"   AI model     : {Path(upscaler_model).name}")
    print(f"   Framerate    : {fps} FPS | Audio: {'YES (preserved)' if has_audio else 'NO (silent)'}")
    print(f"   Resolution   : {target_res} | Bitrate: {bitrate} (AMD AMF)")
    print(f"   Destination  : {output_video}")
    print("=" * 80)

    # 1. Frame extraction
    print("\n📸 1. Extraction of the source frames...")
    cmd_extract = [
        FFMPEG, "-y", "-i", input_video,
        # -vsync removed in ffmpeg 9.0 → -fps_mode (custom 9.0.1 build)
        "-fps_mode", "passthrough", "-q:v", "2",
        os.path.join(raw_frames, "frame_%04d.png")
    ]
    subprocess.run(cmd_extract, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    frames = sorted([f for f in os.listdir(raw_frames) if f.endswith(".png")])
    total = len(frames)
    print(f"   -> {total} frames ready for the AI processing.")

    # 2. Vulkan AI upscaling frame by frame
    print(f"\n⚡ 2. Vulkan neural network processing ({total} frames)...")
    t0 = time.time()
    for idx, fname in enumerate(frames, 1):
        in_f = os.path.join(raw_frames, fname)
        out_f = os.path.join(up_frames, fname)

        if not os.path.exists(out_f) or os.path.getsize(out_f) < 10000:
            tf = time.time()
            cmd_up = [
                SD_CLI, "-M", "upscale",
                "--upscale-model", upscaler_model,
                "-i", in_f,
                "-o", out_f,
                "--backend", "vulkan0"
            ]
            subprocess.run(cmd_up, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            elapsed_f = time.time() - tf
            print(f"   [Frame {idx}/{total}] Reconstructed in {elapsed_f:.2f}s")
        else:
            print(f"   [Frame {idx}/{total}] Already cached.")

    t_upscale = time.time() - t0
    print(f"\n✅ Upscaling finished in {t_upscale:.1f}s ({t_upscale/60:.2f} min, avg. {t_upscale/total:.1f}s/frame)!")

    # 3. Assembly & 4K Master Conform
    print("\n🎬 3. Hardware 4K Master encoding (AMD AMF + FidelityFX CAS)...")
    frame_pattern = os.path.join(up_frames, "frame_%04d.png")
    vf_filter = f"scale={target_res}:flags=lanczos,cas={cas_strength}"

    if has_audio:
        cmd_asm = [
            FFMPEG, "-y",
            "-framerate", str(fps),
            "-i", frame_pattern,
            "-i", input_video,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-vf", vf_filter,
            "-c:v", "h264_amf", "-b:v", bitrate,
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            output_video
        ]
    else:
        cmd_asm = [
            FFMPEG, "-y",
            "-framerate", str(fps),
            "-i", frame_pattern,
            "-vf", vf_filter,
            "-c:v", "h264_amf", "-b:v", bitrate,
            "-pix_fmt", "yuv420p",
            output_video
        ]
    subprocess.run(cmd_asm, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    # Cleanup
    try:
        shutil.rmtree(work_dir)
    except Exception:
        pass

    print(f"\n🏆 4K VIDEO MASTER AVAILABLE: {output_video}")
    return output_video

def main():
    parser = argparse.ArgumentParser(description="4K / 1080p AI Video Super-Resolution under Vulkan")
    parser.add_argument("input", help="Path of the source video file (.webm or .mp4)")
    parser.add_argument("-o", "--output", help="Path of the output master", default=None)
    parser.add_argument("-m", "--model", help="ESRGAN model", default=DEFAULT_MODEL)
    parser.add_argument("-r", "--res", help="Target resolution (e.g. 3840:2160 or 1920:1080)", default="3840:2160")
    parser.add_argument("-b", "--bitrate", help="Video bitrate (e.g. 45M)", default="50M")
    parser.add_argument("--cas", help="AMD CAS strength", type=float, default=0.3)
    args = parser.parse_args()

    upscale_video_ai(
        input_video=args.input,
        output_video=args.output,
        upscaler_model=args.model,
        target_res=args.res,
        bitrate=args.bitrate,
        cas_strength=args.cas
    )

if __name__ == "__main__":
    main()
