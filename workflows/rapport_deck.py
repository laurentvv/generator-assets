#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rapport_deck workflow: benchmark report deck via DeckCraft.

Turns a JSON file of measures ([{"label": ..., "valeur": ..., "unite": ...},
{"section": ..., "lignes": [...]}] both accepted) into a presentation —
title slide plus one summary slide per section or one global summary —
exported as PDF through the headless DeckCraft engine. Slides are 960x540
points; body lines land as one text block per slide.
"""

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict

from core.config import DEFAULT_OUTPUT_DIR
from core.photocraft import ErreurPhotocraft, trouver_cli_craftapp
from workflows.base import BaseWorkflow, WorkflowRegistry


def _lignes_des_donnees(donnees: list) -> list:
    """Normalizes the input JSON into display lines."""
    lignes: list[str] = []
    for entree in donnees:
        if not isinstance(entree, dict):
            continue
        if "section" in entree:
            lignes.append(f"{entree['section']} :")
            for ligne in entree.get("lignes", []):
                lignes.append(f"  {ligne}")
        elif "label" in entree:
            valeur = entree.get("valeur", "?")
            unite = entree.get("unite", "")
            lignes.append(f"{entree['label']} : {valeur} {unite}".rstrip())
    return lignes


def _mesures_numeriques(donnees: list) -> tuple[list[str], list[float]]:
    """Extracts (labels, values) pairs for the chart: explicit label/valeur
    entries, plus 'label : 123 unit' lines inside sections."""
    etiquettes: list[str] = []
    valeurs: list[float] = []
    motif = re.compile(r"^(.{2,60}?)\s*:\s*(-?[0-9]+(?:[.,][0-9]+)?)")
    for entree in donnees:
        if not isinstance(entree, dict):
            continue
        if "label" in entree and isinstance(entree.get("valeur"), (int, float)):
            etiquettes.append(str(entree["label"]))
            valeurs.append(float(entree["valeur"]))
        elif "section" in entree:
            for ligne in entree.get("lignes", []):
                m = motif.match(str(ligne))
                if m:
                    etiquettes.append(m.group(1).strip())
                    valeurs.append(float(m.group(2).replace(",", ".")))
    return etiquettes, valeurs


@WorkflowRegistry.register
class RapportDeckWorkflow(BaseWorkflow):
    """Benchmark JSON -> presentation -> PDF (DeckCraft headless)."""

    name = "rapport_deck"
    description = (
        "Benchmark report deck via DeckCraft headless: JSON measures -> title "
        "+ chart slide + summary slides -> PDF"
    )

    emoji = "📊"
    PARAMETRES = [
        dict(flags=("--donnees",), default=None,
             help="JSON file of measures: [{'label','valeur','unite'}] or "
                  "[{'section','lignes':[...]}]"),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        chemin_donnees = params.get("donnees")
        if not chemin_donnees or not os.path.exists(chemin_donnees):
            raise ValueError(
                "The rapport_deck workflow requires a valid JSON measures file "
                "(--donnees)."
            )
        with open(chemin_donnees, encoding="utf-8") as f:
            donnees = json.load(f)
        if not isinstance(donnees, list) or not donnees:
            raise ValueError("--donnees must be a non-empty JSON array")

        titre = params.get("titre") or "Rapport de benchmarks"
        sous_titre = params.get("sous_titre")
        lignes = _lignes_des_donnees(donnees)
        if not lignes:
            raise ValueError("no measure found in the JSON file")

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)
        nom_base = Path(chemin_donnees).stem
        chemin_pdf = Path(output_dir) / f"rapport_{nom_base}.pdf"

        try:
            cli = trouver_cli_craftapp("deckcraft", "DECKCRAFT_CLI")
        except ErreurPhotocraft as e:
            raise ValueError(str(e)) from e

        # A fresh `run` presentation starts with one EMPTY title slide; we add
        # our own title slide first, then delete the empty one (index 0).
        titre_params = {"layout": "title", "title": titre}
        if sous_titre:
            titre_params["body"] = sous_titre
        # Split the lines over slides of at most 12 lines each.
        morceaux = [lignes[i:i + 12] for i in range(0, len(lignes), 12)] or [[]]
        commande = [str(cli), "run",
                    "--cmd", "slide.new=" + json.dumps(titre_params, ensure_ascii=False)]
        # Chart slide first when numeric measures exist (the illustration),
        # then the text summary slides.
        etiquettes, valeurs = _mesures_numeriques(donnees)
        if len(valeurs) >= 2:
            chart = {"type": "column", "categories": etiquettes,
                     "series": [{"name": titre, "values": valeurs}],
                     "rect": [60, 110, 840, 380]}
            commande += ["--cmd", "slide.new=" + json.dumps(
                {"layout": "titleOnly", "title": f"{titre} - graphique"}, ensure_ascii=False),
                "--cmd", "insert.chart=" + json.dumps(chart, ensure_ascii=False)]
            self.log(f"chart slide: {len(valeurs)} measures")
        for morceau in morceaux:
            body = {"layout": "titleAndContent",
                    "title": titre if len(morceaux) == 1 else f"{titre} ({len(morceaux)} slides)",
                    "body": "\n".join(morceau)}
            commande += ["--cmd", "slide.new=" + json.dumps(body, ensure_ascii=False)]
        commande += ["--cmd", "slide.delete=" + json.dumps({"index": 0}),
                     "--save", str(chemin_pdf)]

        self.log(f"building deck: {titre} ({len(lignes)} measures, {len(morceaux)} slide(s))")
        r = subprocess.run(commande, capture_output=True, text=True,
                           encoding="utf-8", timeout=300)
        if r.returncode != 0 or not chemin_pdf.exists():
            raise RuntimeError(f"deckcraft run failed: {(r.stderr or r.stdout)[:300]}")

        self.log(f"report saved: {chemin_pdf} "
                 f"({chemin_pdf.stat().st_size / 1024:.0f} KB)", emoji="🎉")
        return {"output_file": str(chemin_pdf), "files": [str(chemin_pdf)]}
