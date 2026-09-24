#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exécution des moteurs externes (sd-cli, Blender, ESRGAN…) via un helper unique.

Centralise ce qui était dispersé dans des `subprocess.run` nus (audit §2.4) :
journalisation de la commande, timeout systématique, erreur typée portant le
code retour et la fin du stderr au lieu d'une `CalledProcessError` muette.
"""

import subprocess
from pathlib import Path
from typing import List, Optional

_QUEUE_ERREUR = 800  # caractères de stderr inclus dans un EngineError


class EngineError(RuntimeError):
    """Échec d'un moteur externe (code retour ≠ 0 ou timeout)."""

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
    """Exécute un moteur externe et centralise la gestion d'erreur.

    - journalise la commande sur la console (traçabilité des appels moteurs) ;
    - `timeout` : fait échouer l'appel au-delà du délai — un moteur qui pend ne
      bloque plus le CLI à l'infini. À dimensionner par appel à partir des
      repères de durées MEMORY_BANK (jamais « au plus juste » : les journées
      lentes existent) ;
    - `capture=True` (défaut) : stdout/stderr capturés, retournés dans le
      CompletedProcess et ajoutés à `log_path` si fourni ; la fin du stderr
      alimente `EngineError.stderr_fin` ;
    - `capture=False` : sortie laissée en direct sur la console (jobs longs où
      la progression compte) — EngineError portera alors seulement le code ;
    - `check=True` (défaut) : lève EngineError si le code retour ≠ 0.
    """
    affichage = subprocess.list2cmdline(commande)
    print(f"▶️ [{etiquette}] {affichage}")
    if timeout is None:
        print(f"⚠️ [{etiquette}] exécution SANS timeout — à réserver aux cas maîtrisés")

    try:
        resultat = subprocess.run(
            commande,
            capture_output=capture,
            text=True,
            timeout=timeout,
            check=False,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired as e:
        stderr_fin = e.stderr or ""
        if isinstance(stderr_fin, bytes):
            stderr_fin = stderr_fin.decode("utf-8", errors="replace")
        raise EngineError(
            f"[{etiquette}] timeout après {timeout:.0f} s : {affichage}",
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
            f"[{etiquette}] code retour {resultat.returncode} : {affichage}"
            + (f"\n--- fin de stderr ---\n{stderr_fin}" if stderr_fin else ""),
            commande, resultat.returncode, stderr_fin,
        )
    return resultat
