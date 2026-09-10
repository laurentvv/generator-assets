#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core/cinema.py — plan-séquence IA « monoplan » (VALIDÉ utilisateur le 2026-09-10).

Recette gagnante (MEMORY_BANK §1.17, intro Vent-Gris « L'HÉRITIER DU VIDE ») :
une SEULE génération LTX-2.5 I2V depuis une image d'amorce (65 trames = plafond
GPU stable), ralentie vers la durée cible avec interpolation motion-compensée,
puis re-cadrée par un zoom pur CONÇU (rampe monotone avec easing — aucune mesure
de suivi dans le warp : le traceur NCC injecterait son bruit en translation).
Résultat : plan unique sans coupe ni vibration de caméra.

Pourquoi pas plus long/multi-plans : le chaînage I2V crée des coupes de contenu
(nuages/vagues réinterprétés → saccades, toutes les réparations v2-v5 rejetées),
et le module interne `ltxav` de LTX mange ~29 Mo de VRAM par trame (plafond
~81 trames à 832×480 sur RX 6950 XT). Le ralenti est donc LE levier durée.
"""

import os
import shutil
import subprocess
import tempfile
import time
from typing import Callable, Dict, Optional, Tuple

from PIL import Image

from core.config import DEFAULT_MODEL_DIR, DEFAULT_SD_CLI, DEFAULT_FFMPEG as FFMPEG_PATH

# Modèles LTX-2.5 Distilled validés (§1.1 / §1.17)
LTX_DIT = os.path.join(DEFAULT_MODEL_DIR, "LTX-2.5-Distilled-Q4_K_M.gguf")
LTX_VAE = os.path.join(DEFAULT_MODEL_DIR, "ltx-2.5-video-vae-conv-bf16.safetensors")
LTX_LLM = os.path.join(DEFAULT_MODEL_DIR, "gemma4-12b-with-proj-ltx-2.5-Q5_K_M.gguf")

# Sigmas officiels distillés Lightricks (8 steps, cfg 1.0 = 1 passe/step)
SIGMAS_LTX = "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"

NEGATIF_DEFAUT = (
    "text, watermark, logo, subtitles, warm colors, autumn colors, sunny, cartoon, "
    "anime, modern elements, crowds, blurry, jitter, sudden cuts, glitch, low "
    "quality, noisy, distorted, morphing, lowres"
)

# Ancre du zoom en ratio de cadre (validée sur le château du Vent-Gris :
# position du sujet principal légèrement à gauche du centre)
ANCRE_X, ANCRE_Y = 0.656, 0.472


def conformer_amorce_16_9(source: str, destination: str, largeur: int = 832,
                          hauteur: int = 480) -> str:
    """Recadrage 16:9 exact + redimensionnement Lanczos (aucune déformation)."""
    img = Image.open(source).convert("RGB")
    w, h = img.size
    cible = 16.0 / 9.0
    if abs(w / h - cible) > 0.005:
        nouvelle_l = int(h * cible)
        x0 = max(0, (w - nouvelle_l) // 2)
        img = img.crop((x0, 0, x0 + nouvelle_l, h))
    img = img.resize((largeur, hauteur), Image.Resampling.LANCZOS)
    img.save(destination, quality=100)
    return destination


def generer_monoplan_ltx(
    amorce: str,
    prompt: str,
    sortie: str,
    frames: int = 65,
    fps: int = 24,
    seed: int = 42,
    negatif: str = NEGATIF_DEFAUT,
    max_vram: int = 10,
    log_fn: Callable[[str], None] = print,
) -> str:
    """Plan unique LTX-2.5 Distilled I2V (recette §1.17, 8 steps euler_a, cfg 1.0)."""
    manquants = [p for p in (DEFAULT_SD_CLI, LTX_DIT, LTX_VAE, LTX_LLM) if not os.path.exists(p)]
    if manquants:
        raise FileNotFoundError("Modèles LTX-2.5 ou sd-cli manquants : " + "; ".join(manquants))
    os.makedirs(os.path.dirname(os.path.abspath(sortie)), exist_ok=True)
    commande = [
        DEFAULT_SD_CLI, "-M", "vid_gen",
        "--diffusion-model", LTX_DIT,
        "--vae", LTX_VAE,
        "--llm", LTX_LLM,
        "-i", amorce,
        "-p", prompt,
        "-n", negatif,
        "-W", "832", "-H", "480",
        "--video-frames", str(frames),
        "--fps", str(fps),
        "--steps", "8",
        "--sigmas", SIGMAS_LTX,
        "--sampling-method", "euler_a",
        "--cfg-scale", "1.0",
        "--diffusion-fa",
        "--max-vram", str(max_vram),
        "--backend", "diffusion=vulkan0,te=cpu,vae=cpu",
        "-s", str(seed),
        "-o", sortie,
        "-v",
    ]
    log_fn("[cinéma] Génération monoplan LTX-2.5 ({} trames @ {} fps, seed {})…".format(frames, fps, seed))
    subprocess.run(commande, check=True)
    if not os.path.exists(sortie):
        candidat = sortie.replace(".webm", "_0.webm")
        if os.path.exists(candidat):
            os.rename(candidat, sortie)
    if not os.path.exists(sortie):
        raise RuntimeError(f"Monoplan non produit : {sortie}")
    return sortie


def ralentir_interp_1080p(webm: str, sortie: str, duree_cible: float,
                          fps: int = 24) -> Tuple[str, int]:
    """Ralenti temporel vers la durée cible + interpolation motion-compensée 24→24
    + upscale lanczos 1080p (l'étape zoom travaille en coordonnées 1920×1080)."""
    info = subprocess.run(
        [FFMPEG_PATH, "-i", webm], capture_output=True, text=True, encoding="utf-8",
        errors="replace",
    ).stderr
    import re
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", info)
    if not m:
        raise RuntimeError(f"Durée illisible : {webm}")
    duree_src = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    facteur = duree_cible / max(duree_src, 0.1)
    ok = subprocess.run(
        [FFMPEG_PATH, "-y", "-v", "error", "-i", webm, "-vf",
         f"setpts={facteur:.4f}*PTS,"
         f"minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"
         "scale=1920:1080:flags=lanczos",
         "-an", "-c:v", "libx264", "-crf", "12", "-preset", "slow",
         "-pix_fmt", "yuv420p", sortie],
        capture_output=True,
    ).returncode == 0
    if not ok or not os.path.exists(sortie):
        raise RuntimeError(f"Ralenti/interpolation échoué : {sortie}")
    return sortie, facteur


def zoom_pur(video_1080p: str, sortie: str, zoom_debut: float = 1.10,
             zoom_fin: float = 1.32, ancre: Tuple[float, float] = (ANCRE_X, ANCRE_Y),
             cas: float = 0.75) -> str:
    """Rampe de zoom CONÇUE (smootherstep) autour d'une ancre fixe — aucune mesure
    de suivi dans le warp : le rendu est incapable de vibrer par construction."""
    import cv2
    import numpy as np

    tmp = tempfile.mkdtemp(prefix="cinema_zoom_")
    try:
        subprocess.run(
            [FFMPEG_PATH, "-y", "-v", "error", "-i", video_1080p, "-fps_mode", "passthrough",
             "-q:v", "2", os.path.join(tmp, "f_%04d.png")], capture_output=True, check=True,
        )
        pngs = sorted(f for f in os.listdir(tmp) if f.startswith("f_"))
        n = len(pngs)
        W, H = 1920, 1080
        centre = (ancre[0] * W, ancre[1] * H)
        u = np.linspace(0.0, 1.0, n)
        ease = u * u * u * (u * (u * 6.0 - 15.0) + 10.0)  # smootherstep
        for i, nom in enumerate(pngs):
            img = cv2.imread(os.path.join(tmp, nom))
            k = 1.0 / (zoom_debut + (zoom_fin - zoom_debut) * ease[i])
            tx = centre[0] * (1.0 - k)
            ty = centre[1] * (1.0 - k)
            tx = min(max(tx, min(0.0, W * (1 - k))), max(0.0, W * (1 - k)))
            ty = min(max(ty, min(0.0, H * (1 - k))), max(0.0, H * (1 - k)))
            M = np.array([[k, 0.0, tx], [0.0, k, ty]], dtype=np.float64)
            corr = cv2.warpAffine(img, M, (W, H),
                                  flags=cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP)
            cv2.imwrite(os.path.join(tmp, "s_%04d.png" % (i + 1)), corr,
                        [cv2.IMWRITE_PNG_COMPRESSION, 3])
        filtre_cas = f",cas={cas}" if cas else ""
        subprocess.run(
            [FFMPEG_PATH, "-y", "-v", "error", "-framerate", "24", "-start_number", "1",
             "-i", os.path.join(tmp, "s_%04d.png"), "-frames:v", str(n),
             "-vf", "format=yuv420p" + filtre_cas,
             "-c:v", "libx264", "-crf", "16", sortie],
            capture_output=True, check=True,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return sortie


def muxer_audio(video: str, wav: str, sortie: str) -> str:
    """Colle une piste audio (lit sonore) sur la vidéo, vidéo copiée à l'identique."""
    subprocess.run(
        [FFMPEG_PATH, "-y", "-v", "error", "-i", video, "-i", wav,
         "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", sortie],
        capture_output=True, check=True,
    )
    return sortie


def generer_lit_ambiance(prompt: str, duree: float, seed: int = 42,
                         chemin_wav: Optional[str] = None) -> str:
    """Lit sonore via le moteur SFX IA validé (SA3 Small, normalisation incluse).
    Écrit un WAV prêt à muxer (et son OGG Godot à côté si chemin_wav fourni)."""
    import numpy as np
    import soundfile as sf
    from core.sfx_ia import generer_sfx_ia

    res = generer_sfx_ia(prompt, duree=duree, seed=seed)
    if chemin_wav is None:
        fd, chemin_wav = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
    sf.write(chemin_wav, res["audio"], res["sr"], subtype="PCM_16", format="WAV")
    if res["rognage_pct"] > 0.01:
        # rogner les silences structurels comme le workflow sfx (± garde-fou 50 %)
        audio = res["audio"]
        seuil = 0.0056  # ≈ −45 dBFS
        actifs = np.where(np.abs(audio).max(axis=1) > seuil)[0]
        if len(actifs) and (actifs[-1] - actifs[0]) > len(audio) * 0.5:
            audio = audio[actifs[0]:actifs[-1] + 1]
            sf.write(chemin_wav, audio, res["sr"], subtype="PCM_16", format="WAV")
    return chemin_wav


# ---------------------------------------------------------------------------
# Carton de titre « haute couture » (image figée + titre animé, exigence
# utilisateur 2026-09-10 : le titre doit être TRÈS beau graphiquement).
# Traitement multi-couches Pillow : dégradé ivoire→or, biseau ciselé, halo
# chaud, ombre portée profonde, vignette de contraste, ornement filet+losange.
# ---------------------------------------------------------------------------

# Palette du titre (harmonisée au château d'hiver : or ancien sur ciel d'orage)
TITRE_OR_HAUT = (247, 240, 223)     # ivoire chaud (haut du dégradé)
TITRE_OR_BAS = (201, 169, 106)      # or ancien (bas du dégradé)
TITRE_BISEAU_CLAIR = (255, 252, 240)
TITRE_BISEAU_SOMBRE = (58, 40, 18)
TITRE_HALO = (247, 240, 223)
TITRE_OMBRE = (8, 14, 26)
TITRE_VIGNETTE = (6, 10, 20)
TITRE_ORNEMENT_OR = (201, 169, 106)
TITRE_ORNEMENT_IVOIRE = (240, 232, 210)

POLICE_DEFAUT_TITRE = r"C:\Windows\Fonts\FELIXTI.TTF"    # Felix Titling (capitales inscriptionnelles)
POLICE_REPLI_TITRE = r"C:\Windows\Fonts\georgia.ttf"     # repli si accent manquant

# Chronologie de la révélation (secondes, carton de 6 s)
_T_FADE_DEBUT, _T_FADE_FIN = 0.7, 2.2          # fondu global du bloc
_T_STAGGER = 0.035                             # décalage par glyphe (vague gauche→droite)
_TRACK_DEBUT_EM, _TRACK_FIN_EM = 0.12, 0.22    # interlettrage début→fin (en em)
_T_TRACK_DEBUT, _T_TRACK_FIN = 0.7, 3.4
_T_MONTEE_FIN = 2.6                            # fin de la montée douce du bloc
_T_ORN_DEBUT = 1.4                             # apparition de l'ornement
_T_ORN_ALPHA_FIN, _T_ORN_CROISSANCE_FIN = 2.4, 2.8
_MONTEE_PX = 15.0


def _smooth(u: float) -> float:
    """Smootherstep clampé (même courbe que la rampe de zoom_pur)."""
    u = 0.0 if u < 0.0 else (1.0 if u > 1.0 else u)
    return u * u * u * (u * (u * 6.0 - 15.0) + 10.0)


def _duree_media(chemin: str) -> float:
    """Durée d'un média via l'en-tête stderr ffmpeg (motif du ralenti §1.17)."""
    import re
    info = subprocess.run(
        [FFMPEG_PATH, "-i", chemin], capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    ).stderr
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", info)
    if not m:
        raise RuntimeError(f"Durée illisible : {chemin}")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def _couche_unie(mask, couleur, intensite: float):
    """Calque RGBA uni dont l'alpha = masque L × intensité (0..1)."""
    alpha = mask.point(lambda v: int(v * intensite))
    calque = Image.new("RGBA", mask.size, couleur + (0,))
    calque.putalpha(alpha)
    return calque


def _tuile_glyphe(font, glyphe: str, em: int):
    """Rend UN glyphe en tuile RGBA : ombre + halo + dégradé or + biseau ciselé.

    Retourne (tuile, dx, dy) — dx/dy = ancre d'encre relative à l'origine de
    dessin, pour garder les lignes de base alignées entre glyphes accentués
    (É) et non accentués. Rend None si le glyphe est absent de la police.
    """
    from PIL import ImageChops, ImageDraw, ImageFilter

    marge = int(em * 0.45) + 4
    canvas = Image.new("L", (em + 2 * marge, em + 2 * marge), 0)
    dessin = ImageDraw.Draw(canvas)
    dessin.text((marge, marge), glyphe, font=font, fill=255)
    boite = canvas.getbbox()
    if not boite:
        return None  # glyphe absent de la police (ex. accent manquant)
    x0, y0, x1, y1 = boite
    x0, y0 = max(0, x0 - marge // 2), max(0, y0 - marge // 2)
    x1, y1 = min(canvas.width, x1 + marge // 2), min(canvas.height, y1 + marge // 2)
    ancre = (x0 - marge, y0 - marge)
    mask = canvas.crop((x0, y0, x1, y1))

    # 1) ombre portée profonde (bleu-noir, floue, décalée bas)
    ombre = _couche_unie(
        mask.transform(mask.size, Image.AFFINE, (1, 0, 0, 0, 1, -int(em * 0.055)))
        .filter(ImageFilter.GaussianBlur(em * 0.045)),
        TITRE_OMBRE, 0.78)
    # 2) halo chaud large derrière la lettre
    halo = _couche_unie(mask.filter(ImageFilter.GaussianBlur(em * 0.10)),
                        TITRE_HALO, 0.30)
    # 3) remplissage dégradé ivoire→or via masque (colonne 1px étirée : rapide)
    colonne = Image.new("RGBA", (1, mask.size[1]))
    px_haut, px_bas = TITRE_OR_HAUT, TITRE_OR_BAS
    for y in range(mask.size[1]):
        k = y / max(1, mask.size[1] - 1)
        c = tuple(int(px_haut[i] + (px_bas[i] - px_haut[i]) * k) for i in range(3))
        colonne.putpixel((0, y), c + (255,))
    degrade = colonne.resize(mask.size)
    degrade.putalpha(mask)
    # 4) biseau ciselé : liseré lumineux haut/gauche, arête sombre bas/droite
    decale_bdr = mask.transform(mask.size, Image.AFFINE, (1, 0, -2, 0, 1, -2))
    decale_hg = mask.transform(mask.size, Image.AFFINE, (1, 0, 2, 0, 1, 2))
    biseau_clair = _couche_unie(ImageChops.subtract(mask, decale_bdr),
                                TITRE_BISEAU_CLAIR, 0.85)
    biseau_sombre = _couche_unie(ImageChops.subtract(mask, decale_hg),
                                 TITRE_BISEAU_SOMBRE, 0.65)

    tuile = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    for calque in (ombre, halo, degrade, biseau_clair, biseau_sombre):
        tuile = Image.alpha_composite(tuile, calque)
    return tuile, ancre[0], ancre[1]


class _BlocTitre:
    """Bloc titre prêt à animer : tuiles de glyphes pré-rendues + ornement.

    Une fois construit (coût : quelques dizaines de ms par glyphe), composer
    une trame coûte seulement des collages — la beauté est cuite dans les
    tuiles (dégradé, biseau, halo, ombre) et l'animation reste fluide.
    """

    def __init__(self, lignes, chemin_police: str, largeur_max: int = 1575,
                 hauteur: int = 1080):
        from PIL import ImageFont

        self.lignes = [l.upper() for l in lignes]
        # taille auto : la ligne la plus large doit tenir à l'interlettrage FINAL
        taille_test = 200
        font_test = ImageFont.truetype(chemin_police, taille_test)
        ligne_ref = max(self.lignes, key=lambda l: self._largeur(font_test, l, _TRACK_FIN_EM, taille_test))
        largeur_test = self._largeur(font_test, ligne_ref, _TRACK_FIN_EM, taille_test)
        self.em = max(80, int(taille_test * largeur_max / largeur_test))
        self.font = ImageFont.truetype(chemin_police, self.em)
        self.hauteur = hauteur

        # tuiles + métriques par ligne (le glyphe espace n'a pas de tuile)
        self.tuiles, self.avances = [], []
        for ligne in self.lignes:
            tuiles_l, avances_l = [], []
            for glyphe in ligne:
                if glyphe == " ":
                    tuiles_l.append(None)
                else:
                    rendu = _tuile_glyphe(self.font, glyphe, self.em)
                    if rendu is None:
                        raise ValueError(
                            f"Glyphe « {glyphe} » absent de {chemin_police} "
                            "(accents non couverts ?)")
                    tuiles_l.append(rendu)  # (tuile RGBA, dx, dy)
                avances_l.append(self.font.getlength(glyphe))
            self.tuiles.append(tuiles_l)
            self.avances.append(avances_l)

        # géométrie du bloc : ligne 1 / ornement / ligne 2, centré à 45 % du cadre
        # (retouches QA 2026-09-10 : ciel plus calme que la maçonnerie du donjon,
        # écart plus généreux AU-DESSUS de l'ornement pour équilibrer le rythme)
        cap = self.em * 0.72
        cy = hauteur * 0.45
        self.haut_bloc = cy - (cap * 2 + self.em * 0.94) / 2
        self.y_ligne1 = self.haut_bloc
        self.y_ornement = self.haut_bloc + cap + self.em * 0.42
        self.y_ligne2 = self.y_ornement + self.em * 0.52
        # ornement calé sur la largeur finale de la dernière ligne (charnière
        # visuelle entre la ligne large et la ligne étroite — QA 2026-09-10)
        if len(self.avances) > 1:
            largeur_l2 = sum(self.avances[-1]) + _TRACK_FIN_EM * self.em * max(0, len(self.avances[-1]) - 1)
            self.demi_filet = int(min(max(largeur_l2 / 2 * 1.05, self.em * 0.6), 900))
        else:
            self.demi_filet = int(self.em * 1.35)
        self.demi_losange = max(6, int(self.em * 0.085))

        # vignette de contraste derrière le bloc (assombrissement radial doux)
        import numpy as np
        yy, xx = np.mgrid[0:hauteur, 0:1920].astype(np.float32)
        d = np.sqrt(((xx - 960) / 1150.0) ** 2 + ((yy - cy) / 330.0) ** 2)
        alpha = np.clip(1.0 - d, 0.0, 1.0) ** 2.0 * 88.0
        self.vignette = np.dstack([
            np.full((hauteur, 1920), TITRE_VIGNETTE[0], np.uint8),
            np.full((hauteur, 1920), TITRE_VIGNETTE[1], np.uint8),
            np.full((hauteur, 1920), TITRE_VIGNETTE[2], np.uint8),
            alpha.astype(np.uint8)])

    def _largeur(self, font, ligne: str, track_em: float, em: int) -> float:
        n = len(ligne)
        return sum(font.getlength(c) for c in ligne) + track_em * em * max(0, n - 1)

    def _positions_ligne(self, i_ligne: int, track_px: float):
        """Positions x (bord gauche) et y (haut de tuile) de chaque glyphe."""
        avances = self.avances[i_ligne]
        largeur = sum(avances) + track_px * max(0, len(avances) - 1)
        x = (1920 - largeur) / 2
        y = self.y_ligne1 if i_ligne == 0 else self.y_ligne2
        pos = []
        for j, avance in enumerate(avances):
            pos.append((x, y))
            x += avance + track_px
        return pos

    def composer(self, t: float) -> "Image.Image":
        """Compose le bloc titre à l'instant t sur un RGBA 1920×hauteur transparent."""
        from PIL import Image, ImageDraw

        a_global = _smooth((t - _T_FADE_DEBUT) / (_T_FADE_FIN - _T_FADE_DEBUT))
        canvas = Image.new("RGBA", (1920, self.hauteur), (0, 0, 0, 0))
        if a_global <= 0.001:
            return canvas

        track_px = (_TRACK_DEBUT_EM + (_TRACK_FIN_EM - _TRACK_DEBUT_EM)
                    * _smooth((t - _T_TRACK_DEBUT) / (_T_TRACK_FIN - _T_TRACK_DEBUT))) * self.em
        dy_monte = _MONTEE_PX * (1.0 - _smooth((t - _T_FADE_DEBUT) / (_T_MONTEE_FIN - _T_FADE_DEBUT)))

        # vignette de contraste (alpha global uniquement, pas de stagger)
        vignette = Image.fromarray(self.vignette, "RGBA").copy()
        if a_global < 0.999:
            r, g, b, a = vignette.split()
            vignette = Image.merge("RGBA", (r, g, b, a.point(lambda v: int(v * a_global))))
        canvas = Image.alpha_composite(canvas, vignette)

        # glyphes : vague de stagger gauche→droite sur tout le bloc
        index = 0
        for i_ligne in range(len(self.lignes)):
            for (x, y), rendu in zip(self._positions_ligne(i_ligne, track_px), self.tuiles[i_ligne]):
                if rendu is not None:
                    tuile, dx, dy = rendu
                    a_glyphe = a_global * _smooth(
                        (t - _T_FADE_DEBUT - index * _T_STAGGER) / (_T_FADE_FIN - _T_FADE_DEBUT))
                    if a_glyphe > 0.003:
                        if a_glyphe < 0.999:
                            r, g, b, a = tuile.split()
                            tuile = Image.merge("RGBA", (r, g, b, a.point(lambda v: int(v * a_glyphe))))
                        canvas.alpha_composite(tuile, (int(x + dx), int(y + dy + dy_monte)))
                index += 1

        # ornement : filets qui se déploient depuis le centre + losange
        a_orn = a_global * _smooth((t - _T_ORN_DEBUT) / (_T_ORN_ALPHA_FIN - _T_ORN_DEBUT))
        if a_orn > 0.003:
            longueur = self.demi_filet * _smooth((t - _T_ORN_DEBUT) / (_T_ORN_CROISSANCE_FIN - _T_ORN_DEBUT))
            cx, cy_orn = 960, int(self.y_ornement + dy_monte)
            dessin = ImageDraw.Draw(canvas)
            iv = int(255 * a_orn)
            ombre_a = int(110 * a_orn)
            for signe in (-1, 1):
                xa = int(cx + signe * (self.demi_losange + 4))
                xb = int(cx + signe * longueur)
                x1, x2 = min(xa, xb), max(xa, xb)
                # ombre du filet puis filet or avec cœur ivoire
                dessin.rectangle((x1, cy_orn + 3, x2, cy_orn + 5), fill=TITRE_OMBRE + (ombre_a,))
                dessin.rectangle((x1, cy_orn - 1, x2, cy_orn + 1), fill=TITRE_ORNEMENT_OR + (iv,))
                dessin.rectangle((x1, cy_orn, x2, cy_orn), fill=TITRE_ORNEMENT_IVOIRE + (iv,))
                # point doré au bout du filet
                dessin.rectangle((xb - 2, cy_orn - 2, xb + 2, cy_orn + 2),
                                 fill=TITRE_ORNEMENT_OR + (iv,))
            d = self.demi_losange
            dessin.polygon([(cx, cy_orn - d), (cx + d, cy_orn), (cx, cy_orn + d), (cx - d, cy_orn)],
                           fill=TITRE_ORNEMENT_IVOIRE + (iv,), outline=TITRE_BISEAU_SOMBRE + (iv,))
        return canvas


def rendre_titre_beau(fond_png: str, lignes, sortie_png: str,
                      chemin_police: str = POLICE_DEFAUT_TITRE) -> str:
    """Rendu STILL du bloc titre en pleine beauté sur un fond (QA / planches)."""
    from PIL import Image

    fond = Image.open(fond_png).convert("RGBA")
    bloc = _BlocTitre(lignes, chemin_police)
    fond = Image.alpha_composite(fond, bloc.composer(t=1e9))
    fond.convert("RGB").save(sortie_png, quality=100)
    return sortie_png


def extraire_derniere_trame(video: str, png: str) -> str:
    """Extrait la toute dernière trame d'une vidéo en PNG haute qualité."""
    subprocess.run(
        [FFMPEG_PATH, "-y", "-v", "error", "-sseof", "-0.1", "-i", video,
         "-update", "1", "-frames:v", "1", "-q:v", "1", png],
        capture_output=True, check=True,
    )
    if not os.path.exists(png):
        raise RuntimeError(f"Extraction de la dernière trame échouée : {video}")
    return png


def construire_carton_titre(
    image_png: str,
    lignes,
    sortie: str,
    duree: float = 6.0,
    fps: int = 48,
    zoom_abs_debut: float = 1.32,
    zoom_abs_fin: float = 1.36,
    ancre: Tuple[float, float] = (ANCRE_X, ANCRE_Y),
    chemin_police: str = POLICE_DEFAUT_TITRE,
    fondu_sortie: float = 1.5,
    log_fn: Callable[[str], None] = print,
) -> str:
    """Carton de fin : image figée + zoom pur qui POURSUIT le monoplan + titre
    haute couture animé (fondu + vague + interlettrage + ornement).

    Le zoom est exprimé en valeurs absolues (ex. 1.32→1.36 après un monoplan
    terminé à 1.32) : la trame extraite est déjà au zoom de départ, le warp
    applique donc le ratio z(t)/z(0) — même math que zoom_pur, zéro vibration.
    """
    import cv2
    import numpy as np
    from PIL import Image

    for candidat_police in (chemin_police, POLICE_REPLI_TITRE):
        try:
            bloc = _BlocTitre(lignes, candidat_police)
            if candidat_police != chemin_police:
                log_fn(f"[cinéma] Police de repli utilisée : {candidat_police}")
            break
        except ValueError as err:
            log_fn(f"[cinéma] {err}")
            bloc = None
    if bloc is None:
        raise RuntimeError("Aucune police utilisable pour le titre (accents manquants).")

    fond = cv2.imread(image_png)
    if fond is None:
        raise FileNotFoundError(f"Image introuvable : {image_png}")
    H, W = fond.shape[:2]
    centre = (ancre[0] * W, ancre[1] * H)

    n = int(round(duree * fps))
    rapport = zoom_abs_fin / zoom_abs_debut  # warp relatif sur la trame figée
    tmp = tempfile.mkdtemp(prefix="cinema_carton_")
    t0 = time.time()
    try:
        for i in range(n):
            t = i / fps
            ease = _smooth(i / max(1, n - 1))
            k = 1.0 / rapport ** ease  # zoom in continu : 1 → 1/rapport
            tx = centre[0] * (1.0 - k)
            ty = centre[1] * (1.0 - k)
            tx = min(max(tx, min(0.0, W * (1 - k))), max(0.0, W * (1 - k)))
            ty = min(max(ty, min(0.0, H * (1 - k))), max(0.0, H * (1 - k)))
            M = np.array([[k, 0.0, tx], [0.0, k, ty]], dtype=np.float64)
            trame = cv2.warpAffine(fond, M, (W, H), flags=cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP)
            pil = Image.fromarray(cv2.cvtColor(trame, cv2.COLOR_BGR2RGB)).convert("RGBA")
            pil = Image.alpha_composite(pil, bloc.composer(t))
            bgr = cv2.cvtColor(np.array(pil.convert("RGB")), cv2.COLOR_RGB2BGR)
            cv2.imwrite(os.path.join(tmp, "s_%04d.png" % (i + 1)), bgr,
                        [cv2.IMWRITE_PNG_COMPRESSION, 3])
            if (i + 1) % 48 == 0:
                log_fn("[cinéma] Carton : trame {}/{} ({:.0f} %)".format(
                    i + 1, n, 100 * (i + 1) / n))
        log_fn(f"[cinéma] {n} trames composées en {time.time() - t0:.1f} s.")
        args = [FFMPEG_PATH, "-y", "-v", "error", "-framerate", str(fps),
                "-start_number", "1", "-i", os.path.join(tmp, "s_%04d.png"),
                "-frames:v", str(n)]
        if fondu_sortie > 0:
            args += ["-vf", f"fade=t=out:st={max(0.0, duree - fondu_sortie):.3f}:d={fondu_sortie},format=yuv420p"]
        else:
            args += ["-vf", "format=yuv420p"]
        args += ["-c:v", "libx264", "-crf", "16", sortie]
        subprocess.run(args, capture_output=True, check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if not os.path.exists(sortie):
        raise RuntimeError(f"Carton non produit : {sortie}")
    return sortie


def etendre_ambiance(wav: str, duree_totale: float, sortie: str,
                     fondu_sortie: float = 2.5) -> str:
    """Étend/recoupe un lit d'ambiance à la durée exacte voulue, fondu de sortie
    compris (boucle interne si la source est trop courte — transparent ici)."""
    st = max(0.0, duree_totale - fondu_sortie)
    ok = subprocess.run(
        [FFMPEG_PATH, "-y", "-v", "error", "-stream_loop", "-1", "-i", wav,
         "-t", f"{duree_totale:.3f}",
         "-af", f"afade=t=out:st={st:.3f}:d={fondu_sortie:.3f}",
         "-c:a", "pcm_s16le", sortie],
        capture_output=True,
    ).returncode == 0
    if not ok or not os.path.exists(sortie):
        raise RuntimeError(f"Extension d'ambiance échouée : {sortie}")
    return sortie


def assembler_finale(base_video: str, carton_video: str, wav_etendu: Optional[str],
                     sortie: str, fps: int = 48) -> str:
    """Assemblage en une passe : base + carton (concat filtre) + ambiance étendue
    (wav_etendu = None pour une finale muette)."""
    args = [FFMPEG_PATH, "-y", "-v", "error", "-i", base_video, "-i", carton_video]
    if wav_etendu:
        args += ["-i", wav_etendu]
    args += ["-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]"]
    if wav_etendu:
        args += ["-map", "[v]", "-map", "2:a", "-c:a", "aac", "-b:a", "256k"]
    else:
        args += ["-map", "[v]", "-an"]
    args += ["-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-r", str(fps),
             "-movflags", "+faststart", sortie]
    subprocess.run(args, capture_output=True, check=True)
    if not os.path.exists(sortie):
        raise RuntimeError(f"Assemblage final échoué : {sortie}")
    return sortie
