#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Execution of external engines (sd-cli, Blender, ESRGAN…) via a single helper.

Centralizes what used to be scattered across bare `subprocess.run` calls (audit §2.4):
command logging, systematic timeout, typed error carrying the
return code and the tail of stderr instead of a mute `CalledProcessError`.
"""

import logging
import subprocess
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

_QUEUE_ERREUR = 800  # characters of stderr included in an EngineError


class EngineError(RuntimeError):
    """Failure of an external engine (return code ≠ 0 or timeout)."""

    def __init__(self, message: str, commande: List[str], code: int, stderr_fin: str = ""):
        super().__init__(message)
        self.commande = commande
        self.code = code
        self.stderr_fin = stderr_fin


def run_engine(
    commande: List[str],
    *,
    timeout: Optional[float] = None,
    log_path: Optional[str] = None,
    check: bool = True,
    capture: bool = True,
    cwd: Optional[str] = None,
    etiquette: str = "moteur",
) -> subprocess.CompletedProcess:
    """Runs an external engine and centralizes error handling.

    - logs the command to the console (traceability of engine calls);
    - `timeout`: fails the call beyond the deadline — a hung engine no
      longer blocks the CLI forever. Size per call from the MEMORY_BANK
      duration landmarks (never "just tight enough": slow days exist);
    - `capture=True` (default): stdout/stderr captured, returned in the
      CompletedProcess and appended to `log_path` if provided; the tail of stderr
      feeds `EngineError.stderr_fin`;
    - `capture=False`: output left live on the console (long jobs where
      progress matters) — EngineError will then carry only the code;
    - `check=True` (default): raises EngineError if return code ≠ 0.
    """
    affichage = subprocess.list2cmdline(commande)
    logger.info("▶️ [%s] %s", etiquette, affichage)
    if timeout is None:
        logger.warning("⚠️ [%s] execution WITHOUT timeout — reserve for mastered cases", etiquette)

    try:
        resultat = subprocess.run(
            commande,
            capture_output=capture,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired as e:
        stderr_fin = e.stderr or ""
        if isinstance(stderr_fin, bytes):
            stderr_fin = stderr_fin.decode("utf-8", errors="replace")
        raise EngineError(
            f"[{etiquette}] timeout after {timeout:.0f} s: {affichage}",
            commande, -1, stderr_fin[-_QUEUE_ERREUR:],
        ) from e

    if log_path:
        chemin_log = Path(log_path)
        chemin_log.parent.mkdir(parents=True, exist_ok=True)
        with open(chemin_log, "a", encoding="utf-8") as f:
            f.write(
                f"$ {affichage}\n--- stdout ---\n{resultat.stdout or ''}"
                f"\n--- stderr ---\n{resultat.stderr or ''}\n"
            )

    if check and resultat.returncode != 0:
        stderr_fin = (resultat.stderr or "")[-_QUEUE_ERREUR:]
        raise EngineError(
            f"[{etiquette}] return code {resultat.returncode}: {affichage}"
            + (f"\n--- stderr tail ---\n{stderr_fin}" if stderr_fin else ""),
            commande, resultat.returncode, stderr_fin,
        )
    return resultat
