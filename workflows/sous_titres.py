#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Word-timestamped subtitle workflow (Qwen3-ForcedAligner-0.6B via audio.cpp).

Turns an audio file into a word-level SRT. Two modes (MEMORY_BANK §1.68,
USER VALIDATED 2026-11-21 — v2 validation page 3/3):
- `align` (default): the prompt (-p) is the EXACT transcript of the audio —
  standalone forced alignment, short clips only (upstream does not chunk).
- `asr`: no transcript needed — Qwen3-ASR-0.6B + Silero VAD chunks long audio
  and the forced aligner attaches word timestamps (16 kHz mono resample).

Outputs: `<name>.srt` (one cue per word, 80 ms grid) + `<name>_words.json`
(raw engine output, samples in the fed file's domain) +, in asr mode,
`<name>_transcript.txt`.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.process import run_engine
from core.sous_titres import (
    DUREE_ALIGN_STANDALONE_MAX_S,
    aligner_mots,
    duree_audio,
    ecrire_srt_mots,
    transcrire_aligner,
)
from workflows.base import BaseWorkflow, WorkflowRegistry

SCRIPT_CHECK_CHARGE = Path(__file__).resolve().parent.parent / "scripts" / "check_charge_systeme.py"


@WorkflowRegistry.register
class SousTitresWorkflow(BaseWorkflow):
    """Word-timestamped subtitles: audio -> word-level SRT (ForcedAligner)."""

    name = "sous_titres"
    description = (
        "Word-timestamped subtitles from audio (Qwen3-ForcedAligner-0.6B, audio.cpp "
        "Vulkan): align mode = exact transcript (-p) + short clip; asr mode = long "
        "audio via Qwen3-ASR + Silero VAD chunking"
    )
    emoji = "💬"

    # CLI declaration (audit §2.2 keystone). --audio is declared ONCE
    # (acestep_cover, registered first) and consumed here too (§1.28).
    PARAMETRES = [
        dict(flags=("--st-mode",), choices=["align", "asr"], default="align",
             help="sous_titres engine path: align (default — exact transcript via -p, short clip) or asr (long audio, ASR produces the words)."),
        dict(flags=("--st-langue",), default="fr",
             help="sous_titres language, ISO 639-1 (default: fr; fr/en tested — MEMORY_BANK §1.68)."),
        dict(flags=("--st-quant",), choices=["q8_0", "f16"], default="q8_0",
             help="sous_titres aligner GGUF quantization (default: q8_0 — byte-identical to f16, MEMORY_BANK §1.68)."),
        dict(flags=("--st-vad",), default=None,
             help="sous_titres asr mode only: Silero VAD weights directory (16 kHz). Default: C:/Modeles_LLM/vad/silero_vad."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        audio = params.get("audio")
        if not audio:
            raise SystemExit(
                "❌ sous_titres needs the audio: pass --audio <path> (declared by the "
                "acestep_cover workflow, shared CLI flag)."
            )
        mode = params.get("st_mode") or "align"
        langue = params.get("st_langue") or "fr"
        quant = params.get("st_quant") or "q8_0"
        vad_dir = params.get("st_vad")

        transcript = params.get("prompt")
        if mode == "align" and not (transcript and transcript.strip()):
                raise SystemExit(
                    "❌ sous_titres align mode needs the EXACT transcript as the prompt: "
                    'uv run python main.py -w sous_titres --audio audio.wav -p "Le mot pour mot exact de l\'audio." '
                    "(or --st-mode asr for long audio without a transcript)."
                )

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        dossier = os.path.join(output_dir, "sous_titres")
        os.makedirs(dossier, exist_ok=True)
        nom = params.get("output") or slugifier_texte(
            os.path.splitext(os.path.basename(audio))[0]
        )
        base = os.path.join(dossier, nom)
        chemin_json = base + "_words.json"
        chemin_srt = base + ".srt"

        # Load pre-check (AGENTS.md rule: never launch heavy generation on a busy machine)
        if SCRIPT_CHECK_CHARGE.exists():
            self.log("System load pre-check (CPU/GPU/RAM/VRAM)...")
            retour = run_engine(
                [sys.executable, str(SCRIPT_CHECK_CHARGE)],
                capture=False, check=False, timeout=300, etiquette="load check",
            )
            if retour.returncode == 1:
                raise RuntimeError("Busy machine (check_charge_systeme exit 1) — wait for a free slot before relaunching.")

        if mode == "align":
            duree = duree_audio(audio)
            if duree is not None and duree > DUREE_ALIGN_STANDALONE_MAX_S:
                self.log(
                    f"Audio is {duree:.1f} s (> {DUREE_ALIGN_STANDALONE_MAX_S:.0f} s): standalone "
                    "align does NOT chunk — timestamps may drift; --st-mode asr is the long-audio path.",
                    emoji="⚠️",
                )
            self.log(f"Forced alignment ({langue}, {quant}, transcript prompt) — validated pipeline §1.68...")
            mots, taux = aligner_mots(audio, transcript, chemin_json, langue=langue, quant=quant)
        else:
            self.log(f"ASR word timestamps ({langue}, Silero VAD chunking) — validated pipeline §1.68...")
            mots, texte, taux = transcrire_aligner(
                audio, chemin_json, langue=langue, quant=quant, vad_dir=vad_dir,
            )
            self.log(f"ASR transcript: {texte[:80]}{'…' if len(texte) > 80 else ''}")

        ecrire_srt_mots(mots, taux, chemin_srt)
        nb = len(mots)
        self.log(f"{nb} words timed — SRT: {chemin_srt}", emoji="✅")
        return {
            "srt": chemin_srt,
            "words_json": chemin_json,
            "words": nb,
            "mode": mode,
            "langue": langue,
            "sample_rate": taux,
        }
