"""
assemble_2plans.py
Assemble et masterise les 2 premiers plans générés (01_horizon et 02_glisse).
Génère le sound design dédié, assemble la vidéo en flux continu et produit le master Full HD 1080p 60 FPS (AMD AMF).
"""
import os
import sys
import time
import json
import subprocess
import numpy as np
from scipy.io import wavfile

# Forçage encodage UTF-8 sous console Windows
for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

FFMPEG = r"C:\Program Files\Amuse\ffmpeg.exe"
OUTPUT_DIR = r"C:\GIT\generator-assets\output\film_10s"

PLAN1 = os.path.join(OUTPUT_DIR, "01_horizon.webm")
PLAN2 = os.path.join(OUTPUT_DIR, "02_glisse.webm")
ASSEMBLED_RAW = os.path.join(OUTPUT_DIR, "film_2plans_brut.mp4")
SOUNDTRACK = os.path.join(OUTPUT_DIR, "soundtrack_2plans.wav")
MASTER_1080P = os.path.join(OUTPUT_DIR, "film_2plans_dragon_1080p_master.mp4")
PREVIEW_PNG = os.path.join(OUTPUT_DIR, "film_2plans_preview_hd.png")
REPORT_JSON = os.path.join(OUTPUT_DIR, "rapport_production_2plans.json")

def generer_audio_2plans(out_wav, duration_sec=2.125, sample_rate=48000):
    print(f"\n🎵 [Sound Design] Synthèse de la bande sonore pour 2 plans ({duration_sec:.2f}s, 48 kHz Stéréo)...")
    total_samples = int(duration_sec * sample_rate)
    t = np.linspace(0, duration_sec, total_samples, endpoint=False)

    # 1. Drone sub-bass orchestral (48 Hz - 55 Hz)
    f_sweep = np.linspace(48.0, 56.0, total_samples)
    drone = np.sin(2 * np.pi * f_sweep * t) * 0.40
    drone += np.sin(2 * np.pi * f_sweep * 2 * t) * 0.18

    # 2. Vent atmosphérique dynamique avec souffle montant
    noise = np.random.normal(0, 1, total_samples)
    wind = np.zeros(total_samples)
    alpha = 0.04
    for i in range(1, total_samples):
        wind[i] = alpha * noise[i] + (1 - alpha) * wind[i-1]
    wind = wind * (0.3 + 0.7 * (t / duration_sec)) * 0.45

    # 3. Battement d'ailes cinématique à la transition (t = 1.0s)
    wing = np.zeros(total_samples)
    idx = int(1.0 * sample_rate)
    width = int(0.4 * sample_rate)
    if idx + width < total_samples:
        w_t = np.linspace(0, 0.4, width)
        wing[idx:idx+width] = 0.45 * np.sin(2 * np.pi * 35 * w_t) * np.hanning(width)

    # 4. Éther / Shimmer céleste
    shimmer = np.sin(2 * np.pi * 528.0 * t) * (t / duration_sec) * 0.05

    # Mixage stéréo
    pan_l = 0.5 + 0.25 * np.cos(2 * np.pi * 0.5 * t)
    pan_r = 0.5 - 0.25 * np.cos(2 * np.pi * 0.5 * t)
    mix_l = drone * 0.5 + wind * pan_l + wing * 0.4 + shimmer
    mix_r = drone * 0.5 + wind * pan_r + wing * 0.4 + shimmer

    # Enveloppe globale (Fade in 0.3s, Fade out 0.5s)
    fade_in = int(0.3 * sample_rate)
    fade_out = int(0.5 * sample_rate)
    env = np.ones(total_samples)
    env[:fade_in] = np.sin(np.linspace(0, np.pi/2, fade_in)) ** 2
    env[-fade_out:] = np.cos(np.linspace(0, np.pi/2, fade_out)) ** 2
    mix_l *= env
    mix_r *= env

    # Normalisation -1 dBFS
    peak = max(np.max(np.abs(mix_l)), np.max(np.abs(mix_r)), 1e-6)
    scale = 0.89 / peak
    mix_l = np.clip(mix_l * scale, -1.0, 1.0)
    mix_r = np.clip(mix_r * scale, -1.0, 1.0)

    stereo = np.column_stack(((mix_l * 32767).astype(np.int16), (mix_r * 32767).astype(np.int16)))
    wavfile.write(out_wav, sample_rate, stereo)
    print(f"   ✅ Bande sonore masterisée : {out_wav}")
    return out_wav

def assembler_et_masteriser():
    print("=" * 80)
    print("🎬 [ASSEMBLAGE MASTER 2 PLANS] WAN 2.1 14B FLAGSHIP")
    print("=" * 80)

    if not os.path.exists(PLAN1) or not os.path.exists(PLAN2):
        print(f"❌ Erreur : L'un des plans manque :\n   Plan 1 : {PLAN1}\n   Plan 2 : {PLAN2}")
        return

    # 1. Concaténation des 2 plans
    t0 = time.time()
    print("\n🔗 [Étape 1] Concaténation fluide des Plans 1 & 2...")
    concat_txt = os.path.join(OUTPUT_DIR, "concat_2plans.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        f.write(f"file '{PLAN1.replace('\\', '/')}'\n")
        f.write(f"file '{PLAN2.replace('\\', '/')}'\n")

    subprocess.run([
        FFMPEG, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_txt,
        "-c:v", "h264_amf",
        "-b:v", "20M",
        ASSEMBLED_RAW
    ], check=True)
    duree_concat = time.time() - t0
    print(f"   ✅ Plans assemblés en {duree_concat:.2f}s : {ASSEMBLED_RAW}")

    # 2. Sound Design
    t_audio = time.time()
    generer_audio_2plans(SOUNDTRACK, duration_sec=2.125)
    duree_audio = time.time() - t_audio

    # 3. Mastering Full HD 1080p 60 FPS
    t_master = time.time()
    print(f"\n🚀 [Étape 2] Mastering Full HD 1080p 60 FPS (AMF Hardware CBR 20M)...")
    cmd_master = [
        FFMPEG, "-y",
        "-i", ASSEMBLED_RAW,
        "-i", SOUNDTRACK,
        "-vf", "scale=1920:1080:flags=lanczos,fps=60",
        "-c:v", "h264_amf",
        "-quality", "quality",
        "-rc", "cbr",
        "-b:v", "20M",
        "-c:a", "aac",
        "-b:a", "256k",
        "-shortest",
        MASTER_1080P
    ]
    subprocess.run(cmd_master, check=True)
    duree_master = time.time() - t_master
    print(f"   ✅ Mastering achevé en {duree_master:.2f}s : {MASTER_1080P}")

    # 4. Trame d'aperçu HD
    subprocess.run([FFMPEG, "-y", "-ss", "00:00:01.000", "-i", MASTER_1080P, "-vframes", "1", PREVIEW_PNG],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    rapport = {
        "projet": "Film 2 Plans Liés - Wan 2.1 14B Flagship",
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "resolution_native": "832x480",
        "resolution_master": "1920x1080 Full HD (60 FPS)",
        "duree_film_sec": 2.125,
        "plans": [
            {"id": 1, "nom": "01_horizon", "fichier": PLAN1},
            {"id": 2, "nom": "02_glisse", "fichier": PLAN2}
        ],
        "fichier_video_master": MASTER_1080P,
        "fichier_audio_master": SOUNDTRACK,
        "apercu_png": PREVIEW_PNG,
        "timings_secondes": {
            "concatenation": round(duree_concat, 2),
            "sound_design": round(duree_audio, 2),
            "mastering_1080p": round(duree_master, 2)
        }
    }
    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(rapport, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print("🎉 SUCCÈS TOTAL : FILM 2 PLANS MASTERISÉ AVEC SUCCÈS !")
    print(f"   🎥 Vidéo Full HD 1080p : {MASTER_1080P}")
    print(f"   🎵 Bande sonore 48kHz :  {SOUNDTRACK}")
    print(f"   📸 Aperçu HD :           {PREVIEW_PNG}")
    print(f"   📋 Rapport technique :   {REPORT_JSON}")
    print("=" * 80)

if __name__ == "__main__":
    assembler_et_masteriser()
