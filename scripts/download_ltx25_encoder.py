import os
import subprocess
import shutil
import sys

TARGET_DIR = r"C:\Modeles_LLM"
curl = shutil.which("curl.exe") or "curl"

DEST_NAME = "gemma4-12b-with-proj-ltx-2.5-int8.safetensors"
URL = "https://huggingface.co/DeepNeuralNerd/Gemma-4-12B-it-uncensored-heretic-DeepNeuralNerd-LTX_2.5_ComfyUI/resolve/main/Gemma-4-12B-it-uncensored-heretic%20-%20DeepNeuralNerd%20-LTX%202.5-ComfyUI-int8convrot.safetensors"

dest = os.path.join(TARGET_DIR, DEST_NAME)
if os.path.exists(dest) and os.path.getsize(dest) > 10 * 1024 * 1024 * 1024:
    print(f"[OK] {DEST_NAME} déjà présent.")
    sys.exit(0)

print(f"Téléchargement de {DEST_NAME} (12.26 Go)...")
cmd = [curl, "-L", "-C", "-", "--fail", "--retry", "5", "-o", dest, URL]
subprocess.run(cmd, check=True)
print(f"[SUCCÈS] {DEST_NAME} téléchargé !")
