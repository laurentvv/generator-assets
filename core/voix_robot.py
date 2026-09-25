#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Voix de robot en anglais (recette VALIDÉE utilisateur le 2026-09-17, essai 17
« petit robot tranquille ») : TTS Kokoro-82M via audio.cpp (Vulkan) puis effet
« petit robot » FFmpeg.

Recette validée (output/test_voix_robot/essai17_kokoro_ringmod120_tranquille.mp3) :
1. TTS      : famille kokoro_tts, voix `af_heart`, en-us, 24 kHz mono, débit normal.
2. Effet FF : pitch +30 % (asetrate 31200), atempo 0.65 (débit posé, pitch intact),
              ring modulation 120 Hz (aeval — la voix multipliée par un sinus perd
              son fondamental → timbre métallique), gain -4 dB.

⚠️ Moteur : le zip release audio.cpp (v0.7.4 et v0.8.0) ne peut pas lancer
kokoro_tts (« Could not load eSpeak-ng » — ni DLL espeak partagée ni pack statique
fournis, cf. MEMORY_BANK §1.21) → le binaire scratch `build-357` (espeak embarqué)
est résolu automatiquement tant qu'il existe ; surchargeable par la variable
d'environnement AUDIOCPP_KOKORO_CLI. À revoir si une release embarque espeak.
"""

import os
import subprocess
from typing import Any, Dict, Optional

from core.config import DEFAULT_MODEL_DIR
from core.music_ai import convertir_mp3, resoudre_ffmpeg

# Paquet GGUF Kokoro-82M (org audio-cpp, cf. MEMORY_BANK §1.21).
MODELE_KOKORO = os.getenv(
    "KOKORO_TTS_MODEL",
    os.path.join(DEFAULT_MODEL_DIR, "Kokoro-82M-GGUF", "kokoro-82m-q8_0.gguf"),
)

# Binaire scratch avec espeak-ng embarqué (kokoro_tts inutilisable dans la release,
# cf. docstring). Surcharge : AUDIOCPP_KOKORO_CLI.
BINARIE_SCRATCH_KOKORO = (
    r"C:\IA\audio_cpp_master_test\build-357\bin\Release\audiocpp_cli.exe"
)

# Réglages validés par l'utilisateur (essai 17) — défauts du workflow.
RECIPE = {
    "voice_id": "af_heart",
    "pitch": 1.30,        # asetrate = 24000 * pitch (1.30 = +30 %)
    "ringmod_hz": 120.0,  # fréquence de la ring modulation
    "tempo": 0.65,        # atempo post-pitch (0.65 = débit « tranquille » validé)
    "gain_db": -4.0,      # volume final (voix « calme » validée)
}


def resoudre_audiocpp_kokoro() -> str:
    """Résout un binaire audiocpp capable de lancer kokoro_tts (espeak présent)."""
    surcharge = os.getenv("AUDIOCPP_KOKORO_CLI")
    if surcharge and os.path.exists(surcharge):
        return surcharge
    if os.path.exists(BINARIE_SCRATCH_KOKORO):
        return BINARIE_SCRATCH_KOKORO
    # Repli : binaire release (échouera sur kokoro sans espeak-ng partagé —
    # l'erreur « Could not load eSpeak-ng » reste explicite).
    from core.music_ai import resoudre_audiocpp
    return resoudre_audiocpp()


def generer_base_kokoro(
    texte: str,
    sortie: str,
    voice_id: str = "af_heart",
    speaking_rate: float = 1.0,
    backend: str = "vulkan",
) -> Dict[str, Any]:
    """Synthétise la parole anglaise (Kokoro-82M, 24 kHz mono) avant effet robot."""
    if not os.path.exists(MODELE_KOKORO):
        raise FileNotFoundError(
            f"Kokoro-82M introuvable : {MODELE_KOKORO} — le télécharger depuis "
            f"audio-cpp/Kokoro-82M-GGUF (scripts/telecharger_gros_fichier_parallele.py)."
        )
    audiocpp = resoudre_audiocpp_kokoro()
    cmd = [
        audiocpp, "--task", "tts", "--family", "kokoro_tts",
        "--model", MODELE_KOKORO, "--backend", backend,
        "--language", "en-us", "--voice-id", voice_id,
        "--metrics", "--out", sortie,
    ]
    if speaking_rate != 1.0:
        cmd += ["--speaking-rate", str(speaking_rate)]
    cmd += ["--text", texte]

    print(f"🤖 TTS Kokoro (voix {voice_id}, backend {backend}) — binaire : {audiocpp}")
    subprocess.run(cmd, check=True, timeout=600)
    if not os.path.exists(sortie):
        raise RuntimeError(f"La génération n'a pas produit {sortie}")
    return {"sortie": sortie, "voice_id": voice_id}


def appliquer_effet_robot(
    source: str,
    sortie: str,
    pitch: float = RECIPE["pitch"],
    ringmod_hz: float = RECIPE["ringmod_hz"],
    tempo: float = RECIPE["tempo"],
    gain_db: float = RECIPE["gain_db"],
) -> str:
    """
    Effet « petit robot » validé : pitch up (asetrate), débit posé (atempo),
    ring modulation (aeval, sinus mono), gain final. Chaîne identique à l'essai 17.
    """
    ffmpeg = resoudre_ffmpeg()
    asetrate = int(24000 * pitch)
    filtre = (
        f"asetrate={asetrate},aresample=24000,atempo={tempo},"
        f"aeval='val(0)*sin(2*PI*{ringmod_hz:g}*t)',volume={gain_db:g}dB"
    )
    subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", source,
         "-af", filtre, "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", sortie],
        check=True, timeout=180,
    )
    return sortie


def generer_voix_robot(
    texte: str,
    dossier: str,
    nom: str = "voix_robot",
    voice_id: str = RECIPE["voice_id"],
    pitch: float = RECIPE["pitch"],
    ringmod_hz: float = RECIPE["ringmod_hz"],
    tempo: float = RECIPE["tempo"],
    gain_db: float = RECIPE["gain_db"],
    speaking_rate: float = 1.0,
    backend: str = "vulkan",
) -> Dict[str, Any]:
    """Pipeline complet : base TTS → effet robot → WAV final + MP3 d'écoute."""
    os.makedirs(dossier, exist_ok=True)
    wav_base = os.path.join(dossier, f"{nom}_brut.wav")
    wav_final = os.path.join(dossier, f"{nom}.wav")
    mp3_final = os.path.join(dossier, f"{nom}.mp3")

    generer_base_kokoro(texte, wav_base, voice_id=voice_id,
                        speaking_rate=speaking_rate, backend=backend)
    appliquer_effet_robot(wav_base, wav_final, pitch=pitch,
                          ringmod_hz=ringmod_hz, tempo=tempo, gain_db=gain_db)
    convertir_mp3(wav_final, mp3_final)
    return {"wav": wav_final, "mp3": mp3_final, "brut": wav_base}
