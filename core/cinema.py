#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core/cinema.py — plan-séquence IA « monoplan » (VALIDÉ utilisateur le 2026-09-10).

Recette gagnante (MEMORY_BANK §1.17, intro Vent-Gris « L'HÉRITIER DU VIDE ») :
une SEULE génération LTX-2.5 I2V depuis une image d'amorce (65 trames = plafond
GPU stable), ralentie vers la durée cible avec interpolation motion-compensée,
puis re-cadrée par un zoom pur CONÇU (rampe monotone avec easing — aucune mesure
de suivi dans le warp : le traceur NCC injecterait son bruit en translation).
Résultat : plan unique sans coupe ni vibration de caméra.

Pourquoi pas plus long/multi-plans : le chaînage I2V crée des coupes de contenu
(nuages/vagues réinterprétés → saccades, toutes les réparations v2-v5 rejetées),
et le module interne `ltxav` de LTX mange ~29 Mo de VRAM par trame (plafond
~81 trames à 832×480 sur RX 6950 XT). Le ralenti est donc LE levier durée.
"""

import os
import shutil
import subprocess
import tempfile
from typing import Callable, Dict, Optional, Tuple

from PIL import Image

from core.config import DEFAULT_MODEL_DIR, DEFAULT_SD_CLI, DEFAULT_FFMPEG as FFMPEG_PATH

# Modèles LTX-2.5 Distilled validés (§1.1 / §1.17)
LTX_DIT = os.path.join(DEFAULT_MODEL_DIR, "LTX-2.5-Distilled-Q4_K_M.gguf")
LTX_VAE = os.path.join(DEFAULT_MODEL_DIR, "ltx-2.5-video-vae-conv-bf16.safetensors")
LTX_LLM = os.path.join(DEFAULT_MODEL_DIR, "gemma4-12b-with-proj-ltx-2.5-Q5_K_M.gguf")

# Sigmas officiels distillés Lightricks (8 steps, cfg 1.0 = 1 passe/step)
SIGMAS_LTX = "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"

NEGATIF_DEFAUT = (
    "text, watermark, logo, subtitles, warm colors, autumn colors, sunny, cartoon, "
    "anime, modern elements, crowds, blurry, jitter, sudden cuts, glitch, low "
    "quality, noisy, distorted, morphing, lowres"
)

# Ancre du zoom en ratio de cadre (validée sur le château du Vent-Gris :
# position du sujet principal légèrement à gauche du centre)
ANCRE_X, ANCRE_Y = 0.656, 0.472


def conformer_amorce_16_9(source: str, destination: str, largeur: int = 832,
                          hauteur: int = 480) -> str:
    """Recadrage 16:9 exact + redimensionnement Lanczos (aucune déformation)."""
    img = Image.open(source).convert("RGB")
    w, h = img.size
    cible = 16.0 / 9.0
    if abs(w / h - cible) > 0.005:
        nouvelle_l = int(h * cible)
        x0 = max(0, (w - nouvelle_l) // 2)
        img = img.crop((x0, 0, x0 + nouvelle_l, h))
    img = img.resize((largeur, hauteur), Image.Resampling.LANCZOS)
    img.save(destination, quality=100)
    return destination


def generer_monoplan_ltx(
    amorce: str,
    prompt: str,
    sortie: str,
    frames: int = 65,
    fps: int = 24,
    seed: int = 42,
    negatif: str = NEGATIF_DEFAUT,
    max_vram: int = 10,
    log_fn: Callable[[str], None] = print,
) -> str:
    """Plan unique LTX-2.5 Distilled I2V (recette §1.17, 8 steps euler_a, cfg 1.0)."""
    manquants = [p for p in (DEFAULT_SD_CLI, LTX_DIT, LTX_VAE, LTX_LLM) if not os.path.exists(p)]
    if manquants:
        raise FileNotFoundError("Modèles LTX-2.5 ou sd-cli manquants : " + "; ".join(manquants))
    os.makedirs(os.path.dirname(os.path.abspath(sortie)), exist_ok=True)
    commande = [
        DEFAULT_SD_CLI, "-M", "vid_gen",
        "--diffusion-model", LTX_DIT,
        "--vae", LTX_VAE,
        "--llm", LTX_LLM,
        "-i", amorce,
        "-p", prompt,
        "-n", negatif,
        "-W", "832", "-H", "480",
        "--video-frames", str(frames),
        "--fps", str(fps),
        "--steps", "8",
        "--sigmas", SIGMAS_LTX,
        "--sampling-method", "euler_a",
        "--cfg-scale", "1.0",
        "--diffusion-fa",
        "--max-vram", str(max_vram),
        "--backend", "diffusion=vulkan0,te=cpu,vae=cpu",
        "-s", str(seed),
        "-o", sortie,
        "-v",
    ]
    log_fn("[cinéma] Génération monoplan LTX-2.5 ({} trames @ {} fps, seed {})…".format(frames, fps, seed))
    subprocess.run(commande, check=True)
    if not os.path.exists(sortie):
        candidat = sortie.replace(".webm", "_0.webm")
        if os.path.exists(candidat):
            os.rename(candidat, sortie)
    if not os.path.exists(sortie):
        raise RuntimeError(f"Monoplan non produit : {sortie}")
    return sortie


def ralentir_interp_1080p(webm: str, sortie: str, duree_cible: float,
                          fps: int = 24) -> Tuple[str, int]:
    """Ralenti temporel vers la durée cible + interpolation motion-compensée 24→24
    + upscale lanczos 1080p (l'étape zoom travaille en coordonnées 1920×1080)."""
    info = subprocess.run(
        [FFMPEG_PATH, "-i", webm], capture_output=True, text=True, encoding="utf-8",
        errors="replace",
    ).stderr
    import re
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", info)
    if not m:
        raise RuntimeError(f"Durée illisible : {webm}")
    duree_src = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    facteur = duree_cible / max(duree_src, 0.1)
    ok = subprocess.run(
        [FFMPEG_PATH, "-y", "-v", "error", "-i", webm, "-vf",
         f"setpts={facteur:.4f}*PTS,"
         f"minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"
         "scale=1920:1080:flags=lanczos",
         "-an", "-c:v", "libx264", "-crf", "12", "-preset", "slow",
         "-pix_fmt", "yuv420p", sortie],
        capture_output=True,
    ).returncode == 0
    if not ok or not os.path.exists(sortie):
        raise RuntimeError(f"Ralenti/interpolation échoué : {sortie}")
    return sortie, facteur


def zoom_pur(video_1080p: str, sortie: str, zoom_debut: float = 1.10,
             zoom_fin: float = 1.32, ancre: Tuple[float, float] = (ANCRE_X, ANCRE_Y),
             cas: float = 0.75) -> str:
    """Rampe de zoom CONÇUE (smootherstep) autour d'une ancre fixe — aucune mesure
    de suivi dans le warp : le rendu est incapable de vibrer par construction."""
    import cv2
    import numpy as np

    tmp = tempfile.mkdtemp(prefix="cinema_zoom_")
    try:
        subprocess.run(
            [FFMPEG_PATH, "-y", "-v", "error", "-i", video_1080p, "-fps_mode", "passthrough",
             "-q:v", "2", os.path.join(tmp, "f_%04d.png")], capture_output=True, check=True,
        )
        pngs = sorted(f for f in os.listdir(tmp) if f.startswith("f_"))
        n = len(pngs)
        W, H = 1920, 1080
        centre = (ancre[0] * W, ancre[1] * H)
        u = np.linspace(0.0, 1.0, n)
        ease = u * u * u * (u * (u * 6.0 - 15.0) + 10.0)  # smootherstep
        for i, nom in enumerate(pngs):
            img = cv2.imread(os.path.join(tmp, nom))
            k = 1.0 / (zoom_debut + (zoom_fin - zoom_debut) * ease[i])
            tx = centre[0] * (1.0 - k)
            ty = centre[1] * (1.0 - k)
            tx = min(max(tx, min(0.0, W * (1 - k))), max(0.0, W * (1 - k)))
            ty = min(max(ty, min(0.0, H * (1 - k))), max(0.0, H * (1 - k)))
            M = np.array([[k, 0.0, tx], [0.0, k, ty]], dtype=np.float64)
            corr = cv2.warpAffine(img, M, (W, H),
                                  flags=cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP)
            cv2.imwrite(os.path.join(tmp, "s_%04d.png" % (i + 1)), corr,
                        [cv2.IMWRITE_PNG_COMPRESSION, 3])
        filtre_cas = f",cas={cas}" if cas else ""
        subprocess.run(
            [FFMPEG_PATH, "-y", "-v", "error", "-framerate", "24", "-start_number", "1",
             "-i", os.path.join(tmp, "s_%04d.png"), "-frames:v", str(n),
             "-vf", "format=yuv420p" + filtre_cas,
             "-c:v", "libx264", "-crf", "16", sortie],
            capture_output=True, check=True,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return sortie


def muxer_audio(video: str, wav: str, sortie: str) -> str:
    """Colle une piste audio (lit sonore) sur la vidéo, vidéo copiée à l'identique."""
    subprocess.run(
        [FFMPEG_PATH, "-y", "-v", "error", "-i", video, "-i", wav,
         "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", sortie],
        capture_output=True, check=True,
    )
    return sortie


def generer_lit_ambiance(prompt: str, duree: float, seed: int = 42,
                         chemin_wav: Optional[str] = None) -> str:
    """Lit sonore via le moteur SFX IA validé (SA3 Small, normalisation incluse).
    Écrit un WAV prêt à muxer (et son OGG Godot à côté si chemin_wav fourni)."""
    import numpy as np
    import soundfile as sf
    from core.sfx_ia import generer_sfx_ia

    res = generer_sfx_ia(prompt, duree=duree, seed=seed)
    if chemin_wav is None:
        fd, chemin_wav = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
    sf.write(chemin_wav, res["audio"], res["sr"], subtype="PCM_16", format="WAV")
    if res["rognage_pct"] > 0.01:
        # rogner les silences structurels comme le workflow sfx (± garde-fou 50 %)
        audio = res["audio"]
        seuil = 0.0056  # ≈ −45 dBFS
        actifs = np.where(np.abs(audio).max(axis=1) > seuil)[0]
        if len(actifs) and (actifs[-1] - actifs[0]) > len(audio) * 0.5:
            audio = audio[actifs[0]:actifs[-1] + 1]
            sf.write(chemin_wav, audio, res["sr"], subtype="PCM_16", format="WAV")
    return chemin_wav
