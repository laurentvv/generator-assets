#!/usr/bin/env python3 -*-
# -*- coding: utf-8 -*-
"""
Character Voice Workflow: English character voices from the VALIDATED pilot
casting recipes (novel2video-ai E01, user verdicts 2026-09-27 — MEMORY_BANK
§1.31).

Two engines, auto-selected:
- `--kokoro-voice <id>` → raw Kokoro-82M preset render (audio.cpp, Vulkan),
  language auto-resolved from the voice prefix (a* → en-us, b* → en-gb);
- `--instruct "<EN>"` (no --kokoro-voice) → Qwen3-TTS 1.7B VoiceDesign
  (qwentts.cpp), `--lang English`, seed 42 by default.

Post chains (composable): `--pitch-ratio` (duration-preserving, source-rate
aware), `--whisper` (Elder treatment), `--hollow` (Void treatment, level
compensated). Final normalization -16 LUFS + listening MP3 by default
(`--brut` to keep the raw comparison render).

Validated examples (the pilot's cast):
  -w voix_perso "<line>" --kokoro-voice am_onyx                          # Alaric
  -w voix_perso "<line>" --kokoro-voice am_michael                      # Elder
  -w voix_perso "<line>" --instruct "<marc>" --pitch-ratio 0.90         # Marc
  -w voix_perso "<line>" --instruct "<elian>"                           # Elian
  -w voix_perso "<line>" --kokoro-voice am_onyx --pitch-ratio 0.85 --hollow  # Void
"""

import os
import functools
import shutil
from typing import Any, Dict

from core.config import slugifier_texte
from core.voix_off import finaliser_voix
from core.voix_perso import (
    generer_voix_design_qwen,
    generer_voix_kokoro,
    appliquer_hollow,
    appliquer_ratio_pitch,
    appliquer_whisper,
)
from core.music_ai import convertir_mp3
from workflows.base import BaseWorkflow, WorkflowRegistry

# Instructs of the validated pilot cast (novel2video-ai E01) — usable verbatim.
INSTRUCTS_VALIDES = {
    "marc": ("very young boy of exactly eight years old, extremely high "
             "pitched child voice, energetic bratty teasing, fast excited speech"),
    "elian": ("tiny boy of five years old, extremely high pitched soft voice, "
              "very quiet slow gentle speech, shy"),
}


@WorkflowRegistry.register
class VoixPersoWorkflow(BaseWorkflow):
    """English character voice (Kokoro preset or Qwen3 VoiceDesign + post chains)."""

    name = "voix_perso"
    description = ("English character voice — raw Kokoro preset or Qwen3-TTS "
                   "VoiceDesign instruct (qwentts.cpp), validated post chains "
                   "(pitch/whisper/hollow), -16 LUFS + MP3")

    emoji = "🎭"

    # --instruct (voix_off), --seed (flat table) and --lufs-voix (voix_off)
    # are reused from the aggregated surface — never redeclared (anti-duplicate).
    PARAMETRES = [
        dict(flags=("--kokoro-voice",), default=None,
             help="Kokoro preset voice id (e.g. am_onyx, bm_george) — raw human "
                  "render, selects the Kokoro engine; language auto-resolved "
                  "from the prefix (a* en-us, b* en-gb)."),
        dict(flags=("--pitch-ratio",), type=float, default=1.0,
             help="Pitch ratio applied after synthesis (1.0 = unchanged, 0.90 = "
                  "validated Marc recipe) — duration preserved."),
        dict(flags=("--whisper",), action="store_true",
             help="Dry-whisper post chain (lowpass 1800 Hz + 60 ms echo) — "
                  "validated Elder treatment."),
        dict(flags=("--hollow",), action="store_true",
             help="Cavernous hollow post chain (lowpass 900 Hz + 120 ms echo + "
                  "6 dB compensation) — validated Void treatment."),
        dict(flags=("--brut",), action="store_true",
             help="Skip the final -16 LUFS normalization (raw comparison render)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        brut = (params.get("prompt") or "").strip()
        if not brut:
            raise ValueError("Provide the English text to read (positional parameter).")
        if os.path.isfile(brut) and brut.lower().endswith(".txt"):
            with open(brut, encoding="utf-8") as f:
                texte = f.read().strip()
            self.log(f"Text loaded from {brut} ({len(texte)} characters)", "📄")
        else:
            texte = brut
        if not texte:
            raise ValueError("The text to read is empty.")

        kokoro_voice = params.get("kokoro_voice") or None
        instruct = params.get("instruct") or None
        if not kokoro_voice and not instruct:
            raise ValueError(
                "Select an engine: --kokoro-voice <id> (preset voice) or "
                "--instruct \"<English instruction>\" (VoiceDesign)."
            )
        if kokoro_voice and instruct:
            self.log("Kokoro engine selected (--kokoro-voice): --instruct ignored.", "⚠️")

        nom = slugifier_texte(params.get("output") or "voix_perso")[:60]
        output_dir = params.get("output_dir") or ""
        if not output_dir or output_dir == "godot_assets":
            output_dir = "output/voix_perso"
        dossier = os.path.join(output_dir, nom)
        os.makedirs(dossier, exist_ok=True)

        wav_brut = os.path.join(dossier, f"{nom}_brut.wav")
        if kokoro_voice:
            self.log(f"Engine Kokoro (voice {kokoro_voice}), raw render", "🎭")
            generer_voix_kokoro(texte, wav_brut, voice_id=kokoro_voice)
        else:
            seed = params.get("seed")
            seed = int(seed) if seed is not None and int(seed) >= 0 else 42
            generer_voix_design_qwen(texte, instruct, wav_brut, seed=seed)

        # Post chains, composable in the validated order: pitch → whisper/hollow.
        # Intermediate steps write to alternating temp files (ffmpeg refuses a
        # chain reading and writing the same path); only the last step writes
        # the final <name>.wav.
        wav_final = os.path.join(dossier, f"{nom}.wav")
        ratio = float(params.get("pitch_ratio") or 1.0)
        etapes = []
        if abs(ratio - 1.0) > 1e-6:
            etapes.append((functools.partial(appliquer_ratio_pitch, ratio=ratio),
                           f"Pitch ratio x{ratio:g} (duration preserved)"))
        if params.get("whisper"):
            etapes.append((appliquer_whisper, "Whisper chain (Elder treatment)"))
        if params.get("hollow"):
            etapes.append((appliquer_hollow, "Hollow chain (Void treatment, +6 dB compensation)"))

        if not etapes:
            shutil.copyfile(wav_brut, wav_final)
            self.log("No post chain: raw render delivered as-is", "ℹ️")
        else:
            tmp_a = os.path.join(dossier, f"{nom}_post_a.tmp.wav")
            tmp_b = os.path.join(dossier, f"{nom}_post_b.tmp.wav")
            source = wav_brut
            for i, (fonction, desc) in enumerate(etapes):
                derniere = i == len(etapes) - 1
                destination = wav_final if derniere else (tmp_a if i % 2 == 0 else tmp_b)
                fonction(source, destination)
                self.log(f"{desc} applied", "🎚️")
                if source != wav_brut:
                    os.remove(source)
                source = destination

        if params.get("brut"):
            mp3 = os.path.splitext(wav_final)[0] + ".mp3"
            convertir_mp3(wav_final, mp3)
            self.log(f"Character voice (raw, unnormalized): {wav_final}", "✅")
            return {"wav": wav_final, "mp3": mp3, "brut": wav_brut,
                    "files": [wav_final, mp3]}

        lufs = float(params.get("lufs_voix") or -16.0)
        finals = finaliser_voix(wav_final, lufs_cible=lufs)
        self.log(f"Character voice ready: {finals['wav']} ({finals['lufs']} LUFS) — "
                 f"listening: {finals['mp3']}", "✅")
        return {"wav": finals["wav"], "mp3": finals["mp3"], "brut": wav_brut,
                "intermediaire": wav_final,
                "files": [finals["wav"], finals["mp3"]]}
