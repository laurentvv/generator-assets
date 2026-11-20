#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests of the IndexTTS2.5 voice pipeline (core.voix_indextts + workflow).

Conventions: pure Python with the external binaries (ffmpeg ebur128/loudnorm,
audiocpp_cli) mocked via monkeypatch — same policy as tests/test_icon_lottie.py
(and validated by separate real-path legs, MEMORY_BANK §1.67 evidence).
"""

import os
import subprocess

import pytest

from core.voix_indextts import (
    REFERENCE_SANE_LUFS,
    REFERENCE_TARGET_LUFS,
    generer_voix_indextts,
    mesurer_lufs,
    normaliser_reference,
)
from workflows.indextts25_tts import Indextts25TtsWorkflow


def _ebur128(lufs: float) -> str:
    """A minimal ffmpeg ebur128 summary fragment."""
    return f"[Parsed_ebur128_0]     I:        {lufs:.1f} LUFS\n    Peak:   -1.0 dBFS\n"


class _FakeEngines:
    """Routes run_engine calls: ebur128 -> scripted loudness, loudnorm/tts -> recorded.

    `lufs_stream` selects which ffmpeg stream carries the ebur128 summary —
    real ffmpeg writes it on stderr (100% of the I: lines measured), stdout
    is kept as a supported variant.
    """

    def __init__(self, ref_lufs: float, lufs_stream: str = "stderr"):
        self.ref_lufs = ref_lufs
        self.lufs_stream = lufs_stream
        self.calls = []

    def __call__(self, commande, **kwargs):
        self.calls.append((list(commande), dict(kwargs)))
        joined = " ".join(commande)
        if "ebur128" in joined:
            if self.lufs_stream == "stderr":
                return subprocess.CompletedProcess(commande, 0, stdout="", stderr=_ebur128(self.ref_lufs))
            return subprocess.CompletedProcess(commande, 0, stdout=_ebur128(self.ref_lufs), stderr="")
        if "loudnorm" in joined:
            sortie = commande[-1]
            os.makedirs(os.path.dirname(sortie) or ".", exist_ok=True)
            with open(sortie, "wb") as handle:
                handle.write(b"RIFF")
            return subprocess.CompletedProcess(commande, 0, stdout="", stderr="")
        # audiocpp generation: create the requested output file
        sortie = commande[commande.index("--out") + 1]
        os.makedirs(os.path.dirname(sortie) or ".", exist_ok=True)
        with open(sortie, "wb") as handle:
            handle.write(b"RIFF....WAVE")
        return subprocess.CompletedProcess(commande, 0, stdout="", stderr="")


def _touch(path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(b"x")
    return str(path)


def _run_generation(fake, tmp_path, ref, **kwargs):
    """Runs generer_voix_indextts with explicit (existing) binary/model paths."""
    return generer_voix_indextts(
        "hello factory",
        str(tmp_path / "out.wav"),
        ref,
        audiocpp=_touch(tmp_path / "fake_cli.exe"),
        modele=_touch(tmp_path / "model.gguf"),
        **kwargs,
    )


def test_mesurer_lufs_parses_integrated_value(monkeypatch, tmp_path):
    """Production reality: ffmpeg writes the ebur128 summary on STDERR."""
    wav = _touch(tmp_path / "ref.wav")
    fake = _FakeEngines(-39.0, lufs_stream="stderr")
    monkeypatch.setattr("core.voix_indextts.run_engine", fake)
    assert mesurer_lufs(wav) == -39.0


def test_mesurer_lufs_also_reads_stdout(monkeypatch, tmp_path):
    wav = _touch(tmp_path / "ref.wav")
    fake = _FakeEngines(-39.0, lufs_stream="stdout")
    monkeypatch.setattr("core.voix_indextts.run_engine", fake)
    assert mesurer_lufs(wav) == -39.0


def test_normaliser_reference_passes_sane_reference_through(monkeypatch, tmp_path):
    """A reference already >= -23 LUFS is returned untouched (no loudnorm call)."""
    wav = _touch(tmp_path / "ref_ok.wav")
    fake = _FakeEngines(-14.0)
    monkeypatch.setattr("core.voix_indextts.run_engine", fake)
    assert normaliser_reference(wav) == wav
    assert not any("loudnorm" in " ".join(c[0]) for c in fake.calls)


def test_normaliser_reference_normalizes_quiet_reference(monkeypatch, tmp_path):
    """A -39 LUFS reference (the measured §1.67 pitfall) is loudnorm'd to -16."""
    wav = _touch(tmp_path / "ref_quiet.wav")
    fake = _FakeEngines(-39.0)
    monkeypatch.setattr("core.voix_indextts.run_engine", fake)
    resultat = normaliser_reference(wav)
    assert resultat == str(tmp_path / "ref_quiet_ttsnorm.wav")
    loudnorm_calls = [c[0] for c in fake.calls if "loudnorm" in " ".join(c[0])]
    assert loudnorm_calls and f"I={REFERENCE_TARGET_LUFS}" in " ".join(loudnorm_calls[0])


def test_generer_voix_rejects_missing_reference(tmp_path):
    with pytest.raises(FileNotFoundError):
        generer_voix_indextts(
            "hello", str(tmp_path / "out.wav"), str(tmp_path / "absent.wav"),
            audiocpp=_touch(tmp_path / "fake_cli.exe"),
            modele=_touch(tmp_path / "model.gguf"),
        )


def test_generer_voix_rejects_empty_text(tmp_path):
    with pytest.raises(ValueError):
        generer_voix_indextts(
            "  ", str(tmp_path / "out.wav"), str(tmp_path / "ref.wav"),
            audiocpp=_touch(tmp_path / "fake_cli.exe"),
            modele=_touch(tmp_path / "model.gguf"),
        )


def test_generer_voix_happy_path_wires_reference_and_seed(monkeypatch, tmp_path):
    """The engine call carries the (normalized) reference, seed and language."""
    ref = _touch(tmp_path / "ref.wav")
    fake = _FakeEngines(-39.0)  # quiet ref -> normalization kicks in
    monkeypatch.setattr("core.voix_indextts.run_engine", fake)
    resultat = _run_generation(fake, tmp_path, ref, langue="en", graine=42)
    appel = [c for c in fake.calls if "--out" in c[0]][-1][0]
    assert appel[appel.index("--voice-ref") + 1] == str(tmp_path / "ref_ttsnorm.wav")
    assert appel[appel.index("--seed") + 1] == "42"
    assert appel[appel.index("--language") + 1] == "en"
    assert appel[appel.index("--family") + 1] == "index_tts2"
    assert resultat["reference_normalisee"] is True
    assert resultat["moteur"] == "indextts25_q8_0"


def test_generer_voix_raw_ref_skips_normalization(monkeypatch, tmp_path):
    ref = _touch(tmp_path / "ref.wav")
    fake = _FakeEngines(-39.0)
    monkeypatch.setattr("core.voix_indextts.run_engine", fake)
    _run_generation(fake, tmp_path, ref, normaliser_ref=False)
    appel = [c for c in fake.calls if "--out" in c[0]][-1][0]
    assert appel[appel.index("--voice-ref") + 1] == ref
    assert not any("loudnorm" in " ".join(c[0]) for c in fake.calls)


def test_workflow_requires_reference():
    workflow = Indextts25TtsWorkflow()
    with pytest.raises(ValueError):
        workflow.run({"prompt": "hello"})


def test_workflow_flags_are_declared():
    """The audit §2.2 keystone: the 4 flags exist with validated defaults.

    Namespace `--indextts-*` (the global parser is flat: --tts-langue is
    already taken by lfm3_tts — the conflict test caught the first draft).
    """
    flags = {flag for p in Indextts25TtsWorkflow.PARAMETRES for flag in p["flags"]}
    assert flags == {
        "--indextts-langue", "--indextts-reference", "--indextts-seed", "--indextts-raw-ref",
    }
    langue = next(p for p in Indextts25TtsWorkflow.PARAMETRES if "--indextts-langue" in p["flags"])
    assert langue["default"] == "en"  # the validated narration path


def test_reference_gate_thresholds_are_measured_values():
    """§1.67 constants sanity: sane band and target come from the EBU R128 measurements."""
    assert REFERENCE_SANE_LUFS == -23.0  # broadcast floor
    assert REFERENCE_TARGET_LUFS == -16.0
