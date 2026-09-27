#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch Workflow: generation of asset batches from a recipe / configuration file (JSON/Text).
Allows generating complete packs (10 weapons, 5 creatures, etc.) in a single run.
"""

import json
import os
from typing import Any, Dict, List

from core.config import DEFAULT_OUTPUT_DIR
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class BatchWorkflow(BaseWorkflow):
    name = "batch"
    description = "Batch generation from a JSON file or a textual list of concepts"

    emoji = "📦"

    # CLI declarations (audit §2.2, migration from cli/parser.py's flat table:
    # help/defaults kept as-is, unchanged surface).
    PARAMETRES = [
        dict(flags=("--file", "--recipe"), dest="file",
             help="JSON file or text list for the batch workflow."),
        dict(flags=("--continue-on-error",), dest="continue_on_error", action="store_true",
             help="batch: keep going through the batch after an asset failure and exit with code != 0 at the end with the list of failures (default: stop at the first error, code != 0)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        fichier_recette = params.get("file") or params.get("recipe")
        if not fichier_recette or not os.path.exists(fichier_recette):
            raise FileNotFoundError(f"Recipe file not found: {fichier_recette}")

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)

        self.log(f"Reading the batch recipe: {fichier_recette}...")

        # Load the task list
        tasks: List[Dict[str, Any]] = []
        if fichier_recette.endswith(".json"):
            with open(fichier_recette, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    tasks = data
                elif isinstance(data, dict) and "assets" in data:
                    tasks = data["assets"]
                else:
                    raise ValueError("Invalid JSON format: must be a list or an object with the 'assets' key.")
        else:
            # Line-by-line text file
            with open(fichier_recette, "r", encoding="utf-8") as f:
                for line in f:
                    concept = line.strip()
                    if concept and not concept.startswith("#"):
                        tasks.append({"prompt": concept})

        total = len(tasks)
        self.log(f"Starting the generation of {total} asset(s)...")

        # Default: stop at the first error (return code != 0 on the CLI side).
        # --continue-on-error: go through the whole batch then report the failures (code != 0 if failures).
        continue_sur_erreur = bool(params.get("continue_on_error"))
        echecs = []
        resultats = []
        for index, task in enumerate(tasks, start=1):
            prompt = task.get("prompt")
            wf_nom = task.get("workflow", "generate")
            self.log(f"--- Progress [{index}/{total}]: '{prompt}' (Workflow: {wf_nom}) ---")

            # Merge the global and task-specific parameters
            merged_params = dict(params)
            merged_params.update(task)
            merged_params["output_dir"] = output_dir

            wf_cls = WorkflowRegistry.get(wf_nom)
            wf_instance = wf_cls(self.config)

            try:
                res = wf_instance.run(merged_params)
                resultats.append(res)
            except Exception as e:
                echecs.append({"prompt": prompt, "workflow": wf_nom, "erreur": str(e)})
                if not continue_sur_erreur:
                    raise RuntimeError(
                        f"Asset {index}/{total} failed ('{prompt}' via {wf_nom}): {e} — "
                        f"batch interrupted (rerun with --continue-on-error to finish the batch anyway)."
                    ) from e
                self.log(f"❌ Error on asset '{prompt}': {e}")

        self.log(f"Batch finished: {len(resultats)}/{total} assets generated, {len(echecs)} failure(s).", emoji="🎉")

        return {
            "total_tasks": total,
            "completed": len(resultats),
            "echecs": echecs,
            "results": resultats
        }
