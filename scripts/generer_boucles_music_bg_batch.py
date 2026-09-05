#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pilote de batch résilient pour la génération des boucles music_bg.

Génère les candidats manquants un par un (chaque génération dans son propre
processus audiocpp), reprend là où le batch s'est arrêté, survit aux resets
du pilote GPU AMD (LiveKernelEvent 141) en réessayant, puis finalise toutes
les boucles via l'algorithme corrigé (zone d'énergie stable).

Usage :
  uv run python -u scripts/generer_boucles_music_bg_batch.py [nb_candidats] [moteur]
  moteur : acestep (défaut, rapide) | music3 (lent, ~25 min/candidat)
"""

import os
import sys
import time

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.music_ai import generer_musique_acestep, generer_musique_music3, empreinte_fichier

NB_CANDIDATS = int(sys.argv[1]) if len(sys.argv) > 1 else 10
MOTEUR = sys.argv[2] if len(sys.argv) > 2 else "acestep"
DOSSIER = os.path.join("output", "music_bg")
DOSSIER_BRUTS = os.path.join(DOSSIER, "candidats")

PROMPT = (
    "subtle minimal techno groove, soft pulsing analog synth bass, muffled kick, "
    "airy hi-hats, clean dark pads, instrumental only, steady understated momentum, no vocals"
)
# 20 s de boucle visée + marge : ACE-Step termine par un long fondu de sortie
# (~4-6 s) → +8 s ; Music3 se contente de +3 s.
if MOTEUR == "acestep":
    DUREE_GENERATION = 28.0
    ETAPES = 8
else:
    DUREE_GENERATION = 23.0
    ETAPES = 30
PAUSE_ENTRE_CANDIDATS_S = 8.0


def main():
    os.makedirs(DOSSIER_BRUTS, exist_ok=True)
    print(f"🎵 Batch résilient music_bg : {NB_CANDIDATS} candidats, moteur {MOTEUR}, "
          f"génération {DUREE_GENERATION:.0f} s, prompt minimal techno instrumental")
    print(f"   Dossier : {DOSSIER_BRUTS}")

    reussis, echoues = [], []
    for i in range(1, NB_CANDIDATS + 1):
        chemin = os.path.join(DOSSIER_BRUTS, f"cand_{i}_brut.wav")

        if os.path.exists(chemin) and os.path.getsize(chemin) > 1024 * 1024:
            print(f"✅ cand_{i} déjà présent ({os.path.getsize(chemin) / 1048576:.1f} Mo) — reprise")
            reussis.append(chemin)
            continue

        t0 = time.time()
        print(f"\n▶️ Génération cand_{i}/{NB_CANDIDATS} (moteur {MOTEUR}, graine {1000 + i})...")
        try:
            # Graine explicite par candidat : garantit des variations distinctes
            # (le seed par défaut du runtime est déterministe).
            generateur = generer_musique_acestep if MOTEUR == "acestep" else generer_musique_music3
            chemin_ok, backend = generateur(
                description=PROMPT,
                chemin_sortie=chemin,
                duree=DUREE_GENERATION,
                etapes=ETAPES,
                backend="vulkan",
                lyrics="[Instrumental]",
                graine=1000 + i,
                log=print,
            )
            print(f"✅ cand_{i} terminé en {(time.time() - t0) / 60:.1f} min (backend {backend}, "
                  f"{os.path.getsize(chemin_ok) / 1048576:.1f} Mo, md5 {empreinte_fichier(chemin_ok)[:8]})")
            reussis.append(chemin_ok)
        except Exception as e:
            print(f"❌ cand_{i} ÉCHOUÉ après tous les essais : {e}")
            echoues.append(i)

        time.sleep(PAUSE_ENTRE_CANDIDATS_S)

    print(f"\n{'=' * 60}")
    print(f"Générations : {len(reussis)} réussie(s), {len(echoues)} échouée(s) {echoues if echoues else ''}")
    if not reussis:
        print("❌ Aucun candidat — abandon.")
        sys.exit(1)

    print("\n🎬 Finalisation (bouclage zone stable + bed LUFS + MP3)...")
    os.execv(sys.executable, [sys.executable, "-u",
             os.path.join("scripts", "finaliser_boucles_music_bg.py"), DOSSIER])


if __name__ == "__main__":
    main()
