#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/create_comparison_2.5d_vs_wan22.py
Generation of a 50/50 split-screen 4K Ultra HD (3840x2160) video comparison:
- Left: 2.5D animation (raw_clip_01.mp4 - Camera Motion & Zoom)
- Right: AI animation (Wan 2.2 MoE 28B + 4K CAS 0.75 super-resolution)
"""

import os
import sys
import subprocess

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
        raise FileNotFoundError(f"2.5D video not found: {REF_25D}")
    if not os.path.exists(WAN_4K):
        raise FileNotFoundError(f"Wan 2.2 4K video not found: {WAN_4K}")

    print("=" * 80)
    print("🎬 [CREATING THE 4K SPLIT-SCREEN COMPARISON]")
    print(f"   2.5D video   : {REF_25D}")
    print(f"   Wan 2.2 video: {WAN_4K}")
    print(f"   Split output : {OUTPUT_SPLIT}")
    print("=" * 80)

    # FFmpeg filter: 50/50 side-by-side split screen (1920x2160 left + 1920x2160 right = 3840x2160)
    # with a cyan separator bar and text labels
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

    print("🚀 AMF hardware encoding of the 4K split-screen video...")
    subprocess.run(cmd, check=True)
    print(f"✅ Split-screen video generated: {OUTPUT_SPLIT}")

    # Capture of a comparative contact sheet at midpoint (t = 2.75s)
    cmd_snap = [
        FFMPEG, "-y",
        "-ss", "00:00:02.75",
        "-i", OUTPUT_SPLIT,
        "-vframes", "1",
        OUTPUT_SHEET
    ]
    subprocess.run(cmd_snap, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"📸 Comparative capture sheet saved: {OUTPUT_SHEET}")

if __name__ == "__main__":
    main()
