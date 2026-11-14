#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video S2V Workflow: Speech-to-Video talking avatar from portrait image + driving audio.

Engine: Wan2.2-S2V-14B-Q4_K_M + wav2vec2_large_english_fp16 + LightX2V 4-step
low_noise LoRA via `sd-cli -M vid_gen` on Vulkan0 (`te=cpu, vae=cpu`).

USER VALIDATED 2026-11-14 (`s2v_probe_512_33f_4step.mp4` "c'est ok"):
  512x512, 33 frames @ 16 fps (2.0 s), 4 steps, cfg 1.0, euler, flow-shift 3.0,
  `--max-vram 10 --offload-to-cpu --vae-tiling --flash-attn off,diffusion=on --rng cpu`
  (~24.1 min compute on NVMe; ~2.9 min one-shot temporary D:->C: staging when cold).
832x480x33 (`14,040` tokens vs `9,216`) exceeds RX 6950 XT 16 GB / 32 GB RAM limits
(`ErrorDeviceLost` with diffusion FA or 53 GiB Commit swap stall without FA); keep
512x512 + optional RealESRGAN/SeedVR2 upscale for HD outputs.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

from core.config import DEFAULT_BACKEND, DEFAULT_FFMPEG, DEFAULT_OUTPUT_DIR, slugifier_texte
from core.diffusion import generer_video_s2v_wan
from core.process import run_engine
from core.video_qc import auditer_clip_video
from workflows.base import BaseWorkflow, WorkflowRegistry

SCRIPT_CHECK_CHARGE = Path(__file__).resolve().parent.parent / "scripts" / "check_charge_systeme.py"
DEFAULT_S2V_PROMPT = (
    "A person speaking calmly and clearly, natural lip-sync and subtle head movements, steady camera."
)


def _remux_mp4_compatible(webm_path: str, mp4_path: str, ffmpeg_bin: str = DEFAULT_FFMPEG) -> str:
    """Transcodes sd-cli WebM (VP8 + pcm_s16le) into desktop-playable H.264/AAC MP4."""
    run_engine(
        [
            ffmpeg_bin, "-y", "-v", "error",
            "-i", webm_path,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            mp4_path,
        ],
        capture=True, check=True, timeout=300, etiquette="ffmpeg s2v mp4 remux",
    )
    return mp4_path


@WorkflowRegistry.register
class VideoS2VWorkflow(BaseWorkflow):
    """Speech-driven talking portrait video (.webm + .mp4) via Wan2.2-S2V 14B on Vulkan."""

    name = "video_s2v"
    description = (
        "Speech-to-Video talking portrait: portrait (-i) + speech (--audio) via Wan2.2-S2V 14B "
        "(validated 2026-11-14: 512x512, 33f @ 16 fps, 4 steps LightX2V)"
    )
    emoji = "🎙️"

    # Reuses existing shared CLI flags so the frozen consumer CLI surface never drifts:
    #   -i/--input, --audio (acestep_cover), --frames/--fps/--width/--height (shared),
    #   --steps/--cfg-scale/--seed/--lora-dir/-l (parser), --flow-shift (video),
    #   --max-vram/--dry-run (h3_ref2va).
    PARAMETRES = []

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        init_img = params.get("input")
        if not init_img:
            raise ValueError("A portrait image is required for video_s2v (-i <portrait.png>).")
        if not os.path.exists(init_img):
            raise FileNotFoundError(f"Portrait image not found: {init_img}")

        audio_path = params.get("audio")
        if not audio_path:
            raise ValueError("A driving speech audio file is required for video_s2v (--audio <speech.wav>).")
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Driving audio file not found: {audio_path}")

        prompt = (params.get("prompt") or "").strip() or DEFAULT_S2V_PROMPT
        dry_run = bool(params.get("dry_run"))
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)

        out_name = params.get("output")
        base_name = out_name or f"{slugifier_texte(Path(init_img).stem)[:40]}_s2v"
        stem = str(Path(base_name).with_suffix("")) if base_name.lower().endswith((".webm", ".mp4")) else base_name
        webm_output_path = os.path.join(output_dir, f"{stem}.webm")
        mp4_output_path: Optional[str] = None if params.get("no_mp4") else os.path.join(output_dir, f"{stem}.mp4")

        width = int(params.get("width") or 512)
        height = int(params.get("height") or 512)
        frames = int(params.get("frames") or 33)
        fps = int(params.get("fps") or 16)
        requested_steps = params.get("steps")
        if requested_steps in (None, 25):
            steps = 4
            if requested_steps == 25:
                self.log("steps=25 (global CLI default) → validated Wan2.2-S2V LoRA recipe = 4 steps.", emoji="ℹ️")
        else:
            steps = int(requested_steps)
        cfg_scale = float(params["cfg_scale"]) if params.get("cfg_scale") is not None else 1.0
        flow_shift = float(params["flow_shift"]) if params.get("flow_shift") is not None else 3.0
        seed = int(params["seed"]) if params.get("seed") is not None else 42
        max_vram = int(params["max_vram"]) if params.get("max_vram") is not None else 10

        raw_loras = params.get("loras")
        if not raw_loras and isinstance(params.get("lora"), str):
            raw_loras = [params["lora"]]
        if raw_loras is not None:
            cleaned_loras = [s.strip() for s in raw_loras if isinstance(s, str) and s.strip()]
            loras_val = (
                []
                if (not cleaned_loras or all(s.lower() in ("none", "off") for s in cleaned_loras))
                else cleaned_loras
            )
        else:
            loras_val = None

        if not dry_run and SCRIPT_CHECK_CHARGE.exists():
            self.log("System load pre-check (CPU/GPU/RAM/VRAM)...")
            gate_result = run_engine(
                [sys.executable, str(SCRIPT_CHECK_CHARGE)],
                capture=False, check=False, timeout=300, etiquette="load check",
            )
            if gate_result.returncode == 1:
                raise RuntimeError("Busy machine (check_charge_systeme exit 1) — wait for a free slot before relaunching.")

        cfg_backend = self.config.get("backend")
        effective_backend = (
            params.get("backend")
            or (cfg_backend if cfg_backend and cfg_backend != DEFAULT_BACKEND else None)
            or "diffusion=vulkan0,te=cpu,vae=cpu"
        )

        t_start = time.time()
        webm_path = generer_video_s2v_wan(
            prompt=prompt,
            init_image=init_img,
            audio_path=audio_path,
            sd_cli=self.config.get("sd_cli"),
            model_path=params.get("diffusion_model"),
            t5xxl_path=params.get("t5xxl"),
            vae_path=params.get("vae"),
            audio_encoder_path=params.get("audio_encoder"),
            video_frames=frames,
            fps=fps,
            width=width,
            height=height,
            steps=steps,
            cfg_scale=cfg_scale,
            flow_shift=flow_shift,
            seed=seed,
            max_vram=max_vram,
            loras=loras_val,
            lora_dir=params.get("lora_dir") or self.config.get("lora_dir"),
            flash_attn=params.get("flash_attn") or "off,diffusion=on",
            backend=effective_backend,
            threads=int(self.config.get("threads", 16)),
            output_path=webm_output_path,
            stage_to_nvme=bool(params.get("stage_to_nvme", True)),
            dry_run=dry_run,
            log_fn=self.log,
        )

        mp4_real: Optional[str] = None
        qc_res: Optional[Dict[str, Any]] = None
        if not dry_run:
            if mp4_output_path:
                mp4_real = _remux_mp4_compatible(webm_path, mp4_output_path)
                self.log(f"Windows-playable MP4 exported: {mp4_real}")
            if not params.get("skip_qc"):
                qc_target = mp4_real or webm_path
                qc_res = auditer_clip_video(qc_target)
                self.log(f"Video QC ({os.path.basename(qc_target)}): ok={qc_res.get('ok')} metrics={qc_res.get('metrics')}")
                if not qc_res.get("ok"):
                    self.log(f"⚠️ Video QC warnings/issues: {qc_res.get('issues')}", emoji="⚠️")

        duration_min = (time.time() - t_start) / 60.0
        result = {
            "prompt": prompt,
            "video_path": mp4_real or webm_path,
            "webm_path": webm_path,
            "mp4_path": mp4_real,
            "reference_image": init_img,
            "audio_path": audio_path,
            "resolution": f"{max(16, (width + 15) // 16 * 16)}x{max(16, (height + 15) // 16 * 16)}",
            "frames": max(5, frames),
            "fps": fps,
            "steps": steps,
            "cfg_scale": cfg_scale,
            "flow_shift": flow_shift,
            "seed": seed,
            "qc": qc_res,
            "duration_min": round(duration_min, 1),
            "dry_run": dry_run,
            "status": "success",
        }
        self.log(json.dumps(result, ensure_ascii=False, indent=2), emoji="📊")
        return result
