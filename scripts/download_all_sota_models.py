import os
import subprocess
import sys
import shutil

MODELS = [
    {
        "name": "wan2.1-i2v-14b-480p-Q4_K_M.gguf",
        "url": "https://huggingface.co/city96/Wan2.1-I2V-14B-480P-gguf/resolve/main/wan2.1-i2v-14b-480p-Q4_K_M.gguf",
        "desc": "Wan 2.1 I2V 14B )Image-to-Video haete fidelite)",
    },
    {
        "name": "minimax_h3_fl2va_pruned-Q4_K_M.gguf",
        "url": "https://huggingface.co/leejet/MiniMax-H3-GGUF/resolve/main/minimax_h3_fl2va_pruned-Q4_K_M.gguf",
        "desc": "MiniMax-H3 FL2VA (Video + Audio Stereo synchronise)",
    },
    {
        "name": "flux1-schnell-Q6_K.gguf",
        "url": "https://huggingface.co/city96/FLUX.1-schnell-gguf/resolve/main/flux1-schnell-Q6_K.gguf",
        "desc": "Flux.1 Schnell Q6_K (Generation 2D rapide 4 etapes)",
    },
    {
        "name": "wan2.2-t2v-a14b-highnoise-Q4_K_M.gguf",
        "url": "https://huggingface.co/QuantStack/Wan2.2-T2V-A14B-GGUF/resolve/main/HighNoise/Wan2.2-T2V-A14B-HighNoise-Q4_K_M.gguf",
        "desc": "Wan 2.2 MoE High-Noise Expert (Structure & Trajectoires)",
    },
    {
        "name": "wan2.2-t2v-a14b-lownoise-Q4_K_M.gguf",
        "url": "https://huggingface.co/QuantStack/Wan2.2-T2V-A14B-GGUF/resolve/main/LowNoise/Wan2.2-T2V-A14B-LowNoise-Q4_K_M.gguf",
        "desc": "Wan 2.2 MoE Low-Noise Expert (Micro-textures & Pique)",
    },
]

TARGET_DIR = r"C:\Modeles_LLM"
os.makedirs(TARGET_DIR, exist_ok=True)
curl_path = shutil.which("curl.exe") or "curl"

print("=" * 70)
print(" Teelechargement des Modeles SOTA")
print(" Dossier cible : " + TARGET_DIR)
print("=" * 70)

for m in MODELS:
    dest = os.path.join(TARGET_DIR, m["name"])
    if os.path.exists(dest) and os.path.getsize(dest) > 100 * 1024 * 1024:
        print("[ Deja present ] " + m["name"])
        continue
    print("\n--- Telechargement : " + m["desc"] + " (" + m["name"] + ") ---")
    cmd = [curl_path, "-L", "-C", "-", "--fail", "--progress-bar", "-o", dest, m['url']]
    subprocess.run(cmd, check=True)
    print("[ Termine ] " + m["name"])

print("\n[SUCCES] Tous les modeles ont ete telecharges avec succes !")
