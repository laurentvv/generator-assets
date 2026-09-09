#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module de synthèse audio procédurale, effets sonores (SFX), ambiances et voix émotionnelles pour Godot 4.
Supporte :
- Effets sonores procéduraux (SFX)
- Synthèse vocale émotionnelle (TTS) avec modulation (Pitch, Formants, Tremolo, Saturation)
- Extraction de visèmes pour Lip-Sync Godot
- Ambiances procédurales multicouches (Donjon, Forêt, Orage, Espace, Feu de camp) en boucle sans couture
- Export WAV (PCM 16-bit), OGG Vorbis et Bus Audio Godot (.tres)
"""

import math
import os
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import scipy.signal as signal
import soundfile as sf


def _appliquer_enveloppe_adsr(
    signal_in: np.ndarray,
    sr: int,
    attack: float = 0.01,
    decay: float = 0.1,
    sustain_level: float = 0.7,
    sustain_time: float = 0.2,
    release: float = 0.2
) -> np.ndarray:
    """Applique une enveloppe ADSR sur un signal numpy."""
    n_a = int(attack * sr)
    n_d = int(decay * sr)
    n_s = int(sustain_time * sr)
    n_r = int(release * sr)
    total = n_a + n_d + n_s + n_r

    if total > len(signal_in):
        signal_in = np.pad(signal_in, (0, total - len(signal_in)))
    else:
        signal_in = signal_in[:total]

    env = np.zeros(total, dtype=np.float32)
    if n_a > 0:
        env[:n_a] = np.linspace(0.0, 1.0, n_a)
    if n_d > 0:
        env[n_a:n_a + n_d] = np.linspace(1.0, sustain_level, n_d)
    if n_s > 0:
        env[n_a + n_d:n_a + n_d + n_s] = sustain_level
    if n_r > 0:
        env[n_a + n_d + n_s:total] = np.linspace(sustain_level, 0.0, n_r)

    return (signal_in[:total] * env).astype(np.float32)


# ==============================================================================
# 1. Synthèse SFX Procédurale
# ==============================================================================

def synthetiser_sfx(
    sfx_type: str = "sword",
    duree: float = 1.0,
    sr: int = 44100
) -> np.ndarray:
    """
    Synthétise un effet sonore procédural haute qualité.
    
    Types disponibles :
    - 'sword' / 'slash' / 'whoosh' : Tranchant d'épée avec bruit filtré balayé
    - 'coin' / 'pickup' : Clochette magique ou pièce rétro (chime harmonique)
    - 'explosion' / 'impact' : Onde de choc basse fréquence et saturation
    - 'potion' / 'bubble' : Glouglou magique avec modulation de fréquence
    - 'magic' / 'spell' : Shimmering magique et nappe d'énergie
    - 'jump' / 'powerup' : Glissando ascendant
    - 'chest' : Grincement de coffre et cliquetis
    """
    t = np.linspace(0, duree, int(sr * duree), endpoint=False)
    sfx_type = sfx_type.lower()

    if any(k in sfx_type for k in ["sword", "slash", "whoosh", "blade"]):
        bruit = np.random.uniform(-1.0, 1.0, len(t))
        freq_env = np.geomspace(3500.0, 250.0, len(t))
        sos = signal.butter(4, [200, 4000], btype='bandpass', fs=sr, output='sos')
        filtre = signal.sosfilt(sos, bruit)
        son = _appliquer_enveloppe_adsr(filtre, sr, attack=0.005, decay=0.08, sustain_level=0.15, sustain_time=0.05, release=0.15)

    elif any(k in sfx_type for k in ["coin", "pickup", "gem", "gold"]):
        n_half = len(t) // 2
        f1 = np.sin(2 * np.pi * 987.77 * t[:n_half])
        f2 = np.sin(2 * np.pi * 1318.51 * t[n_half:])
        son = np.concatenate([f1, f2])
        chime = 0.3 * np.sin(2 * np.pi * 2637.0 * t)
        son = son[:len(t)] + chime
        son = _appliquer_enveloppe_adsr(son, sr, attack=0.002, decay=0.1, sustain_level=0.4, sustain_time=0.1, release=0.25)

    elif any(k in sfx_type for k in ["explosion", "boom", "impact", "blast"]):
        bruit = np.random.uniform(-1.0, 1.0, len(t))
        sos = signal.butter(4, 300, btype='lowpass', fs=sr, output='sos')
        sub = signal.sosfilt(sos, bruit) * 1.5
        sub_drop = np.sin(2 * np.pi * np.geomspace(140.0, 20.0, len(t)) * t)
        son = sub + sub_drop * 0.8
        son = np.tanh(son * 1.8)
        son = _appliquer_enveloppe_adsr(son, sr, attack=0.005, decay=0.2, sustain_level=0.3, sustain_time=0.2, release=0.5)

    elif any(k in sfx_type for k in ["potion", "drink", "bubble", "liquid"]):
        son = np.zeros_like(t)
        for i in range(5):
            t_start = int((0.05 + i * 0.12) * sr)
            if t_start < len(t):
                d_bubble = int(0.08 * sr)
                t_b = np.linspace(0, 0.08, d_bubble)
                freq = 400.0 + i * 80.0
                bubble = np.sin(2 * np.pi * freq * (1.0 + 0.5 * t_b) * t_b)
                bubble *= np.hanning(len(bubble))
                end_idx = min(len(son), t_start + d_bubble)
                son[t_start:end_idx] += bubble[:end_idx - t_start]
        son = _appliquer_enveloppe_adsr(son, sr, attack=0.01, decay=0.1, sustain_level=0.5, sustain_time=0.3, release=0.2)

    elif any(k in sfx_type for k in ["magic", "spell", "portal", "cast"]):
        freqs = [440, 554.37, 659.25, 880, 1108.73, 1318.51]
        son = np.zeros_like(t)
        for idx, f in enumerate(freqs):
            mod = np.sin(2 * np.pi * 4.0 * t) * 10.0
            son += np.sin(2 * np.pi * (f + mod) * t) * (1.0 / (idx + 1))
        son = _appliquer_enveloppe_adsr(son, sr, attack=0.05, decay=0.2, sustain_level=0.6, sustain_time=0.4, release=0.4)

    elif any(k in sfx_type for k in ["jump", "powerup", "glide"]):
        freq_ramp = np.geomspace(150.0, 800.0, len(t))
        son = np.sin(2 * np.pi * freq_ramp * t)
        son = _appliquer_enveloppe_adsr(son, sr, attack=0.01, decay=0.05, sustain_level=0.8, sustain_time=0.1, release=0.15)

    else:
        bruit = np.random.uniform(-0.5, 0.5, len(t))
        latch = np.sin(2 * np.pi * 220.0 * t) * np.exp(-15.0 * t)
        son = bruit * np.exp(-8.0 * t) + latch
        son = _appliquer_enveloppe_adsr(son, sr, attack=0.01, decay=0.1, sustain_level=0.3, sustain_time=0.1, release=0.3)

    max_val = np.max(np.abs(son))
    if max_val > 0:
        son = (son / max_val) * 0.9

    return son.astype(np.float32)


# ==============================================================================
# 2. Synthèse Vocale Émotionnelle (TTS / Formants & Voice Modeling)
# ==============================================================================

# Formants standards des voyelles (F1, F2, F3 en Hz)
VOWEL_FORMANTS = {
    'a': (800, 1200, 2500),
    'e': (500, 1800, 2600),
    'i': (300, 2200, 3000),
    'o': (500, 1000, 2400),
    'u': (350, 800, 2300),
    'm': (250, 1000, 2200),
    's': (4000, 5500, 7000)
}


def extraire_visemes_phonetiques(texte: str, duree: float) -> List[Dict[str, Any]]:
    """Génère la timeline de visèmes phonétiques pour le lip-sync dans Godot."""
    mots = texte.lower().split()
    if not mots:
        return [{"time_start": 0.0, "time_end": round(duree, 2), "word": "", "viseme": "neutral"}]

    visemes = []
    t_par_mot = duree / max(len(mots), 1)

    for i, mot in enumerate(mots):
        t_debut = i * t_par_mot
        has_o = any(c in mot for c in 'ouo')
        has_e = any(c in mot for c in 'eiy')
        has_a = any(c in mot for c in 'a')
        has_m = any(c in mot for c in 'mbp')

        if has_o:
            v = "round_O"
        elif has_e:
            v = "wide_E"
        elif has_a:
            v = "open_A"
        elif has_m:
            v = "closed_M"
        else:
            v = "neutral"

        visemes.append({
            "time_start": round(t_debut, 2),
            "time_end": round(t_debut + t_par_mot * 0.8, 2),
            "word": mot,
            "viseme": v
        })

    return visemes


def synthetiser_voix_emotionnelle(
    texte: str,
    emotion: str = "neutral",
    pitch_base: float = 160.0,
    duree: Optional[float] = None,
    sr: int = 44100
) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
    """
    Synthétise une réplique vocale avec modulation formantique et intonation émotionnelle.
    Retourne le signal audio normalisé et la liste des visèmes pour le lip-sync Godot.
    """
    emotion = emotion.lower()
    nb_mots = max(len(texte.split()), 1)
    if duree is None:
        facteur_vitesse = 0.35
        if emotion in ["angry", "surprised"]:
            facteur_vitesse = 0.28
        elif emotion in ["sad", "hurt"]:
            facteur_vitesse = 0.45
        duree = max(1.2, nb_mots * facteur_vitesse + 0.4)

    t = np.linspace(0, duree, int(sr * duree), endpoint=False)
    n_samples = len(t)

    # Profil d'intonation de pitch selon l'émotion
    if emotion == "happy":
        pitch_curve = pitch_base * 1.25 + np.sin(2 * np.pi * 3.0 * t) * 20.0 + (t / duree) * 15.0
    elif emotion == "angry":
        pitch_curve = pitch_base * 1.15 - (t / duree) * 35.0
    elif emotion == "sad":
        pitch_curve = pitch_base * 0.85 - (t / duree) * 20.0 + np.sin(2 * np.pi * 1.5 * t) * 6.0
    elif emotion == "surprised":
        pitch_curve = pitch_base * 1.0 + (t / duree)**1.5 * 70.0
    elif emotion == "hurt":
        pitch_curve = pitch_base * 0.9 + np.random.normal(0, 8.0, n_samples)
    else:  # neutral
        pitch_curve = pitch_base + np.sin(2 * np.pi * 1.0 * t) * 5.0

    phase = np.cumsum(2 * np.pi * pitch_curve / sr)
    source_glottique = np.sin(phase) + 0.5 * np.sin(2 * phase) + 0.25 * np.sin(3 * phase) + 0.12 * np.sin(4 * phase)

    syllabes = [c for c in texte.lower() if c in VOWEL_FORMANTS] or ['a', 'e', 'o']
    duree_syl = max(n_samples // len(syllabes), 1)

    signal_filtre = np.zeros(n_samples, dtype=np.float32)

    for i, syl in enumerate(syllabes):
        idx_debut = i * duree_syl
        idx_fin = min(idx_debut + duree_syl, n_samples)
        chunk = source_glottique[idx_debut:idx_fin]
        f1, f2, f3 = VOWEL_FORMANTS.get(syl, (500, 1500, 2500))

        try:
            sos1 = signal.butter(2, [max(50, f1 - 100), min(sr // 2 - 100, f1 + 100)], btype='bandpass', fs=sr, output='sos')
            sos2 = signal.butter(2, [max(50, f2 - 150), min(sr // 2 - 100, f2 + 150)], btype='bandpass', fs=sr, output='sos')
            r1 = signal.sosfilt(sos1, chunk) * 1.2
            r2 = signal.sosfilt(sos2, chunk) * 0.8
            signal_filtre[idx_debut:idx_fin] = (r1 + r2).astype(np.float32)
        except Exception:
            signal_filtre[idx_debut:idx_fin] = chunk.astype(np.float32)

    if emotion == "angry":
        signal_filtre = np.tanh(signal_filtre * 2.5) * 0.9
    elif emotion == "hurt":
        tremolo = 0.6 + 0.4 * np.sin(2 * np.pi * 8.0 * t)
        signal_filtre = signal_filtre * tremolo
        sos_hurt = signal.butter(2, 1800, btype='lowpass', fs=sr, output='sos')
        signal_filtre = signal_filtre.astype(np.float64)
        signal_filtre = signal_filtre[:len(t)]
        signal_filtre = signal.sosfilt(sos_hurt, signal_filtre).astype(np.float32)

    env_globale = np.hanning(n_samples)
    audio_out = signal_filtre * env_globale

    max_val = np.max(np.abs(audio_out))
    if max_val > 0:
        audio_out = (audio_out / max_val) * 0.92

    visemes = extraire_visemes_phonetiques(texte, duree)
    return audio_out.astype(np.float32), visemes


# ==============================================================================
# 3. Synthèse d'Ambiances Procédurales Multicouches (Seamless Loop)
# ==============================================================================

def synthetiser_ambiance(
    ambience_type: str = "dungeon",
    duree: float = 8.0,
    sr: int = 44100
) -> np.ndarray:
    """
    Génère une nappe d'ambiance sonore stéréo 2 canaux en boucle seamless parfaite.
    
    Types d'ambiances :
    - 'dungeon' : Sub-bass drone sombre, résonance de caverne et échos de gouttes d'eau.
    - 'forest' / 'enchanted' : Vent feutré, gazouillis magiques, scintillements de fées.
    - 'storm' / 'volcano' : Grondement de basse fréquence, vent orageux et sifflements.
    - 'space' / 'void' : Drones binauaux cosmiques, textures stellaires étirées.
    - 'campfire' / 'tavern' : Crépitement de feu de bois chaud et ronronnement de braises.
    """
    n_samples = int(sr * duree)
    t = np.linspace(0, duree, n_samples, endpoint=False)
    ambience_type = ambience_type.lower()

    canal_g = np.zeros(n_samples, dtype=np.float32)
    canal_d = np.zeros(n_samples, dtype=np.float32)

    if any(k in ambience_type for k in ["dungeon", "cave", "crypt", "catacomb"]):
        drone = np.sin(2 * np.pi * 45.0 * t) * 0.4 + np.sin(2 * np.pi * 90.0 * t) * 0.2
        bruit = np.random.normal(0, 0.3, n_samples)
        sos_cave = signal.butter(4, 350, btype='lowpass', fs=sr, output='sos')
        bruit_cave = signal.sosfilt(sos_cave, bruit)

        canal_g = drone + bruit_cave * 0.6
        canal_d = drone * 0.95 + np.roll(bruit_cave, int(0.03 * sr)) * 0.6

        nb_gouttes = max(int(duree * 1.5), 3)
        for i in range(nb_gouttes):
            t_drop = int((0.5 + i * (duree - 1.0) / nb_gouttes + np.random.uniform(-0.2, 0.2)) * sr)
            if 0 <= t_drop < n_samples - int(0.3 * sr):
                d_g = int(0.25 * sr)
                t_g = np.linspace(0, 0.25, d_g)
                f_drop = np.geomspace(1200, 300, d_g)
                goutte = np.sin(2 * np.pi * f_drop * t_g) * np.exp(-25.0 * t_g) * 0.3
                pan = np.random.uniform(0.2, 0.8)
                canal_g[t_drop:t_drop + d_g] += (goutte * (1.0 - pan)).astype(np.float32)
                canal_d[t_drop:t_drop + d_g] += (goutte * pan).astype(np.float32)

    elif any(k in ambience_type for k in ["forest", "enchanted", "woods", "nature"]):
        bruit_vent = np.random.normal(0, 0.4, n_samples)
        lfo_vent = 0.5 + 0.5 * np.sin(2 * np.pi * 0.25 * t)
        sos_vent = signal.butter(2, [300, 1800], btype='bandpass', fs=sr, output='sos')
        vent = signal.sosfilt(sos_vent, bruit_vent) * lfo_vent

        chime_g = np.sin(2 * np.pi * 1760.0 * t) * (0.1 + 0.1 * np.sin(2 * np.pi * 3.5 * t))
        chime_d = np.sin(2 * np.pi * 2093.0 * t) * (0.1 + 0.1 * np.sin(2 * np.pi * 4.2 * t))

        canal_g = vent * 0.7 + chime_g * 0.3
        canal_d = vent * 0.7 + chime_d * 0.3

    elif any(k in ambience_type for k in ["storm", "volcano", "lava", "thunder"]):
        rumble = np.random.normal(0, 0.5, n_samples)
        sos_rumble = signal.butter(4, 120, btype='lowpass', fs=sr, output='sos')
        r_low = signal.sosfilt(sos_rumble, rumble) * 1.5

        bruit_air = np.random.normal(0, 0.3, n_samples)
        sos_air = signal.butter(2, [200, 1200], btype='bandpass', fs=sr, output='sos')
        r_air = signal.sosfilt(sos_air, bruit_air)

        canal_g = r_low + r_air * 0.5
        canal_d = r_low * 0.9 + np.roll(r_air, int(0.02 * sr)) * 0.5

    elif any(k in ambience_type for k in ["space", "void", "cosmic", "abyss"]):
        drone_g = np.sin(2 * np.pi * 60.0 * t) * 0.4 + np.sin(2 * np.pi * 120.0 * t) * 0.2
        drone_d = np.sin(2 * np.pi * 64.0 * t) * 0.4 + np.sin(2 * np.pi * 128.0 * t) * 0.2

        shimmer = np.sin(2 * np.pi * 880.0 * t) * (0.05 + 0.05 * np.sin(2 * np.pi * 0.5 * t))
        canal_g = drone_g + shimmer
        canal_d = drone_d + shimmer

    else:  # Campfire / Tavern
        bruit_base = np.random.normal(0, 0.2, n_samples)
        sos_fire = signal.butter(2, [100, 800], btype='bandpass', fs=sr, output='sos')
        fire_hum = signal.sosfilt(sos_fire, bruit_base)

        crackle = np.zeros(n_samples, dtype=np.float32)
        pop_count = int(duree * 12)
        for _ in range(pop_count):
            idx = np.random.randint(0, n_samples - 200)
            crackle[idx:idx + 50] += np.random.uniform(-0.8, 0.8, 50) * np.hanning(50)

        canal_g = fire_hum + crackle * 0.7
        canal_d = fire_hum + np.roll(crackle, 100) * 0.7

    fade_len = int(0.5 * sr)
    fade_in = np.linspace(0.0, 1.0, fade_len)
    fade_out = np.linspace(1.0, 0.0, fade_len)

    canal_g_loop = canal_g.copy()
    canal_d_loop = canal_d.copy()

    canal_g_loop[:fade_len] = canal_g[:fade_len] * fade_in + canal_g[-fade_len:] * fade_out
    canal_g_loop[-fade_len:] = canal_g_loop[:fade_len]

    canal_d_loop[:fade_len] = canal_d[:fade_len] * fade_in + canal_d[-fade_len:] * fade_out
    canal_d_loop[-fade_len:] = canal_d_loop[:fade_len]

    stereo = np.stack([canal_g_loop, canal_d_loop], axis=-1)

    max_val = np.max(np.abs(stereo))
    if max_val > 0:
        stereo = (stereo / max_val) * 0.88

    return stereo.astype(np.float32)


def exporter_ambiance_godot(
    nom_base: str,
    output_dir: str,
    audio_data: np.ndarray,
    sr: int = 44100
) -> Tuple[str, str, str]:
    """Exporte l'ambiance stéréo en .wav, .ogg et produit la ressource AudioBusLayout Godot 4."""
    os.makedirs(output_dir, exist_ok=True)
    chemin_wav = os.path.join(output_dir, f"{nom_base}.wav")
    chemin_ogg = os.path.join(output_dir, f"{nom_base}.ogg")
    chemin_bus = os.path.join(output_dir, f"{nom_base}_bus_layout.tres")

    sf.write(chemin_wav, audio_data, sr, subtype='PCM_16', format='WAV')
    try:
        sf.write(chemin_ogg, audio_data, sr, format='OGG')
    except Exception:
        chemin_ogg = chemin_wav

    code_bus = """[gd_resource type="AudioBusLayout" load_steps=3 format=3]

[sub_resource type="AudioEffectReverb" id="AudioEffectReverb_1"]
resource_name = "CaveReverb"
room_size = 0.6
damping = 0.5
spread = 0.8
wet = 0.35

[sub_resource type="AudioEffectLowPassFilter" id="AudioEffectLowPassFilter_1"]
resource_name = "AtmosphereFilter"
cutoff_hz = 3500.0

[resource]
bus/1/name = &"Ambience"
bus/1/solo = false
bus/1/mute = false
bus/1/bypass_fx = false
bus/1/volume_db = -2.0
bus/1/send = &"Master"
bus/1/effect/0/effect = SubResource("AudioEffectReverb_1")
bus/1/effect/0/enabled = true
bus/1/effect/1/effect = SubResource("AudioEffectLowPassFilter_1")
bus/1/effect/1/enabled = true
"""
    with open(chemin_bus, "w", encoding="utf-8") as f:
        f.write(code_bus)

    return chemin_wav, chemin_ogg, chemin_bus


def exporter_sfx_godot(
    nom_base: str,
    output_dir: str,
    audio_data: np.ndarray,
    sr: int = 44100
) -> Tuple[str, str]:
    """Exporte les fichiers audio .wav et .ogg prêts pour Godot 4 AudioStreamPlayer."""
    from core.music_ai import convertir_ogg

    os.makedirs(output_dir, exist_ok=True)
    chemin_wav = os.path.join(output_dir, f"{nom_base}.wav")
    chemin_ogg = os.path.join(output_dir, f"{nom_base}.ogg")

    sf.write(chemin_wav, audio_data, sr, subtype='PCM_16', format='WAV')
    try:
        # OGG toujours via ffmpeg : le libsndfile fait un stack overflow C (exit 127
        # silencieux) au-delà de quelques secondes — règle §1.10 MEMORY_BANK.
        convertir_ogg(chemin_wav, chemin_ogg)
    except Exception:
        chemin_ogg = chemin_wav

    return chemin_wav, chemin_ogg

