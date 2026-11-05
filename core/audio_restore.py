#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Speech restoration (denoise / degrade repair) via RE-USE, audio.cpp
`reuse` family (audio-to-audio, conv encoder/decoder + 30 bidirectional
time-frequency Mamba blocks).

Recipe USER-VALIDATED on 2026-11-05 ("OK" on the restored A/B, degraded
synthetic voice vs restored — MEMORY_BANK §1.53):
- offline `reuse` family, NemotronLabs checkpoint (F32 GGUF, 38.7 MB),
  Vulkan, RTF 0.46 on a 9 s sample (4.21 s wall).
- Input 8-48 kHz, mono or stereo (channels processed independently),
  longer than ~20 ms; output = same rate, channels and length (s16le).
- NO seed: restoration is deterministic (enhancement, not generation).

⚠️ Storage: the F32 package is MANDATORY on Vulkan — the doc states F16
and Q8_0 produce incorrect Vulkan output (validated on CUDA only).

⚠️ License: the NemotronLabs checkpoint is OpenMDW-1.1
(commercial-friendly). The `realtime_reuse` family (streaming, 20 ms
causal) is NVIDIA NSCLv1 NON-COMMERCIAL — deliberately NOT wired here.
The original `reuse-f32` checkpoint is also non-commercial (NSCLv1).

For long recordings, per-chunk graph memory can be bounded with
`--restore-chunk <seconds>` (Hann overlap `--restore-overlap`, default
1 s). Chunking changes the bidirectional/normalization context → the
output can differ from the whole-recording render.
"""

import os
from typing import Any, Dict, List

from core.music_ai import resoudre_audiocpp
from core.process import run_engine

# NemotronLabs RE-USE GGUF (audio-cpp org, 38.7 MB — MEMORY_BANK §1.53).
MODELE_REUSE_NEMOTRONLABS = os.getenv(
    "REUSE_NEMOTRONLABS_MODEL",
    os.path.join("C:\\Modeles_LLM", "RE-USE-GGUF", "reuse-nemotronlabs-f32.gguf"),
)

# Default settings (validated recipe — deterministic, no seed involved).
RECIPE = {
    "backend": "vulkan",
    "threads": 8,
    "chunk": 0.0,     # 0 = whole recording in one pass (native batching)
    "overlap": 1.0,   # Hann-weighted overlap, only used when chunk > 0
}


def resoudre_modele() -> str:
    """Path of the RE-USE NemotronLabs F32 GGUF (the Vulkan-valid, commercial-friendly package)."""
    modele = MODELE_REUSE_NEMOTRONLABS
    if not os.path.exists(modele):
        raise FileNotFoundError(
            f"RE-USE GGUF not found: {modele} — downloadable from "
            f"audio-cpp/RE-USE-GGUF (reuse-nemotronlabs-f32.gguf)."
        )
    return modele


def construire_cmd_reuse(
    modele: str,
    entree: str,
    sortie: str,
    threads: int = RECIPE["threads"],
    chunk: float = RECIPE["chunk"],
    overlap: float = RECIPE["overlap"],
) -> List[str]:
    """Build the audiocpp_cli command line (pure function, unit-tested).

    Chunk options are transmitted only when chunking is enabled (chunk > 0),
    mirroring the CLI contract: unprovided options keep engine defaults.
    """
    cmd = [
        resoudre_audiocpp(), "--task", "s2s", "--family", "reuse",
        "--model", modele, "--backend", RECIPE["backend"],
        "--threads", str(threads),
        "--audio", entree,
    ]
    if chunk > 0:
        cmd += [
            "--request-option", f"audio_chunk_duration_sec={chunk}",
            "--request-option", f"audio_chunk_overlap_sec={overlap}",
        ]
    cmd += ["--metrics", "--out", sortie]
    return cmd


def restaurer_reuse(
    source: str,
    sortie: str,
    threads: int = RECIPE["threads"],
    chunk: float = RECIPE["chunk"],
    overlap: float = RECIPE["overlap"],
) -> Dict[str, Any]:
    """Full restoration path: RE-USE NemotronLabs on Vulkan.

    WAV output at the input rate/channels/length (s16le, engine format —
    the exact format of the sample the user validated).
    """
    modele = resoudre_modele()
    if chunk < 0:
        raise ValueError(f"--restore-chunk must be >= 0 (got {chunk}); 0 = whole recording.")
    if chunk > 0 and overlap >= chunk:
        raise ValueError(
            f"--restore-overlap ({overlap} s) must be shorter than "
            f"--restore-chunk ({chunk} s)."
        )
    libelle = f"chunk {chunk:g}s/overlap {overlap:g}s" if chunk > 0 else "whole recording"
    print(f"🧪 RE-USE speech restoration (NemotronLabs F32, Vulkan, {libelle})")
    cmd = construire_cmd_reuse(modele, source, sortie,
                               threads=threads, chunk=chunk, overlap=overlap)
    run_engine(cmd, capture=False, check=True, timeout=3600, etiquette="audio.cpp reuse")
    if not os.path.exists(sortie):
        raise RuntimeError(f"The restoration did not produce {sortie}")
    return {"sortie": sortie, "modele": modele, "chunk": chunk, "overlap": overlap}
