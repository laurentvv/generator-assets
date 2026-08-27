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
    DEFAULT_LORA_DIRS,
    DEFAULT_SD_CLI,
    DEFAULT_SD_MODEL,
    DEFAULT_T5XXL,
    DEFAULT_VAE,
    DEFAULT_BACKEND,
    DEFAULT_THREADS,
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
            "-v"
        ]

    # Gestion du dossier LoRA
    dossier_lora_effectif = lora_dir or DEFAULT_LORA_DIRS[0]
    if os.path.exists(dossier_lora_effectif):
        commande.extend(["--lora-model-dir", dossier_lora_effectif, "--lora-apply-mode", "auto"])

    if seed >= 0:
        commande.extend(["-s", str(seed)])

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
