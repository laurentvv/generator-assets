#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests of the sous_titres pipeline (core.sous_titres + workflow).

Conventions: pure Python with the external binaries (audiocpp_cli, ffmpeg)
mocked via monkeypatch — same policy as tests/test_voix_indextts.py (the real
paths were validated on the engine, MEMORY_BANK §1.68 evidence).
"""

import json
import os
import subprocess
import wave

import pytest

from core.sous_titres import (
    TAUX_SILERO,
    aligner_mots,
    duree_audio,
    ecrire_srt_mots,
    transcrire_aligner,
)
from workflows.base import WorkflowRegistry
from workflows.sous_titres import SousTitresWorkflow


def _ecrire_wav(chemin: str, taux: int = 16000, secondes: float = 1.0) -> str:
    """A minimal silent PCM WAV (stdlib wave)."""
    os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)
    with wave.open(chemin, "wb") as lecteur:
        lecteur.setnchannels(1)
        lecteur.setsampwidth(2)
        lecteur.setframerate(taux)
        lecteur.writeframes(b"\x00\x00" * int(taux * secondes))
    return chemin


class _FakeAlignEngine:
    """Routes run_engine calls: load gate -> ok, align/asr -> words JSON file."""

    def __init__(self, mots):
        self.mots = mots
        self.calls = []

    def __call__(self, commande, **kwargs):
        self.calls.append((list(commande), dict(kwargs)))
        joined = " ".join(str(c) for c in commande)
        if "check_charge_systeme" in joined:
            return subprocess.CompletedProcess(commande, 0, stdout="", stderr="")
        if "ffmpeg" in joined:
            # resample leg: write the requested output (last argument)
            sortie = commande[-1]
            os.makedirs(os.path.dirname(sortie) or ".", exist_ok=True)
            with open(sortie, "wb") as handle:
                handle.write(b"RIFF")
            return subprocess.CompletedProcess(commande, 0, stdout="", stderr="")
        sortie = commande[commande.index("--words-out") + 1]
        os.makedirs(os.path.dirname(sortie) or ".", exist_ok=True)
        with open(sortie, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(self.mots, handle)
        return subprocess.CompletedProcess(commande, 0, stdout="transcript mot par mot", stderr="")

    def appel_unique_avec(self, fragment: str):
        """The single engine call whose command contains `fragment`."""
        correspondances = [c for c in self.calls if fragment in " ".join(str(x) for x in c[0])
                           and "check_charge_systeme" not in " ".join(str(x) for x in c[0])]
        assert len(correspondances) == 1, f"expected one '{fragment}' call, got {len(correspondances)}"
        return correspondances[0][0]


# ============================================================================
# SRT builder (pure)
# ============================================================================

MOTS_TEST = [
    {"start_sample": 1600, "end_sample": 4380, "word": "Le", "confidence": 0},
    {"start_sample": 4380, "end_sample": 9000, "word": "vide", "confidence": 0},
    {"start_sample": 9000, "end_sample": 8990, "word": "s'éveille", "confidence": 0},  # inverted -> nudged
]


def test_srt_mots_horodatage_et_numerotation(tmp_path):
    cible = tmp_path / "sortie.srt"
    ecrire_srt_mots(MOTS_TEST, TAUX_SILERO, str(cible))
    contenu = cible.read_text(encoding="utf-8")
    blocs = contenu.strip().split("\n\n")
    assert len(blocs) == 3
    assert blocs[0] == "1\n00:00:00,100 --> 00:00:00,274\nLe"
    assert "00:00:00,274 --> 00:00:00,562\nvide" in blocs[1]
    # inverted end nudged to start + 1 ms
    assert "00:00:00,562 --> 00:00:00,563\ns'éveille" in blocs[2]
    assert contenu.endswith("\n")


def test_duree_audio(tmp_path):
    wav = _ecrire_wav(str(tmp_path / "a.wav"), taux=16000, secondes=2.0)
    assert abs(duree_audio(wav) - 2.0) < 1e-6
    assert duree_audio(str(tmp_path / "absent.wav")) is None


# ============================================================================
# Engine paths (mocked binaries)
# ============================================================================

def test_aligner_mots_commande_et_json(tmp_path, monkeypatch):
    mots = [{"start_sample": 160, "end_sample": 500, "word": "Fort", "confidence": 0}]
    fake = _FakeAlignEngine(mots)
    monkeypatch.setattr("core.sous_titres.run_engine", fake)
    monkeypatch.setattr("core.sous_titres.resoudre_audiocpp", lambda: "audiocpp_cli.exe")
    gguf = tmp_path / "aligner.gguf"
    gguf.write_bytes(b"x")
    monkeypatch.setattr("core.sous_titres.MODELE_FORCED_ALIGNER", str(gguf))
    wav = _ecrire_wav(str(tmp_path / "clip.wav"), taux=24000)
    chemin_json = str(tmp_path / "mots.json")

    lus, taux = aligner_mots(wav, "Fort", chemin_json, langue="fr", quant="q8_0")

    assert taux == 24000  # input file's sample domain
    assert lus == mots
    cmd = fake.appel_unique_avec("qwen3_forced_aligner")
    assert "--task" in cmd and cmd[cmd.index("--task") + 1] == "align"
    assert cmd[cmd.index("--family") + 1] == "qwen3_forced_aligner"
    assert cmd[cmd.index("--model") + 1] == str(gguf)
    assert cmd[cmd.index("--language") + 1] == "fr"
    assert cmd[cmd.index("--text") + 1] == "Fort"
    assert cmd[cmd.index("--words-out") + 1] == chemin_json


def test_aligner_mots_exige_transcript(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="EXACT transcript"):
        aligner_mots("x.wav", "  ", str(tmp_path / "m.json"))


def test_transcrire_aligner_options_session(tmp_path, monkeypatch):
    mots = [{"start_sample": 0, "end_sample": 100, "word": "Mot", "confidence": 0}]
    fake = _FakeAlignEngine(mots)
    monkeypatch.setattr("core.sous_titres.run_engine", fake)
    monkeypatch.setattr("core.sous_titres.resoudre_audiocpp", lambda: "audiocpp_cli.exe")
    monkeypatch.setattr("core.sous_titres.resoudre_ffmpeg", lambda: "ffmpeg.exe")
    monkeypatch.setattr("core.sous_titres.MODELE_QWEN3_ASR", "asr.gguf")
    gguf = tmp_path / "aligner.gguf"
    gguf.write_bytes(b"x")
    monkeypatch.setattr("core.sous_titres.MODELE_FORCED_ALIGNER", str(gguf))
    vad = tmp_path / "vad"
    vad.mkdir()
    monkeypatch.setattr("core.sous_titres.DOSSIER_VAD_SILERO", str(tmp_path / "jamais_utilise"))
    wav = _ecrire_wav(str(tmp_path / "long.wav"))
    chemin_json = str(tmp_path / "long_words.json")

    # explicit vad_dir wins over the module default (Kilo review warning fix)
    lus, texte, taux = transcrire_aligner(wav, chemin_json, langue="fr", vad_dir=str(vad))

    assert taux == TAUX_SILERO
    assert lus == mots
    assert texte == "transcript mot par mot"
    cmd = fake.appel_unique_avec("qwen3_asr")
    assert cmd[cmd.index("--task") + 1] == "asr"
    assert "--session-option" in cmd
    options = [cmd[i + 1] for i, f in enumerate(cmd) if f == "--session-option"]
    assert any(o.startswith("qwen3_asr.forced_aligner_path=") and o.endswith("aligner.gguf") for o in options)
    assert any(o == f"qwen3_asr.vad_model_path={vad}" for o in options)
    # 16 kHz mono resample happened before the engine call
    resample = [c for c, _ in fake.calls if "ffmpeg.exe" in " ".join(str(x) for x in c)]
    assert resample and "-ar" in resample[0] and "16000" in resample[0]
    assert os.path.exists(str(tmp_path / "long_words_transcript.txt"))


def test_transcrire_aligner_exige_vad(tmp_path, monkeypatch):
    monkeypatch.setattr("core.sous_titres.DOSSIER_VAD_SILERO", str(tmp_path / "inexistant"))
    with pytest.raises(FileNotFoundError, match="VAD"):
        transcrire_aligner("x.wav", str(tmp_path / "m.json"))


# ============================================================================
# Workflow registration + run (gate + engine mocked)
# ============================================================================

def test_workflow_enregistre():
    assert "sous_titres" in WorkflowRegistry.list_all()
    assert SousTitresWorkflow.name == "sous_titres"


def _lancer(tmp_path, monkeypatch, mots, **params):
    fake = _FakeAlignEngine(mots)
    monkeypatch.setattr("workflows.sous_titres.run_engine", fake)
    monkeypatch.setattr("core.sous_titres.run_engine", fake)
    monkeypatch.setattr("core.sous_titres.resoudre_audiocpp", lambda: "audiocpp_cli.exe")
    monkeypatch.setattr("core.sous_titres.resoudre_ffmpeg", lambda: "ffmpeg.exe")
    gguf = tmp_path / "aligner.gguf"
    gguf.write_bytes(b"x")
    monkeypatch.setattr("core.sous_titres.MODELE_FORCED_ALIGNER", str(gguf))
    vad = tmp_path / "vad"
    vad.mkdir()
    monkeypatch.setattr("core.sous_titres.DOSSIER_VAD_SILERO", str(vad))
    wav = _ecrire_wav(str(tmp_path / "entree.wav"))
    params.update({"audio": wav, "output_dir": str(tmp_path)})
    return SousTitresWorkflow({}).run(params), fake


def test_workflow_align_bout_en_bout(tmp_path, monkeypatch):
    mots = [{"start_sample": 0, "end_sample": 1000, "word": "Bonjour", "confidence": 0}]
    resultat, fake = _lancer(tmp_path, monkeypatch, mots, prompt="Bonjour", output="test")

    assert os.path.exists(resultat["srt"]) and resultat["srt"].endswith(".srt")
    assert resultat["words"] == 1 and resultat["mode"] == "align"
    assert resultat["sample_rate"] == 16000
    cmd = fake.appel_unique_avec("qwen3_forced_aligner")
    assert cmd[cmd.index("--text") + 1] == "Bonjour"


def test_workflow_asr_bout_en_bout(tmp_path, monkeypatch):
    mots = [{"start_sample": 0, "end_sample": 500, "word": "Narrateur", "confidence": 0}]
    resultat, fake = _lancer(tmp_path, monkeypatch, mots, st_mode="asr",
                             st_vad=str(tmp_path / "vad"), output="test")

    assert resultat["mode"] == "asr" and resultat["words"] == 1
    assert os.path.exists(resultat["srt"])
    cmd = fake.appel_unique_avec("--task asr")
    assert "--text" not in cmd
    options = [cmd[i + 1] for i, f in enumerate(cmd) if f == "--session-option"]
    assert any(o == f"qwen3_asr.vad_model_path={tmp_path / 'vad'}" for o in options)


def test_workflow_exige_audio_puis_transcript():
    wf = SousTitresWorkflow({})
    with pytest.raises(SystemExit, match="--audio"):
        wf.run({})
    with pytest.raises(SystemExit, match="EXACT transcript"):
        wf.run({"audio": "x.wav"})


def test_workflow_asr_sans_transcript_passe(tmp_path, monkeypatch):
    # asr mode does not need the prompt — regression guard on the mode gate
    mots = [{"start_sample": 0, "end_sample": 500, "word": "Mot", "confidence": 0}]
    resultat, _ = _lancer(tmp_path, monkeypatch, mots, st_mode="asr")
    assert resultat["mode"] == "asr"
