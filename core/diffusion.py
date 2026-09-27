#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diffusion rendering module via stable-diffusion.cpp (Flux.1 & SDXL on Vulkan).
Supports Txt2Img, Img2Img, High-Res Fix, Circular Seamless, and LoRA injection.
Automatically detects Flux.1 models (GGUF + Encoders) and SDXL / SD 1.5 (Safetensors Checkpoints).
"""

import os
import tempfile
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
    resoudre_modele_video,
    resoudre_vae_video,
    resoudre_t5xxl_video
)
from core.process import run_engine


def est_modele_flux(sd_model_path: str) -> bool:
    """Detects whether the given model is a Flux model (GGUF or name containing flux)."""
    nom = os.path.basename(sd_model_path).lower()
    return "flux" in nom or nom.endswith(".gguf")


def formater_prompt_avec_loras(prompt: str, loras: Optional[List[Union[str, Tuple[str, float]]]] = None) -> str:
    """Adds the <lora:name:weight> tags to the prompt when LoRAs are specified."""
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
    control_image: Optional[str] = None,
    control_net: Optional[str] = None,
    control_strength: float = 0.9,
    ip_adapter: Optional[str] = None,
    ip_adapter_image: Optional[str] = None,
    ip_adapter_strength: float = 1.0,
    clip_vision: Optional[str] = None,
    circular: bool = False,
    hires: bool = False,
    hires_scale: float = 2.0,
    hires_strength: float = 0.5,
    loras: Optional[List[Union[str, Tuple[str, float]]]] = None,
    lora_dir: Optional[str] = None,
    output_path: Optional[str] = None
) -> Image.Image:
    """
    Runs sd-cli.exe under Vulkan with LoRA support and automatic Flux / SDXL switching.
    Image ControlNet support (control_image + control_net required together;
    recipe validated on 2026-09-26: SDXL juggernautXL + ControlNet OpenPose xinsir,
    A/B with/without in output/test_controlnet/). Without output_path, the render goes
    through a unique temporary file (tempfile), removed after reading: compatible with
    several parallel runs and insensitive to leftovers from a previous call.
    """
    prompt_final = formater_prompt_avec_loras(prompt, loras)
    is_flux = est_modele_flux(sd_model)

    if control_image and not os.path.exists(control_image):
        raise FileNotFoundError(f"ControlNet control image not found: {control_image}")
    if (control_image or control_net) and not (control_image and control_net):
        raise ValueError("ControlNet: control_image and control_net must be provided together.")
    if ip_adapter and not (ip_adapter_image and clip_vision):
        raise ValueError("IP-Adapter: ip_adapter, ip_adapter_image and clip_vision must be provided together.")
    if ip_adapter_image and not os.path.exists(ip_adapter_image):
        raise FileNotFoundError(f"IP-Adapter reference image not found: {ip_adapter_image}")

    chemin_temporaire = output_path is None
    if chemin_temporaire:
        descripteur, output_path = tempfile.mkstemp(suffix=".png", prefix="ga_rendu_")
        os.close(descripteur)
        # sd-cli must create the file itself: we remove the empty placeholder so
        # a stale image can never be read back on failure.
        os.remove(output_path)

    moteur_nom = "Flux.1" if is_flux else "SDXL / SD"
    mode_str = "Img2Img" if init_img else ("Seamless Tile" if circular else "Txt2Img")
    if control_image and control_net:
        mode_str += " + ControlNet"
    if ip_adapter:
        mode_str += " + IP-Adapter"
    if loras:
        mode_str += f" + {len(loras)} LoRA(s)"

    cfg_effectif = cfg_scale if cfg_scale != 1.0 or is_flux else 7.0
    print(f"[{moteur_nom} - {mode_str}] Launching sd-cli ({width}x{height}, steps={steps}, cfg={cfg_effectif})...")

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
        # Monolithic SDXL or SD 1.5 checkpoint (.safetensors)
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

    # LoRA folder handling
    dossier_lora_effectif = lora_dir or DEFAULT_LORA_DIRS[0]
    if os.path.exists(dossier_lora_effectif):
        commande.extend(["--lora-model-dir", dossier_lora_effectif, "--lora-apply-mode", "auto"])

    if seed >= 0:
        commande.extend(["-s", str(seed)])
    else:
        commande.extend(["-s", "-1"])

    if init_img and os.path.exists(init_img):
        commande.extend(["-i", init_img, "--strength", str(strength)])

    if control_image and control_net:
        commande.extend([
            "--control-image", control_image,
            "--control-net", control_net,
            "--control-strength", str(control_strength)
        ])

    if ip_adapter and ip_adapter_image and clip_vision:
        commande.extend([
            "--ip-adapter", ip_adapter,
            "--ip-adapter-image", ip_adapter_image,
            "--ip-adapter-strength", str(ip_adapter_strength),
            "--clip_vision", clip_vision
        ])

    if circular:
        commande.append("--circular")

    if hires:
        commande.extend([
            "--hires",
            "--hires-scale", str(hires_scale),
            "--hires-denoising-strength", str(hires_strength)
        ])

    try:
        run_engine(commande, timeout=1800, capture=False, check=True, etiquette=f"sd-cli {moteur_nom}")
        if not os.path.exists(output_path):
            raise FileNotFoundError(f"The output file {output_path} was not produced.")
        # .copy() loads the pixels into memory before the temporary file is removed.
        return Image.open(output_path).copy()
    except Exception as e:
        print(f"❌ Error during the render ({moteur_nom}) via sd-cli: {e}")
        raise
    finally:
        if chemin_temporaire and os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass


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
    Generates a video sequence (.webm or image sequence) via stable-diffusion.cpp
    leveraging Vulkan hardware acceleration (Wan 2.1/2.2, LTX-2.3/2.5, MiniMax-H3).
    Supports Text-to-Video (T2V), Image-to-Video (I2V), First & Last Frame (FLF2V), and Video-to-Video (V2V).
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

    print(f"[Vulkan Video - {mode_str}] Generating ({width}x{height}, {video_frames} frames @ {fps} fps, steps={steps})...")

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

    # VRAM optimization: the 1.3B models fit 100% in VRAM (16 GB).
    # --offload-to-cpu is only enabled for heavy models (14B) or when explicitly required.
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
        run_engine(commande, timeout=7200, capture=False, check=True, etiquette="sd-cli video")
        if not os.path.exists(output_path):
            raise FileNotFoundError(f"The output video {output_path} was not produced.")
        print(f"✅ Video generated successfully: {output_path}")
        return output_path
    except Exception as e:
        print(f"❌ Error during video generation via sd-cli: {e}")
        raise


def arrondir_grille_h3(video_frames: int) -> int:
    """Rounds a frame count to the MiniMax-H3 "5 + 17k" grid (minimum 5).

    H3 only accepts frame counts 5, 22, 39, 56…; sd-cli rounds up by itself,
    we do it here so logs and outputs are exact.
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
    lora: Optional[str] = None,
    lora_dir: Optional[str] = None,
    backend: str = "diffusion=vulkan0,te=cpu,vae=cpu",
    threads: int = DEFAULT_THREADS,
    output_path: str = "output/h3_ref2va.webm",
    dry_run: bool = False,
    log_fn=print
) -> str:
    """
    Generates a video WITH audio via MiniMax-H3 Ref2VA: a reference video
    (folder of frames at 24 fps) + its paired WAV condition the DiT (tags
    <Video 1> / <Audio 1> in the prompt). Recipe validated on 2026-09-09
    (RX 6950 XT 16 GB / 31.8 GB RAM) — see MEMORY_BANK §1.16:
      • mandatory memory placement: DiT on GPU with a cap (--max-vram, else
        device lost), Qwen3-VL 32B and video VAE on CPU (else VRAM OOM);
      • frame grid "5 + 17k" (22/39/56…), 24 fps imposed by the model;
      • Ref2VA incompatible with --init-img/--end-img (the reference carries
        the continuity); flow-shift handled internally by H3 (do not impose it).
      • `lora` = LoRA to load as at_runtime (format "name[:weight]", resolved in
        lora_dir or DEFAULT_LORA_DIRS) — e.g. the validated 8-step distilled turbo
        (sampling −64%, total −46%, quality/match ≥ baseline, §1.16).
    """
    modele = model_path or DEFAULT_H3_REF2VA_MODEL
    vae = vae_path or DEFAULT_H3_VIDEO_VAE
    audio_vae = audio_vae_path or DEFAULT_H3_AUDIO_VAE
    llm = llm_path or DEFAULT_H3_LLM

    manquants = [p for p in (modele, vae, audio_vae, llm) if not os.path.exists(p)]
    if manquants:
        raise FileNotFoundError(
            "Missing MiniMax-H3 Ref2VA models: " + "; ".join(manquants)
            + " — download: HF repo leejet/MiniMax-H3-GGUF (ref2va DiT) and Comfy-Org/MiniMax-H3 (VAEs)"
        )
    if not ref_video_dir or not os.path.isdir(ref_video_dir):
        raise ValueError(f"Invalid reference frame folder: {ref_video_dir}")
    if ref_audio_path and not os.path.exists(ref_audio_path):
        raise FileNotFoundError(f"Reference WAV not found: {ref_audio_path}")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # 5+17k grid and 32 px-aligned canvas (otherwise H3 rounds up)
    frames_grille = arrondir_grille_h3(video_frames)
    w_aligne = max(32, (width + 31) // 32 * 32)
    h_aligne = max(32, (height + 31) // 32 * 32)

    n_ref = len([f for f in os.listdir(ref_video_dir) if f.lower().endswith((".png", ".jpg", ".jpeg"))])
    log_fn(
        f"[H3 Ref2VA] {w_aligne}x{h_aligne}, {frames_grille} frames @ 24 fps, "
        f"steps={steps}, cfg={cfg_scale}, seed={seed}, ref={n_ref} frames"
        + (f" + audio {os.path.basename(ref_audio_path)}" if ref_audio_path else "")
        + (f" + LoRA {lora}" if lora else "")
    )

    prompt_final = formater_prompt_avec_loras(prompt, [lora]) if lora else prompt

    commande = [
        sd_cli,
        "-M", "vid_gen",
        "--diffusion-model", modele,
        "--vae", vae,
        "--audio-vae", audio_vae,
        "--llm", llm,
        "-p", prompt_final,
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

    if lora:
        dossier_lora_effectif = lora_dir or DEFAULT_LORA_DIRS[0]
        if not os.path.isdir(dossier_lora_effectif):
            raise FileNotFoundError(f"LoRA folder not found: {dossier_lora_effectif}")
        commande.extend(["--lora-model-dir", dossier_lora_effectif, "--lora-apply-mode", "auto"])

    if dry_run:
        log_fn(f"[H3 Ref2VA] DRY-RUN — command built ({len(commande)} args), not executed:")
        log_fn("  " + " ".join(f'"{c}"' if " " in c else c for c in commande))
        return output_path

    try:
        run_engine(commande, timeout=7200, capture=False, check=True, etiquette="sd-cli H3 Ref2VA")
        if not os.path.exists(output_path):
            raise FileNotFoundError(f"The output video {output_path} was not produced.")
        log_fn(f"✅ H3 Ref2VA video generated: {output_path}")
        return output_path
    except Exception as e:
        log_fn(f"❌ Error during H3 Ref2VA generation via sd-cli: {e}")
        raise

