#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génération de voix off par TTS local (audio.cpp, Vulkan) avec clonage vocal.

Moteurs GGUF (paquets monolithiques q8_0 dans C:\\Modeles_LLM) :
- qwen3   : Qwen3-TTS 12Hz 1.7B Base (Apache-2.0) — clonage avec transcript,
            expression via --instruct, sortie 24 kHz
- voxcpm2 : VoxCPM2 (Apache-2.0) — clonage SANS transcript, sortie 48 kHz
- fish    : Fish Audio S2 Pro (licence recherche, commercial payant) — zéro-shot
            ou clonage avec transcript, balises d'expression inline ([whisper]…),
            sortie 44,1 kHz

Pipeline intégré : conversion/rééchantillonnage de la référence, contrôle du
niveau (minimum -26 dB moyen, sinon normalisation -18 LUFS / -1,5 dBTP),
transcription automatique par qwen3-asr (0.6B) quand le moteur l'exige,
normalisation finale de la voix (défaut -16 LUFS, standard dialogue YouTube).
"""

import os
import re
import subprocess
from typing import Any, Dict, Optional

from core.config import DEFAULT_MODEL_DIR
from core.music_ai import (
    convertir_mp3,
    exporter_bed_lufs,
    mesurer_lufs,
    resoudre_audiocpp,
    resoudre_ffmpeg,
)

# Chemins des paquets GGUF (surchargeables par variable d'environnement).
MODELE_QWEN3_TTS = os.getenv(
    "QWEN3_TTS_MODEL",
    os.path.join(DEFAULT_MODEL_DIR, "Qwen3-TTS-12Hz-1.7B-Base-GGUF",
                 "qwen3-tts-12hz-1.7b-base-q8_0_v2.gguf"),
)
MODELE_QWEN3_ASR = os.getenv(
    "QWEN3_ASR_MODEL",
    os.path.join(DEFAULT_MODEL_DIR, "Qwen3-ASR-0.6B-GGUF", "qwen3-asr-0.6b-q8_0.gguf"),
)
MODELE_VOXCPM2 = os.getenv(
    "VOXCPM2_MODEL",
    os.path.join(DEFAULT_MODEL_DIR, "VoxCPM2-GGUF", "voxcpm2-q8_0.gguf"),
)
MODELE_FISH = os.getenv(
    "FISH_S2PRO_MODEL",
    os.path.join(DEFAULT_MODEL_DIR, "Fish-Audio-S2-Pro-GGUF", "fish-audio-s2-pro-q8_0.gguf"),
)

MOTEURS: Dict[str, Dict[str, Any]] = {
    "qwen3": {
        "famille": "qwen3_tts",
        "modele": MODELE_QWEN3_TTS,
        "ref_obligatoire": True,
        "transcript_obligatoire": True,
        "langue": "French",
        "licence": "Apache-2.0",
    },
    "voxcpm2": {
        "famille": "voxcpm2",
        "modele": MODELE_VOXCPM2,
        "ref_obligatoire": False,
        "transcript_obligatoire": False,
        "langue": "French",
        "licence": "Apache-2.0",
    },
    "fish": {
        "famille": "fish_audio",
        "modele": MODELE_FISH,
        "ref_obligatoire": False,      # zéro-shot possible, clonage si ref fournie
        "transcript_obligatoire": False,  # ... mais transcript exigé QUAND une ref est fournie
        "langue": None,                # détection auto
        "licence": "Fish Audio Research (non commercial sans licence)",
    },
}

SEUIL_NIVEAU_DB = -26.0  # en dessous : la référence est jugée trop faible
LUFS_REF = -18.0         # cible de normalisation de la référence vocale
TP_REF = -1.5            # plafond de crête de la référence


def _verifier_modele(moteur: str) -> str:
    """Vérifie que le paquet GGUF du moteur est présent, sinon lève une erreur claire."""
    chemin = MOTEURS[moteur]["modele"]
    if not os.path.exists(chemin):
        raise FileNotFoundError(
            f"Paquet GGUF du moteur '{moteur}' introuvable : {chemin} — "
            f"le télécharger depuis audio-cpp/audio.cpp-gguf "
            f"(scripts/telecharger_gros_fichier_parallele.py)."
        )
    return chemin


def mesurer_niveau_db(chemin: str) -> Dict[str, float]:
    """Mesure les niveaux (dB) d'un fichier audio via ffmpeg volumedetect."""
    ffmpeg = resoudre_ffmpeg()
    resultat = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", chemin, "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )
    texte = resultat.stderr or ""
    def _extraire(motif: str) -> float:
        m = re.search(motif + r"\s*:\s*([-\d.]+) dB", texte)
        return float(m.group(1)) if m else -120.0
    return {"mean": _extraire("mean_volume"), "max": _extraire("max_volume")}


def preparer_reference(chemin_ref: str, dossier_travail: str) -> str:
    """
    Prépare la référence vocale : conversion WAV mono 48 kHz si besoin puis,
    si le niveau moyen est sous SEUIL_NIVEAU_DB, normalisation -18 LUFS / -1,5 dBTP.
    Retourne le chemin du WAV effectif à utiliser (l'original s'il est correct).
    """
    ffmpeg = resoudre_ffmpeg()
    os.makedirs(dossier_travail, exist_ok=True)
    base = os.path.splitext(os.path.basename(chemin_ref))[0]
    wav_converti = os.path.join(dossier_travail, f"ref_{base}.wav")
    if not os.path.exists(wav_converti):
        subprocess.run(
            [ffmpeg, "-hide_banner", "-y", "-i", chemin_ref,
             "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", wav_converti],
            check=True, capture_output=True, timeout=180,
        )

    niveaux = mesurer_niveau_db(wav_converti)
    if niveaux["mean"] >= SEUIL_NIVEAU_DB:
        print(f"ℹ️ Référence {chemin_ref} : niveau moyen {niveaux['mean']:.1f} dB (OK, ≥ {SEUIL_NIVEAU_DB:.0f} dB).")
        return wav_converti

    print(f"⚠️ Référence trop faible ({niveaux['mean']:.1f} dB moyen) → normalisation {LUFS_REF} LUFS / {TP_REF} dBTP.")
    wav_normalise = os.path.join(dossier_travail, f"ref_{base}_norm.wav")
    mesures = mesurer_lufs(wav_converti)
    filtre = (
        f"loudnorm=I={LUFS_REF}:TP={TP_REF}:LRA=7.0:"
        f"measured_I={mesures['I']}:measured_TP={mesures['TP']}:"
        f"measured_LRA={mesures['LRA']}:measured_thresh={mesures['thresh']}:"
        f"offset={mesures['offset']}:linear=true"
    )
    subprocess.run(
        [ffmpeg, "-hide_banner", "-y", "-i", wav_converti, "-af", filtre,
         "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", wav_normalise],
        check=True, capture_output=True, timeout=180,
    )
    apres = mesurer_niveau_db(wav_normalise)
    print(f"✅ Référence normalisée : {apres['mean']:.1f} dB moyen / {apres['max']:.1f} dB crête.")
    return wav_normalise


def transcrire_reference(wav_ref: str, dossier_travail: str, backend: str = "vulkan") -> str:
    """
    Transcrit la référence vocale avec qwen3-asr 0.6B (mémoire cache à côté du WAV).
    Requis par qwen3-tts (mode ICL) et fish (clonage inline).
    """
    cache = os.path.splitext(wav_ref)[0] + "_transcript.txt"
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            return f.read().strip()

    if not os.path.exists(MODELE_QWEN3_ASR):
        raise FileNotFoundError(
            f"qwen3-asr introuvable ({MODELE_QWEN3_ASR}) — nécessaire pour transcrire "
            f"la référence (ou fournir le transcript à côté du WAV : {cache})."
        )
    audiocpp = resoudre_audiocpp()
    resultat = subprocess.run(
        [audiocpp, "--task", "asr", "--family", "qwen3_asr", "--model", MODELE_QWEN3_ASR,
         "--backend", backend, "--language", "fr", "--audio", wav_ref],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
    )
    m = re.search(r"text_output=(.+)", (resultat.stdout or "") + (resultat.stderr or ""))
    if not m or not m.group(1).strip():
        raise RuntimeError(f"Transcription ASR vide pour {wav_ref}")
    transcript = m.group(1).strip()
    with open(cache, "w", encoding="utf-8") as f:
        f.write(transcript)
    print(f"📝 Transcript de la référence (qwen3-asr) : « {transcript[:80]}… »")
    return transcript


def generer_voix_off(
    texte: str,
    moteur: str = "qwen3",
    wav_ref: Optional[str] = None,
    instruct: Optional[str] = None,
    sortie: str = "voix_off.wav",
    backend: str = "vulkan",
    seed: Optional[int] = None,
    dossier_travail: str = ".",
) -> Dict[str, Any]:
    """
    Génère une voix off avec le moteur choisi. Si wav_ref est fourni, clone la voix
    (transcription ASR automatique pour qwen3/fish). instruct = consigne de style/
    émotion (qwen3). Les balises d'expression fish ([whisper], [excited]…) se
    placent directement dans `texte`.
    """
    if moteur not in MOTEURS:
        raise ValueError(f"Moteur inconnu : {moteur} (choix : {', '.join(MOTEURS)})")
    conf = MOTEURS[moteur]
    modele = _verifier_modele(moteur)

    if conf["ref_obligatoire"] and not wav_ref:
        raise ValueError(f"Le moteur '{moteur}' exige une référence vocale (--voix-ref).")

    ref_effective = preparer_reference(wav_ref, dossier_travail) if wav_ref else None

    cmd = [resoudre_audiocpp(), "--task", "tts", "--family", conf["famille"],
           "--model", modele, "--backend", backend, "--text", texte,
           "--metrics", "--out", sortie]
    if conf["langue"]:
        cmd += ["--language", conf["langue"]]
    if ref_effective:
        cmd += ["--voice-ref", ref_effective]
        if conf["famille"] in ("qwen3_tts", "fish_audio"):
            transcript = transcrire_reference(ref_effective, dossier_travail, backend)
            cmd += ["--reference-text", transcript]
    if instruct and moteur == "qwen3":
        cmd += ["--instruct", instruct]
    if seed is not None and seed >= 0:
        cmd += ["--seed", str(seed)]

    print(f"🎙️ Génération voix off : moteur={moteur}, clonage={'oui' if ref_effective else 'non'}, backend={backend}…")
    subprocess.run(cmd, check=True, timeout=3600)
    if not os.path.exists(sortie):
        raise RuntimeError(f"La génération n'a pas produit {sortie}")
    return {"sortie": sortie, "moteur": moteur, "clonage": bool(ref_effective),
            "licence": conf["licence"]}


def finaliser_voix(wav_source: str, lufs_cible: float = -16.0) -> Dict[str, str]:
    """
    Normalise la voix (loudnorm 2 passes → LUFS cible, 48 kHz PCM16) et produit
    un MP3 d'écoute. Défaut -16 LUFS = standard dialogue YouTube.
    """
    base = os.path.splitext(wav_source)[0]
    wav_final = f"{base}_final.wav"
    mp3_final = f"{base}_final.mp3"
    mesures = exporter_bed_lufs(wav_source, wav_final, lufs_cible=lufs_cible)
    convertir_mp3(wav_final, mp3_final)
    print(f"✅ Voix finalisée : {wav_final} ({mesures['I']:.1f} LUFS) + {mp3_final}")
    return {"wav": wav_final, "mp3": mp3_final, "lufs": f"{mesures['I']:.1f}"}
