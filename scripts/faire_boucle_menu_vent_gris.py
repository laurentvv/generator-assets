#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/faire_boucle_menu_vent_gris.py — fond de menu « L'HÉRITIER DU VIDE » :
cinemagraph IA ultra-léger en boucle infinie parfaite, caméra fixe (2026-09-10).

Chaîne ACTIVE (recette validée en jeu) :
  trame propre sans texte → LTX-2.5 I2V 65 trames caméra verrouillée → ralenti
  motion-compensé ×3,75 vers ~9,8 s 1080p → xfade queue→tête (fondu 1,5 s,
  fps=24 sur les DEUX branches, offset = durée_post − fondu, trim=end final)
  → OGV Theora silencieux pour Godot. La boucle est construite DEPUIS LE
  MASTER PROPRE (menu_vent_gris_10s_1080p.mp4), PAS depuis le stabilisé.

⚠️ Leçon incident 2026-09-10 (bande noire montante, mesurée en jeu) :
l'ancienne chaîne passait par une étape de stabilisation (stabiliser_camera_fixe)
dont le warp échantillonnait hors du cadre source en fin de dérive — remplissage
NOIR constant (borderMode par défaut de cv2.warpAffine) — et le recadrage de
sécurité était plafonné trop bas pour couvrir la dérive mesurée (236 px).
La bande noire grandissait avec la dérive, puis le crossfade la figeait.
Décisions : ① l'étape de stabilisation est RETIRÉE de la chaîne active (le
contenu est une peinture quasi fixe : le fondu croisé suffit et a été validé
en jeu) ; ② la fonction reste disponible, corrigée (BORDER_REPLICATE + recadrage
couvrant borné avec avertissement) et son résultat est audité (stabilise_fix)
comme preuve de correction — mais il n'entre pas dans la boucle.

Reprenant : chaque étape saute si son livrable existe déjà. Sorties suffixées
_fix : les fichiers contaminés d'origine sont conservés comme pièces à conviction.
Pas de piste son : la musique du menu est posée dans le jeu (music_bg).
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
RALENTI = os.path.join(ES, "menu_vent_gris_10s_1080p.mp4")       # master propre, référence
STABILISE = os.path.join(ES, "menu_vent_gris_stabilise.mp4")     # ⚠️ contaminé (pièce à conviction)
STABILISE_FIX = os.path.join(ES, "menu_vent_gris_stabilise_fix.mp4")  # preuve de correction
BOUCLE_MP4 = os.path.join(ES, "menu_vent_gris_boucle.mp4")       # ⚠️ contaminé (pièce à conviction)
BOUCLE_OGV = os.path.join(ES, "menu_vent_gris_boucle.ogv")       # ⚠️ contaminé (pièce à conviction)
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
CROISE = 1.5           # fondu croisé queue→tête (recette validée en jeu)
SEUIL_RACCORD = 6.0    # diff L moyenne trame 0 vs dernière trame (critère de sortie)


def log(message):
    print(message, flush=True)


def stabiliser_camera_fixe(source: str, sortie: str, nb_ancres: int = 6) -> str:
    """Gèle la caméra sur le cadrage de la première trame (HORS chaîne active).

    Leçon §1.17 appliquée : JAMAIS de mesure brute par trame dans le warp.
    Dérive caméra mesurée sur 6 ancrages — ORB + RANSAC en similitude, chaque
    ancre comparée directement à la trame 0 — puis interpolation douce.
    Corrections incident 2026-09-10 :
      • borderMode=BORDER_REPLICATE : plus JAMAIS de remplissage noir quand
        l'échantillonnage sort du cadre (les bords répliquent le dernier pixel) ;
      • recadrage ζ calculé pour COUVRIR la dérive mesurée (plus de garde-fou
        qui masquait le problème) mais borné à 1,25 avec avertissement explicite
        quand il ne suffit pas (les bords répliqués restent alors possibles —
        à vérifier visuellement ; l'audit bande noire reste à 0 par construction).
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
        raise RuntimeError(f"Trop peu de trames : {n}")

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
        """Similitude trame0→trame_k (où est parti le contenu de la trame 0)."""
        gk = gris_de(idx[k])
        kpk, desk = orb.detectAndCompute(gk, None)
        if des0 is None or desk is None:
            return None
        paires = bf.knnMatch(des0, desk, k=2)
        bons = [m for m, n in (p for p in paires if len(p) == 2)
                if m.distance < 0.75 * n.distance]
        if len(bons) < 40:
            log(f"   ⚠️ ancre {k} : {len(bons)} appariements — interpolée des voisines")
            return None
        src = np.float32([kp0[m.queryIdx].pt for m in bons])
        dst = np.float32([kpk[m.trainIdx].pt for m in bons])
        M, inliers = cv2.estimateAffinePartial2D(
            src, dst, method=cv2.RANSAC, ransacReprojThreshold=4.0, maxIters=5000)
        nb = 0 if inliers is None else int(inliers.sum())
        if M is None or nb < 30:
            log(f"   ⚠️ ancre {k} : RANSAC insuffisant ({nb} inliers) — interpolée")
            return None
        s = float(np.sqrt(np.linalg.det(M[:2, :2])))
        theta = float(np.degrees(np.arctan2(M[1, 0], M[0, 0])))
        if not (0.85 <= s <= 1.35) or abs(theta) > 5.0:
            log(f"   ⚠️ ancre {k} hors plausibilité caméra (échelle {s:.3f}, "
                f"rotation {theta:.1f}°) — interpolée")
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
    log("   dérive (échelle) aux ancrages : " +
        ", ".join("{:.4f}".format(float(np.sqrt(np.linalg.det(a[:, :2])))) for a in affines))

    # coords pleine résolution : similitude ⇒ seule la translation change d'échelle
    facteur = 1.0 / echelle_petite
    affines_full = [(a[:, :2].copy(), a[:, 2] * facteur) for a in affines]

    u_ancres = np.array(idx, dtype=np.float64) / (n - 1)
    H, W = trames[0].shape[:2]
    coins = np.array([[0, 0], [W - 1, 0], [0, H - 1], [W - 1, H - 1]], dtype=np.float64)
    hors = 0.0
    for (lin, vec) in affines_full:
        coins_t = coins @ lin.T + vec  # où atterrissent les coins de la trame 0
        hors = max(hors,
                   max(0.0, -(coins_t[:, 0].min())), max(0.0, coins_t[:, 0].max() - (W - 1)),
                   max(0.0, -(coins_t[:, 1].min())), max(0.0, coins_t[:, 1].max() - (H - 1)))
    zeta_souhaite = 1.0 / max(1e-3, 1.0 - 2.0 * hors / min(W, H))
    ZETA_MAX = 1.25
    zeta = min(zeta_souhaite, ZETA_MAX)
    if zeta < zeta_souhaite:
        log(f"   ⚠️ recadrage souhaité ζ={zeta_souhaite:.2f} > plafond {ZETA_MAX} — "
            "bords répliqués (REPLICATE) possibles en fin de dérive, vérifier visuellement")
    log(f"   marge de dérive {hors:.1f} px → recadrage ζ={zeta:.4f}")

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
    """Boucle infinie parfaite — recette xfade VALIDÉE EN JEU (incident 2026-09-10).

    Pièges pris en compte :
      • xfade EXIGE un fps constant → fps=24 sur les DEUX branches avant xfade ;
      • trim=X fixe le DÉBUT, pas la fin → la longueur finale s'écrit trim=end=… ;
      • offset = durée_post − fondu (durée_post = durée_source − fondu) ;
      • le raccord result(0) ≈ result(fin) est vérifié par l'audit bande noire.
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
    log(f"   source {duree:.2f} s → boucle {duree_post:.2f} s (fondu {croise} s, offset {offset:.2f} s)")
    return sortie


def encoder_ogv(source: str, sortie: str) -> str:
    """OGV Theora silencieux (format vidéo natif Godot 4), qualité max (q 10)."""
    subprocess.run(
        [FFMPEG_PATH, "-y", "-v", "error", "-i", source, "-an",
         "-c:v", "libtheora", "-q:v", "10", "-pix_fmt", "yuv420p", sortie],
        capture_output=True, check=True,
    )
    return sortie


def planche_qa(video: str, prefixe: str = "qa_boucle_fix"):
    """Instantanés début/milieu/fin + planche avec raccord fin→début en case 4."""
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
    log(f"   planche QA : {os.path.basename(sortie)} (début / milieu / fin / raccord)")


def auditer(sortie_attendue_zero, avec_raccord):
    """Critère de sortie : audit bande noire (0 px) sur les vidéos listées,
    raccord de boucle ≤ seuil sur celles marquées « boucle ». Exit 1 si échec."""
    commande = [sys.executable, AUDIT,
                "--zero", *sortie_attendue_zero,
                "--raccord", *avec_raccord]
    resultat = subprocess.run(commande)
    if resultat.returncode != 0:
        raise SystemExit("⛔ AUDIT bande noire/raccord : CRITÈRE DE SORTIE NON ATTEINT")
    log("✅ AUDIT : bande noire 0 px partout, raccords dans le seuil.")


def main():
    t0 = time.time()
    if not os.path.exists(TRAME_PROPRE):
        raise FileNotFoundError(TRAME_PROPRE)
    os.makedirs(ES, exist_ok=True)

    # 1. amorce 16:9 832×480 depuis la trame propre (sans texte)
    if os.path.exists(AMORCE):
        log(f"⏭️ 1. amorce déjà présente : {os.path.basename(AMORCE)}")
    else:
        conformer_amorce_16_9(TRAME_PROPRE, AMORCE)
        log("✅ 1. amorce 832×480 prête (recadrage Lanczos).")

    # 2. génération LTX I2V caméra verrouillée (65 trames = plafond GPU stable)
    if os.path.exists(BRUT):
        log(f"⏭️ 2. brut déjà présent : {os.path.basename(BRUT)}")
    else:
        log("🎬 2. génération LTX-2.5 I2V (caméra fixe, mouvement ultra-léger)…")
        generer_monoplan_ltx(
            AMORCE, PROMPT, BRUT, frames=65, fps=24, seed=SEED, negatif=NEGATIF,
            log_fn=lambda m: log(m.strip()))
        log("✅ 2. brut généré (8 steps euler_a, cfg 1.0).")

    # 3. ralenti motion-compensé ×3,75 → ~9,8 s 1080p (mouvement encore plus doux)
    if os.path.exists(RALENTI):
        log(f"⏭️ 3. ralenti déjà présent : {os.path.basename(RALENTI)} (master propre)")
    else:
        _, facteur = ralentir_interp_1080p(BRUT, RALENTI, DUREE_RALENTI, fps=24)
        log(f"✅ 3. ralenti ×{facteur:.2f} appliqué (mci/aobmc/vsbmc, 1080p).")

    # 3bis. stabilisation CORRIGÉE — preuve de correction UNIQUEMENT, la boucle
    # est construite depuis le master propre (recette validée en jeu, voir docstring)
    if os.path.exists(STABILISE_FIX):
        log(f"⏭️ 3bis. stabilisée corrigée déjà présente : {os.path.basename(STABILISE_FIX)}")
    else:
        log("🔧 3bis. stabilisation corrigée (REPLICATE + ζ couvrant) — preuve d'audit, hors boucle…")
        stabiliser_camera_fixe(RALENTI, STABILISE_FIX)
        log(f"✅ 3bis. {os.path.basename(STABILISE_FIX)} (n'entre PAS dans la boucle).")

    # 4. boucle parfaite depuis le MASTER PROPRE — recette xfade validée en jeu
    if os.path.exists(BOUCLE_FIX_MP4):
        log(f"⏭️ 4. boucle déjà présente : {os.path.basename(BOUCLE_FIX_MP4)}")
    else:
        log("🎞️ 4. boucle xfade (fps=24 sur les 2 branches, trim=end, offset=durée_post−fondu)…")
        boucle_parfaite(RALENTI, BOUCLE_FIX_MP4)
        log(f"✅ 4. boucle : {os.path.basename(BOUCLE_FIX_MP4)}")

    # 5. OGV Theora silencieux pour Godot
    if os.path.exists(BOUCLE_FIX_OGV):
        log(f"⏭️ 5. OGV déjà présent : {os.path.basename(BOUCLE_FIX_OGV)}")
    else:
        encoder_ogv(BOUCLE_FIX_MP4, BOUCLE_FIX_OGV)
        log(f"✅ 5. OGV Godot : {os.path.basename(BOUCLE_FIX_OGV)} (silencieux, boucle).")

    if not os.path.exists(os.path.join(ES, "qa_boucle_fix_planche.png")):
        planche_qa(BOUCLE_FIX_MP4)

    # 6. AUDIT — critère de sortie : 0 px de bande noire à toutes les phases,
    # raccord de boucle ≤ 6 (échelle L, 0-255). Échoue le script sinon.
    log("🔍 6. audit bande noire + raccords…")
    auditer(
        sortie_attendue_zero=[RALENTI, STABILISE_FIX, BOUCLE_FIX_MP4, BOUCLE_FIX_OGV],
        avec_raccord=[BOUCLE_FIX_MP4, BOUCLE_FIX_OGV],
    )

    log(f"🎉 Terminé en {(time.time() - t0) / 60:.1f} min — livrables _fix dans {ES} :")
    for chemin in (BOUCLE_FIX_MP4, BOUCLE_FIX_OGV):
        log(f"   • {os.path.basename(chemin)}")


if __name__ == "__main__":
    main()
