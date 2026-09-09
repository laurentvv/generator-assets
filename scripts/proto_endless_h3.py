#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 PROTOTYPE EXPÉRIMENTAL — boucle multi-chunks H3 Ref2VA (« endless », façon
ComfyUI-HR-Endless-Sampler, version CLI). NON VALIDÉ : les raccords chunk→chunk
n'ont jamais été jugés à l'œil ; ce script n'est PAS un workflow (règle AGENTS.md :
un workflow n'encapsule que du validé utilisateur — cf. docs/proto_endless_h3.md
pour la procédure complète, les estimations et le critère go/no-go du 1er raccord).

Chaque chunk = un appel au workflow VALIDÉ `h3_ref2va` en mode `--turbo` (LoRA
distillé 8 steps, validé utilisateur le 2026-09-09 — ~38 min/chunk au lieu de ~70,
raccord référence ≥ baseline ; MEMORY_BANK §1.16). La référence de chaque chunk est
pré-extraite ICI (le workflow reçoit un dossier de trames + `--ref-audio`) avec 3
leviers du rapport de recherche ComfyUI (défauts = recette validée §1.16) :
  • --ref-audio-sec : fenêtre audio qui SE TERMINe au raccord et « remonte » dans
    le son déjà joué (leçon ComfyUI-H3-Motion-Context : le modèle continue la piste
    au lieu d'écrire quelque chose qui ressemble). La fenêtre est découpée dans la
    TIMELINE audio complète (source + chunks déjà générés), pas dans le seul chunk
    précédent. Défaut 0,5 s = recette validée ; sonder 4-6 s pour l'A/B.
  • --ref-frames : trames de queue extraites du chunk précédent. ⚠️ sd-cli tronque
    le dossier à la grille 17k+5 et n'encode que les 5 PREMIÈRES trames (12 → 5,
    = trames -12..-8, qui ne touchent pas le raccord). --ref-frames 5 met les 5
    trames encodées EXACTEMENT sur le raccord et divise l'encodage VAE réf par ~2,4
    (sonde de raccord maximal, non validé). Défaut 12 = recette validée.
  • --ref-scale : downscale des trames réf (aligné 32 px, équivalent CLI de
    `video_continuation_res`). N'a d'effet QUE si le résultat passe sous la taille
    nominale interne de sd-cli (768×432 en 16:9 — ex. 3840×2160 × 0,15 → 576×320) ;
    au-dessus, sd-cli re-agrandit vers la nominale. Défaut 1.0 = recette validée.
Idempotent : reprend au premier chunk manquant. Fenêtre temps par défaut 23 h,
marge 50 min/chunk, 3 tentatives par chunk espacées de 15 min (absorbe un
check_charge refusant parce que la machine est momentanément occupée).
Concatène tout à la fin (-c copy).

Usage (depuis la racine du dépôt, machine LIBRE — cf. check_charge_systeme) :
  uv run python scripts/proto_endless_h3.py --output-dir output/endless_dragon_24h
Sonde raccord recommandée (~1 h 15, juger chunk_01→chunk_02 avant de tout lancer) :
  uv run python scripts/proto_endless_h3.py --output-dir output/endless_sonde \
      --deadline-min 100
Options : --source <vidéo initiale> --deadline-min 1380 --chunk-min 50 --max-essais 3
          --ref-frames 12 --ref-audio-sec 0.5 --ref-scale 1.0
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ancre d'identité : chaque prompt part de la référence <Video 1> (+ <Audio 1>
# seulement si un WAV de référence est disponible pour ce chunk).
PREFIX_VIDEO = "Use the dragon from <Video 1>"
PREFIX_AUDIO = " and the roar from <Audio 1>"
PREFIX_SUFFIX = " as the opening state. "

# Storyboard par défaut : 18 chunks ≈ 16 s de vidéo (~11,5 h de rendu en turbo,
# ~21 h en recette de base) — progression narrative continue du dragon
# (marche → feu → envol → lac → falaises → grotte → trésor → sommeil).
# Modifiable librement avant lancement (un prompt = un chunk ; garder le prefix).
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

FFMPEG = "ffmpeg"


def log(msg: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def lancer(cmd: list, **kw) -> bool:
    r = subprocess.run(cmd, **kw)
    return r.returncode == 0


def duree_media(chemin: str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", chemin],
        capture_output=True, text=True
    )
    try:
        return float(r.stdout.strip())
    except (ValueError, TypeError):
        return 0.0


def a_audio(chemin: str) -> bool:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", chemin],
        capture_output=True, text=True
    )
    return r.returncode == 0 and bool(r.stdout.strip())


def extraire_trames_ref(source: str, ref_dir: str, n_frames: int, echelle: float) -> bool:
    """Extrait la queue de la source en trames PNG 24 fps (± downscale aligné 32).

    Ré-extrait à chaque appel (quelques secondes) : garantit que les trames
    correspondent TOUJOURS aux --ref-frames/--ref-scale courants, même après un
    changement de paramètres entre deux reprises de la boucle.
    """
    os.makedirs(ref_dir, exist_ok=True)
    for vieux in [f for f in os.listdir(ref_dir) if f.endswith(".png")]:
        os.remove(os.path.join(ref_dir, vieux))
    duree = duree_media(source)
    if duree <= 0:
        log(f"⚠️ Durée illisible pour {source} — réf vidéo impossible")
        return False
    fenetre = n_frames / 24.0
    start = max(0.0, duree - fenetre)
    vf = "fps=24"
    if echelle < 0.999:
        vf += (f",scale=trunc(iw*{echelle:.4f}/32)*32:trunc(ih*{echelle:.4f}/32)*32")
    return lancer([
        FFMPEG, "-y", "-v", "error",
        "-ss", f"{start:.3f}", "-i", source, "-t", f"{fenetre:.3f}",
        "-vf", vf, "-frames:v", str(n_frames),
        os.path.join(ref_dir, "frame_%04d.png")
    ])


def extraire_piece_audio(source: str, piece: str) -> bool:
    """Normalise une piste audio en PCM 32 kHz stéréo (brique de la timeline)."""
    if os.path.exists(piece) and os.path.getsize(piece) > 1000:
        return True
    if not a_audio(source):
        return False
    os.makedirs(os.path.dirname(piece), exist_ok=True)
    return lancer([
        FFMPEG, "-y", "-v", "error", "-i", source, "-vn",
        "-ar", "32000", "-ac", "2", "-c:a", "pcm_s16le", piece
    ])


def couper_fenetre_audio(timeline: str, wav_ref: str, fenetre_s: float) -> bool:
    """Découpe les DERNIÈRES `fenetre_s` secondes de la timeline (fin = raccord)."""
    duree = duree_media(timeline)
    if duree <= 0:
        return False
    start = max(0.0, duree - fenetre_s)
    return lancer([
        FFMPEG, "-y", "-v", "error",
        "-ss", f"{start:.3f}", "-i", timeline, "-t", f"{fenetre_s:.3f}",
        "-c:a", "pcm_s16le", wav_ref
    ])


def preparer_reference(idx: int, source: str, pieces_audio: list, out: str,
                       args) -> tuple:
    """Prépare (trames + WAV) la référence Ref2VA du chunk `idx`.

    Retourne (ref_frames_dir, ref_wav ou None) — les deux en chemins absolus.
    """
    ref_dir = os.path.join(out, "refs", f"ref_{idx:02d}")
    if not extraire_trames_ref(source, ref_dir, args.ref_frames, args.ref_scale):
        return (None, None)

    ref_wav = None
    pieces_valides = [p for p in pieces_audio if os.path.exists(p)]
    if pieces_valides and args.ref_audio_sec > 0.01:
        # Timeline = concat des pistes normalisées (source + chunks déjà générés)
        timeline = os.path.join(out, "refs", "timeline_audio.wav")
        liste = os.path.join(out, "refs", "timeline_list.txt")
        with open(liste, "w", encoding="utf-8") as f:
            for p in pieces_valides:
                # chemins ABSOLUS : ffmpeg résout la liste relativement à elle-même
                f.write(f"file '{os.path.abspath(p).replace(os.sep, '/')}'\n")
        if lancer([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0",
                   "-i", liste, "-c", "copy", timeline]):
            ref_wav = os.path.join(ref_dir, "ref_audio.wav")
            if not couper_fenetre_audio(timeline, ref_wav, args.ref_audio_sec):
                ref_wav = None
    return (ref_dir, ref_wav)


def main() -> None:
    ap = argparse.ArgumentParser(description="Prototype endless H3 Ref2VA (non validé)")
    ap.add_argument("--output-dir", required=True, help="dossier des chunks (créé si besoin)")
    ap.add_argument("--source", default=os.path.join(
        "output", "overnight", "esrgan_4k", "01_ltx25_dragon_4k_ultrasharp.mp4"),
        help="vidéo initiale (sa queue référence le chunk 1)")
    ap.add_argument("--deadline-min", type=int, default=1380, help="fenêtre totale en min (défaut 1380 = 23 h)")
    ap.add_argument("--chunk-min", type=int, default=50, help="marge de temps min pour entamer un chunk (défaut 50 = chunk turbo ~38 min + marge)")
    ap.add_argument("--max-essais", type=int, default=3, help="tentatives par chunk (défaut 3, délai 15 min)")
    ap.add_argument("--ref-frames", type=int, default=12,
                    help="trames de queue extraites comme réf vidéo (défaut 12 = recette validée ; 5 = raccord maximal, non validé)")
    ap.add_argument("--ref-audio-sec", type=float, default=0.5,
                    help="fenêtre audio de référence finissant au raccord, découpée dans la timeline (défaut 0.5 = recette validée ; 4-6 = leçon Motion-Context, non validé)")
    ap.add_argument("--ref-scale", type=float, default=1.0,
                    help="downscale des trames réf, facteur sur la source aligné 32 px (défaut 1.0 ; actif seulement si le résultat passe sous la taille nominale sd-cli 768×432 — ex. 0.15 sur du 4K → 576×320, 0.85 sur du 864-wide → 736×416 ; non validé)")
    args = ap.parse_args()

    out = os.path.join(REPO, args.output_dir)
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    log(f"Démarrage boucle endless — {len(STORYBOARD)} chunks prévus, fenêtre {args.deadline_min} min "
        f"(réf : {args.ref_frames} trames, audio {args.ref_audio_sec}s, échelle {args.ref_scale})")

    source_abs = os.path.join(REPO, args.source) if not os.path.isabs(args.source) else args.source
    if not os.path.exists(source_abs):
        log(f"Source initiale manquante : {source_abs} — arrêt")
        return
    pieces_audio = []  # pistes normalisées (source puis chunks) de la timeline
    piece_source = os.path.join(out, "refs", "audio_piece_00.wav")
    if extraire_piece_audio(source_abs, piece_source):
        pieces_audio.append(piece_source)
    else:
        log("Source sans audio exploitable — chunks générés sans <Audio 1>.")

    for i, suite in enumerate(STORYBOARD, start=1):
        nom = f"chunk_{i:02d}"
        webm = os.path.join(out, f"{nom}.webm")
        if os.path.exists(webm) and os.path.getsize(webm) > 100_000:
            log(f"{nom} déjà présent — skip")
            piece = os.path.join(out, "refs", f"audio_piece_{i:02d}.wav")
            if extraire_piece_audio(webm, piece):
                if len(pieces_audio) < i + 1:
                    pieces_audio.append(piece)
            continue

        reste_min = args.deadline_min - (time.time() - t0) / 60.0
        if reste_min < args.chunk_min:
            log(f"Fenêtre temps insuffisante ({reste_min:.0f} min restantes < {args.chunk_min}) — arrêt avant {nom}")
            break

        src = source_abs if i == 1 else os.path.join(out, f"chunk_{i-1:02d}.webm")
        if not os.path.exists(src):
            log(f"Source manquante pour {nom} : {src} — arrêt de la boucle")
            break

        ref_dir, ref_wav = preparer_reference(i, src, pieces_audio, out, args)
        if not ref_dir:
            log(f"⚠️ Impossible de préparer la référence vidéo de {nom} — arrêt de la boucle")
            break
        prefix = PREFIX_VIDEO + (PREFIX_AUDIO if ref_wav else "") + PREFIX_SUFFIX
        if ref_wav:
            log(f"{nom} : réf {args.ref_frames} trames + audio {args.ref_audio_sec}s (fenêtre finissant au raccord)")
        else:
            log(f"{nom} : réf {args.ref_frames} trames (sans audio)")

        succes = False
        for essai in range(1, args.max_essais + 1):
            log(f"=== {nom} ({i}/{len(STORYBOARD)}), essai {essai}/{args.max_essais} — réf : {os.path.basename(src)}")
            debut = time.time()
            cmd = [sys.executable, "main.py", "-w", "h3_ref2va",
                   "-i", ref_dir, "-p", prefix + suite,
                   "-o", nom, "--output-dir", out, "--seed", "42", "--turbo"]
            if ref_wav:
                cmd.extend(["--ref-audio", ref_wav])
            r = subprocess.run(cmd, cwd=REPO)
            dt = (time.time() - debut) / 60.0
            if r.returncode == 0 and os.path.exists(webm) and os.path.getsize(webm) > 100_000:
                log(f"✅ {nom} terminé en {dt:.1f} min → {webm}")
                piece = os.path.join(out, "refs", f"audio_piece_{i:02d}.wav")
                if extraire_piece_audio(webm, piece):
                    pieces_audio.append(piece)
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
            [FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0",
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
