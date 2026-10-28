#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Local OCR — openbmb MiniCPM-OCR-1.0 (1.3B, Apache-2.0) via llama.cpp
`llama-server`.

A 1.3B vision model specialized in document/screenshot text extraction
(text, tables, formulas, UI text). Runs on the RX 6950 XT through the Vulkan
backend like every other llama.cpp tool of the factory — measured ~4 s/page
(image encoding 2.7-3.9 s + generation ~237 t/s, Q8_0, ~2 GB VRAM).

Server-only by design: the model emits its transcription inside the thinking
block, and the request-level `reasoning_effort: "none"` (llama-server only —
the mtmd-cli exposes no reasoning flag) is what routes the text to `content`.
Measured on the validation smokes: without it, `content` comes back empty.
Pipeline USER VALIDATED 2026-10-28 — MEMORY_BANK §1.49.
"""

import base64
import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List

from core.config import (
    DEFAULT_LLAMA_SERVER,
    DEFAULT_MINICPM_OCR_MODEL,
    DEFAULT_MINICPM_OCR_MMPROJ,
)

CONSIGNE_DEFAUT = "Transcribe all text in this image exactly, preserving layout."
_DELAI_SANTE_S = 90.0
_DELAI_PAGE_S = 240.0
_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def _port_libre() -> int:
    """Returns a free localhost port for the OCR server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _demarrer_serveur(
    llama_server: str,
    modele: str,
    mmproj: str,
    ngl: int,
) -> tuple[subprocess.Popen, int, str]:
    """Starts llama-server with the OCR model; waits for /health.

    Returns (process, port, log_path). The caller MUST stop the process
    (see _arreter_serveur). Raises RuntimeError with the log tail if the
    server dies or never becomes healthy.
    """
    for chemin, role in ((llama_server, "llama-server"), (modele, "model"), (mmproj, "mmproj")):
        if not os.path.exists(chemin):
            raise FileNotFoundError(f"{role} not found: {chemin}")

    port = _port_libre()
    desc_log = tempfile.NamedTemporaryFile(
        prefix="ocr_server_", suffix=".log", delete=False, mode="w"
    )
    journal = desc_log.name
    processus = subprocess.Popen(
        [
            llama_server,
            "-m", modele,
            "--mmproj", mmproj,
            "--host", "127.0.0.1",
            "--port", str(port),
            "-ngl", str(ngl),
        ],
        stdout=desc_log,
        stderr=subprocess.STDOUT,
    )
    desc_log.close()

    debut = time.monotonic()
    while time.monotonic() - debut < _DELAI_SANTE_S:
        if processus.poll() is not None:
            raise RuntimeError(
                f"llama-server exited early (code {processus.returncode}). Log: {journal}"
            )
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/health", timeout=2
            ) as reponse:
                if json.loads(reponse.read()).get("status") == "ok":
                    return processus, port, journal
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(0.5)
    _arreter_serveur(processus)
    raise RuntimeError(
        f"llama-server did not become healthy within {_DELAI_SANTE_S:.0f}s. Log: {journal}"
    )


def _arreter_serveur(processus: subprocess.Popen) -> None:
    """Stops the OCR server and releases the VRAM."""
    if processus.poll() is None:
        processus.terminate()
        try:
            processus.wait(timeout=10)
        except subprocess.TimeoutExpired:
            processus.kill()
            processus.wait(timeout=10)


def _transcrire_page(
    image: str, consigne: str, port: int, delai_s: float
) -> Dict[str, Any]:
    """OCR of one image through /v1/chat/completions (reasoning off)."""
    donnees = base64.b64encode(open(image, "rb").read()).decode()
    requete = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{donnees}"},
                    },
                    {"type": "text", "text": consigne},
                ],
            }
        ],
        "temperature": 0,
        "reasoning_effort": "none",
        "max_tokens": 4096,
    }
    appel = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=json.dumps(requete).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(appel, timeout=delai_s) as reponse:
        corps = json.loads(reponse.read())
    message = corps["choices"][0]["message"]
    texte = (message.get("content") or "").strip()
    if not texte:
        raise RuntimeError(
            "Empty OCR output: reasoning_effort was not honored (server too old?) "
            f"or the image contains no text ({image})."
        )
    minutages = corps.get("timings", {})
    return {
        "image": image,
        "texte": texte,
        "encodage_s": minutages.get("prompt_ms", 0) / 1000.0,
        "generation_s": minutages.get("predicted_ms", 0) / 1000.0,
    }


def executer_ocr(
    images: List[str],
    consigne: str = CONSIGNE_DEFAUT,
    llama_server: str = DEFAULT_LLAMA_SERVER,
    modele: str = DEFAULT_MINICPM_OCR_MODEL,
    mmproj: str = DEFAULT_MINICPM_OCR_MMPROJ,
    ngl: int = 99,
) -> Dict[str, Any]:
    """Runs OCR over `images` with one server session (load once, batch after).

    Returns {"pages": [ {image, texte, encodage_s, generation_s}, … ],
    "journal_serveur": path}. The server always shuts down before returning
    (VRAM released, even on error).
    """
    if not images:
        raise ValueError("No image to OCR.")
    processus, port, journal = _demarrer_serveur(llama_server, modele, mmproj, ngl)
    try:
        pages = [
            _transcrire_page(image, consigne, port, _DELAI_PAGE_S) for image in images
        ]
    finally:
        _arreter_serveur(processus)
    return {"pages": pages, "journal_serveur": journal}
