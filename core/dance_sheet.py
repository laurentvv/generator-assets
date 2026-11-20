#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dance-sheet chain: 16 dual-ref poses → numbered 4×4 sheet → monoplan seed
frame → (clip via the monoplan_ia workflow) → identity grid.

Chain USER VALIDATED end-to-end 2026-11-20 (MEMORY_BANK §1.55, interactive
page verdicts): the dual-ref design fixed the v1 "la tête est horrible"
verdict — body reference + head-only identity patch keep the face consistent
across the 16 poses AND through the LTX-2.5 I2V clip.

Validated recipe (frozen): qwen-image-edit-2511 Q3_K_M + Qwen2.5-VL-7B encoder
+ mmproj-F16 + original 20B VAE, 512², 8 steps, cfg 1.0, euler, seed 42,
flash-attn + offload-to-cpu, Lightning-8steps LoRA (tag via
`formater_prompt_avec_loras`), framing-lock note appended to every pose prompt.
"""

import os
from pathlib import Path
from typing import List, Tuple

from PIL import Image, ImageDraw, ImageFont

from core.config import (
    DEFAULT_FFMPEG,
    DEFAULT_QWEN_IMAGE_EDIT2511_LLM,
    DEFAULT_QWEN_IMAGE_EDIT2511_LORA_DIR,
    DEFAULT_QWEN_IMAGE_EDIT2511_MODEL,
    DEFAULT_QWEN_IMAGE_EDIT2511_VAE,
    DEFAULT_QWEN_IMAGE_EDIT2511_VISION,
)
from core.diffusion import generer_image_qwen21
from core.process import run_engine

# Validated chain constants (§1.55) — do not improvise.
POSE_COUNT = 16
POSE_SIZE = 512
SHEET_COLUMNS = 4
AMORCE_CANVAS = (832, 480)
AMORCE_INSET = 10
AMORCE_FIG_H = 466
IDENTITY_GRID_TIMES = (0.0, 1.3, 2.6, 3.9)

LIGHTNING_8STEPS_LORA: Tuple[str, float] = (
    "Qwen-Image-Edit-2511-Lightning-8steps-V1.0-bf16", 1.0,
)

# Monoplan clip prompt — validated 2026-11-20 on the v2 chain (identity hold
# start-to-end, fluid footwork; night_dance_v2.sh verbatim, --zoom 1.0→1.0).
DANCE_CLIP_PROMPT = (
    "The same man from the image dances smoothly in place on a plain white"
    " background: elegant rhythmic dance with natural weight shifts,"
    " coordinated arm gestures, a light side step and a gentle pivot,"
    " finishing in a confident stance. His shirt, sleeves and trousers follow"
    " the movement softly. He keeps exactly the same face, short brown hair,"
    " brown linen shirt, beige trousers, brown belt and wristwatch"
    " throughout. Fixed eye-level full-body shot, generous margins, plain"
    " white background, no cuts, no zoom, no duplicates, no morphing, natural"
    " footwork without sliding."
)

FRAMING_LOCK_NOTE = (
    " The second reference image is a close-up of his face for identity only"
    " - match it exactly. Keep a WIDE full-body shot: the entire figure from"
    " head to feet visible, centered, with generous white margins, feet never"
    " cropped."
)

FONT_CANDIDATES = [
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/seguisb.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def render_pose_dualref(
    prompt: str,
    output_path: str,
    ref_body: str,
    ref_head: str,
    seed: int = 42,
    steps: int = 8,
    modele: str = DEFAULT_QWEN_IMAGE_EDIT2511_MODEL,
    llm: str = DEFAULT_QWEN_IMAGE_EDIT2511_LLM,
    vae: str = DEFAULT_QWEN_IMAGE_EDIT2511_VAE,
    vision: str = DEFAULT_QWEN_IMAGE_EDIT2511_VISION,
    lora_dir: str = DEFAULT_QWEN_IMAGE_EDIT2511_LORA_DIR,
) -> None:
    """Renders ONE 512² pose from the two references (validated §1.55 recipe).

    `prompt` must NOT carry the Lightning LoRA tag: it is appended exactly once
    here via the `loras` plumbing (sd-cli ACCUMULATES duplicate tags — the
    P0 review finding of 2026-11-20; strength 2.0 instead of 1.0 = silent
    divergence from the frozen recipe).
    """
    for chemin, role in ((ref_body, "body reference"), (ref_head, "head reference")):
        if not os.path.exists(chemin):
            raise FileNotFoundError(f"{role} not found: {chemin}")
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    generer_image_qwen21(
        prompt=prompt + FRAMING_LOCK_NOTE,
        model=modele,
        llm=llm,
        vae=vae,
        width=POSE_SIZE,
        height=POSE_SIZE,
        steps=steps,
        cfg_scale=1.0,
        seed=seed,
        output_path=output_path,
        loras=[LIGHTNING_8STEPS_LORA],
        lora_dir=lora_dir,
        ref_images=[ref_body, ref_head],
        llm_vision=vision,
    )


def assemble_sheet(poses_dir: str, output_path: str) -> Path:
    """Stitches the 16 numbered poses into the 4×4 white sheet (validated v2 look)."""
    cellules: List[Image.Image] = []
    for i in range(1, POSE_COUNT + 1):
        p = Path(poses_dir) / f"pose{i:02d}.png"
        if not p.exists():
            raise FileNotFoundError(f"missing cell: {p}")
        cellules.append(Image.open(p).convert("RGB"))
    cote = cellules[0].width
    heterogenes = [im.size for im in cellules if im.size != cellules[0].size]
    if heterogenes:
        raise ValueError(
            "Heterogeneous pose cells (resume across resolutions?): "
            f"expected {cellules[0].size}, got {heterogenes[:4]}…"
        )
    sheet = Image.new("RGB", (cote * SHEET_COLUMNS, cote * SHEET_COLUMNS), "white")
    draw = ImageDraw.Draw(sheet)
    police = _load_font(cote // 8)
    for idx, img in enumerate(cellules):
        n = idx + 1
        x, y = (idx % SHEET_COLUMNS) * cote, (idx // SHEET_COLUMNS) * cote
        sheet.paste(img, (x, y))
        draw.rectangle([x + 4, y + 4, x + 4 + cote // 7, y + 4 + cote // 11], fill="white")
        draw.text((x + cote // 60, y + cote // 120), str(n), fill="black", font=police)
        draw.rectangle([x, y, x + cote - 1, y + cote - 1], outline="lightgray", width=2)
    sortie_path = Path(output_path)
    os.makedirs(sortie_path.parent, exist_ok=True)
    sheet.save(sortie_path)
    return sortie_path


def compose_seed_frame(pose_path: str, output_path: str) -> Path:
    """Composes the monoplan seed frame ("amorce" — repo domain vocabulary)
    from pose01 (validated geometry v3)."""
    src = Image.open(pose_path).convert("RGB")
    largeur, hauteur = src.size
    fig = src.crop((AMORCE_INSET, AMORCE_INSET, largeur - AMORCE_INSET, hauteur - AMORCE_INSET))
    echelle = AMORCE_FIG_H / fig.height
    fig = fig.resize((round(fig.width * echelle), AMORCE_FIG_H), Image.LANCZOS)
    canvas = Image.new("RGB", AMORCE_CANVAS, "white")
    canvas.paste(fig, ((AMORCE_CANVAS[0] - fig.width) // 2, (AMORCE_CANVAS[1] - AMORCE_FIG_H) // 2))
    sortie_path = Path(output_path)
    os.makedirs(sortie_path.parent, exist_ok=True)
    canvas.save(sortie_path)
    return sortie_path


def identity_grid(video: str, output_path: str, times: Tuple[float, ...] = IDENTITY_GRID_TIMES) -> Path:
    """Extracts frames at `times` from the clip into a half-size 2×2 identity grid."""
    cadres: List[Image.Image] = []
    for t in times:
        brut = f"{output_path}.f{t}.png"
        commande = [
            DEFAULT_FFMPEG, "-y", "-v", "error", "-ss", str(t),
            "-i", video, "-frames:v", "1", brut,
        ]
        run_engine(commande, capture=True, check=True, timeout=120, etiquette="frame extraction")
        if not os.path.exists(brut):
            raise FileNotFoundError(f"frame not extracted at t={t}s: {brut}")
        cadres.append(Image.open(brut).convert("RGB"))
        os.remove(brut)
    largeur, hauteur = cadres[0].size
    grid = Image.new("RGB", (largeur * 2, hauteur * 2), "white")
    for i, cadre in enumerate(cadres):
        grid.paste(cadre, ((i % 2) * largeur, (i // 2) * hauteur))
    grid = grid.resize((largeur, hauteur), Image.LANCZOS)
    sortie_path = Path(output_path)
    os.makedirs(sortie_path.parent, exist_ok=True)
    grid.save(sortie_path)
    return sortie_path


def missing_poses(poses_dir: str) -> List[int]:
    """Indices (1-based) of the poses not yet rendered — the chain resumes."""
    manquantes: List[int] = []
    for i in range(1, POSE_COUNT + 1):
        if not (Path(poses_dir) / f"pose{i:02d}.png").exists():
            manquantes.append(i)
    return manquantes
