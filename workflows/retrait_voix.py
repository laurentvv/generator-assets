#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Retrait de Voix : suppression du chant d'un morceau par séparation
de sources HTDemucs (audio.cpp, Vulkan). Validé par l'utilisateur le
2026-09-06 sur une piste complète de 4 min 07 s.

Produit l'instrumental sans chant (mixage drums+bass+other à niveaux
préservés) + les 4 stems complets (drums, bass, other, vocals).
"""

import os
from typing import Any, Dict

from core.config import slugifier_texte
from core.separation import retirer_voix
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class RetraitVoixWorkflow(BaseWorkflow):
    """Retrait du chant d'un morceau (HTDemucs GGUF, Vulkan) — instrumental + stems."""

    name = "retrait_voix"
    description = ("Supprime le chant d'un morceau via HTDemucs (audio.cpp Vulkan) : "
                   "instrumental sans voix + 4 stems (drums/bass/other/vocals), "
                   "rééchantillonnage 44,1 kHz automatique")

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        source = params.get("input")
        if not source or not os.path.exists(source):
            raise ValueError("Audio source introuvable : le passer via -i <MP3/WAV>.")
        backend = params.get("music_backend") or "vulkan"
        if backend == "auto":
            backend = "vulkan"

        nom = slugifier_texte(params.get("output") or os.path.splitext(os.path.basename(source))[0])[:60]
        dossier = os.path.join("output", "retrait_voix", nom)

        self.log(f"Séparation HTDemucs de {source} (backend {backend})", "🎧")
        res = retirer_voix(source, dossier, backend=backend)
        self.log(f"Instrumental prêt : {res['instrumental_mp3']} — écoute pour valider", "✅")
        self.log(f"Stems conservés : {res['stems_dir']} (voix isolée : vocals.wav)", "📦")
        return res
