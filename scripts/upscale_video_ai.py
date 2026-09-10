#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/upscale_video_ai.py
Module et CLI de Super-Résolution Vidéo IA 4K / 1080p pour generator-assets.
Exécute Real-ESRGAN / 4x-UltraSharp frame par frame sur AMD Radeon RX 6950 XT (Vulkan),
préserve la piste audio native, et encode en AMD AMF Hardware Ultra HD.
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
# ffmpeg 9.0.1 custom prioritaire (règle §1.10 MEMORY_BANK) ; l'ancien build
# Amuse 7.1.1 a disparu avec la migration MSYS2 du 2026-09-09.
FFMPEG = r"C:\ffmpeg\dist\bin\ffmpeg.exe"
if not os.path.exists(FFMPEG):
    FFMPEG = r"C:\Program Files\Amuse\ffmpeg.exe"
DEFAULT_MODEL = r"C:\Modeles_LLM\upscalers\4x-UltraSharp.pth"

def get_video_info(video_path):
    """Extrait le framerate, la durée et la présence d'audio via ffprobe/ffmpeg."""
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
        raise FileNotFoundError(f"Vidéo source introuvable : {input_video}")
    if not os.path.exists(upscaler_model):
        raise FileNotFoundError(f"Modèle upscaler introuvable : {upscaler_model}")

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
    print(f"🚀 [SUPER-RÉSOLUTION VIDÉO IA 4K] : {Path(input_video).name}")
    print(f"   Modèle IA    : {Path(upscaler_model).name}")
    print(f"   Framerate    : {fps} FPS | Audio : {'OUI (préservé)' if has_audio else 'NON (muet)'}")
    print(f"   Résolution   : {target_res} | Débit : {bitrate} (AMD AMF)")
    print(f"   Destination  : {output_video}")
    print("=" * 80)

    # 1. Extraction des trames
    print("\n📸 1. Extraction des trames sources...")
    cmd_extract = [
        FFMPEG, "-y", "-i", input_video,
        # -vsync retiré en ffmpeg 9.0 → -fps_mode (build custom 9.0.1)
        "-fps_mode", "passthrough", "-q:v", "2",
        os.path.join(raw_frames, "frame_%04d.png")
    ]
    subprocess.run(cmd_extract, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    frames = sorted([f for f in os.listdir(raw_frames) if f.endswith(".png")])
    total = len(frames)
    print(f"   -> {total} trames prêtes pour le traitement IA.")

    # 2. Upscaling IA Vulkan trame par trame
    print(f"\n⚡ 2. Traitement par réseau de neurones Vulkan ({total} trames)...")
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
            print(f"   [Trame {idx}/{total}] Reconstruite en {elapsed_f:.2f}s")
        else:
            print(f"   [Trame {idx}/{total}] Déjà en cache.")

    t_upscale = time.time() - t0
    print(f"\n✅ Upscaling terminé en {t_upscale:.1f}s ({t_upscale/60:.2f} min, moy. {t_upscale/total:.1f}s/trame) !")

    # 3. Assemblage & Conformation Master 4K
    print("\n🎬 3. Encodage Master 4K matériel (AMD AMF + FidelityFX CAS)...")
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

    # Nettoyage
    try:
        shutil.rmtree(work_dir)
    except Exception:
        pass

    print(f"\n🏆 MASTER VIDÉO 4K DISPONIBLE : {output_video}")
    return output_video

def main():
    parser = argparse.ArgumentParser(description="Super-Résolution Vidéo IA 4K / 1080p sous Vulkan")
    parser.add_argument("input", help="Chemin du fichier vidéo source (.webm ou .mp4)")
    parser.add_argument("-o", "--output", help="Chemin du master de sortie", default=None)
    parser.add_argument("-m", "--model", help="Modèle ESRGAN", default=DEFAULT_MODEL)
    parser.add_argument("-r", "--res", help="Résolution cible (ex: 3840:2160 ou 1920:1080)", default="3840:2160")
    parser.add_argument("-b", "--bitrate", help="Débit vidéo (ex: 45M)", default="50M")
    parser.add_argument("--cas", help="Intensité AMD CAS", type=float, default=0.3)
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
