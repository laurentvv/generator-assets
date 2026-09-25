#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Super-résolution audio → 48 kHz via UniverSR (audio.cpp, famille `universr`).

Recette VALIDÉE utilisateur le 2026-09-18 (MEMORY_BANK §1.27) :
- Voix 16 kHz → 48 kHz (paquet `speech`) : « copie sans bug, parfait même ».
- Musique 24 kHz → 48 kHz (paquet `audio`) : « très bien, belle batterie ».

⚠️ Limites moteur (audio.cpp v0.8.1) :
- backend Vulkan cassé (« UniverSR conditioning contains unsupported backend op
  'MUL_MAT' ») → CPU OBLIGATOIRE, RTF ~13 (28 s → ~6 min ; une voix off de
  3 min → ~40 min). À retester si un chemin Vulkan arrive en amont.
- sortie MONO seulement (l'entrée stéréo est avalée) — la voix off, cas
  d'usage principal, est mono natif.

Bandes d'entrée exposées par la spec : 8000/12000/16000/24000 Hz. Le fichier
est rééchantillonné automatiquement (FFmpeg) vers la bande déclarée si sa
fréquence diffère ; au-dessus de 24 kHz l'entrée est déjà pleine bande →
refus (la super-résolution n'a plus de sens).
"""

import os
import shutil
from typing import Any, Dict

from core.music_ai import resoudre_audiocpp, resoudre_ffmpeg
from core.process import run_engine

# Paquets GGUF UniverSR (org audio-cpp, 229 Mo chacun — cf. MEMORY_BANK §1.27).
MODELE_UNIVERSR_AUDIO = os.getenv(
    "UNIVERSR_AUDIO_MODEL",
    os.path.join("C:\\Modeles_LLM", "UniverSR-GGUF", "universr-audio-orig.gguf"),
)
MODELE_UNIVERSR_SPEECH = os.getenv(
    "UNIVERSR_SPEECH_MODEL",
    os.path.join("C:\\Modeles_LLM", "UniverSR-GGUF", "universr-speech-orig.gguf"),
)

# Réglages par défaut (recette validée — steps/seed = défauts de spec).
RECIPE = {
    "variante": "speech",  # speech = voix off (cas principal) | audio = musique
    "steps": 4,            # pas d'intégration ODE (sampler midpoint)
    "seed": 42,            # graine du bruit de flow (reproductibilité A/B)
    "threads": 20,         # CPU (i7-13700KF) — Vulkan indisponible sur cette famille
}

# Bandes d'entrée exposées par la spec universr.
BANDES_AUTORISEES = (8000, 12000, 16000, 24000)
BANDE_MAX = 24000


def resoudre_modele(variante: str) -> str:
    """Chemin du GGUF UniverSR pour la variante demandée (speech|audio)."""
    if variante == "speech":
        modele = MODELE_UNIVERSR_SPEECH
    elif variante == "audio":
        modele = MODELE_UNIVERSR_AUDIO
    else:
        raise ValueError(f"Variante UniverSR inconnue : {variante} (speech|audio).")
    if not os.path.exists(modele):
        raise FileNotFoundError(
            f"GGUF UniverSR introuvable : {modele} — téléchargeable depuis "
            f"audio-cpp/audio.cpp-gguf (dossier UniverSR-GGUF)."
        )
    return modele


def detecter_frequence(chemin: str) -> int:
    """Fréquence d'échantillonnage du premier flux audio (ffprobe)."""
    probe = shutil.which("ffprobe")
    if not probe:
        voisin = os.path.join(os.path.dirname(resoudre_ffmpeg()), "ffprobe.exe")
        probe = voisin if os.path.exists(voisin) else "ffprobe"
    out = run_engine(
        [probe, "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=sample_rate", "-of", "csv=p=0", chemin],
        check=True, timeout=60, etiquette="ffprobe fréquence",
    ).stdout.strip()
    return int(out or 0)


def choisir_bande(frequence: int, bande_forcee: int = 0) -> int:
    """Bande d'entrée à déclarer au modèle (8000/12000/16000/24000).

    Bande forcée (--upsr-rate) = contrôle total (fichier rééchantillonné
    dessus). Sinon : la fréquence du fichier si c'est une bande supportée,
    sinon la plus grande bande supportée SOUS cette fréquence (22050 → 16000,
    11025 → 8000…) ; au-dessus de 24 kHz → refus (déjà pleine bande).
    """
    if bande_forcee:
        if bande_forcee not in BANDES_AUTORISEES:
            raise ValueError(
                f"Bande {bande_forcee} Hz non supportée par universr "
                f"(autorisées : {', '.join(map(str, BANDES_AUTORISEES))})."
            )
        return bande_forcee
    if frequence in BANDES_AUTORISEES:
        return frequence
    candidates = [b for b in BANDES_AUTORISEES if b < frequence]
    if not candidates:
        raise ValueError(
            f"Entrée à {frequence} Hz : au-dessus de la bande max universr "
            f"({BANDE_MAX} Hz) — déjà pleine bande, super-résolution sans objet. "
            f"Forcer une bande avec --upsr-rate si c'est assumé."
        )
    return max(candidates)


def restaurer_universr(
    source: str,
    sortie: str,
    variante: str = RECIPE["variante"],
    bande: int = 0,
    steps: int = RECIPE["steps"],
    seed: int = RECIPE["seed"],
    threads: int = RECIPE["threads"],
) -> Dict[str, Any]:
    """Pipeline complet : bande auto/forcée → pré-rééchantillonnage → UniverSR CPU.

    Sortie WAV 48 kHz MONO (limite moteur, cf. docstring module).
    """
    modele = resoudre_modele(variante)
    frequence = detecter_frequence(source)
    if frequence <= 0:
        raise ValueError(f"Piste audio illisible ou sans flux audio : {source}")
    bande = choisir_bande(frequence, bande)

    entree = source
    if frequence != bande:
        ffmpeg = resoudre_ffmpeg()
        entree = os.path.splitext(sortie)[0] + f"_entree_{bande}.wav"
        print(f"🎚️ Pré-rééchantillonnage {frequence} → {bande} Hz (bande déclarée au modèle)")
        run_engine(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", source,
             "-af", f"aresample={bande}", "-ac", "1", "-c:a", "pcm_s16le", entree],
            capture=False, check=True, timeout=600, etiquette="ffmpeg resample bande",
        )

    cmd = [
        resoudre_audiocpp(), "--task", "s2s", "--family", "universr",
        "--model", modele, "--backend", "cpu", "--threads", str(threads),
        "--audio", entree,
        "--request-option", f"input_sample_rate={bande}",
        "--request-option", f"num_inference_steps={steps}",
        "--request-option", f"seed={seed}",
        "--metrics", "--out", sortie,
    ]
    print(f"🧪 UniverSR ({variante}, bande {bande} Hz, CPU {threads} threads — "
          f"RTF ~13, prévoir plusieurs minutes)")
    # Progression en direct : RTF ~13 en CPU (28 s → ~6 min, voix 3 min → ~40 min)
    run_engine(cmd, capture=False, check=True, timeout=7200, etiquette="audio.cpp universr")
    if entree != source:
        os.remove(entree)
    if not os.path.exists(sortie):
        raise RuntimeError(f"La restauration n'a pas produit {sortie}")
    return {"sortie": sortie, "bande": bande, "variante": variante,
            "frequence_source": frequence}
