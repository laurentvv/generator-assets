#!/usr/bin/env python
"""Test de statut MiniMax-H3 Ref2VA turbo sur master-864 — à lancer APRÈS REBOOT (machine propre).

Contexte (2026-09-14) : H3 n'a jamais été retesté depuis master-841/6b3edaa (validation §1.16
= époque 6b3edaa). La découverte du jour (LTX cassé sur m864 ET m866, dernier build bon =
6b3edaa) rend le statut H3 critique : c'est le moteur de production de la chaîne YouTube.

Ce script :
  1. Vérifie que C:\\SD est bien sur master-864/ca37fad (abort sinon — le test cible m864).
  2. Affiche l'uptime + lance scripts/check_charge_systeme.py (abort si machine occupée).
  3. Vérifie modèles H3 + LoRA turbo + assets de référence.
  4. Lance le workflow validé : main.py -w h3_ref2va --turbo (réf ref_frames12 + ref_audio_05,
     22 trames, seed 42 — identique au test de référence du 2026-09-09).
  5. Analyse le log et rend un verdict (PASS + segments graphe / signature d'échec précise).

Durée attendue : ~38 min (encodes réf ~15 min CPU + sampling 8×~134 s + décode).
Usage :
    uv run python scripts/statut_h3_m864.py            # test complet
    uv run python scripts/statut_h3_m864.py --dry-run  # vérifie le câblage sans générer
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

# Le test cible master-864/ca37fad précisément (résultats non comparables sur un autre build)
COMMIT_ATTENDU = "ca37fad"

# Références de segmentation graphe DiT connues (diagnostic amont #1976)
SEGMENTS_6B3EDAA = 2   # graph-cut validé §1.16 : 2 segments (8,5 Go + 1,7 Go)
SEGMENTS_M866 = 51     # comportement cassé observé sur master-866

PROMPT = (
    "Use the dragon from <Video 1> and the roar from <Audio 1> as the opening state. "
    "The dragon turns its head toward the camera and breathes a stream of fire "
    "across the stone bridge."
)

SIGNATURES = {
    "ErrorOutOfDeviceMemory": "OOM au submit Vulkan (même famille que m866 hier)",
    "workspace capacity check": "refus de capacité workspace par le gestionnaire mémoire",
    "ErrorDeviceLost": "device lost (pilote — rebooter avant de conclure)",
    "device fault": "device fault (pilote — rebooter avant de conclure)",
    "failed during weight preparation": "échec de préparation de poids (famille #1946)",
}


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    # encoding="utf-8" explicite : par défaut, subprocess+text=True capturé (pipe, pas
    # une vraie console) retombe sur l'encodage système (cp1252 ici) au lieu de l'UTF-8
    # du terminal, ce qui fait planter tout sous-processus qui imprime des emojis
    # (UnicodeEncodeError sur '\U0001f50d' etc. — cf. crash de check_charge_systeme.py).
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def verifier_prerequis(dry_run: bool) -> None:
    # Version sd-cli : le test est spécifique à master-864
    if not SD_CLI.exists():
        sys.exit(f"❌ {SD_CLI} introuvable")
    r = run([str(SD_CLI), "--version"])
    commit = r.stdout.strip().split()[-1]
    print(f"sd-cli : commit {commit}")
    if commit != COMMIT_ATTENDU:
        sys.exit(f"❌ Ce test cible master-864/{COMMIT_ATTENDU} — build actuel différent. Abort.")

    # Uptime (info : l'objectif est une machine fraîchement rebootée)
    try:
        r = run(["powershell.exe", "-NoProfile", "-Command",
                 "(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime | "
                 "Select-Object -ExpandProperty TotalHours"])
        heures = float(r.stdout.strip().replace(",", "."))
        print(f"uptime : {heures:.1f} h" + ("" if heures < 2 else "  (⚠️ reboot recommandé pour un test « propre »)"))
    except Exception:
        print("uptime : indéterminé (non bloquant)")

    # Charge système (bloquant — règle AGENTS.md)
    # NB : on affiche la sortie COMPLETE (pas seulement la dernière ligne / le verdict)
    # pour pouvoir diagnostiquer immédiatement quel compteur (CPU/RAM/GPU/VRAM) et quel
    # process ont fait échouer le check, sans devoir le relancer manuellement à côté.
    r = run([sys.executable, str(CHECK_CHARGE)])
    if r.stdout:
        print(r.stdout.strip())
    if r.stderr:
        print(f"[stderr check_charge_systeme.py]\n{r.stderr.strip()}")
    print(f"[exit code check_charge_systeme.py : {r.returncode}]")
    if r.returncode != 0 and not dry_run:
        sys.exit("❌ Machine occupée — attendre un créneau libre (ou rebooter) puis relancer.")

    # Assets de référence
    manquants = [str(p) for p in (REF_FRAMES, REF_AUDIO) if not p.exists()]
    if manquants:
        sys.exit(f"❌ Assets de référence manquants : {manquants}")
    n_frames = len(list(REF_FRAMES.glob("*.png")))
    print(f"référence : {REF_FRAMES.name} ({n_frames} trames) + {REF_AUDIO.name}")

    # Modèles H3 (simple existence — l'intégrité est vérifiée par le workflow)
    modeles = [
        r"C:\Modeles_LLM\minimax_h3_ref2va_pruned-Q4_K_M.gguf",
        r"C:\Modeles_LLM\minimax_h3_video_vae_fp16.safetensors",
        r"C:\Modeles_LLM\minimax_h3_audio_vae_fp32.safetensors",
        r"C:\Modeles_LLM\qwen3vl_32b_minimax_h3-Q2_K_M.gguf",
        r"C:\Modeles_LLM\loras\minimax_h3_ref2v_turbo_8step_v1.0_768p_bf16.safetensors",
    ]
    manquants = [m for m in modeles if not Path(m).exists()]
    if manquants:
        sys.exit(f"❌ Modèles manquants : {manquants}")
    print(f"modèles H3 + LoRA turbo : {len(modeles)}/{len(modeles)} présents")


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

    print(f"\n🚀 Lancement H3 turbo (log : {log})" + ("  [DRY-RUN]" if dry_run else ""))
    print("   ~38 min : encodes réf ~15 min CPU → sampling 8×~134 s → décode\n")
    debut = time.time()
    with open(log, "w", encoding="utf-8", errors="replace") as flux:
        processus = subprocess.Popen(cmd, stdout=flux, stderr=subprocess.STDOUT, cwd=REPO)
        try:
            code = processus.wait()
        except KeyboardInterrupt:
            processus.kill()
            sys.exit("\n⏹ Interrompu — relancer la commande pour reprendre depuis zéro.")
    duree = time.time() - debut
    print(f"terminé en {duree/60:.0f} min (exit {code})")
    return code, log


def analyser_verdict(code: int, log: Path, dry_run: bool) -> None:
    if dry_run:
        print("\n=== DRY-RUN : câblage OK, aucune génération lancée ===")
        return
    texte = log.read_text(encoding="utf-8", errors="replace").replace("\r", "\n")
    webm = sorted(COMPTES_RENDUS.glob("*.webm"), key=lambda p: p.stat().st_mtime)
    segments = re.findall(r"minimax_h3 using (\d+) segments", texte)

    print("\n" + "=" * 70)
    if code == 0 and webm:
        print("✅ VERDICT : H3 FONCTIONNE sur master-864")
        print(f"   webm : {webm[-1].name} — à écouter/voir avant validation qualité.")
        print("   → Production chaîne OK sur m864 (qualité à juger sur le webm).")
    else:
        print(f"❌ VERDICT : H3 ÉCHOUE sur master-864 (exit {code})")
        for motif, libelle in SIGNATURES.items():
            if motif in texte:
                print(f"   signature : {libelle}  [{motif}]")
        if segments:
            print(f"   segmentation DiT : {segments[-1]} segments"
                  f"  (références : {SEGMENTS_6B3EDAA} sur 6b3edaa-validé, {SEGMENTS_M866} sur m866-cassé)")
        print("   → Production H3 indisponible sur m864 : rester sur Wan ≤20 trames,")
        print("     et reporter la donnée en commentaire de l'issue #1976 (accord utilisateur).")
    print(f"log complet : {log}")
    print("=" * 70)


def main() -> None:
    parseur = argparse.ArgumentParser(description="Statut H3 Ref2VA turbo sur master-864 (post-reboot)")
    parseur.add_argument("--dry-run", action="store_true", help="vérifie le câblage sans générer")
    args = parseur.parse_args()

    print("=== Test H3 Ref2VA turbo sur master-864 ===\n")
    verifier_prerequis(args.dry_run)
    code, log = lancer_test(args.dry_run)
    analyser_verdict(code, log, args.dry_run)


if __name__ == "__main__":
    main()
