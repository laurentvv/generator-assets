#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Système de Workflows Modulaires pour Generator-Assets.
Inspiré par les architectures de graphes de traitement (ComfyUI) mais optimisé
pour une exécution CLI ultra-légère, sans interface et avec gestion mémoire stricte.
"""

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Type


class BaseWorkflow(ABC):
    """Classe de base pour tous les workflows automatisés."""

    name: str = "base"
    description: str = "Workflow de base"

    # Déclaration des paramètres CLI spécifiques au workflow (audit §2.2 keystone).
    # Chaque entrée = kwargs d'add_argument, avec la clé spéciale "flags" portant
    # les options (ex. dict(flags=("--res",), type=int, default=512, help="…")).
    # La surface CLI reste agrégée (tous les flags de tous les workflows toujours
    # acceptés — contrat consommateurs préservé) : cli/parser.py agrège ces
    # déclarations via WorkflowRegistry. La table plate du parseur est migrée
    # famille par famille ; un flag ne doit exister QUE dans une seule déclaration
    # ou dans la table plate (test anti-doublon).
    PARAMETRES: List[Dict[str, Any]] = []

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}

    def log(self, message: str, emoji: str = "⚡"):
        print(f"{emoji} [{self.name.upper()}] {message}")

    @abstractmethod
    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Exécute les étapes du workflow."""
        pass


class WorkflowRegistry:
    """Registre centralisé des workflows disponibles."""
    
    _workflows: Dict[str, Type[BaseWorkflow]] = {}

    @classmethod
    def register(cls, workflow_cls: Type[BaseWorkflow]):
        cls._workflows[workflow_cls.name.lower()] = workflow_cls
        return workflow_cls

    @classmethod
    def get(cls, name: str) -> Type[BaseWorkflow]:
        nom = name.lower()
        if nom not in cls._workflows:
            dispos = ", ".join(cls._workflows.keys())
            raise ValueError(f"Workflow '{name}' inconnu. Workflows disponibles : {dispos}")
        return cls._workflows[nom]

    @classmethod
    def list_all(cls) -> Dict[str, str]:
        return {name: wf.description for name, wf in cls._workflows.items()}

    @classmethod
    def parametres_declares(cls) -> List[Dict[str, Any]]:
        """Agrège les PARAMETRES déclarés par tous les workflows enregistrés.

        Utilisé par cli/parser.py pour générer le groupe d'options « par
        workflow » ; l'ordre suit celui du registre (menu interactif).
        Une classe fille hérite de la liste PARAMETRES de sa mère (même objet) —
        ex. character3d ⊂ character_makeup : la déclaration ne doit être émise
        qu'une fois, sinon argparse refuse le flag en doublon.
        """
        declarations: List[Dict[str, Any]] = []
        vus: set = set()
        for wf_cls in cls._workflows.values():
            for declaration in getattr(wf_cls, "PARAMETRES", []):
                if id(declaration) not in vus:
                    vus.add(id(declaration))
                    declarations.append(declaration)
        return declarations
