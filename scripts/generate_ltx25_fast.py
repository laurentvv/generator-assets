"""
generate_ltx25_fast.py
Workflow ultra-rapide d'itération en journée avec LTX-2.5 Distilled.
Permet de prototyper et valider des cinématiques en < 2 minutes sur AMD Radeon RX 6950 XT.
"""
import os
import sys
import time
import subprocess
from pathlib import Path

# UTF-8 stdout
for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

SD_CLI = r"C:\SD\sd-cli.exe"
FFMPEG = r"C:\Program Files\Amuse\ffmpeg.exe"
CONFORM_SCRIPT = r"C:\GIT\generator-assets\scripts\conform_youtube_hd.py"

LTX_MODEL = r"C:\Modeles_LLM\LTX-2.5-Distilled-Q4_K_M.gguf"
T5XXL = r"C:\Modeles_LLM\umt5-xxl-encoder-Q4_K_M.gguf"
OUTPUT_DIR = r"C:\GIT\generator-assets\output\fast_iteration"
os.makedirs(OUTPUT_DIR, exist_ok=True)

PROMPT_DEFAULT = (
    "Cinematic tracking shot, a futuristic sleek cybernetic hoverbike speeding through "
    "a neon-lit cyberpunk metropolis at rainy night, brilliant cyan and magenta neon reflections on wet asphalt, "
    "dramatic camera motion blur, photorealistic, 8k resolution, cinematic lighting."
)

def run_fast_generation(prompt=PROMPT_DEFAULT, frames=25, steps=10, fps=24, output_name="ltx25_fast_demo"):
    out_webm = os.path.join(OUTPUT_DIR, f"{output_name}.webm")
    out_mp4 = os.path.join(OUTPUT_DIR, f"{output_name}_1080p.mp4")
    out_png = os.path.join(OUTPUT_DIR, f"{output_name}_preview.png")

    print("=" * 80)
    print("⚡ [ITÉRATION RAPIDE EN JOURNÉE - LTX-2.5 DISTILLED]")
    print(f"   Modèle : {os.path.basename(LTX_MODEL)}")
    print(f"   Objectif : Rendu rapide < 2 min | Trames : {frames} ({frames/fps:.1f}s) @ {fps} fps")
    print(f"   Steps : {steps} | Résolution : 768x512 (Native LTX)")
    print(f"   Prompt : {prompt}")
    print("=" * 80)

    if not os.path.exists(LTX_MODEL):
        print(f"\n⚠️ Le fichier {LTX_MODEL} est en cours de finalisation de téléchargement.")
        print(f"   Veuillez patienter quelques instants que le téléchargement se termine.")
        return None, None, None

    cmd = [
        SD_CLI,
        "-M", "vid_gen",
        "--diffusion-model", LTX_MODEL,
        "--t5xxl", T5XXL,
        "-p", prompt,
        "-W", "768",
        "-H", "512",
        "--video-frames", str(frames),
        "--fps", str(fps),
        "--steps", str(steps),
        "--scheduler", "ltx2",
        "--diffusion-fa",
        "--backend", "diffusion=vulkan0,te=cpu",
        "-o", out_webm
    ]

    t0 = time.time()
    try:
        subprocess.run(cmd, check=True)
        duree = time.time() - t0
        print(f"\n⚡ Rendu LTX-2.5 achevé en {duree:.1f}s ({duree/steps:.2f}s/step) !")
        print(f"   Fichier brut : {out_webm}")

        # Extraction preview
        subprocess.run([FFMPEG, "-y", "-i", out_webm, "-vframes", "1", out_png], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"   📸 Trame d'aperçu : {out_png}")

        # Conformation YouTube HD 1080p
        if os.path.exists(CONFORM_SCRIPT):
            print(f"   🚀 Conformation matérielle YouTube Full HD 1080p...")
            subprocess.run([sys.executable, CONFORM_SCRIPT, out_webm, out_mp4], check=True)
            print(f"   🎥 Vidéo Full HD 1080p prête : {out_mp4}")

        return out_webm, out_mp4, out_png
    except Exception as e:
        print(f"❌ Erreur lors de l'exécution LTX-2.5 : {e}")
        return None, None, None

if __name__ == "__main__":
    prompt = sys.argv[1] if len(sys.argv) > 1 else PROMPT_DEFAULT
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    frames = int(sys.argv[3]) if len(sys.argv) > 3 else 25
    run_fast_generation(prompt=prompt, steps=steps, frames=frames)
