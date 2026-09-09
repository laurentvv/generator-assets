#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génération de bruitages (SFX) par IA : Stable Audio 3 Small SFX via audio.cpp.

Moteur validé par l'utilisateur le 2026-09-09 (4/5 échantillons « ok » : épée, pas
gravier, porte, whoosh) sur les SFX du cas d'usage jeu Godot — RTF ~0,2 Vulkan,
le plus rapide du poste.

Traitements intégrés (issus des itérations d'écoute sur le sample pluie/orage) :
- **Sélection du prompt = 1er levier de qualité.** Le modèle peut sortir des textures
  déséquilibrées : « heavy rain on window glass, distant thunder rumble » produit un
  grondement 50-250 Hz à +18 dB avec le crépitement HF à −17..−28 dB (« assourdie »,
  verdict utilisateur) ; « heavy rain falling on glass, dense patter with natural
  splashes » est spectralement équilibré (HF/LF ≈ −2 dB). Nommer LE CONTENU (patter,
  splashes) plutôt que l'ambiance (thunder rumble) oriente le spectre.
- **Rognage des silences d'entrée/sortie** : SA3 fondu la fin (jusqu'à plusieurs
  secondes muettes) — rognage automatique des bords sous −45 dBFS (garde-fou :
  jamais plus de 50 % du fichier).
- **Deux traitements de niveau** (le volume ne suffit pas, verdict « son trop faible ») :
  texture « nappe » (I < seuil) = gain vers la cible LUFS + limiteur de plafond
  (alimiter — ne touche QUE les crêtes qui dépassent, préserve le crépitement ; la
  1re version avec acompressor seuil −20 dB écrasait la modulation de la texture
  et l'assourdissait davantage) ; SFX transitoire = simple normalisation de crête
  (comportement historique, échantillons validés inchangés).

Écueils intégrés :
- sortie SA3 = 44,1 kHz stéréo (le workflow sfx historique était mono procédural ;
  l'export Godot WAV/OGG accepte les deux)
- OGG interdit via soundfile (stack overflow libsndfile, règle §1.10) — l'export
  final passe par exporter_sfx_godot (ffmpeg), ce module ne fait que le WAV intermédiaire
"""

import os
import re
import subprocess
import tempfile
from typing import Any, Dict

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

# Texture « nappe » : seuil de détection, cible loudness du corps et plafond de crête.
SEUIL_NAPPE_LUFS = -20.0
LUFS_CIBLE_NAPPE = -16.0
PLAFOND_DBFS = -1.5

# Rognage des silences d'entrée/sortie (fondu structurel SA3).
SEUIL_ROGNAGE_DB = -45.0
MARGE_ROGNAGE_S = 0.05
MAX_ROGNAGE_FRAC = 0.5


def _rogner_silences(audio: np.ndarray, sr: int) -> np.ndarray:
    """Coupe les bords silencieux (env. RMS 20 ms sous SEUIL_ROGNAGE_DB, marge conservée).

    Garde-fou : aucun rognage si plus de MAX_ROGNAGE_FRAC du fichier disparaîtrait
    (génération dégénérée — on la laisse telle quelle).
    """
    mono = audio.mean(axis=1) if audio.ndim > 1 else audio
    w = max(int(sr * 0.02), 1)
    env = np.sqrt(np.convolve(mono.astype(np.float64) ** 2, np.ones(w) / w, mode="same"))
    db = 20 * np.log10(env + 1e-12)
    actifs = np.where(db > SEUIL_ROGNAGE_DB)[0]
    if actifs.size == 0:
        return audio
    marge = int(MARGE_ROGNAGE_S * sr)
    i0 = max(0, int(actifs[0]) - marge)
    i1 = min(len(audio), int(actifs[-1]) + 1 + marge)
    if (i1 - i0) < int(len(audio) * MAX_ROGNAGE_FRAC):
        return audio
    return audio[i0:i1]


def _traiter_loudness_nappe(chemin_wav: str, gain_db: float) -> None:
    """Remonte le corps du signal vers LUFS_CIBLE_NAPPE et plafonne les crêtes (in place).

    Gain linéaire puis alimiter : le limiteur ne touche que les crêtes qui dépassent
    le plafond — la texture (modulation du crépitement) reste intacte. Une version
    antérieure avec acompressor seuil fixe écrasait la texture elle-même (rendu sourd).
    """
    ffmpeg = resoudre_ffmpeg()
    chaine = (
        f"volume={gain_db:.2f}dB,"
        f"alimiter=limit={10 ** (PLAFOND_DBFS / 20):.4f}:attack=2:release=50:level=disabled"
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
    "pic_source": float, "niveau_mode": "crete"|"nappe", "lufs_source": float|None,
    "rognage_pct": float}.
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

        audio, sr = sf.read(wav_brut, always_2d=False, dtype="float32")

        # Rognage des fondu/silences structurels d'entrée/sortie.
        taille_avant = len(audio)
        audio = _rogner_silences(audio, sr)
        rognage_pct = 100.0 * (1.0 - len(audio) / max(taille_avant, 1))
        if rognage_pct > 0.01:
            sf.write(wav_brut, audio, sr, subtype="PCM_16", format="WAV")

        # Traitement de niveau : nappe (gain + plafond) ou crête simple.
        lufs_source = None
        niveau_mode = "crete"
        gain_db = 0.0
        try:
            mesures = mesurer_lufs(wav_brut)
            lufs_source = mesures["I"]
        except RuntimeError:
            mesures = None
        if mesures and mesures["I"] < SEUIL_NAPPE_LUFS:
            niveau_mode = "nappe"
            gain_db = LUFS_CIBLE_NAPPE - mesures["I"]
            _traiter_loudness_nappe(wav_brut, gain_db)
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
        "gain_db": round(gain_db, 1), "rognage_pct": round(rognage_pct, 1),
    }
