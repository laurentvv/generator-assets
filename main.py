#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generator Assets - Pipeline & Workflows Modulaires d'Assets 2D & 3D pour Godot Engine.
Combine Flux.1 Dev (Vulkan), LoRAs, Upscalers IA (ESRGAN), LLM local (llama.cpp),
Matériaux PBR 3D, Skyboxes 360, Fiches de modélisation et Génération de Mesh .glb via Blender.
100% Ligne de Commande Locale (CLI) • Zéro Gradio • Léger et Rapide.
"""

import os
import sys

# Console Windows : force l'UTF-8 pour les emojis/accents
for flux in (sys.stdout, sys.stderr):
    if hasattr(flux, "reconfigure"):
        flux.reconfigure(encoding="utf-8", errors="replace")





# ==============================================================================
# Mode Interactif

# Imports différés vers les sous-modules CLI (ré-exportés pour compat :
# tests/test_cli_contract.py et consommateurs utilisent main.construire_parseur).
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
from workflows import WorkflowRegistry


def main():
    """Point d'entrée CLI."""
    parser = construire_parseur()
    args = parser.parse_args()

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
        print("\n📋 Workflows Disponibles (2D & 3D) dans Generator Assets :")
        for nom, desc in WorkflowRegistry.list_all().items():
            print(f"  • {nom.ljust(16)} : {desc}")
        print()
        sys.exit(0)

    if args.list_loras:
        loras = lister_loras()
        print("\n🧩 LoRAs Installés :")
        if not loras:
            print(f"  (Aucun LoRA détecté dans {[d for d in DEFAULT_LORA_DIRS if os.path.exists(d)]})")
            print("  💡 Placez vos fichiers .safetensors dans 'C:\\Modeles_LLM\\loras' ou le dossier 'loras/'")
        else:
            for l in loras:
                print(f"  • {l['name'].ljust(30)} ({l['size_mb']} Mo) -> {l['path']}")
        print()
        sys.exit(0)

    if args.list_upscalers:
        upscalers = lister_upscalers()
        print("\n🚀 Modèles d'Upscaling (ESRGAN / Super-Résolution) Installés :")
        if not upscalers:
            print("  (Aucun modèle d'upscale détecté)")
            print("  💡 Placez vos fichiers .pth dans 'C:\\Modeles_LLM\\upscalers' ou le dossier 'upscalers/'")
        else:
            for u in upscalers:
                print(f"  • {u['name'].ljust(35)} ({u['size_mb']} Mo) -> {u['path']}")
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
        print("🔍 Vérification des prérequis et des chemins...")
        valide = verifier_prerequis(config)
        if valide:
            print("✅ Tous les exécutables et fichiers modèles sont prêts !")
        sys.exit(0 if valide else 1)

    prompt_texte = args.prompt_flag or args.prompt

    # Lancement du mode interactif si demandé explicitement ou si aucun paramètre fourni
    a_des_entrees = bool(prompt_texte or args.input_file or args.recipe_file or args.biome_a)
    if args.interactive or (not a_des_entrees and args.workflow == "generate"):
        lancer_mode_interactif(config)
        return

    params = construire_params(args, prompt_texte)

    # Détection automatique du workflow si l'argument -w n'est pas spécifié
    wf_cible = args.workflow.lower()
    if wf_cible == "generate" and args.recipe_file:
        wf_cible = "batch"

    try:
        workflow_cls = WorkflowRegistry.get(wf_cible)
        workflow_instance = workflow_cls(config)
        resultat = workflow_instance.run(params)
        if wf_cible == "batch" and isinstance(resultat, dict) and resultat.get("echecs"):
            print(f"❌ Batch terminé avec {len(resultat['echecs'])} asset(s) en échec sur {resultat.get('total_tasks')} :")
            for echec in resultat["echecs"]:
                print(f"   • '{echec['prompt']}' (workflow {echec['workflow']}) : {echec['erreur']}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Erreur lors de l'exécution du workflow '{wf_cible}' : {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
