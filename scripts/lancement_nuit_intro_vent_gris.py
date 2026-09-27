#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/lancement_nuit_intro_vent_gris.py  —  LTX-2.5 EDITION (night of 2026-09-10)
Cinematic establishing shot of the Château du Vent-Gris (« L'HÉRITIER DU VIDE »)
— 10 s @ 24 fps 16:9, I2V from the user reference image.

ENGINE HISTORY (finding 2026-09-10, 6 destroyed configurations):
  Wan 2.2 I2V MoE / LowNoise is UNUSABLE on the sd-cli 6b3edaa + RDNA2 build
  that night: wan_vae staging (4.2 GB) on Vulkan0 despite vae=cpu / --vae-on-cpu,
  device lost "No fault detected" at highly variable memory pressures, MoE
  dead at the HighNoise→LowNoise switch, ~160 GB graph without --diffusion-fa.
  → Recorded in C:\\SD\\README.md (Wan line); retest on a fixed build.
  LTX-2.5 Distilled (recipe §1.1) goes THROUGH WITHOUT A PROBLEM the same vid_gen
  path (T2V 250 s, I2V 442 s, CPU VAE decoding 100 s, 65 healthy frames at probe) →
  the night deliverable switches to LTX-2.5 I2V, native 24 fps with generated audio.

DELIVERED RECIPE:
  1. 832×480 lead-in (16:9 Lanczos crop of the user reference image).
  2. 4 I2V shots of 65 frames @ 24 fps native (2.708 s each = 10.83 s → 10.0 s),
     Lightricks distilled 8-step sigmas, euler_a, cfg 1.0, seed 42, generated audio
     (kept in the raw shots, NOT mixed — sound joints too noisy).
  3. Chaining §1.8: the last frame of shot N leads in shot N+1.
  4. Full HD 1080p @ 24 fps conform (lanczos + AMD FidelityFX CAS 0.75, AMF).
  5. AI 4K UHD master (4x-UltraSharp Vulkan + CAS 0.75, upscale_video_ai.py).
  6. 10 s storm ambience (validated `sfx` workflow SA3 Small) + muxed listening MP4.

Resilience: resumption on existing files, 2 attempts per GPU phase (AMD driver
reset pitfall §1.10), load check before each GPU phase, final JSON report.
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime

from PIL import Image

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

REPO = r"C:\GIT\generator-assets"
SD_CLI = r"C:\SD\sd-cli.exe"
FFMPEG = r"C:\ffmpeg\dist\bin\ffmpeg.exe"
if not os.path.exists(FFMPEG):
    FFMPEG = r"C:\Program Files\Amuse\ffmpeg.exe"  # historical fallback

MODELS_DIR = r"C:\Modeles_LLM"
IMAGE_SOURCE = r"C:\Users\laurent\Downloads\Gemini_Generated_Image_3kvg3q3kvg3q3kvg.jpg"

OUTPUT_DIR = os.path.join(REPO, "output", "intro_vent_gris")
os.makedirs(OUTPUT_DIR, exist_ok=True)
RAPPORT = os.path.join(OUTPUT_DIR, "rapport_nuit.json")

LTX = os.path.join(MODELS_DIR, "LTX-2.5-Distilled-Q4_K_M.gguf")
LTX_VAE = os.path.join(MODELS_DIR, "ltx-2.5-video-vae-conv-bf16.safetensors")
LTX_AUDIO_VAE = os.path.join(MODELS_DIR, "ltx-2.5-audio-vae-bf16.safetensors")
LTX_LLM = os.path.join(MODELS_DIR, "gemma4-12b-with-proj-ltx-2.5-Q5_K_M.gguf")

# Official Lightricks distilled sigmas (8 steps, cfg 1.0 = 1 pass/step)
SIGMAS = "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"

PLANS = [
    {"cle": "plan1", "frames": 65, "prompt": "PROMPT_PLAN1"},
    {"cle": "plan2", "frames": 65, "prompt": "PROMPT_PLAN2"},
    {"cle": "plan3", "frames": 65, "prompt": "PROMPT_PLAN3"},
    {"cle": "plan4", "frames": 65, "prompt": "PROMPT_PLAN4"},
]
FPS = 24            # NATIVE LTX-2.5 cadence (no interpolation needed)
W, H = 832, 480     # ~394k px ≈ the validated 768×512 canvas; 32-aligned
STEPS = 8
CFG = 1.0
SEED = 42
DUREE_TOTALE = 10.0  # s (4 × 2.708 s = 10.83 s → trimmed to 10.0)

NEGATIF = (
    "text, watermark, logo, subtitles, warm colors, autumn colors, sunny, cartoon, "
    "anime, modern elements, crowds, blurry, out of focus, jitter, sudden cuts, "
    "glitch, low quality, noisy, distorted, morphing, lowres"
)

PROMPT_PLAN1 = (
    "Slow cinematic dolly-in toward a gaunt medieval fortress clinging to a "
    "windswept cliff above a storm-gray sea. Heavy lead-gray storm clouds drift "
    "slowly overhead, salt mist sweeps horizontally across the battlements, storm "
    "waves crash and foam against the dark rocks below, a distant sailing ship bobs "
    "gently on the swell, faint warm window lights flicker in the keep. Desaturated "
    "cold palette, painterly dark fantasy, oppressive melancholic atmosphere."
)
PROMPT_PLAN2 = (
    "Seamless continuation of the very slow dolly-in toward the medieval fortress "
    "on its cliff. The fortress grows slightly larger in frame as the camera glides "
    "steadily forward through drifting salt mist. Storm clouds crawl overhead, waves "
    "keep crashing on the dark rocks below, the distant sailing ship rocks on the "
    "swell, the warm window lights flicker faintly. Desaturated cold palette, "
    "painterly dark fantasy, oppressive melancholic atmosphere."
)
PROMPT_PLAN3 = (
    "Seamless continuation of the slow dolly-in: the fortress keep now dominates "
    "the frame from its windswept cliff. The camera keeps gliding steadily forward "
    "through thinning salt mist, battlements and narrow windows slowly growing "
    "larger, storm clouds crawling overhead, waves crashing below, warm window "
    "lights flickering faintly. Desaturated cold palette, painterly dark fantasy, "
    "oppressive melancholic atmosphere."
)
PROMPT_PLAN4 = (
    "Final continuation of the slow dolly-in, ending on a medium-wide view of the "
    "fortress gate and the high narrow window above it. The camera glides forward "
    "and slowly settles, mist drifting across the battlements, clouds turning slowly "
    "overhead, warm window light flickering steadily as if someone waits inside. "
    "Desaturated cold palette, painterly dark fantasy, oppressive melancholic "
    "atmosphere, the shot comes to rest for a title card."
)

PROMPT_AMBIANCE = (
    "violent coastal storm, strong gusting wind whistling over rocky sea cliffs, "
    "dense salt spray, heavy waves crashing on rocks below, cold howling ambience"
)

rapport = {
    "projet": "Intro Château du Vent-Gris — L'HÉRITIER DU VIDE (10 s establishing shot)",
    "date_debut": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "image_source": IMAGE_SOURCE,
    "moteur": "LTX-2.5 Distilled I2V (Wan 2.2 ruled out that night: vid_gen/RDNA2 bug, see C:/SD/README.md)",
    "recette": "4 shots × 65 frames @ 24 fps native, Lightricks 8-step sigmas, cfg 1.0, "
               "chaining §1.8 → 1080p CAS 0.75 conform → AI 4K",
    "seed": SEED,
    "etapes": [],
}


def log(message: str) -> None:
    ligne = f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
    print(ligne, flush=True)


def etape(nom: str, duree: float, details: str = "") -> None:
    rapport["etapes"].append({
        "etape": nom,
        "duree_sec": round(duree, 2),
        "duree_min": round(duree / 60, 2),
        "horodatage": datetime.now().strftime("%H:%M:%S"),
        "details": details,
    })
    with open(RAPPORT, "w", encoding="utf-8") as f:
        json.dump(rapport, f, indent=2, ensure_ascii=False)


def verifier_charge() -> bool:
    """AGENTS.md rule: never a heavy generation on a loaded machine."""
    try:
        res = subprocess.run(
            [sys.executable, os.path.join(REPO, "scripts", "check_charge_systeme.py")],
            capture_output=True, text=True, timeout=120,
        )
        return res.returncode == 0
    except Exception as exc:
        log(f"⚠️ Load check inconclusive ({exc}) — continuing.")
        return True


def executer(commande: list, fichier_log: str, tentatives: int = 2, gpu: bool = False) -> bool:
    """Runs a command with file log and retries (AMD driver reset pitfall)."""
    for essai in range(1, tentatives + 1):
        if gpu:
            if not verifier_charge():
                log("⛔ Machine busy — waiting 10 min before a new attempt.")
                time.sleep(600)
            log(f"  ▶ attempt {essai}/{tentatives}: {' '.join(os.path.basename(c) for c in commande[:3])}…")
        t0 = time.time()
        with open(fichier_log, "w", encoding="utf-8") as lf:
            code = subprocess.run(commande, stdout=lf, stderr=subprocess.STDOUT).returncode
        duree = time.time() - t0
        if code == 0:
            log(f"  ✅ succeeded in {duree/60:.2f} min")
            return True
        log(f"  ❌ failed with code {code} after {duree/60:.2f} min — log: {fichier_log}")
        time.sleep(60)
    return False


def conformer_amorce(source: str, destination: str) -> str:
    """Exact 16:9 crop + 832×480 Lanczos resize."""
    img = Image.open(source).convert("RGB")
    w, h = img.size
    cible = 16.0 / 9.0
    if abs(w / h - cible) > 0.005:
        nouvelle_l = int(h * cible)
        x0 = max(0, (w - nouvelle_l) // 2)
        img = img.crop((x0, 0, x0 + nouvelle_l, h))
        log(f"  📐 16:9 crop: {w}×{h} → {img.size[0]}×{img.size[1]}")
    img = img.resize((W, H), Image.Resampling.LANCZOS)
    img.save(destination, quality=100)
    log(f"  ✅ lead-in ready: {destination}")
    return destination


def generer_ltx_i2v(amorce: str, prompt: str, sortie: str, fichier_log: str, frames: int) -> bool:
    """Validated LTX-2.5 Distilled I2V recipe (Lightricks sigmas, cfg 1.0, native audio)."""
    commande = [
        SD_CLI, "-M", "vid_gen",
        "--diffusion-model", LTX,
        "--vae", LTX_VAE,
        "--audio-vae", LTX_AUDIO_VAE,
        "--llm", LTX_LLM,
        "-i", amorce,
        "-p", prompt,
        "-n", NEGATIF,
        "-W", str(W), "-H", str(H),
        "--video-frames", str(frames),
        "--fps", str(FPS),
        "--steps", str(STEPS),
        "--sigmas", SIGMAS,
        "--sampling-method", "euler_a",
        "--cfg-scale", str(CFG),
        "--diffusion-fa",
        "--backend", "diffusion=vulkan0,te=cpu,vae=cpu",
        "-s", str(SEED),
        "-o", sortie,
        "-v",
    ]
    ok = executer(commande, fichier_log, tentatives=2, gpu=True)
    if not ok:
        return False
    if not os.path.exists(sortie):
        candidat = sortie.replace(".webm", "_0.webm")
        if os.path.exists(candidat):
            os.rename(candidat, sortie)
    return os.path.exists(sortie)


def extraire_derniere_trame(video: str, destination: str) -> str:
    """Chaining §1.8: the last frame of shot N becomes the lead-in of shot N+1."""
    subprocess.run(
        [FFMPEG, "-y", "-sseof", "-0.15", "-i", video, "-update", "1", "-frames:v", "1", destination],
        capture_output=True,
    )
    if os.path.exists(destination):
        conformer_amorce(destination, destination)  # crops/resizes for safety
    return destination


def conformer_1080p(source: str, destination: str) -> bool:
    """Full HD scale + CAS 0.75, AMF hardware encoder (libx264 fallback), no audio."""
    base = [FFMPEG, "-y", "-i", source,
            "-vf", "scale=1920:1080:flags=lanczos,cas=0.75",
            "-an", "-pix_fmt", "yuv420p"]
    ok = subprocess.run(
        base + ["-c:v", "h264_amf", "-quality", "quality", "-rc", "cbr", "-b:v", "20M",
                destination],
        capture_output=True,
    ).returncode == 0
    if not ok:
        log("  ⚠️ h264_amf refused — libx264 fallback.")
        ok = subprocess.run(
            base + ["-c:v", "libx264", "-crf", "14", "-preset", "slow", destination],
            capture_output=True,
        ).returncode == 0
    return ok


def main() -> None:
    t_global = time.time()
    chemins = {
        "amorce": os.path.join(OUTPUT_DIR, "amorce_832x480.png"),
        "master_1080p": os.path.join(OUTPUT_DIR, "intro_vent_gris_10s_1080p.mp4"),
        "apercu": os.path.join(OUTPUT_DIR, "intro_vent_gris_apercu_t5s.png"),
        "master_4k": os.path.join(OUTPUT_DIR, "intro_vent_gris_10s_4k_master.mp4"),
        "ambiance": os.path.join(OUTPUT_DIR, "ambiance_tempete_vent_gris.wav"),
        "master_1080p_son": os.path.join(OUTPUT_DIR, "intro_vent_gris_10s_1080p_avec_ambiance.mp4"),
    }
    for plan in PLANS:
        cle = plan["cle"]
        chemins[cle] = os.path.join(OUTPUT_DIR, f"{cle}_brut.webm")
        chemins[cle + "_1080p"] = os.path.join(OUTPUT_DIR, f"{cle}_1080p.mp4")
        if plan["cle"] != "plan1":
            chemins["amorce_" + cle] = os.path.join(OUTPUT_DIR, f"amorce_{cle}.png")

    print("=" * 85)
    log("🌙 NIGHT RUN (LTX-2.5 EDITION) — INTRO CHÂTEAU DU VENT-GRIS (10 s @ 24 fps)")
    log(f"   Outputs: {OUTPUT_DIR}")
    print("=" * 85)

    manquants = [p for p in (SD_CLI, FFMPEG, LTX, LTX_VAE, LTX_AUDIO_VAE, LTX_LLM,
                             IMAGE_SOURCE) if not os.path.exists(p)]
    if manquants:
        log(f"⛔ Missing required files: {manquants}")
        sys.exit(2)

    # ── Phase 1: 832×480 lead-in ─────────────────────────────────────────────
    t0 = time.time()
    if not os.path.exists(chemins["amorce"]):
        conformer_amorce(IMAGE_SOURCE, chemins["amorce"])
    etape("832×480 lead-in (Lanczos 16:9)", time.time() - t0)

    # ── Phases 2-5: chained I2V generation of the 4 shots (65 frames native 24fps) ─
    for idx, plan in enumerate(PLANS):
        cle = plan["cle"]
        prompt_plan = globals()[plan["prompt"]]
        if idx == 0:
            amorce_plan = chemins["amorce"]
        elif not os.path.exists(chemins[PLANS[idx - 1]["cle"]]):
            log(f"⏭️ {cle} skipped: {PLANS[idx - 1]['cle']} absent (chaining impossible).")
            continue
        else:
            cle_amorce = "amorce_" + cle
            if not os.path.exists(chemins[cle_amorce]):
                extraire_derniere_trame(chemins[PLANS[idx - 1]["cle"]], chemins[cle_amorce])
                etape(f"Last frame extraction {PLANS[idx - 1]['cle']} (chaining §1.8)", 0)
            amorce_plan = chemins[cle_amorce]

        if os.path.exists(chemins[cle]):
            log(f"⏭️ {cle} already present.")
            continue
        log(f"🎥 Shot {idx + 1}/{len(PLANS)} — LTX-2.5 I2V ({plan['frames']} frames @ {FPS} fps)…")
        t0 = time.time()
        ok = generer_ltx_i2v(amorce_plan, prompt_plan, chemins[cle],
                             os.path.join(OUTPUT_DIR, f"{cle}.log"), frames=plan["frames"])
        if ok:
            etape(f"{cle} LTX-2.5 I2V ({plan['frames']} frames"
                  + (", chained" if idx > 0 else "") + ")", time.time() - t0)
        elif idx == 0:
            log("⛔ Shot 1 impossible after 2 attempts — stopping the chain.")
            sys.exit(3)
        else:
            log(f"⚠️ {cle} impossible — the assembly will use the previous shots.")
            etape(f"{cle} LTX-2.5 I2V — FAILURE (assembly on previous shots)", time.time() - t0)

    # ── Phase 6: per-shot 1080p conform (native 24 fps, no interpolation) ────
    for plan in PLANS:
        cle = plan["cle"]
        if os.path.exists(chemins[cle]) and not os.path.exists(chemins[cle + "_1080p"]):
            log(f"🎬 Phase 6: 1080p conform — {cle}…")
            t0 = time.time()
            ok = conformer_1080p(chemins[cle], chemins[cle + "_1080p"])
            etape(f"CAS 1080p conform ({cle})", time.time() - t0, "OK" if ok else "FAILED")
            if not ok:
                chemins[cle + "_1080p"] = None

    # ── Phase 7: concat + 1080p master 10.0 s ────────────────────────────────
    if not os.path.exists(chemins["master_1080p"]):
        log("🎬 Phase 7: Full HD 1080p @ 24 fps master assembly…")
        t0 = time.time()
        segments = [chemins[p["cle"] + "_1080p"] for p in PLANS
                    if chemins.get(p["cle"] + "_1080p")]
        if not segments:
            log("⛔ No usable segment — stopping.")
            sys.exit(4)
        if len(segments) > 1:
            liste = os.path.join(OUTPUT_DIR, "concat_list.txt")
            with open(liste, "w", encoding="utf-8") as f:
                for s in segments:
                    f.write(f"file '{s.replace(os.sep, '/')}'\n")
            entree = ["-f", "concat", "-safe", "0", "-i", liste]
        else:
            entree = ["-i", segments[0]]
        ok = subprocess.run(
            [FFMPEG, "-y", *entree, "-t", str(DUREE_TOTALE),
             "-c:v", "h264_amf", "-quality", "quality", "-rc", "cbr", "-b:v", "20M",
             "-pix_fmt", "yuv420p",
             chemins["master_1080p"]],
            capture_output=True,
        ).returncode == 0
        if not ok:
            ok = subprocess.run(
                [FFMPEG, "-y", *entree, "-t", str(DUREE_TOTALE),
                 "-c:v", "libx264", "-crf", "14", "-preset", "slow", "-pix_fmt", "yuv420p",
                 chemins["master_1080p"]],
                capture_output=True,
            ).returncode == 0
        etape("1080p @ 24 fps master (concat 4 shots, 10.0 s)", time.time() - t0,
              "OK" if ok else "FAILED")
        subprocess.run(
            [FFMPEG, "-y", "-ss", "5", "-i", chemins["master_1080p"], "-vframes", "1",
             chemins["apercu"]],
            capture_output=True,
        )

    # ── Phase 8: AI 4K master ────────────────────────────────────────────────
    if os.path.exists(chemins["master_1080p"]) and not os.path.exists(chemins["master_4k"]):
        log("🚀 Phase 8: AI 4K super-resolution (4x-UltraSharp Vulkan + CAS 0.75)…")
        t0 = time.time()
        ok = executer(
            [sys.executable, os.path.join(REPO, "scripts", "upscale_video_ai.py"),
             chemins["master_1080p"], "-o", chemins["master_4k"],
             "-r", "3840:2160", "--cas", "0.75", "-b", "50M"],
            os.path.join(OUTPUT_DIR, "upscale_4k.log"), tentatives=2, gpu=True,
        ) and os.path.exists(chemins["master_4k"])
        etape("AI 4K UHD master (4x-UltraSharp + CAS)", time.time() - t0,
              "OK" if ok else "FAILED — 1080p master kept")

    # ── Phase 9: storm ambience (bonus, validated sfx workflow) ──────────────
    if not os.path.exists(chemins["ambiance"]):
        log("🔊 Phase 9: 10 s storm ambience (sfx workflow, SA3 Small)…")
        t0 = time.time()
        ok = executer(
            [sys.executable, os.path.join(REPO, "main.py"), "-w", "sfx", PROMPT_AMBIANCE,
             "--duration", "10", "--seed", str(SEED), "-o", "ambiance_tempete_vent_gris",
             "--output-dir", OUTPUT_DIR],
            os.path.join(OUTPUT_DIR, "ambiance.log"), tentatives=2, gpu=True,
        )
        brut = os.path.join(OUTPUT_DIR, "ambiance_tempete_vent_gris.wav")
        if ok and os.path.exists(brut):
            os.replace(brut, chemins["ambiance"])
        etape("10 s storm ambience (AI sfx)", time.time() - t0,
              "OK" if os.path.exists(chemins["ambiance"]) else "FAILED — master delivered without sound")

    if os.path.exists(chemins["ambiance"]) and not os.path.exists(chemins["master_1080p_son"]):
        subprocess.run(
            [FFMPEG, "-y", "-i", chemins["master_1080p"], "-i", chemins["ambiance"],
             "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest",
             chemins["master_1080p_son"]],
            capture_output=True,
        )

    # ── Wrap-up ──────────────────────────────────────────────────────────────
    total = time.time() - t_global
    rapport["date_fin"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rapport["duree_totale_min"] = round(total / 60, 2)
    rapport["livrables"] = {k: v for k, v in chemins.items() if v and os.path.exists(v)}
    with open(RAPPORT, "w", encoding="utf-8") as f:
        json.dump(rapport, f, indent=2, ensure_ascii=False)

    print("=" * 85)
    log(f"🌅 NIGHT CHAIN FINISHED IN {total/60:.1f} min — deliverables present:")
    for cle, chemin in rapport["livrables"].items():
        log(f"   • {cle} : {chemin}")
    log(f"   📊 report: {RAPPORT}")
    print("=" * 85)


if __name__ == "__main__":
    main()
