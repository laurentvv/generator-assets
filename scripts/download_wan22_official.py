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
        "name": "Wan2.2-T2V-A14B-LowNoise-Q4_K_M.gguf",
        "url": "https://huggingface.co/QuantStack/Wan2.2-T2V-A14B-GGUF/resolve/main/LowNoise/Wan2.2-T2V-A14B-LowNoise-Q4_K_M.gguf",
        "size_gb": 9.65
    },
    {
        "name": "Wan2.2-T2V-A14B-HighNoise-Q4_K_M.gguf",
        "url": "https://huggingface.co/QuantStack/Wan2.2-T2V-A14B-GGUF/resolve/main/HighNoise/Wan2.2-T2V-A14B-HighNoise-Q4_K_M.gguf",
        "size_gb": 9.65
    }
]

def download_file(file_info):
    name = file_info["name"]
    url = file_info["url"]
    dest = os.path.join(TARGET_DIR, name)
    part_file = dest + ".part"

    if os.path.exists(dest):
        actual_size = os.path.getsize(dest)
        if actual_size > 1024 * 1024 * 1024 * 8: # > 8 GB
            print(f"✅ Déjà présent : {name} ({actual_size / (1024**3):.2f} Go)", flush=True)
            return

    print(f"\n⬇️ Téléchargement : {name} (~{file_info['size_gb']} Go)...", flush=True)
    print(f"   Source : {url}", flush=True)

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
                print(f"   Progression : {downloaded / (1024**3):.2f} / {total_size / (1024**3):.2f} Go ({pct:.1f}%) - {speed:.1f} Mo/s", flush=True)
                last_print = now

    os.replace(part_file, dest)
    print(f"✅ Terminé : {name} ({os.path.getsize(dest) / (1024**3):.2f} Go) en {time.time() - t0:.1f}s", flush=True)

def main():
    print("=" * 80, flush=True)
    print("📦 TÉLÉCHARGEMENT OFFICIEL WAN 2.2 MoE (A14B LowNoise + HighNoise)", flush=True)
    print(f"   Dossier de destination : {TARGET_DIR}", flush=True)
    print("=" * 80, flush=True)

    for f in FILES:
        download_file(f)

    print("\n🎉 SUCCÈS : Wan 2.2 MoE est prêt !", flush=True)

if __name__ == "__main__":
    main()
