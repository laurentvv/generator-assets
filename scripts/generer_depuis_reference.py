#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generation of NEW music with the DNA of a reference: automatic BPM and key
detection on the reference audio (full file recommended), then ACE-Step
generation (xl-turbo by default) with those constraints IMPOSED on the
planner LM. Method validated on 2026-09-06 on Love Like Blood's
"Johannesburg" (rendered BPM 83.3 vs 83.3 source).

The style itself is described in text (--style): the script locks the numbers,
the human (or the agent) provides the words.

Usage:
  uv run python scripts/generer_depuis_reference.py <audio_ref> --style "<style EN>" [options]

Example:
  uv run python scripts/generer_depuis_reference.py "C:\\musique\\ref.mp3" \
    --style "German gothic rock 1990, dark wave, hypnotic tribal groove, pulsing bass, chiming chorus guitars" \
    --duree 240 -o mon_titre
"""

import argparse
import os
import subprocess
import sys
import tempfile

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from core.config import ACESTEP15_VARIANTES
from core.music_ai import (
    charger_audio,
    convertir_mp3,
    estimer_bpm,
    generer_musique_acestep,
    resoudre_ffmpeg,
)

NOTES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
PROFIL_MAJEUR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
PROFIL_MINEUR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def convertir_en_wav(chemin: str) -> str:
    """Converts any audio (mp3…) to 48 kHz WAV if soundfile cannot read it."""
    try:
        charger_audio(chemin)
        return chemin
    except Exception:
        sortie = os.path.join(tempfile.gettempdir(), "ref_48k_" + os.path.basename(chemin) + ".wav")
        cmd = [resoudre_ffmpeg(), "-hide_banner", "-y", "-i", chemin,
               "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", sortie]
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        return sortie


def detecter_tonalite(audio: np.ndarray, sr: int) -> str:
    """Key via correlation of the chroma with the Krumhansl profiles."""
    mono = audio.mean(axis=1)
    fen, hop = 8192, 4096
    freqs = np.fft.rfftfreq(fen, 1 / sr)
    demi_tons = np.where(freqs > 0, np.round(12 * np.log2(np.maximum(freqs, 1e-9) / 440.0)).astype(int) % 12, -1)
    chroma = np.zeros(12)
    for i in range(0, len(mono) - fen, hop):
        s = np.abs(np.fft.rfft(mono[i:i + fen] * np.hanning(fen))) ** 2
        for d in range(12):
            chroma[d] += s[demi_tons == d].sum()
    chroma /= max(chroma.sum(), 1e-12)

    meilleur = None
    for tonique in range(12):
        for profil, mode in ((PROFIL_MINEUR, "minor"), (PROFIL_MAJEUR, "major")):
            c = np.corrcoef(chroma, np.roll(profil, tonique))[0, 1]
            if meilleur is None or c > meilleur[0]:
                meilleur = (c, f"{NOTES[tonique]} {mode}")
    return meilleur[1]


def main():
    parseur = argparse.ArgumentParser(description="New music with the DNA (BPM + key) of a reference")
    parseur.add_argument("reference", help="Reference audio (MP3/WAV — full file recommended)")
    parseur.add_argument("--style", required=True,
                         help="EN style description (the script appends BPM/key and \"instrumental\")")
    parseur.add_argument("--duree", type=float, default=60.0, help="Duration in seconds (default: 60)")
    parseur.add_argument("--variante", choices=list(ACESTEP15_VARIANTES), default="xl-turbo",
                         help="ACE-Step variant (default: xl-turbo)")
    parseur.add_argument("--avec-paroles", default=None,
                         help=".txt lyrics file ([Verse]/[Chorus]… structure) for a song instead of an instrumental")
    parseur.add_argument("--langue", default="fr", help="Lyrics language (default: fr)")
    parseur.add_argument("--tonalite", default=None,
                         help="Force the key (e.g. \"C# minor\") — otherwise auto-detected from the reference")
    parseur.add_argument("--negatif", default=None,
                         help="EN negative prompt — what to EXCLUDE (e.g. \"pop, soft, mellow, gentle, ambient, ballad\")")
    parseur.add_argument("--graine", type=int, default=-1)
    parseur.add_argument("-o", "--output", default="inspire_de_ref", help="Output name (default: inspire_de_ref)")
    args = parseur.parse_args()

    if not os.path.exists(args.reference):
        print(f"❌ Not found: {args.reference}")
        sys.exit(1)

    print(f"🔍 Analyzing the reference: {args.reference}")
    chemin_wav = convertir_en_wav(args.reference)
    audio, sr = charger_audio(chemin_wav)
    bpm = estimer_bpm(audio, sr)
    if bpm is None:
        print("❌ No tempo detected in the reference (non-pulsive audio?).")
        sys.exit(1)
    bpm = int(round(bpm))
    tonalite = args.tonalite or detecter_tonalite(audio, sr)
    print(f"🧬 Detected DNA: {bpm} BPM • {tonalite} • {len(audio) / sr:.0f} s analyzed")

    paroles = "[Instrumental]"
    if args.avec_paroles:
        with open(args.avec_paroles, encoding="utf-8") as f:
            paroles = f.read().strip()

    description = f"{args.style}, {bpm} BPM, {tonalite}, completely instrumental, no vocals"

    sortie = os.path.join("output", "music_chanson", f"{args.output}.wav")
    os.makedirs(os.path.dirname(sortie), exist_ok=True)
    print(f"🎵 Generation: {args.duree:.0f} s • variant {args.variante} • BPM {bpm} and {tonalite} imposed on the planner")
    chemin, backend = generer_musique_acestep(
        description=description,
        chemin_sortie=sortie,
        duree=args.duree,
        etapes=8,
        backend="vulkan",
        lyrics=paroles,
        variante=args.variante,
        langue=args.langue,
        graine=args.graine,
        negatif=args.negatif,
        log=print,
    )
    mp3 = convertir_mp3(chemin, chemin.replace(".wav", ".mp3"), 224)
    print(f"\n🎧 Listen: {os.path.abspath(mp3)} ({os.path.getsize(mp3) / 1048576:.1f} MB) — backend {backend}")


if __name__ == "__main__":
    main()
