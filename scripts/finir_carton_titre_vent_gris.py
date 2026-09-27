#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/finir_carton_titre_vent_gris.py — title card "L'HÉRITIER DU VIDE"
at the end of the Grey-Wind intro (2026-09-10).

Chain: last frame of the 48 fps v6 frozen → pure zoom that CONTINUES the
dolly-in (1.32→1.36, smootherstep) + animated couture title (fade + stagger
wave + letter-spacing 0.12→0.22 em + ornament, 6 s @ 48 fps) → SA3 ambience
extended over the total duration (2.5 s fade-out) → assembly in a single
pass. See core/cinema.py ("carton de titre haute couture" block).

Resumable: each step is skipped if its deliverable already exists.
"""

import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.cinema import (  # noqa: E402
    FFMPEG_PATH,
    _duree_media,
    assembler_finale,
    construire_carton_titre,
    etendre_ambiance,
    extraire_derniere_trame,
    rendre_titre_beau,
)

ES = os.path.join("output", "intro_vent_gris")
BASE = os.path.join(ES, "intro_vent_gris_10s_v6_48fps.mp4")
AMBIANCE = os.path.join(ES, "ambiance_tempete_vent_gris.wav")
TRAME = os.path.join(ES, "intro_vent_gris_v6_derniere_trame.png")
CARTON = os.path.join(ES, "intro_vent_gris_v6_carton.mp4")
FINAL = os.path.join(ES, "intro_vent_gris_final_titre.mp4")
AMB_ETENDUE = os.path.join(ES, "ambiance_tempete_vent_gris_etendue.wav")

LIGNES = ["L'HÉRITIER", "DU VIDE"]
POLICE_MAIN = r"C:\Windows\Fonts\FELIXTI.TTF"   # Felix Titling (inscriptional capitals)
POLICE_ALT = r"C:\Windows\Fonts\CENTAUR.TTF"    # Centaur (Renaissance, QA comparison)
DUREE_CARTON = 6.0
FPS = 48
FONDU_SORTIE_AMBIANCE = 2.5
INSTANTS_QA = (1.0, 2.0, 3.0, 5.0)  # snapshots of the revelation


def log(message):
    print(message, flush=True)


def planche_carton():
    """Snapshots of the animated card (t = 1/2/3/5 s) + 2×2 contact sheet for visual QA."""
    vignettes = []
    for t in INSTANTS_QA:
        chemin = os.path.join(ES, f"qa_carton_t{t:.0f}s.png")
        subprocess.run(
            [FFMPEG_PATH, "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", CARTON,
             "-frames:v", "1", "-q:v", "2", chemin],
            capture_output=True, check=True)
        vignettes.append((t, chemin))
    from PIL import Image
    cases = [Image.open(c).resize((960, 540), Image.Resampling.LANCZOS) for _, c in vignettes]
    planche = Image.new("RGB", (1920, 1080))
    for i, case in enumerate(cases):
        planche.paste(case, ((i % 2) * 960, (i // 2) * 540))
    sortie = os.path.join(ES, "qa_carton_planche.png")
    planche.save(sortie, quality=100)
    log(f"   QA contact sheet: {os.path.basename(sortie)} (t = " +
        "/".join(f"{t:.0f}s" for t, _ in vignettes) + ")")


def main():
    t0 = time.time()
    for chemin in (BASE, AMBIANCE):
        if not os.path.exists(chemin):
            raise FileNotFoundError(chemin)

    # 1. last frame of the v6 (card seed)
    if os.path.exists(TRAME):
        log(f"⏭️ 1. frame already extracted: {os.path.basename(TRAME)}")
    else:
        extraire_derniere_trame(BASE, TRAME)
        log(f"✅ 1. last frame extracted: {os.path.basename(TRAME)}")

    # 2. QA stills of both fonts (judge the typography without a video render)
    for nom, police in (("qa_titre_felix.png", POLICE_MAIN),
                        ("qa_titre_centaur.png", POLICE_ALT)):
        chemin = os.path.join(ES, nom)
        if os.path.exists(chemin):
            log(f"⏭️ 2. QA still already present: {nom}")
        else:
            rendre_titre_beau(TRAME, LIGNES, chemin, police)
            log(f"✅ 2. QA still: {nom}")

    # 3. animated card (288 frames @ 48 fps)
    if os.path.exists(CARTON):
        log(f"⏭️ 3. card already present: {os.path.basename(CARTON)}")
    else:
        log("🎬 3. composing the card (zoom 1.32→1.36 + couture title)…")
        construire_carton_titre(
            TRAME, LIGNES, CARTON,
            duree=DUREE_CARTON, fps=FPS,
            zoom_abs_debut=1.32, zoom_abs_fin=1.36,
            chemin_police=POLICE_MAIN, log_fn=log)
        log(f"✅ 3. card: {os.path.basename(CARTON)}")
    if not os.path.exists(os.path.join(ES, "qa_carton_planche.png")):
        planche_carton()

    # 4. extended ambience + final assembly (single pass)
    if os.path.exists(FINAL):
        log(f"⏭️ 4. final already present: {os.path.basename(FINAL)}")
    else:
        duree_base = _duree_media(BASE)
        totale = duree_base + DUREE_CARTON
        log(f"🎞️ 4. assembly: base {duree_base:.2f} s + card {DUREE_CARTON:.1f} s "
            f"= {totale:.2f} s")
        if os.path.exists(AMB_ETENDUE):
            log(f"⏭️    extended ambience already present: {os.path.basename(AMB_ETENDUE)}")
        else:
            etendre_ambiance(AMBIANCE, totale, AMB_ETENDUE, fondu_sortie=FONDU_SORTIE_AMBIANCE)
            log(f"✅    extended ambience ({totale:.2f} s, fade {FONDU_SORTIE_AMBIANCE} s)")
        assembler_finale(BASE, CARTON, AMB_ETENDUE, FINAL, fps=FPS)
        log(f"✅ 4. finale : {os.path.basename(FINAL)}")

    log(f"🎉 Done in {(time.time() - t0) / 60:.1f} min — deliverables in {ES}:")
    for chemin in (CARTON, FINAL):
        log(f"   • {os.path.basename(chemin)}")


if __name__ == "__main__":
    main()
