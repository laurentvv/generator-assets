#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/download_wan22_i2v_models.py
Direct, resilient download of the Wan 2.2 I2V MoE models (Dual-DiT 28B Image-to-Video):
- HighNoise/Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf (~8.99 GB)
- LowNoise/Wan2.2-I2V-A14B-LowNoise-Q4_K_M.gguf (~8.99 GB)
from the HuggingFace repo QuantStack/Wan2.2-I2V-A14B-GGUF into C:\\Modeles_LLM.
"""

import os
import sys
import shutil
import time
from pathlib import Path
from huggingface_hub import hf_hub_download

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

MODELS_DIR = r"C:\Modeles_LLM"
REPO_ID = "QuantStack/Wan2.2-I2V-A14B-GGUF"

FILES = [
    ("HighNoise/Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf", "Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf"),
    ("LowNoise/Wan2.2-I2V-A14B-LowNoise-Q4_K_M.gguf", "Wan2.2-I2V-A14B-LowNoise-Q4_K_M.gguf")
]

def main():
    print("=" * 80)
    print("🚀 [OFFICIAL WAN 2.2 I2V MoE 28B DOWNLOAD]")
    print(f"   Source repo: https://huggingface.co/{REPO_ID}")
    print(f"   Destination : {MODELS_DIR}")
    print("=" * 80)

    os.makedirs(MODELS_DIR, exist_ok=True)

    for remote_path, local_filename in FILES:
        target_path = os.path.join(MODELS_DIR, local_filename)
        if os.path.exists(target_path) and os.path.getsize(target_path) > 8.5 * (1024**3):
            sz = os.path.getsize(target_path) / (1024**3)
            print(f"\n✅ Already complete: {local_filename} ({sz:.2f} GB) - Skipped.")
            continue

        print(f"\n📥 Downloading: {remote_path} -> {local_filename}...")
        t0 = time.time()

        downloaded = hf_hub_download(
            repo_id=REPO_ID,
            filename=remote_path,
            local_dir=MODELS_DIR,
            local_dir_use_symlinks=False
        )

        # If hf_hub_download placed it in a HighNoise/ or LowNoise/ subfolder, move it to the root of C:\Modeles_LLM
        if downloaded != target_path and os.path.exists(downloaded):
            if os.path.exists(target_path):
                os.remove(target_path)
            shutil.move(downloaded, target_path)
            parent = Path(downloaded).parent
            try:
                parent.rmdir()
            except Exception:
                pass

        elapsed = time.time() - t0
        sz_gb = os.path.getsize(target_path) / (1024**3)
        speed = (sz_gb * 1024) / max(elapsed, 1)
        print(f"✅ Downloaded in {elapsed:.1f}s ({sz_gb:.2f} GB, {speed:.1f} MB/s): {target_path}")

    print("\n" + "=" * 80)
    print("🎉 All Wan 2.2 I2V MoE 28B models are installed and ready for animation!")
    print("=" * 80)

if __name__ == "__main__":
    main()
