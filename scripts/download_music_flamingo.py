import os
import shutil
import subprocess
import sys
import time

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

# Music Flamingo (NVIDIA) — music UNDERSTANDING model (analysis, no generation)
# Serves as an optional quality check for the music_bg workflow via llama-cli.
# ⚠️ NVIDIA OneWay Noncommercial license: non-commercial use only.
TARGET_DIR = os.getenv("MUSIC_FLAMINGO_DIR", r"C:\Modeles_LLM\music-flamingo")
BASE_URL = "https://huggingface.co/mradermacher/music-flamingo-hf-GGUF/resolve/main/"

FILES = [
    {"name": "music-flamingo-hf.Q4_K_M.gguf", "size_gb": 4.80},
    {"name": "music-flamingo-hf.mmproj-f16.gguf", "size_gb": 1.40},
]

curl_path = shutil.which("curl.exe") or "curl"


def telecharger(file_info):
    name = file_info["name"]
    dest = os.path.join(TARGET_DIR, name)
    os.makedirs(TARGET_DIR, exist_ok=True)

    if os.path.exists(dest) and os.path.getsize(dest) > 100 * 1024 * 1024:
        print(f"✅ Already present: {name} ({os.path.getsize(dest) / (1024**3):.2f} GB)")
        return

    print(f"\n⬇️ Downloading: {name} (~{file_info['size_gb']} GB)...")
    print(f"   Source: {BASE_URL + name}")
    part = dest + ".part"
    t0 = time.time()
    cmd = [curl_path, "-L", "-C", "-", "--fail", "--retry", "5", "--retry-delay", "3",
           "--progress-bar", "-o", part, BASE_URL + name]
    result = subprocess.run(cmd)
    if result.returncode != 0 or not os.path.exists(part):
        raise RuntimeError(f"Download of {name} failed (code {result.returncode})")
    os.replace(part, dest)
    print(f"✅ Done: {name} ({os.path.getsize(dest) / (1024**3):.2f} GB) in {time.time() - t0:.1f}s")


def main():
    print("=" * 80)
    print("📦 MUSIC FLAMINGO DOWNLOAD (OPTIONAL MUSIC ANALYSIS)")
    print(f"   Destination folder: {TARGET_DIR}")
    print("   ⚠️  Non-commercial NVIDIA license — optional QA module for the music_bg workflow")
    print("=" * 80)

    for f_info in FILES:
        telecharger(f_info)

    print("\n🎉 SUCCESS: Music Flamingo is ready (enable analysis via --analyse).")


if __name__ == "__main__":
    main()
