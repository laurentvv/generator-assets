#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/lancement_nuit_intro_vent_gris.py  —  ÉDITION LTX-2.5 (nuit du 2026-09-10)
Plan d'établissement cinématique du Château du Vent-Gris (« L'HÉRITIER DU VIDE »)
— 10 s @ 24 fps 16:9, I2V depuis l'image de référence utilisateur.

HISTORIQUE MOTEUR (constat 2026-09-10, 6 configurations détruites) :
  Wan 2.2 I2V MoE / LowNoise est INUTILISABLE sur le build sd-cli 6b3edaa + RDNA2
  cette nuit : staging wan_vae (4,2 Go) sur Vulkan0 malgré vae=cpu / --vae-on-cpu,
  device lost « No fault detected » à des pressions mémoire très variables, MoE
  mort au basculement HighNoise→LowNoise, graphe ~160 Go sans --diffusion-fa.
  → Consigné dans C:\\SD\\README.md (ligne Wan) ; retester sur un build corrigé.
  LTX-2.5 Distilled (recette §1.1) passe SANS PROBLÈME le même chemin vid_gen
  (T2V 250 s, I2V 442 s, décodage VAE CPU 100 s, 65 trames saines au probe) →
  le livrable de nuit bascule sur LTX-2.5 I2V, natif 24 fps avec audio généré.

RECETTE LIVRÉE :
  1. Amorce 832×480 (recadrage 16:9 Lanczos de l'image de référence utilisateur).
  2. 4 plans I2V de 65 trames @ 24 fps natif (2,708 s chacun = 10,83 s → 10,0 s),
     sigmas distillés Lightricks 8 steps, euler_a, cfg 1.0, seed 42, audio généré
     (conservé dans les plans bruts, NON mixé — raccords sonores trop bruités).
  3. Chaînage §1.8 : l'ultime trame du plan N amorce le plan N+1.
  4. Conformation Full HD 1080p @ 24 fps (lanczos + AMD FidelityFX CAS 0.75, AMF).
  5. Master 4K UHD IA (4x-UltraSharp Vulkan + CAS 0.75, upscale_video_ai.py).
  6. Ambiance tempête 10 s (workflow `sfx` SA3 Small validé) + MP4 d'écoute muxé.

Résilience : reprise sur fichiers existants, 2 essais par phase GPU (écueil resets
pilote AMD §1.10), contrôle de charge avant chaque phase GPU, rapport JSON final.
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from PIL import Image

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

REPO = r"C:\GIT\generator-assets"
SD_CLI = r"C:\SD\sd-cli.exe"
FFMPEG = r"C:\ffmpeg\dist\bin\ffmpeg.exe"
if not os.path.exists(FFMPEG):
    FFMPEG = r"C:\Program Files\Amuse\ffmpeg.exe"  # repli historique

MODELS_DIR = r"C:\Modeles_LLM"
IMAGE_SOURCE = r"C:\Users\laurent\Downloads\Gemini_Generated_Image_3kvg3q3kvg3q3kvg.jpg"

OUTPUT_DIR = os.path.join(REPO, "output", "intro_vent_gris")
os.makedirs(OUTPUT_DIR, exist_ok=True)
RAPPORT = os.path.join(OUTPUT_DIR, "rapport_nuit.json")

LTX = os.path.join(MODELS_DIR, "LTX-2.5-Distilled-Q4_K_M.gguf")
LTX_VAE = os.path.join(MODELS_DIR, "ltx-2.5-video-vae-conv-bf16.safetensors")
LTX_AUDIO_VAE = os.path.join(MODELS_DIR, "ltx-2.5-audio-vae-bf16.safetensors")
LTX_LLM = os.path.join(MODELS_DIR, "gemma4-12b-with-proj-ltx-2.5-Q5_K_M.gguf")

# Sigmas officiels distillés Lightricks (8 steps, cfg 1.0 = 1 passe/step)
SIGMAS = "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"

PLANS = [
    {"cle": "plan1", "frames": 65, "prompt": "PROMPT_PLAN1"},
    {"cle": "plan2", "frames": 65, "prompt": "PROMPT_PLAN2"},
    {"cle": "plan3", "frames": 65, "prompt": "PROMPT_PLAN3"},
    {"cle": "plan4", "frames": 65, "prompt": "PROMPT_PLAN4"},
]
FPS = 24            # cadence NATIVE LTX-2.5 (aucune interpolation nécessaire)
W, H = 832, 480     # ~394k px ≈ le canevas validé 768×512 ; aligné 32
STEPS = 8
CFG = 1.0
SEED = 42
DUREE_TOTALE = 10.0  # s (4 × 2,708 s = 10,83 s → rogner à 10,0)

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
    "projet": "Intro Château du Vent-Gris — L'HÉRITIER DU VIDE (plan d'établissement 10 s)",
    "date_debut": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "image_source": IMAGE_SOURCE,
    "moteur": "LTX-2.5 Distilled I2V (Wan 2.2 écarté cette nuit : bug vid_gen/RDNA2, cf. C:/SD/README.md)",
    "recette": "4 plans × 65 trames @ 24 fps natif, sigmas Lightricks 8 steps, cfg 1.0, "
               "chaînage §1.8 → conform 1080p CAS 0.75 → 4K IA",
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
    """Règle AGENTS.md : jamais de génération lourde sur machine chargée."""
    try:
        res = subprocess.run(
            [sys.executable, os.path.join(REPO, "scripts", "check_charge_systeme.py")],
            capture_output=True, text=True, timeout=120,
        )
        return res.returncode == 0
    except Exception as exc:
        log(f"⚠️ Contrôle de charge indécis ({exc}) — on poursuit.")
        return True


def executer(commande: list, fichier_log: str, tentatives: int = 2, gpu: bool = False) -> bool:
    """Exécute une commande avec log fichier et réessais (écueil resets pilote AMD)."""
    for essai in range(1, tentatives + 1):
        if gpu:
            if not verifier_charge():
                log("⛔ Machine occupée — attente 10 min avant nouvel essai.")
                time.sleep(600)
            log(f"  ▶ essai {essai}/{tentatives} : {' '.join(os.path.basename(c) for c in commande[:3])}…")
        t0 = time.time()
        with open(fichier_log, "w", encoding="utf-8") as lf:
            code = subprocess.run(commande, stdout=lf, stderr=subprocess.STDOUT).returncode
        duree = time.time() - t0
        if code == 0:
            log(f"  ✅ réussi en {duree/60:.2f} min")
            return True
        log(f"  ❌ échec code {code} après {duree/60:.2f} min — log : {fichier_log}")
        time.sleep(60)
    return False


def conformer_amorce(source: str, destination: str) -> str:
    """Recadrage 16:9 exact + redimensionnement 832×480 Lanczos."""
    img = Image.open(source).convert("RGB")
    w, h = img.size
    cible = 16.0 / 9.0
    if abs(w / h - cible) > 0.005:
        nouvelle_l = int(h * cible)
        x0 = max(0, (w - nouvelle_l) // 2)
        img = img.crop((x0, 0, x0 + nouvelle_l, h))
        log(f"  📐 recadrage 16:9 : {w}×{h} → {img.size[0]}×{img.size[1]}")
    img = img.resize((W, H), Image.Resampling.LANCZOS)
    img.save(destination, quality=100)
    log(f"  ✅ amorce prête : {destination}")
    return destination


def generer_ltx_i2v(amorce: str, prompt: str, sortie: str, fichier_log: str, frames: int) -> bool:
    """Recette LTX-2.5 Distilled I2V validée (sigmas Lightricks, cfg 1.0, audio natif)."""
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
    """Chaînage §1.8 : l'ultime trame du plan N devient l'amorce du plan N+1."""
    subprocess.run(
        [FFMPEG, "-y", "-sseof", "-0.15", "-i", video, "-update", "1", "-frames:v", "1", destination],
        capture_output=True,
    )
    if os.path.exists(destination):
        conformer_amorce(destination, destination)  # recadre/redimensionne par sécurité
    return destination


def conformer_1080p(source: str, destination: str) -> bool:
    """Échelle Full HD + CAS 0.75, encodeur matériel AMF (repli libx264), sans audio."""
    base = [FFMPEG, "-y", "-i", source,
            "-vf", "scale=1920:1080:flags=lanczos,cas=0.75",
            "-an", "-pix_fmt", "yuv420p"]
    ok = subprocess.run(
        base + ["-c:v", "h264_amf", "-quality", "quality", "-rc", "cbr", "-b:v", "20M",
                destination],
        capture_output=True,
    ).returncode == 0
    if not ok:
        log("  ⚠️ h264_amf refusé — repli libx264.")
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
    log("🌙 LANCEMENT DE NUIT (ÉDITION LTX-2.5) — INTRO CHÂTEAU DU VENT-GRIS (10 s @ 24 fps)")
    log(f"   Sorties : {OUTPUT_DIR}")
    print("=" * 85)

    manquants = [p for p in (SD_CLI, FFMPEG, LTX, LTX_VAE, LTX_AUDIO_VAE, LTX_LLM,
                             IMAGE_SOURCE) if not os.path.exists(p)]
    if manquants:
        log(f"⛔ Fichiers requis manquants : {manquants}")
        sys.exit(2)

    # ── Phase 1 : amorce 832×480 ─────────────────────────────────────────────
    t0 = time.time()
    if not os.path.exists(chemins["amorce"]):
        conformer_amorce(IMAGE_SOURCE, chemins["amorce"])
    etape("Amorce 832×480 (Lanczos 16:9)", time.time() - t0)

    # ── Phases 2-5 : génération I2V chaînée des 4 plans (65 trames natif 24fps) ─
    for idx, plan in enumerate(PLANS):
        cle = plan["cle"]
        prompt_plan = globals()[plan["prompt"]]
        if idx == 0:
            amorce_plan = chemins["amorce"]
        elif not os.path.exists(chemins[PLANS[idx - 1]["cle"]]):
            log(f"⏭️ {cle} sauté : {PLANS[idx - 1]['cle']} absent (chaînage impossible).")
            continue
        else:
            cle_amorce = "amorce_" + cle
            if not os.path.exists(chemins[cle_amorce]):
                extraire_derniere_trame(chemins[PLANS[idx - 1]["cle"]], chemins[cle_amorce])
                etape(f"Extraction dernière trame {PLANS[idx - 1]['cle']} (chaînage §1.8)", 0)
            amorce_plan = chemins[cle_amorce]

        if os.path.exists(chemins[cle]):
            log(f"⏭️ {cle} déjà présent.")
            continue
        log(f"🎥 Plan {idx + 1}/{len(PLANS)} — LTX-2.5 I2V ({plan['frames']} trames @ {FPS} fps)…")
        t0 = time.time()
        ok = generer_ltx_i2v(amorce_plan, prompt_plan, chemins[cle],
                             os.path.join(OUTPUT_DIR, f"{cle}.log"), frames=plan["frames"])
        if ok:
            etape(f"{cle} LTX-2.5 I2V ({plan['frames']} trames"
                  + (", chaîné" if idx > 0 else "") + ")", time.time() - t0)
        elif idx == 0:
            log("⛔ Plan 1 impossible après 2 essais — arrêt de la chaîne.")
            sys.exit(3)
        else:
            log(f"⚠️ {cle} impossible — l'assemblage utilisera les plans précédents.")
            etape(f"{cle} LTX-2.5 I2V — ÉCHEC (assemblage sur plans précédents)", time.time() - t0)

    # ── Phase 6 : conform 1080p par plan (natif 24 fps, pas d'interpolation) ────
    for plan in PLANS:
        cle = plan["cle"]
        if os.path.exists(chemins[cle]) and not os.path.exists(chemins[cle + "_1080p"]):
            log(f"🎬 Phase 6 : conform 1080p — {cle}…")
            t0 = time.time()
            ok = conformer_1080p(chemins[cle], chemins[cle + "_1080p"])
            etape(f"Conform 1080p CAS ({cle})", time.time() - t0, "OK" if ok else "ÉCHEC")
            if not ok:
                chemins[cle + "_1080p"] = None

    # ── Phase 7 : concat + master 1080p 10,0 s ────────────────────────────────
    if not os.path.exists(chemins["master_1080p"]):
        log("🎬 Phase 7 : assemblage master Full HD 1080p @ 24 fps…")
        t0 = time.time()
        segments = [chemins[p["cle"] + "_1080p"] for p in PLANS
                    if chemins.get(p["cle"] + "_1080p")]
        if not segments:
            log("⛔ Aucun segment exploitable — arrêt.")
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
        etape("Master 1080p @ 24 fps (concat 4 plans, 10,0 s)", time.time() - t0,
              "OK" if ok else "ÉCHEC")
        subprocess.run(
            [FFMPEG, "-y", "-ss", "5", "-i", chemins["master_1080p"], "-vframes", "1",
             chemins["apercu"]],
            capture_output=True,
        )

    # ── Phase 8 : master 4K IA ────────────────────────────────────────────────
    if os.path.exists(chemins["master_1080p"]) and not os.path.exists(chemins["master_4k"]):
        log("🚀 Phase 8 : super-résolution IA 4K (4x-UltraSharp Vulkan + CAS 0.75)…")
        t0 = time.time()
        ok = executer(
            [sys.executable, os.path.join(REPO, "scripts", "upscale_video_ai.py"),
             chemins["master_1080p"], "-o", chemins["master_4k"],
             "-r", "3840:2160", "--cas", "0.75", "-b", "50M"],
            os.path.join(OUTPUT_DIR, "upscale_4k.log"), tentatives=2, gpu=True,
        ) and os.path.exists(chemins["master_4k"])
        etape("Master 4K UHD IA (4x-UltraSharp + CAS)", time.time() - t0,
              "OK" if ok else "ÉCHEC — master 1080p conservé")

    # ── Phase 9 : ambiance tempête (bonus, workflow sfx validé) ───────────────
    if not os.path.exists(chemins["ambiance"]):
        log("🔊 Phase 9 : ambiance tempête 10 s (workflow sfx, SA3 Small)…")
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
        etape("Ambiance tempête 10 s (sfx IA)", time.time() - t0,
              "OK" if os.path.exists(chemins["ambiance"]) else "ÉCHEC — master livré sans son")

    if os.path.exists(chemins["ambiance"]) and not os.path.exists(chemins["master_1080p_son"]):
        subprocess.run(
            [FFMPEG, "-y", "-i", chemins["master_1080p"], "-i", chemins["ambiance"],
             "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest",
             chemins["master_1080p_son"]],
            capture_output=True,
        )

    # ── Bilan ────────────────────────────────────────────────────────────────
    total = time.time() - t_global
    rapport["date_fin"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rapport["duree_totale_min"] = round(total / 60, 2)
    rapport["livrables"] = {k: v for k, v in chemins.items() if v and os.path.exists(v)}
    with open(RAPPORT, "w", encoding="utf-8") as f:
        json.dump(rapport, f, indent=2, ensure_ascii=False)

    print("=" * 85)
    log(f"🌅 CHAÎNE DE NUIT TERMINÉE EN {total/60:.1f} min — livrables présents :")
    for cle, chemin in rapport["livrables"].items():
        log(f"   • {cle} : {chemin}")
    log(f"   📊 rapport : {RAPPORT}")
    print("=" * 85)


if __name__ == "__main__":
    main()
