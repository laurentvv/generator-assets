#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified manager of the Vulkan AI Suite for Generator Assets.
Supervises and automates Vulkan updates and compilation for:
  1. stable-diffusion.cpp (Image Engine, PBR Materials, and Wan/LTX/MiniMax Video)
  2. llama.cpp (Art Direction & Prompt Engineering LLM Engine)
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# UTF-8 support on Windows consoles (avoids cp1252 UnicodeEncodeError errors)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Import resolution regardless of the current working directory
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
    """Displays information about the system's Vulkan GPU and driver."""
    vulkaninfo_bin = shutil.which("vulkaninfo")
    sdk = detecter_vulkan_sdk()

    print("\n" + "=" * 70)
    print(" 🎮 SYSTEM VULKAN HARDWARE DIAGNOSTIC")
    print("=" * 70)
    print(f"  • Vulkan SDK installed: {sdk or '❌ Not detected'}")

    if vulkaninfo_bin:
        try:
            res = subprocess.run(
                ["vulkaninfo", "--summary"],
                capture_output=True,
                text=True,
                timeout=8
            )
            out = res.stdout or ""
            gpu_lines = [ligne.strip() for ligne in out.split("\n") if "deviceName" in ligne or "driverVersion" in ligne or "apiVersion" in ligne]
            for ligne in gpu_lines:
                print(f"  • {ligne}")
        except Exception:
            print("  • vulkaninfo available in System32")
    else:
        print("  • vulkaninfo not found in PATH")
    print("=" * 70 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Unified manager of the Vulkan AI Suite (stable-diffusion.cpp + llama.cpp)."
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Checks the state of the whole Vulkan suite (SD + LLaMA + GPU)."
    )
    parser.add_argument(
        "--download", action="store_true",
        help="Updates the whole Vulkan suite via the latest official GitHub releases."
    )
    parser.add_argument(
        "--build", action="store_true",
        help="Rebuilds both engines natively with Vulkan (CMake + MSVC)."
    )
    parser.add_argument(
        "--rollback", action="store_true",
        help="Restores the previous backup for both engines."
    )
    parser.add_argument(
        "--clean", action="store_true",
        help="Cleans the build folders before rebuilding."
    )
    parser.add_argument(
        "--jobs", "-j", type=int, default=None,
        help="Number of CPU cores for compilation."
    )

    args = parser.parse_args()

    # If no specific argument, run the full check
    if not (args.check or args.download or args.build or args.rollback):
        args.check = True

    inspecter_gpu_vulkan()

    if args.check:
        print("▶️ [1/2] Inspecting stable-diffusion.cpp...")
        check_sd(DEFAULT_SD_DIR)
        print("▶️ [2/2] Inspecting llama.cpp...")
        check_llama(DEFAULT_LLAMA_DIR)
        sys.exit(0)

    if args.download:
        print("\n🚀 Downloading and updating the Vulkan Suite...")
        ok_sd = download_sd(DEFAULT_SD_DIR)
        ok_llama = download_llama(DEFAULT_LLAMA_DIR)
        if ok_sd and ok_llama:
            print("\n🎉 ENTIRE VULKAN SUITE SUCCESSFULLY UPDATED!\n")
            sys.exit(0)
        else:
            print("\n⚠️ Some components hit an error.\n")
            sys.exit(1)

    if args.build:
        print("\n⚙️ Full native compilation of the Vulkan Suite...")
        print("\n▶️ [1/2] Compiling stable-diffusion.cpp...")
        ok_sd = build_sd(
            source_dir=DEFAULT_SD_SRC,
            install_dir=DEFAULT_SD_DIR,
            clean=args.clean,
            parallel_jobs=args.jobs
        )
        print("\n▶️ [2/2] Compiling llama.cpp...")
        ok_llama = build_llama(
            source_dir=DEFAULT_LLAMA_SRC,
            install_dir=DEFAULT_LLAMA_DIR,
            clean=args.clean,
            parallel_jobs=args.jobs
        )
        if ok_sd and ok_llama:
            print("\n🎉 ALL VULKAN ENGINES WERE REBUILT SUCCESSFULLY!\n")
            sys.exit(0)
        else:
            sys.exit(1)

    if args.rollback:
        print("\n⏪ Restoring previous backups...")
        rollback_sd(DEFAULT_SD_DIR)
        rollback_llama(DEFAULT_LLAMA_DIR)
        sys.exit(0)


if __name__ == "__main__":
    main()
