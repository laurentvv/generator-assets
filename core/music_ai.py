#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génération musicale IA locale : MiniMax-Music3 GGUF via audio.cpp (Vulkan),
fabrication de boucles sans couture et préparation de lits musicaux (« beds »)
discrets derrière une voix off.

Chaîne de traitement :
1. Génération audio.cpp  → WAV stéréo 32 kHz (fallback CPU si Vulkan échoue)
2. Fabrication de la boucle → percussive (alignée BPM/mesures) ou ambiante (crossfade 1 s)
3. Post-traitement « lit derrière voix » → highpass 80 Hz + creux présence -3 dB @ 2.8 kHz
4. Exports → WAV 48 kHz PCM16 pleine + « bed » normalisé LUFS + OGG boucle + MP3
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from math import gcd
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import scipy.signal
import soundfile

from core.config import (
    ACESTEP15_VARIANTES,
    DEFAULT_AUDIOCPP_CLI,
    DEFAULT_FFMPEG,
    DEFAULT_LLAMA_CLI,
    DEFAULT_MUSIC_FLAMINGO_LM,
    DEFAULT_MUSIC_FLAMINGO_MMPROJ,
    resoudre_gguf_acestep15,
    resoudre_modele_musique,
)

SR_CIBLE = 48000
SEUIL_SILENCE_RMS = 1e-4


# ==============================================================================
# Résolution des exécutables
# ==============================================================================

def resoudre_audiocpp(chemin: Optional[str] = None) -> str:
    """Résout le chemin de audiocpp_cli.exe (env, défaut, recherche récursive, PATH)."""
    candidats = [chemin, DEFAULT_AUDIOCPP_CLI] if chemin else [DEFAULT_AUDIOCPP_CLI]
    for c in candidats:
        if c and os.path.exists(c):
            return c

    base = os.path.dirname(DEFAULT_AUDIOCPP_CLI)
    if os.path.isdir(base):
        for racine, _, fichiers in os.walk(base):
            for f in fichiers:
                if f.lower() == "audiocpp_cli.exe":
                    return os.path.join(racine, f)

    return shutil.which("audiocpp_cli") or DEFAULT_AUDIOCPP_CLI


def resoudre_ffmpeg() -> str:
    """Résout le chemin de ffmpeg (défaut Amuse, sinon PATH)."""
    if os.path.exists(DEFAULT_FFMPEG):
        return DEFAULT_FFMPEG
    return shutil.which("ffmpeg") or DEFAULT_FFMPEG


# ==============================================================================
# Génération MiniMax-Music3 via audio.cpp
# ==============================================================================

def generer_musique_music3(
    description: str,
    chemin_sortie: str,
    duree: float = 14.0,
    etapes: int = 30,
    backend: str = "vulkan",
    lyrics: str = "[Instrumental]",
    graine: int = -1,
    log: Callable[[str], None] = print,
    timeout_s: int = 2400,
) -> Tuple[str, str]:
    """
    Génère un extrait musical via audiocpp_cli (famille minimax_music3).
    Retourne (chemin_wav, backend_utilisé). Bascule sur CPU si Vulkan échoue.
    """
    exe = resoudre_audiocpp()
    if not os.path.exists(exe):
        raise FileNotFoundError(
            f"audiocpp_cli.exe introuvable : {exe}\n"
            "→ Lancez : uv run python scripts/download_music3_gguf.py"
        )

    dossier_modele = resoudre_modele_musique()
    os.makedirs(os.path.dirname(os.path.abspath(chemin_sortie)), exist_ok=True)

    def _construire(backend_cible: str, avec_graine: bool) -> List[str]:
        cmd = [
            exe, "--task", "gen", "--family", "minimax_music3",
            "--model", dossier_modele, "--backend", backend_cible,
            "--threads", "16", "--log", "--metrics",
            "--text", description,
            "--request-option", f"lyrics={lyrics}",
            "--request-option", f"duration_sec={int(round(duree))}",
            "--request-option", f"num_inference_steps={int(etapes)}",
            "--out", chemin_sortie,
        ]
        if avec_graine and graine >= 0:
            cmd += ["--request-option", f"seed={int(graine)}"]
        return cmd

    backends = ["vulkan", "cpu"] if backend in ("vulkan", "auto") else ["cpu"]
    essais = []
    for b in backends:
        # Vulkan : 2 tentatives (un reset du pilote GPU AMD est récupérable)
        nb_fois = 2 if b == "vulkan" else 1
        for _ in range(nb_fois):
            essais.append((b, True))
        if graine >= 0:
            essais.append((b, False))

    derniere_erreur: Optional[str] = None
    for i, (backend_cible, avec_graine) in enumerate(essais):
        if i > 0:
            log(f"🔄 Nouvel essai : backend={backend_cible}, graine={'oui' if avec_graine else 'non'}...")
            time.sleep(5.0)
        cmd = _construire(backend_cible, avec_graine)
        try:
            resultat = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            derniere_erreur = f"timeout après {timeout_s}s"
            continue

        erreurs = (resultat.stderr or "") + (resultat.stdout or "")
        if resultat.returncode == 0 and os.path.exists(chemin_sortie) and os.path.getsize(chemin_sortie) > 4096:
            # Garde-fou anti-silence : le modèle peut s'effondrer en queue de morceau
            audio, sr = soundfile.read(chemin_sortie, always_2d=True)
            if float(np.sqrt((audio ** 2).mean())) < SEUIL_SILENCE_RMS:
                derniere_erreur = "sortie quasiment silencieuse (effondrement du modèle)"
                os.remove(chemin_sortie)
                continue
            for ligne in (resultat.stdout or "").splitlines():
                if "RTF" in ligne or "wall" in ligne.lower():
                    log(f"⏱️  {ligne.strip()}")
            return chemin_sortie, backend_cible

        if "seed" in erreurs.lower() and avec_graine:
            # Option graine refusée par cette build → réessai sans (déjà dans la liste)
            derniere_erreur = f"option seed refusée :: {erreurs.strip()[-300:]}"
            continue

        extrait = erreurs.strip()[-600:]
        derniere_erreur = f"code {resultat.returncode} :: {extrait}"

    raise RuntimeError(f"Génération MiniMax-Music3 impossible. Dernière erreur : {derniere_erreur}")


# ==============================================================================
# Génération ACE-Step 1.5 via audio.cpp (famille ace_step)
# ==============================================================================

LYRICS_INSTRUMENTAL = ("", "[instrumental]", "[Instrumental]", "instrumental")


def generer_musique_acestep(
    description: str,
    chemin_sortie: str,
    duree: float = 14.0,
    etapes: int = 8,
    backend: str = "vulkan",
    lyrics: str = "[Instrumental]",
    graine: int = -1,
    bpm: Optional[int] = None,
    tonalite: Optional[str] = None,
    mesure: Optional[str] = None,
    negatif: Optional[str] = None,
    variante: str = "turbo",
    langue: str = "en",
    log: Callable[[str], None] = print,
    timeout_s: int = 2400,
) -> Tuple[str, str]:
    """
    Génère un extrait musical via audiocpp_cli (famille ace_step, ACE-Step 1.5
    bf16). Retourne (chemin_wav, backend_utilisé). Bascule sur CPU si
    Vulkan échoue.

    Variantes : turbo (DiT 2B distillé, défaut) | xl-turbo (DiT 4B distillé,
    ~1,8× plus lent) | xl-sft (DiT 4B avec CFG, plus de pas requis).

    Spécificités ACE-Step 1.5 :
    - lyrics vide = instrumental natif (pas de méta-tag à passer)
    - 8 pas suffisent pour les variantes distillées (turbo)
    - BPM / tonalité / signature peuvent être imposés au planner (request
      options bpm / keyscale / timesignature) → boucles alignées au mesure
      garanties, au lieu d'estimer le tempo a posteriori
    """
    exe = resoudre_audiocpp()
    if not os.path.exists(exe):
        raise FileNotFoundError(
            f"audiocpp_cli.exe introuvable : {exe}\n"
            "→ Lancez : uv run python scripts/download_music3_gguf.py"
        )

    # Le paquet est monolithique : audio.cpp exige le chemin du .gguf lui-même
    # (les configs/tokenizers sont embarqués dans le fichier — embedded_sidecars).
    gguf = resoudre_gguf_acestep15(variante)
    if not os.path.exists(gguf):
        raise FileNotFoundError(
            f"GGUF ACE-Step 1.5 ({variante}) introuvable : {gguf}\n"
            "→ Lancez : uv run python scripts/download_acestep15_gguf.py\n"
            "  (variantes XL : miroir ModelScope, voir docs/MEMORY_BANK.md §1.11)"
        )
    _, dit_model_path = ACESTEP15_VARIANTES[variante]
    os.makedirs(os.path.dirname(os.path.abspath(chemin_sortie)), exist_ok=True)

    instrumental = (lyrics or "").strip() in LYRICS_INSTRUMENTAL

    def _construire(backend_cible: str) -> List[str]:
        cmd = [
            exe, "--task", "gen", "--family", "ace_step",
            "--model", gguf, "--backend", backend_cible,
            "--task-route", "text2music",
            "--threads", "16", "--log", "--metrics",
            "--text", description,
            "--duration-seconds", f"{int(round(duree))}",
            "--num-inference-steps", str(int(etapes)),
            # Un seul morceau par processus : libérer la VRAM de graphe est gratuit
            "--session-option", "ace_step.mem_saver=true",
            "--out", chemin_sortie,
        ]
        if dit_model_path:
            # Les paquets GGUF sont spécifiques à une variante : il faut la nommer
            cmd += ["--load-option", f"ace_step.dit_model_path={dit_model_path}"]
        if not instrumental:
            cmd += ["--lyrics", lyrics, "--language", langue]
        if graine >= 0:
            cmd += ["--seed", str(int(graine))]
        if bpm:
            cmd += ["--request-option", f"bpm={int(bpm)}"]
        if tonalite:
            cmd += ["--request-option", f"keyscale={tonalite}"]
        if mesure:
            cmd += ["--request-option", f"timesignature={mesure}"]
        if negatif:
            cmd += ["--request-option", f"negative_prompt={negatif}"]
        return cmd

    backends = ["vulkan", "cpu"] if backend in ("vulkan", "auto") else ["cpu"]
    essais = []
    for b in backends:
        # Vulkan : 2 tentatives (un reset du pilote GPU AMD est récupérable)
        essais += [b] * (2 if b == "vulkan" else 1)

    derniere_erreur: Optional[str] = None
    for i, backend_cible in enumerate(essais):
        if i > 0:
            log(f"🔄 Nouvel essai : backend={backend_cible}...")
            time.sleep(5.0)
        cmd = _construire(backend_cible)
        try:
            resultat = subprocess.run(
                cmd, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            derniere_erreur = f"timeout après {timeout_s}s"
            continue

        erreurs = (resultat.stderr or "") + (resultat.stdout or "")
        if resultat.returncode == 0 and os.path.exists(chemin_sortie) and os.path.getsize(chemin_sortie) > 4096:
            # Garde-fou anti-silence (même risque d'effondrement que Music3)
            audio, _sr = soundfile.read(chemin_sortie, always_2d=True)
            if float(np.sqrt((audio ** 2).mean())) < SEUIL_SILENCE_RMS:
                derniere_erreur = "sortie quasiment silencieuse (effondrement du modèle)"
                os.remove(chemin_sortie)
                continue
            for ligne in (resultat.stdout or "").splitlines():
                if "RTF" in ligne or "wall" in ligne.lower():
                    log(f"⏱️  {ligne.strip()}")
            return chemin_sortie, backend_cible

        extrait = erreurs.strip()[-600:]
        derniere_erreur = f"code {resultat.returncode} :: {extrait}"

    raise RuntimeError(f"Génération ACE-Step 1.5 impossible. Dernière erreur : {derniere_erreur}")


# ==============================================================================
# DSP : chargement, BPM, bouclage, post-traitement
# ==============================================================================

def charger_audio(chemin: str) -> Tuple[np.ndarray, int]:
    """Charge un fichier audio en tableau float [échantillons, canaux]."""
    audio, sr = soundfile.read(chemin, always_2d=True, dtype="float64")
    return audio, sr


def _mono(audio: np.ndarray) -> np.ndarray:
    return audio.mean(axis=1) if audio.ndim > 1 else audio


def estimer_bpm(audio: np.ndarray, sr: int) -> Optional[float]:
    """Estime le tempo (BPM) par autocorrélation de l'enveloppe d'onsets (60-180 BPM)."""
    mono = _mono(audio)
    hop, fen = 256, 1024
    n_frames = max(2, (len(mono) - fen) // hop)
    frames = np.lib.stride_tricks.sliding_window_view(mono, fen)[::hop][:n_frames]
    energie = np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-10)
    flux = np.maximum(0.0, np.diff(energie))
    if flux.std() < 1e-6:
        return None

    flux = flux - flux.mean()
    autocorr = np.correlate(flux, flux, mode="full")[len(flux) - 1:]
    fps = sr / hop
    lag_min = max(1, int(fps * 60 / 180))
    lag_max = min(int(fps * 60 / 60), len(autocorr) - 1)
    if lag_max <= lag_min + 1:
        return None

    meilleur_lag = lag_min + int(np.argmax(autocorr[lag_min:lag_max]))
    if meilleur_lag <= 0:
        return None
    bpm = 60.0 * fps / meilleur_lag
    while bpm < 70.0:
        bpm *= 2.0
    while bpm > 180.0:
        bpm /= 2.0
    return round(bpm, 1)


def _trouver_passage_zero(audio: np.ndarray, index: int, sr: int, fenetre_ms: float = 10.0) -> int:
    """Snappe un index sur le passage par zéro le plus proche (± fenetre_ms)."""
    mono = _mono(audio)
    rayon = int(fenetre_ms / 1000.0 * sr)
    debut, fin = max(0, index - rayon), min(len(mono) - 1, index + rayon)
    meilleur, distance = index, rayon + 1
    for i in range(debut, fin):
        if mono[i] == 0.0 or (mono[i] < 0) != (mono[i + 1] < 0):
            d = abs(i - index)
            if d < distance:
                meilleur, distance = i, d
    return meilleur


def _zone_stable(audio: np.ndarray, sr: int, seuil_rel: float = 0.5) -> Tuple[int, int]:
    """
    Délimite la zone d'énergie stable (en échantillons) : ignore les intros/outros
    en fondu que produit souvent le modèle. Le seuil est relatif à la médiane de
    l'énergie du cœur du morceau (20 %-80 %).
    """
    mono = _mono(audio)
    fen = max(1, int(0.05 * sr))
    n = max(1, len(mono) // fen)
    env = np.array([
        float(np.sqrt((mono[i * fen:(i + 1) * fen] ** 2).mean() + 1e-12)) for i in range(n)
    ])
    milieu = env[int(n * 0.2):int(n * 0.8) + 1] if n >= 5 else env
    seuil = seuil_rel * float(np.median(milieu))

    debut_idx = 0
    for i, e in enumerate(env):
        if e >= seuil:
            debut_idx = i
            break
    fin_idx = n - 1
    for i in range(n - 1, -1, -1):
        if env[i] >= seuil:
            fin_idx = i
            break
    return debut_idx * fen, min(len(mono), (fin_idx + 1) * fen)


def _rms_db_cumul(cumsum_carres: np.ndarray, debut: int, fin: int) -> float:
    """RMS (dB) d'une tranche via somme cumulée des carrés (O(1))."""
    n = max(1, fin - debut)
    energie = float(cumsum_carres[fin] - cumsum_carres[debut]) / n
    return 10.0 * np.log10(max(energie, 1e-12))


def fabriquer_boucle_percussive(
    audio: np.ndarray, sr: int, bpm: float, duree_cible: float = 12.0
) -> Tuple[np.ndarray, Dict]:
    """
    Recherche du meilleur point de boucle : parmi toutes les fenêtres d'un nombre
    entier de mesures (durée ≥ duree_cible, jusqu'à +30 %), retient celle dont la
    tête et la queue s'apparient le mieux en énergie (couture), en pénalisant les
    extrémités trop faibles (intro/outro en fondu) et les trous profonds.
    Extrémités snappées sur passages par zéro + micro-fondu equal-power 20 ms :
    la longueur exacte en mesures garantit la continuité rythmique.
    """
    duree_mesure = 4.0 * 60.0 / bpm
    mono = _mono(audio)
    n_total = len(mono)
    ech_mesure = duree_mesure * sr

    k_min = max(1, int(np.ceil(duree_cible / duree_mesure - 1e-6)))
    k_max = max(k_min, int(np.floor(duree_cible * 1.3 / duree_mesure)))
    candidats_k = [k for k in range(k_max, k_min - 1, -1) if int(round(k * ech_mesure)) <= n_total]
    if not candidats_k:
        candidats_k = [max(1, int(np.floor(n_total / ech_mesure)))]

    cumsum = np.concatenate([[0.0], np.cumsum(mono.astype(np.float64) ** 2)])
    # Plusieurs largeurs de fenêtre aux bords : une seule (200 ms) peut masquer un
    # fondu très court en tête ou en queue
    fen_bords = [int(w * sr) for w in (0.05, 0.1, 0.2, 0.5)]
    hop = max(1, int(0.05 * sr))
    fen_trou = int(1.0 * sr)
    n_trames = max(1, (n_total - fen_trou) // hop)
    env_1s_db = np.array([
        _rms_db_cumul(cumsum, i * hop, i * hop + fen_trou) for i in range(n_trames)
    ])

    pas = max(1, int(0.02 * sr))
    # La recherche est restreinte à la zone d'énergie stable : ACE-Step (comme
    # tout modèle compositionnel) termine ses morceaux par un fondu de sortie de
    # plusieurs secondes — une fenêtre qui s'y termine produit une couture
    # catastrophique (queue quasi silencieuse).
    debut_stable, fin_stable = _zone_stable(audio, sr)
    meilleur = None
    for k in candidats_k:
        longueur = int(round(k * ech_mesure))
        bornes = range(debut_stable, min(fin_stable, n_total) - longueur + 1, pas)
        if not len(bornes):
            # Zone stable trop courte pour k mesures → recherche sur tout l'audio
            bornes = range(0, n_total - longueur + 1, pas)
        for debut in bornes:
            fin = debut + longueur
            ecarts, tetes, queues = [], [], []
            for fb in fen_bords:
                t_db = _rms_db_cumul(cumsum, debut, min(fin, debut + fb))
                q_db = _rms_db_cumul(cumsum, max(debut, fin - fb), fin)
                ecarts.append(abs(t_db - q_db))
                tetes.append(t_db)
                queues.append(q_db)
            couture = max(ecarts)
            tete, queue = tetes[1], queues[1]

            i0, i1 = debut // hop, max(debut // hop + 1, min(n_trames, (fin - fen_trou) // hop))
            tranche = env_1s_db[i0:i1]
            mediane = float(np.median(tranche)) if len(tranche) else _rms_db_cumul(cumsum, debut, fin)
            creux = float(tranche.min()) if len(tranche) else mediane

            score = couture
            score += 0.5 * max(0.0, (mediane - 12.0) - min(tete, queue))
            score += 0.3 * max(0.0, (mediane - creux) - 15.0)
            score -= 0.02 * k
            if meilleur is None or score < meilleur[0]:
                meilleur = (score, debut, fin, k, couture)

    score, debut, fin, mesures, couture = meilleur
    debut = _trouver_passage_zero(audio, debut, sr, fenetre_ms=5.0)
    fin = min(n_total, _trouver_passage_zero(audio, fin, sr, fenetre_ms=5.0))
    boucle = audio[debut:fin].copy()

    xf = min(int(0.020 * sr), len(boucle) // 4)
    if xf > 8:
        tail = boucle[-xf:].copy()
        t = np.linspace(0.0, np.pi / 2.0, xf)
        boucle[:xf] = boucle[:xf] * np.cos(t)[:, None] + tail * np.sin(t)[:, None]

    infos = {
        "strategie": "percussive",
        "bpm": bpm,
        "mesures": mesures,
        "duree": round(len(boucle) / sr, 3),
        "crossfade_ms": round(xf / sr * 1000, 1),
        "depart_s": round(debut / sr, 2),
        "couture_estimee_db": round(float(couture), 1),
        "score": round(float(score), 2),
    }
    return boucle, infos


def fabriquer_boucle_ambiante(
    audio: np.ndarray, sr: int, crossfade_s: float = 1.0
) -> Tuple[np.ndarray, Dict]:
    """
    Boucle ambiante découpée dans la zone d'énergie stable :
    fondu enchaîné equal-power long (~1 s) queue→tête.
    """
    debut_stable, fin_stable = _zone_stable(audio, sr)
    segment = audio[debut_stable:fin_stable]

    xf = min(int(crossfade_s * sr), (len(segment) - 1) // 2)
    boucle = segment[:-xf].copy() if xf > 0 else segment.copy()
    if xf > 8:
        queue = segment[-xf:].copy()
        t = np.linspace(0.0, np.pi / 2.0, xf)
        boucle[:xf] = boucle[:xf] * np.cos(t)[:, None] + queue * np.sin(t)[:, None]

    infos = {
        "strategie": "ambiante",
        "bpm": None,
        "mesures": None,
        "duree": round(len(boucle) / sr, 3),
        "crossfade_ms": round(xf / sr * 1000, 1),
        "depart_s": round(debut_stable / sr, 2),
    }
    return boucle, infos


def fabriquer_boucle(
    audio: np.ndarray, sr: int, duree_cible: float = 12.0, mode: str = "percussive"
) -> Tuple[np.ndarray, Dict]:
    """Fabrique la boucle sans couture ; bascule en ambiante si aucun BPM fiable."""
    if mode == "percussive":
        bpm = estimer_bpm(audio, sr)
        if bpm is not None:
            return fabriquer_boucle_percussive(audio, sr, bpm, duree_cible)
        # Pas de pulsatilité détectée → fondu long plus sûr
    return fabriquer_boucle_ambiante(audio, sr)


def _biquad_peaking(sr: int, f0: float, q: float, gain_db: float) -> Tuple[np.ndarray, np.ndarray]:
    """Filtre biquad peak EQ (formules RBJ Audio EQ Cookbook)."""
    a_amp = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * np.pi * f0 / sr
    alpha = np.sin(w0) / (2.0 * q)
    b0 = 1.0 + alpha * a_amp
    b1 = -2.0 * np.cos(w0)
    b2 = 1.0 - alpha * a_amp
    a0 = 1.0 + alpha / a_amp
    a1 = -2.0 * np.cos(w0)
    a2 = 1.0 - alpha / a_amp
    return np.array([b0, b1, b2]) / a0, np.array([a0, a1, a2]) / a0


def post_traiter_lit_voix(audio: np.ndarray, sr: int) -> np.ndarray:
    """
    Prépare le lit musical pour rester discret derrière une voix (masculine) :
    - highpass 80 Hz (2e ordre) : libère le registre grave de la voix
    - creux -3 dB @ 2.8 kHz (Q=1) : libère la zone de présence/intelligibilité
    """
    sos = scipy.signal.butter(2, 80.0, btype="highpass", fs=sr, output="sos")
    audio = scipy.signal.sosfiltfilt(sos, audio, axis=0)
    b, a = _biquad_peaking(sr, 2800.0, 1.0, -3.0)
    audio = scipy.signal.filtfilt(b, a, audio, axis=0)
    return audio


def ressampler(audio: np.ndarray, sr_orig: int, sr_cible: int = SR_CIBLE) -> Tuple[np.ndarray, int]:
    """Rééchantillonne au rapport rationnel (ex. 32 kHz → 48 kHz = 3:2)."""
    if sr_orig == sr_cible:
        return audio, sr_cible
    g = gcd(sr_orig, sr_cible)
    up, down = sr_cible // g, sr_orig // g
    return scipy.signal.resample_poly(audio, up, down, axis=0), sr_cible


def normaliser_pic(audio: np.ndarray, pic_dbfs: float = -1.0) -> np.ndarray:
    """Normalise le pic à pic_dbfs (défaut -1 dBFS, anti-clipping)."""
    pic = float(np.abs(audio).max())
    if pic < 1e-9:
        return audio
    cible = 10.0 ** (pic_dbfs / 20.0)
    return audio * (cible / pic)


# ==============================================================================
# Mesure LUFS & exports via ffmpeg
# ==============================================================================

def mesurer_lufs(chemin: str, filtre_amont: Optional[str] = None) -> Dict[str, float]:
    """Mesure l'intensité intégrée (LUFS) et paramètres loudnorm via ffmpeg.

    `filtre_amont` (ex. un limiteur) est appliqué AVANT la mesure — permet de mesurer
    le signal tel qu'il entrera dans l'étape de normalisation.
    """
    ffmpeg = resoudre_ffmpeg()
    chaine = f"{filtre_amont},loudnorm=print_format=json" if filtre_amont else "loudnorm=print_format=json"
    cmd = [ffmpeg, "-hide_banner", "-i", chemin, "-af", chaine, "-f", "null", "-"]
    resultat = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120
    )
    texte = resultat.stderr or ""
    correspondances = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", texte, flags=re.DOTALL)
    if not correspondances:
        raise RuntimeError(f"Impossible de mesurer le LUFS de {chemin}")

    brut = json.loads(correspondances[-1])
    return {
        "I": float(brut.get("input_i", "-70")),
        "TP": float(brut.get("input_tp", "-70")),
        "LRA": float(brut.get("input_lra", "0")),
        "thresh": float(brut.get("input_thresh", "-70")),
        "offset": float(brut.get("target_offset", "0")),
        "gain_db": float(brut.get("input_i", "-70")),
    }


def exporter_bed_lufs(chemin_source: str, chemin_sortie: str, lufs_cible: float = -30.0) -> Dict[str, float]:
    """Normalise un WAV vers lufs_cible (loudnorm 2 passes, mode linéaire quand possible)."""
    ffmpeg = resoudre_ffmpeg()
    mesures = mesurer_lufs(chemin_source)

    ecart = abs(mesures["I"] - lufs_cible)
    filtre = (
        f"loudnorm=I={lufs_cible}:TP=-3.0:LRA=7.0:"
        f"measured_I={mesures['I']}:measured_TP={mesures['TP']}:"
        f"measured_LRA={mesures['LRA']}:measured_thresh={mesures['thresh']}:"
        f"offset={mesures['offset']}:linear=true"
        if ecart <= 30.0
        else f"loudnorm=I={lufs_cible}:TP=-3.0:LRA=7.0"
    )
    cmd = [ffmpeg, "-hide_banner", "-y", "-i", chemin_source, "-af", filtre,
           "-ar", str(SR_CIBLE), "-c:a", "pcm_s16le", chemin_sortie]
    subprocess.run(cmd, check=True, capture_output=True, timeout=180)
    return mesurer_lufs(chemin_sortie)


def convertir_mp3(chemin_source: str, chemin_sortie: str, debit_k: int = 192) -> str:
    """Convertit vers MP3 (aperçu léger pour écoute rapide)."""
    ffmpeg = resoudre_ffmpeg()
    cmd = [ffmpeg, "-hide_banner", "-y", "-i", chemin_source, "-c:a", "libmp3lame",
           "-b:a", f"{debit_k}k", chemin_sortie]
    subprocess.run(cmd, check=True, capture_output=True, timeout=180)
    return chemin_sortie


def convertir_ogg(chemin_source: str, chemin_sortie: str, qualite: int = 5) -> str:
    """
    Convertit vers OGG Vorbis via ffmpeg.
    ⚠️ Ne PAS utiliser soundfile pour l'OGG : son libsndfile fait un stack
    overflow C (exit 127 silencieux) sur les fichiers de plus de quelques
    secondes — crash confirmé sous Windows sur ce poste.
    """
    ffmpeg = resoudre_ffmpeg()
    cmd = [ffmpeg, "-hide_banner", "-y", "-i", chemin_source, "-c:a", "libvorbis",
           "-qscale:a", str(qualite), chemin_sortie]
    subprocess.run(cmd, check=True, capture_output=True, timeout=180)
    return chemin_sortie


# ==============================================================================
# Validation des boucles
# ==============================================================================

def _rms_db(audio: np.ndarray) -> float:
    rms = float(np.sqrt((audio ** 2).mean()))
    return 20.0 * np.log10(max(rms, 1e-10))


def verifier_boucle(chemin: str) -> Dict:
    """
    Vérifie qu'un WAV boucle proprement : continuité de couture (RMS 100 ms
    début vs fin), absence de clipping, durée, LUFS.
    """
    audio, sr = charger_audio(chemin)
    fen = int(0.1 * sr)
    rms_debut = _rms_db(audio[:fen])
    rms_fin = _rms_db(audio[-fen:])
    pic_dbfs = 20.0 * np.log10(max(float(np.abs(audio).max()), 1e-10))

    ecart_couture = abs(rms_debut - rms_fin)
    return {
        "duree_s": round(len(audio) / sr, 3),
        "sr": sr,
        "rms_debut_db": round(rms_debut, 1),
        "rms_fin_db": round(rms_fin, 1),
        "ecart_couture_db": round(ecart_couture, 1),
        "pic_dbfs": round(pic_dbfs, 1),
        "clipping": pic_dbfs > -0.1,
        "propre": ecart_couture <= 6.0 and pic_dbfs <= -0.1,
    }


def empreinte_fichier(chemin: str) -> str:
    """Empreinte MD5 (détection de générations identiques quand la graine n'est pas supportée)."""
    h = hashlib.md5()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloc)
    return h.hexdigest()


# ==============================================================================
# Analyse optionnelle Music Flamingo (compréhension musicale via llama.cpp)
# ==============================================================================

PROMPT_ANALYSE = (
    "You are a professional music QA engineer. Analyze this audio loop and answer "
    "with a single compact JSON object, nothing else: "
    '{"bpm": <estimated tempo number>, "instrumental": <true|false>, '
    '"energy_1_to_10": <number>, "suitable_as_subtle_background_under_voice": <true|false>, '
    '"one_line_note": "<short note in French>"}'
)


def analyser_boucle_flamingo(
    chemin_wav: str, log: Callable[[str], None] = print, timeout_s: int = 900
) -> Optional[Dict]:
    """
    QA optionnelle d'une boucle via Music Flamingo (llama-cli + mmproj audio).
    Retourne un dict d'analyse ou None si indisponible (jamais bloquant).
    ⚠️ Licence NVIDIA non commerciale.
    """
    manquants = [
        c for c in (DEFAULT_LLAMA_CLI, DEFAULT_MUSIC_FLAMINGO_LM, DEFAULT_MUSIC_FLAMINGO_MMPROJ)
        if not os.path.exists(c)
    ]
    if manquants:
        log(f"⚠️ Analyse Music Flamingo ignorée (fichiers manquants : {manquants})")
        return None

    cmd = [
        DEFAULT_LLAMA_CLI, "-m", DEFAULT_MUSIC_FLAMINGO_LM,
        "--mmproj", DEFAULT_MUSIC_FLAMINGO_MMPROJ,
        "--audio", chemin_wav,
        "-p", PROMPT_ANALYSE, "-n", "220", "--no-display-prompt",
        "--temp", "0.1", "-ngl", "99",
    ]
    try:
        resultat = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        log("⚠️ Analyse Music Flamingo : timeout, ignorée.")
        return None

    sortie = resultat.stdout or ""
    erreurs = (resultat.stderr or "").lower()
    if resultat.returncode != 0:
        if "audio" in erreurs and ("unrecognized" in erreurs or "unknown argument" in erreurs):
            log("⚠️ Analyse Music Flamingo : ce llama-cli ne supporte pas l'entrée audio (--audio), ignorée.")
        else:
            log("⚠️ Analyse Music Flamingo : échec llama-cli, ignorée.")
        return None

    correspondance = re.search(r"\{.*\}", sortie, flags=re.DOTALL)
    if not correspondance:
        log("⚠️ Analyse Music Flamingo : réponse illisible, ignorée.")
        return None
    try:
        return json.loads(correspondance.group(0))
    except json.JSONDecodeError:
        return None


# ==============================================================================
# Recette de mixage sous voix (ducking sidechain)
# ==============================================================================

def construire_recette_ducking(
    chemin_voix: str, chemin_musique: str, chemin_sortie: str, volume_musique: float = 1.0
) -> str:
    """
    Commande ffmpeg prête à l'emploi : la boucle est répétée à la durée de la
    voix et automatiquement atténuée quand la voix parle (sidechaincompress),
    puis mixée (amix sans re-normalisation).
    """
    return (
        f'ffmpeg -y -i "{chemin_voix}" -stream_loop -1 -i "{chemin_musique}" -filter_complex '
        f'"[1:a]volume={volume_musique}[mus];'
        f'[mus][0:a]sidechaincompress=threshold=0.05:ratio=6:attack=80:release=600[mus_duck];'
        f'[mus_duck][0:a]amix=inputs=2:duration=first:dropout_transition=3:normalize=0[aout]" '
        f'-map "[aout]" -c:a pcm_s16le "{chemin_sortie}"'
    )
