#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Retrait de voix par séparation de sources HTDemucs (audio.cpp, Vulkan).

Capacité validée par l'utilisateur le 2026-09-06 (« retrait de la voix : OK »)
sur la piste complète Love Like Blood. Produit :
- l'instrumental sans chant (mixage drums+bass+other, niveaux préservés)
- les 4 stems complets (drums, bass, other, vocals) pour usage ultérieur

Écueils intégrés :
- HTDemucs exige du 44,1 kHz (« sample rate mismatch » sinon) → rééchantillonnage
  automatique de toute source
- l'écriture des stems exige --out-dir (multi-sorties nommées) ; --out est refusé
"""

import os
import subprocess
from typing import Any, Dict

from core.music_ai import convertir_mp3, resoudre_audiocpp, resoudre_ffmpeg

MODELE_HTDEMUCS = os.getenv(
    "HTDEMUCS_MODEL",
    os.path.join("C:\\Modeles_LLM", "HTDemucs-GGUF", "htdemucs-f16.gguf"),
)
SR_HDEMUCS = 44100
STEMS_INSTRUMENTAL = ("drums", "bass", "other")


def retirer_voix(chemin_audio: str, dossier_travail: str, backend: str = "vulkan") -> Dict[str, Any]:
    """
    Sépare l'audio en stems HTDemucs et construit l'instrumental sans chant.
    Retourne les chemins {instrumental_wav, instrumental_mp3, stems_dir, voix_wav}.
    """
    if not os.path.exists(MODELE_HTDEMUCS):
        raise FileNotFoundError(
            f"Paquet HTDemucs introuvable : {MODELE_HTDEMUCS} — le télécharger depuis "
            f"audio-cpp/audio.cpp-gguf (HTDemucs-GGUF/htdemucs-f16.gguf, 84 Mo)."
        )
    ffmpeg = resoudre_ffmpeg()
    os.makedirs(dossier_travail, exist_ok=True)

    # 1) Rééchantillonnage 44,1 kHz stéréo (exigé par HTDemucs)
    wav44 = os.path.join(dossier_travail, "source_44k.wav")
    subprocess.run(
        [ffmpeg, "-hide_banner", "-y", "-i", chemin_audio,
         "-ar", str(SR_HDEMUCS), "-ac", "2", "-c:a", "pcm_s16le", wav44],
        check=True, capture_output=True, timeout=600,
    )

    # 2) Séparation en stems (multi-sorties => --out-dir obligatoire)
    stems_dir = os.path.join(dossier_travail, "stems")
    os.makedirs(stems_dir, exist_ok=True)
    subprocess.run(
        [resoudre_audiocpp(), "--task", "sep", "--family", "htdemucs",
         "--model", MODELE_HTDEMUCS, "--backend", backend, "--threads", "16",
         "--audio", wav44, "--out-dir", stems_dir],
        check=True, timeout=3600,
    )
    manquants = [s for s in STEMS_INSTRUMENTAL + ("vocals",)
                 if not os.path.exists(os.path.join(stems_dir, f"{s}.wav"))]
    if manquants:
        raise RuntimeError(f"Stems HTDemucs manquants : {', '.join(manquants)}")

    # 3) Instrumental = drums + bass + other (somme sans le chant, niveaux préservés)
    instrumental = os.path.join(dossier_travail, "instrumental.wav")
    entrees: list = []
    for s in STEMS_INSTRUMENTAL:
        entrees += ["-i", os.path.join(stems_dir, f"{s}.wav")]
    filtre = "".join(f"[{i}:a]" for i in range(len(STEMS_INSTRUMENTAL)))
    filtre += f"amix=inputs={len(STEMS_INSTRUMENTAL)}:normalize=0"
    subprocess.run(
        [ffmpeg, "-hide_banner", "-y", *entrees, "-filter_complex", filtre,
         "-c:a", "pcm_s16le", instrumental],
        check=True, capture_output=True, timeout=600,
    )

    # 4) MP3 d'écoute
    mp3 = convertir_mp3(instrumental, instrumental.replace(".wav", ".mp3"), 192)
    return {
        "instrumental_wav": instrumental,
        "instrumental_mp3": mp3,
        "stems_dir": stems_dir,
        "voix_wav": os.path.join(stems_dir, "vocals.wav"),
    }
