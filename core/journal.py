#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Journalisation structurée du dépôt (audit §2.8).

Convention du dépôt :
- messages destinés à l'UTILISATEUR (menus interactifs, listes, récapitulatifs,
  emojis de progression) : print() sur stdout — inchangés ;
- messages de DIAGNOSTIC (étapes techniques, avertissements, erreurs
  contextuelles, mesures) : logging via ``logger = logging.getLogger(__name__)``
  — horodatés, typés, filtrables par niveau, dupliquables vers un fichier ;
- ``configurer_journal()`` est appelé par main.py (``--verbose`` → DEBUG) ;
  les scripts autonomes qui veulent les mêmes entrées l'appellent aussi.
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
    """Configure la journalisation du dépôt (console stderr + fichier optionnel).

    Idempotent : ré-appeler REMPLACE les handlers au lieu d'empiler (utile en
    tests et dans les scripts qui reconfigurent).

    - ``niveau`` : "DEBUG", "INFO" (défaut), "WARNING"… ;
    - ``fichier`` : si fourni, duplique les entrées horodatées (date complète)
      dans ce fichier — runs de fond et batchs (ex. ``output/batch_<date>.log``).
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
