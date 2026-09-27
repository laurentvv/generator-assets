#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
H3 Ref2VA Workflow: video+audio continuation by MiniMax-H3 reference (sd-cli Vulkan).

Generates a video (webm, audio included) that continues a source video: the tail of
the source (last N frames + paired WAV, extracted by ffmpeg) becomes the
Ref2VA <Video 1>/<Audio 1> reference of the H3 DiT. Brick validated on 2026-09-09
(MEMORY_BANK §1.16) — the mechanism of the ComfyUI node "HR Endless Sampler" reproduced
in CLI, here for ONE chunk (the multi-chunk loop remains to be validated separately).
Reference window = validated recipe (12 frames + 0.5 s of audio ending at the
join); the "endless" join levers (audio window reaching backwards, 5 reference
frames on the join, reference downscale) are tested upstream by
`scripts/proto_endless_h3.py` and will only land here once validated.

⚠️ Heavy: ~70 min for 22 frames on RX 6950 XT in the base recipe, ~38 min with the
turbo mode (distilled 8-step LoRA, validated on 2026-09-09 — `--turbo`). The load
pre-check blocks if the machine is busy.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

from core.config import (
    DEFAULT_FFMPEG,
    DEFAULT_H3_REF2VA_TURBO_LORA,
    DEFAULT_OUTPUT_DIR,
    slugifier_texte,
)
from core.diffusion import generer_video_ref2va_h3
from core.process import EngineError, run_engine
from workflows.base import BaseWorkflow, WorkflowRegistry

SCRIPT_CHECK_CHARGE = Path(__file__).resolve().parent.parent / "scripts" / "check_charge_systeme.py"


def _duree_et_audio(ffmpeg: str, video_path: str) -> tuple:
    """Returns (duration_s, has_audio_track) of a video via ffprobe/ffmpeg."""
    probe = str(ffmpeg).replace("ffmpeg.exe", "ffprobe.exe")
    duree = None
    try:
        sortie = run_engine(
            [probe, "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", video_path],
            check=True, timeout=60, etiquette="ffprobe duration",
        ).stdout.strip()
        duree = float(sortie)
    except Exception:
        duree = None
    try:
        run_engine(
            [probe, "-v", "error", "-select_streams", "a", "-show_entries",
             "stream=index", "-of", "csv=p=0", video_path],
            check=True, timeout=60, etiquette="ffprobe audio",
        )
        a_audio = True
    except EngineError:
        a_audio = False
    return duree, a_audio


@WorkflowRegistry.register
class H3Ref2VAWorkflow(BaseWorkflow):
    """Video+audio continuation by Ref2VA reference (MiniMax-H3, webm output with audio)."""

    name = "h3_ref2va"
    description = "Video+audio continuation via MiniMax-H3 Ref2VA (ref = tail of a source video, webm with audio)"

    emoji = "🗣️"

    # CLI declarations (audit §2.2, migration from cli/parser.py's flat table:
    # help/defaults kept as-is, unchanged surface). --frames and --width/
    # --height stay in the flat table (shared across families).
    PARAMETRES = [
        dict(flags=("--ref-frames",), type=int, default=12,
             help="h3_ref2va: tail frames extracted from the source video as reference (default: 12)."),
        dict(flags=("--ref-audio",),
             help="h3_ref2va: Ref2VA reference WAV (extracted automatically from the source if omitted)."),
        dict(flags=("--max-vram",), type=int, default=10,
             help="h3_ref2va: VRAM GiB budget of the DiT via sd-cli graph-cut (default: 10, mandatory on 16 GB)."),
        dict(flags=("--turbo",), action="store_true",
             help="h3_ref2va: distilled 8-step turbo LoRA (VALIDATED recipe 2026-09-09 — ~2x faster, quality and reference join >= baseline; MEMORY_BANK §1.16)."),
        dict(flags=("--dry-run",), action="store_true", default=False,
             help="Builds the command (extraction + sd-cli) without running the generation."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        prompt = params.get("prompt")
        if not prompt:
            raise ValueError("The 'prompt' parameter is required for the h3_ref2va workflow (describe the SEQUEL, with <Video 1>/<Audio 1>).")
        source = params.get("input")
        if not source:
            raise ValueError("The '-i <source video | frame folder>' parameter is required (Ref2VA reference).")

        dry_run = bool(params.get("dry_run"))
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)

        nom_base = params.get("output") or f"{slugifier_texte(prompt)[:60]}_h3"
        video_output_path = os.path.join(output_dir, f"{nom_base}.webm")

        # --- Load pre-check (AGENTS.md rule: never launch heavy generation on a busy machine)
        if not dry_run and SCRIPT_CHECK_CHARGE.exists():
            self.log("System load pre-check (CPU/GPU/RAM/VRAM)...")
            retour = run_engine(
                [sys.executable, str(SCRIPT_CHECK_CHARGE)],
                capture=False, check=False, timeout=300, etiquette="load check",
            )
            if retour.returncode == 1:
                raise RuntimeError("Busy machine (check_charge_systeme exit 1) — wait for a free slot before relaunching.")

        # --- Reference resolution: direct frame folder, or extraction of a video's tail
        ref_frames_dir: Optional[str] = None
        ref_audio_path: Optional[str] = params.get("ref_audio")
        source_abs = os.path.abspath(source)

        if os.path.isdir(source_abs):
            ref_frames_dir = source_abs
            self.log(f"Reference = provided frame folder: {ref_frames_dir}"
                     + (f" + WAV {ref_audio_path}" if ref_audio_path else " (no WAV → do not mention <Audio 1>)"))
        else:
            if not os.path.exists(source_abs):
                raise FileNotFoundError(f"Source not found: {source_abs}")
            n_ref = int(params.get("ref_frames", 12) or 12)
            duree_ref = n_ref / 24.0
            duree_src, a_audio = _duree_et_audio(DEFAULT_FFMPEG, source_abs)
            if duree_src is None:
                raise RuntimeError(f"Cannot read the duration of {source_abs} via ffprobe.")

            ref_dir = os.path.join(output_dir, f"{nom_base}_ref")
            os.makedirs(ref_dir, exist_ok=True)
            ref_frames_dir = ref_dir
            start = max(0.0, duree_src - duree_ref)
            self.log(f"Extracting the reference tail: {n_ref} frames ({duree_ref:.2f}s) starting at {start:.2f}s / {duree_src:.2f}s...")

            cmd_frames = [
                DEFAULT_FFMPEG, "-y", "-v", "error",
                "-ss", f"{start:.3f}", "-i", source_abs, "-t", f"{duree_ref:.3f}",
                "-vf", "fps=24", os.path.join(ref_dir, "frame_%04d.png")
            ]
            run_engine(cmd_frames, capture=False, check=True, timeout=600, etiquette="ffmpeg reference frames")
            n_extraits = len([f for f in os.listdir(ref_dir) if f.endswith(".png")])
            self.log(f"→ {n_extraits} frames extracted into {ref_dir}")

            if a_audio and not ref_audio_path:
                ref_audio_path = os.path.join(ref_dir, "ref_audio.wav")
                run_engine(
                    [DEFAULT_FFMPEG, "-y", "-v", "error",
                     "-ss", f"{start:.3f}", "-i", source_abs, "-t", f"{duree_ref:.3f}",
                     "-vn", "-acodec", "pcm_s16le", ref_audio_path],
                    capture=False, check=True, timeout=300, etiquette="ffmpeg reference audio",
                )
                self.log(f"→ Reference WAV extracted: {ref_audio_path}")
            elif not a_audio:
                self.log("Source without audio track → video-only reference (prompt without <Audio 1>).", emoji="⚠️")

        # --- Generation (validated recipe §1.16: te=cpu, vae=cpu, max-vram 10, cfg 1.0, rng cpu)
        # Turbo mode (validated 2026-09-09): distilled LoRA + 8 steps → ~38 min instead of ~70.
        turbo = bool(params.get("turbo"))
        lora = DEFAULT_H3_REF2VA_TURBO_LORA if turbo else None
        steps_demandes = params.get("steps")
        if steps_demandes in (None, 25):
            steps = 8 if turbo else 20
            if steps_demandes == 25:
                self.log(
                    f"steps=25 (global CLI default) → validated H3 recipe = {steps} steps"
                    + (" (turbo)" if turbo else "") + ", adjusted.", emoji="ℹ️"
                )
        else:
            steps = int(steps_demandes)
        if turbo:
            self.log("Turbo mode: distilled 8-step LoRA (validated recipe 2026-09-09, MEMORY_BANK §1.16)...")

        self.log(f"H3 Ref2VA generation (allow ~{38 if turbo else 70} min for 22 frames on this machine)...")
        debut = time.time()
        generer_video_ref2va_h3(
            prompt=prompt,
            sd_cli=self.config.get("sd_cli"),
            ref_video_dir=ref_frames_dir,
            ref_audio_path=ref_audio_path,
            video_frames=int(params.get("frames") or 22),
            fps=24,  # H3 enforces 24 fps (any other value is overridden by the model)
            width=int(params.get("width") or 864),
            height=int(params.get("height") or 480),
            steps=steps,
            cfg_scale=float(params.get("cfg_scale") or 1.0),
            seed=int(params.get("seed", -1)),
            max_vram=int(params.get("max_vram") or 10),
            lora=lora,
            lora_dir=params.get("lora_dir"),
            threads=int(self.config.get("threads", 16)),
            output_path=video_output_path,
            dry_run=dry_run,
            log_fn=self.log
        )
        duree_min = (time.time() - debut) / 60.0

        resultat = {
            "prompt": prompt,
            "video_path": video_output_path,
            "ref_frames_dir": ref_frames_dir,
            "ref_audio": ref_audio_path,
            "duree_run_min": round(duree_min, 1),
            "dry_run": dry_run,
            "status": "success"
        }
        self.log(json.dumps(resultat, ensure_ascii=False, indent=2), emoji="📊")
        return resultat
