import os
import sys
import time
import subprocess

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

SD_CLI = r"C:\SD\sd-cli.exe"
DIFFUSION = r"C:\Modeles_LLM\LTX-2.5-Distilled-Q4_K_M.gguf"
VAE = r"C:\Modeles_LLM\ltx-2.5-video-vae-conv-bf16.safetensors"
AUDIO_VAE = r"C:\Modeles_LLM\ltx-2.5-audio-vae-bf16.safetensors"
LLM = r"C:\Modeles_LLM\gemma4-12b-with-proj-ltx-2.5-Q5_K_M.gguf"

OUTPUT_DIR = r"C:\GIT\generator-assets\output\comparatif"
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUT_WEBM = os.path.join(OUTPUT_DIR, "ltx25_dragon_2steps.webm")

if not os.path.exists(LLM):
    print(f"❌ En attente du fichier : {LLM}")
    sys.exit(1)

prompt = "Cinematic wide tracking shot, a colossal golden dragon with shimmering scales soaring majestically through sunset clouds, volumetric rays, high quality, 8k"

cmd = [
    SD_CLI,
    "-M", "vid_gen",
    "--diffusion-model", DIFFUSION,
    "--vae", VAE,
    "--audio-vae", AUDIO_VAE,
    "--llm", LLM,
    "-p", prompt,
    "-W", "768",
    "-H", "512",
    "--video-frames", "33",
    "--fps", "24",
    "--steps", "2",
    "--sampling-method", "euler_a",
    "--cfg-scale", "1.0",
    "--diffusion-fa",
    "--backend", "diffusion=vulkan0,te=cpu",
    "-o", OUT_WEBM,
    "-v"
]

print("=" * 75)
print("🚀 Lancement du test LTX-2.5 (2 steps, CFG 1.0, Audio+Vidéo synchro)")
print(f"   Sortie : {OUT_WEBM}")
print("=" * 75)

t_start = time.time()
res = subprocess.run(cmd)
elapsed = time.time() - t_start
if res.returncode == 0:
    print(f"\n✅ LTX-2.5 généré en {elapsed:.2f}s ({elapsed/60:.2f} min) !")
else:
    print(f"\n❌ Erreur code {res.returncode}")
