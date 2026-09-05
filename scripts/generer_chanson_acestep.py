#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génération d'une chanson complète AVEC PAROLES via ACE-Step 1.5 (audio.cpp,
backend Vulkan). Capacité validée le 2026-09-06 (« La Symphonie du Silence »,
« Le Neuvième Fils » — univers Vent-Gris, paroles FR, xl-turbo).

Le fichier de paroles (.txt) peut contenir des balises de structure que le
planner orchestre ([Intro: ...], [Verse], [Chorus], [Bridge], [Outro: ...]).
⚠️ Nettoyer toute citation/annotation (ex. « [2] », notes de bas de page) :
sinon elle est chantée.

Usage :
  uv run python scripts/generer_chanson_acestep.py paroles.txt [options]

Exemple :
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

# Style par défaut : direction musicale validée pour l'univers Vent-Gris
STYLE_DEFAUT = (
    "dark neoclassical folk and gothic orchestral in the style of Wardruna, "
    "haunting low solo cello, sparse metallic prepared piano, slow muffled "
    "heartbeat percussion, dark wooden flute, whispered choir in the "
    "background, deep male vocals, intimate and visceral, French lyrics, "
    "glacial desolate atmosphere, slow tempo, minor key"
)


def main():
    parseur = argparse.ArgumentParser(description="Chanson complète ACE-Step 1.5 (paroles + musique)")
    parseur.add_argument("paroles", help="Fichier .txt des paroles (balises [Verse]/[Chorus]... acceptées)")
    parseur.add_argument("--style", default=STYLE_DEFAUT, help="Description musicale EN (défaut : dark folk Vent-Gris)")
    parseur.add_argument("--duree", type=float, default=180.0, help="Durée cible en secondes (défaut : 180)")
    parseur.add_argument("--variante", choices=list(ACESTEP15_VARIANTES), default="xl-turbo",
                         help="Variante ACE-Step (défaut : xl-turbo — qualité vocale)")
    parseur.add_argument("--langue", default="fr", help="Code langue des paroles (défaut : fr)")
    parseur.add_argument("--etapes", type=int, default=8, help="Pas de diffusion (défaut : 8, turbo distillé)")
    parseur.add_argument("--graine", type=int, default=-1, help="Graine (défaut : aléatoire)")
    parseur.add_argument("-o", "--output", default=None, help="Nom de sortie (défaut : nom du fichier paroles)")
    parseur.add_argument("--backend", default="vulkan", choices=["vulkan", "cpu", "auto"])
    args = parseur.parse_args()

    if not os.path.exists(args.paroles):
        print(f"❌ Fichier introuvable : {args.paroles}")
        sys.exit(1)
    with open(args.paroles, encoding="utf-8") as f:
        paroles = f.read().strip()
    if not paroles:
        print("❌ Fichier de paroles vide.")
        sys.exit(1)

    nom_base = args.output or os.path.splitext(os.path.basename(args.paroles))[0]
    sortie = os.path.join("output", "music_chanson", f"{nom_base}.wav")
    os.makedirs(os.path.dirname(sortie), exist_ok=True)

    nb_lignes = len([l for l in paroles.splitlines() if l.strip() and not l.strip().startswith("[")])
    print(f"🎵 Chanson : {nom_base} • {nb_lignes} lignes chantées • {args.duree:.0f} s • "
          f"variante {args.variante} • langue {args.langue}")
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
    print(f"\n🎧 Écoute : {os.path.abspath(mp3)} ({os.path.getsize(mp3) / 1048576:.1f} Mo) — backend {backend}")


if __name__ == "__main__":
    main()
