#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/faire_boucle_menu_vent_gris.py — background of the « L'HÉRITIER DU VIDE » menu:
ultra-light AI cinemagraph in a perfect infinite loop, locked camera (2026-09-10).

ACTIVE chain (recipe validated in game):
  clean text-free frame → LTX-2.5 I2V 65 frames locked camera → motion-compensated
  slow motion ×3.75 to ~9.8 s 1080p → xfade queue→head (1.5 s crossfade,
  fps=24 on BOTH branches, offset = post_duration − fade, trim=end final)
  → silent OGV Theora for Godot. The loop is built FROM THE CLEAN
  MASTER (menu_vent_gris_10s_1080p.mp4), NOT from the stabilized version.

⚠️ Lesson from the 2026-09-10 incident (rising black band, measured in game):
the old chain went through a stabilization step (stabiliser_camera_fixe)
whose warp sampled outside the source frame at the end of the drift — constant
BLACK fill (cv2.warpAffine default borderMode) — and the safety crop
was capped too low to cover the measured drift (236 px).
The black band grew with the drift, then the crossfade froze it.
Decisions: ① the stabilization step is REMOVED from the active chain (the
content is an almost static painting: the crossfade is enough and was validated
in game); ② the function remains available, fixed (BORDER_REPLICATE + covering
bounded crop with warning) and its result is audited (stabilise_fix)
as proof of the fix — but it does not enter the loop.

Resumable: each step is skipped if its deliverable already exists. Outputs suffixed
_fix: the originally contaminated files are kept as evidence.
No audio track: the menu music is laid in game (music_bg).
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.cinema import (  # noqa: E402
    FFMPEG_PATH,
    NEGATIF_DEFAUT,
    _duree_media,
    conformer_amorce_16_9,
    generer_monoplan_ltx,
    ralentir_interp_1080p,
)

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT = os.path.join(RACINE, "scripts", "audit_bande_noire.py")

ES_SOURCE = os.path.join("output", "intro_vent_gris")
TRAME_PROPRE = os.path.join(ES_SOURCE, "intro_vent_gris_v6_derniere_trame.png")
ES = os.path.join("output", "menu_vent_gris")
AMORCE = os.path.join(ES, "menu_vent_gris_amorce_832x480.png")
BRUT = os.path.join(ES, "menu_vent_gris_brut.webm")
RALENTI = os.path.join(ES, "menu_vent_gris_10s_1080p.mp4")       # clean master, reference
STABILISE = os.path.join(ES, "menu_vent_gris_stabilise.mp4")     # ⚠️ contaminated (evidence)
STABILISE_FIX = os.path.join(ES, "menu_vent_gris_stabilise_fix.mp4")  # proof of the fix
BOUCLE_MP4 = os.path.join(ES, "menu_vent_gris_boucle.mp4")       # ⚠️ contaminated (evidence)
BOUCLE_OGV = os.path.join(ES, "menu_vent_gris_boucle.ogv")       # ⚠️ contaminated (evidence)
BOUCLE_FIX_MP4 = os.path.join(ES, "menu_vent_gris_boucle_fix.mp4")
BOUCLE_FIX_OGV = os.path.join(ES, "menu_vent_gris_boucle_fix.ogv")

PROMPT = (
    "Locked static camera, completely fixed shot, no camera movement: a dark "
    "medieval fortress on a stormy sea cliff at dusk, painterly style. Only "
    "very slow drifting storm clouds and a calm sea gently shimmering, slow "
    "soft waves against the rocks, warm window lights glowing steadily, "
    "serene still atmosphere."
)
NEGATIF = NEGATIF_DEFAUT + (
    ", camera movement, camera pan, camera zoom, dolly, handheld, fast waves, "
    "storm surge, flickering lights"
)
SEED = 42
DUREE_RALENTI = 10.0
CROISE = 1.5           # queue→head crossfade (recipe validated in game)
SEUIL_RACCORD = 6.0    # mean L diff frame 0 vs last frame (exit criterion)


def log(message):
    print(message, flush=True)


def stabiliser_camera_fixe(source: str, sortie: str, nb_ancres: int = 6) -> str:
    """Freezes the camera on the framing of the first frame (OUTSIDE the active chain).

    Lesson §1.17 applied: NEVER per-frame raw measurement in the warp.
    Camera drift measured over 6 anchors — ORB + RANSAC in similarity, each
    anchor compared directly to frame 0 — then smooth interpolation.
    Fixes from the 2026-09-10 incident:
      • borderMode=BORDER_REPLICATE: NEVER again a black fill when
        sampling leaves the frame (edges replicate the last pixel);
      • crop ζ computed to COVER the measured drift (no more safety guard
        that masked the problem) but bounded at 1.25 with an explicit warning
        when it is not enough (replicated edges then remain possible —
        to check visually; the black band audit stays at 0 by construction).
    """
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(source)
    trames = []
    while True:
        ok, t = cap.read()
        if not ok:
            break
        trames.append(t)
    cap.release()
    n = len(trames)
    if n < 10:
        raise RuntimeError(f"Too few frames: {n}")

    echelle_petite = 960.0 / trames[0].shape[1]
    petit = (960, int(trames[0].shape[0] * echelle_petite))
    idx = [round(i * (n - 1) / (nb_ancres - 1)) for i in range(nb_ancres)]
    orb = cv2.ORB_create(6000)
    bf = cv2.BFMatcher(cv2.NORM_HAMMING)

    def gris_de(i):
        return cv2.resize(cv2.cvtColor(trames[i], cv2.COLOR_BGR2GRAY), petit)

    g0 = gris_de(idx[0])
    kp0, des0 = orb.detectAndCompute(g0, None)

    def similitude_vers_trame0(k):
        """Similarity frame0→frame_k (where the frame 0 content went)."""
        gk = gris_de(idx[k])
        kpk, desk = orb.detectAndCompute(gk, None)
        if des0 is None or desk is None:
            return None
        paires = bf.knnMatch(des0, desk, k=2)
        bons = [m for m, n in (p for p in paires if len(p) == 2)
                if m.distance < 0.75 * n.distance]
        if len(bons) < 40:
            log(f"   ⚠️ anchor {k}: {len(bons)} matches — interpolated from neighbors")
            return None
        src = np.float32([kp0[m.queryIdx].pt for m in bons])
        dst = np.float32([kpk[m.trainIdx].pt for m in bons])
        M, inliers = cv2.estimateAffinePartial2D(
            src, dst, method=cv2.RANSAC, ransacReprojThreshold=4.0, maxIters=5000)
        nb = 0 if inliers is None else int(inliers.sum())
        if M is None or nb < 30:
            log(f"   ⚠️ anchor {k}: RANSAC insufficient ({nb} inliers) — interpolated")
            return None
        s = float(np.sqrt(np.linalg.det(M[:2, :2])))
        theta = float(np.degrees(np.arctan2(M[1, 0], M[0, 0])))
        if not (0.85 <= s <= 1.35) or abs(theta) > 5.0:
            log(f"   ⚠️ anchor {k} outside camera plausibility (scale {s:.3f}, "
                f"rotation {theta:.1f}°) — interpolated")
            return None
        return M.astype(np.float64)

    affines = [np.eye(2, 3, dtype=np.float64)]
    for k in range(1, nb_ancres):
        M = similitude_vers_trame0(k)
        affines.append(M if M is not None else None)
    derniere_valide = np.eye(2, 3)
    for k in range(1, nb_ancres):
        if affines[k] is None:
            affines[k] = derniere_valide.copy()
        else:
            derniere_valide = affines[k]
    log("   drift (scale) at the anchors: " +
        ", ".join("{:.4f}".format(float(np.sqrt(np.linalg.det(a[:, :2])))) for a in affines))

    # full-resolution coords: similarity ⇒ only the translation rescales
    facteur = 1.0 / echelle_petite
    affines_full = [(a[:, :2].copy(), a[:, 2] * facteur) for a in affines]

    u_ancres = np.array(idx, dtype=np.float64) / (n - 1)
    H, W = trames[0].shape[:2]
    coins = np.array([[0, 0], [W - 1, 0], [0, H - 1], [W - 1, H - 1]], dtype=np.float64)
    hors = 0.0
    for (lin, vec) in affines_full:
        coins_t = coins @ lin.T + vec  # where the frame 0 corners land
        hors = max(hors,
                   max(0.0, -(coins_t[:, 0].min())), max(0.0, coins_t[:, 0].max() - (W - 1)),
                   max(0.0, -(coins_t[:, 1].min())), max(0.0, coins_t[:, 1].max() - (H - 1)))
    zeta_souhaite = 1.0 / max(1e-3, 1.0 - 2.0 * hors / min(W, H))
    ZETA_MAX = 1.25
    zeta = min(zeta_souhaite, ZETA_MAX)
    if zeta < zeta_souhaite:
        log(f"   ⚠️ desired crop ζ={zeta_souhaite:.2f} > cap {ZETA_MAX} — "
            "replicated edges (REPLICATE) possible at the end of the drift, check visually")
    log(f"   drift margin {hors:.1f} px → crop ζ={zeta:.4f}")

    def matrice(i):
        u = i / (n - 1)
        lin = np.empty((2, 2))
        vec = np.empty(2)
        for r in range(2):
            vec[r] = np.interp(u, u_ancres, [a[1][r] for a in affines_full])
            for c in range(2):
                lin[r, c] = np.interp(u, u_ancres, [a[0][r, c] for a in affines_full])
        cx, cy = (W - 1) / 2.0, (H - 1) / 2.0
        P_lin = np.diag([1.0 / zeta, 1.0 / zeta])
        P_vec = np.array([(1 - 1 / zeta) * cx, (1 - 1 / zeta) * cy])
        return np.hstack([lin @ P_lin, (lin @ P_vec + vec).reshape(2, 1)]).astype(np.float32)

    tmp = tempfile.mkdtemp(prefix="menu_stab_")
    try:
        for i in range(n):
            out = cv2.warpAffine(trames[i], matrice(i), (W, H),
                                 flags=cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP,
                                 borderMode=cv2.BORDER_REPLICATE)
            cv2.imwrite(os.path.join(tmp, "s_%04d.png" % (i + 1)), out,
                        [cv2.IMWRITE_PNG_COMPRESSION, 3])
        subprocess.run(
            [FFMPEG_PATH, "-y", "-v", "error", "-framerate", "24", "-start_number", "1",
             "-i", os.path.join(tmp, "s_%04d.png"), "-frames:v", str(n),
             "-vf", "format=yuv420p", "-c:v", "libx264", "-crf", "16", sortie],
            capture_output=True, check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return sortie


def boucle_parfaite(source: str, sortie: str, croise: float = CROISE) -> str:
    """Perfect infinite loop — xfade recipe VALIDATED IN GAME (2026-09-10 incident).

    Pitfalls taken into account:
      • xfade REQUIRES a constant fps → fps=24 on BOTH branches before xfade;
      • trim=X sets the START, not the end → the final length is written trim=end=…;
      • offset = post_duration − fade (post_duration = source_duration − fade);
      • the joint result(0) ≈ result(end) is verified by the black band audit.
    """
    duree = _duree_media(source)
    duree_post = duree - croise
    offset = duree_post - croise
    filtre = (
        "[0:v]split[body][pre];"
        f"[pre]trim=0:{croise:.3f},setpts=PTS-STARTPTS,fps=24[pre];"
        f"[body]trim={croise:.3f},setpts=PTS-STARTPTS,fps=24[post];"
        f"[post][pre]xfade=transition=fade:duration={croise:.3f}:offset={offset:.3f}[xf];"
        f"[xf]trim=end={duree_post:.3f},setpts=PTS-STARTPTS[out]"
    )
    subprocess.run(
        [FFMPEG_PATH, "-y", "-v", "error", "-i", source,
         "-filter_complex", filtre, "-map", "[out]", "-an",
         "-c:v", "libx264", "-crf", "16", "-preset", "slow", sortie],
        capture_output=True, check=True,
    )
    log(f"   source {duree:.2f} s → loop {duree_post:.2f} s (fade {croise} s, offset {offset:.2f} s)")
    return sortie


def encoder_ogv(source: str, sortie: str) -> str:
    """Silent OGV Theora (native Godot 4 video format), max quality (q 10)."""
    subprocess.run(
        [FFMPEG_PATH, "-y", "-v", "error", "-i", source, "-an",
         "-c:v", "libtheora", "-q:v", "10", "-pix_fmt", "yuv420p", sortie],
        capture_output=True, check=True,
    )
    return sortie


def planche_qa(video: str, prefixe: str = "qa_boucle_fix"):
    """Start/middle/end snapshots + board with the end→start joint in cell 4."""
    from PIL import Image
    duree = _duree_media(video)
    instantanes = []
    for nom, t in ((f"{prefixe}_debut.png", 0.0),
                   (f"{prefixe}_milieu.png", duree / 2),
                   (f"{prefixe}_fin.png", duree - 0.25)):
        chemin = os.path.join(ES, nom)
        subprocess.run(
            [FFMPEG_PATH, "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", video,
             "-frames:v", "1", "-q:v", "2", chemin],
            capture_output=True, check=True)
        instantanes.append(chemin)
    raccord = os.path.join(ES, f"{prefixe}_raccord.png")
    gauche = Image.open(instantanes[2]).resize((960, 540), Image.Resampling.LANCZOS)
    droite = Image.open(instantanes[0]).resize((960, 540), Image.Resampling.LANCZOS)
    cote = Image.new("RGB", (1920, 540))
    cote.paste(gauche, (0, 0))
    cote.paste(droite, (960, 0))
    cote.save(raccord, quality=100)
    planche = Image.new("RGB", (1920, 1080))
    for i, chemin in enumerate(instantanes):
        case = Image.open(chemin).resize((960, 540), Image.Resampling.LANCZOS)
        planche.paste(case, ((i % 2) * 960, (i // 2) * 540))
    rac = Image.open(raccord).resize((960, 270), Image.Resampling.LANCZOS)
    planche.paste(rac, (960, 540 + 135))
    sortie = os.path.join(ES, f"{prefixe}_planche.png")
    planche.save(sortie, quality=100)
    log(f"   QA board: {os.path.basename(sortie)} (start / middle / end / joint)")


def auditer(sortie_attendue_zero, avec_raccord):
    """Exit criterion: black band audit (0 px) on the listed videos,
    loop joint ≤ threshold on those marked "loop". Exit 1 on failure."""
    commande = [sys.executable, AUDIT,
                "--zero", *sortie_attendue_zero,
                "--raccord", *avec_raccord]
    resultat = subprocess.run(commande)
    if resultat.returncode != 0:
        raise SystemExit("⛔ AUDIT black band/joint: EXIT CRITERION NOT MET")
    log("✅ AUDIT: black band 0 px everywhere, joints within threshold.")


def main():
    t0 = time.time()
    if not os.path.exists(TRAME_PROPRE):
        raise FileNotFoundError(TRAME_PROPRE)
    os.makedirs(ES, exist_ok=True)

    # 1. 832×480 16:9 lead-in from the clean frame (text-free)
    if os.path.exists(AMORCE):
        log(f"⏭️ 1. lead-in already present: {os.path.basename(AMORCE)}")
    else:
        conformer_amorce_16_9(TRAME_PROPRE, AMORCE)
        log("✅ 1. 832×480 lead-in ready (Lanczos crop).")

    # 2. LTX I2V generation locked camera (65 frames = stable GPU ceiling)
    if os.path.exists(BRUT):
        log(f"⏭️ 2. raw already present: {os.path.basename(BRUT)}")
    else:
        log("🎬 2. LTX-2.5 I2V generation (locked camera, ultra-light movement)…")
        generer_monoplan_ltx(
            AMORCE, PROMPT, BRUT, frames=65, fps=24, seed=SEED, negatif=NEGATIF,
            log_fn=lambda m: log(m.strip()))
        log("✅ 2. raw generated (8 euler_a steps, cfg 1.0).")

    # 3. motion-compensated slow motion ×3.75 → ~9.8 s 1080p (even smoother movement)
    if os.path.exists(RALENTI):
        log(f"⏭️ 3. slow motion already present: {os.path.basename(RALENTI)} (clean master)")
    else:
        _, facteur = ralentir_interp_1080p(BRUT, RALENTI, DUREE_RALENTI, fps=24)
        log(f"✅ 3. slow motion ×{facteur:.2f} applied (mci/aobmc/vsbmc, 1080p).")

    # 3bis. FIXED stabilization — proof of the fix ONLY, the loop
    # is built from the clean master (recipe validated in game, see docstring)
    if os.path.exists(STABILISE_FIX):
        log(f"⏭️ 3bis. fixed stabilized already present: {os.path.basename(STABILISE_FIX)}")
    else:
        log("🔧 3bis. fixed stabilization (REPLICATE + covering ζ) — audit proof, outside the loop…")
        stabiliser_camera_fixe(RALENTI, STABILISE_FIX)
        log(f"✅ 3bis. {os.path.basename(STABILISE_FIX)} (does NOT enter the loop).")

    # 4. perfect loop from the CLEAN MASTER — xfade recipe validated in game
    if os.path.exists(BOUCLE_FIX_MP4):
        log(f"⏭️ 4. loop already present: {os.path.basename(BOUCLE_FIX_MP4)}")
    else:
        log("🎞️ 4. xfade loop (fps=24 on both branches, trim=end, offset=post_duration−fade)…")
        boucle_parfaite(RALENTI, BOUCLE_FIX_MP4)
        log(f"✅ 4. loop: {os.path.basename(BOUCLE_FIX_MP4)}")

    # 5. silent OGV Theora for Godot
    if os.path.exists(BOUCLE_FIX_OGV):
        log(f"⏭️ 5. OGV already present: {os.path.basename(BOUCLE_FIX_OGV)}")
    else:
        encoder_ogv(BOUCLE_FIX_MP4, BOUCLE_FIX_OGV)
        log(f"✅ 5. Godot OGV: {os.path.basename(BOUCLE_FIX_OGV)} (silent, loop).")

    if not os.path.exists(os.path.join(ES, "qa_boucle_fix_planche.png")):
        planche_qa(BOUCLE_FIX_MP4)

    # 6. AUDIT — exit criterion: 0 px of black band at every phase,
    # loop joint ≤ 6 (L scale, 0-255). The script fails otherwise.
    log("🔍 6. black band + joints audit…")
    auditer(
        sortie_attendue_zero=[RALENTI, STABILISE_FIX, BOUCLE_FIX_MP4, BOUCLE_FIX_OGV],
        avec_raccord=[BOUCLE_FIX_MP4, BOUCLE_FIX_OGV],
    )

    log(f"🎉 Done in {(time.time() - t0) / 60:.1f} min — _fix deliverables in {ES}:")
    for chemin in (BOUCLE_FIX_MP4, BOUCLE_FIX_OGV):
        log(f"   • {os.path.basename(chemin)}")


if __name__ == "__main__":
    main()
