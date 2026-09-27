#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core/cinema.py — AI single-take shot ("monoplan") (user-VALIDATED on 2026-09-10).

Winning recipe (MEMORY_BANK §1.17, Vent-Gris intro "L'HÉRITIER DU VIDE"):
a SINGLE LTX-2.5 I2V generation from a seed image (65 frames = stable GPU
ceiling), slowed down to the target duration with motion-compensated
interpolation, then re-framed by a DESIGNED pure zoom (monotone ramp with easing
— no tracking inside the warp: the NCC tracker would inject its translation
noise). Result: one single shot with no cuts and no camera vibration.

Why not longer/multi-shot: I2V chaining creates content cuts
(clouds/waves reinterpreted → jerks, all v2-v5 repairs rejected),
and LTX's internal `ltxav` module eats ~29 MB of VRAM per frame (ceiling
~81 frames at 832×480 on RX 6950 XT). Slow motion is therefore THE duration lever.
"""

import os
import shutil
import tempfile
import time
from typing import Callable, Optional, Tuple

from PIL import Image

from core.config import DEFAULT_MODEL_DIR, DEFAULT_SD_CLI, DEFAULT_FFMPEG as FFMPEG_PATH
from core.process import run_engine

# Validated LTX-2.5 Distilled models (§1.1 / §1.17)
LTX_DIT = os.path.join(DEFAULT_MODEL_DIR, "LTX-2.5-Distilled-Q4_K_M.gguf")
LTX_VAE = os.path.join(DEFAULT_MODEL_DIR, "ltx-2.5-video-vae-conv-bf16.safetensors")
LTX_LLM = os.path.join(DEFAULT_MODEL_DIR, "gemma4-12b-with-proj-ltx-2.5-Q5_K_M.gguf")

# Official Lightricks distilled sigmas (8 steps, cfg 1.0 = 1 pass/step)
SIGMAS_LTX = "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"

NEGATIF_DEFAUT = (
    "text, watermark, logo, subtitles, warm colors, autumn colors, sunny, cartoon, "
    "anime, modern elements, crowds, blurry, jitter, sudden cuts, glitch, low "
    "quality, noisy, distorted, morphing, lowres"
)

# Zoom anchor as a frame ratio (validated on the Vent-Gris castle:
# main subject positioned slightly left of center)
ANCRE_X, ANCRE_Y = 0.656, 0.472

# 4K UHD "Hero Hooks" path (ai-doc2video spec, integrated on 2026-09-12):
# AI 4x upscale of the ONLY raw 480p frames (§1.17 — never from an interpolated
# master), slow-down + zoom at 3328×1920 (native 4x-UltraSharp output), then
# final 3840×2160 @ 30 fps conform with h264_amf + CAS.
TAILLE_UPSCALE_4X = (3328, 1920)   # 832×480 × 4 — native 4x-UltraSharp output
TAILLE_MASTER_4K = (3840, 2160)    # 4K UHD broadcast YouTube
FPS_SORTIE_4K = 30                 # Hero Hooks cadence (165 frames / 5.5 s)
BITRATE_MASTER_4K = "45M"          # 45-50 Mbps band of the broadcast spec
CAS_MASTER_4K = 0.75               # FidelityFX, same value as the validated 1080p zoom


def conformer_amorce_16_9(source: str, destination: str, largeur: int = 832,
                          hauteur: int = 480) -> str:
    """Exact 16:9 reframe + Lanczos resize (no distortion)."""
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
    """Single-take LTX-2.5 Distilled I2V shot (recipe §1.17, 8 steps euler_a, cfg 1.0)."""
    manquants = [p for p in (DEFAULT_SD_CLI, LTX_DIT, LTX_VAE, LTX_LLM) if not os.path.exists(p)]
    if manquants:
        raise FileNotFoundError("Missing LTX-2.5 models or sd-cli: " + "; ".join(manquants))
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
    log_fn("[cinema] LTX-2.5 single-take generation ({} frames @ {} fps, seed {})…".format(frames, fps, seed))
    # Uncaptured output: sd-cli streams its progress live; 7200 s = MEMORY_BANK
    # video benchmark (65 frames ~ minutes, ×3 margin for slow days)
    run_engine(commande, capture=False, check=True, timeout=7200, etiquette="sd-cli LTX")
    if not os.path.exists(sortie):
        candidat = sortie.replace(".webm", "_0.webm")
        if os.path.exists(candidat):
            os.rename(candidat, sortie)
    if not os.path.exists(sortie):
        raise RuntimeError(f"Single-take shot not produced: {sortie}")
    return sortie


def ralentir_interp(webm: str, sortie: str, duree_cible: float, fps: int = 24,
                    taille: Optional[Tuple[int, int]] = (1920, 1080)) -> Tuple[str, int]:
    """Temporal slow-down to the target duration + motion-compensated
    interpolation + lanczos upscale to `taille` (the zoom step then works in
    those coordinates). taille=None keeps the source resolution: that is the
    4K path, where the input is already the 3328×1920 AI-upscaled master (no
    software lanczos before the zoom — the UltraSharp sharpness must stay intact)."""
    info = run_engine(
        [FFMPEG_PATH, "-i", webm], check=False, timeout=120,
        etiquette="ffmpeg probe duration",
    ).stderr
    import re
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", info)
    if not m:
        raise RuntimeError(f"Unreadable duration: {webm}")
    duree_src = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    facteur = duree_cible / max(duree_src, 0.1)
    filtre = (f"setpts={facteur:.4f}*PTS,"
              f"minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1")
    if taille:
        filtre += f",scale={taille[0]}:{taille[1]}:flags=lanczos"
    ok = run_engine(
        [FFMPEG_PATH, "-y", "-v", "error", "-i", webm, "-vf", filtre,
         "-an", "-c:v", "libx264", "-crf", "12", "-preset", "slow",
         "-pix_fmt", "yuv420p", sortie],
        check=False, timeout=3600, etiquette="ffmpeg slow-motion minterpolate",
    ).returncode == 0
    if not ok or not os.path.exists(sortie):
        raise RuntimeError(f"Slow-down/interpolation failed: {sortie}")
    return sortie, facteur


# Backward-compatible alias (production scripts §1.17/§1.18: finir_monoplan_intro,
# faire_boucle_menu_vent_gris, lancement_nuit_intro_vent_gris)
ralentir_interp_1080p = ralentir_interp


def zoom_pur(video: str, sortie: str, zoom_debut: float = 1.10,
             zoom_fin: float = 1.32, ancre: Tuple[float, float] = (ANCRE_X, ANCRE_Y),
             cas: float = 0.75, taille: Tuple[int, int] = (1920, 1080),
             fps: int = 24) -> str:
    """DESIGNED zoom ramp (smootherstep) around a fixed anchor — no tracking
    measurement inside the warp: the render is unable to vibrate by construction.
    `taille`/`fps` follow the working resolution (1920×1080/24 by default;
    3328×1920/30 on the 4K path). `cas=0` defers the FidelityFX sharpness to the
    final conform (avoids double sharpening before the 3840×2160 lanczos)."""
    import cv2
    import numpy as np

    tmp = tempfile.mkdtemp(prefix="cinema_zoom_")
    try:
        run_engine(
            [FFMPEG_PATH, "-y", "-v", "error", "-i", video, "-fps_mode", "passthrough",
             "-q:v", "2", os.path.join(tmp, "f_%04d.png")],
            check=True, timeout=600, etiquette="ffmpeg frame extraction",
        )
        pngs = sorted(f for f in os.listdir(tmp) if f.startswith("f_"))
        n = len(pngs)
        W, H = taille
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
        run_engine(
            [FFMPEG_PATH, "-y", "-v", "error", "-framerate", str(fps), "-start_number", "1",
             "-i", os.path.join(tmp, "s_%04d.png"), "-frames:v", str(n),
             "-vf", "format=yuv420p" + filtre_cas,
             "-c:v", "libx264", "-crf", "16", sortie],
            check=True, timeout=1800, etiquette="ffmpeg zoom encode",
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return sortie


def master_brut_4k(webm: str, sortie: str, modele: Optional[str] = None,
                   bitrate: str = "50M",
                   log_fn: Callable[[str], None] = print) -> str:
    """Raw 4x AI super-resolution master (scripts/upscale_video_ai.py chain):
    extraction of the raw 480p frames → 4x-UltraSharp frame by frame on Vulkan
    (sd-cli, ~6.9 s/frame measured on RX 6950 XT) → reassembly at the native
    4x resolution (832×480 → 3328×1920), audio track preserved.

    §1.17 rule: the AI upscale is ALWAYS done on the raw 480p, NEVER on an
    interpolated master (65 frames ≈ 7-8 min GPU here, vs ~43 s/frame and 3 h
    if sourced from 1080p — the network's pixel budget is calibrated for 480p)."""
    import cv2
    from scripts.upscale_video_ai import DEFAULT_MODEL as MODELE_UPSCALE_DEFAUT
    from scripts.upscale_video_ai import upscale_video_ai
    from core.config import resoudre_upscaler

    if not os.path.exists(webm):
        raise FileNotFoundError(f"Raw single-take shot not found: {webm}")
    cap = cv2.VideoCapture(webm)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open the raw single-take shot: {webm}")
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    if (w, h) != (832, 480):
        log_fn(f"[cinema] Source {w}×{h} (validated recipe: 832×480) — 4x target: {w * 4}×{h * 4}.")
    modele = modele or resoudre_upscaler("4x-UltraSharp") or MODELE_UPSCALE_DEFAUT
    return upscale_video_ai(
        input_video=webm,
        output_video=sortie,
        upscaler_model=modele,
        target_res=f"{w * 4}:{h * 4}",
        bitrate=bitrate,
        cas_strength=0.0,  # sharpness applied only once, at the 4K conform
    )


def conformer_master_4k(source: str, sortie: str, fps: int = FPS_SORTIE_4K,
                        bitrate: str = BITRATE_MASTER_4K, cas: float = CAS_MASTER_4K,
                        taille: Tuple[int, int] = TAILLE_MASTER_4K) -> str:
    """4K UHD broadcast master conform (ai-doc2video Hero Hooks spec):
    lanczos to 3840×2160 + FidelityFX CAS, AMD AMF hardware encoding (h264_amf)
    — the 4K master forces YouTube's high-bitrate VP09/AV01 profile even in
    1080p playback (README §4.10)."""
    os.makedirs(os.path.dirname(os.path.abspath(sortie)), exist_ok=True)
    filtre = f"scale={taille[0]}:{taille[1]}:flags=lanczos"
    if cas:
        filtre += f",cas={cas}"
    ok = run_engine(
        [FFMPEG_PATH, "-y", "-v", "error", "-i", source, "-vf", filtre,
         "-c:v", "h264_amf", "-b:v", bitrate, "-pix_fmt", "yuv420p",
         "-r", str(fps), "-movflags", "+faststart", sortie],
        check=False, timeout=1800, etiquette="ffmpeg conform 4K AMF",
    ).returncode == 0
    if not ok or not os.path.exists(sortie):
        raise RuntimeError(f"4K master conform failed: {sortie}")
    return sortie


def muxer_audio(video: str, wav: str, sortie: str) -> str:
    """Glues an audio track (sound bed) onto the video, video stream copied as-is."""
    run_engine(
        [FFMPEG_PATH, "-y", "-v", "error", "-i", video, "-i", wav,
         "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", sortie],
        check=True, timeout=600, etiquette="ffmpeg mux audio",
    )
    return sortie


def generer_lit_ambiance(prompt: str, duree: float, seed: int = 42,
                         chemin_wav: Optional[str] = None) -> str:
    """Sound bed via the validated AI SFX engine (SA3 Small, normalization included).
    Writes a mux-ready WAV (and its Godot OGG next to it if chemin_wav is given)."""
    import numpy as np
    import soundfile as sf
    from core.sfx_ia import generer_sfx_ia

    res = generer_sfx_ia(prompt, duree=duree, seed=seed)
    if chemin_wav is None:
        fd, chemin_wav = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
    sf.write(chemin_wav, res["audio"], res["sr"], subtype="PCM_16", format="WAV")
    if res["rognage_pct"] > 0.01:
        # trim structural silences like the sfx workflow (± 50% safety cap)
        audio = res["audio"]
        seuil = 0.0056  # ≈ −45 dBFS
        actifs = np.where(np.abs(audio).max(axis=1) > seuil)[0]
        if len(actifs) and (actifs[-1] - actifs[0]) > len(audio) * 0.5:
            audio = audio[actifs[0]:actifs[-1] + 1]
            sf.write(chemin_wav, audio, res["sr"], subtype="PCM_16", format="WAV")
    return chemin_wav


# ---------------------------------------------------------------------------
# "Haute couture" title card (frozen image + animated title, user requirement
# 2026-09-10: the title must look VERY beautiful graphically).
# Multi-layer Pillow processing: ivory→gold gradient, chiseled bevel, warm
# halo, deep drop shadow, contrast vignette, rule+diamond ornament.
# ---------------------------------------------------------------------------

# Title palette (matched to the winter castle: antique gold on storm sky)
TITRE_OR_HAUT = (247, 240, 223)     # warm ivory (top of the gradient)
TITRE_OR_BAS = (201, 169, 106)      # antique gold (bottom of the gradient)
TITRE_BISEAU_CLAIR = (255, 252, 240)
TITRE_BISEAU_SOMBRE = (58, 40, 18)
TITRE_HALO = (247, 240, 223)
TITRE_OMBRE = (8, 14, 26)
TITRE_VIGNETTE = (6, 10, 20)
TITRE_ORNEMENT_OR = (201, 169, 106)
TITRE_ORNEMENT_IVOIRE = (240, 232, 210)

POLICE_DEFAUT_TITRE = r"C:\Windows\Fonts\FELIXTI.TTF"    # Felix Titling (inscriptional capitals)
POLICE_REPLI_TITRE = r"C:\Windows\Fonts\georgia.ttf"     # fallback if a glyph is missing

# Reveal chronology (seconds, 6 s title card)
_T_FADE_DEBUT, _T_FADE_FIN = 0.7, 2.2          # global fade of the block
_T_STAGGER = 0.035                             # per-glyph offset (left→right wave)
_TRACK_DEBUT_EM, _TRACK_FIN_EM = 0.12, 0.22    # letter tracking start→end (in em)
_T_TRACK_DEBUT, _T_TRACK_FIN = 0.7, 3.4
_T_MONTEE_FIN = 2.6                            # end of the block's soft rise
_T_ORN_DEBUT = 1.4                             # ornament appearance
_T_ORN_ALPHA_FIN, _T_ORN_CROISSANCE_FIN = 2.4, 2.8
_MONTEE_PX = 15.0


def _smooth(u: float) -> float:
    """Clamped smootherstep (same curve as the zoom_pur ramp)."""
    u = 0.0 if u < 0.0 else (1.0 if u > 1.0 else u)
    return u * u * u * (u * (u * 6.0 - 15.0) + 10.0)


def _duree_media(chemin: str) -> float:
    """Media duration via the ffmpeg stderr header (slow-down pattern §1.17)."""
    import re
    info = run_engine(
        [FFMPEG_PATH, "-i", chemin], check=False, timeout=120,
        etiquette="ffmpeg probe duration",
    ).stderr
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", info)
    if not m:
        raise RuntimeError(f"Unreadable duration: {chemin}")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def _couche_unie(mask, couleur, intensite: float):
    """Uniform RGBA layer whose alpha = L mask × intensity (0..1)."""
    alpha = mask.point(lambda v: int(v * intensite))
    calque = Image.new("RGBA", mask.size, couleur + (0,))
    calque.putalpha(alpha)
    return calque


def _tuile_glyphe(font, glyphe: str, em: int):
    """Renders ONE glyph into an RGBA tile: shadow + halo + gold gradient + chiseled bevel.

    Returns (tile, dx, dy) — dx/dy = ink anchor relative to the drawing
    origin, to keep baselines aligned between accented (É) and non-accented
    glyphs. Returns None if the glyph is missing from the font.
    """
    from PIL import ImageChops, ImageDraw, ImageFilter

    marge = int(em * 0.45) + 4
    canvas = Image.new("L", (em + 2 * marge, em + 2 * marge), 0)
    dessin = ImageDraw.Draw(canvas)
    dessin.text((marge, marge), glyphe, font=font, fill=255)
    boite = canvas.getbbox()
    if not boite:
        return None  # glyph missing from the font (e.g. missing accent)
    x0, y0, x1, y1 = boite
    x0, y0 = max(0, x0 - marge // 2), max(0, y0 - marge // 2)
    x1, y1 = min(canvas.width, x1 + marge // 2), min(canvas.height, y1 + marge // 2)
    ancre = (x0 - marge, y0 - marge)
    mask = canvas.crop((x0, y0, x1, y1))

    # 1) deep drop shadow (blue-black, blurred, shifted down)
    ombre = _couche_unie(
        mask.transform(mask.size, Image.AFFINE, (1, 0, 0, 0, 1, -int(em * 0.055)))
        .filter(ImageFilter.GaussianBlur(em * 0.045)),
        TITRE_OMBRE, 0.78)
    # 2) wide warm halo behind the letter
    halo = _couche_unie(mask.filter(ImageFilter.GaussianBlur(em * 0.10)),
                        TITRE_HALO, 0.30)
    # 3) ivory→gold gradient fill via mask (stretched 1px column: fast)
    colonne = Image.new("RGBA", (1, mask.size[1]))
    px_haut, px_bas = TITRE_OR_HAUT, TITRE_OR_BAS
    for y in range(mask.size[1]):
        k = y / max(1, mask.size[1] - 1)
        c = tuple(int(px_haut[i] + (px_bas[i] - px_haut[i]) * k) for i in range(3))
        colonne.putpixel((0, y), c + (255,))
    degrade = colonne.resize(mask.size)
    degrade.putalpha(mask)
    # 4) chiseled bevel: bright top/left rim, dark bottom/right edge
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
    """Title block ready to animate: pre-rendered glyph tiles + ornament.

    Once built (cost: a few tens of ms per glyph), composing a frame costs
    only pastes — the beauty is baked into the tiles (gradient, bevel, halo,
    shadow) and the animation stays smooth.
    """

    def __init__(self, lignes, chemin_police: str, largeur_max: int = 1575,
                 hauteur: int = 1080, largeur: int = 1920):
        from PIL import ImageFont

        self.lignes = [ligne.upper() for ligne in lignes]
        self.largeur = largeur
        # scale factor of the fixed metrics (ornament strokes, vignette):
        # 1.0 at 1080p (validated render unchanged), 2.0 at 4K
        self.facteur = largeur / 1920.0
        # auto size: the widest line must fit at the FINAL letter tracking
        taille_test = 200
        font_test = ImageFont.truetype(chemin_police, taille_test)
        ligne_ref = max(self.lignes, key=lambda ligne: self._largeur(font_test, ligne, _TRACK_FIN_EM, taille_test))
        largeur_test = self._largeur(font_test, ligne_ref, _TRACK_FIN_EM, taille_test)
        self.em = max(80, int(taille_test * largeur_max / largeur_test))
        self.font = ImageFont.truetype(chemin_police, self.em)
        self.hauteur = hauteur

        # tiles + metrics per line (the space glyph has no tile)
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
                            f"Glyph '{glyphe}' missing from {chemin_police} "
                            "(accents not covered?)")
                    tuiles_l.append(rendu)  # (RGBA tile, dx, dy)
                avances_l.append(self.font.getlength(glyphe))
            self.tuiles.append(tuiles_l)
            self.avances.append(avances_l)

        # block geometry: line 1 / ornament / line 2, centered at 45% of the frame
        # (QA touch-ups 2026-09-10: calmer sky than the keep masonry, more
        # generous gap ABOVE the ornament to balance the rhythm)
        cap = self.em * 0.72
        cy = hauteur * 0.45
        self.haut_bloc = cy - (cap * 2 + self.em * 0.94) / 2
        self.y_ligne1 = self.haut_bloc
        self.y_ornement = self.haut_bloc + cap + self.em * 0.42
        self.y_ligne2 = self.y_ornement + self.em * 0.52
        # ornament fitted to the final width of the last line (visual hinge
        # between the wide line and the narrow line — QA 2026-09-10)
        if len(self.avances) > 1:
            largeur_l2 = sum(self.avances[-1]) + _TRACK_FIN_EM * self.em * max(0, len(self.avances[-1]) - 1)
            self.demi_filet = int(min(max(largeur_l2 / 2 * 1.05, self.em * 0.6), 900 * self.facteur))
        else:
            self.demi_filet = int(self.em * 1.35)
        self.demi_losange = max(6, int(self.em * 0.085))

        # contrast vignette behind the block (soft radial darkening)
        import numpy as np
        yy, xx = np.mgrid[0:hauteur, 0:largeur].astype(np.float32)
        d = np.sqrt(((xx - largeur / 2) / (1150.0 * self.facteur)) ** 2
                    + ((yy - cy) / (330.0 * self.facteur)) ** 2)
        alpha = np.clip(1.0 - d, 0.0, 1.0) ** 2.0 * 88.0
        self.vignette = np.dstack([
            np.full((hauteur, largeur), TITRE_VIGNETTE[0], np.uint8),
            np.full((hauteur, largeur), TITRE_VIGNETTE[1], np.uint8),
            np.full((hauteur, largeur), TITRE_VIGNETTE[2], np.uint8),
            alpha.astype(np.uint8)])

    def _largeur(self, font, ligne: str, track_em: float, em: int) -> float:
        n = len(ligne)
        return sum(font.getlength(c) for c in ligne) + track_em * em * max(0, n - 1)

    def _positions_ligne(self, i_ligne: int, track_px: float):
        """x positions (left edge) and y positions (tile top) of each glyph."""
        avances = self.avances[i_ligne]
        largeur = sum(avances) + track_px * max(0, len(avances) - 1)
        x = (self.largeur - largeur) / 2
        y = self.y_ligne1 if i_ligne == 0 else self.y_ligne2
        pos = []
        for j, avance in enumerate(avances):
            pos.append((x, y))
            x += avance + track_px
        return pos

    def composer(self, t: float) -> "Image.Image":
        """Composes the title block at time t onto a transparent 1920×height RGBA."""
        from PIL import Image, ImageDraw

        a_global = _smooth((t - _T_FADE_DEBUT) / (_T_FADE_FIN - _T_FADE_DEBUT))
        canvas = Image.new("RGBA", (self.largeur, self.hauteur), (0, 0, 0, 0))
        if a_global <= 0.001:
            return canvas

        track_px = (_TRACK_DEBUT_EM + (_TRACK_FIN_EM - _TRACK_DEBUT_EM)
                    * _smooth((t - _T_TRACK_DEBUT) / (_T_TRACK_FIN - _T_TRACK_DEBUT))) * self.em
        dy_monte = _MONTEE_PX * (1.0 - _smooth((t - _T_FADE_DEBUT) / (_T_MONTEE_FIN - _T_FADE_DEBUT)))

        # contrast vignette (global alpha only, no stagger)
        vignette = Image.fromarray(self.vignette, "RGBA").copy()
        if a_global < 0.999:
            r, g, b, a = vignette.split()
            vignette = Image.merge("RGBA", (r, g, b, a.point(lambda v: int(v * a_global))))
        canvas = Image.alpha_composite(canvas, vignette)

        # glyphs: left→right stagger wave across the whole block
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

        # ornament: rules deploying from the center + diamond
        a_orn = a_global * _smooth((t - _T_ORN_DEBUT) / (_T_ORN_ALPHA_FIN - _T_ORN_DEBUT))
        if a_orn > 0.003:
            e = max(1, int(round(self.facteur)))  # stroke thickness (1 px at 1080p)
            longueur = self.demi_filet * _smooth((t - _T_ORN_DEBUT) / (_T_ORN_CROISSANCE_FIN - _T_ORN_DEBUT))
            cx, cy_orn = self.largeur // 2, int(self.y_ornement + dy_monte)
            dessin = ImageDraw.Draw(canvas)
            iv = int(255 * a_orn)
            ombre_a = int(110 * a_orn)
            for signe in (-1, 1):
                xa = int(cx + signe * (self.demi_losange + 4 * e))
                xb = int(cx + signe * longueur)
                x1, x2 = min(xa, xb), max(xa, xb)
                # rule shadow then gold rule with ivory core
                dessin.rectangle((x1, cy_orn + 3 * e, x2, cy_orn + 5 * e), fill=TITRE_OMBRE + (ombre_a,))
                dessin.rectangle((x1, cy_orn - e, x2, cy_orn + e), fill=TITRE_ORNEMENT_OR + (iv,))
                dessin.rectangle((x1, cy_orn - e + 1, x2, cy_orn + e - 1), fill=TITRE_ORNEMENT_IVOIRE + (iv,))
                # gold dot at the end of the rule
                dessin.rectangle((xb - 2 * e, cy_orn - 2 * e, xb + 2 * e, cy_orn + 2 * e),
                                 fill=TITRE_ORNEMENT_OR + (iv,))
            d = self.demi_losange
            dessin.polygon([(cx, cy_orn - d), (cx + d, cy_orn), (cx, cy_orn + d), (cx - d, cy_orn)],
                           fill=TITRE_ORNEMENT_IVOIRE + (iv,), outline=TITRE_BISEAU_SOMBRE + (iv,))
        return canvas


def rendre_titre_beau(fond_png: str, lignes, sortie_png: str,
                      chemin_police: str = POLICE_DEFAUT_TITRE) -> str:
    """STILL render of the title block in full beauty over a background (QA / contact sheets)."""
    from PIL import Image

    fond = Image.open(fond_png).convert("RGBA")
    largeur_cadre, hauteur_cadre = fond.size
    bloc = _BlocTitre(lignes, chemin_police, largeur_max=int(1575 * largeur_cadre / 1920),
                      hauteur=hauteur_cadre, largeur=largeur_cadre)
    fond = Image.alpha_composite(fond, bloc.composer(t=1e9))
    fond.convert("RGB").save(sortie_png, quality=100)
    return sortie_png


def extraire_derniere_trame(video: str, png: str) -> str:
    """Extracts the very last frame of a video into a high-quality PNG."""
    run_engine(
        [FFMPEG_PATH, "-y", "-v", "error", "-sseof", "-0.1", "-i", video,
         "-update", "1", "-frames:v", "1", "-q:v", "1", png],
        check=True, timeout=300, etiquette="ffmpeg last frame",
    )
    if not os.path.exists(png):
        raise RuntimeError(f"Last frame extraction failed: {video}")
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
    """End card: frozen image + pure zoom that CONTINUES the single-take shot +
    haute couture animated title (fade + wave + letter tracking + ornament).

    The zoom is expressed in absolute values (e.g. 1.32→1.36 after a single-take
    shot ending at 1.32): the extracted frame is already at the starting zoom,
    so the warp applies the ratio z(t)/z(0) — same math as zoom_pur, zero vibration.
    """
    import cv2
    import numpy as np
    from PIL import Image

    fond = cv2.imread(image_png)
    if fond is None:
        raise FileNotFoundError(f"Image not found: {image_png}")
    H, W = fond.shape[:2]
    centre = (ancre[0] * W, ancre[1] * H)

    # the title block adapts to the frame of the frozen frame (1920×1080 validated,
    # 3840×2160 on the 4K path — metrics ×2: em, vignette, ornament strokes)
    facteur_cadre = W / 1920.0
    for candidat_police in (chemin_police, POLICE_REPLI_TITRE):
        try:
            bloc = _BlocTitre(lignes, candidat_police,
                              largeur_max=int(1575 * facteur_cadre),
                              hauteur=H, largeur=W)
            if candidat_police != chemin_police:
                log_fn(f"[cinema] Fallback font used: {candidat_police}")
            break
        except ValueError as err:
            log_fn(f"[cinema] {err}")
            bloc = None
    if bloc is None:
        raise RuntimeError("No usable font for the title (missing accents).")

    n = int(round(duree * fps))
    rapport = zoom_abs_fin / zoom_abs_debut  # relative warp on the frozen frame
    tmp = tempfile.mkdtemp(prefix="cinema_carton_")
    t0 = time.time()
    try:
        for i in range(n):
            t = i / fps
            ease = _smooth(i / max(1, n - 1))
            k = 1.0 / rapport ** ease  # continuous zoom in: 1 → 1/rapport
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
                log_fn("[cinema] Title card: frame {}/{} ({:.0f} %)".format(
                    i + 1, n, 100 * (i + 1) / n))
        log_fn(f"[cinema] {n} frames composed in {time.time() - t0:.1f} s.")
        args = [FFMPEG_PATH, "-y", "-v", "error", "-framerate", str(fps),
                "-start_number", "1", "-i", os.path.join(tmp, "s_%04d.png"),
                "-frames:v", str(n)]
        if fondu_sortie > 0:
            args += ["-vf", f"fade=t=out:st={max(0.0, duree - fondu_sortie):.3f}:d={fondu_sortie},format=yuv420p"]
        else:
            args += ["-vf", "format=yuv420p"]
        args += ["-c:v", "libx264", "-crf", "16", sortie]
        run_engine(args, check=True, timeout=1800, etiquette="ffmpeg title card encode")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if not os.path.exists(sortie):
        raise RuntimeError(f"Title card not produced: {sortie}")
    return sortie


def etendre_ambiance(wav: str, duree_totale: float, sortie: str,
                     fondu_sortie: float = 2.5) -> str:
    """Extends/trims an ambience bed to the exact wanted duration, output fade
    included (internal looping if the source is too short — transparent here)."""
    st = max(0.0, duree_totale - fondu_sortie)
    ok = run_engine(
        [FFMPEG_PATH, "-y", "-v", "error", "-stream_loop", "-1", "-i", wav,
         "-t", f"{duree_totale:.3f}",
         "-af", f"afade=t=out:st={st:.3f}:d={fondu_sortie:.3f}",
         "-c:a", "pcm_s16le", sortie],
        check=False, timeout=600, etiquette="ffmpeg ambience extension",
    ).returncode == 0
    if not ok or not os.path.exists(sortie):
        raise RuntimeError(f"Ambience extension failed: {sortie}")
    return sortie


def assembler_finale(base_video: str, carton_video: str, wav_etendu: Optional[str],
                     sortie: str, fps: int = 48) -> str:
    """One-pass assembly: base + title card (concat filter) + extended ambience
    (wav_etendu = None for a silent finale)."""
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
    run_engine(args, check=True, timeout=1800, etiquette="ffmpeg final assembly")
    if not os.path.exists(sortie):
        raise RuntimeError(f"Final assembly failed: {sortie}")
    return sortie
