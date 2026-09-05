import os
import sys
import time
import subprocess

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

SD_CLI = r"C:\SD\sd-cli.exe"
FFMPEG = r"C:\Program Files\Amuse\ffmpeg.exe"
MODELS_DIR = r"C:\Modeles_LLM"
OUTPUT_DIR = r"C:\GIT\generator-assets\output\comparatif"
os.makedirs(OUTPUT_DIR, exist_ok=True)

PROMPT = (
    "Cinematic heroic medium shot, a colossal golden dragon flying directly towards camera, "
    "jaws open roaring, sharp fangs, radiant glowing amber eyes, majestic curved horns, "
    "massive wings spread wide, shimmering iridescent gold scales, dramatic clouds, sunset lighting, masterpiece, 8k"
)

def wait_for_file(filepath, min_size_gb=1.0, timeout_sec=1800):
    print(f"⏳ Attente de finalisation du téléchargement : {os.path.basename(filepath)}...", flush=True)
    part_path = filepath + ".part"
    t0 = time.time()
    while time.time() - t0 < timeout_sec:
        if os.path.exists(filepath) and not os.path.exists(part_path):
            size_gb = os.path.getsize(filepath) / (1024**3)
            if size_gb >= min_size_gb:
                print(f"✅ Fichier prêt : {os.path.basename(filepath)} ({size_gb:.2f} Go)", flush=True)
                return True
        time.sleep(5)
    raise TimeoutError(f"Délai dépassé pour {filepath}")

def extract_and_conform(video_path, name, has_audio=False):
    frames_dir = os.path.join(OUTPUT_DIR, f"frames_{name}")
    os.makedirs(frames_dir, exist_ok=True)
    out_mp4 = os.path.join(OUTPUT_DIR, f"{name}_1080p.mp4")

    # Extraire trames clés
    cmd_frames = [
        FFMPEG, "-y", "-i", video_path,
        "-vf", "select=not(mod(n\\,8))",
        "-vsync", "vfr", "-q:v", "2",
        os.path.join(frames_dir, "frame_%02d.png")
    ]
    subprocess.run(cmd_frames, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"   🖼️ Trames extraites dans : {frames_dir}", flush=True)

    # Conformer MP4
    if has_audio:
        cmd_mp4 = [
            FFMPEG, "-y", "-i", video_path,
            "-c:v", "h264_amf", "-b:v", "15M",
            "-c:a", "aac", "-b:a", "192k",
            out_mp4
        ]
    else:
        cmd_mp4 = [
            FFMPEG, "-y", "-i", video_path,
            "-c:v", "h264_amf", "-b:v", "15M",
            out_mp4
        ]
    subprocess.run(cmd_mp4, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"   🎬 MP4 1080p matériel généré : {out_mp4}", flush=True)

def run_wan22():
    low_noise = os.path.join(MODELS_DIR, "Wan2.2-T2V-A14B-LowNoise-Q4_K_M.gguf")
    high_noise = os.path.join(MODELS_DIR, "Wan2.2-T2V-A14B-HighNoise-Q4_K_M.gguf")
    vae = os.path.join(MODELS_DIR, "wan_2.1_vae.safetensors")
    t5 = os.path.join(MODELS_DIR, "umt5-xxl-encoder-Q4_K_M.gguf")
    out_webm = os.path.join(OUTPUT_DIR, "wan22_moe_dragon.webm")

    wait_for_file(high_noise, min_size_gb=8.0)

    print("\n" + "=" * 80, flush=True)
    print("🚀 [LANCEMENT DU BENCHMARK] WAN 2.2 MoE (A14B LowNoise + HighNoise)", flush=True)
    print(f"   Sortie : {out_webm}", flush=True)
    print("=" * 80, flush=True)

    cmd = [
        SD_CLI,
        "-M", "vid_gen",
        "--diffusion-model", low_noise,
        "--high-noise-diffusion-model", high_noise,
        "--vae", vae,
        "--t5xxl", t5,
        "-p", PROMPT,
        "-W", "832",
        "-H", "480",
        "--video-frames", "17",
        "--fps", "16",
        "--steps", "10",
        "--high-noise-steps", "8",
        "--cfg-scale", "3.5",
        "--high-noise-cfg-scale", "3.5",
        "--sampling-method", "euler",
        "--high-noise-sampling-method", "euler",
        "--diffusion-fa",
        "--offload-to-cpu",
        "--flow-shift", "3.0",
        "-o", out_webm,
        "-v"
    ]

    t0 = time.time()
    res = subprocess.run(cmd)
    elapsed = time.time() - t0
    if res.returncode == 0:
        print(f"\n✅ Wan 2.2 MoE terminé en {elapsed:.2f}s ({elapsed/60:.2f} min) !", flush=True)
        extract_and_conform(out_webm, "wan22_moe_dragon", has_audio=False)
    else:
        print(f"\n❌ Erreur Wan 2.2 code {res.returncode}", flush=True)

def run_minimax():
    dit = os.path.join(MODELS_DIR, "minimax_h3_fl2va_pruned-Q4_K_M.gguf")
    llm = os.path.join(MODELS_DIR, "qwen3vl_32b_minimax_h3-Q2_K_M.gguf")
    video_vae = os.path.join(MODELS_DIR, "minimax_h3_video_vae_fp16.safetensors")
    audio_vae = os.path.join(MODELS_DIR, "minimax_h3_audio_vae_fp32.safetensors")
    out_webm = os.path.join(OUTPUT_DIR, "minimax_h3_dragon.webm")

    wait_for_file(llm, min_size_gb=10.0)

    print("\n" + "=" * 80, flush=True)
    print("🚀 [LANCEMENT DU BENCHMARK] MINIMAX-H3 (T2VA Vidéo + Audio)", flush=True)
    print(f"   Sortie : {out_webm}", flush=True)
    print("=" * 80, flush=True)

    cmd = [
        SD_CLI,
        "-M", "vid_gen",
        "--diffusion-model", dit,
        "--vae", video_vae,
        "--audio-vae", audio_vae,
        "--llm", llm,
        "-p", PROMPT,
        "-W", "864",
        "-H", "480",
        "--video-frames", "22",
        "--fps", "24",
        "--cfg-scale", "1.0",
        "--diffusion-fa",
        "--offload-to-cpu",
        "--rng", "cpu",
        "-o", out_webm,
        "-v"
    ]

    t0 = time.time()
    res = subprocess.run(cmd)
    elapsed = time.time() - t0
    if res.returncode == 0:
        print(f"\n✅ MiniMax-H3 terminé en {elapsed:.2f}s ({elapsed/60:.2f} min) !", flush=True)
        extract_and_conform(out_webm, "minimax_h3_dragon", has_audio=True)
    else:
        print(f"\n❌ Erreur MiniMax-H3 code {res.returncode}", flush=True)

def main():
    print("🚀 CHAÎNE D'EXÉCUTION AUTOMATIQUE : Wan 2.2 MoE -> MiniMax-H3", flush=True)
    try:
        run_wan22()
    except Exception as e:
        print(f"⚠️ Exception lors de Wan 2.2 : {e}", flush=True)

    try:
        run_minimax()
    except Exception as e:
        print(f"⚠️ Exception lors de MiniMax-H3 : {e}", flush=True)

    print("\n🏁 CHAÎNE COMPLÈTE TERMINÉE !", flush=True)

if __name__ == "__main__":
    main()
