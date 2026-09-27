#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generator Assets - Modular 2D & 3D Asset Pipeline & Workflows for the Godot Engine.
Combines Flux.1 Dev (Vulkan), LoRAs, AI Upscalers (ESRGAN), local LLM (llama.cpp),
3D PBR materials, 360 skyboxes, modeling sheets and .glb mesh generation via Blender.
100% Local Command Line (CLI) • Zero Gradio • Light and Fast.
"""

import logging
import os
import sys

# Windows console: force UTF-8 for emojis/accents
for flux in (sys.stdout, sys.stderr):
    if hasattr(flux, "reconfigure"):
        flux.reconfigure(encoding="utf-8", errors="replace")





# ==============================================================================
# Interactive Mode

# Deferred imports to the CLI submodules (re-exported for compatibility:
# tests/test_cli_contract.py and consumers use main.construire_parseur).
from cli.interactive import lancer_mode_interactif
from cli.maintenance import gerer_maintenance_llama, gerer_maintenance_sd, gerer_maintenance_vulkan
from cli.parser import construire_parseur, construire_params
from core.config import (
    DEFAULT_ESRGAN_MODEL,
    DEFAULT_LORA_DIRS,
    lister_loras,
    lister_upscalers,
    resoudre_sd_model,
    verifier_prerequis,
)
from core.journal import configurer_journal
from workflows import WorkflowRegistry


def main():
    """CLI entry point."""
    parser = construire_parseur()
    args = parser.parse_args()

    # Structured logging (stderr): INFO by default, DEBUG with --verbose.
    configurer_journal("DEBUG" if args.verbose else "INFO")
    logger = logging.getLogger(__name__)

    config = {
        "llama_cli": args.llama_cli,
        "llm_model": args.llm_model,
        "sd_cli": args.sd_cli,
        "sd_model": resoudre_sd_model(args.sd_model),
        "clip_l": args.clip_l,
        "t5xxl": args.t5xxl,
        "vae": args.vae,
        "esrgan_model": args.upscale_model or DEFAULT_ESRGAN_MODEL,
        "lora_dir": args.lora_dir or DEFAULT_LORA_DIRS[0],
        "backend": args.backend,
        "threads": args.threads,
        "style_anchor": args.style,
        "output_dir": args.output_dir
    }

    if args.list_workflows:
        print("\n📋 Available Workflows (2D & 3D) in Generator Assets:")
        for nom, desc in WorkflowRegistry.list_all().items():
            print(f"  • {nom.ljust(16)} : {desc}")
        print()
        sys.exit(0)

    if args.list_loras:
        loras = lister_loras()
        print("\n🧩 Installed LoRAs:")
        if not loras:
            print(f"  (No LoRA detected in {[d for d in DEFAULT_LORA_DIRS if os.path.exists(d)]})")
            print("  💡 Put your .safetensors files in 'C:\\Modeles_LLM\\loras' or the 'loras/' folder")
        else:
            for lora in loras:
                print(f"  • {lora['name'].ljust(30)} ({lora['size_mb']} MB) -> {lora['path']}")
        print()
        sys.exit(0)

    if args.list_upscalers:
        upscalers = lister_upscalers()
        print("\n🚀 Installed Upscaling Models (ESRGAN / Super-Resolution):")
        if not upscalers:
            print("  (No upscale model detected)")
            print("  💡 Put your .pth files in 'C:\\Modeles_LLM\\upscalers' or the 'upscalers/' folder")
        else:
            for u in upscalers:
                print(f"  • {u['name'].ljust(35)} ({u['size_mb']} MB) -> {u['path']}")
        print()
        sys.exit(0)
    if args.update_sd:
        gerer_maintenance_sd(args)
        sys.exit(0)

    if args.update_llama:
        gerer_maintenance_llama(args)
        sys.exit(0)

    if args.update_vulkan:
        gerer_maintenance_vulkan(args)
        sys.exit(0)

    if args.check:
        print("🔍 Checking prerequisites and paths...")
        valide = verifier_prerequis(config)
        if valide:
            print("✅ All executables and model files are ready!")
        sys.exit(0 if valide else 1)

    prompt_texte = args.prompt_flag or args.prompt

    # Launch interactive mode if explicitly requested or if no parameter was provided
    a_des_entrees = bool(prompt_texte or args.input or args.file or args.biome_a)
    if args.interactive or (not a_des_entrees and args.workflow == "generate"):
        lancer_mode_interactif(config)
        return

    params = construire_params(args, prompt_texte)

    # Automatic workflow detection if the -w argument is not specified
    wf_cible = args.workflow.lower()
    if wf_cible == "generate" and args.file:
        wf_cible = "batch"

    try:
        workflow_cls = WorkflowRegistry.get(wf_cible)
        workflow_instance = workflow_cls(config)
        resultat = workflow_instance.run(params)
        if wf_cible == "batch" and isinstance(resultat, dict) and resultat.get("echecs"):
            print(f"❌ Batch finished with {len(resultat['echecs'])} failed asset(s) out of {resultat.get('total_tasks')}:")
            for echec in resultat["echecs"]:
                print(f"   • '{echec['prompt']}' (workflow {echec['workflow']}): {echec['erreur']}")
            sys.exit(1)
    except Exception as e:
        # Full traceback available in DEBUG (--verbose); short message to the user.
        logger.debug("Full traceback of workflow '%s' failure:", wf_cible, exc_info=True)
        print(f"❌ Error while running workflow '{wf_cible}': {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
