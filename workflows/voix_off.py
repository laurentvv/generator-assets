#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Voice-Over Workflow: expressive reading of a text by local TTS (audio.cpp Vulkan),
with cloning of a French reference voice if provided.

Engines: qwen3-tts 1.7B (default with a reference, Apache-2.0, --instruct expression),
VoxCPM2 (default without reference, Apache-2.0, cloning without transcript),
Fish S2-Pro (inline tags [whisper]/[excited], research licence).

Pipeline: level control/normalization of the reference (gap ≤ 2026-09-06:
recording at -39 LUFS → normalization -18 LUFS), automatic ASR transcription if the
engine requires it, generation, final normalization -16 LUFS (YouTube dialogue
standard) + listening MP3.
"""

import os
from typing import Any, Dict

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.voix_off import MOTEURS, finaliser_voix, generer_voix_off
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class VoixOffWorkflow(BaseWorkflow):
    """Cloned/expressive voice-over (qwen3-tts / VoxCPM2 / Fish S2-Pro GGUF, Vulkan) normalized for YouTube."""

    name = "voix_off"
    description = ("Expressive reading of a text by local TTS (audio.cpp Vulkan) with "
                   "optional voice cloning — qwen3-tts/VoxCPM2 (Apache-2.0) or Fish S2-Pro, "
                   "normalized output -16 LUFS + MP3")

    emoji = "🎙️"

    # CLI declarations (audit §2.2, migration from cli/parser.py's flat table:
    # help/defaults kept as-is, unchanged surface). --moteur (shared with
    # music_bg) lives in music_bg.
    PARAMETRES = [
        dict(flags=("--voix-ref",), default=None,
             help="Voice reference to clone for voix_off (WAV/MP3/M4A; level automatically controlled/normalized)."),
        dict(flags=("--instruct",), default=None,
             help="Style/emotion instruction for qwen3-tts (voix_off) — e.g.: 'energetic YouTube narrator tone'."),
        dict(flags=("--lufs-voix",), type=float, default=-16.0,
             help="Target LUFS of the voice-over (default: -16, YouTube dialogue standard)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # The text: prompt parameter (the text itself) OR path of a .txt file
        brut = (params.get("prompt") or "").strip()
        if not brut:
            raise ValueError("Provide the text to read (positional parameter) or a .txt file.")
        if os.path.isfile(brut) and brut.lower().endswith(".txt"):
            with open(brut, encoding="utf-8") as f:
                texte = f.read().strip()
            self.log(f"Text loaded from {brut} ({len(texte)} characters)", "📄")
        else:
            texte = brut
        if not texte:
            raise ValueError("The text to read is empty.")

        # Engine: --moteur is shared with music_bg (default 'acestep') → any
        # value outside the voice engines = automatic choice.
        moteur = params.get("moteur")
        if moteur not in MOTEURS:
            moteur = None
        voix_ref = params.get("voix_ref") or None
        if not moteur:
            moteur = "qwen3" if voix_ref else "voxcpm2"
            self.log(f"Automatic engine: {moteur}", "🎚️")

        instruct = params.get("instruct") or None
        lufs = float(params.get("lufs_voix") or -16.0)
        backend = params.get("music_backend") or "vulkan"
        seed = params.get("seed")

        nom = slugifier_texte(params.get("output") or "voix_off")[:60]
        # By convention (like music_bg), production tracks go into output/
        output_dir = params.get("output_dir") or ""
        if not output_dir or output_dir == DEFAULT_OUTPUT_DIR:
            output_dir = "output/voix_off"
        dossier = os.path.join(output_dir, nom)
        os.makedirs(dossier, exist_ok=True)

        self.log(f"Engine {moteur} ({MOTEURS[moteur]['licence']}) — "
                 f"cloning {'enabled' if voix_ref else 'disabled'}", "🎙️")
        brut_wav = os.path.join(dossier, "voix_off_brut.wav")
        res = generer_voix_off(
            texte=texte,
            moteur=moteur,
            wav_ref=voix_ref,
            instruct=instruct,
            sortie=brut_wav,
            backend=backend,
            seed=int(seed) if seed is not None and int(seed) >= 0 else None,
            dossier_travail=dossier,
        )
        finals = finaliser_voix(brut_wav, lufs_cible=lufs)
        self.log(f"Voice ready: {finals['wav']} ({finals['lufs']} LUFS) — listening: {finals['mp3']}", "✅")
        return {**res, **finals}
