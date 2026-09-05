import os
import subprocess
import shutil
import sys

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

TARGET_DIR = r"C:\Modeles_LLM"
DEST_NAME = "gemma4-12b-with-proj-ltx-2.5-Q5_K_M.gguf"
dest = os.path.join(TARGET_DIR, DEST_NAME)

token_path = os.path.expanduser(r"~/.cache/huggingface/token")
token = ""
if os.path.exists(token_path):
    with open(token_path, "r", encoding="utf-8") as f:
        token = f.read().strip()

URL = "https://huggingface.co/elix3r/gemma4-12b-with-proj-ltx-2.5-GGUF/resolve/main/gemma4-12b-with-proj-ltx-2.5-Q5_K_M.gguf"
EXPECTED_SIZE = 9514920864

if os.path.exists(dest) and os.path.getsize(dest) == EXPECTED_SIZE:
    print(f"[OK] {DEST_NAME} est déjà téléchargé et complet ({EXPECTED_SIZE} octets) !")
    sys.exit(0)

print(f"[START] Téléchargement de {DEST_NAME} (8.86 Go)...")
print(f"Destination : {dest}")

curl = shutil.which("curl.exe") or "curl"
cmd = [
    curl, "-L", "-C", "-",
    "--fail", "--retry", "5", "--retry-delay", "3",
    "-H", f"Authorization: Bearer {token}",
    "-o", dest,
    URL
]

res = subprocess.run(cmd)
if res.returncode == 0:
    final_size = os.path.getsize(dest)
    print(f"[OK] Téléchargement terminé avec succès ! Taille finale : {final_size / (1024**3):.2f} Go")
else:
    print(f"[ERREUR] Échec du téléchargement (code {res.returncode})")
    sys.exit(res.returncode)
