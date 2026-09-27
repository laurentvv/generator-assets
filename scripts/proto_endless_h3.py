#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 EXPERIMENTAL PROTOTYPE — H3 Ref2VA multi-chunk loop ("endless", in the vein of
ComfyUI-HR-Endless-Sampler, CLI version). NOT VALIDATED: the chunk→chunk joints
have never been judged by eye; this script is NOT a workflow (AGENTS.md rule:
a workflow only encapsulates user-validated things — see docs/proto_endless_h3.md
for the full procedure, the estimates and the go/no-go criterion of the 1st joint).

Each chunk = one call to the VALIDATED `h3_ref2va` workflow in `--turbo` mode
(distilled 8-step LoRA, user-validated on 2026-09-09 — ~38 min/chunk instead of ~70,
reference joint ≥ baseline; MEMORY_BANK §1.16). The reference of each chunk is
pre-extracted HERE (the workflow receives a frame folder + `--ref-audio`) with 3
levers from the ComfyUI research report (defaults = validated recipe §1.16):
  • --ref-audio-sec: audio window that ENDS at the joint and "reaches back" into
    the already-played sound (ComfyUI-H3-Motion-Context lesson: the model continues
    the track instead of writing something that sounds alike). The window is cut from
    the complete audio TIMELINE (source + already generated chunks), not from the
    previous chunk alone. Default 0.5 s = validated recipe; probe 4-6 s for the A/B.
  • --ref-frames: tail frames extracted from the previous chunk. ⚠️ sd-cli truncates
    the folder to the 17k+5 grid and only encodes the FIRST 5 frames (12 → 5,
    = frames -12..-8, which do not touch the joint). --ref-frames 5 puts the 5
    encoded frames EXACTLY on the joint and divides the ref VAE encoding by ~2.4
    (maximal joint probe, not validated). Default 12 = validated recipe.
  • --ref-scale: downscale of the ref frames (32 px aligned, CLI equivalent of
    `video_continuation_res`). Only has an effect IF the result goes below sd-cli's
    internal nominal size (768×432 in 16:9 — e.g. 3840×2160 × 0.15 → 576×320);
    above, sd-cli upscales back to nominal. Default 1.0 = validated recipe.
Idempotent: resumes at the first missing chunk. Default time window 23 h,
50 min margin/chunk, 3 attempts per chunk 15 min apart (absorbs a
check_charge refusal because the machine is momentarily busy).
Concatenates everything at the end (-c copy).

Usage (from the repo root, FREE machine — see check_charge_systeme):
  uv run python scripts/proto_endless_h3.py --output-dir output/endless_dragon_24h
Recommended joint probe (~1 h 15, judge chunk_01→chunk_02 before launching everything):
  uv run python scripts/proto_endless_h3.py --output-dir output/endless_sonde \
      --deadline-min 100
Options: --source <initial video> --deadline-min 1380 --chunk-min 50 --max-essais 3
         --ref-frames 12 --ref-audio-sec 0.5 --ref-scale 1.0
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Identity anchor: each prompt starts from the <Video 1> reference (+ <Audio 1>
# only if a reference WAV is available for that chunk).
PREFIX_VIDEO = "Use the dragon from <Video 1>"
PREFIX_AUDIO = " and the roar from <Audio 1>"
PREFIX_SUFFIX = " as the opening state. "

# Default storyboard: 18 chunks ≈ 16 s of video (~11.5 h of rendering in turbo,
# ~21 h with the base recipe) — continuous narrative progression of the dragon
# (walk → fire → takeoff → lake → cliffs → cave → treasure → sleep).
# Freely editable before launch (one prompt = one chunk; keep the prefix).
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
    """Extracts the tail of the source into 24 fps PNG frames (± 32-aligned downscale).

    Re-extracts at every call (a few seconds): guarantees that the frames
    ALWAYS match the current --ref-frames/--ref-scale, even after a
    parameter change between two resumptions of the loop.
    """
    os.makedirs(ref_dir, exist_ok=True)
    for vieux in [f for f in os.listdir(ref_dir) if f.endswith(".png")]:
        os.remove(os.path.join(ref_dir, vieux))
    duree = duree_media(source)
    if duree <= 0:
        log(f"⚠️ Unreadable duration for {source} — video ref impossible")
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
    """Normalizes an audio track into 32 kHz stereo PCM (building block of the timeline)."""
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
    """Cuts the LAST `fenetre_s` seconds of the timeline (end = joint)."""
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
    """Prepares (frames + WAV) the Ref2VA reference of chunk `idx`.

    Returns (ref_frames_dir, ref_wav or None) — both as absolute paths.
    """
    ref_dir = os.path.join(out, "refs", f"ref_{idx:02d}")
    if not extraire_trames_ref(source, ref_dir, args.ref_frames, args.ref_scale):
        return (None, None)

    ref_wav = None
    pieces_valides = [p for p in pieces_audio if os.path.exists(p)]
    if pieces_valides and args.ref_audio_sec > 0.01:
        # Timeline = concat of the normalized tracks (source + already generated chunks)
        timeline = os.path.join(out, "refs", "timeline_audio.wav")
        liste = os.path.join(out, "refs", "timeline_list.txt")
        with open(liste, "w", encoding="utf-8") as f:
            for p in pieces_valides:
                # ABSOLUTE paths: ffmpeg resolves the list relative to itself
                f.write(f"file '{os.path.abspath(p).replace(os.sep, '/')}'\n")
        if lancer([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0",
                   "-i", liste, "-c", "copy", timeline]):
            ref_wav = os.path.join(ref_dir, "ref_audio.wav")
            if not couper_fenetre_audio(timeline, ref_wav, args.ref_audio_sec):
                ref_wav = None
    return (ref_dir, ref_wav)


def main() -> None:
    ap = argparse.ArgumentParser(description="Endless H3 Ref2VA prototype (not validated)")
    ap.add_argument("--output-dir", required=True, help="chunk folder (created if needed)")
    ap.add_argument("--source", default=os.path.join(
        "output", "overnight", "esrgan_4k", "01_ltx25_dragon_4k_ultrasharp.mp4"),
        help="initial video (its tail seeds chunk 1)")
    ap.add_argument("--deadline-min", type=int, default=1380, help="total window in min (default 1380 = 23 h)")
    ap.add_argument("--chunk-min", type=int, default=50, help="min time margin to start a chunk (default 50 = turbo chunk ~38 min + margin)")
    ap.add_argument("--max-essais", type=int, default=3, help="attempts per chunk (default 3, 15 min delay)")
    ap.add_argument("--ref-frames", type=int, default=12,
                    help="tail frames extracted as video ref (default 12 = validated recipe; 5 = maximal joint, not validated)")
    ap.add_argument("--ref-audio-sec", type=float, default=0.5,
                    help="reference audio window ending at the joint, cut from the timeline (default 0.5 = validated recipe; 4-6 = Motion-Context lesson, not validated)")
    ap.add_argument("--ref-scale", type=float, default=1.0,
                    help="downscale of the ref frames, factor on the source aligned 32 px (default 1.0; active only if the result goes below the sd-cli nominal size 768×432 — e.g. 0.15 on 4K → 576×320, 0.85 on 864-wide → 736×416; not validated)")
    args = ap.parse_args()

    out = os.path.join(REPO, args.output_dir)
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    log(f"Starting the endless loop — {len(STORYBOARD)} chunks planned, window {args.deadline_min} min "
        f"(ref: {args.ref_frames} frames, audio {args.ref_audio_sec}s, scale {args.ref_scale})")

    source_abs = os.path.join(REPO, args.source) if not os.path.isabs(args.source) else args.source
    if not os.path.exists(source_abs):
        log(f"Missing initial source: {source_abs} — stopping")
        return
    pieces_audio = []  # normalized tracks (source then chunks) of the timeline
    piece_source = os.path.join(out, "refs", "audio_piece_00.wav")
    if extraire_piece_audio(source_abs, piece_source):
        pieces_audio.append(piece_source)
    else:
        log("Source without usable audio — chunks generated without <Audio 1>.")

    for i, suite in enumerate(STORYBOARD, start=1):
        nom = f"chunk_{i:02d}"
        webm = os.path.join(out, f"{nom}.webm")
        if os.path.exists(webm) and os.path.getsize(webm) > 100_000:
            log(f"{nom} already present — skip")
            piece = os.path.join(out, "refs", f"audio_piece_{i:02d}.wav")
            if extraire_piece_audio(webm, piece):
                if len(pieces_audio) < i + 1:
                    pieces_audio.append(piece)
            continue

        reste_min = args.deadline_min - (time.time() - t0) / 60.0
        if reste_min < args.chunk_min:
            log(f"Insufficient time window ({reste_min:.0f} min left < {args.chunk_min}) — stopping before {nom}")
            break

        src = source_abs if i == 1 else os.path.join(out, f"chunk_{i-1:02d}.webm")
        if not os.path.exists(src):
            log(f"Missing source for {nom}: {src} — stopping the loop")
            break

        ref_dir, ref_wav = preparer_reference(i, src, pieces_audio, out, args)
        if not ref_dir:
            log(f"⚠️ Unable to prepare the video reference of {nom} — stopping the loop")
            break
        prefix = PREFIX_VIDEO + (PREFIX_AUDIO if ref_wav else "") + PREFIX_SUFFIX
        if ref_wav:
            log(f"{nom}: ref {args.ref_frames} frames + audio {args.ref_audio_sec}s (window ending at the joint)")
        else:
            log(f"{nom}: ref {args.ref_frames} frames (no audio)")

        succes = False
        for essai in range(1, args.max_essais + 1):
            log(f"=== {nom} ({i}/{len(STORYBOARD)}), attempt {essai}/{args.max_essais} — ref: {os.path.basename(src)}")
            debut = time.time()
            cmd = [sys.executable, "main.py", "-w", "h3_ref2va",
                   "-i", ref_dir, "-p", prefix + suite,
                   "-o", nom, "--output-dir", out, "--seed", "42", "--turbo"]
            if ref_wav:
                cmd.extend(["--ref-audio", ref_wav])
            r = subprocess.run(cmd, cwd=REPO)
            dt = (time.time() - debut) / 60.0
            if r.returncode == 0 and os.path.exists(webm) and os.path.getsize(webm) > 100_000:
                log(f"✅ {nom} done in {dt:.1f} min → {webm}")
                piece = os.path.join(out, "refs", f"audio_piece_{i:02d}.wav")
                if extraire_piece_audio(webm, piece):
                    pieces_audio.append(piece)
                succes = True
                break
            log(f"❌ {nom} failed after {dt:.1f} min (exit {r.returncode})")
            if essai < args.max_essais:
                log("New attempt in 15 min (machine possibly busy)...")
                time.sleep(900)
        if not succes:
            log(f"{nom} failed after {args.max_essais} attempts — stopping the loop")
            break

    # Final concatenation of the present chunks (same sd-cli encoder → -c copy)
    chunks = sorted(
        f for f in os.listdir(out)
        if f.startswith("chunk_") and f.endswith(".webm") and os.path.getsize(os.path.join(out, f)) > 100_000
    )
    log(f"Loop finished: {len(chunks)} valid chunks")
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
            log(f"🎬 Final video: {final} ({len(chunks)} chunks, {duree} s)")
        else:
            log("⚠️ Concat -c copy failed — re-encode manually: see concat_list.txt")
    elif len(chunks) == 1:
        log("Only one chunk — no concat needed.")
    else:
        log("No valid chunk produced.")


if __name__ == "__main__":
    main()
