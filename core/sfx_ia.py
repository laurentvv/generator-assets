#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génération de bruitages (SFX) par IA : Stable Audio 3 Small SFX via audio.cpp.

Moteur validé par l'utilisateur le 2026-09-09 (4/5 échantillons « ok » : épée, pas
gravier, porte, whoosh) sur les SFX du cas d'usage jeu Godot — RTF ~0,2 Vulkan,
le plus rapide du poste.

Deux traitements de niveau selon la nature de la sortie (retour utilisateur :
« son trop faible » sur la pluie/orage, même après normalisation de crête) :
- SFX transitoire (I >= seuil) : simple normalisation de crête (comportement
  historique, ne change pas le caractère des échantillons validés) ;
- texture « nappe » (I < seuil, ex. pluie) : le modèle sort un corps très bas
  (mesuré −35 LUFS) surmonté d'un pic isolé qui occupe toute la dynamique
  (TP 19 LU au-dessus du corps, LRA 3,4) → la crête seule ne remonte rien.
  Chaîne validée en prototype : limiteur (écrase le pic) puis loudnorm 2 passes
  linéaire (remonte le corps vers la cible). Mesuré : −27,7 → −17,4 LUFS,
  TP tenue à −1,5 dBTP — zone des échantillons « ok » (épée −15,1, whoosh −18,2).

Écueils intégrés :
- sortie SA3 = 44,1 kHz stéréo (le workflow sfx historique était mono procédural ;
  l'export Godot WAV/OGG accepte les deux) — loudnorm rééchantillonne à 44,1 kHz
- OGG interdit via soundfile (stack overflow libsndfile, règle §1.10) — l'export
  final passe par exporter_sfx_godot (ffmpeg), ce module ne fait que le WAV intermédiaire
"""

import os
import re
import subprocess
import tempfile
from typing import Any, Dict, Optional

import numpy as np
import soundfile as sf

from core.music_ai import mesurer_lufs, resoudre_audiocpp, resoudre_ffmpeg

MODELE_SA3_SFX = os.getenv(
    "SA3_SFX_MODEL",
    os.path.join(
        "C:\\Modeles_LLM",
        "Stable-Audio-3-Small-SFX-GGUF",
        "stable-audio-3-small-sfx-f16.gguf",
    ),
)

# Normalisation de crête (~ -0,9 dBFS) : même convention que la synthèse procédurale (0,9).
PIC_CIBLE = 0.9

# Texture « nappe » : seuil de détection et cible loudness du corps.
SEUIL_NAPPE_LUFS = -20.0
LUFS_CIBLE_NAPPE = -16.0
TP_CIBLE_DB = -1.5
# Limiteur : ratio 20 = quasi-brickwall sur le pic isolé, corps (bien plus bas) intact.
LIMITEUR_PIC = "acompressor=threshold=-20dB:ratio=20:attack=0.5:release=80:knee=3"


def _traiter_loudness_nappe(chemin_wav: str) -> None:
    """Limite le pic isolé puis remonte le corps du signal vers LUFS_CIBLE_NAPPE (in place).

    2 passes loudnorm (mesure du signal limité, puis gain linéaire — pas de dynamique
    ajoutée sur la texture, seul le pic est écrasé par le limiteur amont).
    """
    ffmpeg = resoudre_ffmpeg()
    m2 = mesurer_lufs(chemin_wav, filtre_amont=LIMITEUR_PIC)
    lra = max(m2["LRA"], 7.0)
    chaine = (
        f"{LIMITEUR_PIC},loudnorm=I={LUFS_CIBLE_NAPPE}:TP={TP_CIBLE_DB}:LRA={lra}:"
        f"measured_I={m2['I']}:measured_TP={m2['TP']}:measured_LRA={m2['LRA']}:"
        f"measured_thresh={m2['thresh']}:offset={m2['offset']}:linear=true"
    )
    tmp = chemin_wav + ".lufs.wav"
    try:
        subprocess.run(
            [ffmpeg, "-hide_banner", "-y", "-i", chemin_wav, "-af", chaine,
             "-ar", "44100", "-c:a", "pcm_s16le", tmp],
            check=True, capture_output=True, timeout=180,
        )
        os.replace(tmp, chemin_wav)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def generer_sfx_ia(
    prompt: str,
    duree: float = 2.0,
    seed: int = 42,
    backend: str = "vulkan",
) -> Dict[str, Any]:
    """
    Génère un effet sonore par IA (stable_audio, texte → audio).
    Retourne {"audio": float32 (stéréo), "sr": 44100, "rtf": float|None,
    "pic_source": float, "niveau_mode": "crete"|"nappe", "lufs_source": float|None}.
    Graine < 0 = laisser le défaut du runtime (déterministe).
    """
    if not os.path.exists(MODELE_SA3_SFX):
        raise FileNotFoundError(
            f"Paquet SA3 Small SFX introuvable : {MODELE_SA3_SFX} — le télécharger depuis "
            f"audio-cpp/audio.cpp-gguf (Stable-Audio-3-Small-SFX-GGUF/stable-audio-3-small-sfx-f16.gguf, "
            f"2,20 Gio ; téléchargeur parallèle recommandé)."
        )

    fd, wav_brut = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    cmd = [
        resoudre_audiocpp(), "--task", "gen", "--family", "stable_audio",
        "--model", MODELE_SA3_SFX, "--backend", backend, "--metrics",
        "--text", prompt, "--duration-seconds", str(float(duree)),
        "--out", wav_brut,
    ]
    if seed is not None and seed >= 0:
        cmd += ["--seed", str(int(seed))]

    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=int(duree * 10 + 300), encoding="utf-8", errors="replace",
        )
        if res.returncode != 0 or not os.path.exists(wav_brut):
            extrait = (res.stderr or res.stdout or "").strip()[-400:]
            raise RuntimeError(f"Génération SFX IA échouée (exit {res.returncode}) : {extrait}")

        rtf = None
        m = re.search(r"metrics\.rtf=([\d.]+)", res.stdout)
        if m:
            rtf = float(m.group(1))

        lufs_source: Optional[float] = None
        niveau_mode = "crete"
        try:
            mesures = mesurer_lufs(wav_brut)
            lufs_source = mesures["I"]
        except RuntimeError:
            mesures = None
        if mesures and mesures["I"] < SEUIL_NAPPE_LUFS:
            _traiter_loudness_nappe(wav_brut)
            niveau_mode = "nappe"

        audio, sr = sf.read(wav_brut, always_2d=False, dtype="float32")
    finally:
        if os.path.exists(wav_brut):
            os.remove(wav_brut)

    pic = float(np.max(np.abs(audio))) if audio.size else 0.0
    if pic > 0:
        audio = (audio / pic) * PIC_CIBLE

    return {
        "audio": audio.astype(np.float32), "sr": int(sr), "rtf": rtf,
        "pic_source": pic, "niveau_mode": niveau_mode, "lufs_source": lufs_source,
    }
