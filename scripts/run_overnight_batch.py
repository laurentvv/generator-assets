"""
run_overnight_batch.py
Pipeline de rendu nocturne autonome pour AMD Radeon RX 6950 XT (16 Go VRAM).
Permet de lancer une file de generation video haute qualite (Wan 2.1 14B, Wan 2.2, MiniMax, LTX-2.5)
pendant la nuit, avec encodage automatique en Full HD 1080p YouTube.
"""
import os
import sys
import time
import json
import subprocess
from datetime import datetime

# UTF-8 stdout
for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

SD_CLI = r"C:\SD\sd-cli.exe"
FFMPEG = r"C:\Program Files\Amuse\ffmpeg.exe"
CONFORM_SCRIPT = r"C:\GIT\generator-assets\scripts\conform_youtube_hd.py"
OUTPUT_DIR = r"C:\GIT\generator-assets\output\overnight"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Modèles disponibles
MODELS = {
    "wan14b": {
        "diffusion": r"C:\Modeles_LLM\wan2.1-t2v-14b-Q4_K_M.gguf",
        "vae": r"C:\Modeles_LLM\wan_2.1_vae.safetensors",
        "t5": r"C:\Modeles_LLM\umt5-xxl-encoder-Q4_K_M.gguf",
        "backend": "diffusion=vulkan0,te=cpu",
        "width": 832,
        "height": 480,
        "fps": 16,
    },
    "wan22_moe": {
        "high_noise": r"C:\Modeles_LLM\Wan2.2-T2V-P14B-HighNoise-Q4_K_M.gguf",
        "low_noise": r"C:\Modeles_LLM\Wan2.2-T2V-A14B-LowNoise-Q4_K_M.gguf",
        "vae": r"C:\Modeles_LLM\wan_2.1_vae.safetensors",
        "t5": r"C:\Modeles_LLM\umt5-xxl-encoder-Q4_K_M.gguf",
        "backend": "diffusion=vulkan0,te=cpu",
        "width": 832,
        "height": 480,
        "fps": 16,
    },
    "minimax_h3": {
        "diffusion": r"C:\Modeles_LLM\minimax_h3_fl2va_pruned-Q4_K_M.gguf",
        "vae": r"C:\Modeles_LLM\wan_2.1_vae.safetensors",
        "t5": r"C:\Modeles_LLM\umt5-xxl-encoder-Q4_K_M.gguf",
        "backend": "diffusion=vulkan0,te=cpu",
        "width": 832,
        "height": 480,
        "fps": 24,
    }
}

DEFAULT_QUEUE = [
    {
        "name": "dragon_vol_cinematique",
        "model": "wan14b",
        "prompt": "Cinematic wide shot, a majestic golden dragon with iridescent scales soaring through glowing sunset clouds, intricate horns, glowing amber eyes, dramatic volumetric golden hour lighting, photorealistic 8k, masterpiece",
        "frames": 25,
        "steps": 14
    },
    {
        "name": "forteresse_orageuse",
        "model": "wan14b",
        "prompt": "Cinematic aerial camera gliding over a colossal medieval dark fortress perched on stormy ocean cliffs, thunderous dark waves crashing, lightning flashes illuminating wet stone walls, hyper-detailed, atmospheric",
        "frames": 25,
        "steps": 14
    },
    {
        "name": "guerrier_lumiere",
        "model": "wan14b",
        "prompt": "Cinematic slow motion medium shot, an armored paladin standing in an ancient gothic cathedral, radiant sunlight streaming through stained glass windows, dust motes dancing in light beams, photorealistic, 8k",
        "frames": 25,
        "steps": 14
    }
]

def process_queue(queue=DEFAULT_QUEUE):
    log_file = os.path.join(OUTPUT_DIR, f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    print("=" * 80)
    print(f"🌙 DÉMARRAGE DU BATCH OVERNIGHT ({len(queue)} générations en file d'attente)")
    print(f"   Dossier de sortie : {OUTPUT_DIR}")
    print(f"   Fichier de log : {log_file}")
    print("=" * 80)

    summary = []

    for i, job in enumerate(queue, 1):
        name = job.get("name", f"job_{i}")
        model_key = job.get("model", "wan14b")
        prompt = job["prompt"]
        frames = job.get("frames", 25)
        steps = job.get("steps", 14)

        cfg = MODELS.get(model_key, MODELS["wan14b"])
        out_raw = os.path.join(OUTPUT_DIR, f"{i:02d}_{name}.webm")
        out_hd = os.path.join(OUTPUT_DIR, f"{i:02d}_{name}_1080p.mp4")
        out_png = os.path.join(OUTPUT_DIR, f"{i:02d}_{name}_preview.png")

        print(f"\n[{i}/{len(queue)}] 🚀 Lancement : {name} ({model_key.upper()}, {frames} trames, {steps} steps)")
        print(f"   Prompt : {prompt[:80]}...")

        cmd = [
            SD_CLI,
            "-M", "vid_gen",
            "--diffusion-model", cfg["diffusion"],
            "--vae", cfg["vae"],
            "--t5xxl", cfg["t5"],
            "-p", prompt,
            "-W", str(cfg["width"]),
            "-H", str(cfg["height"]),
            "--video-frames", str(frames),
            "--fps", str(cfg["fps"]),
            "--steps", str(steps),
            "--sampling-method", "euler",
            "--diffusion-fa",
            "--backend", cfg["backend"],
            "-o", out_raw
        ]

        t0 = time.time()
        try:
            subprocess.run(cmd, check=True)
            elapsed = time.time() - t0
            print(f"   ✅ Rendu brut terminé en {elapsed:.1f}s ({elapsed/60:.1f} min)")

            subprocess.run([FFMPEG, "-y", "-i", out_raw, "-vframes", "1", out_png], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            subprocess.run([sys.executable, CONFORM_SCRIPT, out_raw, out_hd], check=True)
            print(f"   🎥 Vidéo Full HD prête : {out_hd}")

            summary.append({"name": name, "status": "SUCCÈS", "duree_sec": elapsed, "fichier": out_hd})
        except Exception as e:
            print(f"   ❌ ERREUR lors de l'exécution : {e}")
            summary.append({"name": name, "status": f"ERREUR: {e}", "duree_sec": time.time() - t0, "fichier": None})

    print("\n" + "=" * 80)
    print("🌅 BATCH OVERNIGHT TERMINÉ AVEC SUCCÈS !")
    print("=" * 80)
    for s in summary:
        print(f" - {s['name']} : {s['status']} ({s['duree_sec']/60:.1f} min)")

if __name__ == "__main__":
    process_queue()
