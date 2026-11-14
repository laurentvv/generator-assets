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
    DEFAULT_H3_FL2VA_MODEL,
    DEFAULT_H3_LLM,
    DEFAULT_H3_REF2VA_MODEL,
    DEFAULT_H3_VIDEO_VAE,
    DEFAULT_LORA_DIRS,
    DEFAULT_MOSS_IMAGE_LLM,
    DEFAULT_MOSS_IMAGE_MODEL,
    DEFAULT_MOSS_IMAGE_TOKENIZER,
    DEFAULT_MOSS_IMAGE_VAE,
    DEFAULT_QWEN_IMAGE21_LLM,
    DEFAULT_QWEN_IMAGE21_LLM_VISION,
    DEFAULT_QWEN_IMAGE21_MODEL,
    DEFAULT_QWEN_IMAGE21_VAE,
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
    control_type: Optional[str] = None,
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
        if control_type:
            commande.extend(["--control-type", control_type])

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


def generer_image_qwen21(
    prompt: str,
    negative_prompt: Optional[str] = None,
    sd_cli: str = DEFAULT_SD_CLI,
    model: str = DEFAULT_QWEN_IMAGE21_MODEL,
    llm: str = DEFAULT_QWEN_IMAGE21_LLM,
    vae: str = DEFAULT_QWEN_IMAGE21_VAE,
    width: int = 1152,
    height: int = 640,
    steps: int = 40,
    cfg_scale: float = 6.0,
    seed: int = -1,
    output_path: Optional[str] = None,
    init_image: Optional[str] = None,
    strength: float = 0.65,
    loras: Optional[List[Union[str, Tuple[str, float]]]] = None,
    lora_dir: Optional[str] = None,
    sigmas: Optional[str] = None,
    ref_images: Optional[List[str]] = None,
    llm_vision: Optional[str] = None,
) -> Image.Image:
    """
    Renders an image with Qwen-Image-2.1 (7B DiT GGUF, Vulkan).

    Recipe user-VALIDATED 2026-10-04 on the RX 6950 XT (MEMORY_BANK §1.39):
    Q8_0 diffusion + Qwen3-VL-8B Q4_K_M text encoder (offloaded to CPU, encoded
    once per prompt) + dedicated VAE. Dimensions MUST be multiples of 32
    (sd-cli requirement for this architecture). Measured ~23.6 s/step at
    1152x640 (40 steps ≈ 16 min/image) — Text encoder/VAE run from RAM,
    diffusion from VRAM.

    Compositing / Multi-Reference modes:
    - ``init_image`` (-i + --strength): pixel-blend img2img compositing (user-VALIDATED
      2026-10-05 with RunningHubAI LoRA).
    - ``ref_images`` (-r + ``--llm_vision``): multimodal reference conditioning via
      ``mmproj-Qwen3VL-8B-Instruct-F16.gguf`` (user-VALIDATED 2026-11-14 with
      ``qwen21_multiple_angles_v2`` LoRA and ``<mva>`` trigger).
    ⚠️ Model under Qwen RESEARCH license: personal / non-commercial use ONLY.
    """
    if width % 32 != 0 or height % 32 != 0:
        raise ValueError(
            f"Qwen-Image-2.1 requires dimensions divisible by 32 (got {width}x{height})."
        )
    if init_image and not os.path.exists(init_image):
        raise FileNotFoundError(f"Init image not found: {init_image}")
    refs = list(ref_images or [])
    for ref in refs:
        if not os.path.exists(ref):
            raise FileNotFoundError(f"Reference image not found: {ref}")
    vision_path: Optional[str] = None
    if refs:
        vision_path = llm_vision or DEFAULT_QWEN_IMAGE21_LLM_VISION
        if not os.path.exists(vision_path):
            raise FileNotFoundError(
                f"Qwen3-VL vision projector (--llm_vision) not found: {vision_path}"
            )

    prompt_final = formater_prompt_avec_loras(prompt, loras)

    chemin_temporaire = output_path is None
    if chemin_temporaire:
        descripteur, output_path = tempfile.mkstemp(suffix=".png", prefix="ga_rendu_qwen21_")
        os.close(descripteur)
        os.remove(output_path)

    mode_str = "ref" if refs else ("img2img" if init_image else "t2i")
    if loras:
        mode_str += f" + {len(loras)} LoRA(s)"
    print(f"[Qwen-Image-2.1 - {mode_str}] Launching sd-cli ({width}x{height}, steps={steps}, cfg={cfg_scale})...")
    sd_cli = sd_cli or DEFAULT_SD_CLI
    commande = [
        sd_cli,
        "--diffusion-model", model,
        "--vae", vae,
        "--llm", llm,
        "-p", prompt_final,
        "--cfg-scale", str(cfg_scale),
        "--sampling-method", "euler",
        "--steps", str(steps),
        "-W", str(width),
        "-H", str(height),
        "-s", str(seed),
        "--flash-attn", "on",
        "--offload-to-cpu",
        "-o", output_path,
    ]
    if sigmas:
        commande.extend(["--sigmas", sigmas])
    if negative_prompt:
        commande.extend(["-n", negative_prompt])
    if vision_path:
        commande.extend(["--llm_vision", vision_path])
    for ref in refs:
        commande.extend(["-r", ref])
    if init_image:
        commande.extend(["-i", init_image, "--strength", str(strength)])
    dossier_lora_effectif = lora_dir or DEFAULT_LORA_DIRS[0]
    if loras and os.path.exists(dossier_lora_effectif):
        commande.extend(["--lora-model-dir", dossier_lora_effectif, "--lora-apply-mode", "auto"])

    try:
        run_engine(commande, timeout=7200, capture=False, check=True, etiquette="sd-cli Qwen-Image-2.1")
        if not os.path.exists(output_path):
            raise FileNotFoundError(f"The output file {output_path} was not produced.")
        return Image.open(output_path).copy()
    except Exception as e:
        print(f"❌ Error during the render (Qwen-Image-2.1) via sd-cli: {e}")
        raise
    finally:
        if chemin_temporaire and os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass


def generer_image_moss(
    prompt: str,
    sd_cli: str = DEFAULT_SD_CLI,
    model: str = DEFAULT_MOSS_IMAGE_MODEL,
    llm: str = DEFAULT_MOSS_IMAGE_LLM,
    vae: str = DEFAULT_MOSS_IMAGE_VAE,
    tokenizer: str = DEFAULT_MOSS_IMAGE_TOKENIZER,
    width: int = 1024,
    height: int = 1024,
    steps: int = 50,
    cfg_scale: float = 3.0,
    sampling_method: str = "euler",
    seed: int = -1,
    output_path: Optional[str] = None,
) -> Image.Image:
    """
    Renders an image with MOSS-Image-SFT (OpenMOSS 5.1B DiT flow-matching, GGUF).

    Pipeline user-VALIDATED 2026-10-24 on the RX 6950 XT (MEMORY_BANK §1.45,
    "Moss parfait oui"): moss_image arch (sd-cli since master-973) + Qwen3.5-9B
    Q8_0 text encoder + external tokenizer.json + flux2 VAE. Validated recipe:
    euler, 50 steps, CFG 3.0, --fa, everything resident in VRAM (11.4 GB on the
    16 GB card — do NOT pass --offload-to-cpu: it forces the graph through the
    pinned-pool streaming path, which cannot allocate once the weights fill the
    card). In-image text rendering is the model's strength; small secondary
    text is garbled (documented base weakness). Apache-2.0: commercial use OK.

    Dimensions must be multiples of 32 (same grid requirement as the other
    flow-matching architectures). Measured 42.5-43.0 s/step at 1024x1024 on
    RDNA2 (50 steps ≈ 36 min) — the arch is new on Vulkan, kernels still young.
    Without output_path, goes through a unique temporary file like
    generer_image_qwen21.
    """
    if width % 32 != 0 or height % 32 != 0:
        raise ValueError(
            f"MOSS-Image requires dimensions divisible by 32 (got {width}x{height})."
        )

    chemin_temporaire = output_path is None
    if chemin_temporaire:
        descripteur, output_path = tempfile.mkstemp(suffix=".png", prefix="ga_rendu_moss_")
        os.close(descripteur)
        os.remove(output_path)

    print(f"[MOSS-Image-SFT - t2i] Launching sd-cli ({width}x{height}, steps={steps}, cfg={cfg_scale})...")
    sd_cli = sd_cli or DEFAULT_SD_CLI
    commande = [
        sd_cli,
        "--diffusion-model", model,
        "--llm", llm,
        "--vae", vae,
        "--tokenizer", tokenizer,
        "-p", prompt,
        "--cfg-scale", str(cfg_scale),
        "--sampling-method", sampling_method,
        "--steps", str(steps),
        "-W", str(width),
        "-H", str(height),
        "-s", str(seed),
        "--fa",
        "-o", output_path,
    ]

    try:
        run_engine(commande, timeout=7200, capture=False, check=True, etiquette="sd-cli MOSS-Image")
        if not os.path.exists(output_path):
            raise FileNotFoundError(f"The output file {output_path} was not produced.")
        return Image.open(output_path).copy()
    except Exception as e:
        print(f"❌ Error during the render (MOSS-Image-SFT) via sd-cli: {e}")
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
    flow_shift: Optional[float] = 3.0,
    sampling_method: str = "euler",
    seed: int = -1,
    negative_prompt: Optional[str] = None,
    init_img: Optional[str] = None,
    end_img: Optional[str] = None,
    control_video_dir: Optional[str] = None,
    offload_to_cpu: bool = True,
    diffusion_fa: bool = True,
    temporal_tiling: bool = True,
    vae_on_cpu: bool = False,
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

    sd_cli = sd_cli or DEFAULT_SD_CLI
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
    if flow_shift is not None:
        commande.extend(["--flow-shift", str(flow_shift)])

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
    if vae_on_cpu:
        # Mandatory for the 14B video models on 16 GB: the GPU VAE decode alone
        # requests ~19.4 GB (MEMORY_BANK §1.16) — the decode runs on CPU instead.
        commande.append("--vae-on-cpu")

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


def _executer_vid_gen_h3(
    *,
    tag: str,
    prompt: str,
    sd_cli: str,
    modele: str,
    vae: str,
    audio_vae: str,
    llm: str,
    extra_args: List[str],
    video_frames: int,
    fps: int,
    width: int,
    height: int,
    steps: int,
    cfg_scale: float,
    seed: int,
    max_vram: int,
    lora: Optional[str],
    lora_dir: Optional[str],
    backend: str,
    threads: int,
    output_path: str,
    dry_run: bool,
    log_fn,
) -> str:
    """Shared MiniMax-H3 vid_gen execution helper for Ref2VA and FL2VA routes."""
    manquants = [p for p in (modele, vae, audio_vae, llm) if not os.path.exists(p)]
    if manquants:
        raise FileNotFoundError(
            f"Missing MiniMax-H3 ({tag}) models: " + "; ".join(manquants)
            + " — check C:\\Modeles_LLM / D:\\Modeles_LLM (HF leejet/MiniMax-H3-GGUF and Comfy-Org/MiniMax-H3)."
        )

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    frames_grille = arrondir_grille_h3(video_frames)
    w_aligne = max(32, (width + 31) // 32 * 32)
    h_aligne = max(32, (height + 31) // 32 * 32)
    prompt_final = formater_prompt_avec_loras(prompt, [lora]) if lora else prompt

    sd_cli = sd_cli or DEFAULT_SD_CLI
    commande = [
        sd_cli,
        "-M", "vid_gen",
        "--diffusion-model", modele,
        "--vae", vae,
        "--audio-vae", audio_vae,
        "--llm", llm,
        "-p", prompt_final,
        *extra_args,
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
        "-v",
    ]
    if lora:
        dossier_lora_effectif = lora_dir or DEFAULT_LORA_DIRS[0]
        if not os.path.isdir(dossier_lora_effectif):
            raise FileNotFoundError(f"LoRA folder not found: {dossier_lora_effectif}")
        commande.extend(["--lora-model-dir", dossier_lora_effectif, "--lora-apply-mode", "auto"])

    if dry_run:
        log_fn(f"[{tag}] DRY-RUN — command built ({len(commande)} args), not executed:")
        log_fn("  " + " ".join(f'"{c}"' if " " in c else c for c in commande))
        return output_path

    try:
        run_engine(commande, timeout=7200, capture=False, check=True, etiquette=f"sd-cli {tag}")
        if not os.path.exists(output_path):
            raise FileNotFoundError(f"The output video {output_path} was not produced.")
        log_fn(f"✅ {tag} video generated: {output_path}")
        return output_path
    except Exception as e:
        log_fn(f"❌ Error during {tag} generation via sd-cli: {e}")
        raise


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
    (RX 6950 XT 16 GB / 31.8 GB RAM) — see MEMORY_BANK §1.16.
    """
    if not ref_video_dir or not os.path.isdir(ref_video_dir):
        raise ValueError(f"Invalid reference frame folder: {ref_video_dir}")
    if ref_audio_path and not os.path.exists(ref_audio_path):
        raise FileNotFoundError(f"Reference WAV not found: {ref_audio_path}")

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
    extra_args = ["--ref-video", ref_video_dir]
    if ref_audio_path:
        extra_args.extend(["--ref-video-audio", ref_audio_path])

    return _executer_vid_gen_h3(
        tag="H3 Ref2VA",
        prompt=prompt,
        sd_cli=sd_cli,
        modele=model_path or DEFAULT_H3_REF2VA_MODEL,
        vae=vae_path or DEFAULT_H3_VIDEO_VAE,
        audio_vae=audio_vae_path or DEFAULT_H3_AUDIO_VAE,
        llm=llm_path or DEFAULT_H3_LLM,
        extra_args=extra_args,
        video_frames=video_frames,
        fps=fps,
        width=width,
        height=height,
        steps=steps,
        cfg_scale=cfg_scale,
        seed=seed,
        max_vram=max_vram,
        lora=lora,
        lora_dir=lora_dir,
        backend=backend,
        threads=threads,
        output_path=output_path,
        dry_run=dry_run,
        log_fn=log_fn,
    )


def generer_video_fl2va_h3(
    prompt: str,
    init_image: str,
    end_image: Optional[str] = None,
    sd_cli: str = DEFAULT_SD_CLI,
    model_path: Optional[str] = None,
    vae_path: Optional[str] = None,
    audio_vae_path: Optional[str] = None,
    llm_path: Optional[str] = None,
    video_frames: int = 22,
    fps: int = 24,
    width: int = 864,
    height: int = 480,
    steps: int = 8,
    cfg_scale: float = 1.0,
    seed: int = 42,
    max_vram: int = 10,
    lora: Optional[str] = None,
    lora_dir: Optional[str] = None,
    backend: str = "diffusion=vulkan0,te=cpu,vae=cpu",
    threads: int = DEFAULT_THREADS,
    output_path: str = "output/h3_fl2va.webm",
    dry_run: bool = False,
    log_fn=print,
) -> str:
    """First/Last-Frame-to-Video+Audio generation via MiniMax-H3 FL2VA.

    Wave 1 chain verified (2026-11-14): accepts ``--init-img`` and optional
    ``--end-img`` with ``minimax_h3_fl2va_pruned-Q4_K_M.gguf`` + optional
    8-step turbo LoRA (624/624 tensors). Mutually exclusive with ``--ref-video``.
    """
    if not init_image or not os.path.exists(init_image):
        raise FileNotFoundError(f"Start keyframe (--init-img) not found: {init_image}")
    if end_image and not os.path.exists(end_image):
        raise FileNotFoundError(f"End keyframe (--end-img) not found: {end_image}")

    frames_grille = arrondir_grille_h3(video_frames)
    w_aligne = max(32, (width + 31) // 32 * 32)
    h_aligne = max(32, (height + 31) // 32 * 32)
    if frames_grille < 22:
        log_fn(
            f"⚠️ H3 FL2VA with {frames_grille} frames (0.17 s) is too short for full "
            "transitions; use --frames >= 22 (17k+5 grid).",
        )
    log_fn(
        f"[H3 FL2VA] {w_aligne}x{h_aligne}, {frames_grille} frames @ 24 fps, "
        f"steps={steps}, cfg={cfg_scale}, seed={seed}, init={os.path.basename(init_image)}"
        + (f" -> end={os.path.basename(end_image)}" if end_image else "")
        + (f" + LoRA {lora}" if lora else "")
    )
    extra_args = ["--init-img", init_image]
    if end_image:
        extra_args.extend(["--end-img", end_image])

    return _executer_vid_gen_h3(
        tag="H3 FL2VA",
        prompt=prompt,
        sd_cli=sd_cli,
        modele=model_path or DEFAULT_H3_FL2VA_MODEL,
        vae=vae_path or DEFAULT_H3_VIDEO_VAE,
        audio_vae=audio_vae_path or DEFAULT_H3_AUDIO_VAE,
        llm=llm_path or DEFAULT_H3_LLM,
        extra_args=extra_args,
        video_frames=video_frames,
        fps=fps,
        width=width,
        height=height,
        steps=steps,
        cfg_scale=cfg_scale,
        seed=seed,
        max_vram=max_vram,
        lora=lora,
        lora_dir=lora_dir,
        backend=backend,
        threads=threads,
        output_path=output_path,
        dry_run=dry_run,
        log_fn=log_fn,
    )

