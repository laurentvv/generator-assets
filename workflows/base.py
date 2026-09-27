#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modular Workflow System for Generator-Assets.
Inspired by processing-graph architectures (ComfyUI) but optimized
for ultra-lightweight CLI execution, with no UI and strict memory management.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Type


class BaseWorkflow(ABC):
    """Base class for all automated workflows."""

    name: str = "base"
    description: str = "Base workflow"

    # Declaration of the workflow-specific CLI parameters (audit §2.2 keystone).
    # Each entry = add_argument kwargs, with the special key "flags" carrying
    # the options (e.g. dict(flags=("--res",), type=int, default=512, help="…")).
    # The CLI surface stays aggregated (all flags of all workflows always
    # accepted — consumer contract preserved): cli/parser.py aggregates these
    # declarations via WorkflowRegistry. Migration DONE: the parser's flat
    # table only keeps the cross-family options (--factor, --frames…).
    # A flag must exist ONLY in a single declaration or in the flat
    # table (anti-duplicate test + frozen surface tests/surface_cli.json).
    PARAMETRES: List[Dict[str, Any]] = []

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}

    def log(self, message: str, emoji: str = "⚡"):
        print(f"{emoji} [{self.name.upper()}] {message}")

    @abstractmethod
    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Runs the workflow steps."""
        pass


class WorkflowRegistry:
    """Centralized registry of the available workflows."""

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
            raise ValueError(f"Unknown workflow '{name}'. Available workflows: {dispos}")
        return cls._workflows[nom]

    @classmethod
    def list_all(cls) -> Dict[str, str]:
        return {name: wf.description for name, wf in cls._workflows.items()}

    @classmethod
    def parametres_declares(cls) -> List[Dict[str, Any]]:
        """Aggregates the PARAMETRES declared by all registered workflows.

        Used by cli/parser.py to generate the "per workflow" option group;
        the order follows that of the registry (interactive menu).
        A child class inherits the PARAMETRES list of its parent (same object) —
        e.g. character3d ⊂ character_makeup: the declaration must be emitted
        only once, otherwise argparse rejects the duplicated flag.
        """
        declarations: List[Dict[str, Any]] = []
        vus: set = set()
        for wf_cls in cls._workflows.values():
            for declaration in getattr(wf_cls, "PARAMETRES", []):
                if id(declaration) not in vus:
                    vus.add(id(declaration))
                    declarations.append(declaration)
        return declarations
