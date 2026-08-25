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
