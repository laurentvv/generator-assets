#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module d'estimation PBR neuronale (DeepBump / Deep Learning via ONNX Runtime).
Génère des Normal Maps, Roughness, Height, AO et le pack ORM Godot 4 de haute fidélité.
"""

import os
from typing import Dict, List, Optional, Tuple
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from core.config import DEFAULT_DEEPBUMP_MODEL, resoudre_modele_onnx

_SESSION_CACHE = {}


def _get_onnx_session(model_path: str):
    """Récupère ou met en cache la session ONNX."""
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


def _creer_fenetre_hanning_2d(taille: int) -> np.ndarray:
    """Crée un masque de fenêtrage 2D de Hanning pour le fondu des tuiles."""
    w1d = np.hanning(taille)
    w2d = np.outer(w1d, w1d).astype(np.float32)
    return np.maximum(w2d, 1e-4)


def estimer_normal_deepbump(
    image: Image.Image,
    model_path: Optional[str] = None,
    strength: float = 1.0
) -> Image.Image:
    """
    Génère une Normal Map OpenGL via DeepBump ONNX par fenêtrage glissant sans couture.
    """
    chemin = resoudre_modele_onnx(model_path, DEFAULT_DEEPBUMP_MODEL)
    if not chemin or not os.path.exists(chemin):
        print(f"⚠️ [DeepPBR] Modèle DeepBump introuvable ({chemin}).")
        from core.image_ops import generer_normal_map
        return generer_normal_map(image, strength=strength * 3.5)

    try:
        session = _get_onnx_session(chemin)
        img_gray = image.convert("L")
        w_orig, h_orig = img_gray.size

        # Si l'image est petite (<= 256), inférence directe
        if w_orig <= 256 and h_orig <= 256:
            img_resized = img_gray.resize((256, 256), Image.BILINEAR)
            arr = np.array(img_resized, dtype=np.float32) / 255.0
            tensor = arr[np.newaxis, np.newaxis, :, :].astype(np.float32)
            input_name = session.get_inputs()[0].name
            out = session.run(None, {input_name: tensor})[0][0]
            # out shape: (3, 256, 256)
            norm_rgb = np.transpose(out, (1, 2, 0))
            # Normaliser et convertir en uint8
            norm_rgb = (norm_rgb * 255.0).clip(0, 255).astype(np.uint8)
            norm_img = Image.fromarray(norm_rgb, mode="RGB").resize((w_orig, h_orig), Image.BILINEAR)
            return norm_img

        # Traitement par fenêtrage glissant avec recouvrement pour éviter les coutures
        tile_size = 256
        stride = 128
        hann = _creer_fenetre_hanning_2d(tile_size)

        # Padding pour que l'image soit couverte par les tuiles
        pad_x = (stride - (w_orig % stride)) % stride
        pad_y = (stride - (h_orig % stride)) % stride
        img_padded = ImageOps.expand(img_gray, (0, 0, pad_x + tile_size, pad_y + tile_size), fill=128)
        w_pad, h_pad = img_padded.size

        arr_padded = np.array(img_padded, dtype=np.float32) / 255.0

        # Accumulateurs pour vecteur normal (X, Y, Z) et poids
        accum = np.zeros((3, h_pad, w_pad), dtype=np.float32)
        poids = np.zeros((h_pad, w_pad), dtype=np.float32)

        input_name = session.get_inputs()[0].name

        for y in range(0, h_pad - tile_size + 1, stride):
            for x in range(0, w_pad - tile_size + 1, stride):
                patch = arr_padded[y:y + tile_size, x:x + tile_size]
                tensor = patch[np.newaxis, np.newaxis, :, :].astype(np.float32)
                out = session.run(None, {input_name: tensor})[0][0]  # shape (3, 256, 256)

                # Convertir [0, 1] en vecteurs normalisés [-1, 1]
                vec = out * 2.0 - 1.0

                for c in range(3):
                    accum[c, y:y + tile_size, x:x + tile_size] += vec[c] * hann
                poids[y:y + tile_size, x:x + tile_size] += hann

        # Normaliser par les poids
        poids = np.maximum(poids, 1e-4)
        for c in range(3):
            accum[c] /= poids

        # Découper la zone originale
        nx = accum[0, :h_orig, :w_orig]
        ny = accum[1, :h_orig, :w_orig]
        nz = accum[2, :h_orig, :w_orig]

        # Ajuster l'intensité de la normale
        nx *= strength
        ny *= strength
        nz = np.maximum(nz, 0.01)

        # Re-normaliser chaque vecteur (nx, ny, nz)
        longueur = np.sqrt(nx**2 + ny**2 + nz**2)
        nx /= longueur
        ny /= longueur
        nz /= longueur

        # Conversion en espace couleur Normal Map OpenGL (R=X, G=Y, B=Z) dans [0, 255]
        r = ((nx * 0.5 + 0.5) * 255.0).clip(0, 255).astype(np.uint8)
        g = ((ny * 0.5 + 0.5) * 255.0).clip(0, 255).astype(np.uint8)
        b = ((nz * 0.5 + 0.5) * 255.0).clip(0, 255).astype(np.uint8)

        norm_arr = np.stack([r, g, b], axis=-1)
        return Image.fromarray(norm_arr, mode="RGB")

    except Exception as e:
        print(f"❌ [DeepPBR] Erreur DeepBump : {e}")
        from core.image_ops import generer_normal_map
        return generer_normal_map(image, strength=strength * 3.5)


def estimer_pbr_complet(
    image: Image.Image,
    model_path: Optional[str] = None,
    strength: float = 1.0
) -> Dict[str, Image.Image]:
    """
    Génère l'ensemble du pack PBR physique :
    - Albedo (Base Color)
    - Normal Map (DeepBump neuronale)
    - Height Map (Relief)
    - Roughness Map (Rugosité estimée)
    - AO (Occlusion ambiante par courbure)
    - ORM Pack Godot (R=AO, G=Roughness, B=Metallic)
    """
    albedo = image.convert("RGB")
    normal = estimer_normal_deepbump(albedo, model_path=model_path, strength=strength)

    # 1. Height map : dérivée de la normale et de la luminance
    norm_arr = np.array(normal, dtype=np.float32) / 255.0
    # Z component indique la planéité
    nz = norm_arr[:, :, 2]
    lum = np.array(albedo.convert("L"), dtype=np.float32) / 255.0
    height_arr = (lum * 0.6 + (1.0 - nz) * 0.4)
    height_arr = ((height_arr - height_arr.min()) / (height_arr.max() - height_arr.min() + 1e-6) * 255.0).astype(np.uint8)
    height = Image.fromarray(height_arr, mode="L")

    # 2. Roughness map : calcul de la micro-rugosité via dispersion des normales
    nx_2d = norm_arr[:, :, 0]
    ny_2d = norm_arr[:, :, 1]
    norm_diff_x = np.abs(np.diff(nx_2d, axis=1, prepend=nx_2d[:, 0:1]))
    norm_diff_y = np.abs(np.diff(ny_2d, axis=0, prepend=ny_2d[0:1, :]))
    micro_relief = (norm_diff_x + norm_diff_y) * 4.0
    rough_base = 0.55 + 0.35 * (1.0 - lum) + 0.2 * micro_relief
    rough_arr = (rough_base.clip(0.1, 0.95) * 255.0).astype(np.uint8)
    roughness = Image.fromarray(rough_arr, mode="L")

    # 3. Ambient Occlusion (AO) : ombrage des creux
    ao_arr = (1.0 - (1.0 - lum) * 0.4 - (1.0 - nz) * 0.5)
    ao_arr = (ao_arr.clip(0.2, 1.0) * 255.0).astype(np.uint8)
    ao = Image.fromarray(ao_arr, mode="L")

    # 4. Metallic map : détection heuristique des surfaces métalliques sombres/réfléchissantes
    metal_arr = np.zeros_like(ao_arr)
    metallic = Image.fromarray(metal_arr, mode="L")

    # 5. Pack ORM (R=AO, G=Roughness, B=Metallic) pour Godot 4
    orm = Image.merge("RGB", (ao, roughness, metallic))

    return {
        "albedo": albedo,
        "normal": normal,
        "roughness": roughness,
        "height": height,
        "ao": ao,
        "metallic": metallic,
        "orm": orm
    }
