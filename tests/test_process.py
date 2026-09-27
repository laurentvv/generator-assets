#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests of core/process.py: external engine execution helper.

Uses real `python -c` subprocesses (no mock, no engine required).
"""

import sys

import pytest

from core.process import EngineError, run_engine


def test_succes_retourne_le_processus():
    res = run_engine([sys.executable, "-c", "print('hello from the engine')"], timeout=60, etiquette="test")
    assert res.returncode == 0
    assert "hello from the engine" in res.stdout


def test_code_nonzero_leve_engineerror_avec_stderr():
    with pytest.raises(EngineError) as excinfo:
        run_engine(
            [sys.executable, "-c", "import sys; print('engine failure', file=sys.stderr); raise SystemExit(3)"],
            timeout=60,
            etiquette="test",
        )
    assert excinfo.value.code == 3
    assert "engine failure" in excinfo.value.stderr_fin
    assert excinfo.value.commande[-1].startswith("import sys")


def test_check_false_ne_leve_pas():
    res = run_engine([sys.executable, "-c", "raise SystemExit(2)"], check=False, timeout=60)
    assert res.returncode == 2


def test_timeout_leve_engineerror():
    with pytest.raises(EngineError) as excinfo:
        run_engine([sys.executable, "-c", "import time; time.sleep(30)"], timeout=2, etiquette="test")
    assert excinfo.value.code == -1
    assert "timeout" in str(excinfo.value)


def test_log_path_ecrit_stdout_et_stderr(tmp_path):
    log = tmp_path / "logs" / "engine.log"
    run_engine(
        [sys.executable, "-c", "print('visible line'); import sys; print('noise', file=sys.stderr)"],
        log_path=str(log),
        timeout=60,
    )
    contenu = log.read_text(encoding="utf-8")
    assert "visible line" in contenu
    assert "noise" in contenu
    assert "--- stderr ---" in contenu
