#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dance_sheet workflow — identity-consistent multi-pose sheet + dance clip.

Full chain USER VALIDATED end-to-end 2026-11-20 (MEMORY_BANK §1.55):
16 dual-ref poses (body + head-only identity patch, framing-lock note) →
numbered 4×4 sheet → monoplan seed frame → LTX-2.5 clip (via the validated
monoplan_ia workflow, zoom 1.0→1.0, 4 s) → 4-frame identity grid. The
dual-ref design fixed the v1 "la tête est horrible" verdict.

Machine-local by design: the body/head references and the 16 pose prompt
texts describe the user's own character — they stay under `--dance-dir`
(git-ignored), with explicit existence checks.

License note: Qwen-Image-Edit-2511 is RESEARCH licensed (personal /
non-commercial ONLY); the LTX clip inherits the LTX-2 Community terms.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.dance_sheet import (
    DANCE_CLIP_PROMPT,
    POSE_COUNT,
    assembler_planche,
    composer_amorce,
    generer_pose_dualref,
    grille_identite,
    poses_manquantes,
)
from core.process import run_engine
from workflows.base import BaseWorkflow, WorkflowRegistry
from workflows.monoplan_ia import MonoplanIaWorkflow

SCRIPT_CHECK_CHARGE = Path(__file__).resolve().parent.parent / "scripts" / "check_charge_systeme.py"


@WorkflowRegistry.register
class DanceSheetWorkflow(BaseWorkflow):
    name = "dance_sheet"
    description = (
        "Dance sheet chain (VALIDATED end-to-end 2026-11-20): 16 dual-ref identity"
        " poses (qwen-image-edit-2511, 512², 8 steps) -> numbered 4×4 sheet ->"
        " monoplan seed frame -> LTX-2.5 dance clip (zoom 1.0→1.0) -> identity grid"
    )

    emoji = "🕺"

    # CLI declaration (audit §2.2 keystone). --output comes from the flat table.
    PARAMETRES = [
        dict(flags=("--dance-dir",), dest="dance_dir", default="output/test_dance_sheet_m1106",
             help="dance_sheet: machine-local working dir holding the references and"
                  " the 16 pose prompt texts (output/ is git-ignored)."),
        dict(flags=("--dance-ref",), dest="dance_ref", default=None,
             help="dance_sheet: body reference PNG (default: <dance-dir>/ref512.png)."),
        dict(flags=("--dance-ref-head",), dest="dance_ref_head", default=None,
             help="dance_sheet: head-only identity reference PNG (default:"
                  " <dance-dir>/ref_head512.png)."),
        dict(flags=("--dance-prompts-dir",), dest="dance_prompts_dir", default=None,
             help="dance_sheet: dir with pose01.txt…pose16.txt (default:"
                  " <dance-dir>/prompts16)."),
        dict(flags=("--dance-no-clips",), dest="dance_no_clips", action="store_true", default=False,
             help="dance_sheet: stop after sheet + seed frame (skip the LTX clip and"
                  " the identity grid)."),
        dict(flags=("--dance-prompt",), dest="dance_prompt", default=None,
             help="dance_sheet: clip prompt (default: the validated identity-locked"
                  " dance prompt)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        dance_dir = params.get("dance_dir") or "output/test_dance_sheet_m1106"
        ref_corps = params.get("dance_ref") or os.path.join(dance_dir, "ref512.png")
        ref_tete = params.get("dance_ref_head") or os.path.join(dance_dir, "ref_head512.png")
        prompts_dir = params.get("dance_prompts_dir") or os.path.join(dance_dir, "prompts16")

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)
        prefixe = params.get("output") or slugifier_texte(
            params.get("prompt") or "dance_sheet"
        )[:60] or "dance_sheet"

        dossier_poses = os.path.join(output_dir, f"{prefixe}_poses")
        planche = os.path.join(output_dir, f"{prefixe}_2048.png")
        amorce = os.path.join(output_dir, f"{prefixe}_amorce.png")

        # Load pre-check (AGENTS.md rule: never launch heavy generation on a busy machine)
        if SCRIPT_CHECK_CHARGE.exists():
            self.log("System load pre-check (CPU/GPU/RAM/VRAM)...")
            retour = run_engine(
                [sys.executable, str(SCRIPT_CHECK_CHARGE)],
                capture=False, check=False, timeout=300, etiquette="load check",
            )
            if retour.returncode == 1:
                raise RuntimeError("Busy machine (check_charge_systeme exit 1) — wait for a free slot before relaunching.")

        # 1. The 16 dual-ref poses (resume-friendly: existing cells are skipped)
        manquantes = poses_manquantes(dossier_poses)
        if not manquantes:
            self.log(f"All {POSE_COUNT} poses already present — skipped.", emoji="↩️")
        for i in manquantes:
            chemin_prompt = os.path.join(prompts_dir, f"pose{i:02d}.txt")
            if not os.path.exists(chemin_prompt):
                raise FileNotFoundError(f"Pose prompt not found: {chemin_prompt}")
            with open(chemin_prompt, encoding="utf-8") as handle:
                texte = handle.read().strip()
            self.log(f"Pose {i:02d}/{POSE_COUNT} (dual-ref, 512², 8 steps)…")
            generer_pose_dualref(
                prompt=texte,
                sortie=os.path.join(dossier_poses, f"pose{i:02d}.png"),
                ref_corps=ref_corps,
                ref_tete=ref_tete,
                graine=int(params.get("seed") or 42),
            )
            self.log(f"Pose {i:02d} done.", emoji="✅")

        # 2. Numbered 4×4 sheet
        if not os.path.exists(planche):
            assembler_planche(dossier_poses, planche)
            self.log(f"Sheet assembled: {planche}", emoji="🧩")
        else:
            self.log(f"Sheet already present: {planche}")

        # 3. Monoplan seed frame (validated amorce geometry v3)
        if not os.path.exists(amorce):
            composer_amorce(os.path.join(dossier_poses, "pose01.png"), amorce)
            self.log(f"Seed frame composed: {amorce}", emoji="🖼️")
        else:
            self.log(f"Seed frame already present: {amorce}")

        livrables = {"poses": dossier_poses, "planche": planche, "amorce": amorce}
        if bool(params.get("dance_no_clips")):
            self.log("Sheet + seed frame delivered (--dance-no-clips).", emoji="✅")
            return livrables

        # 4. Dance clip through the validated monoplan_ia workflow (zoom 1.0→1.0)
        monoplan = MonoplanIaWorkflow()
        resultat = monoplan.run({
            "prompt": params.get("dance_prompt") or DANCE_CLIP_PROMPT,
            "input": amorce,
            "seed": int(params.get("seed") or 42),
            "monoplan_duration": 4.0,
            "zoom_debut": 1.0,
            "zoom_fin": 1.0,
            "output_dir": output_dir,
            "output": prefixe,
        })
        master = resultat["master"]
        livrables["clip"] = master

        # 5. Identity grid (validated 11-12 protocol: 4 frames, half-size 2×2)
        grille = os.path.join(output_dir, f"{prefixe}_grille_identite.png")
        grille_identite(master, grille)
        livrables["grille_identite"] = str(grille)
        self.log(f"Identity grid: {grille}", emoji="🪪")

        self.log(f"Dance chain complete — sheet: {planche} · clip: {master}", emoji="✅")
        return livrables
