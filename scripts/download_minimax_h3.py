import os
import sys
import time
import urllib.request

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

TARGET_DIR = r"C:\Modeles_LLM"
os.makedirs(TARGET_DIR, exist_ok=True)

FILES = [
    {
        "name": "minimax_h3_audio_vae_fp32.safetensors",
        "url": "https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_audio_vae_fp32.safetensors",
        "size_gb": 0.60
    },
    {
        "name": "minimax_h3_video_vae_fp16.safetensors",
        "url": "https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_video_vae_fp16.safetensors",
        "size_gb": 4.85
    },
    {
        "name": "minimax_h3_fl2va_pruned-Q4_K_M.gguf",
        "url": "https://huggingface.co/leejet/MiniMax-H3-GGUF/resolve/main/minimax_h3_fl2va_pruned-Q4_K_M.gguf",
        "size_gb": 11.42
    },
    {
        "name": "qwen3vl_32b_minimax_h3-Q2_K_M.gguf",
        "url": "https://huggingface.co/leejet/MiniMax-H3-GGUF/resolve/main/qwen3vl_32b_minimax_h3-Q2_K_M.gguf",
        "size_gb": 12.19
    }
]

def download_file(file_info):
    name = file_info["name"]
    url = file_info["url"]
    dest = os.path.join(TARGET_DIR, name)
    part_file = dest + ".part"

    if os.path.exists(dest):
        actual_size = os.path.getsize(dest)
        if actual_size > 1024 * 1024 * 100: # > 100 MB
            print(f"✅ Déjà présent : {name} ({actual_size / (1024**3):.2f} Go)")
            return

    print(f"\n⬇️ Téléchargement : {name} (~{file_info['size_gb']} Go)...")
    print(f"   Source : {url}")

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp, open(part_file, "wb") as out_f:
        total_size = int(resp.headers.get("content-length", 0))
        downloaded = 0
        chunk_size = 1024 * 1024 * 8 # 8 MB chunks
        t0 = time.time()
        last_print = t0

        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            out_f.write(chunk)
            downloaded += len(chunk)
            now = time.time()
            if now - last_print >= 5.0:
                speed = (downloaded / (1024 * 1024)) / (now - t0 + 1e-6)
                pct = (downloaded / total_size * 100) if total_size > 0 else 0
                print(f"   Progression : {downloaded / (1024**3):.2f} / {total_size / (1024**3):.2f} Go ({pct:.1f}%) - {speed:.1f} Mo/s")
                last_print = now

    os.replace(part_file, dest)
    print(f"✅ Terminé avec succès : {name} ({os.path.getsize(dest) / (1024**3):.2f} Go) en {time.time() - t0:.1f}s")

def main():
    print("=" * 80)
    print("📦 TÉLÉCHARGEMENT DE LA SUITE COMPLÈTE MINIMAX-H3 (T2VA)")
    print(f"   Dossier de destination : {TARGET_DIR}")
    print("=" * 80)

    for f in FILES:
        download_file(f)

    print("\n🎉 SUCCÈS : Tous les composants MiniMax-H3 sont prêts !")

if __name__ == "__main__":
    main()
