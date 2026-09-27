"""
benchmark_vram.py
Precise measurement and profiling of VRAM consumption in real time via Windows PDH counters.
Makes it possible to identify with certainty the memory peak (Peak VRAM) and the safety margin before saturation.
"""
import os
import sys
import time
import subprocess
import threading
import json

# UTF-8 stdout
for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

SD_CLI = r"C:\SD\sd-cli.exe"
DIFFUSION_14B = r"C:\Modeles_LLM\wan2.1-t2v-14b-Q4_K_M.gguf"
VAE = r"C:\Modeles_LLM\wan_2.1_vae.safetensors"
T5XXL = r"C:\Modeles_LLM\umt5-xxl-encoder-Q4_K_M.gguf"
TEST_OUT = r"C:\GIT\generator-assets\output\vram_test_clip.webm"
REPORT_JSON = r"C:\GIT\generator-assets\output\vram_benchmark_results.json"

TOTAL_VRAM_GB = 16.0

class VRAMMonitor:
    def __init__(self):
        self.running = False
        self.peak_bytes = 0
        self.current_bytes = 0
        self.thread = None
        self.proc = None

    def _monitor(self):
        cmd = ["typeperf", r"\GPU Adapter Memory(*)\Dedicated Usage", "-si", "1"]
        self.proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1
        )
        for line in self.proc.stdout:
            if not self.running:
                break
            line = line.strip()
            if line.startswith('"0'):
                parts = line.split('","')
                if len(parts) >= 2:
                    try:
                        val_str = parts[1].replace('"', '').strip()
                        val_b = float(val_str)
                        self.current_bytes = val_b
                        if val_b > self.peak_bytes:
                            self.peak_bytes = val_b
                    except ValueError:
                        pass

    def start(self):
        self.running = True
        self.peak_bytes = 0
        self.thread = threading.Thread(target=self._monitor, daemon=True)
        self.thread.start()
        time.sleep(1.2) # Let typeperf initialize

    def stop(self):
        self.running = False
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.kill()
            except Exception:
                pass
        return self.peak_bytes

def benchmark_config(width, height, frames, label, steps=1):
    print("=" * 70)
    print(f"🔍 VRAM TEST: {label} ({width}x{height}, {frames} frames, {steps} step)")
    print("=" * 70)

    monitor = VRAMMonitor()
    monitor.start()

    vram_init_gb = monitor.current_bytes / (1024**3)
    print(f"   VRAM at rest before launch: {vram_init_gb:.2f} GB")

    cmd = [
        SD_CLI,
        "-M", "vid_gen",
        "--diffusion-model", DIFFUSION_14B,
        "--vae", VAE,
        "--t5xxl", T5XXL,
        "-p", "A majestic golden dragon soaring through clouds, 8k",
        "-W", str(width),
        "-H", str(height),
        "--video-frames", str(frames),
        "--fps", "16",
        "--steps", str(steps),
        "--sampling-method", "euler",
        "--diffusion-fa",
        "--temporal-tiling",
        "--vae-tiling",
        "--backend", "diffusion=vulkan0,te=cpu",
        "-o", TEST_OUT
    ]

    t0 = time.time()
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    duree = time.time() - t0
    peak_b = monitor.stop()

    if os.path.exists(TEST_OUT):
        try:
            os.remove(TEST_OUT)
        except Exception:
            pass

    peak_gb = peak_b / (1024**3)
    marge_gb = TOTAL_VRAM_GB - peak_gb
    pct = (peak_gb / TOTAL_VRAM_GB) * 100

    statut = "🟢 SAFE (Excellent headroom)"
    if peak_gb > 13.5:
        statut = "🟡 CAUTION (Borderline zone)"
    if res.returncode != 0 or peak_gb > 15.0:
        statut = "🔴 SATURATION RISK"

    print(f"   📊 MEASURED VRAM PEAK: {peak_gb:.2f} GB / 16 GB ({pct:.1f}%)")
    print(f"   🛡️ Remaining safety headroom: {marge_gb:.2f} GB free")
    print(f"   ⏱️ Test duration: {duree:.1f}s | Status: {statut}")

    return {
        "label": label,
        "resolution": f"{width}x{height}",
        "trames": frames,
        "duree_video_sec": round(frames / 16, 2),
        "peak_vram_gb": round(peak_gb, 2),
        "marge_libre_gb": round(marge_gb, 2),
        "pourcentage_vram": f"{pct:.1f}%",
        "statut": statut,
        "succes": res.returncode == 0
    }

def main():
    print("=" * 80)
    print("🚀 REAL VRAM BENCHMARK: AMD RADEON RX 6950 XT (16 GB VRAM)")
    print("   Goal: Measure the exact saturation for each frame count & resolution")
    print("=" * 80)

    configs = [
        (832, 480, 5,  "832x480 Standard (5 frames)"),
        (832, 480, 9,  "832x480 Moderate (9 frames)"),
        (832, 480, 17, "832x480 Extended (17 frames)"),
        (640, 360, 17, "640x360 Eco (17 frames)"),
        (640, 360, 25, "640x360 Eco (25 frames)"),
        (640, 360, 33, "640x360 Eco (33 frames)")
    ]

    results = []
    for w, h, frames, label in configs:
        res = benchmark_config(w, h, frames, label, steps=1)
        results.append(res)
        time.sleep(2) # Cooling pause and VRAM flush

    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print("📋 FINAL VRAM TELEMETRY TABLE (REAL MEASUREMENT RESULTS)")
    print("=" * 80)
    print(f"{'Configuration':<22} | {'Trames':<7} | {'Peak VRAM':<10} | {'Free Headroom':<12} | {'Status'}")
    print("-" * 80)
    for r in results:
        print(f"{r['resolution']:<22} | {r['trames']:<7} | {r['peak_vram_gb']:>5.2f} GB   | {r['marge_libre_gb']:>5.2f} GB free | {r['statut']}")
    print("=" * 80)
    print(f"Report saved to: {REPORT_JSON}")

if __name__ == "__main__":
    main()
