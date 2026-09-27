#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Finalization of "music_bg" music loops from the generated raw WAVs.
Replays phases 2-6 of the workflow (stable-zone looping, voice-bed
post-processing, LUFS bed, MP3, best-candidate selection) — useful after a
batch or to reprocess old candidates with an improved algorithm.

Usage:
  uv run python scripts/finaliser_boucles_music_bg.py [output_folder]
  (default: output/music_bg — scans candidats/cand_*_brut.wav)
"""

import os
import shutil
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
    construire_recette_ducking,
    convertir_mp3,
    convertir_ogg,
    exporter_bed_lufs,
    fabriquer_boucle,
    normaliser_pic,
    post_traiter_lit_voix,
    ressampler,
    verifier_boucle,
)

DUREE_CIBLE = 20.0
LUFS_CIBLE = -30.0


def main():
    dossier = sys.argv[1] if len(sys.argv) > 1 else os.path.join("output", "music_bg")
    dossier_bruts = os.path.join(dossier, "candidats")
    bruts = sorted(
        f for f in os.listdir(dossier_bruts) if f.startswith("cand_") and f.endswith("_brut.wav")
    )
    if not bruts:
        print(f"❌ No raw candidate in {dossier_bruts}")
        sys.exit(1)

    print(f"🎵 Finalizing {len(bruts)} loop(s) from {dossier_bruts}")
    candidats = []
    for nom in bruts:
        chemin = os.path.join(dossier_bruts, nom)
        index = nom.replace("cand_", "").replace("_brut.wav", "")
        audio, sr = charger_audio(chemin)
        boucle, infos = fabriquer_boucle(audio, sr, duree_cible=DUREE_CIBLE, mode="percussive")
        boucle = post_traiter_lit_voix(boucle, sr)
        boucle, sr = ressampler(boucle, sr, SR_CIBLE)
        boucle = normaliser_pic(boucle, -1.0)

        chemin_full = os.path.join(dossier_bruts, f"cand_{index}_loop_full.wav")
        soundfile.write(chemin_full, boucle, sr, subtype="PCM_16")
        verification = verifier_boucle(chemin_full)

        bed = os.path.join(dossier_bruts, f"cand_{index}_bed.wav")
        mesures = exporter_bed_lufs(chemin_full, bed, LUFS_CIBLE)
        mp3 = convertir_mp3(bed, os.path.join(dossier_bruts, f"cand_{index}_preview.mp3"))

        # Listening preview: loop ×3 at -16 LUFS (judge music + seam)
        tmp_x3 = os.path.join(dossier_bruts, f"_ecoute_{index}_tmp.wav")
        wav_x3 = os.path.join(dossier_bruts, f"_ecoute_{index}_x3.wav")
        soundfile.write(tmp_x3, np.tile(boucle, (3, 1)), sr, subtype="PCM_16")
        exporter_bed_lufs(tmp_x3, wav_x3, -16.0)
        ecoute = convertir_mp3(wav_x3, os.path.join(dossier, f"ECOUTE_cand{index}_boucle_x3.mp3"))
        os.remove(tmp_x3)
        os.remove(wav_x3)

        bpm_txt = f"{infos['bpm']:.0f} BPM" if infos.get("bpm") else "ambient"
        propre = "✅" if verification["propre"] else "⚠️"
        print(
            f"  cand_{index}: {bpm_txt}, {infos['duree']:.1f} s, "
            f"seam Δ{verification['ecart_couture_db']} dB, bed {mesures['I']:.1f} LUFS {propre}"
        )
        candidats.append({
            "index": index, "chemin": chemin_full, "bed": bed, "mp3": mp3, "ecoute": ecoute,
            "infos": infos, "verification": verification,
        })

    valides = [c for c in candidats if c["verification"]["propre"]]
    pool = valides or candidats
    meilleur = min(pool, key=lambda c: c["verification"]["ecart_couture_db"])
    print(f"\n🏆 Best loop: cand_{meilleur['index']} "
          f"(seam Δ{meilleur['verification']['ecart_couture_db']} dB)")

    # Promoting the best one to the root level
    nom_base = "tech_loop_minimal"
    shutil.copyfile(meilleur["chemin"], os.path.join(dossier, f"{nom_base}_full.wav"))
    shutil.copyfile(meilleur["bed"], os.path.join(dossier, f"{nom_base}_bed.wav"))
    shutil.copyfile(meilleur["mp3"], os.path.join(dossier, f"{nom_base}_preview.mp3"))
    convertir_ogg(os.path.join(dossier, f"{nom_base}_bed.wav"),
                  os.path.join(dossier, f"{nom_base}.ogg"))

    recette = construire_recette_ducking("voix_off.wav", f"{nom_base}_bed.wav", "mix_final.wav")
    chemin_recette = os.path.join(dossier, "recette_mixage_voix.txt")
    with open(chemin_recette, "w", encoding="utf-8") as f:
        f.write(
            "RECIPE: mixing the loop under a voice-over (automatic ducking)\n"
            "=============================================================\n\n"
            "1) Place this file next to your voice-over: voix_off.wav\n"
            "2) Run the command:\n\n"
            f"    {recette}\n\n"
            "3) Result: mix_final.wav — the loop is repeated to the length of the\n"
            "   voice and automatically attenuated as soon as the voice speaks.\n"
            "   Adjustments:\n"
            "   - music too present → lower volume=1.0 (e.g. 0.7)\n"
            "   - stronger ducking → ratio=8 and/or threshold=0.03\n"
            "   - faster recovery after the voice → release=350\n"
        )

    print(f"\n🎉 Deliverables in '{dossier}/':")
    print(f"  • {nom_base}_full.wav (full 48 kHz loop)")
    print(f"  • {nom_base}_bed.wav ({LUFS_CIBLE:.0f} LUFS, ready behind a voice)")
    print(f"  • {nom_base}.ogg / {nom_base}_preview.mp3")
    print("  • recette_mixage_voix.txt")
    print(f"  • {len(candidats)} finalized loops in candidats/ (bed + MP3)")
    print(f"  • {len(candidats)} listening previews ECOUTE_cand<N>_boucle_x3.mp3 (×3, -16 LUFS)")
    print("\n📋 Summary:")
    for c in sorted(candidats, key=lambda c: int(c["index"]) if c["index"].isdigit() else 0):
        b = c["infos"]
        bpm_txt = f"{b['bpm']:.0f} BPM" if b.get("bpm") else "ambient"
        print(f"  cand_{c['index']:>2} | {bpm_txt:>8} | {b['duree']:5.1f} s | {b.get('mesures') or '-':>2} measures | "
              f"seam {c['verification']['ecart_couture_db']:4.1f} dB")


if __name__ == "__main__":
    main()
