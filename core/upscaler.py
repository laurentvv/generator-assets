#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Upscaling and Super-Resolution module for 2D Assets.
Supports:
1. ESRGAN / Real-ESRGAN on Vulkan GPU (sd-cli -M upscale) with perfect RGBA Alpha channel preservation
2. Smart Lanczos software super-resolution with Unsharp Mask and edge preservation
"""

import os
import tempfile
from pathlib import Path
from typing import Optional
from PIL import Image, ImageFilter
from core.config import (
    DEFAULT_BACKEND,
    DEFAULT_ESRGAN_MODEL,
    DEFAULT_FFMPEG,
    DEFAULT_SD_CLI,
    DEFAULT_SEEDVR2_MODEL,
    DEFAULT_SEEDVR2_VAE,
    resoudre_upscaler,
)
from core.process import run_engine


_VALID_UPSCALE_MODES = ("auto", "esrgan", "seedvr2", "lanczos")


def resoudre_options_upscale(params: dict) -> tuple[str, int, int]:
    """Resolves upscale mode, SeedVR2 temporal chunk size, and seed from CLI/UI params."""
    # Upscale owns its own mode key: global --mode belongs to asset_blendkit ("prop"/"plate").
    mode = (
        params.get("upscale_mode")
        or (params.get("mode") if params.get("mode") in _VALID_UPSCALE_MODES else None)
        or "auto"
    )
    raw_chunk = params.get("vsr_temporal_chunk_size")
    temporal_chunk = 1 if raw_chunk is None else int(raw_chunk)
    seed = int(params.get("seed", 42))
    return mode, temporal_chunk, seed


def _reinjecter_alpha(image_source: Image.Image, img_upscaled_rgb: Image.Image) -> Image.Image:
    """Restores the source alpha channel resized cleanly onto an upscaled RGB image."""
    if image_source.mode != "RGBA":
        return img_upscaled_rgb
    alpha_orig = image_source.split()[-1]
    alpha_upscaled = alpha_orig.resize(img_upscaled_rgb.size, Image.Resampling.LANCZOS)
    r, g, b = img_upscaled_rgb.split()
    return Image.merge("RGBA", (r, g, b, alpha_upscaled))


def upscale_esrgan(
    image_entree: Image.Image,
    esrgan_model_path: str = DEFAULT_ESRGAN_MODEL,
    repeats: int = 1,
    sd_cli: str = DEFAULT_SD_CLI,
    backend: str = DEFAULT_BACKEND
) -> Image.Image:
    """
    Runs the ESRGAN model via sd-cli on Vulkan while preserving RGBA transparency.
    """
    if not os.path.exists(esrgan_model_path):
        raise FileNotFoundError(f"ESRGAN model not found: {esrgan_model_path}")

    # Unique temp files (tempfile): compatible with parallel runs,
    # and no leftover from a previous call can be read back.
    with tempfile.TemporaryDirectory(prefix="ga_esrgan_") as dossier_temp:
        temp_in = os.path.join(dossier_temp, "entree.png")
        temp_out = os.path.join(dossier_temp, "sortie.png")

        rgb_in = image_entree.convert("RGB")
        rgb_in.save(temp_in, "PNG")

        nom_modele = Path(esrgan_model_path).name
        print(f"[ESRGAN Vulkan] AI upscaling with '{nom_modele}'...")

        commande = [
            sd_cli,
            "-M", "upscale",
            "--upscale-model", esrgan_model_path,
            "-i", temp_in,
            "-o", temp_out,
            "--upscale-repeats", str(repeats),
            "--backend", backend,
            "-v"
        ]

        run_engine(commande, timeout=600, capture=False, check=True, etiquette="sd-cli ESRGAN")
        img_upscaled_rgb = Image.open(temp_out).convert("RGB")

    return _reinjecter_alpha(image_entree, img_upscaled_rgb)


def upscale_seedvr2(
    image_entree: Image.Image,
    facteur: int = 2,
    seedvr2_model_path: str = DEFAULT_SEEDVR2_MODEL,
    seedvr2_vae_path: str = DEFAULT_SEEDVR2_VAE,
    sd_cli: str = DEFAULT_SD_CLI,
    backend: Optional[str] = None,
    seed: int = 42,
) -> Image.Image:
    """Single-image AI super-resolution via SeedVR2 3B int8_convrot (sd-cli -M vid_upscale).

    Wave 1 user-validated (2026-11-14) on RX 6950 XT Vulkan0 (``int dot: 1``,
    sd-cli ``master-1092``+): preserves RGBA transparency and requires the official
    Comfy-Org ``seedvr2_3b_int8_convrot.safetensors`` + ``seedvr2_ema_vae_fp16.safetensors``.
    """
    if not os.path.exists(seedvr2_model_path):
        raise FileNotFoundError(f"SeedVR2 model not found: {seedvr2_model_path}")
    if not os.path.exists(seedvr2_vae_path):
        raise FileNotFoundError(f"SeedVR2 VAE not found: {seedvr2_vae_path}")
    sd_cli = sd_cli or DEFAULT_SD_CLI
    factor_int = max(1, int(facteur))

    with tempfile.TemporaryDirectory(prefix="ga_seedvr2_") as dossier_temp:
        temp_in = os.path.join(dossier_temp, "entree.png")
        temp_out = os.path.join(dossier_temp, "sortie.png")
        image_entree.convert("RGB").save(temp_in, "PNG")

        print(f"[SeedVR2 Vulkan] Diffusion upscaling {factor_int}x ({Path(seedvr2_model_path).name})...")
        commande = [
            sd_cli,
            "-M", "vid_upscale",
            "--diffusion-model", seedvr2_model_path,
            "--vae", seedvr2_vae_path,
            "-i", temp_in,
            "-o", temp_out,
            "--upscale-factor", str(factor_int),
            "-s", str(int(seed)),
            "-v",
        ]
        if backend:
            commande.extend(["--backend", backend])

        run_engine(commande, timeout=1800, capture=False, check=True, etiquette="sd-cli SeedVR2 image")
        if not os.path.exists(temp_out):
            raise FileNotFoundError(f"SeedVR2 did not produce output image: {temp_out}")
        img_upscaled_rgb = Image.open(temp_out).convert("RGB")

    return _reinjecter_alpha(image_entree, img_upscaled_rgb)


def upscale_smart_lanczos(
    image: Image.Image,
    target_width: int,
    target_height: int,
    unsharp_radius: float = 1.2,
    unsharp_percent: int = 130,
    unsharp_threshold: int = 3
) -> Image.Image:
    """
    Multi-pass software super-resolution with the Lanczos filter,
    Unsharp Mask sharpening and clean Alpha channel handling.
    """
    has_alpha = image.mode == "RGBA"

    if has_alpha:
        r, g, b, a = image.split()
        rgb = Image.merge("RGB", (r, g, b))

        rgb_upscaled = rgb.resize((target_width, target_height), Image.Resampling.LANCZOS)
        a_upscaled = a.resize((target_width, target_height), Image.Resampling.LANCZOS)

        sharp_rgb = rgb_upscaled.filter(
            ImageFilter.UnsharpMask(radius=unsharp_radius, percent=unsharp_percent, threshold=unsharp_threshold)
        )

        r_u, g_u, b_u = sharp_rgb.split()
        return Image.merge("RGBA", (r_u, g_u, b_u, a_upscaled))
    else:
        upscaled = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        return upscaled.filter(
            ImageFilter.UnsharpMask(radius=unsharp_radius, percent=unsharp_percent, threshold=unsharp_threshold)
        )


def upscaler_asset(
    image_entree: Image.Image,
    facteur: float = 2.0,
    taille_cible: Optional[int] = None,
    mode: str = "auto",
    upscale_model: Optional[str] = None,
    sd_cli: str = DEFAULT_SD_CLI,
    backend: str = DEFAULT_BACKEND,
    seed: int = 42,
) -> Image.Image:
    """
    Unified entry point for 2D asset upscaling.
    Supports ``auto``/``esrgan`` (RealESRGAN/UltraSharp), ``seedvr2``
    (SeedVR2 3B int8_convrot via ``-M vid_upscale``), and ``lanczos``.
    """
    largeur_init, hauteur_init = image_entree.size

    if taille_cible and taille_cible > 0:
        largeur_cible = taille_cible
        hauteur_cible = int(hauteur_init * (taille_cible / largeur_init))
    else:
        largeur_cible = int(largeur_init * facteur)
        hauteur_cible = int(hauteur_init * facteur)

    if mode == "seedvr2":
        import math
        seedvr_factor = max(2, math.ceil(largeur_cible / max(1, largeur_init)))
        img_ia = upscale_seedvr2(
            image_entree=image_entree,
            facteur=seedvr_factor,
            sd_cli=sd_cli,
            seed=seed,
        )
        if img_ia.size != (largeur_cible, hauteur_cible):
            img_ia = img_ia.resize((largeur_cible, hauteur_cible), Image.Resampling.LANCZOS)
        return img_ia

    modele_resolu = resoudre_upscaler(upscale_model)

    # 1. Use the ESRGAN AI model if available
    if mode in ["esrgan", "auto"] and modele_resolu and os.path.exists(modele_resolu) and os.path.exists(sd_cli):
        try:
            img_ia = upscale_esrgan(
                image_entree=image_entree,
                esrgan_model_path=modele_resolu,
                sd_cli=sd_cli,
                backend=backend
            )
            # Adjust to the exact requested dimension if needed
            if img_ia.size != (largeur_cible, hauteur_cible):
                img_ia = img_ia.resize((largeur_cible, hauteur_cible), Image.Resampling.LANCZOS)
            return img_ia
        except Exception as e:
            print(f"⚠️  ESRGAN failure ({e}), switching to Smart Lanczos...")

    # 2. Fallback to Smart Lanczos
    print(f"🔍 [Smart Lanczos] Software upscaling to {largeur_cible}x{hauteur_cible}...")
    return upscale_smart_lanczos(image_entree, largeur_cible, hauteur_cible)


def _video_possede_audio(ffmpeg: str, video_path: str) -> bool:
    """Returns True if the video container exposes an audio stream via ffprobe."""
    ffprobe = os.path.join(os.path.dirname(ffmpeg), "ffprobe.exe") if os.name == "nt" else os.path.join(os.path.dirname(ffmpeg), "ffprobe")
    if not os.path.exists(ffprobe):
        ffprobe = "ffprobe"
    try:
        res = run_engine(
            [ffprobe, "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=codec_type", "-of", "csv=p=0", video_path],
            capture=True, check=False, timeout=60, etiquette="ffprobe audio check",
        )
        return bool((res.stdout or "").strip())
    except Exception:
        return False


def upscale_video_seedvr2(
    video_input_path: str,
    output_path: str,
    *,
    facteur: float = 2.0,
    taille_cible: Optional[int] = None,
    temporal_chunk_size: int = 1,
    seedvr2_model_path: str = DEFAULT_SEEDVR2_MODEL,
    seedvr2_vae_path: str = DEFAULT_SEEDVR2_VAE,
    sd_cli: str = DEFAULT_SD_CLI,
    ffmpeg: str = DEFAULT_FFMPEG,
    seed: int = 42,
    log_fn=print,
) -> str:
    """Temporally coherent video upscaling via SeedVR2 ``-M vid_upscale --input-frames``.

    Extracts PNG frames, runs SeedVR2 in Vulkan0, and remuxes with the source
    audio stream (``-M vid_upscale`` drops audio) into ``output_path``.
    """
    import math
    import cv2

    if not os.path.exists(video_input_path):
        raise FileNotFoundError(f"Source video not found: {video_input_path}")
    if not os.path.exists(seedvr2_model_path):
        raise FileNotFoundError(f"SeedVR2 model not found: {seedvr2_model_path}")
    if not os.path.exists(seedvr2_vae_path):
        raise FileNotFoundError(f"SeedVR2 VAE not found: {seedvr2_vae_path}")
    if temporal_chunk_size < 1 or (temporal_chunk_size > 1 and (temporal_chunk_size - 1) % 4 != 0):
        raise ValueError(
            f"--vsr-temporal-chunk-size must be 1 or 4n+1 (got {temporal_chunk_size})."
        )
    sd_cli = sd_cli or DEFAULT_SD_CLI
    ffmpeg = ffmpeg or DEFAULT_FFMPEG

    cap = cv2.VideoCapture(video_input_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open the source video: {video_input_path}")
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        largeur_init = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        hauteur_init = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        cap.release()

    if taille_cible and taille_cible > 0:
        largeur_cible = int(taille_cible)
        hauteur_cible = int(hauteur_init * (taille_cible / max(1, largeur_init)))
    else:
        largeur_cible = int(largeur_init * facteur)
        hauteur_cible = int(hauteur_init * facteur)
    largeur_cible = (largeur_cible // 2) * 2
    hauteur_cible = (hauteur_cible // 2) * 2

    seedvr_factor = max(2, math.ceil(largeur_cible / max(1, largeur_init)))
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    ext = os.path.splitext(output_path)[1].lower()
    if ext not in (".webm", ".mp4"):
        output_path = os.path.splitext(output_path)[0] + ".mp4"
        ext = ".mp4"

    has_audio = _video_possede_audio(ffmpeg, video_input_path)
    log_fn(
        f"[SeedVR2 Video] {largeur_init}x{hauteur_init} -> {largeur_cible}x{hauteur_cible} "
        f"(factor={seedvr_factor}x, chunk={temporal_chunk_size}, audio={'yes' if has_audio else 'no'})..."
    )

    with tempfile.TemporaryDirectory(prefix="ga_seedvr2_vid_") as dossier_temp:
        frames_dir = os.path.join(dossier_temp, "frames_in")
        os.makedirs(frames_dir, exist_ok=True)
        run_engine(
            [ffmpeg, "-y", "-v", "error", "-i", video_input_path,
             os.path.join(frames_dir, "%06d.png")],
            check=True, timeout=600, etiquette="ffmpeg extract seedvr2 frames",
        )
        raw_video = os.path.join(dossier_temp, "seedvr2_raw.webm")
        run_engine(
            [
                sd_cli,
                "-M", "vid_upscale",
                "--diffusion-model", seedvr2_model_path,
                "--vae", seedvr2_vae_path,
                "--input-frames", frames_dir,
                "-o", raw_video,
                "--upscale-factor", str(seedvr_factor),
                "--vsr-temporal-chunk-size", str(temporal_chunk_size),
                "--fps", str(max(1, int(round(fps)))),
                "-s", str(int(seed)),
                "-v",
            ],
            capture=False, check=True, timeout=7200, etiquette="sd-cli SeedVR2 video",
        )
        if not os.path.exists(raw_video):
            raise FileNotFoundError(f"SeedVR2 video output not produced: {raw_video}")

        # Remux with original audio stream and guarantee exact even target dimensions.
        cmd_remux = [ffmpeg, "-y", "-v", "error", "-i", raw_video]
        if has_audio:
            cmd_remux.extend(["-i", video_input_path, "-map", "0:v:0", "-map", "1:a:0"])
        else:
            cmd_remux.extend(["-map", "0:v:0"])
        cmd_remux.extend(["-vf", f"scale={largeur_cible}:{hauteur_cible}:flags=lanczos"])
        if ext == ".webm":
            cmd_remux.extend(["-c:v", "libvpx-vp9", "-crf", "18", "-b:v", "0"])
            if has_audio:
                cmd_remux.extend(["-c:a", "libopus", "-b:a", "192k"])
        else:
            cmd_remux.extend(["-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p"])
            if has_audio:
                cmd_remux.extend(["-c:a", "aac", "-b:a", "192k"])
        if has_audio:
            cmd_remux.append("-shortest")
        cmd_remux.append(output_path)
        run_engine(cmd_remux, check=True, timeout=1800, etiquette="ffmpeg seedvr2 remux")

    log_fn(f"✅ SeedVR2 video upscaled: {output_path} ({largeur_cible}x{hauteur_cible})")
    return output_path


def upscale_video(
    video_input_path: str,
    output_path: str,
    facteur: float = 2.0,
    taille_cible: Optional[int] = None,
    mode: str = "auto",
    upscale_model: Optional[str] = None,
    sd_cli: str = DEFAULT_SD_CLI,
    backend: str = DEFAULT_BACKEND,
    log_fn=print,
    temporal_chunk_size: int = 1,
    seed: int = 42,
) -> str:
    """
    Upscales a video (.webm, .mp4, .avi) with SeedVR2 (``mode="seedvr2"``),
    ESRGAN Vulkan, or Smart Lanczos.
    """
    if mode == "seedvr2":
        return upscale_video_seedvr2(
            video_input_path=video_input_path,
            output_path=output_path,
            facteur=facteur,
            taille_cible=taille_cible,
            temporal_chunk_size=temporal_chunk_size,
            sd_cli=sd_cli,
            seed=seed,
            log_fn=log_fn,
        )

    import cv2
    import numpy as np

    if not os.path.exists(video_input_path):
        raise FileNotFoundError(f"Source video not found: {video_input_path}")

    cap = cv2.VideoCapture(video_input_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open the source video: {video_input_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    largeur_init = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    hauteur_init = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if taille_cible and taille_cible > 0:
        largeur_cible = taille_cible
        hauteur_cible = int(hauteur_init * (taille_cible / largeur_init))
    else:
        largeur_cible = int(largeur_init * facteur)
        hauteur_cible = int(hauteur_init * facteur)

    # Even dimensions required by the codecs
    largeur_cible = (largeur_cible // 2) * 2
    hauteur_cible = (hauteur_cible // 2) * 2

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    ext = os.path.splitext(output_path)[1].lower()
    if ext not in [".webm", ".mp4"]:
        output_path = os.path.splitext(output_path)[0] + ".mp4"
        ext = ".mp4"

    log_fn(f"[Video Upscale] {largeur_init}x{hauteur_init} ➔ {largeur_cible}x{hauteur_cible} ({total_frames} frames @ {fps:.1f} fps)...")

    writer = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (largeur_cible, hauteur_cible))
    if not writer.isOpened():
        output_path = os.path.splitext(output_path)[0] + ".avi"
        writer = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*'XVID'), fps, (largeur_cible, hauteur_cible))

    frame_idx = 0
    try:
        while True:
            ret, frame_bgr = cap.read()
            if not ret:
                break
            frame_idx += 1
            if frame_idx % 5 == 0 or frame_idx == 1 or frame_idx == total_frames:
                log_fn(f"  Frame {frame_idx}/{total_frames} in progress...")

            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(frame_rgb)

            img_upscaled = upscaler_asset(
                image_entree=img_pil,
                facteur=facteur,
                taille_cible=largeur_cible,
                mode=mode,
                upscale_model=upscale_model,
                sd_cli=sd_cli,
                backend=backend
            )

            arr_upscaled = cv2.cvtColor(np.array(img_upscaled), cv2.COLOR_RGB2BGR)
            if arr_upscaled.shape[1] != largeur_cible or arr_upscaled.shape[0] != hauteur_cible:
                arr_upscaled = cv2.resize(arr_upscaled, (largeur_cible, hauteur_cible), interpolation=cv2.INTER_LANCZOS4)

            writer.write(arr_upscaled)
    finally:
        cap.release()
        writer.release()

    log_fn(f"✅ Video upscaled successfully: {output_path} ({largeur_cible}x{hauteur_cible})")
    return output_path

