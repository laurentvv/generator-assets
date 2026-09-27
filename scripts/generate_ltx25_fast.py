"""
generate_ltx25_fast.py
Ultra-fast daytime iteration workflow with LTX-2.5 Distilled.
Lets you prototype and validate cinematics in < 2 minutes on AMD Radeon RX 6950 XT.
"""
import os
import sys
import time
import subprocess

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
    print("⚡ [FAST DAYTIME ITERATION - LTX-2.5 DISTILLED]")
    print(f"   Model: {os.path.basename(LTX_MODEL)}")
    print(f"   Goal: Fast render < 2 min | Frames: {frames} ({frames/fps:.1f}s) @ {fps} fps")
    print(f"   Steps: {steps} | Resolution: 768x512 (Native LTX)")
    print(f"   Prompt: {prompt}")
    print("=" * 80)

    if not os.path.exists(LTX_MODEL):
        print(f"\n⚠️ The file {LTX_MODEL} is still finishing downloading.")
        print("   Please wait a few moments for the download to complete.")
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
        print(f"\n⚡ LTX-2.5 render completed in {duree:.1f}s ({duree/steps:.2f}s/step)!")
        print(f"   Raw file: {out_webm}")

        # Extraction preview
        subprocess.run([FFMPEG, "-y", "-i", out_webm, "-vframes", "1", out_png], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"   📸 Preview frame: {out_png}")

        # YouTube HD 1080p conformance
        if os.path.exists(CONFORM_SCRIPT):
            print("   🚀 YouTube Full HD 1080p hardware conformance...")
            subprocess.run([sys.executable, CONFORM_SCRIPT, out_webm, out_mp4], check=True)
            print(f"   🎥 Full HD 1080p video ready: {out_mp4}")

        return out_webm, out_mp4, out_png
    except Exception as e:
        print(f"❌ Error while running LTX-2.5: {e}")
        return None, None, None

if __name__ == "__main__":
    prompt = sys.argv[1] if len(sys.argv) > 1 else PROMPT_DEFAULT
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    frames = int(sys.argv[3]) if len(sys.argv) > 3 else 25
    run_fast_generation(prompt=prompt, steps=steps, frames=frames)
