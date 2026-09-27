#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Listening preview of a music_bg candidate: fixed loop (stable zone) repeated
3 times and normalized to -16 LUFS -> ECOUTE_cand<N>_boucle_x3.mp3.
Lets you judge both the music AND the loop seam before finalization.

Usage:
  uv run python scripts/ecoute_candidat_music_bg.py <N> [dossier_output]
"""

import os
import sys

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import soundfile

from core.music_ai import (
    SR_CIBLE,
    charger_audio,
    convertir_mp3,
    exporter_bed_lufs,
    fabriquer_boucle,
    normaliser_pic,
    post_traiter_lit_voix,
    ressampler,
    verifier_boucle,
)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    index = sys.argv[1]
    dossier = sys.argv[2] if len(sys.argv) > 2 else os.path.join("output", "music_bg")
    brut = os.path.join(dossier, "candidats", f"cand_{index}_brut.wav")
    if not os.path.exists(brut):
        print(f"❌ Not found: {brut}")
        sys.exit(1)

    audio, sr = charger_audio(brut)
    boucle, infos = fabriquer_boucle(audio, sr, duree_cible=20.0, mode="percussive")
    boucle = post_traiter_lit_voix(boucle, sr)
    boucle, sr = ressampler(boucle, sr, SR_CIBLE)
    boucle = normaliser_pic(boucle, -1.0)

    tmp = os.path.join(dossier, "candidats", f"_ecoute_{index}_tmp.wav")
    wav_ecoute = os.path.join(dossier, f"ECOUTE_cand{index}_boucle_x3.wav")
    soundfile.write(tmp, np.tile(boucle, (3, 1)), sr, subtype="PCM_16")
    exporter_bed_lufs(tmp, wav_ecoute, -16.0)
    mp3 = convertir_mp3(wav_ecoute, os.path.join(dossier, f"ECOUTE_cand{index}_boucle_x3.mp3"))
    os.remove(tmp)
    os.remove(wav_ecoute)

    verifier_boucle(brut)
    bpm_txt = f"{infos['bpm']:.0f} BPM" if infos.get("bpm") else "ambient"
    print(f"🎧 cand_{index}: {bpm_txt}, loop {infos['duree']:.1f} s ({infos['mesures']} bars), "
          f"start {infos['depart_s']} s")
    print(f"   → {os.path.abspath(mp3)} ({os.path.getsize(mp3) / 1048576:.2f} MB)")


if __name__ == "__main__":
    main()
