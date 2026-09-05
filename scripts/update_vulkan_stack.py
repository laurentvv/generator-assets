#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gestionnaire unifié de la Suite IA Vulkan pour Generator Assets.
Supervise et automatise la mise à jour et la compilation Vulkan de :
  1. stable-diffusion.cpp (Moteur Image, Matériaux PBR, et Vidéo Wan/LTX/MiniMax)
  2. llama.cpp (Moteur LLM Direction Artistique & Prompt Engineering)
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Support UTF-8 sur consoles Windows (évite les erreurs UnicodeEncodeError cp1252)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Résolution des imports quel que soit le dossier de travail courant
script_dir = Path(__file__).resolve().parent
repo_root = script_dir.parent
for p in [str(repo_root), str(script_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from scripts.update_sd_cpp import (
        DEFAULT_INSTALL_DIR as DEFAULT_SD_DIR,
        DEFAULT_SOURCE_DIR as DEFAULT_SD_SRC,
        action_compiler_vulkan as build_sd,
        action_telecharger_release as download_sd,
        action_verifier as check_sd,
        detecter_vulkan_sdk,
        restaurer_sauvegarde as rollback_sd
    )
    from scripts.update_llama_cpp import (
        DEFAULT_INSTALL_DIR as DEFAULT_LLAMA_DIR,
        DEFAULT_SOURCE_DIR as DEFAULT_LLAMA_SRC,
        action_compiler_vulkan as build_llama,
        action_telecharger_release as download_llama,
        action_verifier as check_llama,
        restaurer_sauvegarde as rollback_llama
    )
except ImportError:
    from update_sd_cpp import (
        DEFAULT_INSTALL_DIR as DEFAULT_SD_DIR,
        DEFAULT_SOURCE_DIR as DEFAULT_SD_SRC,
        action_compiler_vulkan as build_sd,
        action_telecharger_release as download_sd,
        action_verifier as check_sd,
        detecter_vulkan_sdk,
        restaurer_sauvegarde as rollback_sd
    )
    from update_llama_cpp import (
        DEFAULT_INSTALL_DIR as DEFAULT_LLAMA_DIR,
        DEFAULT_SOURCE_DIR as DEFAULT_LLAMA_SRC,
        action_compiler_vulkan as build_llama,
        action_telecharger_release as download_llama,
        action_verifier as check_llama,
        restaurer_sauvegarde as rollback_llama
    )


def inspecter_gpu_vulkan() -> None:
    """Affiche les informations sur le GPU et le pilote Vulkan du système."""
    vulkaninfo_bin = shutil.which("vulkaninfo")
    sdk = detecter_vulkan_sdk()

    print("\n" + "=" * 70)
    print(" 🎮 DIAGNOSTIC MATÉRIEL VULKAN DU SYSTÈME")
    print("=" * 70)
    print(f"  • SDK Vulkan installé : {sdk or '❌ Non détecté'}")

    if vulkaninfo_bin:
        try:
            res = subprocess.run(
                ["vulkaninfo", "--summary"],
                capture_output=True,
                text=True,
                timeout=8
            )
            out = res.stdout or ""
            gpu_lines = [l.strip() for l in out.split("\n") if "deviceName" in l or "driverVersion" in l or "apiVersion" in l]
            for l in gpu_lines:
                print(f"  • {l}")
        except Exception:
            print("  • vulkaninfo disponible dans System32")
    else:
        print("  • vulkaninfo non trouvé dans le PATH")
    print("=" * 70 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gestionnaire unifié de la Suite IA Vulkan (stable-diffusion.cpp + llama.cpp)."
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Vérifie l'état de l'ensemble de la suite Vulkan (SD + LLaMA + GPU)."
    )
    parser.add_argument(
        "--download", action="store_true",
        help="Met à jour l'ensemble de la suite Vulkan via les dernières releases officielles GitHub."
    )
    parser.add_argument(
        "--build", action="store_true",
        help="Recompile nativement les deux moteurs avec Vulkan (CMake + MSVC)."
    )
    parser.add_argument(
        "--rollback", action="store_true",
        help="Restaure la sauvegarde précédente pour les deux moteurs."
    )
    parser.add_argument(
        "--clean", action="store_true",
        help="Nettoie les dossiers build avant de recompiler."
    )
    parser.add_argument(
        "--jobs", "-j", type=int, default=None,
        help="Nombre de cœurs processeur pour la compilation."
    )

    args = parser.parse_args()

    # Si aucun argument spécifique, exécuter la vérification complète
    if not (args.check or args.download or args.build or args.rollback):
        args.check = True

    inspecter_gpu_vulkan()

    if args.check:
        print("▶️ [1/2] Inspection de stable-diffusion.cpp...")
        check_sd(DEFAULT_SD_DIR)
        print("▶️ [2/2] Inspection de llama.cpp...")
        check_llama(DEFAULT_LLAMA_DIR)
        sys.exit(0)

    if args.download:
        print("\n🚀 Téléchargement et mise à jour de la Suite Vulkan...")
        ok_sd = download_sd(DEFAULT_SD_DIR)
        ok_llama = download_llama(DEFAULT_LLAMA_DIR)
        if ok_sd and ok_llama:
            print("\n🎉 SUITE VULKAN ENTIÈREMENT MISE À JOUR AVEC SUCCÈS !\n")
            sys.exit(0)
        else:
            print("\n⚠️ Certains composants ont rencontré une erreur.\n")
            sys.exit(1)

    if args.build:
        print("\n⚙️ Compilation native complète de la Suite Vulkan...")
        print("\n▶️ [1/2] Compilation de stable-diffusion.cpp...")
        ok_sd = build_sd(
            source_dir=DEFAULT_SD_SRC,
            install_dir=DEFAULT_SD_DIR,
            clean=args.clean,
            parallel_jobs=args.jobs
        )
        print("\n▶️ [2/2] Compilation de llama.cpp...")
        ok_llama = build_llama(
            source_dir=DEFAULT_LLAMA_SRC,
            install_dir=DEFAULT_LLAMA_DIR,
            clean=args.clean,
            parallel_jobs=args.jobs
        )
        if ok_sd and ok_llama:
            print("\n🎉 TOUS LES MOTEURS VULKAN ONT ÉTÉ RECOMPILÉS AVEC SUCCÈS !\n")
            sys.exit(0)
        else:
            sys.exit(1)

    if args.rollback:
        print("\n⏪ Restauration des sauvegardes précédentes...")
        rollback_sd(DEFAULT_SD_DIR)
        rollback_llama(DEFAULT_LLAMA_DIR)
        sys.exit(0)


if __name__ == "__main__":
    main()
