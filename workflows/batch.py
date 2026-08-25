#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Batch : Génération de lots d'assets par recette / fichier de configuration (JSON/Text).
Permet de générer des packs complets (10 armes, 5 créatures, etc.) en une seule exécution.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from core.config import DEFAULT_OUTPUT_DIR
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class BatchWorkflow(BaseWorkflow):
    name = "batch"
    description = "Génération par lots depuis un fichier JSON ou liste textuelle de concepts"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        fichier_recette = params.get("file") or params.get("recipe")
        if not fichier_recette or not os.path.exists(fichier_recette):
            raise FileNotFoundError(f"Fichier de recette introuvable : {fichier_recette}")

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)

        self.log(f"Lecture de la recette batch : {fichier_recette}...")

        # Charger la liste des tâches
        tasks: List[Dict[str, Any]] = []
        if fichier_recette.endswith(".json"):
            with open(fichier_recette, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    tasks = data
                elif isinstance(data, dict) and "assets" in data:
                    tasks = data["assets"]
                else:
                    raise ValueError("Format JSON invalide : doit être une liste ou un objet avec la clé 'assets'.")
        else:
            # Fichier texte ligne par ligne
            with open(fichier_recette, "r", encoding="utf-8") as f:
                for line in f:
                    concept = line.strip()
                    if concept and not concept.startswith("#"):
                        tasks.append({"prompt": concept})

        total = len(tasks)
        self.log(f"Lancement de la génération de {total} asset(s)...")

        resultats = []
        for index, task in enumerate(tasks, start=1):
            prompt = task.get("prompt")
            wf_nom = task.get("workflow", "generate")
            self.log(f"--- Progression [{index}/{total}] : '{prompt}' (Workflow: {wf_nom}) ---")

            # Fusionner les paramètres globaux et spécifiques à la tâche
            merged_params = dict(params)
            merged_params.update(task)
            merged_params["output_dir"] = output_dir

            wf_cls = WorkflowRegistry.get(wf_nom)
            wf_instance = wf_cls(self.config)

            try:
                res = wf_instance.run(merged_params)
                resultats.append(res)
            except Exception as e:
                self.log(f"❌ Erreur sur l'asset '{prompt}' : {e}")

        self.log(f"Batch terminé : {len(resultats)}/{total} assets générés avec succès.", emoji="🎉")

        return {
            "total_tasks": total,
            "completed": len(resultats),
            "results": resultats
        }
