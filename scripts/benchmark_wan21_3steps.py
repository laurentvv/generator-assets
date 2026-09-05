import os
import sys
import time
import subprocess

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

SD_CLI = r"C:\SD\sd-cli.exe"
DIFFUSION = r"C:\Modeles_LLM\wan2.1-t2v-14b-Q4_K_M.gguf"
VAE = r"C:\Modeles_LLM\wan_2.1_vae.safetensors"
T5XXL = r"C:\Modeles_LLM\umt5-xxl-encoder-Q4_K_M.gguf"

OUTPUT_DIR = r"C:\GIT\generator-assets\output\comparatif"
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUT_WEBM = os.path.join(OUTPUT_DIR, "wan21_14b_dragon_3steps.webm")

prompt = (
    "Cinematic heroic medium shot, a colossal golden dragon flying directly towards camera, "
    "jaws open roaring, sharp fangs, radiant glowing amber eyes, majestic curved horns, "
    "massive wings spread wide, shimmering iridescent gold scales, dramatic clouds, sunset lighting, masterpiece, 8k"
)

cmd = [
    SD_CLI,
    "-M", "vid_gen",
    "--diffusion-model", DIFFUSION,
    "--vae", VAE,
    "--t5xxl", T5XXL,
    "-p", prompt,
    "-W", "832",
    "-H", "480",
    "--video-frames", "17",
    "--fps", "16",
    "--steps", "3",
    "--sampling-method", "euler",
    "--diffusion-fa",
    "--temporal-tiling",
    "--vae-tiling",
    "--backend", "diffusion=vulkan0,te=cpu",
    "-o", OUT_WEBM,
    "-v"
]

print("=" * 75)
print("🚀 [BENCHMARK 3 STEPS] Wan 2.1 14B (Flagship T2V)")
print(f"   Sortie : {OUT_WEBM}")
print("=" * 75)

t_start = time.time()
res = subprocess.run(cmd)
elapsed = time.time() - t_start
if res.returncode == 0:
    print(f"\n✅ Wan 2.1 14B 3-steps généré en {elapsed:.2f}s ({elapsed/60:.2f} min) !")
else:
    print(f"\n❌ Erreur code {res.returncode}")
    sys.exit(res.returncode)
