import os
import subprocess
import shutil
import sys

TARGET_DIR = r"C:\Modeles_LLM"
curl = shutil.which("curl.exe") or "curl"

FILE_NAME = "LTX-2.5-Distilled-Q4_K_M.gguf"
URL = "https://huggingface.co/realrebelai/LTX-2.5_GGUFs/resolve/main/LTX-2.5-Distilled-Q4_K_M.gguf"
EXPECTED_SIZE = 15086587904

dest = os.path.join(TARGET_DIR, FILE_NAME)

if os.path.exists(dest) and os.path.getsize(dest) >= EXPECTED_SIZE:
    print(f"[OK] {FILE_NAME} est déjà présent et complet ({os.path.getsize(dest)} octets).")
    sys.exit(0)

print(f"===========================================================")
print(f" Téléchargement SOTA : {FILE_NAME} (14.05 Go)")
print(f" Destination : {dest}")
print(f"===========================================================")

cmd = [
    curl,
    "-L",
    "-C", "-",
    "--fail",
    "--retry", "5",
    "--retry-delay", "3",
    "-o", dest,
    URL
]

res = subprocess.run(cmd)
if res.returncode == 0:
    print(f"\n[SUCCÈS] {FILE_NAME} téléchargé avec succès !")
else:
    print(f"\n[ERREUR] Échec du téléchargement (code {res.returncode})", file=sys.stderr)
    sys.exit(res.returncode)
