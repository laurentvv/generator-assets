import os
import sys
import time
import subprocess
from pathlib import Path

# UTF-8 stdout
for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

# Paths
SD_CLI = r"C:\SD\sd-cli.exe"
DIFFUSION_14B = r"C:\Modeles_LLM\wan2.1-t2v-14b-Q4_K_M.gguf"
VAE = r"C:\Modeles_LLM\wan_2.1_vae.safetensors"
T5XXL = r"C:\Modeles_LLM\umt5-xxl-encoder-Q4_K_M.gguf"
OUTPUT_DIR = r"C:\GIT\generator-assets\output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

PROMPT_DEFAULT = (
    "Cinematic movie shot, a majestic golden dragon with iridescent scales soaring through glowing sunset clouds, "
    "intricate horns, glowing amber eyes, dramatic golden hour volumetric lighting, photorealistic, 8k resolution, "
    "cinematic atmosphere, smooth slow-motion flight."
)

def run_generation(prompt=PROMPT_DEFAULT, frames=9, steps=8, output_name="dragon_14b_cinema"):
    out_webm = os.path.join(OUTPUT_DIR, f"{output_name}.webm")
    out_mp4 = os.path.join(OUTPUT_DIR, f"{output_name}_1080p.mp4")
    out_png = os.path.join(OUTPUT_DIR, f"{output_name}_preview.png")

    print("=" * 80)
    print(f"🎬 GÉNÉRATION WAN 2.1 14B (FLAGSHIP CINÉMA)")
    print(f"   Modèle : {os.path.basename(DIFFUSION_14B)} (14 Milliards de paramètres)")
    print(f"   VRAM allouée : ~9.65 Go sur AMD Radeon RX 6950 XT (16 Go)")
    print(f"   Encodeur Texte : T5XXL CPU RAM (stabilité numérique FP32)")
    print(f"   Trames : {frames} | Pas (steps) : {steps} | Résolution : 832x480")
    print(f"   Prompt : {prompt}")
    print("=" * 80)

    cmd = [
        SD_CLI,
        "-M", "vid_gen",
        "--diffusion-model", DIFFUSION_14B,
        "--vae", VAE,
        "--t5xxl", T5XXL,
        "-p", prompt,
        "-W", "832",
        "-H", "480",
        "--video-frames", str(frames),
        "--fps", "16",
        "--steps", str(steps),
        "--sampling-method", "euler",
        "--diffusion-fa",
        "--backend", "diffusion=vulkan0,te=cpu",
        "-o", out_webm
    ]

    t0 = time.time()
    subprocess.run(cmd, check=True)
    duree = time.time() - t0
    print(f"\n✅ Génération 14B terminée en {duree:.1f}s ({duree/steps:.2f}s/step)")
    print(f"   Fichier brut généré : {out_webm}")

    # Extraction aperçu
    ffmpeg = r"C:\Program Files\Amuse\ffmpeg.exe"
    subprocess.run([ffmpeg, "-y", "-i", out_webm, "-vframes", "1", out_png], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"   📸 Trame d'aperçu : {out_png}")

    # Conformation YouTube Full HD 1080p via AMD AMF
    conform_script = r"C:\GIT\generator-assets\scripts\conform_youtube_hd.py"
    if os.path.exists(conform_script):
        print(f"\n🚀 Conformation YouTube Full HD 1080p (AMF Hardware)...")
        subprocess.run([sys.executable, conform_script, out_webm, out_mp4], check=True)
        print(f"   🎥 Vidéo finale YouTube HD : {out_mp4}")

    return out_webm, out_mp4, out_png

if __name__ == "__main__":
    frames = 9
    steps = 8
    if len(sys.argv) > 1:
        steps = int(sys.argv[1])
    if len(sys.argv) > 2:
        frames = int(sys.argv[2])
    run_generation(frames=frames, steps=steps)
