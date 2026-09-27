#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
High-precision AI segmentation and cutout module (RMBG / BiRefNet via ONNX Runtime).
"""

import os
from typing import Optional
import numpy as np
from PIL import Image

from core.config import DEFAULT_RMBG_MODEL, resoudre_modele_onnx

_SESSION_CACHE = {}


def _get_onnx_session(model_path: str):
    """Retrieves or creates a cached ONNX Runtime session."""
    global _SESSION_CACHE
    if model_path not in _SESSION_CACHE:
        import onnxruntime as ort
        # Use the available providers (DirectML / CPU)
        available = ort.get_available_providers()
        preferred_providers = []
        if "DmlExecutionProvider" in available:
            preferred_providers.append("DmlExecutionProvider")
        if "CPUExecutionProvider" in available:
            preferred_providers.append("CPUExecutionProvider")

        session = ort.InferenceSession(model_path, providers=preferred_providers or available)
        _SESSION_CACHE[model_path] = session
    return _SESSION_CACHE[model_path]


def detourer_ia(
    image: Image.Image,
    model_path: Optional[str] = None,
    threshold: float = 0.5
) -> Image.Image:
    """
    Cuts out an image with a segmentation neural network (RMBG-1.4 / BiRefNet).
    Guarantees a clean cut with no white fringe, handling hair, weapons and transparencies.

    Args:
        image: Source PIL image (RGB or RGBA)
        model_path: Path to the ONNX model (or None for the default path)
        threshold: Mask cutoff threshold (if needed)

    Returns:
        PIL image in RGBA mode with the alpha channel cut out
    """
    chemin = resoudre_modele_onnx(model_path, DEFAULT_RMBG_MODEL)
    if not chemin or not os.path.exists(chemin):
        print(f"⚠️ [Segmentation] ONNX model not found ({chemin}).")
        return image.convert("RGBA")

    try:
        session = _get_onnx_session(chemin)
        img_rgb = image.convert("RGB")
        w_orig, h_orig = img_rgb.size

        # Standard RMBG / BiRefNet preprocessing: normalized 1024x1024
        input_size = (1024, 1024)
        img_resized = img_rgb.resize(input_size, Image.BILINEAR)

        arr = np.array(img_resized, dtype=np.float32) / 255.0
        # Normalisation standard (mean=[0.5, 0.5, 0.5], std=[1.0, 1.0, 1.0])
        arr = (arr - [0.5, 0.5, 0.5]) / [1.0, 1.0, 1.0]
        tensor = np.transpose(arr, (2, 0, 1))[np.newaxis, :].astype(np.float32)

        # Inference
        input_name = session.get_inputs()[0].name
        outputs = session.run(None, {input_name: tensor})
        mask_raw = outputs[0][0, 0]

        # Mask normalization 0.0 -> 1.0
        min_v = mask_raw.min()
        max_v = mask_raw.max()
        if max_v > min_v:
            mask_norm = (mask_raw - min_v) / (max_v - min_v)
        else:
            mask_norm = mask_raw

        # Resize the mask back to the original size
        mask_uint8 = (mask_norm * 255.0).clip(0, 255).astype(np.uint8)
        mask_img = Image.fromarray(mask_uint8, mode="L").resize((w_orig, h_orig), Image.BILINEAR)

        # Apply the alpha channel
        result = img_rgb.convert("RGBA")
        result.putalpha(mask_img)
        return result

    except Exception as e:
        print(f"❌ [Segmentation] AI cutout error: {e}")
        return image.convert("RGBA")
