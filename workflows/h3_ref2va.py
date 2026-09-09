#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow H3 Ref2VA : continuation vidéo+audio par référence MiniMax-H3 (sd-cli Vulkan).

Génère une vidéo (webm, audio inclus) qui continue une vidéo source : la queue de
la source (N dernières trames + WAV appairé, extraits par ffmpeg) devient la
référence Ref2VA <Video 1>/<Audio 1> du DiT H3. Brique validée le 2026-09-09
(MEMORY_BANK §1.16) — mécanisme du nœud ComfyUI « HR Endless Sampler » reproduit
en CLI, ici pour UN chunk (la boucle multi-chunks reste à valider séparément).
Fenêtre de référence = recette validée (12 trames + 0,5 s audio finissant au
raccord) ; les leviers de raccord « endless » (fenêtre audio qui remonte, 5 trames
de réf sur le raccord, downscale réf) sont testés en amont par
`scripts/proto_endless_h3.py` et ne remonteront ici qu'une fois validés.

⚠️ Lourd : ~70 min pour 22 trames sur RX 6950 XT en recette de base, ~38 min avec le
mode turbo (LoRA distillé 8 steps, validé le 2026-09-09 — `--turbo`). Le pré-contrôle
de charge système bloque si la machine est occupée.
"""

import json
import os
import subprocess
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
from workflows.base import BaseWorkflow, WorkflowRegistry

SCRIPT_CHECK_CHARGE = Path(__file__).resolve().parent.parent / "scripts" / "check_charge_systeme.py"


def _duree_et_audio(ffmpeg: str, video_path: str) -> tuple:
    """Retourne (durée_s, a_piste_audio) d'une vidéo via ffprobe/ffmpeg."""
    probe = str(ffmpeg).replace("ffmpeg.exe", "ffprobe.exe")
    duree = None
    try:
        sortie = subprocess.run(
            [probe, "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", video_path],
            capture_output=True, text=True, check=True
        ).stdout.strip()
        duree = float(sortie)
    except Exception:
        duree = None
    try:
        subprocess.run(
            [probe, "-v", "error", "-select_streams", "a", "-show_entries",
             "stream=index", "-of", "csv=p=0", video_path],
            capture_output=True, text=True, check=True
        )
        a_audio = True
    except subprocess.CalledProcessError:
        a_audio = False
    return duree, a_audio


@WorkflowRegistry.register
class H3Ref2VAWorkflow(BaseWorkflow):
    """Continuation vidéo+audio par référence Ref2VA (MiniMax-H3, sortie webm avec audio)."""

    name = "h3_ref2va"
    description = "Continuation vidéo+audio via MiniMax-H3 Ref2VA (réf = queue d'une vidéo source, webm avec audio)"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        prompt = params.get("prompt")
        if not prompt:
            raise ValueError("Le paramètre 'prompt' est requis pour le workflow h3_ref2va (décrire la SUITE, avec <Video 1>/<Audio 1>).")
        source = params.get("input")
        if not source:
            raise ValueError("Le paramètre '-i <vidéo source | dossier de trames>' est requis (référence Ref2VA).")

        dry_run = bool(params.get("dry_run"))
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)

        nom_base = params.get("output") or f"{slugifier_texte(prompt)[:60]}_h3"
        video_output_path = os.path.join(output_dir, f"{nom_base}.webm")

        # --- Pré-contrôle de charge (règle AGENTS.md : jamais de génération lourde sur machine occupée)
        if not dry_run and SCRIPT_CHECK_CHARGE.exists():
            self.log("Pré-contrôle de charge système (CPU/GPU/RAM/VRAM)...")
            retour = subprocess.run([sys.executable, str(SCRIPT_CHECK_CHARGE)])
            if retour.returncode == 1:
                raise RuntimeError("Machine occupée (check_charge_systeme exit 1) — attendre un créneau libre avant de relancer.")

        # --- Résolution de la référence : dossier de trames direct, ou extraction de la queue d'une vidéo
        ref_frames_dir: Optional[str] = None
        ref_audio_path: Optional[str] = params.get("ref_audio")
        source_abs = os.path.abspath(source)

        if os.path.isdir(source_abs):
            ref_frames_dir = source_abs
            self.log(f"Référence = dossier de trames fourni : {ref_frames_dir}"
                     + (f" + WAV {ref_audio_path}" if ref_audio_path else " (sans WAV → ne pas mentionner <Audio 1>)"))
        else:
            if not os.path.exists(source_abs):
                raise FileNotFoundError(f"Source introuvable : {source_abs}")
            n_ref = int(params.get("ref_frames", 12) or 12)
            duree_ref = n_ref / 24.0
            duree_src, a_audio = _duree_et_audio(DEFAULT_FFMPEG, source_abs)
            if duree_src is None:
                raise RuntimeError(f"Impossible de lire la durée de {source_abs} via ffprobe.")

            ref_dir = os.path.join(output_dir, f"{nom_base}_ref")
            os.makedirs(ref_dir, exist_ok=True)
            ref_frames_dir = ref_dir
            start = max(0.0, duree_src - duree_ref)
            self.log(f"Extraction de la queue de référence : {n_ref} trames ({duree_ref:.2f}s) à partir de {start:.2f}s / {duree_src:.2f}s...")

            cmd_frames = [
                DEFAULT_FFMPEG, "-y", "-v", "error",
                "-ss", f"{start:.3f}", "-i", source_abs, "-t", f"{duree_ref:.3f}",
                "-vf", "fps=24", os.path.join(ref_dir, "frame_%04d.png")
            ]
            subprocess.run(cmd_frames, check=True)
            n_extraits = len([f for f in os.listdir(ref_dir) if f.endswith(".png")])
            self.log(f"→ {n_extraits} trames extraites dans {ref_dir}")

            if a_audio and not ref_audio_path:
                ref_audio_path = os.path.join(ref_dir, "ref_audio.wav")
                subprocess.run(
                    [DEFAULT_FFMPEG, "-y", "-v", "error",
                     "-ss", f"{start:.3f}", "-i", source_abs, "-t", f"{duree_ref:.3f}",
                     "-vn", "-acodec", "pcm_s16le", ref_audio_path],
                    check=True
                )
                self.log(f"→ WAV de référence extrait : {ref_audio_path}")
            elif not a_audio:
                self.log("Source sans piste audio → référence vidéo seule (prompt sans <Audio 1>).", emoji="⚠️")

        # --- Génération (recette validée §1.16 : te=cpu, vae=cpu, max-vram 10, cfg 1.0, rng cpu)
        # Mode turbo (validé 2026-09-09) : LoRA distillé + 8 steps → ~38 min au lieu de ~70.
        turbo = bool(params.get("turbo"))
        lora = DEFAULT_H3_REF2VA_TURBO_LORA if turbo else None
        steps_demandes = params.get("steps")
        if steps_demandes in (None, 25):
            steps = 8 if turbo else 20
            if steps_demandes == 25:
                self.log(
                    f"steps=25 (défaut CLI global) → recette H3 validée = {steps} steps"
                    + (" (turbo)" if turbo else "") + ", ajusté.", emoji="ℹ️"
                )
        else:
            steps = int(steps_demandes)
        if turbo:
            self.log("Mode turbo : LoRA distillé 8 steps (recette validée 2026-09-09, MEMORY_BANK §1.16)...")

        self.log(f"Génération H3 Ref2VA (compter ~{38 if turbo else 70} min pour 22 trames sur ce poste)...")
        debut = time.time()
        generer_video_ref2va_h3(
            prompt=prompt,
            sd_cli=self.config.get("sd_cli"),
            ref_video_dir=ref_frames_dir,
            ref_audio_path=ref_audio_path,
            video_frames=int(params.get("frames") or 22),
            fps=24,  # H3 impose 24 fps (toute autre valeur est surchargée par le modèle)
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
