#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Construction du parseur d'arguments CLI et des paramètres workflows."""

import argparse
from workflows.base import WorkflowRegistry
from core.config import (
    DEFAULT_BACKEND,
    DEFAULT_CLIP_L,
    DEFAULT_LLAMA_CLI,
    DEFAULT_LLM_MODEL,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SD_CLI,
    DEFAULT_SD_MODEL,
    DEFAULT_STYLE_ANCHOR,
    DEFAULT_T5XXL,
    DEFAULT_THREADS,
    DEFAULT_VAE,
)

# ==============================================================================
def construire_parseur() -> argparse.ArgumentParser:
    """Construit le parseur d'arguments CLI (extrait de main pour testabilité du contrat consommateurs)."""
    parser = argparse.ArgumentParser(
        prog="generator-assets",
        description="⚔️ Système de Workflows IA pour Assets 2D & 3D Godot (Flux.1 Vulkan + LoRAs + PBR Materials + Blender Mesh GLB + Upscale ESRGAN).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples de Workflows 3D & 2D :
  # 1. Modèle 3D Maillé PBR via Blender (Cube, Dalle, Pilier, Sphère, Card)
  python main.py -w mesh3d "coffre ancien orné de runes en acier sombre" --shape cube
  python main.py -w mesh3d -i godot_assets/casque.png --shape card -o casque_3d

  # 1b. Objet 3D IA volumique depuis une image ou un prompt (TRELLIS.2 GGUF, Vulkan)
  python main.py -w mesh_ia -i godot_assets/casque.png --res 512
  python main.py -w mesh_ia "crâne de dragon sculpté dans l'obsidienne" --res 1024

  # 2. Pack Matériau 3D PBR complet (Albedo, Normal, Roughness, ORM, Height + .tres Godot)
  python main.py -w material3d "dalles de pierre sombre avec runes violettes et mousse" -s 1024

  # 3. Skybox 360° Équirectangulaire pour éclairage 3D & Ciel
  python main.py -w skybox "ciel nocturne dark fantasy avec nébuleuse violette et lunes"

  # 4. Planche de modélisation 3D pour Blender (Face + Profil calibrés)
  python main.py -w turnaround3d "chevalier de l'ombre en armure complète"

  # 5. Upscaling IA d'une texture en 4K avec modèle ESRGAN
  python main.py -w upscale -i godot_assets/casque.png --upscale-model anime --factor 4

  # Diagnostics
  python main.py --list-workflows
  python main.py --list-upscalers
  python main.py --list-loras
  python main.py --check
  python main.py --interactive
        """
    )

    # Paramètres principaux
    parser.add_argument(
        "prompt",
        nargs="?",
        default=None,
        help="Concept ou description textuelle de l'asset."
    )
    parser.add_argument(
        "-w", "--workflow",
        default="generate",
        help="Nom du workflow : generate, mesh3d, mesh_ia, material3d, skybox, turnaround3d, upscale, spritesheet, variations, tileable, pixelart, batch."
    )
    parser.add_argument(
        "-p", "--prompt",
        dest="prompt_flag",
        help="Description alternative via flag."
    )
    parser.add_argument(
        "-i", "--input",
        dest="input",
        help="Chemin de l'image source pour mesh3d, upscale, material3d, pixelart ou variations."
    )
    parser.add_argument(
        "-t", "--type",
        choices=["item", "character", "prop", "tile", "1", "2", "3"],
        default="item",
        help="Type d'asset : item (défaut), character, prop, tile."
    )
    parser.add_argument(
        "--shape",
        choices=["tile", "cube", "pillar", "cylinder", "sphere", "card", "cutout"],
        default="tile",
        help="Forme géométrique 3D pour le workflow mesh3d (défaut: 'tile')."
    )
    parser.add_argument(
        "-o", "--output",
        help="Nom du fichier de sortie sans extension."
    )
    parser.add_argument(
        "-d", "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Dossier de destination pour les assets Godot (défaut: '{DEFAULT_OUTPUT_DIR}')."
    )
    parser.add_argument(
        "-s", "--size",
        type=int,
        default=None,
        help="Résolution carrée finale en pixels."
    )

    # Gestion des LoRAs et Upscalers
    groupe_ia_ext = parser.add_argument_group("LoRAs & Upscalers")
    groupe_ia_ext.add_argument(
        "-l", "--lora",
        action="append",
        dest="loras",
        help="Applique un LoRA sous la forme 'nom:poids' (ex: -l 'pixel_art:0.8'). Répétable."
    )
    groupe_ia_ext.add_argument(
        "--lora-dir",
        help="Dossier contenant les fichiers de LoRAs (.safetensors)."
    )
    groupe_ia_ext.add_argument(
        "--upscale-model",
        help="Nom ou chemin du modèle d'upscaling ESRGAN (ex: 'anime', 'ultrasharp', '4x-UltraSharp.pth')."
    )
    groupe_ia_ext.add_argument(
        "--upscale",
        action="store_true",
        help="Active l'upscaling IA automatique (ESRGAN 4x ou Lanczos) après la génération."
    )

    # Paramètres spécifiques aux workflows
    groupe_wf = parser.add_argument_group("Options des Workflows Avancés")
    groupe_wf.add_argument("--factor", type=float, default=None, help="Facteur d'agrandissement pour l'upscale ou l'interpolation (ex: 2.0, 4.0 ; défaut : propre au workflow — 2.0, ou 4.0 quand l'upscale IA est actif pour generate).")
    groupe_wf.add_argument("--normal-strength", type=float, default=3.5, help="Intensité du relief pour la Normal Map PBR (défaut: 3.5).")
    groupe_wf.add_argument("--pbr-engine", default="auto", choices=["auto", "deep", "sobel"], help="Moteur d'estimation PBR (deep = DeepBump ONNX, sobel = filtres 2D).")
    groupe_wf.add_argument("--segmenter", default="auto", choices=["auto", "birefnet", "rmbg", "floodfill", "none"], help="Moteur de détourage 2D.")
    groupe_wf.add_argument("--palette", default="pico8", choices=["pico8", "gameboy", "endesga32"], help="Palette pour le workflow pixelart.")
    groupe_wf.add_argument("--grid-size", type=int, default=64, help="Taille de grille pour le pixel art (ex: 32, 64).")
    groupe_wf.add_argument("--query", help="Mots-clés de recherche Blendkit (workflow asset_blendkit) — ex: 'wooden barrel'.")
    groupe_wf.add_argument("--asset-type", dest="asset_type", choices=["model", "scene", "material"], default="model", help="Type d'asset Blendkit pour asset_blendkit (défaut: model ; mode plate utilise scene).")
    groupe_wf.add_argument("--licence", choices=["cc_zero", "any"], default="cc_zero", help="Filtre de licence Blendkit (défaut: cc_zero — recommandé jeu + monétisation).")
    groupe_wf.add_argument("--index", type=int, default=0, help="Index du résultat Blendkit à télécharger (voir --list-assets ; défaut: 0).")
    groupe_wf.add_argument("--list-assets", dest="list_assets", action="store_true", help="asset_blendkit : affiche les résultats de recherche puis s'arrête.")
    groupe_wf.add_argument("--mode", choices=["prop", "plate"], default="prop", help="asset_blendkit : prop = .glb Godot + aperçu Workbench | plate = rendu décor Cycles/EEVEE pour la chaîne (défaut: prop).")
    groupe_wf.add_argument("--resolution", choices=["blend", "8K", "4K", "2K", "1K", "0.5K"], default="2K", help="asset_blendkit mode prop : variante de textures du .blend (défaut: 2K, léger pour le jeu ; blend = qualité max).")
    groupe_wf.add_argument("--engine", choices=["cycles", "eevee"], default="cycles", help="asset_blendkit mode plate : moteur de rendu (défaut: cycles, GPU HIP — EEVEE sature certaines scènes, MEMORY_BANK 1.23).")
    groupe_wf.add_argument("--camera", default=None, help="asset_blendkit mode plate : nom de la caméra de la scène à utiliser (défaut: caméra de la scène).")
    groupe_wf.add_argument("--exposure", type=float, default=-1.0, help="asset_blendkit mode plate : exposition du rendu (défaut: -1.0, look officiel des scènes néon).")
    groupe_wf.add_argument("--percentage", type=int, default=100, help="asset_blendkit mode plate : pourcentage de résolution Blender (défaut: 100 ; les fichiers scène imposent parfois 300 = 6K, à maîtriser).")
    groupe_wf.add_argument("--no-cache", dest="no_cache", action="store_true", help="asset_blendkit : force le retéléchargement du .blend (défaut: cache local).")
    groupe_wf.add_argument("--themes", help="Liste des thèmes séparés par des virgules pour le workflow variations.")
    groupe_wf.add_argument("--file", "--recipe", dest="file", help="Fichier JSON ou liste texte pour le workflow batch.")
    groupe_wf.add_argument("--continue-on-error", dest="continue_on_error", action="store_true", help="batch : continue le lot après l'échec d'un asset et sort en code ≠ 0 à la fin avec la liste des échecs (défaut : arrêt à la première erreur, code ≠ 0).")
    groupe_wf.add_argument("--columns", type=int, default=4, help="Nombre de colonnes pour la planche de sprites.")
    groupe_wf.add_argument("--no-preview", action="store_true", help="Désactive l'aperçu 3x3 pour le workflow tileable.")
    groupe_wf.add_argument("--angle", type=float, default=90.0, help="Angle de direction en degrés pour le workflow flowmap (défaut: 90 = bas).")
    groupe_wf.add_argument("--flow-type", default="river", choices=["river", "vortex", "radial", "optical"], help="Type de flux pour le workflow flowmap.")
    groupe_wf.add_argument("--turbulence", type=float, default=0.35, help="Intensité des tourbillons/méandres pour flowmap (défaut: 0.35).")
    groupe_wf.add_argument("--margin", type=int, default=32, help="Taille de marge fixe en pixels pour le workflow ui_9slice.")
    groupe_wf.add_argument("--auto-margin", action="store_true", help="Détection automatique des marges de tranches pour ui_9slice.")
    groupe_wf.add_argument("--voxel-depth", type=int, default=4, help="Épaisseur en voxels pour l'extrusion 3D (workflow voxel3d).")
    groupe_wf.add_argument("--voxel-scale", type=float, default=0.05, help="Taille d'un voxel en unités Godot (workflow voxel3d).")
    groupe_wf.add_argument("--biome-a", help="Description ou image du premier biome pour autotile_pack.")
    groupe_wf.add_argument("--biome-b", help="Description ou image du second biome pour autotile_pack.")
    groupe_wf.add_argument("--frames", type=int, default=None, help="Nombre de trames d'animation (video, vfx_flipbook, rife_interp, anim_loop, h3_ref2va ; défaut : propre au workflow — ex. 33 pour video, 22 pour h3_ref2va, 16 pour anim_loop).")
    groupe_wf.add_argument("--vfx-type", default="explosion", choices=["explosion", "fire", "lightning", "portal", "slash", "aura"], help="Type d'effet pour vfx_flipbook.")
    groupe_wf.add_argument("--emotions", default="neutral,happy,angry,sad,hurt", help="Liste des émotions séparées par des virgules pour rpg_portrait et tts_dialogue.")
    groupe_wf.add_argument("--mode-2d", action="store_true", help="Génère un shader ou setup orienté Godot 2D au lieu de 3D.")
    groupe_wf.add_argument("--pose", choices=["idle", "slash_attack", "cast_spell", "shield_block", "jump", "walk"], default="idle", help="Pose OpenPose pour pose_control.")
    groupe_wf.add_argument("--fps", type=float, default=None, help="Cadence FPS pour anim_loop (défaut workflow : 12.0) et video (défaut workflow : 24).")
    groupe_wf.add_argument("--items", help="Liste d'assets cohérents pour le workflow ip_adapter (ex: 'sword,shield,potion,helmet').")
    groupe_wf.add_argument("--samples", type=int, default=48, help="Nombre d'échantillons de rendu Cycles pour Blender (défaut: 48).")
    groupe_wf.add_argument("--width", type=int, default=None, help="Largeur personnalisée en pixels (skybox : panoramique 2:1, video).")
    groupe_wf.add_argument("--height", type=int, default=None, help="Hauteur personnalisée en pixels (skybox : panoramique 2:1, video).")
    # Options déclarées par les workflows eux-mêmes (audit §2.2 keystone) : chaque
    # classe expose PARAMETRES (cf. workflows/base.py) ; la table plate ci-dessus
    # est migrée famille par famille vers ces déclarations. Surface CLI agrégée
    # inchangée (contrat consommateurs).
    groupe_declares = parser.add_argument_group("Options par Workflow (déclarées par les workflows)")
    for declaration in WorkflowRegistry.parametres_declares():
        d = dict(declaration)
        flags = d.pop("flags")
        groupe_declares.add_argument(*flags, **d)

    # Paramètres généraux de rendu
    groupe_ia = parser.add_argument_group("Paramètres IA & Rendu")
    groupe_ia.add_argument("--use-llm", action="store_true", default=False, help="Active l'enrichissement par LLM local (désactivé par défaut).")
    groupe_ia.add_argument("--no-llm", action="store_true", default=False, help="Désactive l'enrichissement par LLM (comportement par défaut).")
    groupe_ia.add_argument("--strength", type=float, default=0.55, help="Force de débruitage Img2Img (défaut: 0.55).")
    groupe_ia.add_argument("--steps", type=int, default=25, help="Nombre d'étapes de diffusion Flux (défaut: 25).")
    groupe_ia.add_argument("--guidance", type=float, default=3.5, help="Guidance Flux (défaut: 3.5).")
    groupe_ia.add_argument("--cfg-scale", type=float, default=1.0, help="CFG scale (défaut: 1.0).")
    groupe_ia.add_argument("--seed", type=int, default=-1, help="Graine aléatoire (-1 pour aléatoire).")
    groupe_ia.add_argument("--tolerance", type=int, default=60, help="Tolérance de détourage flood-fill (défaut: 60).")
    groupe_ia.add_argument("--style", default=DEFAULT_STYLE_ANCHOR, help="Charte visuelle personnalisée.")

    # Modes utilitaires
    parser.add_argument("--interactive", action="store_true", help="Lance la session interactive.")
    parser.add_argument("--verbose", action="store_true", help="Journalisation détaillée (DEBUG) : commandes moteurs, tracebacks complets.")
    parser.add_argument("--check", action="store_true", help="Vérifie la présence des exécutables et des modèles.")
    parser.add_argument("--list-workflows", action="store_true", help="Affiche la liste des workflows disponibles.")
    parser.add_argument("--list-loras", action="store_true", help="Affiche la liste des LoRAs installés.")
    parser.add_argument("--list-upscalers", action="store_true", help="Affiche la liste des modèles d'upscaling installés.")
    parser.add_argument(
        "--update-sd",
        nargs="?",
        const="check",
        choices=["check", "download", "build", "rollback", "list-backups"],
        help="Gère la mise à jour et compilation Vulkan de stable-diffusion.cpp (check, download, build, rollback, list-backups)."
    )
    parser.add_argument("--sd-install-dir", help="Dossier d'installation de stable-diffusion.cpp (défaut: C:\\SD).")
    parser.add_argument("--sd-source-dir", help="Dossier source git pour la compilation Vulkan (défaut: C:\\GIT\\stable-diffusion.cpp).")
    parser.add_argument(
        "--update-llama",
        nargs="?",
        const="check",
        choices=["check", "download", "build", "rollback", "list-backups"],
        help="Gère la mise à jour et compilation Vulkan de llama.cpp (check, download, build, rollback, list-backups)."
    )
    parser.add_argument("--llama-install-dir", help="Dossier d'installation de llama.cpp (défaut: C:\\llama.cpp).")
    parser.add_argument("--llama-source-dir", help="Dossier source git pour la compilation Vulkan (défaut: C:\\GIT\\llama.cpp).")
    parser.add_argument(
        "--update-vulkan",
        "--update-all",
        dest="update_vulkan",
        nargs="?",
        const="check",
        choices=["check", "download", "build", "rollback"],
        help="Gère la mise à jour complète de toute la Suite IA Vulkan (stable-diffusion.cpp + llama.cpp)."
    )

    # Chemins
    groupe_chemins = parser.add_argument_group("Chemins & Exécutables")
    groupe_chemins.add_argument("--llama-cli", default=DEFAULT_LLAMA_CLI, help="Chemin vers llama-cli.exe")
    groupe_chemins.add_argument("--llm-model", default=DEFAULT_LLM_MODEL, help="Chemin vers le modèle LLM GGUF")
    groupe_chemins.add_argument("--sd-cli", default=DEFAULT_SD_CLI, help="Chemin vers sd-cli.exe")
    groupe_chemins.add_argument("--sd-model", default=DEFAULT_SD_MODEL, help="Chemin vers flux1-dev GGUF")
    groupe_chemins.add_argument("--clip-l", default=DEFAULT_CLIP_L, help="Chemin vers clip_l.safetensors")
    groupe_chemins.add_argument("--t5xxl", default=DEFAULT_T5XXL, help="Chemin vers t5xxl_fp16.safetensors")
    groupe_chemins.add_argument("--vae", default=DEFAULT_VAE, help="Chemin vers ae.safetensors")
    groupe_chemins.add_argument("--backend", default=DEFAULT_BACKEND, help="Backend sd-cli")
    groupe_chemins.add_argument("--threads", type=int, default=DEFAULT_THREADS, help="Threads CPU pour encoders")

    return parser


def surface_cli(parseur: argparse.ArgumentParser) -> list:
    """Signature stable de la surface argparse (gel du contrat consommateurs).

    Une entrée par option : flags triés, dest, classe d'action, défaut, choices
    triés, nargs, nom du type. Le help est volontairement exclu (cosmétique).
    Alimente le test de gel tests/test_cli_contract.py : toute dérive de dest,
    de défaut ou de type casse le contrat des dépôts consommateurs
    (ai-doc2video, video-analys-ia) sans que le test anti-doublon ne le voie.
    """
    entrees = []
    for action in parseur._actions:
        entrees.append([
            sorted(action.option_strings),
            action.dest,
            type(action).__name__,
            repr(action.default),
            sorted(action.choices) if action.choices is not None else None,
            action.nargs,
            getattr(action.type, "__name__", None) if action.type is not None else None,
        ])
    entrees.sort(key=lambda e: (e[1], e[0]))
    return entrees


def construire_params(args: argparse.Namespace, prompt_texte: str) -> dict:
    """Construit les paramètres du workflow depuis les arguments CLI.

    Générique : part de vars(args) (dest argparse == clé params) et ne transmet
    que les clés réellement renseignées (non None) — quand une option n'est pas
    passée, chaque workflow applique son propre défaut (contrat consommateurs,
    cf. tests/test_cli_contract.py). Les rares clés dérivées (type normalisé,
    LLM, preview, portrait) sont gérées explicitement ci-dessous ; les clés de
    contrôle CLI (chemins moteurs, flags list/check/update-*) n'y entrent jamais.
    """
    params = vars(args).copy()

    for cle in (
        "workflow", "prompt_flag", "interactive", "check", "verbose", "list_workflows",
        "list_loras", "list_upscalers",
        "update_sd", "sd_install_dir", "sd_source_dir",
        "update_llama", "llama_install_dir", "llama_source_dir",
        "update_vulkan",
        "llama_cli", "llm_model", "sd_cli", "sd_model", "clip_l", "t5xxl",
        "vae", "backend", "threads", "style", "no_preview",
    ):
        params.pop(cle, None)

    params["prompt"] = prompt_texte
    params["type"] = {"1": "item", "2": "character", "3": "prop"}.get(args.type, args.type)
    params["preview"] = not args.no_preview
    params["no_llm"] = True if args.no_llm else not args.use_llm
    params["use_llm"] = args.use_llm and not args.no_llm
    params["sans_llm"] = True if args.no_llm else not args.use_llm
    params["portrait"] = args.portrait or args.input

    return {cle: valeur for cle, valeur in params.items() if valeur is not None}

