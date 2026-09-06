#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génération d'une NOUVELLE musique avec l'ADN d'une référence : détection
automatique du BPM et de la tonalité sur l'audio de référence (fichier
complet recommandé), puis génération ACE-Step (xl-turbo par défaut) avec ces
contraintes IMPOSÉES au planner LM. Méthode validée le 2026-09-06 sur
« Johannesburg » de Love Like Blood (BPM rendu 83,3 vs 83,3 source).

Le style lui-même se décrit en texte (--style) : le script verrouille les
nombres, l'humain (ou l'agent) fournit les mots.

Usage :
  uv run python scripts/generer_depuis_reference.py <audio_ref> --style "<style EN>" [options]

Exemple :
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
    """Convertit un audio quelconque (mp3…) en WAV 48 kHz si soundfile ne le lit pas."""
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
    """Tonalité par corrélation du chroma avec les profils de Krumhansl."""
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
    parseur = argparse.ArgumentParser(description="Nouvelle musique avec l'ADN (BPM + tonalité) d'une référence")
    parseur.add_argument("reference", help="Audio de référence (MP3/WAV — fichier complet recommandé)")
    parseur.add_argument("--style", required=True,
                         help="Description du style EN (le script ajoute BPM/tonalité et « instrumental »)")
    parseur.add_argument("--duree", type=float, default=60.0, help="Durée en secondes (défaut : 60)")
    parseur.add_argument("--variante", choices=list(ACESTEP15_VARIANTES), default="xl-turbo",
                         help="Variante ACE-Step (défaut : xl-turbo)")
    parseur.add_argument("--avec-paroles", default=None,
                         help="Fichier .txt de paroles (structure [Verse]/[Chorus]…) pour une chanson au lieu d'un instrumental")
    parseur.add_argument("--langue", default="fr", help="Langue des paroles (défaut : fr)")
    parseur.add_argument("--tonalite", default=None,
                         help="Forcer la tonalité (ex: \"C# minor\") — sinon détection auto sur la référence")
    parseur.add_argument("--negatif", default=None,
                         help="Prompt négatif EN — ce qu'on EXCLUT (ex: \"pop, soft, mellow, gentle, ambient, ballad\")")
    parseur.add_argument("--graine", type=int, default=-1)
    parseur.add_argument("-o", "--output", default="inspire_de_ref", help="Nom de sortie (défaut : inspire_de_ref)")
    args = parseur.parse_args()

    if not os.path.exists(args.reference):
        print(f"❌ Introuvable : {args.reference}")
        sys.exit(1)

    print(f"🔍 Analyse de la référence : {args.reference}")
    chemin_wav = convertir_en_wav(args.reference)
    audio, sr = charger_audio(chemin_wav)
    bpm = estimer_bpm(audio, sr)
    if bpm is None:
        print("❌ Aucun tempo détecté dans la référence (audio non pulsatif ?).")
        sys.exit(1)
    bpm = int(round(bpm))
    tonalite = args.tonalite or detecter_tonalite(audio, sr)
    print(f"🧬 ADN détecté : {bpm} BPM • {tonalite} • {len(audio) / sr:.0f} s analysées")

    paroles = "[Instrumental]"
    if args.avec_paroles:
        with open(args.avec_paroles, encoding="utf-8") as f:
            paroles = f.read().strip()

    description = f"{args.style}, {bpm} BPM, {tonalite}, completely instrumental, no vocals"

    sortie = os.path.join("output", "music_chanson", f"{args.output}.wav")
    os.makedirs(os.path.dirname(sortie), exist_ok=True)
    print(f"🎵 Génération : {args.duree:.0f} s • variante {args.variante} • BPM {bpm} et {tonalite} imposés au planner")
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
    print(f"\n🎧 Écoute : {os.path.abspath(mp3)} ({os.path.getsize(mp3) / 1048576:.1f} Mo) — backend {backend}")


if __name__ == "__main__":
    main()
