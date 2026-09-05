#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/download_wan22_i2v_models.py
Téléchargement direct et résilient des modèles Wan 2.2 I2V MoE (Dual-DiT 28B Image-to-Video) :
- HighNoise/Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf (~8.99 Go)
- LowNoise/Wan2.2-I2V-A14B-LowNoise-Q4_K_M.gguf (~8.99 Go)
depuis le dépôt HuggingFace QuantStack/Wan2.2-I2V-A14B-GGUF vers C:\\Modeles_LLM.
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
    print("🚀 [TÉLÉCHARGEMENT OFFICIEL WAN 2.2 I2V MoE 28B]")
    print(f"   Dépôt source : https://huggingface.co/{REPO_ID}")
    print(f"   Destination  : {MODELS_DIR}")
    print("=" * 80)

    os.makedirs(MODELS_DIR, exist_ok=True)

    for remote_path, local_filename in FILES:
        target_path = os.path.join(MODELS_DIR, local_filename)
        if os.path.exists(target_path) and os.path.getsize(target_path) > 8.5 * (1024**3):
            sz = os.path.getsize(target_path) / (1024**3)
            print(f"\n✅ Déjà complet : {local_filename} ({sz:.2f} Go) - Ignoré.")
            continue

        print(f"\n📥 Téléchargement en cours : {remote_path} -> {local_filename}...")
        t0 = time.time()
        
        downloaded = hf_hub_download(
            repo_id=REPO_ID,
            filename=remote_path,
            local_dir=MODELS_DIR,
            local_dir_use_symlinks=False
        )
        
        # Si hf_hub_download l'a placé dans un sous-dossier HighNoise/ ou LowNoise/, le déplacer à la racine de C:\Modeles_LLM
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
        print(f"✅ Téléchargé en {elapsed:.1f}s ({sz_gb:.2f} Go, {speed:.1f} Mo/s) : {target_path}")

    print("\n" + "=" * 80)
    print("🎉 Tous les modèles Wan 2.2 I2V MoE 28B sont installés et prêts pour l'animation !")
    print("=" * 80)

if __name__ == "__main__":
    main()
