#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Musical score compiler for VoxCPM2 VocalRender-Pro (audio.cpp).

Upstream syntax (docs/models/vocalrender.md @ audio.cpp v0.9.4):
- Global tempo prefix: `<BPM_120>` (optional, integer BPM)
- Per-unit note encoding: `<syllable><P_60><NOTE_4>` where:
  - `P_n` is integer MIDI pitch (C4 = 60, range 21..108)
  - `NOTE_d` is integer duration code (1 whole, 2 half, 4 quarter, 8 eighth, 16 sixteenth)

This module compiles plain FR/EN lyrics (or explicit `syl:64:4` tokens and
already-formatted `<BPM_...>` scores) into clean `VocalRender` token streams.

⚠️ Wave 1 ASR verdict (2026-11-14, Qwen3-ASR 0.6B): `VocalRender-Pro` (`voxcpm2`)
is **Mandarin (`zh`) only** — FR inputs hum without intelligible lyrics and EN
inputs hallucinate Chinese phonemes. Keep `chanson` powered by `ACE-Step 1.5`
for French and English singing; reserve `VocalRender-Pro` strictly for `zh` prose/score experiments.
"""

from __future__ import annotations

import re
from typing import Iterable, Sequence

# Predefined modal / pentatonic pitch progressions (MIDI around C4=60)
SCALES_MIDI: dict[str, tuple[int, ...]] = {
    "c_major": (60, 62, 64, 65, 67, 69, 71, 72),
    "a_minor": (57, 59, 60, 62, 64, 65, 67, 69),
    "d_dorian": (58, 60, 62, 63, 65, 67, 69, 70),
    "e_minor": (64, 66, 67, 69, 71, 72, 74, 76),
    "g_major": (55, 57, 59, 60, 62, 64, 66, 67),
    "pentatonic_minor": (57, 60, 62, 64, 67, 69, 72),
}

_NOTE_NAME_RE = re.compile(r"^([A-Ga-g])([#b]?)(-?\d)$")
_NOTE_OFFSETS: dict[str, int] = {
    "C": 0,
    "D": 2,
    "E": 4,
    "F": 5,
    "G": 7,
    "A": 9,
    "B": 11,
}
_VALID_NOTE_CODES = (1, 2, 4, 8, 16)
_SCORE_PASSTHROUGH_RE = re.compile(r"<P_\d+>|<NOTE_\d+>")
_EXPLICIT_TOKEN_RE = re.compile(r"^([^:]+):([A-Ga-g][#b]?-?\d|\d{2,3})(?::(\d+))?$")


def note_vers_midi(note: str | int) -> int:
    """Converts a MIDI integer or scientific pitch name (`C4`, `F#3`, `Bb4`) to MIDI."""
    if isinstance(note, bool):
        raise ValueError(f"Invalid musical note specification: {note!r}")
    if isinstance(note, int):
        return max(21, min(108, note))
    brut = str(note).strip()
    if brut.isdigit() or (brut.startswith("-") and brut[1:].isdigit()):
        return max(21, min(108, int(brut)))
    m = _NOTE_NAME_RE.match(brut)
    if not m:
        raise ValueError(f"Invalid musical note specification: {note!r}")
    letter, accidental, octave_str = m.groups()
    midi = (int(octave_str) + 1) * 12 + _NOTE_OFFSETS[letter.upper()]
    if accidental == "#":
        midi += 1
    elif accidental == "b":
        midi -= 1
    if not (21 <= midi <= 108):
        raise ValueError(f"MIDI pitch out of VocalRender range [21..108]: {midi}")
    return midi


def decouper_syllabes(mot: str) -> list[str]:
    """Splits a FR/EN word into simple pronounceable orthographic syllables for singing."""
    clean = re.sub(r"[^\w'’-]", "", mot.strip(), flags=re.UNICODE)
    if not clean:
        return []
    # Respect explicit hyphenation first
    if "-" in clean and not clean.startswith("-"):
        morceaux = []
        for sub in clean.split("-"):
            if sub:
                morceaux.extend(decouper_syllabes(sub))
        return morceaux

    # Heuristic vowel-nucleus segmentation suitable for FR/EN singing cadence
    voyelles = "aeiouyàâäéèêëîïôöùûüÿœæAEIOUYÀÂÄÉÈÊËÎÏÔÖÙÛÜŸŒÆ"
    clusters = re.findall(rf"[^{voyelles}]*[{voyelles}]+(?:[^{voyelles}]+(?![{voyelles}]))?", clean)
    if not clusters:
        return [clean]
    # Merge trailing consonant-only fragment onto the last syllable if any
    joint = "".join(clusters)
    if len(joint) < len(clean):
        clusters[-1] += clean[len(joint):]
    return [c for c in clusters if c]


def normaliser_duree_note(code: int) -> int:
    """Clamps/snaps a duration denominator to the nearest VocalRender code (1, 2, 4, 8, 16)."""
    return min(_VALID_NOTE_CODES, key=lambda c: abs(c - int(code)))


def compiler_partition_chant(
    paroles: str,
    *,
    bpm: int = 96,
    gamme: str | Sequence[int] = "a_minor",
    duree_defaut: int = 4,
    inscrire_bpm: bool = True,
) -> str:
    """Compiles plain lyrics or explicit `syllable:pitch:dur` tokens into VocalRender syntax.

    Already-formatted VocalRender strings containing `<P_...>` / `<NOTE_...>`
    tags pass through cleanly (adding `<BPM_n>` if requested and absent).
    """
    texte = (paroles or "").strip()
    if not texte:
        raise ValueError("Cannot compile an empty vocal score.")

    bpm_val = max(40, min(220, int(bpm)))
    if _SCORE_PASSTHROUGH_RE.search(texte):
        if inscrire_bpm and "<BPM_" not in texte:
            return f"<BPM_{bpm_val}> {texte}"
        return texte

    if isinstance(gamme, str):
        if gamme not in SCALES_MIDI:
            raise ValueError(f"Unknown scale '{gamme}'. Available: {', '.join(SCALES_MIDI)}")
        notes_pool: Sequence[int] = SCALES_MIDI[gamme]
    else:
        notes_pool = [note_vers_midi(n) for n in gamme]
        if not notes_pool:
            raise ValueError("Scale pitch sequence cannot be empty.")

    dur_def = normaliser_duree_note(duree_defaut)
    unites: list[str] = []
    idx = 0

    for ligne in texte.splitlines():
        mots: Iterable[str] = ligne.strip().split()
        for brut in mots:
            exp = _EXPLICIT_TOKEN_RE.match(brut)
            if exp:
                syl, raw_pitch, raw_dur = exp.groups()
                midi = note_vers_midi(raw_pitch)
                dur = normaliser_duree_note(int(raw_dur)) if raw_dur else dur_def
                unites.append(f"{syl}<P_{midi}><NOTE_{dur}>")
                idx += 1
                continue

            syllabes = decouper_syllabes(brut)
            if not syllabes:
                continue
            for pos, syl in enumerate(syllabes):
                # Slight arch cadence: step gently through scale, hold phrase-final syllable
                midi = notes_pool[idx % len(notes_pool)]
                dur = max(1, dur_def // 2) if (pos == len(syllabes) - 1 and brut.endswith((".", "!", "?", ","))) else dur_def
                dur = normaliser_duree_note(dur)
                unites.append(f"{syl}<P_{midi}><NOTE_{dur}>")
                idx += 1

    if not unites:
        raise ValueError("No vocal syllables could be extracted from lyrics.")

    prefixe = f"<BPM_{bpm_val}> " if inscrire_bpm else ""
    return prefixe + " ".join(unites)
