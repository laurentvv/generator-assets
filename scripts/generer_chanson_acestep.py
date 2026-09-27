#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generation of a complete song WITH LYRICS via ACE-Step 1.5 (audio.cpp,
Vulkan backend). Capability validated on 2026-09-06 ("La Symphonie du
Silence", "Le Neuvième Fils" — Grey-Wind universe, FR lyrics, xl-turbo).

The lyrics file (.txt) may contain structure tags that the planner
orchestrates ([Intro: ...], [Verse], [Chorus], [Bridge], [Outro: ...]).
⚠️ Clean out any citation/annotation (e.g. "[2]", footnotes):
otherwise it gets sung.

Usage:
  uv run python scripts/generer_chanson_acestep.py paroles.txt [options]

Example:
  uv run python scripts/generer_chanson_acestep.py paroles.txt \
    --style "minimalist acoustic dark folk ballad, detuned guitar, raspy cello, \
whispered choir, deep weathered male vocals, French lyrics, slow tempo" \
    --duree 240 --variante xl-turbo
"""

import argparse
import os
import sys

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config import ACESTEP15_VARIANTES
from core.music_ai import convertir_mp3, generer_musique_acestep

# Default style: music direction validated for the Grey-Wind universe
STYLE_DEFAUT = (
    "dark neoclassical folk and gothic orchestral in the style of Wardruna, "
    "haunting low solo cello, sparse metallic prepared piano, slow muffled "
    "heartbeat percussion, dark wooden flute, whispered choir in the "
    "background, deep male vocals, intimate and visceral, French lyrics, "
    "glacial desolate atmosphere, slow tempo, minor key"
)


def main():
    parseur = argparse.ArgumentParser(description="Complete ACE-Step 1.5 song (lyrics + music)")
    parseur.add_argument("paroles", help=".txt lyrics file ([Verse]/[Chorus]... tags accepted)")
    parseur.add_argument("--style", default=STYLE_DEFAUT, help="EN music description (default: Grey-Wind dark folk)")
    parseur.add_argument("--duree", type=float, default=180.0, help="Target duration in seconds (default: 180)")
    parseur.add_argument("--variante", choices=list(ACESTEP15_VARIANTES), default="xl-turbo",
                         help="ACE-Step variant (default: xl-turbo — vocal quality)")
    parseur.add_argument("--langue", default="fr", help="Lyrics language code (default: fr)")
    parseur.add_argument("--etapes", type=int, default=8, help="Diffusion steps (default: 8, distilled turbo)")
    parseur.add_argument("--graine", type=int, default=-1, help="Seed (default: random)")
    parseur.add_argument("-o", "--output", default=None, help="Output name (default: lyrics file name)")
    parseur.add_argument("--backend", default="vulkan", choices=["vulkan", "cpu", "auto"])
    args = parseur.parse_args()

    if not os.path.exists(args.paroles):
        print(f"❌ File not found: {args.paroles}")
        sys.exit(1)
    with open(args.paroles, encoding="utf-8") as f:
        paroles = f.read().strip()
    if not paroles:
        print("❌ Empty lyrics file.")
        sys.exit(1)

    nom_base = args.output or os.path.splitext(os.path.basename(args.paroles))[0]
    sortie = os.path.join("output", "music_chanson", f"{nom_base}.wav")
    os.makedirs(os.path.dirname(sortie), exist_ok=True)

    nb_lignes = len([ligne for ligne in paroles.splitlines() if ligne.strip() and not ligne.strip().startswith("[")])
    print(f"🎵 Song: {nom_base} • {nb_lignes} sung lines • {args.duree:.0f} s • "
          f"variant {args.variante} • language {args.langue}")
    chemin, backend = generer_musique_acestep(
        description=args.style,
        chemin_sortie=sortie,
        duree=args.duree,
        etapes=args.etapes,
        backend=args.backend,
        lyrics=paroles,
        variante=args.variante,
        langue=args.langue,
        graine=args.graine,
        log=print,
    )
    mp3 = convertir_mp3(chemin, chemin.replace(".wav", ".mp3"), 224)
    print(f"\n🎧 Listen: {os.path.abspath(mp3)} ({os.path.getsize(mp3) / 1048576:.1f} MB) — backend {backend}")


if __name__ == "__main__":
    main()
