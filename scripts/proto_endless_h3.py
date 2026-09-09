#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 PROTOTYPE EXPÉRIMENTAL — boucle multi-chunks H3 Ref2VA (« endless », façon
ComfyUI-HR-Endless-Sampler, version CLI). NON VALIDÉ : les raccords chunk→chunk
n'ont jamais été jugés à l'œil ; ce script n'est PAS un workflow (règle AGENTS.md :
un workflow n'encapsule que du validé utilisateur — cf. docs/proto_endless_h3.md
pour la procédure complète, les estimations et le critère go/no-go du 1er raccord).

Chaque chunk = un appel au workflow VALIDÉ `h3_ref2va` (recette MEMORY_BANK §1.16) :
la queue du chunk N (12 dernières trames @ 24 fps + WAV appairé, extraite par le
workflow lui-même) devient la référence Ref2VA du chunk N+1. Idempotent : reprend
au premier chunk manquant. Fenêtre temps par défaut 23 h, marge 75 min/chunk,
3 tentatives par chunk espacées de 15 min (absorbe un check_charge refusant parce
que la machine est momentanément occupée). Concatène tout à la fin (-c copy).

Usage (depuis la racine du dépôt, machine LIBRE — cf. check_charge_systeme) :
  uv run python scripts/proto_endless_h3.py --output-dir output/endless_dragon_24h
Options : --source <vidéo initiale> --deadline-min 1380 --chunk-min 75 --max-essais 3
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ancre d'identité : chaque prompt part de la référence <Video 1>/<Audio 1>
PREFIX = ("Use the dragon from <Video 1> and the roar from <Audio 1> as the "
          "opening state. ")

# Storyboard par défaut : 18 chunks ≈ 16 s — progression narrative continue du
# dragon (marche → feu → envol → lac → falaises → grotte → trésor → sommeil).
# Modifiable librement avant lancement (un prompt = un chunk ; garder PREFIX).
STORYBOARD = [
    "The same dragon walks forward on dark stone ground, head low, wings half folded, embers drifting in the air, cinematic lighting.",
    "The same dragon suddenly spreads its massive wings and roars loudly at the camera, dust rising from the ground, dramatic backlight.",
    "The same dragon breathes a jet of orange fire straight toward the camera, flames filling the frame, embers swirling, epic fantasy movie shot.",
    "The fire fades into drifting smoke, the same dragon lowers its head, glowing eyes fixed on the camera, slow embers floating around.",
    "The same dragon takes heavy steps backward, claws scraping the dark stone, tail sweeping dust, muscles tensing under warm torchlight.",
    "The same dragon crouches low, wings folding tight against its body, eyes narrowing, ready to leap, tension building, cinematic low angle.",
    "The same dragon leaps and takes off in an explosion of dust and small stones, powerful wing beats, ground trembling.",
    "The same dragon gains altitude over the dark landscape, huge wings in slow powerful beats, moonlight rim lighting, camera tilting up.",
    "The same dragon flies over a night forest under a full moon, wings casting moving shadows on the treetops, a distant roar echoing.",
    "The same dragon dives steeply toward a dark mountain lake, wind screaming, the water surface rushing closer, reflection of the dragon.",
    "The same dragon skims low over the lake surface, spray exploding in its wake, wing tips almost touching the water, trails of mist.",
    "The same dragon pulls up sharply toward jagged cliffs, wings straining, loose rocks falling into the void, dynamic camera motion.",
    "The same dragon lands heavily on a cliff edge, stones tumbling down the wall, wings folding slowly, mist rolling over the edge.",
    "The same dragon walks slowly into a dark cave entrance, its silhouette backlit by moonlight, eyes glowing in the darkness ahead.",
    "The same dragon moves deeper into the cave, bioluminescent blue crystals lighting the walls, cold reflections on its black scales.",
    "The same dragon curls its body around a pile of ancient gold treasure, smoke rising from its nostrils, guarding posture, warm glints.",
    "The same dragon slowly closes its eyes, its breathing calming down, embers settling on the treasure hoard, dim warm light.",
    "The same dragon sleeps curled around the treasure, slow heavy breathing, thin wisps of smoke, camera slowly pulling back into darkness.",
]


def log(msg: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Prototype endless H3 Ref2VA (non validé)")
    ap.add_argument("--output-dir", required=True, help="dossier des chunks (créé si besoin)")
    ap.add_argument("--source", default=os.path.join(
        "output", "overnight", "esrgan_4k", "01_ltx25_dragon_4k_ultrasharp.mp4"),
        help="vidéo initiale (sa queue référence le chunk 1)")
    ap.add_argument("--deadline-min", type=int, default=1380, help="fenêtre totale en min (défaut 1380 = 23 h)")
    ap.add_argument("--chunk-min", type=int, default=75, help="marge de temps min pour entamer un chunk (défaut 75)")
    ap.add_argument("--max-essais", type=int, default=3, help="tentatives par chunk (défaut 3, délai 15 min)")
    args = ap.parse_args()

    out = os.path.join(REPO, args.output_dir)
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    log(f"Démarrage boucle endless — {len(STORYBOARD)} chunks prévus, fenêtre {args.deadline_min} min")

    for i, suite in enumerate(STORYBOARD, start=1):
        nom = f"chunk_{i:02d}"
        webm = os.path.join(out, f"{nom}.webm")
        if os.path.exists(webm) and os.path.getsize(webm) > 100_000:
            log(f"{nom} déjà présent — skip")
            continue

        reste_min = args.deadline_min - (time.time() - t0) / 60.0
        if reste_min < args.chunk_min:
            log(f"Fenêtre temps insuffisante ({reste_min:.0f} min restantes < {args.chunk_min}) — arrêt avant {nom}")
            break

        src = os.path.join(REPO, args.source) if i == 1 else os.path.join(out, f"chunk_{i-1:02d}.webm")
        if not os.path.exists(src):
            log(f"Source manquante pour {nom} : {src} — arrêt de la boucle")
            break

        succes = False
        for essai in range(1, args.max_essais + 1):
            log(f"=== {nom} ({i}/{len(STORYBOARD)}), essai {essai}/{args.max_essais} — réf : {os.path.basename(src)}")
            debut = time.time()
            cmd = [sys.executable, "main.py", "-w", "h3_ref2va",
                   "-i", src, "-p", PREFIX + suite,
                   "-o", nom, "--output-dir", out, "--seed", "42"]
            r = subprocess.run(cmd, cwd=REPO)
            dt = (time.time() - debut) / 60.0
            if r.returncode == 0 and os.path.exists(webm) and os.path.getsize(webm) > 100_000:
                log(f"✅ {nom} terminé en {dt:.1f} min → {webm}")
                succes = True
                break
            log(f"❌ {nom} échec après {dt:.1f} min (exit {r.returncode})")
            if essai < args.max_essais:
                log("Nouvelle tentative dans 15 min (machine possiblement occupée)...")
                time.sleep(900)
        if not succes:
            log(f"{nom} en échec après {args.max_essais} essais — arrêt de la boucle")
            break

    # Concaténation finale des chunks présents (même encodeur sd-cli → -c copy)
    chunks = sorted(
        f for f in os.listdir(out)
        if f.startswith("chunk_") and f.endswith(".webm") and os.path.getsize(os.path.join(out, f)) > 100_000
    )
    log(f"Boucle terminée : {len(chunks)} chunks valides")
    if len(chunks) >= 2:
        liste = os.path.join(out, "concat_list.txt")
        with open(liste, "w", encoding="utf-8") as f:
            for c in chunks:
                chemin = os.path.join(out, c).replace("\\", "/")
                f.write(f"file '{chemin}'\n")
        final = os.path.join(out, "endless_final.webm")
        rc = subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
             "-i", liste, "-c", "copy", final],
            cwd=REPO
        ).returncode
        if rc == 0 and os.path.exists(final):
            duree = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", final],
                capture_output=True, text=True
            ).stdout.strip()
            log(f"🎬 Vidéo finale : {final} ({len(chunks)} chunks, {duree} s)")
        else:
            log("⚠️ Concat -c copy échouée — re-encoder manuellement : voir concat_list.txt")
    elif len(chunks) == 1:
        log("Un seul chunk — pas de concat nécessaire.")
    else:
        log("Aucun chunk valide produit.")


if __name__ == "__main__":
    main()
