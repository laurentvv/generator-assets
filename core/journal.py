#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Structured logging of the repo (audit §2.8).

Repo convention:
- messages for the USER (interactive menus, lists, recaps,
  progress emojis): print() on stdout — unchanged;
- DIAGNOSTIC messages (technical steps, warnings, contextual
  errors, measurements): logging via ``logger = logging.getLogger(__name__)``
  — timestamped, typed, filterable by level, duplicable to a file;
- ``configurer_journal()`` is called by main.py (``--verbose`` → DEBUG);
  standalone scripts that want the same entries call it too.
"""

import logging
import sys
from pathlib import Path
from typing import Optional, Union

FORMAT_ENTREE = "%(asctime)s %(levelname)-7s %(name)s : %(message)s"


def configurer_journal(
    niveau: str = "INFO",
    fichier: Optional[Union[str, Path]] = None,
) -> None:
    """Configure the repo's logging (stderr console + optional file).

    Idempotent: calling again REPLACES the handlers instead of stacking (useful in
    tests and in scripts that reconfigure).

    - ``niveau``: "DEBUG", "INFO" (default), "WARNING"…;
    - ``fichier``: if provided, duplicates the timestamped entries (full date)
      into that file — background runs and batches (e.g. ``output/batch_<date>.log``).
    """
    racine = logging.getLogger()
    racine.setLevel(getattr(logging, str(niveau).upper(), logging.INFO))
    for handler in list(racine.handlers):
        racine.removeHandler(handler)

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(logging.Formatter(FORMAT_ENTREE, datefmt="%H:%M:%S"))
    racine.addHandler(console)

    if fichier:
        chemin = Path(fichier)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        vers_fichier = logging.FileHandler(chemin, encoding="utf-8")
        vers_fichier.setFormatter(logging.Formatter(FORMAT_ENTREE))
        racine.addHandler(vers_fichier)
