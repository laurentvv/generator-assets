"""
generate_10s_cinema.py
Production complète du film cinématographique de 10 secondes (10 plans liés @ 832x480 natif).
Modèle : Wan 2.1 14B Flagship (Euler 8 steps, Flash Attention, Tiling VAE)
Son : Sound Design cinématique procédural 48 kHz Stéréo (10.6s)
Master : Full HD 1080p 60 FPS via encodeur matériel AMD AMF (h264_amf, 20 Mbps CBR)
"""
import os
import sys
import time
import json
import subprocess
from datetime import datetime
import numpy as np
from scipy.io import wavfile

# Forçage encodage UTF-8 sous console Windows
for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

SD_CLI = r"C:\SD\sd-cli.exe"
FFMPEG = r"C:\Program Files\Amuse\ffmpeg.exe"
DIFFUSION_14B = r"C:\Modeles_LLM\wan2.1-t2v-14b-Q4_K_M.gguf"
VAE = r"C:\Modeles_LLM\wan_2.1_vae.safetensors"
T5XXL = r"C:\Modeles_LLM\umt5-xxl-encoder-Q4_K_M.gguf"

OUTPUT_DIR = r"C:\GIT\generator-assets\output\film_10s"
os.makedirs(OUTPUT_DIR, exist_ok=True)
REPORT_FILE = os.path.join(OUTPUT_DIR, "rapport_timings_production.json")

FPS = 16
FRAMES_PER_SHOT = 17  # 17 trames @ 16 FPS = 1.0625s par plan (Zone de stabilité parfaite 14.05 Go)
STEPS = 8             # Compromis vitesse/qualité optimal pour 14B

SHOTS = [
    {
        "id": 1,
        "name": "01_horizon",
        "title": "Plan 1 : Horizon - Émergence majestueuse au couchant doré",
        "prompt": (
            "Cinematic ultra-wide establishing shot, a colossal golden dragon with shimmering iridescent scales "
            "gliding majestically into glowing orange and purple sunset clouds, volumetric god rays, "
            "hyper-detailed, photorealistic, 8k resolution, smooth slow horizontal camera pan."
        )
    },
    {
        "id": 2,
        "name": "02_glisse",
        "title": "Plan 2 : Envergure - Vol plané rasant captant la lumière",
        "prompt": (
            "Cinematic medium tracking shot, the colossal golden dragon soaring gracefully through golden hour skies, "
            "wings wide spread catching radiant sunlight, glowing amber eyes, detailed scale textures, photorealistic, 8k."
        )
    },
    {
        "id": 3,
        "name": "03_plongeon",
        "title": "Plan 3 : Dynamique - Plongée en piqué à travers la brume",
        "prompt": (
            "Cinematic dynamic tracking shot, the colossal golden dragon folding its massive wings and diving "
            "steeply downwards through storm clouds, turbulent atmospheric vortices, dramatic speed, photorealistic, 8k."
        )
    },
    {
        "id": 4,
        "name": "04_nuages",
        "title": "Plan 4 : Immersion - Fendant les cumulus d'orage violets",
        "prompt": (
            "Cinematic immersion shot, the golden dragon banking sharply through dense glowing cumulus clouds, "
            "mist parting around its horns and dorsal crest, dramatic volumetric lighting, photorealistic, 8k."
        )
    },
    {
        "id": 5,
        "name": "05_sortie",
        "title": "Plan 5 : Vitesse - Sortie de brume dans le ciel enflammé",
        "prompt": (
            "Cinematic action shot, the golden dragon breaking out from dark storm clouds into open fiery sky, "
            "trailing glowing golden embers and atmospheric condensation mist, high speed blur, photorealistic, 8k."
        )
    },
    {
        "id": 6,
        "name": "06_traveling",
        "title": "Plan 6 : Texture - Traveling latéral serré sur les écailles d'or",
        "prompt": (
            "Cinematic lateral tracking shot closely following the dragon's torso, shimmering iridescent gold armor "
            "scales and razor-sharp talons cutting through high altitude wind, intricate reflections, photorealistic, 8k."
        )
    },
    {
        "id": 7,
        "name": "07_portrait",
        "title": "Plan 7 : Héroïque - Gros plan sur le visage et le regard flamboyant",
        "prompt": (
            "Cinematic heroic close-up on the colossal golden dragon's face, piercing glowing amber eye staring "
            "confidently forward, majestic crown horns, ancient wisdom and power, masterpiece, photorealistic, 8k."
        )
    },
    {
        "id": 8,
        "name": "08_climax_feu",
        "title": "Plan 8 : Climax - Souffle titanesque de feu doré",
        "prompt": (
            "Cinematic climax shot, front angle, the colossal golden dragon opening its powerful jaws wide and "
            "unleashing a colossal torrent of brilliant golden fire breath, glowing plasma embers, smoke and light, 8k."
        )
    },
    {
        "id": 9,
        "name": "09_spirale",
        "title": "Plan 9 : Élévation - Tonneau aérien et ascension vers le zénith",
        "prompt": (
            "Cinematic dynamic wide shot, the golden dragon executing a heroic aerial barrel roll, sweeping upwards "
            "through burning sunset clouds toward the twilight stratosphere, glowing wingtips, photorealistic, 8k."
        )
    },
    {
        "id": 10,
        "name": "10_epilogue",
        "title": "Plan 10 : Épilogue - Silhouette céleste dans la nuit étoilée",
        "prompt": (
            "Cinematic wide ending shot, the silhouette of the colossal golden dragon ascending peacefully into "
            "the starlit twilight sky, glowing embers fading into distant stars, epic atmospheric finale, 8k."
        )
    }
]

def generer_soundtrack_10s(out_wav, duration_sec=10.625, sample_rate=48000):
    """
    Génère la bande-son cinématique 48 kHz stéréo sur mesure pour les 10 plans.
    """
    t_start = time.time()
    print(f"\n🎵 [Sound Design] Synthèse de la bande sonore cinématique unifiée ({duration_sec:.2f}s, 48 kHz Stéréo)...")
    total_samples = int(duration_sec * sample_rate)
    t = np.linspace(0, duration_sec, total_samples, endpoint=False)

    # 1. Drone sub-bass orchestral (48 Hz - 55 Hz)
    f_sweep = np.linspace(48.0, 56.0, total_samples)
    drone = np.sin(2 * np.pi * f_sweep * t) * 0.35
    drone += np.sin(2 * np.pi * f_sweep * 2 * t) * 0.15

    # 2. Vent atmosphérique dynamique
    noise = np.random.normal(0, 1, total_samples)
    wind = np.zeros(total_samples)
    alpha = 0.035
    for i in range(1, total_samples):
        wind[i] = alpha * noise[i] + (1 - alpha) * wind[i-1]
    wind_mod = 0.4 + 0.6 * np.sin(2 * np.pi * 0.25 * t)
    wind = wind * wind_mod * 0.40

    # 3. Battements d'ailes (plans 3 à 5 : t=2.5s à 5.5s)
    flaps = np.zeros(total_samples)
    for flap_time in [2.5, 3.8, 5.0]:
        idx = int(flap_time * sample_rate)
        width = int(0.35 * sample_rate)
        if idx + width < total_samples:
            w_t = np.linspace(0, 0.35, width)
            flaps[idx:idx+width] += 0.35 * np.sin(2 * np.pi * 38 * w_t) * np.hanning(width)

    # 4. Climax : Rugissement et souffle de feu (plan 8 : t=7.2s à 9.0s)
    climax_sound = np.zeros(total_samples)
    idx_climax = int(7.2 * sample_rate)
    climax_len = int(2.2 * sample_rate)
    if idx_climax + climax_len <= total_samples:
        t_c = np.linspace(0, 2.2, climax_len)
        f_roar = np.linspace(85.0, 50.0, climax_len)
        roar = np.sin(2 * np.pi * f_roar * t_c) * np.exp(-0.6 * t_c) * 0.45
        fire = np.convolve(np.random.normal(0, 1, climax_len), np.ones(80)/80, mode="same") * 0.40
        climax_sound[idx_climax:idx_climax+climax_len] = (roar + fire) * np.hanning(climax_len)

    # Mixage stéréo
    pan_l = 0.5 + 0.25 * np.cos(2 * np.pi * 0.2 * t)
    pan_r = 0.5 - 0.25 * np.cos(2 * np.pi * 0.2 * t)
    mix_l = drone * 0.5 + wind * pan_l + flaps * 0.4 + climax_sound * 0.5
    mix_r = drone * 0.5 + wind * pan_r + flaps * 0.4 + climax_sound * 0.5

    # Enveloppe globale (Fade in 1.2s, Fade out 2.0s)
    fade_in = int(1.2 * sample_rate)
    fade_out = int(2.0 * sample_rate)
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
    elapsed = time.time() - t_start
    print(f"   ✅ Bande-son masterisée en {elapsed:.2f}s : {out_wav}")
    return out_wav, elapsed

def main():
    t_global_start = time.time()
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rapport = {
        "projet": "Film 10 Secondes - L'Épopée du Dragon d'Or (10 Plans Liés)",
        "date_debut": date_str,
        "gpu": "AMD Radeon RX 6950 XT (16 Go VRAM GDDR6)",
        "backend": "Vulkan 1.4 Native (GPU) + UMT5-XXL (CPU)",
        "diffusion_model": os.path.basename(DIFFUSION_14B),
        "params": "14 Milliards",
        "resolution_native": "832x480 (16:9)",
        "resolution_master": "1920x1080 Full HD (60 FPS)",
        "plans_prevus": 10,
        "trames_par_plan": FRAMES_PER_SHOT,
        "steps_diffusion": STEPS,
        "etapes": []
    }

    print("=" * 80)
    print("🎬 [TOP DÉPART PRODUCTION] FILM 10 SECONDES : 10 PLANS LIÉS")
    print(f"   Heure de départ : {date_str}")
    print(f"   Modèle Flagship : Wan 2.1 14B ({STEPS} étapes Euler)")
    print(f"   Résolution native : 832×480 | Format par plan : 17 trames (1.06s)")
    print(f"   Sortie finale : Full HD 1080p 60 FPS (Master AMF)")
    print("=" * 80)

    clips = []
    for shot in SHOTS:
        sid = shot["id"]
        sname = shot["name"]
        stitle = shot["title"]
        sprompt = shot["prompt"]
        out_raw = os.path.join(OUTPUT_DIR, f"{sname}.webm")
        log_file = os.path.join(OUTPUT_DIR, f"{sname}.log")

        t_plan_start = time.time()
        print("\n" + "-" * 75)
        print(f"🎥 [{sid:02d}/10] {stitle}")
        print(f"   ⏰ Heure de lancement : {datetime.now().strftime('%H:%M:%S')}")
        print(f"   📝 Prompt : {sprompt}")

        cmd = [
            SD_CLI,
            "-M", "vid_gen",
            "--diffusion-model", DIFFUSION_14B,
            "--vae", VAE,
            "--t5xxl", T5XXL,
            "-p", sprompt,
            "-W", "832",
            "-H", "480",
            "--video-frames", str(FRAMES_PER_SHOT),
            "--fps", str(FPS),
            "--steps", str(STEPS),
            "--sampling-method", "euler",
            "--diffusion-fa",
            "--temporal-tiling",
            "--vae-tiling",
            "--backend", "diffusion=vulkan0,te=cpu",
            "-o", out_raw
        ]

        # Redirection propre dans un fichier log pour éviter tout blocage de buffer sous Windows
        with open(log_file, "w", encoding="utf-8") as lf:
            subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, check=True)

        duree_plan = time.time() - t_plan_start
        print(f"   ✅ Plan {sid:02d}/10 achevé à {datetime.now().strftime('%H:%M:%S')}")
        print(f"   ⏱️ Durée : {duree_plan:.1f}s ({duree_plan/60:.2f} min) | Moyenne : {duree_plan/STEPS:.2f}s / step")
        clips.append(out_raw)

        rapport["etapes"].append({
            "etape": f"Plan {sid:02d} : {sname}",
            "titre": stitle,
            "trames": FRAMES_PER_SHOT,
            "steps": STEPS,
            "duree_sec": round(duree_plan, 2),
            "duree_min": round(duree_plan / 60, 2),
            "sec_par_step": round(duree_plan / STEPS, 2),
            "fichier": out_raw
        })

    # 1. Concaténation des 10 plans vidéo
    t_concat_start = time.time()
    print("\n" + "=" * 80)
    print(f"🔗 [Assemblage] Concaténation des 10 plans vidéo (Horodatage : {datetime.now().strftime('%H:%M:%S')})...")
    concat_list = os.path.join(OUTPUT_DIR, "concat_list.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for c in clips:
            c_esc = c.replace("\\", "/")
            f.write(f"file '{c_esc}'\n")

    video_assembled = os.path.join(OUTPUT_DIR, "film_10s_brut.mp4")
    subprocess.run([
        FFMPEG, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list,
        "-c:v", "h264_amf",
        "-b:v", "20M",
        video_assembled
    ], check=True)
    duree_concat = time.time() - t_concat_start
    print(f"   ✅ 10 plans assemblés avec succès en {duree_concat:.2f}s : {video_assembled}")
    rapport["etapes"].append({
        "etape": "Concaténation des 10 plans vidéo",
        "duree_sec": round(duree_concat, 2)
    })

    # 2. Sound Design 10.6 secondes
    soundtrack = os.path.join(OUTPUT_DIR, "soundtrack_10s.wav")
    _, duree_sound = generer_soundtrack_10s(soundtrack, duration_sec=10.625)
    rapport["etapes"].append({
        "etape": "Sound Design procédural 10.6s stéréo 48kHz",
        "duree_sec": round(duree_sound, 2)
    })

    # 3. Mixage final & Conformation YouTube Full HD 1080p (60 FPS)
    t_master_start = time.time()
    film_final_1080p = os.path.join(OUTPUT_DIR, "film_10s_dragon_1080p_master.mp4")
    print(f"\n🚀 [Mastering] Conformation YouTube Full HD 1080p 60 FPS (AMF Hardware CBR 20M)...")

    cmd_master = [
        FFMPEG, "-y",
        "-i", video_assembled,
        "-i", soundtrack,
        "-vf", "scale=1920:1080:flags=lanczos,fps=60",
        "-c:v", "h264_amf",
        "-quality", "quality",
        "-rc", "cbr",
        "-b:v", "20M",
        "-c:a", "aac",
        "-b:a", "256k",
        "-t", "00:00:10.000",
        film_final_1080p
    ]
    subprocess.run(cmd_master, check=True)
    duree_master = time.time() - t_master_start
    print(f"   ✅ Mastering Full HD achevé en {duree_master:.2f}s : {film_final_1080p}")
    rapport["etapes"].append({
        "etape": "Mastering Full HD 1080p 60FPS + Mixage Audio Master",
        "duree_sec": round(duree_master, 2)
    })

    # 4. Trame d'aperçu HD extraite au milieu (t = 5s)
    preview_png = os.path.join(OUTPUT_DIR, "film_10s_preview_hd.png")
    subprocess.run([FFMPEG, "-y", "-ss", "00:00:05", "-i", film_final_1080p, "-vframes", "1", preview_png],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    t_global_total = time.time() - t_global_start
    rapport["date_fin"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rapport["duree_totale_sec"] = round(t_global_total, 2)
    rapport["duree_totale_min"] = round(t_global_total / 60, 2)
    rapport["fichier_final_1080p"] = film_final_1080p
    rapport["apercu_png"] = preview_png

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(rapport, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print("🎉 SUCCÈS TOTAL : FILM 10 SECONDES (10 PLANS LIÉS) TERMINÉ !")
    print(f"   ⏱️ TEMPS DE PRODUCTION TOTAL : {t_global_total/60:.2f} minutes ({t_global_total:.1f}s)")
    print(f"   🎥 Fichier Vidéo Full HD 1080p : {film_final_1080p}")
    print(f"   📸 Trame d'Aperçu HD :           {preview_png}")
    print(f"   📊 Rapport des Timings :         {REPORT_FILE}")
    print("=" * 80)

if __name__ == "__main__":
    main()
