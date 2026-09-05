#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/create_comparison_2.5d_vs_wan22.py
Génération d'un comparatif vidéo split-screen 50/50 en 4K Ultra HD (3840x2160) :
- Gauche : Animation 2.5D (raw_clip_01.mp4 - Motion Camera & Zoom)
- Droite : Animation IA (Wan 2.2 MoE 28B + Super-Résolution 4K CAS 0.75)
"""

import os
import sys
import subprocess
from pathlib import Path

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

FFMPEG = r"C:\Program Files\Amuse\ffmpeg.exe"
REF_25D = r"C:\GIT\ai-doc2video\projects\ansible\video_raw\raw_clip_01.mp4"
WAN_4K = r"C:\GIT\generator-assets\output\ansible_nexus\ansible_nexus_wan22_scene01_5.5s_4k_cas.mp4"
OUTPUT_SPLIT = r"C:\GIT\generator-assets\output\ansible_nexus\comparatif_split_2.5d_vs_wan22_4k.mp4"
OUTPUT_SHEET = r"C:\GIT\generator-assets\output\ansible_nexus\comparatif_split_contact_sheet.png"

def main():
    if not os.path.exists(REF_25D):
        raise FileNotFoundError(f"Vidéo 2.5D introuvable : {REF_25D}")
    if not os.path.exists(WAN_4K):
        raise FileNotFoundError(f"Vidéo Wan 2.2 4K introuvable : {WAN_4K}")

    print("=" * 80)
    print("🎬 [CRÉATION DU COMPARATIF SPLIT-SCREEN 4K]")
    print(f"   Vidéo 2.5D   : {REF_25D}")
    print(f"   Vidéo Wan 2.2: {WAN_4K}")
    print(f"   Sortie Split : {OUTPUT_SPLIT}")
    print("=" * 80)

    # Filtre FFmpeg : Split-screen 50/50 côte à côte (1920x2160 gauche + 1920x2160 droite = 3840x2160)
    # avec bande séparatrice cyan et libellés texte
    filter_complex = (
        "[0:v]scale=3840:2160,crop=1920:2160:0:0,"
        "drawtext=text='Animation 2.5D (Motion Design)':fontcolor=white:fontsize=52:box=1:boxcolor=black@0.6:boxborderw=10:x=50:y=50[left];"
        "[1:v]scale=3840:2160,crop=1920:2160:0:0,"
        "drawtext=text='Animation IA (Wan 2.2 MoE 28B + 4K CAS)':fontcolor=white:fontsize=52:box=1:boxcolor=black@0.6:boxborderw=10:x=50:y=50[right];"
        "[left][right]hstack=inputs=2[outv]"
    )

    cmd = [
        FFMPEG, "-y",
        "-i", REF_25D,
        "-i", WAN_4K,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-c:v", "h264_amf",
        "-b:v", "48M",
        "-maxrate", "55M",
        "-pix_fmt", "yuv420p",
        OUTPUT_SPLIT
    ]

    print("🚀 Encodage matériel AMF de la vidéo split-screen 4K...")
    subprocess.run(cmd, check=True)
    print(f"✅ Vidéo split-screen générée : {OUTPUT_SPLIT}")

    # Capture d'une planche contact comparative à mi-parcours (t = 2.75s)
    cmd_snap = [
        FFMPEG, "-y",
        "-ss", "00:00:02.75",
        "-i", OUTPUT_SPLIT,
        "-vframes", "1",
        OUTPUT_SHEET
    ]
    subprocess.run(cmd_snap, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"📸 Planche de capture comparative enregistrée : {OUTPUT_SHEET}")

if __name__ == "__main__":
    main()
