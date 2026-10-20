#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ocr_pdf workflow: extract text from PDFs via PdfCraft (native then OCR).

For one PDF (or every PDF of a directory) extracts the text layer with the
headless pdfcraft engine; when a document has no text layer (scans), runs
the OCR pass (--language, default fr) and extracts again. Output: one .txt
per document in the output directory, UTF-8.
"""

import os
import subprocess
from pathlib import Path
from typing import Any, Dict

from core.config import DEFAULT_OUTPUT_DIR
from core.photocraft import ErreurPhotocraft, trouver_cli_craftapp
from workflows.base import BaseWorkflow, WorkflowRegistry


def _texte_pdf(cli: Path, pdf: Path, timeout: int) -> str:
    r = subprocess.run([str(cli), "text", str(pdf)],
                       capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"pdfcraft text failed on {pdf.name}: "
                           f"{(r.stderr or r.stdout)[:200]}")
    return r.stdout or ""


def _ocr_pdf(cli: Path, pdf: Path, sortie: Path, langue: str, timeout: int) -> Path:
    """Runs the OCR pass into `sortie` (pdfcraft batch --steps ocr)."""
    dossier = sortie.parent
    dossier.mkdir(parents=True, exist_ok=True)
    if sortie.exists():
        sortie.unlink()
    r = subprocess.run(
        [str(cli), "batch", str(pdf), "--steps", "ocr", "--out-dir", str(dossier),
         "--language", langue],
        capture_output=True, text=True, encoding="utf-8", timeout=timeout,
    )
    if r.returncode != 0 or not sortie.exists():
        raise RuntimeError(f"pdfcraft OCR failed on {pdf.name}: "
                           f"{(r.stderr or r.stdout)[:200]}")
    return sortie


@WorkflowRegistry.register
class OcrPdfWorkflow(BaseWorkflow):
    """PDF text extraction, native layer first, OCR fallback (pdfcraft)."""

    name = "ocr_pdf"
    description = (
        "PDF to text via PdfCraft headless: native text layer first, OCR pass "
        "as fallback for scans (--language fr by default) — file or directory"
    )

    emoji = "📄"
    PARAMETRES = [
        dict(flags=("--language",), default="en",
             help="OCR language — pdfcraft 0.9.0 supports en only (upstream limit, re-screen on updates)"),
        dict(flags=("--forcer-ocr",), action="store_true",
             help="Skip the native text layer, always OCR"),
        dict(flags=("--timeout-ocr",), type=int, default=900,
             help="OCR timeout per document (s)"),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        entree = params.get("image") or params.get("input")
        if not entree or not os.path.exists(entree):
            raise ValueError(
                "The ocr_pdf workflow requires a valid input PDF or directory (-i / --input)."
            )
        langue = params.get("language", "en")
        forcer = bool(params.get("forcer_ocr"))
        timeout_ocr = int(params.get("timeout_ocr", 900))
        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)

        try:
            cli = trouver_cli_craftapp("pdfcraft", "PDFCRAFT_CLI")
        except ErreurPhotocraft as e:
            raise ValueError(str(e)) from e

        chemin_entree = Path(entree)
        pdfs = (
            sorted(p for p in chemin_entree.iterdir() if p.suffix.lower() == ".pdf")
            if chemin_entree.is_dir() else [chemin_entree]
        )
        if not pdfs:
            raise ValueError(f"no PDF found for {chemin_entree}")

        fichiers_sortie: list[str] = []
        dossier_ocr = Path(output_dir) / "_ocr_intermediaire"
        for pdf in pdfs:
            self.log(f"extracting text: {pdf.name}")
            texte = "" if forcer else _texte_pdf(cli, pdf, timeout=120)
            mode = "native"
            if not texte.strip():
                self.log(f"no text layer -> OCR pass ({langue})")
                ocr_sortie = dossier_ocr / f"{pdf.stem}.pdf"
                _ocr_pdf(cli, pdf, ocr_sortie, langue, timeout_ocr)
                texte = _texte_pdf(cli, ocr_sortie, timeout=120)
                mode = f"ocr ({langue})"
            chemin_txt = Path(output_dir) / f"{pdf.stem}.txt"
            chemin_txt.write_text(texte, encoding="utf-8", newline="\n")
            fichiers_sortie.append(str(chemin_txt))
            self.log(f"{pdf.name} -> {chemin_txt.name} "
                     f"({len(texte.split())} words, {mode})")

        self.log(f"{len(fichiers_sortie)} document(s) extracted", emoji="🎉")
        return {"output_file": fichiers_sortie[0] if fichiers_sortie else None,
                "files": fichiers_sortie}
