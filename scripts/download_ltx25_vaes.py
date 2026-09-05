import os
import subprocess
import shutil
import sys

TARGET_DIR = r"C:\Modeles_LLM"
curl = shutil.which("curl.exe") or "curl"

VAES = [
    ("ltx-2.5-video-vae-conv-bf16.safetensors", "https://huggingface.co/dummy9996/LTX-2.5-22b-ungate/resolve/main/ltx-2.5-video-vae-conv-bf16.safetensors"),
    ("ltx-2.5-audio-vae-bf16.safetensors", "https://huggingface.co/dummy9996/LTX-2.5-22b-ungate/resolve/main/ltx-2.5-audio-vae-bf16.safetensors")
]

for name, url in VAES:
    dest = os.path.join(TARGET_DIR, name)
    if os.path.exists(dest) and os.path.getsize(dest) > 10 * 1024 * 1024:
        print(f"[OK] Déjà présent : {name}")
        continue
    print(f"\nTéléchargement de {name}...")
    cmd = [curl, "-L", "-C", "-", "--fail", "--retry", "3", "-o", dest, url]
    subprocess.run(cmd, check=True)
    print(f"[SUCCÈS] {name} téléchargé !")
