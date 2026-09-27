#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/stabiliser_dolly_intro.py — stabilization of the dolly-in (2026-09-10)
The AI camera (LTX-2.5) hesitates: pushes, takes a breath, resumes — perceived as
judders/pullbacks. DETERMINISTIC processing, no regeneration:
  1. Camera trajectory measured: multi-scale NCC tracking of a fixed patch of the keep
     (reference = frame 0) → scale + position per frame (coarse then fine);
  2. Target = moving average made strictly increasing (never a pullback);
  3. Re-render: every frame re-warped (zoom + translation) onto the target, at 1080p;
  4. Outputs: stabilized v4 24 fps + interpolated v4 48 fps (minterpolate mci).
"""
import os
import shutil
import subprocess
import sys

import cv2
import numpy as np

sys.path.insert(0, r"C:\GIT\generator-assets")
from scripts.lancement_nuit_intro_vent_gris import OUTPUT_DIR, FFMPEG, log  # noqa: E402

ES = OUTPUT_DIR
MASTER_V3 = os.path.join(ES, "intro_vent_gris_10s_1080p_v3.mp4")
V4_24 = os.path.join(ES, "intro_vent_gris_10s_1080p_v4_stab.mp4")
V4_48 = os.path.join(ES, "intro_vent_gris_10s_48fps.mp4")

L, H = 640, 360                    # measurement scale
PATCH = (300, 40, 540, 300)        # x0, y0, x1, y1 — the keep at 640×360
GRILLE = np.concatenate([np.arange(0.92, 1.30, 0.02),
                         np.arange(0.90, 1.32, 0.005)])  # coarse then fine


def lire(video: str, largeur: int, hauteur: int):
    cmd = [FFMPEG, "-v", "error", "-i", video, "-vf", f"scale={largeur}:{hauteur}",
           "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    n = len(raw) // (largeur * hauteur)
    return np.frombuffer(raw[:n * largeur * hauteur], dtype=np.uint8).reshape(n, hauteur, largeur)


def moyenne_glissante(x: np.ndarray, fenetre: int = 15) -> np.ndarray:
    noyau = np.ones(fenetre) / fenetre
    borde = np.pad(x, (fenetre // 2, fenetre // 2), mode="edge")
    return np.convolve(borde, noyau, mode="valid")[:len(x)]


def mesurer(trames: np.ndarray):
    """Scale + position of the patch per frame, reference = frame 0 (multi-scale NCC)."""
    px0, py0, px1, py1 = PATCH
    patch = trames[0][py0:py1, px0:px1].astype(np.float32)
    ph, pw = patch.shape
    echelles, positions = [], []
    for t in range(len(trames)):
        frame = trames[t].astype(np.float32)
        candidats = []
        for s in GRILLE:
            dim = (max(int(L / s), pw), max(int(H / s), ph))
            redim = cv2.resize(frame, dim, interpolation=cv2.INTER_AREA)
            res = cv2.matchTemplate(redim, patch, cv2.TM_CCOEFF_NORMED)
            _, score, _, loc = cv2.minMaxLoc(res)
            candidats.append((score, s, loc))
        score, s, (lx, ly) = max(candidats, key=lambda c: c[0])
        echelles.append(s)
        positions.append((lx * s, ly * s))   # patch corner in 640×360 coordinates
        if t % 40 == 0:
            log(f"   frame {t}/{len(trames)}: scale={s:.3f} score={score:.3f}")
    return np.array(echelles), np.array(positions)


def main() -> None:
    log("📖 Measuring the camera trajectory on v3 (480×270, coarse→fine)…")
    trames = lire(MASTER_V3, L, H)
    log(f"   {len(trames)} measurement frames; patch={PATCH}")
    echelles, positions = mesurer(trames)
    reculs = int(np.sum(np.diff(echelles) < -0.002))
    sauts = np.abs(np.diff(echelles))
    log(f"   measured trajectory: start={echelles[0]:.3f} end={echelles[-1]:.3f} | "
        f"pullbacks={reculs} | largest jump={sauts.max():.3f} at frame {int(np.argmax(sauts))+1}")

    # v5: NO measurement in the render (the tracker injected its noise as
    # translation). The warp = pure zoom following the designed ramp, around a
    # fixed anchor = mean position of the keep (640×360). Incapable of shaking
    # by construction; the content animation (waves/clouds/mist) is intact.
    n = len(echelles)
    u = np.linspace(0.0, 1.0, n)
    ease = u * u * u * (u * (u * 6.0 - 15.0) + 10.0)   # smootherstep
    cible = 1.10 + (1.32 - 1.10) * ease                # push-in +20% over 10 s
    pc = np.array([(PATCH[0] + PATCH[2]) / 2, (PATCH[1] + PATCH[3]) / 2])
    ancre = positions.mean(axis=0) + (pc - np.array([PATCH[0], PATCH[1]]))
    log(f"   v5: pure zoom 1.10 → 1.32 around the anchor {ancre.round(1)} (640×360)")

    # 1080p re-render: every frame re-warped onto the target
    log("🎨 Stabilized 1080p re-render…")
    tmp = os.path.join(ES, "temp_stab")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    subprocess.run([FFMPEG, "-y", "-v", "error", "-i", MASTER_V3, "-fps_mode", "passthrough",
                    "-q:v", "2", os.path.join(tmp, "f_%04d.png")], capture_output=True)
    pngs = sorted(f for f in os.listdir(tmp) if f.startswith("f_"))
    fx = 1920.0 / L
    W, HH = 1920, 1080
    for i, nom in enumerate(pngs[:len(echelles)]):
            img = cv2.imread(os.path.join(tmp, nom))
            k = 1.0 / cible[i]                          # pure zoom: the designed ramp
            c = ancre * fx                              # fixed anchor (full resolution)
            tx = c[0] - k * c[0]
            ty = c[1] - k * c[1]
            # clamp into the coverage window → never a black edge
            tx = min(max(tx, min(0.0, W * (1 - k))), max(0.0, W * (1 - k)))
            ty = min(max(ty, min(0.0, HH * (1 - k))), max(0.0, HH * (1 - k)))
            M = np.array([[k, 0.0, tx],
                          [0.0, k, ty]], dtype=np.float64)
            if i in (0, 12, 120):
                log(f"   DEBUG frame {i}: k={k:.4f} tx={tx:.1f} ty={ty:.1f}")
            corr = cv2.warpAffine(img, M, (img.shape[1], img.shape[0]),
                                  flags=cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP)
            sortie = os.path.join(tmp, f"s_{i+1:04d}.png")
            cv2.imwrite(sortie, corr, [cv2.IMWRITE_PNG_COMPRESSION, 3])

    nb_warpees = len([f for f in os.listdir(tmp) if f.startswith("s_")])
    log(f"   {nb_warpees} stabilized frames written (expected {len(echelles)})")
    if nb_warpees != len(echelles):
        log("⛔ unexpected count — temp kept for diagnosis")
        sys.exit(5)

    subprocess.run([FFMPEG, "-y", "-v", "error", "-framerate", "24",
                    "-start_number", "1", "-i", os.path.join(tmp, "s_%04d.png"),
                    "-frames:v", str(len(echelles)),
                    "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", V4_24],
                   capture_output=True)
    nb_out = subprocess.run(
        ["C:/ffmpeg/dist/bin/ffprobe.exe", "-v", "error", "-count_frames",
         "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
         "-of", "csv=p=0", V4_24], capture_output=True, text=True).stdout.strip()
    if nb_out != str(len(echelles)):
        log(f"⛔ incomplete v4 encoding ({nb_out} frames) — temp kept")
        sys.exit(5)
    log(f"✅ stabilized v4 24 fps ({nb_out} frames): {V4_24}")

    # Re-measurement of the obtained trajectory (acceptance criterion: monotonic, no jump)
    t4 = lire(V4_24, L, H)
    e4, _ = mesurer(t4)
    reculs4 = int(np.sum(np.diff(e4) < -0.003))
    log(f"📊 v4 re-measured trajectory: start={e4[0]:.3f} end={e4[-1]:.3f} | "
        f"pullbacks={reculs4} | largest jump={np.abs(np.diff(e4)).max():.3f}")
    print("   curve (1 pt / 10 frames):", " ".join(f"{v:.2f}" for v in e4[::10]))
    subprocess.run([FFMPEG, "-y", "-v", "error", "-i", V4_24,
                    "-vf", "minterpolate=fps=48:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1",
                    "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", V4_48],
                   capture_output=True)
    log(f"✅ interpolated v4 48 fps: {V4_48}")

    cmd = [FFMPEG, "-v", "error", "-i", V4_24, "-vf", "scale=192:108",
           "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    f2 = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 108, 192).astype(np.float32)
    d2 = np.abs(np.diff(f2, axis=0)).mean(axis=(1, 2))
    log(f"📊 v4 profile: mean diff={d2.mean():.2f} max={d2.max():.2f} "
        f"(v3: mean 3.30 / max 21.4; v2: max 6.0 with ghosting)")
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
