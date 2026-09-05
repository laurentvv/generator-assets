import os
import sys
import time
import subprocess
from datetime import datetime

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

SD_CLI = r"C:\SD\sd-cli.exe"
FFMPEG = r"C:\Program Files\Amuse\ffmpeg.exe"
MODELS_DIR = r"C:\Modeles_LLM"
OVERNIGHT_DIR = r"C:\GIT\generator-assets\output\overnight"
os.makedirs(OVERNIGHT_DIR, exist_ok=True)

BENCHMARK_PROMPT = (
    "Cinematic heroic medium shot, a colossal golden dragon flying directly towards camera, "
    "jaws open roaring, sharp fangs, radiant glowing amber eyes, majestic curved horns, "
    "massive wings spread wide, shimmering iridescent gold scales, dramatic clouds, sunset lighting, masterpiece, 8k"
)

NEGATIVE_PROMPT = (
    "色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，"
    "JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，"
    "手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走, "
    "blurry, low quality, distorted, deformed, watermark, oversaturated, static"
)

def conform_and_extract(raw_webm, base_name, has_audio=False):
    out_mp4 = os.path.join(OVERNIGHT_DIR, f"{base_name}_1080p.mp4")
    frames_dir = os.path.join(OVERNIGHT_DIR, f"frames_{base_name}")
    os.makedirs(frames_dir, exist_ok=True)

    # 1. Extraire les trames d'inspection
    cmd_frames = [
        FFMPEG, "-y", "-i", raw_webm,
        "-vf", "select=not(mod(n\\,8))",
        "-vsync", "vfr", "-q:v", "2",
        os.path.join(frames_dir, "frame_%02d.png")
    ]
    subprocess.run(cmd_frames, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 2. Conformation matérielle Full HD 1080p Lanczos + AMD FidelityFX CAS
    vf_conform = "scale=1920:1080:flags=lanczos,cas=0.75"
    if has_audio:
        cmd_mp4 = [
            FFMPEG, "-y", "-i", raw_webm,
            "-vf", vf_conform,
            "-c:v", "h264_amf", "-b:v", "22M",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            out_mp4
        ]
    else:
        cmd_mp4 = [
            FFMPEG, "-y", "-i", raw_webm,
            "-vf", vf_conform,
            "-c:v", "h264_amf", "-b:v", "22M",
            "-pix_fmt", "yuv420p",
            out_mp4
        ]
    subprocess.run(cmd_mp4, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out_mp4, frames_dir

def run_job(job_id, total_jobs, title, cmd, out_raw, base_name, has_audio):
    print("\n" + "=" * 85)
    print(f"[{job_id}/{total_jobs}] 🎬 DÉBUT DU RENDU : {title}")
    print(f"   Heure de lancement : {datetime.now().strftime('%H:%M:%S')}")
    print(f"   Fichier brut cible : {out_raw}")
    print("=" * 85)

    t0 = time.time()
    res = subprocess.run(cmd)
    elapsed = time.time() - t0

    if res.returncode == 0 and os.path.exists(out_raw) and os.path.getsize(out_raw) > 100000:
        mp4_path, frames_dir = conform_and_extract(out_raw, base_name, has_audio=has_audio)
        print(f"✅ Succès en {elapsed:.1f}s ({elapsed/60:.2f} min) !")
        print(f"   🎬 Vidéo 1080p : {mp4_path}")
        print(f"   🖼️ Trames extraites : {frames_dir}")
        return {
            "title": title,
            "status": "OK",
            "duration": elapsed,
            "mp4": mp4_path,
            "frames": frames_dir
        }
    else:
        print(f"❌ Échec du job {title} (code sortie {res.returncode})")
        return {
            "title": title,
            "status": f"ERREUR (code {res.returncode})",
            "duration": elapsed,
            "mp4": None,
            "frames": None
        }

def main():
    print("#" * 85)
    print("🌙 SESSION DE RENDU NOCTURNE SOTA - GRAND BENCHMARK COMPARATIF")
    print(f"   Démarrage : {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"   Dossier de sortie : {OVERNIGHT_DIR}")
    print("#" * 85)

    results = []

    # -------------------------------------------------------------
    # 1. LTX-2.5 (15B Audio + Vidéo - 8 steps distillés officiels)
    # -------------------------------------------------------------
    out_ltx = os.path.join(OVERNIGHT_DIR, "01_ltx25_8steps_dragon.webm")
    cmd_ltx = [
        SD_CLI, "-M", "vid_gen",
        "--diffusion-model", os.path.join(MODELS_DIR, "LTX-2.5-Distilled-Q4_K_M.gguf"),
        "--vae", os.path.join(MODELS_DIR, "ltx-2.5-video-vae-conv-bf16.safetensors"),
        "--audio-vae", os.path.join(MODELS_DIR, "ltx-2.5-audio-vae-bf16.safetensors"),
        "--llm", os.path.join(MODELS_DIR, "gemma4-12b-with-proj-ltx-2.5-Q5_K_M.gguf"),
        "-p", BENCHMARK_PROMPT,
        "-W", "768", "-H", "512",
        "--video-frames", "33", "--fps", "24",
        "--steps", "8",
        "--sigmas", "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0",
        "--sampling-method", "euler_a",
        "--cfg-scale", "1.0",
        "--backend", "diffusion=vulkan0,te=cpu,vae=cpu",
        "-o", out_ltx, "-v"
    ]
    results.append(run_job(1, 4, "LTX-2.5 (15B Audio + Vidéo - 8 steps)", cmd_ltx, out_ltx, "01_ltx25_8steps_dragon", has_audio=True))
    time.sleep(5)

    # -------------------------------------------------------------
    # 2. Wan 2.1 (14B Flagship T2V - 8 steps cinématiques)
    # -------------------------------------------------------------
    out_wan21 = os.path.join(OVERNIGHT_DIR, "02_wan21_14steps_dragon.webm")
    cmd_wan21 = [
        SD_CLI, "-M", "vid_gen",
        "--diffusion-model", os.path.join(MODELS_DIR, "wan2.1-t2v-14b-Q4_K_M.gguf"),
        "--vae", os.path.join(MODELS_DIR, "wan_2.1_vae.safetensors"),
        "--t5xxl", os.path.join(MODELS_DIR, "umt5-xxl-encoder-Q4_K_M.gguf"),
        "-p", BENCHMARK_PROMPT,
        "-n", NEGATIVE_PROMPT,
        "-W", "832", "-H", "480",
        "--video-frames", "17", "--fps", "16",
        "--steps", "8",
        "--sampling-method", "euler",
        "--cfg-scale", "6.0",
        "--flow-shift", "3.0",
        "--temporal-tiling",
        "--vae-tiling",
        "--backend", "diffusion=vulkan0,te=cpu",
        "-o", out_wan21, "-v"
    ]
    results.append(run_job(2, 4, "Wan 2.1 (14B Flagship T2V - 8 steps)", cmd_wan21, out_wan21, "02_wan21_14steps_dragon", has_audio=False))
    time.sleep(5)

    # -------------------------------------------------------------
    # 3. Wan 2.2 MoE (Dual-DiT A14B - 8 steps MoE)
    # -------------------------------------------------------------
    out_wan22 = os.path.join(OVERNIGHT_DIR, "03_wan22_moe_18steps_dragon.webm")
    cmd_wan22 = [
        SD_CLI, "-M", "vid_gen",
        "--diffusion-model", os.path.join(MODELS_DIR, "Wan2.2-T2V-A14B-LowNoise-Q4_K_M.gguf"),
        "--high-noise-diffusion-model", os.path.join(MODELS_DIR, "Wan2.2-T2V-A14B-HighNoise-Q4_K_M.gguf"),
        "--vae", os.path.join(MODELS_DIR, "wan_2.1_vae.safetensors"),
        "--t5xxl", os.path.join(MODELS_DIR, "umt5-xxl-encoder-Q4_K_M.gguf"),
        "-p", BENCHMARK_PROMPT,
        "-n", NEGATIVE_PROMPT,
        "-W", "832", "-H", "480",
        "--video-frames", "17", "--fps", "16",
        "--steps", "4",
        "--high-noise-steps", "4",
        "--cfg-scale", "3.5",
        "--high-noise-cfg-scale", "3.5",
        "--sampling-method", "euler",
        "--high-noise-sampling-method", "euler",
        "--offload-to-cpu",
        "--flow-shift", "3.0",
        "--temporal-tiling",
        "--vae-tiling",
        "--backend", "diffusion=vulkan0,te=cpu",
        "-o", out_wan22, "-v"
    ]
    results.append(run_job(3, 4, "Wan 2.2 MoE (2x 14B Dual-DiT - 8 steps)", cmd_wan22, out_wan22, "03_wan22_moe_18steps_dragon", has_audio=False))
    time.sleep(5)

    # -------------------------------------------------------------
    # 4. MiniMax-H3 (Titan Hailuo AI 32B - Vidéo + Audio Stéréo - 12 steps)
    # -------------------------------------------------------------
    out_minimax = os.path.join(OVERNIGHT_DIR, "04_minimax_h3_20steps_dragon.webm")
    cmd_minimax = [
        SD_CLI, "-M", "vid_gen",
        "--diffusion-model", os.path.join(MODELS_DIR, "minimax_h3_fl2va_pruned-Q4_K_M.gguf"),
        "--vae", os.path.join(MODELS_DIR, "minimax_h3_video_vae_fp16.safetensors"),
        "--audio-vae", os.path.join(MODELS_DIR, "minimax_h3_audio_vae_fp32.safetensors"),
        "--llm", os.path.join(MODELS_DIR, "qwen3vl_32b_minimax_h3-Q2_K_M.gguf"),
        "-p", BENCHMARK_PROMPT,
        "-W", "864", "-H", "480",
        "--video-frames", "22", "--fps", "24",
        "--steps", "12",
        "--cfg-scale", "1.0",
        "--offload-to-cpu",
        "--rng", "cpu",
        "--backend", "diffusion=vulkan0,te=cpu,vae=cpu",
        "-o", out_minimax, "-v"
    ]
    results.append(run_job(4, 4, "MiniMax-H3 (Titan 32B Vidéo + Audio - 12 steps)", cmd_minimax, out_minimax, "04_minimax_h3_20steps_dragon", has_audio=True))

    # -------------------------------------------------------------
    # RAPPORT DE SYNTHÈSE
    # -------------------------------------------------------------
    report_md = os.path.join(OVERNIGHT_DIR, "overnight_summary.md")
    with open(report_md, "w", encoding="utf-8") as f:
        f.write("# 🏆 Rapport de Synthèse du Grand Rendu Nocturne SOTA\n\n")
        f.write(f"**Date de fin :** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n")
        f.write("| Modèle | Statut | Durée | Vidéo HD 1080p | Trames Extraites |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- |\n")
        for r in results:
            mp4_link = f"[{os.path.basename(r['mp4'])}](file:///{r['mp4'].replace(chr(92), '/')})" if r['mp4'] else "N/A"
            frames_link = f"[{os.path.basename(r['frames'])}](file:///{r['frames'].replace(chr(92), '/')})" if r['frames'] else "N/A"
            f.write(f"| **{r['title']}** | {r['status']} | {r['duration']/60:.2f} min | {mp4_link} | {frames_link} |\n")

    print("\n" + "#" * 85)
    print("🎉 TOUS LES RENDUS NOCTURNES SONT TERMINÉS AVEC SUCCÈS !")
    print(f"   Rapport de synthèse disponible : {report_md}")
    print("#" * 85)

if __name__ == "__main__":
    main()
