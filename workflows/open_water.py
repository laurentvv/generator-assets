#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
open-water procedural storm-sea clips (Leonxlnx/open-water, MIT).

Renders physics-based ocean footage (Tessendorf FFT cascades, Elfouhaily
spectrum, volumetric clouds, rain) as fixed-camera, constant-weather clips —
exactly the shape a loopable backdrop needs. Pipeline USER VALIDATED
2026-10-24 ("image ok" on the 4 Vent-Gris legs, MEMORY_BANK §1.47): local
clone with the LOCAL `tools/render_shot.mjs` addition driving the interactive
frame path (the upstream `render/render.mjs` plays a scripted, non-loopable
60 s film instead). Headless Chrome ANGLE/D3D11 on the RX 6950 XT:
1080p24 ≈ 0.17-0.19 s/frame → a 10 s leg ≈ 1.5 min total (GPU-light).
Optional perfect-loop post-step reuses the in-game-validated xfade recipe
(fps=24 on BOTH branches, offset = post_duration − fade, 1.5 s fade) from
`scripts/faire_boucle_menu_vent_gris.py`, then audits the join
(`scripts/audit_bande_noire.py --raccord`).

Output is SILENT on purpose: the game / channel lays its own music bed.

Measured pitfalls (2026-10-24 night run, kept as warnings below):
- the storm preset defaults to UNSEEDED `lightning=0.7` → multi-second
  exposure crushes (mean L 33→4→30), unloopable → pass `lightning=0`;
- `elev=<negative>` is a TARGET eased from the day default and the
  sun→moon switch wipes the cloud history, which rebuilds on RENDERED
  frames only → keep `--ow-warm >= 10` (render_shot already enforces the
  rendered part, this guards the user shortening it).
"""

import hashlib
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict

from core.config import DEFAULT_OPEN_WATER_DIR, DEFAULT_OUTPUT_DIR
from core.process import run_engine
from workflows.base import BaseWorkflow, WorkflowRegistry

SCRIPT_CHECK_CHARGE = Path(__file__).resolve().parent.parent / "scripts" / "check_charge_systeme.py"
SCRIPT_AUDIT = Path(__file__).resolve().parent.parent / "scripts" / "audit_bande_noire.py"

# render_shot.mjs hardcodes http://localhost:5173 — the server port is part
# of the validated chain, not a knob.
PORT_SERVEUR = 5173

RECIPE_STORM_DAY = "preset=storm&float=0&yaw=200&pitch=6&h=6&fov=50"


def _port_occupe(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _attendre_serveur(delai_s: float = 30.0) -> bool:
    url = f"http://localhost:{PORT_SERVEUR}/"
    deadline = time.monotonic() + delai_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return True
        except Exception:
            time.sleep(0.5)
    return False


@WorkflowRegistry.register
class OpenWaterWorkflow(BaseWorkflow):
    name = "open_water"
    description = (
        "open-water procedural storm-sea clips (WebGL2 physics ocean, MIT; "
        "validated silent backdrop/keyframe source; optional perfect xfade loop)"
    )

    emoji = "🌊"

    # --fps/--width/--height stay in the flat table (shared across families,
    # workflow defaults 24 / 1920 / 1080 applied here when omitted).
    PARAMETRES = [
        dict(flags=("--ow-params",), default=RECIPE_STORM_DAY,
             help="open-water URL params (weather+camera) appended after '?render&q=high&scale=1&' "
                  "(keys: preset wind rain clouds cloudDark elev yaw pitch h fov lightning float; "
                  "default: validated storm-day recipe; loops need lightning=0)."),
        dict(flags=("--ow-duration",), type=float, default=10.0,
             help="Clip duration in seconds (default: 10 — validated leg length)."),
        dict(flags=("--ow-warm",), type=float, default=10.0,
             help="Rendered warm-up seconds before capture (cloud history; keep >= 10 after elev<0 / sun-to-moon switch)."),
        dict(flags=("--ow-crf",), default="15",
             help="x264 CRF of the master (default: 15)."),
        dict(flags=("--ow-loop",), action="store_true", default=False,
             help="Build the perfect infinite loop (validated xfade: fps=24 both branches, offset=post-fade, 1.5 s) + black-band audit."),
        dict(flags=("--ow-dir",), default=None,
             help="open-water clone path (default: env OPEN_WATER_DIR or C:\\GIT\\open-water)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        ow_params = str(params.get("ow_params") or RECIPE_STORM_DAY)
        duration = max(1.0, float(params.get("ow_duration") or 10.0))
        warm = float(params.get("ow_warm") or 10.0)
        crf = str(params.get("ow_crf") or "15")
        construire_boucle = bool(params.get("ow_loop"))

        fps = int(params.get("fps") or 24)
        width = int(params.get("width") or 1920)
        height = int(params.get("height") or 1080)

        ow_dir = Path(params.get("ow_dir") or DEFAULT_OPEN_WATER_DIR)
        self._verifier_prerequis(ow_dir)

        # Measured pitfalls → loud warnings before any GPU time is spent.
        if "preset=storm" in ow_params and "lightning=" not in ow_params:
            self.log(
                "storm preset defaults to UNSEEDED lightning=0.7 — multi-second exposure crushes, "
                "unloopable. For a loop add 'lightning=0' to --ow-params.",
                emoji="⚠️",
            )
        elev = re.search(r"(?:^|&)elev=(-?\d+(?:\.\d+)?)", ow_params)
        if elev and float(elev.group(1)) < 0 and warm < 10.0:
            self.log(
                f"elev={elev.group(1)} eases from the day default and the sun→moon switch wipes the "
                f"cloud history (rebuilt on rendered frames only) — --ow-warm {warm} < 10 risks a dark dip.",
                emoji="⚠️",
            )

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        nom = params.get("output")
        if not nom:
            preset = re.search(r"(?:^|&)preset=([^&]+)", ow_params)
            slug = preset.group(1) if preset else "custom"
            digest = hashlib.md5(ow_params.encode("utf-8")).hexdigest()[:8]
            nom = f"open_water_{slug}_{digest}"
        master = str((Path(output_dir) / f"{nom}.mp4").resolve())  # ABSOLUTE: render_shot runs with cwd=ow_dir

        # Load pre-check (AGENTS.md rule: never launch heavy generation on a busy machine)
        if SCRIPT_CHECK_CHARGE.exists():
            self.log("System load pre-check (CPU/GPU/RAM/VRAM)...")
            retour = run_engine(
                [sys.executable, str(SCRIPT_CHECK_CHARGE)],
                capture=False, check=False, timeout=300, etiquette="load check",
            )
            if retour.returncode == 1:
                raise RuntimeError("Busy machine (check_charge_systeme exit 1) — wait for a free slot before relaunching.")

        self.log(
            f"Rendering {duration:.0f}s {width}x{height}@{fps} (warm {warm:.0f}s, crf {crf}) — silent clip, MIT."
        )
        serveur = self._demarrer_serveur(ow_dir)
        try:
            run_engine(
                ["node", "tools/render_shot.mjs",
                 "--params", ow_params,
                 "--fps", str(fps), "--w", str(width), "--h", str(height),
                 "--from", "0", "--to", str(duration),
                 "--warm", str(warm), "--crf", crf,
                 "--out", master],
                capture=True,
                check=True,
                timeout=int(600 + (duration + warm) * fps * 2),
                cwd=str(ow_dir),
                log_path=str(Path(output_dir) / f"{nom}_render.log"),
                etiquette="open-water render",
            )
        finally:
            if serveur is not None:
                serveur.terminate()
                serveur.wait(timeout=15)

        resultat: Dict[str, Any] = {"master": master}
        self.log(f"Master saved: {master}", emoji="✅")

        if construire_boucle:
            boucle, audit = self._construire_boucle(master, str((Path(output_dir) / f"{nom}_boucle.mp4").resolve()))
            resultat["loop"] = boucle
            if audit is not None:
                resultat["audit"] = "CONFORMING" if audit else "NON-CONFORMING"
        return resultat

    def _verifier_prerequis(self, ow_dir: Path) -> None:
        if not ow_dir.is_dir():
            raise FileNotFoundError(
                f"open-water clone not found: {ow_dir} — clone https://github.com/Leonxlnx/open-water "
                f"or point --ow-dir / env OPEN_WATER_DIR at it."
            )
        if not (ow_dir / "tools" / "render_shot.mjs").exists():
            raise FileNotFoundError(
                f"{ow_dir}/tools/render_shot.mjs missing — this workflow needs the LOCAL render_shot "
                f"addition (fixed camera + constant weather), not the bare upstream clone."
            )
        if shutil.which("node") is None:
            raise RuntimeError("node not found on PATH — required to drive the open-water renderer.")
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg not found on PATH — render_shot.mjs pipes raw frames into it.")
        if not (ow_dir / "node_modules" / "puppeteer-core").exists():
            raise RuntimeError(
                f"open-water dependencies not installed — run 'npm install' in {ow_dir} once "
                f"(puppeteer-core → system Chrome, the only dev dependency)."
            )

    def _demarrer_serveur(self, ow_dir: Path) -> subprocess.Popen:
        """Ensures tools/serve.mjs answers on the hardcoded port 5173.

        Returns the Popen to terminate (None if a server was already up —
        not ours to kill).
        """
        if _port_occupe(PORT_SERVEUR):
            self.log(f"Reusing the server already answering on :{PORT_SERVEUR}.")
            return None
        self.log("Starting tools/serve.mjs (static server for the renderer)...")
        serveur = subprocess.Popen(
            ["node", "tools/serve.mjs"],
            cwd=str(ow_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if not _attendre_serveur():
            serveur.terminate()
            serveur.wait(timeout=15)
            raise RuntimeError(f"tools/serve.mjs did not answer on :{PORT_SERVEUR} within 30 s.")
        return serveur

    def _construire_boucle(self, master: str, boucle: str):
        """Perfect infinite loop via the in-game-validated xfade recipe, then audit.

        Returns (loop_path, audit_ok) — audit_ok None when the audit script is absent.
        """
        # Lazy import: pulls the core.cinema chain only when --ow-loop is used.
        from scripts.faire_boucle_menu_vent_gris import boucle_parfaite

        self.log("Perfect loop (xfade recipe validated in game: fps=24 both branches, offset=post−fade)...")
        boucle_parfaite(master, boucle)

        if not SCRIPT_AUDIT.exists():
            return boucle, None
        self.log("Black-band audit of the loop (--zero + --raccord, same checks as the night run)...")
        retour = run_engine(
            [sys.executable, str(SCRIPT_AUDIT), "--zero", boucle, "--raccord", boucle],
            capture=True, check=False, timeout=300, etiquette="loop audit",
        )
        # audit_bande_noire.py exits 0 only when every checked video conforms.
        conforme = retour.returncode == 0
        if conforme:
            self.log(f"Loop audit: CONFORMING ({boucle})", emoji="✅")
        else:
            self.log(f"Loop audit: NON-CONFORMING — inspect {boucle} before production use.", emoji="⛔")
        return boucle, conforme
