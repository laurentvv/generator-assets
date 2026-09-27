#!/usr/bin/env python
"""MiniMax-H3 Ref2VA turbo status test on master-864 — to run AFTER REBOOT (clean machine).

Context (2026-09-14): H3 has never been retested since master-841/6b3edaa (validation §1.16
= 6b3edaa era). Today's discovery (LTX broken on m864 AND m866, last good build =
6b3edaa) makes the H3 status critical: it is the production engine of the YouTube channel.

This script:
  1. Checks that C:\\SD is indeed on master-864/ca37fad (abort otherwise — the test targets m864).
  2. Displays the uptime + runs scripts/check_charge_systeme.py (abort if the machine is busy).
  3. Checks the H3 models + turbo LoRA + reference assets.
  4. Runs the validated workflow: main.py -w h3_ref2va --turbo (ref ref_frames12 + ref_audio_05,
     22 frames, seed 42 — identical to the reference test of 2026-09-09).
  5. Analyzes the log and gives a verdict (PASS + graph segments / precise failure signature).

Expected duration: ~38 min (ref encodes ~15 min CPU + sampling 8×~134 s + decode).
Usage:
    uv run python scripts/statut_h3_m864.py            # full test
    uv run python scripts/statut_h3_m864.py --dry-run  # checks the wiring without generating
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SD_CLI = Path(r"C:\SD\sd-cli.exe")
COMPTES_RENDUS = REPO / "output" / "test_h3_m864"
REF_FRAMES = REPO / "output" / "test_h3_ref2va" / "ref_frames12"
REF_AUDIO = REPO / "output" / "test_h3_ref2va" / "ref_audio_05.wav"
CHECK_CHARGE = REPO / "scripts" / "check_charge_systeme.py"

# The test targets master-864/ca37fad precisely (results not comparable on another build)
COMMIT_ATTENDU = "ca37fad"

# Known DiT graph segmentation references (upstream diagnostic #1976)
SEGMENTS_6B3EDAA = 2   # graph-cut validated §1.16: 2 segments (8.5 GB + 1.7 GB)
SEGMENTS_M866 = 51     # broken behavior observed on master-866

PROMPT = (
    "Use the dragon from <Video 1> and the roar from <Audio 1> as the opening state. "
    "The dragon turns its head toward the camera and breathes a stream of fire "
    "across the stone bridge."
)

SIGNATURES = {
    "ErrorOutOfDeviceMemory": "OOM at the Vulkan submit (same family as m866 yesterday)",
    "workspace capacity check": "workspace capacity refused by the memory manager",
    "ErrorDeviceLost": "device lost (driver — reboot before concluding)",
    "device fault": "device fault (driver — reboot before concluding)",
    "failed during weight preparation": "weight preparation failure (family #1946)",
}


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    # explicit encoding="utf-8": by default, captured subprocess+text=True (pipe, not
    # a real console) falls back to the system encoding (cp1252 here) instead of the
    # terminal's UTF-8, which makes any subprocess printing emojis crash
    # (UnicodeEncodeError on '\U0001f50d' etc. — see the check_charge_systeme.py crash).
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def verifier_prerequis(dry_run: bool) -> None:
    # sd-cli version: the test is specific to master-864
    if not SD_CLI.exists():
        sys.exit(f"❌ {SD_CLI} not found")
    r = run([str(SD_CLI), "--version"])
    commit = r.stdout.strip().split()[-1]
    print(f"sd-cli: commit {commit}")
    if commit != COMMIT_ATTENDU:
        sys.exit(f"❌ This test targets master-864/{COMMIT_ATTENDU} — current build differs. Abort.")

    # Uptime (info: the goal is a freshly rebooted machine)
    try:
        r = run(["powershell.exe", "-NoProfile", "-Command",
                 "(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime | "
                 "Select-Object -ExpandProperty TotalHours"])
        heures = float(r.stdout.strip().replace(",", "."))
        print(f"uptime: {heures:.1f} h" + ("" if heures < 2 else "  (⚠️ reboot recommended for a \"clean\" test)"))
    except Exception:
        print("uptime: undetermined (non-blocking)")

    # System load (blocking — AGENTS.md rule)
    # NB: the COMPLETE output is printed (not just the last line / the verdict)
    # to be able to immediately diagnose which counter (CPU/RAM/GPU/VRAM) and which
    # process made the check fail, without having to re-run it manually alongside.
    r = run([sys.executable, str(CHECK_CHARGE)])
    if r.stdout:
        print(r.stdout.strip())
    if r.stderr:
        print(f"[stderr check_charge_systeme.py]\n{r.stderr.strip()}")
    print(f"[exit code check_charge_systeme.py: {r.returncode}]")
    if r.returncode != 0 and not dry_run:
        sys.exit("❌ Machine busy — wait for a free slot (or reboot) then run again.")

    # Reference assets
    manquants = [str(p) for p in (REF_FRAMES, REF_AUDIO) if not p.exists()]
    if manquants:
        sys.exit(f"❌ Missing reference assets: {manquants}")
    n_frames = len(list(REF_FRAMES.glob("*.png")))
    print(f"reference: {REF_FRAMES.name} ({n_frames} frames) + {REF_AUDIO.name}")

    # H3 models (simple existence — integrity is checked by the workflow)
    modeles = [
        r"C:\Modeles_LLM\minimax_h3_ref2va_pruned-Q4_K_M.gguf",
        r"C:\Modeles_LLM\minimax_h3_video_vae_fp16.safetensors",
        r"C:\Modeles_LLM\minimax_h3_audio_vae_fp32.safetensors",
        r"C:\Modeles_LLM\qwen3vl_32b_minimax_h3-Q2_K_M.gguf",
        r"C:\Modeles_LLM\loras\minimax_h3_ref2v_turbo_8step_v1.0_768p_bf16.safetensors",
    ]
    manquants = [m for m in modeles if not Path(m).exists()]
    if manquants:
        sys.exit(f"❌ Missing models: {manquants}")
    print(f"H3 models + turbo LoRA: {len(modeles)}/{len(modeles)} present")


def lancer_test(dry_run: bool) -> tuple[int, Path]:
    COMPTES_RENDUS.mkdir(parents=True, exist_ok=True)
    horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
    log = COMPTES_RENDUS / f"h3_m864_{horodatage}.log"

    cmd = [sys.executable, str(REPO / "main.py"), "-w", "h3_ref2va",
           "-i", str(REF_FRAMES), "--ref-audio", str(REF_AUDIO),
           "-p", PROMPT, "--turbo", "--frames", "22", "--seed", "42",
           "-d", str(COMPTES_RENDUS)]
    if dry_run:
        cmd.append("--dry-run")

    print(f"\n🚀 Launching H3 turbo (log: {log})" + ("  [DRY-RUN]" if dry_run else ""))
    print("   ~38 min: ref encodes ~15 min CPU → sampling 8×~134 s → decode\n")
    debut = time.time()
    with open(log, "w", encoding="utf-8", errors="replace") as flux:
        processus = subprocess.Popen(cmd, stdout=flux, stderr=subprocess.STDOUT, cwd=REPO)
        try:
            code = processus.wait()
        except KeyboardInterrupt:
            processus.kill()
            sys.exit("\n⏹ Interrupted — run the command again to restart from scratch.")
    duree = time.time() - debut
    print(f"done in {duree/60:.0f} min (exit {code})")
    return code, log


def analyser_verdict(code: int, log: Path, dry_run: bool) -> None:
    if dry_run:
        print("\n=== DRY-RUN: wiring OK, no generation launched ===")
        return
    texte = log.read_text(encoding="utf-8", errors="replace").replace("\r", "\n")
    webm = sorted(COMPTES_RENDUS.glob("*.webm"), key=lambda p: p.stat().st_mtime)
    segments = re.findall(r"minimax_h3 using (\d+) segments", texte)

    print("\n" + "=" * 70)
    if code == 0 and webm:
        print("✅ VERDICT: H3 WORKS on master-864")
        print(f"   webm: {webm[-1].name} — to listen to/watch before quality validation.")
        print("   → Channel production OK on m864 (quality to be judged on the webm).")
    else:
        print(f"❌ VERDICT: H3 FAILS on master-864 (exit {code})")
        for motif, libelle in SIGNATURES.items():
            if motif in texte:
                print(f"   signature: {libelle}  [{motif}]")
        if segments:
            print(f"   DiT segmentation: {segments[-1]} segments"
                  f"  (references: {SEGMENTS_6B3EDAA} on 6b3edaa-validated, {SEGMENTS_M866} on m866-broken)")
        print("   → H3 production unavailable on m864: stay on Wan ≤20 frames,")
        print("     and report the data as a comment on issue #1976 (user approval).")
    print(f"full log: {log}")
    print("=" * 70)


def main() -> None:
    parseur = argparse.ArgumentParser(description="H3 Ref2VA turbo status on master-864 (post-reboot)")
    parseur.add_argument("--dry-run", action="store_true", help="checks the wiring without generating")
    args = parseur.parse_args()

    print("=== H3 Ref2VA turbo test on master-864 ===\n")
    verifier_prerequis(args.dry_run)
    code, log = lancer_test(args.dry_run)
    analyser_verdict(code, log, args.dry_run)


if __name__ == "__main__":
    main()
