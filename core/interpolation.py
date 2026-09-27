#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Frame interpolation module via neural optical flow (RIFE v4 ONNX).
Raises the smoothness of a 2D animation from 4/8 FPS up to 30/60 FPS.
"""

import os
from typing import List, Optional, Tuple
import numpy as np
from PIL import Image

from core.config import DEFAULT_RIFE_MODEL, resoudre_modele_onnx

_SESSION_CACHE = {}


def _get_onnx_session(model_path: str):
    """Retrieves or caches the ONNX RIFE session."""
    global _SESSION_CACHE
    if model_path not in _SESSION_CACHE:
        import onnxruntime as ort
        available = ort.get_available_providers()
        preferred = []
        if "DmlExecutionProvider" in available:
            preferred.append("DmlExecutionProvider")
        if "CPUExecutionProvider" in available:
            preferred.append("CPUExecutionProvider")
        _SESSION_CACHE[model_path] = ort.InferenceSession(model_path, providers=preferred or available)
    return _SESSION_CACHE[model_path]


def _pad_image_tensor(tensor: np.ndarray, multiple: int = 32) -> Tuple[np.ndarray, int, int]:
    """Pads a (1, C, H, W) tensor so that H and W are multiples of 32."""
    _, _, h, w = tensor.shape
    pad_h = (multiple - (h % multiple)) % multiple
    pad_w = (multiple - (w % multiple)) % multiple

    if pad_h == 0 and pad_w == 0:
        return tensor, h, w

    padded = np.pad(tensor, ((0, 0), (0, 0), (0, pad_h), (0, pad_w)), mode="edge")
    return padded, h, w


def interpoler_paire_rife(
    img0: Image.Image,
    img1: Image.Image,
    model_path: Optional[str] = None
) -> Image.Image:
    """
    Generates the intermediate frame (t=0.5) between img0 and img1 via RIFE v4 ONNX.
    """
    chemin = resoudre_modele_onnx(model_path, DEFAULT_RIFE_MODEL)
    if not chemin or not os.path.exists(chemin):
        print(f"⚠️ [RIFE] RIFE model not found ({chemin}). Falling back to linear blend.")
        return Image.blend(img0.convert("RGBA"), img1.convert("RGBA"), 0.5)

    try:
        session = _get_onnx_session(chemin)
        w, h = img0.size

        # Prepare the RGB channels
        rgb0 = np.array(img0.convert("RGB"), dtype=np.float32) / 255.0
        rgb1 = np.array(img1.convert("RGB"), dtype=np.float32) / 255.0

        t0 = np.transpose(rgb0, (2, 0, 1))[np.newaxis, :]
        t1 = np.transpose(rgb1, (2, 0, 1))[np.newaxis, :]

        # Concatenate the 2 frames: shape (1, 6, H, W)
        concat = np.concatenate([t0, t1], axis=1).astype(np.float32)
        padded_tensor, orig_h, orig_w = _pad_image_tensor(concat, 32)

        input_name = session.get_inputs()[0].name
        out = session.run(None, {input_name: padded_tensor})[0][0]

        # Crop the padding
        out_rgb = out[:, :orig_h, :orig_w]
        out_rgb = np.transpose(out_rgb, (1, 2, 0))
        out_rgb = (out_rgb.clip(0.0, 1.0) * 255.0).astype(np.uint8)

        img_interp = Image.fromarray(out_rgb, mode="RGB")

        # Interpolate the Alpha channel if available
        if "A" in img0.getbands() and "A" in img1.getbands():
            a0 = np.array(img0.getchannel("A"), dtype=np.float32)
            a1 = np.array(img1.getchannel("A"), dtype=np.float32)
            alpha_interp = ((a0 + a1) * 0.5).clip(0, 255).astype(np.uint8)
            res = img_interp.convert("RGBA")
            res.putalpha(Image.fromarray(alpha_interp, mode="L"))
            return res

        return img_interp

    except Exception as e:
        print(f"❌ [RIFE] Inference error: {e}")
        return Image.blend(img0.convert("RGBA"), img1.convert("RGBA"), 0.5)


def interpoler_sequence(
    trames: List[Image.Image],
    facteur: int = 2,
    boucler: bool = True,
    model_path: Optional[str] = None
) -> List[Image.Image]:
    """
    Multiplies the frame count of a sequence by a factor (2x or 4x).
    """
    if facteur <= 1 or len(trames) < 2:
        return trames

    sequence_courante = trames
    passes = 1 if facteur == 2 else 2  # 2 passes for 4x

    for p in range(passes):
        nouvelle_sequence = []
        n = len(sequence_courante)

        for i in range(n):
            f0 = sequence_courante[i]
            nouvelle_sequence.append(f0)

            # Next frame
            if i < n - 1:
                f1 = sequence_courante[i + 1]
                f_mid = interpoler_paire_rife(f0, f1, model_path=model_path)
                nouvelle_sequence.append(f_mid)
            elif boucler:
                f1 = sequence_courante[0]
                f_mid = interpoler_paire_rife(f0, f1, model_path=model_path)
                nouvelle_sequence.append(f_mid)

        sequence_courante = nouvelle_sequence

    return sequence_courante
