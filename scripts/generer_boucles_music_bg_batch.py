#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Resilient batch driver for music_bg loop generation.

Generates the missing candidates one by one (each generation in its own
audiocpp process), resumes where the batch stopped, survives AMD GPU driver
resets (LiveKernelEvent 141) by retrying, then finalizes all the loops via
the fixed algorithm (stable energy zone).

Usage:
  uv run python -u scripts/generer_boucles_music_bg_batch.py [nb_candidats] [engine]
  engine: acestep (default, fast) | music3 (slow, ~25 min/candidate)
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
# 20 s target loop + margin: ACE-Step ends with a long fade-out
# (~4-6 s) → +8 s; Music3 only needs +3 s.
if MOTEUR == "acestep":
    DUREE_GENERATION = 28.0
    ETAPES = 8
else:
    DUREE_GENERATION = 23.0
    ETAPES = 30
PAUSE_ENTRE_CANDIDATS_S = 8.0


def main():
    os.makedirs(DOSSIER_BRUTS, exist_ok=True)
    print(f"🎵 Resilient music_bg batch: {NB_CANDIDATS} candidates, engine {MOTEUR}, "
          f"generation {DUREE_GENERATION:.0f} s, instrumental minimal techno prompt")
    print(f"   Folder: {DOSSIER_BRUTS}")

    reussis, echoues = [], []
    for i in range(1, NB_CANDIDATS + 1):
        chemin = os.path.join(DOSSIER_BRUTS, f"cand_{i}_brut.wav")

        if os.path.exists(chemin) and os.path.getsize(chemin) > 1024 * 1024:
            print(f"✅ cand_{i} already present ({os.path.getsize(chemin) / 1048576:.1f} MB) — resuming")
            reussis.append(chemin)
            continue

        t0 = time.time()
        print(f"\n▶️ Generating cand_{i}/{NB_CANDIDATS} (engine {MOTEUR}, seed {1000 + i})...")
        try:
            # Explicit seed per candidate: guarantees distinct variations
            # (the runtime default seed is deterministic).
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
            print(f"✅ cand_{i} done in {(time.time() - t0) / 60:.1f} min (backend {backend}, "
                  f"{os.path.getsize(chemin_ok) / 1048576:.1f} MB, md5 {empreinte_fichier(chemin_ok)[:8]})")
            reussis.append(chemin_ok)
        except Exception as e:
            print(f"❌ cand_{i} FAILED after all attempts: {e}")
            echoues.append(i)

        time.sleep(PAUSE_ENTRE_CANDIDATS_S)

    print(f"\n{'=' * 60}")
    print(f"Generations: {len(reussis)} succeeded, {len(echoues)} failed {echoues if echoues else ''}")
    if not reussis:
        print("❌ No candidate — aborting.")
        sys.exit(1)

    print("\n🎬 Finalization (stable-zone looping + LUFS bed + MP3)...")
    os.execv(sys.executable, [sys.executable, "-u",
             os.path.join("scripts", "finaliser_boucles_music_bg.py"), DOSSIER])


if __name__ == "__main__":
    main()
