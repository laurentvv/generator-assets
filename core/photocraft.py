"""PhotoCraft headless bridge (serve mode, JSON-lines protocol).

Drives the portable ``photocraft-cli`` of the Craft suite (installed under
``D:\\CraftApps\\photocraft``, managed by the ``D:\\GIT\\craft-suite`` repo) to
apply real typography (text layers with font/size/color/tracking/alignment)
and geometric operations (crop with resample) to images without any GUI.

Protocol notes (validated 2026-10-20, photocraft 0.10.0):
- ``serve`` keeps ONE persistent session: documents opened with ``doc.new`` /
  ``doc.open`` stay alive between requests (unlike the stdio MCP server where
  every ``tools/call`` starts a fresh session).
- File paths are RELATIVE to the automation roots granted at launch:
  ``--automation-read-root`` scopes ``doc.open``, ``--automation-write-root``
  scopes ``doc.save``. Nothing outside those roots is readable or writable.
- Requests are one JSON object per line: ``{"id": N, "method": ..., "params":
  {...}}``; each answer comes back on one line as ``{"id": N, "ok": bool,
  "result": ...}`` (or ``"error"`` on failure).
- Batch steps use the Photoshop-actions shape ``{"command": <id>, "params":
  {...}}`` (NOT the ``{"id": ...}`` shape of the MCP ``command_batch`` tool).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

# Default install root of the Craft suite (see D:\GIT\craft-suite\apps.json).
RACINE_CRAFT_APPS = Path(r"D:\CraftApps")
NOM_APPLI = "photocraft"
SUFFIXE_BUILD = "-windows-x64-portable"


class ErreurPhotocraft(RuntimeError):
    """Raised when the photocraft engine rejects a request or answers badly."""


def trouver_cli_photocraft() -> Path:
    """Locates photocraft-cli.exe: env override, then the managed install."""
    override = os.environ.get("PHOTOCRAFT_CLI")
    if override:
        chemin = Path(override)
        if chemin.is_file():
            return chemin
        raise ErreurPhotocraft(
            f"PHOTOCRAFT_CLI={override} does not point to an existing file"
        )
    dossier_app = RACINE_CRAFT_APPS / NOM_APPLI
    if dossier_app.is_dir():
        candidats = sorted(dossier_app.glob(f"{NOM_APPLI}-*{SUFFIXE_BUILD}/{NOM_APPLI}-cli.exe"))
        if candidats:
            return candidats[-1]
    raise ErreurPhotocraft(
        "photocraft-cli.exe not found under "
        f"{dossier_app}. Install the Craft suite first: "
        "`python D:\\GIT\\craft-suite\\manage_craft_suite.py install photocraft`"
    )


class SessionPhotocraft:
    """One persistent headless engine session scoped to two directories."""

    def __init__(self, racine_lecture: Path, racine_ecriture: Path, timeout_s: float = 120.0):
        self.racine_lecture = Path(racine_lecture).resolve()
        self.racine_ecriture = Path(racine_ecriture).resolve()
        self._compteur = 0
        self._processus = subprocess.Popen(
            [
                str(trouver_cli_photocraft()), "serve",
                "--automation-read-root", str(self.racine_lecture),
                "--automation-write-root", str(self.racine_ecriture),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        self._timeout_s = timeout_s

    def __enter__(self) -> "SessionPhotocraft":
        return self

    def __exit__(self, *exc_info) -> None:
        self.fermer()

    def fermer(self) -> None:
        if self._processus.poll() is None:
            try:
                self._processus.stdin.close()
                self._processus.wait(timeout=self._timeout_s)
            except (subprocess.TimeoutExpired, OSError):
                self._processus.kill()

    def appel(self, methode: str, parametres: dict[str, Any] | None = None) -> Any:
        """Sends one request, reads one answer, returns `result` or raises."""
        self._compteur += 1
        requete = {"id": self._compteur, "method": methode, "params": parametres or {}}
        self._processus.stdin.write(json.dumps(requete) + "\n")
        self._processus.stdin.flush()
        ligne = self._processus.stdout.readline()
        if not ligne.strip():
            err = self._processus.stderr.read()[:400]
            raise ErreurPhotocraft(
                f"photocraft serve closed the session on {methode!r} (stderr: {err})"
            )
        message = json.loads(ligne)
        if not message.get("ok", False):
            raise ErreurPhotocraft(
                f"photocraft {methode} failed: {message.get('error', message)}"
            )
        return message.get("result")

    # ── High-level operations ─────────────────────────────────────────────

    def ouvrir_document(self, chemin: Path) -> Any:
        """Opens an image; `chemin` must live under the read root."""
        return self.appel("doc.open", {"path": self._chemin_relatif(chemin, self.racine_lecture)})

    def nouveau_document(self, largeur: int, hauteur: int, fond: str = "#ffffff") -> Any:
        return self.appel(
            "doc.new",
            {"width": largeur, "height": hauteur, "background": fond},
        )

    def lot(self, etapes: list[dict[str, Any]]) -> list[Any]:
        """Runs engine commands in order (one history step each).

        Each step: {"command": <command id>, "params": {...}}. Raises on the
        first failed step so callers never work on a half-applied batch.
        """
        resultat = self.appel("batch", {"steps": etapes})
        for etape in resultat.get("results", []):
            if not etape.get("ok", False):
                raise ErreurPhotocraft(f"photocraft batch step failed: {etape.get('error')}")
        return resultat

    def enregistrer(self, chemin: Path) -> Any:
        """Saves the active document; `chemin` must live under the write root."""
        return self.appel(
            "doc.save", {"path": self._chemin_relatif(chemin, self.racine_ecriture)}
        )

    def ajouter_texte(
        self,
        texte: str,
        x: int,
        y: int,
        taille: float,
        couleur: str = "#ffffff",
        alignement: str = "center",
        interlettrage: int = 0,
    ) -> Any:
        """Adds one text layer; (x, y) is the BASELINE anchor, in pixels.

        `interlettrage` is tracking in 1/1000 em (Photoshop convention).
        """
        return self.lot([
            {
                "command": "type.create",
                "params": {
                    "x": int(x), "y": int(y), "text": texte,
                    "size": taille, "color": couleur, "align": alignement,
                    "tracking": interlettrage,
                },
            }
        ])

    def recadrer(
        self,
        x: int, y: int, largeur: int, hauteur: int,
        largeur_cible: int | None = None, hauteur_cible: int | None = None,
    ) -> Any:
        """Crops a rectangle, optionally resampling to a target size (lanczos)."""
        parametres: dict[str, Any] = {
            "x": int(x), "y": int(y),
            "width": int(largeur), "height": int(hauteur),
            "resample": "lanczos",
        }
        if largeur_cible:
            parametres["targetWidth"] = int(largeur_cible)
        if hauteur_cible:
            parametres["targetHeight"] = int(hauteur_cible)
        return self.lot([{"command": "image.crop", "params": parametres}])

    @staticmethod
    def _chemin_relatif(chemin: Path, racine: Path) -> str:
        chemin = Path(chemin).resolve()
        relatif = chemin.relative_to(racine)
        return relatif.as_posix()
