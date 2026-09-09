#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module de rendu par diffusion via stable-diffusion.cpp (Flux.1 & SDXL en Vulkan).
Supporte Txt2Img, Img2Img, High-Res Fix, Circular Seamless, et l'injection de LoRAs.
Détecte automatiquement les modèles Flux.1 (GGUF + Encoders) et SDXL / SD 1.5 (Checkpoints Safetensors).
"""

import os
import subprocess
from typing import List, Optional, Tuple, Union
from PIL import Image
from core.config import (
    DEFAULT_CLIP_L,
    DEFAULT_H3_AUDIO_VAE,
    DEFAULT_H3_LLM,
    DEFAULT_H3_REF2VA_MODEL,
    DEFAULT_H3_VIDEO_VAE,
    DEFAULT_LORA_DIRS,
    DEFAULT_SD_CLI,
    DEFAULT_SD_MODEL,
    DEFAULT_T5XXL,
    DEFAULT_VAE,
    DEFAULT_BACKEND,
    DEFAULT_THREADS,
    DEFAULT_WAN_MODEL,
    DEFAULT_WAN_VAE,
    DEFAULT_WAN_T5XXL,
    resoudre_modele_video,
    resoudre_vae_video,
    resoudre_t5xxl_video,
    TEMP_IMAGE
)


def est_modele_flux(sd_model_path: str) -> bool:
    """Détecte si le modèle spécifié est un modèle Flux (GGUF ou nom contenant flux)."""
    nom = os.path.basename(sd_model_path).lower()
    return "flux" in nom or nom.endswith(".gguf")


def formater_prompt_avec_loras(prompt: str, loras: Optional[List[Union[str, Tuple[str, float]]]] = None) -> str:
    """Ajoute les balises <lora:nom:poids> au prompt si des LoRAs sont spécifiés."""
    if not loras:
        return prompt

    tags_loras = []
    for item in loras:
        if isinstance(item, (tuple, list)):
            nom, poids = item[0], item[1]
            tags_loras.append(f"<lora:{nom}:{poids}>")
        elif isinstance(item, str):
            if ":" in item:
                nom, poids = item.split(":", 1)
            else:
                nom, poids = item, "1.0"
            tags_loras.append(f"<lora:{nom.strip()}:{poids.strip()}>")

    if tags_loras:
        return f"{prompt} {' '.join(tags_loras)}"
    return prompt


def generer_image_vulkan(
    prompt: str,
    sd_cli: str = DEFAULT_SD_CLI,
    sd_model: str = DEFAULT_SD_MODEL,
    clip_l: str = DEFAULT_CLIP_L,
    t5xxl: str = DEFAULT_T5XXL,
    vae: str = DEFAULT_VAE,
    backend: str = DEFAULT_BACKEND,
    threads: int = DEFAULT_THREADS,
    width: int = 1024,
    height: int = 1024,
    steps: int = 25,
    guidance: float = 3.5,
    cfg_scale: float = 1.0,
    seed: int = -1,
    init_img: Optional[str] = None,
    strength: float = 0.75,
    circular: bool = False,
    hires: bool = False,
    hires_scale: float = 2.0,
    hires_strength: float = 0.5,
    loras: Optional[List[Union[str, Tuple[str, float]]]] = None,
    lora_dir: Optional[str] = None,
    output_path: str = TEMP_IMAGE
) -> Image.Image:
    """
    Exécute sd-cli.exe sous Vulkan avec support des LoRAs et bascule auto Flux / SDXL.
    """
    prompt_final = formater_prompt_avec_loras(prompt, loras)
    is_flux = est_modele_flux(sd_model)

    moteur_nom = "Flux.1" if is_flux else "SDXL / SD"
    mode_str = "Img2Img" if init_img else ("Seamless Tile" if circular else "Txt2Img")
    if loras:
        mode_str += f" + {len(loras)} LoRA(s)"

    cfg_effectif = cfg_scale if cfg_scale != 1.0 or is_flux else 7.0
    print(f"[{moteur_nom} - {mode_str}] Lancement de sd-cli ({width}x{height}, steps={steps}, cfg={cfg_effectif})...")

    if is_flux:
        commande = [
            sd_cli,
            "--diffusion-model", sd_model,
            "--clip_l", clip_l,
            "--t5xxl", t5xxl,
            "--vae", vae,
            "-p", prompt_final,
            "--steps", str(steps),
            "--cfg-scale", str(cfg_scale),
            "--guidance", str(guidance),
            "--sampling-method", "euler",
            "-W", str(width),
            "-H", str(height),
            "-o", output_path,
            "-t", str(threads),
            "--vae-tiling",
            "--backend", backend,
            "-v"
        ]
    else:
        # Checkpoint monolithique SDXL ou SD 1.5 (.safetensors)
        commande = [
            sd_cli,
            "-m", sd_model,
            "-p", prompt_final,
            "--steps", str(steps),
            "--cfg-scale", str(cfg_effectif),
            "--sampling-method", "euler_a",
            "-W", str(width),
            "-H", str(height),
            "-o", output_path,
            "-t", str(threads),
            "--vae-tiling",
            "--backend", backend,
            "-v"
        ]

    # Gestion du dossier LoRA
    dossier_lora_effectif = lora_dir or DEFAULT_LORA_DIRS[0]
    if os.path.exists(dossier_lora_effectif):
        commande.extend(["--lora-model-dir", dossier_lora_effectif, "--lora-apply-mode", "auto"])

    if seed >= 0:
        commande.extend(["-s", str(seed)])
    else:
        commande.extend(["-s", "-1"])

    if init_img and os.path.exists(init_img):
        commande.extend(["-i", init_img, "--strength", str(strength)])

    if circular:
        commande.append("--circular")

    if hires:
        commande.extend([
            "--hires",
            "--hires-scale", str(hires_scale),
            "--hires-denoising-strength", str(hires_strength)
        ])

    try:
        subprocess.run(commande, check=True)
        if not os.path.exists(output_path):
            raise FileNotFoundError(f"Le fichier de sortie {output_path} n'a pas été produit.")
        return Image.open(output_path)
    except Exception as e:
        print(f"❌ Erreur lors du rendu ({moteur_nom}) via sd-cli : {e}")
        raise


def generer_video_vulkan(
    prompt: str,
    sd_cli: str = DEFAULT_SD_CLI,
    model_path: Optional[str] = None,
    vae_path: Optional[str] = None,
    t5xxl_path: Optional[str] = None,
    high_noise_model_path: Optional[str] = None,
    video_frames: int = 33,
    fps: int = 24,
    width: int = 832,
    height: int = 480,
    steps: int = 20,
    cfg_scale: float = 6.0,
    flow_shift: float = 3.0,
    sampling_method: str = "euler",
    seed: int = -1,
    negative_prompt: Optional[str] = None,
    init_img: Optional[str] = None,
    end_img: Optional[str] = None,
    control_video_dir: Optional[str] = None,
    offload_to_cpu: bool = True,
    diffusion_fa: bool = True,
    temporal_tiling: bool = True,
    backend: str = DEFAULT_BACKEND,
    threads: int = DEFAULT_THREADS,
    output_path: str = "godot_assets/output_video.webm"
) -> str:
    """
    Génère une séquence vidéo (.webm ou séquence d'images) via stable-diffusion.cpp
    en exploitant l'accélération matérielle Vulkan (Wan 2.1/2.2, LTX-2.3/2.5, MiniMax-H3).
    Supporte Text-to-Video (T2V), Image-to-Video (I2V), First & Last Frame (FLF2V), et Video-to-Video (V2V).
    """
    modele_effectif = resoudre_modele_video(model_path)
    vae_effectif = resoudre_vae_video(vae_path)
    t5xxl_effectif = resoudre_t5xxl_video(t5xxl_path)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    mode_str = "T2V (Text-to-Video)"
    if init_img and end_img:
        mode_str = "FLF2V (First & Last Frame to Video)"
    elif init_img:
        mode_str = "I2V (Image-to-Video)"
    elif control_video_dir:
        mode_str = "V2V (Video-to-Video Control)"

    print(f"[Vidéo Vulkan - {mode_str}] Génération ({width}x{height}, {video_frames} trames @ {fps} fps, steps={steps})...")

    commande = [
        sd_cli,
        "-M", "vid_gen",
        "--diffusion-model", modele_effectif,
        "-p", prompt,
        "-W", str(width),
        "-H", str(height),
        "--video-frames", str(video_frames),
        "--fps", str(fps),
        "--steps", str(steps),
        "--cfg-scale", str(cfg_scale),
        "--flow-shift", str(flow_shift),
        "--sampling-method", sampling_method,
        "-o", output_path,
        "-t", str(threads),
        "--backend", backend,
        "-v"
    ]

    if vae_effectif and os.path.exists(vae_effectif):
        commande.extend(["--vae", vae_effectif])
    if t5xxl_effectif and os.path.exists(t5xxl_effectif):
        commande.extend(["--t5xxl", t5xxl_effectif])
    if high_noise_model_path and os.path.exists(high_noise_model_path):
        commande.extend(["--high-noise-diffusion-model", high_noise_model_path])

    if negative_prompt:
        commande.extend(["-n", negative_prompt])

    if init_img and os.path.exists(init_img):
        commande.extend(["--init-img", init_img])
    if end_img and os.path.exists(end_img):
        commande.extend(["--end-img", end_img])
    if control_video_dir and os.path.exists(control_video_dir):
        commande.extend(["--control-video", control_video_dir])

    # Optimisation VRAM : les modèles 1.3B tiennent à 100% dans la VRAM (16 Go).
    # On n'active --offload-to-cpu que pour les modèles lourds (14B) ou si explicitement requis.
    activer_offload = offload_to_cpu and ("14b" in modele_effectif.lower())
    if activer_offload:
        commande.append("--offload-to-cpu")
    if diffusion_fa:
        commande.append("--diffusion-fa")
    if temporal_tiling:
        commande.append("--temporal-tiling")

    if seed >= 0:
        commande.extend(["-s", str(seed)])
    else:
        commande.extend(["-s", "-1"])

    try:
        subprocess.run(commande, check=True)
        if not os.path.exists(output_path):
            raise FileNotFoundError(f"La vidéo de sortie {output_path} n'a pas été produite.")
        print(f"✅ Vidéo générée avec succès : {output_path}")
        return output_path
    except Exception as e:
        print(f"❌ Erreur lors de la génération vidéo via sd-cli : {e}")
        raise


def arrondir_grille_h3(video_frames: int) -> int:
    """Arrondit un nombre de trames à la grille MiniMax-H3 « 5 + 17k » (minimum 5).

    H3 n'accepte que les comptes de trames 5, 22, 39, 56… ; sd-cli arrondit
    lui-même à la hausse, on le fait ici pour que les logs et sorties soient exacts.
    """
    if video_frames <= 5:
        return 5
    return 5 + 17 * ((video_frames - 5 + 16) // 17)


def generer_video_ref2va_h3(
    prompt: str,
    sd_cli: str = DEFAULT_SD_CLI,
    model_path: Optional[str] = None,
    vae_path: Optional[str] = None,
    audio_vae_path: Optional[str] = None,
    llm_path: Optional[str] = None,
    ref_video_dir: Optional[str] = None,
    ref_audio_path: Optional[str] = None,
    video_frames: int = 22,
    fps: int = 24,
    width: int = 864,
    height: int = 480,
    steps: int = 20,
    cfg_scale: float = 1.0,
    seed: int = 42,
    max_vram: int = 10,
    backend: str = "diffusion=vulkan0,te=cpu,vae=cpu",
    threads: int = DEFAULT_THREADS,
    output_path: str = "output/h3_ref2va.webm",
    dry_run: bool = False,
    log_fn=print
) -> str:
    """
    Génère une vidéo AVEC audio via MiniMax-H3 Ref2VA : une vidéo de référence
    (dossier de trames à 24 fps) + son WAV appairé conditionnent le DiT (balises
    <Video 1> / <Audio 1> dans le prompt). Recette validée le 2026-09-09
    (RX 6950 XT 16 Go / 31,8 Go RAM) — cf. MEMORY_BANK §1.16 :
      • placement mémoire obligatoire : DiT sur GPU plafonné (--max-vram, sinon
        device lost), Qwen3-VL 32B et VAE vidéo sur CPU (sinon OOM VRAM) ;
      • grille de trames « 5 + 17k » (22/39/56…), 24 fps imposé par le modèle ;
      • Ref2VA incompatible avec --init-img/--end-img (la référence porte la
        continuité) ; flow-shift géré en interne par H3 (ne pas l'imposer).
    """
    modele = model_path or DEFAULT_H3_REF2VA_MODEL
    vae = vae_path or DEFAULT_H3_VIDEO_VAE
    audio_vae = audio_vae_path or DEFAULT_H3_AUDIO_VAE
    llm = llm_path or DEFAULT_H3_LLM

    manquants = [p for p in (modele, vae, audio_vae, llm) if not os.path.exists(p)]
    if manquants:
        raise FileNotFoundError(
            "Modèles MiniMax-H3 Ref2VA manquants : " + "; ".join(manquants)
            + " — téléchargement : repo HF leejet/MiniMax-H3-GGUF (DiT ref2va) et Comfy-Org/MiniMax-H3 (VAEs)"
        )
    if not ref_video_dir or not os.path.isdir(ref_video_dir):
        raise ValueError(f"Dossier de trames de référence invalide : {ref_video_dir}")
    if ref_audio_path and not os.path.exists(ref_audio_path):
        raise FileNotFoundError(f"WAV de référence introuvable : {ref_audio_path}")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # Grille 5+17k et canevas aligné 32 px (H3 arrondit sinon à la hausse)
    frames_grille = arrondir_grille_h3(video_frames)
    w_aligne = max(32, (width + 31) // 32 * 32)
    h_aligne = max(32, (height + 31) // 32 * 32)

    n_ref = len([f for f in os.listdir(ref_video_dir) if f.lower().endswith((".png", ".jpg", ".jpeg"))])
    log_fn(
        f"[H3 Ref2VA] {w_aligne}x{h_aligne}, {frames_grille} trames @ 24 fps, "
        f"steps={steps}, cfg={cfg_scale}, seed={seed}, réf={n_ref} trames"
        + (f" + audio {os.path.basename(ref_audio_path)}" if ref_audio_path else "")
    )

    commande = [
        sd_cli,
        "-M", "vid_gen",
        "--diffusion-model", modele,
        "--vae", vae,
        "--audio-vae", audio_vae,
        "--llm", llm,
        "-p", prompt,
        "--ref-video", ref_video_dir,
        "-W", str(w_aligne),
        "-H", str(h_aligne),
        "--video-frames", str(frames_grille),
        "--fps", str(fps),
        "--steps", str(steps),
        "--cfg-scale", str(cfg_scale),
        "--sampling-method", "euler",
        "--diffusion-fa",
        "--offload-to-cpu",
        "--rng", "cpu",
        "--max-vram", str(max_vram),
        "-s", str(seed),
        "-o", output_path,
        "-t", str(threads),
        "--backend", backend,
        "-v"
    ]
    if ref_audio_path:
        commande.extend(["--ref-video-audio", ref_audio_path])

    if dry_run:
        log_fn(f"[H3 Ref2VA] DRY-RUN — commande construite ({len(commande)} args), non exécutée :")
        log_fn("  " + " ".join(f'"{c}"' if " " in c else c for c in commande))
        return output_path

    try:
        subprocess.run(commande, check=True)
        if not os.path.exists(output_path):
            raise FileNotFoundError(f"La vidéo de sortie {output_path} n'a pas été produite.")
        log_fn(f"✅ Vidéo H3 Ref2VA générée : {output_path}")
        return output_path
    except Exception as e:
        log_fn(f"❌ Erreur lors de la génération H3 Ref2VA via sd-cli : {e}")
        raise

