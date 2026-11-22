#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Consumer export presets (`godot` and `doc2video`).

Centralizes validated production recipes for the two primary consumer projects
(L'Heritier du Vide / Godot 4 and ai-doc2video / YouTube) so consumer bridges
and CLI sessions don't have to repeat the same validated flags.

Rule: preset defaults NEVER overwrite keys explicitly provided by the caller.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, Set

from core.config import classifier_licence_workflow

logger = logging.getLogger(__name__)

# Consumer -> workflow -> validated default parameters
PRESETS_CONSOMMATEURS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "godot": {
        "music_bg": {
            "moteur": "acestep",
            "lufs": -30.0,
            "loop_mode": "percussive",
            "candidats": 3,
        },
        "generate": {
            "segmenter": "auto",
            "size": 512,
        },
        "tileable": {
            "size": 1024,
        },
        "material3d": {
            "size": 1024,
        },
        "spritesheet": {
            "size": 256,
            "columns": 4,
        },
        "mesh_ia": {
            "res": 512,
            "faces_cible": 15000,
        },
        "audio_ambience": {
            "duration": 12.0,
        },
    },
    "doc2video": {
        "music_bg": {
            "moteur": "acestep",
            "lufs": -30.0,
            "loop_mode": "ambient",
            "candidats": 3,
        },
        "voix_off": {
            "moteur": "qwen3",
            "lufs_voix": -16.0,
        },
        "monoplan_ia": {
            "monoplan_frames": 65,
            "upscale_4k": True,
        },
        "h3_ref2va": {
            "turbo": True,
            "frames": 22,
        },
        "video_s2v": {
            "width": 512,
            "height": 512,
            "frames": 33,
            "fps": 16,
            "steps": 4,
            "cfg_scale": 1.0,
            "flow_shift": 3.0,
        },
        "sous_titres": {
            "st_mode": "asr",
            "st_langue": "fr",
            "st_quant": "q8_0",
        },
    },
}

# Flat CLI defaults that act as "unset" sentinels when deciding whether a preset
# may override a key that was NOT explicitly passed on the command line.
_SENTINEL_DEFAULTS: Dict[str, Any] = {
    "moteur": "acestep",
    "loop_mode": "percussive",
    "candidats": 3,
    "segmenter": "auto",
    "columns": 4,
    "res": 512,
    "steps": 25,
    "cfg_scale": 1.0,
    "turbo": False,
    "upscale_4k": False,
    "monoplan_frames": 65,
    "st_mode": "align",
    "st_langue": "fr",
    "st_quant": "q8_0",
    "lufs_voix": -16.0,
}


def appliquer_preset(
    workflow: str,
    params: Dict[str, Any],
    preset: Optional[str],
    *,
    explicites: Optional[Set[str]] = None,
    sd_model: Optional[str] = None,
    log_fn: Callable[[str], None] = print,
) -> Dict[str, Any]:
    """Applies a consumer preset onto `params` without overriding explicit user choices.

    When `preset == "doc2video"`, also checks commercial license clearance via
    `classifier_licence_workflow` and warns if a non-commercial workflow/model
    is selected (never blocks local runs — AGENTS.md 2026-11-21 rule).
    """
    if not preset:
        return params

    nom = preset.strip().lower()
    if nom not in PRESETS_CONSOMMATEURS:
        raise ValueError(
            f"Unknown preset '{preset}' (choices: {', '.join(sorted(PRESETS_CONSOMMATEURS))})."
        )

    wf = (workflow or "").strip().lower()
    out = dict(params)
    locked = set(explicites or ())
    overrides = PRESETS_CONSOMMATEURS[nom].get(wf, {})
    applied: Dict[str, Any] = {}

    for key, value in overrides.items():
        if key in locked:
            continue
        current = out.get(key)
        is_unset = (
            key not in out
            or current is None
            or (key in _SENTINEL_DEFAULTS and current == _SENTINEL_DEFAULTS[key])
        )
        if is_unset:
            out[key] = value
            applied[key] = value

    if applied:
        summary = ", ".join(f"{k}={v}" for k, v in applied.items())
        log_fn(f"🎛️ Preset '{nom}' applied to '{wf}': {summary}")
    else:
        log_fn(f"🎛️ Preset '{nom}' active for '{wf}' (no default override needed).")

    if nom == "doc2video":
        lic = classifier_licence_workflow(wf, moteur=out.get("moteur"), sd_model=sd_model)
        if not lic.get("commercial_ok", True):
            msg = (
                f"⚠️ Commercial clearance warning (--preset doc2video): "
                f"{wf} uses {lic['licence']}."
            )
            if lic.get("alternative_commerciale"):
                msg += f" Alternative: {lic['alternative_commerciale']}."
            logger.warning(msg)
            log_fn(msg)

    return out
