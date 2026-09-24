#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gestionnaires de maintenance des moteurs (--update-sd / --update-llama / --update-vulkan)."""

import os
import sys


def gerer_maintenance_sd(args) -> None:
    """Traite --update-sd (check/download/build/rollback/list-backups)."""
    from pathlib import Path
    from scripts.update_sd_cpp import (
        action_compiler_vulkan,
        action_telecharger_release,
        action_verifier,
        lister_sauvegardes,
        restaurer_sauvegarde
    )
    install_dir = Path(args.sd_install_dir or os.getenv("SD_DIR", r"C:\SD"))
    source_dir = Path(args.sd_source_dir or os.getenv("SD_SOURCE_DIR", r"C:\GIT\stable-diffusion.cpp"))

    if args.update_sd == "check":
        action_verifier(install_dir)
    elif args.update_sd == "download":
        action_telecharger_release(install_dir)
    elif args.update_sd == "build":
        action_compiler_vulkan(source_dir=source_dir, install_dir=install_dir)
    elif args.update_sd == "rollback":
        restaurer_sauvegarde(install_dir)
    elif args.update_sd == "list-backups":
        backups = lister_sauvegardes(install_dir)
        print(f"\n📦 Sauvegardes trouvées dans {install_dir / 'backups'} :")
        if not backups:
            print("  (Aucune sauvegarde)")
        for b in backups:
            print(f"  • {b.name}")
    sys.exit(0)

def gerer_maintenance_llama(args) -> None:
    """Traite --update-llama (check/download/build/rollback/list-backups)."""
    from pathlib import Path
    from scripts.update_llama_cpp import (
        action_compiler_vulkan,
        action_telecharger_release,
        action_verifier,
        lister_sauvegardes,
        restaurer_sauvegarde
    )
    install_dir = Path(args.llama_install_dir or os.getenv("LLAMA_DIR", r"C:\llama.cpp"))
    source_dir = Path(args.llama_source_dir or os.getenv("LLAMA_SOURCE_DIR", r"C:\GIT\llama.cpp"))

    if args.update_llama == "check":
        action_verifier(install_dir)
    elif args.update_llama == "download":
        action_telecharger_release(install_dir)
    elif args.update_llama == "build":
        action_compiler_vulkan(source_dir=source_dir, install_dir=install_dir)
    elif args.update_llama == "rollback":
        restaurer_sauvegarde(install_dir)
    elif args.update_llama == "list-backups":
        backups = lister_sauvegardes(install_dir)
        print(f"\n📦 Sauvegardes trouvées dans {install_dir / 'backups'} :")
        if not backups:
            print("  (Aucune sauvegarde)")
        for b in backups:
            print(f"  • {b.name}")
    sys.exit(0)

def gerer_maintenance_vulkan(args) -> None:
    """Traite --update-vulkan/--update-all (check/download/build/rollback)."""
    import scripts.update_vulkan_stack as v_stack
    v_stack.inspecter_gpu_vulkan()
    mode = args.update_vulkan
    if mode == "check":
        print("▶️ [1/2] Inspection de stable-diffusion.cpp...")
        v_stack.check_sd(v_stack.DEFAULT_SD_DIR)
        print("▶️ [2/2] Inspection de llama.cpp...")
        v_stack.check_llama(v_stack.DEFAULT_LLAMA_DIR)
    elif mode == "download":
        print("\n🚀 Téléchargement et mise à jour de la Suite Vulkan...")
        v_stack.download_sd(v_stack.DEFAULT_SD_DIR)
        v_stack.download_llama(v_stack.DEFAULT_LLAMA_DIR)
    elif mode == "build":
        print("\n⚙️ Compilation native complète de la Suite Vulkan...")
        v_stack.build_sd(v_stack.DEFAULT_SD_SRC, v_stack.DEFAULT_SD_DIR)
        v_stack.build_llama(v_stack.DEFAULT_LLAMA_SRC, v_stack.DEFAULT_LLAMA_DIR)
    elif mode == "rollback":
        v_stack.rollback_sd(v_stack.DEFAULT_SD_DIR)
        v_stack.rollback_llama(v_stack.DEFAULT_LLAMA_DIR)
    sys.exit(0)
