#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generator Assets - Pipeline & Workflows Modulaires d'Assets 2D & 3D pour Godot Engine.
Combine Flux.1 Dev (Vulkan), LoRAs, Upscalers IA (ESRGAN), LLM local (llama.cpp),
Matériaux PBR 3D, Skyboxes 360, Fiches de modélisation et Génération de Mesh .glb via Blender.
100% Ligne de Commande Locale (CLI) • Zéro Gradio • Léger et Rapide.
"""

import argparse
import os
import sys
from pathlib import Path

# Console Windows : force l'UTF-8 pour les emojis/accents
for flux in (sys.stdout, sys.stderr):
    if hasattr(flux, "reconfigure"):
        flux.reconfigure(encoding="utf-8", errors="replace")

from core.config import (
    DEFAULT_BACKEND,
    DEFAULT_CLIP_L,
    DEFAULT_ESRGAN_MODEL,
    DEFAULT_LLAMA_CLI,
    DEFAULT_LLM_MODEL,
    DEFAULT_LORA_DIRS,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SD_CLI,
    DEFAULT_SD_MODEL,
    DEFAULT_STYLE_ANCHOR,
    DEFAULT_T5XXL,
    DEFAULT_THREADS,
    DEFAULT_UPSCALER_DIRS,
    DEFAULT_VAE,
    lister_loras,
    lister_upscalers,
    resoudre_sd_model,
    resoudre_upscaler,
    slugifier_texte,
    verifier_prerequis
)
from workflows import (
    BaseWorkflow,
    WorkflowRegistry,
    GenerateWorkflow,
    UpscaleWorkflow,
    SpriteSheetWorkflow,
    VariationsWorkflow,
    TileableWorkflow,
    PixelArtWorkflow,
    BatchWorkflow,
    Material3DWorkflow,
    SkyboxWorkflow,
    Turnaround3DWorkflow,
    Mesh3DWorkflow
)


# ==============================================================================
# Mode Interactif
# ==============================================================================
def lancer_mode_interactif(config: dict):
    """Interface interactive en console permettant d'exécuter n'importe quel workflow."""
    print("\n" + "=" * 65)
    print(" ⚔️  Generator Assets - Console de Workflows 2D & 3D Godot ⚔️ ")
    print("=" * 65)
    
    verifier_prerequis(config)

    menu_workflows = {
        "1": ("generate", "🎨 Génération d'Asset 2D (Item, Monstre, Décor)"),
        "2": ("mesh3d", "🎲 Modèle 3D Maillé .GLB (Cube, Dalle, Pilier, Sphère, Card)"),
        "3": ("material3d", "🧱 Pack Matériau 3D PBR (Albedo, DeepBump Normal, Roughness, ORM, .tres)"),
        "4": ("skybox", "🌌 Skybox / Panorama 360° Équirectangulaire (.tres Environment)"),
        "5": ("turnaround3d", "📐 Fiche de Modélisation 3D (Vues orthogonales pour Blender)"),
        "6": ("upscale", "🔍 Upscale IA (ESRGAN Vulkan / Lanczos 2x, 4x, 4K)"),
        "7": ("spritesheet", "📊 Planche de Sprites multi-angles (Face, Profils, Dos + JSON)"),
        "8": ("variations", "🌈 Variantes Thématiques (Feu, Glace, Poison, etc.)"),
        "9": ("tileable", "🔲 Texture Raccordable Seamless (Tuile TileMap)"),
        "10": ("pixelart", "👾 Conversion Rétro Pixel Art (Pico-8, Endesga-32)"),
        "11": ("batch", "📦 Génération par Lot (Pack depuis fichier JSON)"),
        "12": ("rembg", "✂️ Détourage IA Haute Précision (RMBG-1.4 / BiRefNet)"),
        "13": ("flowmap", "🌊 Cartes de Flux Vectoriels & Shaders Godot (Eau / Lave)"),
        "14": ("ui_9slice", "🖼️ Cadres & Boutons 9-Patch Extensibles (.tres / .tscn)"),
        "15": ("voxel3d", "🧊 Modèle 3D Voxel (.GLB) pour GridMap Godot 4"),
        "16": ("autotile_pack", "🗺️ Planche Autotile 47 Tuiles Wang Minimal 3x3 (.tres)"),
        "17": ("rife_interp", "⚡ Super-Fluidité d'Animation 60 FPS (RIFE v4 ONNX)"),
        "18": ("vfx_flipbook", "💥 Planche de Particules VFX Flipbook 4x4 + GPUParticles"),
        "19": ("rpg_portrait", "🎭 Galerie de Dialogues RPG Multi-Émotions + JSON"),
        "20": ("sfx", "🔊 Synthèse d'Effets Sonores & Bruitages (.wav / .ogg)"),
        "21": ("ip_adapter", "🎨 Cohérence de Style & Charte Graphique (IP-Adapter)"),
        "22": ("anim_loop", "🔄 Boucles de Textures & Shaders Animés (Loop Engine)"),
        "23": ("pose_control", "🕺 Contrôle d'Armatures & Poses (ControlNet OpenPose)"),
        "24": ("tts_dialogue", "🎙️ Synthèse Vocale Émotionnelle & Lip-Sync Godot"),
        "25": ("audio_ambience", "🌌 Ambiances Sonores Immersives & Paysages Bouclables"),
        "26": ("makehuman_clothes", "👗 Garde-robe MakeHuman / MPFB (Torso, Pantalon, Chaussures) + Scène New Human .blend"),
        "27": ("video", "🎬 Génération Vidéo IA Native (.webm) via Wan 2.1 / LTX / MiniMax Vulkan"),
        "28": ("update_sd", "🔄 Gestionnaire de Mise à Jour & Compilation Vulkan (stable-diffusion.cpp)"),
        "29": ("update_llama", "🦙 Gestionnaire de Mise à Jour & Compilation Vulkan (llama.cpp)"),
        "30": ("update_vulkan", "⚡ Suite Complète IA Vulkan (SD + LLaMA + Diagnostic GPU)")
    }

    while True:
        try:
            print("\n--- Choisissez un Workflow ['q' pour quitter] ---")
            for k, (_, desc) in menu_workflows.items():
                print(f"  [{k.rjust(2)}] {desc}")

            choix = input("\n👉 Choix (1-30) [défaut: 1] : ").strip()
            if choix.lower() == 'q':
                print("👋 Au revoir !")
                break

            wf_name, _ = menu_workflows.get(choix, ("generate", ""))
            wf_cls = WorkflowRegistry.get(wf_name)
            wf_instance = wf_cls(config)

            params = {"output_dir": config.get("output_dir", DEFAULT_OUTPUT_DIR)}

            # Détection des LoRAs disponibles
            loras_dispos = lister_loras()
            if loras_dispos and wf_name in ["generate", "mesh3d", "material3d", "skybox", "turnaround3d", "spritesheet", "variations"]:
                print("\n🧩 LoRAs détectés :")
                for idx, l in enumerate(loras_dispos, 1):
                    print(f"   [{idx}] {l['name']} ({l['size_mb']} Mo)")
                choix_l = input("Appliquer des LoRAs ? (ex: '1:0.8, 2:1.0' ou laisser vide) : ").strip()
                if choix_l:
                    loras_choisis = []
                    for part in choix_l.split(","):
                        part = part.strip()
                        if ":" in part:
                            num, poids = part.split(":", 1)
                        else:
                            num, poids = part, "1.0"
                        if num.isdigit() and 1 <= int(num) <= len(loras_dispos):
                            nom_l = loras_dispos[int(num) - 1]["name"]
                            loras_choisis.append(f"{nom_l}:{poids.strip()}")
                    if loras_choisis:
                        params["loras"] = loras_choisis
                        # Si des LoRAs sont sélectionnés, basculer sur JuggernautXL (SDXL)
                        modele_jugg = resoudre_sd_model("juggernaut")
                        if modele_jugg and os.path.exists(modele_jugg):
                            self_sd = config.get("sd_model", "")
                            if "flux" in self_sd.lower():
                                config["sd_model"] = modele_jugg
                                print("   🚀 Bascule automatique sur SDXL Juggernaut pour la compatibilité avec vos LoRAs.")
                        print(f"   ➔ LoRAs activés : {', '.join(loras_choisis)}")

            if wf_name == "generate":
                concept = input("💡 Concept de l'asset : ").strip()
                if not concept:
                    continue
                type_a = input("📂 Type [1: Item, 2: Personnage, 3: Prop] (défaut: 1) : ").strip()
                type_map = {"1": "item", "2": "character", "3": "prop"}
                params["prompt"] = concept
                params["type"] = type_map.get(type_a, "item")
                params["output"] = input(f"💾 Nom du fichier [défaut: {slugifier_texte(concept)}] : ").strip()
                up = input("🔍 Activer l'upscaling IA 4K automatique (1024 -> 4096 px) ? (o/N) [défaut: N] : ").strip().lower()
                if up in ("o", "oui", "y", "yes"):
                    params["upscale"] = True
                    params["factor"] = 4.0

            elif wf_name == "mesh3d":
                chemin = input("🖼️  Texture ou asset 2D existant (ou laisser vide pour générer) : ").strip()
                if chemin and os.path.exists(chemin):
                    params["input"] = chemin
                else:
                    params["prompt"] = input("💡 Description de l'objet ou matériau 3D : ").strip()
                print("📐 Forme 3D : [1] Dalle/Sol (tile)  [2] Cube/Coffre (cube)  [3] Pilier (pillar)  [4] Sphère (sphere)  [5] 3D Sprite Card (card)")
                choix_s = input("Choix (1-5) [défaut: 1] : ").strip()
                s_map = {"1": "tile", "2": "cube", "3": "pillar", "4": "sphere", "5": "card"}
                params["shape"] = s_map.get(choix_s, "tile")

            elif wf_name == "material3d":
                chemin = input("🖼️  Texture existante (ou laisser vide pour générer à partir d'un prompt) : ").strip()
                if chemin and os.path.exists(chemin):
                    params["input"] = chemin
                else:
                    params["prompt"] = input("🧱 Description du matériau 3D (ex: pavés médiévaux avec mousse) : ").strip()
                params["size"] = int(input("📐 Résolution du matériau [512, 1024, 2048] (défaut: 1024) : ").strip() or 1024)

            elif wf_name == "skybox":
                params["prompt"] = input("🌌 Description du ciel 360° (ex: ciel d'orage dark fantasy avec nébuleuse violette) : ").strip()
                if not params["prompt"]:
                    continue

            elif wf_name == "turnaround3d":
                params["prompt"] = input("📐 Concept du personnage / monstre pour modélisation 3D : ").strip()
                if not params["prompt"]:
                    continue

            elif wf_name == "upscale":
                chemin = input("🖼️  Chemin de l'image source (ex: godot_assets/casque.png) : ").strip()
                if not os.path.exists(chemin):
                    print(f"❌ Fichier introuvable : {chemin}")
                    continue
                
                upscalers = lister_upscalers()
                if upscalers:
                    print("\n🚀 Modèles Upscalers IA disponibles :")
                    for idx, u in enumerate(upscalers, 1):
                        print(f"   [{idx}] {u['name']} ({u['size_mb']} Mo)")
                    choix_u = input("Choisir un modèle IA (numéro ou laisser vide pour par défaut) : ").strip()
                    if choix_u.isdigit() and 1 <= int(choix_u) <= len(upscalers):
                        params["upscale_model"] = upscalers[int(choix_u) - 1]["path"]

                facteur = input("🔍 Facteur d'agrandissement [2, 4] (défaut: 2) : ").strip() or "2"
                params["input"] = chemin
                params["factor"] = float(facteur)

            elif wf_name == "spritesheet":
                concept = input("💡 Concept du personnage/entité : ").strip()
                if not concept:
                    continue
                params["prompt"] = concept
                params["size"] = int(input("📐 Taille d'une cellule [défaut: 256] : ").strip() or 256)

            elif wf_name == "variations":
                chemin = input("🖼️  Image de base (ou laisser vide pour partir d'un texte) : ").strip()
                if chemin and os.path.exists(chemin):
                    params["input"] = chemin
                else:
                    params["prompt"] = input("💡 Concept de base : ").strip()
                themes = input("🎨 Thèmes séparés par des virgules (ex: feu,glace,foudre) : ").strip()
                if themes:
                    params["themes"] = themes

            elif wf_name == "tileable":
                concept = input("🧱 Type de sol / texture raccordable : ").strip()
                if not concept:
                    continue
                params["prompt"] = concept

            elif wf_name == "pixelart":
                chemin = input("🖼️  Image source à pixeliser (ou laisser vide pour générer) : ").strip()
                if chemin and os.path.exists(chemin):
                    params["input"] = chemin
                else:
                    params["prompt"] = input("💡 Concept à générer en pixel art : ").strip()
                pal = input("🎨 Palette [pico8, gameboy, endesga32] (défaut: pico8) : ").strip() or "pico8"
                params["palette"] = pal
                params["grid_size"] = int(input("🔲 Résolution de la grille pixel [32, 64] (défaut: 64) : ").strip() or 64)

            elif wf_name == "batch":
                fichier = input("📄 Chemin vers le fichier JSON de recette (ex: recipes/dark_fantasy_armory.json) : ").strip()
                if not os.path.exists(fichier):
                    print(f"❌ Fichier introuvable : {fichier}")
                    continue
                params["file"] = fichier

            elif wf_name == "ip_adapter":
                chemin = input("🖼️  Image de référence (ou laisser vide pour générer depuis un prompt) : ").strip()
                if chemin and os.path.exists(chemin):
                    params["input"] = chemin
                else:
                    params["prompt"] = input("💡 Concept de référence : ").strip()
                items = input("📦 Items cohérents séparés par des virgules (ex: sword,shield,potion,helmet) : ").strip()
                if items:
                    params["themes"] = items

            elif wf_name == "anim_loop":
                params["prompt"] = input("💡 Type de boucle VFX (ex: portal vortex, magic fire, waterfall) : ").strip() or "portal"
                print("🌀 Type d'effet : [1] Portail (portal)  [2] Flammes (fire)  [3] Cascade (waterfall)  [4] Nébuleuse (nebula)")
                choix_v = input("Choix (1-4) [défaut: 1] : ").strip()
                v_map = {"1": "portal", "2": "fire", "3": "waterfall", "4": "nebula"}
                params["vfx_type"] = v_map.get(choix_v, "portal")
                params["frames"] = int(input("🎞️  Nombre de trames [8, 16, 24] (défaut: 16) : ").strip() or 16)

            elif wf_name == "pose_control":
                params["prompt"] = input("💡 Concept du personnage : ").strip()
                print("🕺 Pose : [1] Stance (idle)  [2] Attaque (slash_attack)  [3] Sort (cast_spell)  [4] Bouclier (shield_block)  [5] Saut (jump)  [6] Course (walk)")
                choix_p = input("Choix (1-6) [défaut: 1] : ").strip()
                p_map = {"1": "idle", "2": "slash_attack", "3": "cast_spell", "4": "shield_block", "5": "jump", "6": "walk"}
                params["pose"] = p_map.get(choix_p, "idle")

            elif wf_name == "tts_dialogue":
                params["prompt"] = input("🎙️  Nom du personnage / Identifiant : ").strip() or "guerriere_sanctuaire"
                params["emotions"] = input("🎭 Émotions séparées par virgules (défaut: neutral,happy,angry,sad,hurt) : ").strip() or "neutral,happy,angry,sad,hurt"

            elif wf_name == "audio_ambience":
                params["prompt"] = input("🌌 Type d'ambiance (dungeon, forest, storm, space, campfire) : ").strip() or "dungeon"
                params["duration"] = float(input("⏱️  Durée en secondes (défaut: 8.0) : ").strip() or 8.0)

            elif wf_name == "video":
                params["prompt"] = input("🎬 Concept / Action de la vidéo (ex: cascade mystique dans jungle luxuriante) : ").strip()
                if not params["prompt"]:
                    continue
                img_init = input("🖼️  Image initiale pour Image-to-Video (ou laisser vide pour Text-to-Video) : ").strip()
                if img_init and os.path.exists(img_init):
                    params["input"] = img_init
                    img_fin = input("🖼️  Image finale (laisser vide pour I2V, spécifier pour FLF2V) : ").strip()
                    if img_fin and os.path.exists(img_fin):
                        params["end_img"] = img_fin
                params["frames"] = int(input("🎞️  Nombre de trames [17, 33, 49, 81] (défaut: 33) : ").strip() or 33)
                params["fps"] = int(input("⏱️  Cadence FPS (défaut: 24) : ").strip() or 24)
                nom_out = input("💾 Nom du fichier vidéo [défaut: auto] : ").strip()
                if nom_out:
                    params["output"] = nom_out

            elif wf_name == "update_sd":
                from pathlib import Path
                import scripts.update_sd_cpp as sd_up
                print("\n🔄 Gestionnaire stable-diffusion.cpp (Vulkan) :")
                print("   [1] Vérifier les versions (locale vs distante)")
                print("   [2] Télécharger la dernière release Vulkan officielle GitHub (Rapide)")
                print("   [3] Compiler nativement depuis les sources avec Vulkan (CMake + MSVC)")
                print("   [4] Restaurer une sauvegarde précédente")
                choix_sd = input("Choix (1-4) [défaut: 1] : ").strip() or "1"
                inst_dir = Path(config.get("sd_dir") or os.getenv("SD_DIR", r"C:\SD"))
                src_dir = Path(os.getenv("SD_SOURCE_DIR", r"C:\GIT\stable-diffusion.cpp"))
                if choix_sd == "1":
                    sd_up.action_verifier(inst_dir)
                elif choix_sd == "2":
                    sd_up.action_telecharger_release(inst_dir)
                elif choix_sd == "3":
                    sd_up.action_compiler_vulkan(source_dir=src_dir, install_dir=inst_dir)
                elif choix_sd == "4":
                    sd_up.restaurer_sauvegarde(inst_dir)
                continue

            elif wf_name == "update_llama":
                from pathlib import Path
                import scripts.update_llama_cpp as llama_up
                print("\n🦙 Gestionnaire llama.cpp (Vulkan) :")
                print("   [1] Vérifier les versions (locale vs distante)")
                print("   [2] Télécharger la dernière release Vulkan officielle GitHub (Rapide)")
                print("   [3] Compiler nativement depuis les sources avec Vulkan (CMake + MSVC)")
                print("   [4] Restaurer une sauvegarde précédente")
                choix_l = input("Choix (1-4) [défaut: 1] : ").strip() or "1"
                inst_dir = Path(config.get("llama_dir") or os.getenv("LLAMA_DIR", r"C:\llama.cpp"))
                src_dir = Path(os.getenv("LLAMA_SOURCE_DIR", r"C:\GIT\llama.cpp"))
                if choix_l == "1":
                    llama_up.action_verifier(inst_dir)
                elif choix_l == "2":
                    llama_up.action_telecharger_release(inst_dir)
                elif choix_l == "3":
                    llama_up.action_compiler_vulkan(source_dir=src_dir, install_dir=inst_dir)
                elif choix_l == "4":
                    llama_up.restaurer_sauvegarde(inst_dir)
                continue

            elif wf_name == "update_vulkan":
                import scripts.update_vulkan_stack as v_stack
                v_stack.inspecter_gpu_vulkan()
                print("   [1] Vérifier l'état de toute la suite IA Vulkan (SD + LLaMA)")
                print("   [2] Mettre à jour tous les moteurs (Releases officielles Vulkan)")
                print("   [3] Recompiler tous les moteurs nativement (CMake + MSVC + Vulkan)")
                print("   [4] Restaurer les sauvegardes précédentes")
                choix_v = input("Choix (1-4) [défaut: 1] : ").strip() or "1"
                if choix_v == "1":
                    v_stack.check_sd(v_stack.DEFAULT_SD_DIR)
                    v_stack.check_llama(v_stack.DEFAULT_LLAMA_DIR)
                elif choix_v == "2":
                    v_stack.download_sd(v_stack.DEFAULT_SD_DIR)
                    v_stack.download_llama(v_stack.DEFAULT_LLAMA_DIR)
                elif choix_v == "3":
                    v_stack.build_sd(v_stack.DEFAULT_SD_SRC, v_stack.DEFAULT_SD_DIR)
                    v_stack.build_llama(v_stack.DEFAULT_LLAMA_SRC, v_stack.DEFAULT_LLAMA_DIR)
                elif choix_v == "4":
                    v_stack.rollback_sd(v_stack.DEFAULT_SD_DIR)
                    v_stack.rollback_llama(v_stack.DEFAULT_LLAMA_DIR)
                continue

            wf_instance.run(params)

        except KeyboardInterrupt:
            print("\n👋 Arrêt demandé.")
            break
        except Exception as e:
            print(f"❌ Une erreur est survenue : {e}")


# ==============================================================================
# Point d'Entrée CLI
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(
        prog="generator-assets",
        description="⚔️ Système de Workflows IA pour Assets 2D & 3D Godot (Flux.1 Vulkan + LoRAs + PBR Materials + Blender Mesh GLB + Upscale ESRGAN).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples de Workflows 3D & 2D :
  # 1. Modèle 3D Maillé PBR via Blender (Cube, Dalle, Pilier, Sphère, Card)
  python main.py -w mesh3d "coffre ancien orné de runes en acier sombre" --shape cube
  python main.py -w mesh3d -i godot_assets/casque.png --shape card -o casque_3d

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
        help="Nom du workflow : generate, mesh3d, material3d, skybox, turnaround3d, upscale, spritesheet, variations, tileable, pixelart, batch."
    )
    parser.add_argument(
        "-p", "--prompt",
        dest="prompt_flag",
        help="Description alternative via flag."
    )
    parser.add_argument(
        "-i", "--input",
        dest="input_file",
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
    groupe_wf.add_argument("--factor", type=float, default=2.0, help="Facteur d'agrandissement pour l'upscale ou l'interpolation (ex: 2.0, 4.0).")
    groupe_wf.add_argument("--normal-strength", type=float, default=3.5, help="Intensité du relief pour la Normal Map PBR (défaut: 3.5).")
    groupe_wf.add_argument("--pbr-engine", default="auto", choices=["auto", "deep", "sobel"], help="Moteur d'estimation PBR (deep = DeepBump ONNX, sobel = filtres 2D).")
    groupe_wf.add_argument("--segmenter", default="auto", choices=["auto", "birefnet", "rmbg", "floodfill", "none"], help="Moteur de détourage 2D.")
    groupe_wf.add_argument("--palette", default="pico8", choices=["pico8", "gameboy", "endesga32"], help="Palette pour le workflow pixelart.")
    groupe_wf.add_argument("--grid-size", type=int, default=64, help="Taille de grille pour le pixel art (ex: 32, 64).")
    groupe_wf.add_argument("--themes", help="Liste des thèmes séparés par des virgules pour le workflow variations.")
    groupe_wf.add_argument("--file", "--recipe", dest="recipe_file", help="Fichier JSON ou liste texte pour le workflow batch.")
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
    groupe_wf.add_argument("--frames", type=int, default=16, help="Nombre de trames d'animation (vfx_flipbook, rife_interp).")
    groupe_wf.add_argument("--vfx-type", default="explosion", choices=["explosion", "fire", "lightning", "portal", "slash", "aura"], help="Type d'effet pour vfx_flipbook.")
    groupe_wf.add_argument("--emotions", default="neutral,happy,angry,sad,hurt", help="Liste des émotions séparées par des virgules pour rpg_portrait et tts_dialogue.")
    groupe_wf.add_argument("--duration", type=float, default=2.0, help="Durée en secondes pour sfx ou audio_ambience.")
    groupe_wf.add_argument("--mode-2d", action="store_true", help="Génère un shader ou setup orienté Godot 2D au lieu de 3D.")
    groupe_wf.add_argument("--pose", choices=["idle", "slash_attack", "cast_spell", "shield_block", "jump", "walk"], default="idle", help="Pose OpenPose pour pose_control.")
    groupe_wf.add_argument("--pitch", type=float, default=160.0, help="Pitch vocal fondamental pour tts_dialogue (défaut: 160Hz).")
    groupe_wf.add_argument("--fps", type=float, default=12.0, help="Cadence FPS pour anim_loop (défaut: 12.0).")
    groupe_wf.add_argument("--items", help="Liste d'assets cohérents pour le workflow ip_adapter (ex: 'sword,shield,potion,helmet').")
    groupe_wf.add_argument("--ambience-type", choices=["dungeon", "forest", "storm", "space", "campfire", "tavern"], help="Type d'ambiance pour audio_ambience.")
    groupe_wf.add_argument("--character", default="marc_novice", help="Nom du personnage cible pour le workflow outfit (ex: marc_novice).")
    groupe_wf.add_argument("--top", default="rustic medieval beige burlap tunic fabric", help="Description du tissu/matière pour le haut/tunique (workflow outfit).")
    groupe_wf.add_argument("--shoes", default="worn dark brown medieval leather shoes texture", help="Description de la matière pour les chaussures/bottes (workflow outfit).")
    groupe_wf.add_argument("--mpfb-dir", help="Répertoire personnalisé des assets MakeHuman / MPFB.")
    groupe_wf.add_argument("--end-img", help="Image clé de fin pour l'interpolation vidéo FLF2V (workflow video).")
    groupe_wf.add_argument("--control-video", help="Dossier de trames de guidage vidéo V2V (workflow video).")
    groupe_wf.add_argument("--flow-shift", type=float, default=3.0, help="Facteur de shift flow-matching pour modèles Wan/SD3 (défaut: 3.0).")

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

    if args.update_llama:
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

    if args.update_vulkan:
        from pathlib import Path
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

    type_normalise = {"1": "item", "2": "character", "3": "prop"}.get(args.type, args.type)

    # Préparation des paramètres du workflow
    params = {
        "prompt": prompt_texte,
        "input": args.input_file,
        "type": type_normalise,
        "shape": args.shape,
        "output": args.output,
        "output_dir": args.output_dir,
        "size": args.size,
        "factor": args.factor,
        "normal_strength": args.normal_strength,
        "palette": args.palette,
        "grid_size": args.grid_size,
        "themes": args.themes,
        "file": args.recipe_file,
        "columns": args.columns,
        "preview": not args.no_preview,
        "no_llm": True if args.no_llm else not args.use_llm,
        "use_llm": args.use_llm and not args.no_llm,
        "sans_llm": True if args.no_llm else not args.use_llm,
        "strength": args.strength,
        "steps": args.steps,
        "guidance": args.guidance,
        "cfg_scale": args.cfg_scale,
        "seed": args.seed,
        "tolerance": args.tolerance,
        "loras": args.loras,
        "lora_dir": args.lora_dir,
        "upscale": args.upscale,
        "upscale_model": args.upscale_model,
        "segmenter": args.segmenter,
        "pbr_engine": args.pbr_engine,
        "angle": args.angle,
        "flow_type": args.flow_type,
        "turbulence": args.turbulence,
        "margin": args.margin,
        "auto_margin": args.auto_margin,
        "voxel_depth": args.voxel_depth,
        "voxel_scale": args.voxel_scale,
        "biome_a": args.biome_a,
        "biome_b": args.biome_b,
        "frames": args.frames,
        "vfx_type": args.vfx_type,
        "emotions": args.emotions,
        "duration": args.duration,
        "mode_2d": args.mode_2d,
        "pose": args.pose,
        "pitch": args.pitch,
        "fps": args.fps,
        "items": args.items,
        "ambience_type": args.ambience_type,
        "character": args.character,
        "top": args.top,
        "shoes": args.shoes,
        "mpfb_dir": args.mpfb_dir,
        "end_img": args.end_img,
        "control_video": args.control_video,
        "flow_shift": args.flow_shift
    }

    # Détection automatique du workflow si l'argument -w n'est pas spécifié
    wf_cible = args.workflow.lower()
    if wf_cible == "generate" and args.recipe_file:
        wf_cible = "batch"

    try:
        workflow_cls = WorkflowRegistry.get(wf_cible)
        workflow_instance = workflow_cls(config)
        workflow_instance.run(params)
    except Exception as e:
        print(f"❌ Erreur lors de l'exécution du workflow '{wf_cible}' : {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()