import os
import shutil
import subprocess
import sys
import time

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

# Music Flamingo (NVIDIA) — modèle de COMPRÉHENSION musicale (analyse, pas de génération)
# Sert de contrôle qualité optionnel au workflow music_bg via llama-cli.
# ⚠️ Licence NVIDIA OneWay Noncommercial : usage non commercial uniquement.
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
        print(f"✅ Déjà présent : {name} ({os.path.getsize(dest) / (1024**3):.2f} Go)")
        return

    print(f"\n⬇️ Téléchargement : {name} (~{file_info['size_gb']} Go)...")
    print(f"   Source : {BASE_URL + name}")
    part = dest + ".part"
    t0 = time.time()
    cmd = [curl_path, "-L", "-C", "-", "--fail", "--retry", "5", "--retry-delay", "3",
           "--progress-bar", "-o", part, BASE_URL + name]
    result = subprocess.run(cmd)
    if result.returncode != 0 or not os.path.exists(part):
        raise RuntimeError(f"Échec du téléchargement de {name} (code {result.returncode})")
    os.replace(part, dest)
    print(f"✅ Terminé : {name} ({os.path.getsize(dest) / (1024**3):.2f} Go) en {time.time() - t0:.1f}s")


def main():
    print("=" * 80)
    print("📦 TÉLÉCHARGEMENT MUSIC FLAMINGO (ANALYSE MUSICALE OPTIONNELLE)")
    print(f"   Dossier de destination : {TARGET_DIR}")
    print("   ⚠️  Licence NVIDIA non commerciale — module optionnel de QA du workflow music_bg")
    print("=" * 80)

    for f_info in FILES:
        telecharger(f_info)

    print("\n🎉 SUCCÈS : Music Flamingo est prêt (activez l'analyse via --analyse).")


if __name__ == "__main__":
    main()
