#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Local OCR workflow: text extraction from documents and screenshots.

Runs openbmb MiniCPM-OCR-1.0 (1.3B, Apache-2.0) through llama-server on the
RX 6950 XT (~4 s/page, ~2 GB VRAM). Accepts one image or a whole directory;
single image → sidecar .txt, directory → one combined .md with a section per
image. Pipeline USER VALIDATED 2026-10-28 — MEMORY_BANK §1.49. Distinct from
`ocr_pdf` (pdfcraft, native PDF text + English-only OCR fallback): this one
is the vision path for scans, screenshots and UI captures, FR included.
"""

import os
from pathlib import Path
from typing import Any, Dict, List

from core.config import DEFAULT_OUTPUT_DIR
from core.ocr_minicpm import CONSIGNE_DEFAUT, executer_ocr
from core.process import run_engine
from workflows.base import BaseWorkflow, WorkflowRegistry

SCRIPT_CHECK_CHARGE = Path(__file__).resolve().parent.parent / "scripts" / "check_charge_systeme.py"


def _collecter_images(entree: str) -> List[Path]:
    """One image path, or every image of a directory (sorted)."""
    chemin = Path(entree)
    if chemin.is_dir():
        images = sorted(p for p in chemin.iterdir() if p.suffix.lower() in
                        {".png", ".jpg", ".jpeg", ".webp", ".bmp"})
        if not images:
            raise ValueError(f"No image found in {chemin}")
        return images
    if not chemin.exists():
        raise ValueError(f"Input not found: {chemin}")
    return [chemin]


@WorkflowRegistry.register
class OcrImageWorkflow(BaseWorkflow):
    """Text extraction from images/screenshots (MiniCPM-OCR-1.0, llama-server)."""

    name = "ocr_image"
    description = (
        "Local OCR on images/screenshots (MiniCPM-OCR-1.0 1.3B via llama-server, "
        "~2 GB VRAM, ~4 s/page; FR/EN; validated 2026-10-28) — one image -> .txt, "
        "directory -> combined .md"
    )

    emoji = "🔍"

    # CLI declaration (audit §2.2 keystone). --input / --output / --output-dir
    # come from the flat table.
    PARAMETRES = [
        dict(flags=("--ocr-consigne",), default=None,
             help="Custom OCR instruction in English (default: exact transcription "
                  "preserving layout)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        entree = params.get("image") or params.get("input")
        if not entree:
            raise ValueError(
                "The ocr_image workflow requires an input image or directory (-i / --input)."
            )
        images = _collecter_images(entree)
        consigne = params.get("ocr_consigne") or CONSIGNE_DEFAUT
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)

        # Load pre-check (AGENTS.md rule: never launch heavy generation on a busy machine)
        if SCRIPT_CHECK_CHARGE.exists():
            self.log("System load pre-check (CPU/GPU/RAM/VRAM)...")
            import sys

            retour = run_engine(
                [sys.executable, str(SCRIPT_CHECK_CHARGE)],
                capture=False, check=False, timeout=300, etiquette="load check",
            )
            if retour.returncode == 1:
                raise RuntimeError(
                    "Busy machine (check_charge_systeme exit 1) — wait for a free slot "
                    "before relaunching."
                )

        self.log(f"OCR on {len(images)} image(s) (MiniCPM-OCR-1.0, ~4 s/page)...")
        resultat = executer_ocr([str(image) for image in images], consigne=consigne)

        fichiers: List[str] = []
        if len(resultat["pages"]) == 1:
            page = resultat["pages"][0]
            nom_sortie = params.get("output") or f"{Path(page['image']).stem}_ocr"
            sortie = Path(output_dir) / f"{nom_sortie}.txt"
            sortie.write_text(page["texte"] + "\n", encoding="utf-8")
            fichiers.append(str(sortie))
            print(f"\n--- {Path(page['image']).name} ---")
            print(page["texte"])
        else:
            nom_sortie = params.get("output") or "ocr_resultat"
            sortie = Path(output_dir) / f"{nom_sortie}.md"
            lignes = ["# OCR results", ""]
            for page in resultat["pages"]:
                lignes += [f"## {Path(page['image']).name}", "", page["texte"], ""]
                print(f"  • {Path(page['image']).name}: {len(page['texte'])} chars")
            sortie.write_text("\n".join(lignes), encoding="utf-8")
            fichiers.append(str(sortie))

        for page in resultat["pages"]:
            self.log(
                f"{Path(page['image']).name}: encode {page['encodage_s']:.1f}s + "
                f"generate {page['generation_s']:.1f}s",
                emoji="⏱️",
            )
        self.log(f"Transcription saved: {fichiers[0]}", emoji="✅")
        return {"output_file": fichiers[0], "files": fichiers,
                "journal_serveur": resultat["journal_serveur"]}
