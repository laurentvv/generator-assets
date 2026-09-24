#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Console interactive de choix et de paramétrage des workflows."""

import os
from core.config import (
    DEFAULT_OUTPUT_DIR,
    lister_loras,
    lister_upscalers,
    resoudre_sd_model,
    slugifier_texte,
    verifier_prerequis,
)
from workflows import (
    WorkflowRegistry,
)


# Entrées de maintenance : hors registre des workflows (routées vers cli.maintenance)
_ENTREES_MAINTENANCE = [
    ("update_sd", "🔄 Gestionnaire de Mise à Jour & Compilation Vulkan (stable-diffusion.cpp)"),
    ("update_llama", "🦙 Gestionnaire de Mise à Jour & Compilation Vulkan (llama.cpp)"),
    ("update_vulkan", "⚡ Suite Complète IA Vulkan (SD + LLaMA + Diagnostic GPU)"),
]


def construire_menu() -> dict:
    """Génère le menu interactif depuis le registre (source unique : WorkflowRegistry).

    Ordre = ordre d'enregistrement ; emoji et description portés par la classe.
    Un workflow enregistré apparaît donc TOUJOURS au menu (testé par
    tests/test_cli_contract.py). Les gestionnaires de maintenance ferment le menu.
    """
    menu = {}
    for i, (nom, desc) in enumerate(WorkflowRegistry.list_all().items(), start=1):
        emoji = getattr(WorkflowRegistry.get(nom), "emoji", "")
        menu[str(i)] = (nom, f"{emoji} {desc}".strip() if emoji else desc)
    for j, (nom, libelle) in enumerate(_ENTREES_MAINTENANCE, start=len(menu) + 1):
        menu[str(j)] = (nom, libelle)
    return menu


def lancer_mode_interactif(config: dict):
    """Interface interactive en console permettant d'exécuter n'importe quel workflow."""
    print("\n" + "=" * 65)
    print(" ⚔️  Generator Assets - Console de Workflows 2D & 3D Godot ⚔️ ")
    print("=" * 65)
    
    verifier_prerequis(config)

    menu_workflows = construire_menu()

    while True:
        try:
            print("\n--- Choisissez un Workflow ['q' pour quitter] ---")
            for k, (_, desc) in menu_workflows.items():
                print(f"  [{k.rjust(2)}] {desc}")

            choix = input("\n👉 Choix (1-42) [défaut: 1] : ").strip()
            if choix.lower() == 'q':
                print("👋 Au revoir !")
                break

            wf_name, _ = menu_workflows.get(choix, ("generate", ""))
            if wf_name in ("update_sd", "update_llama", "update_vulkan"):
                # Gestionnaires de maintenance : hors registre des workflows,
                # dispatch direct vers leur branche dédiée plus bas.
                wf_instance = None
            else:
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

            elif wf_name == "mesh_ia":
                chemin = input("🖼️  Image de l'objet (ou laisser vide pour générer depuis un prompt) : ").strip()
                if chemin and os.path.exists(chemin):
                    params["input"] = chemin
                else:
                    params["prompt"] = input("💡 Description de l'objet 3D (ex: casque de guerre en acier sombre) : ").strip()
                    if not params["prompt"]:
                        continue
                print("🧊 Résolution : [1] 512 — rapide ~11 min (itération)   [2] 1024 — qualité ~55 min (master)")
                choix_r = input("Choix (1-2) [défaut: 1] : ").strip()
                params["res"] = 1024 if choix_r == "2" else 512
                faces = input("📉 Cible de faces du GLB jeu (ex: 30000 ; vide = pas de réduction, master complet) : ").strip()
                if faces:
                    params["faces_cible"] = int(faces)

            elif wf_name == "asset_blendkit":
                params["query"] = input("🔎 Mots-clés Blendkit (ex: wooden barrel / tunnel studio) : ").strip()
                if not params["query"]:
                    continue
                choix_m = input("📂 Mode : [1] prop .glb Godot   [2] plaque décor chaine (défaut: 1) : ").strip()
                params["mode"] = "plate" if choix_m == "2" else "prop"
                idx = input("🔢 Index du résultat (liste affichée avant choix ; défaut: 0) : ").strip()
                if idx.isdigit():
                    params["index"] = int(idx)

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

            elif wf_name == "music_bg":
                params["prompt"] = input(
                    "🎵 Description du fond musical en anglais (défaut: minimal techno discret) : "
                ).strip() or None
                params["duration"] = float(input("⏱️  Durée de la boucle en secondes (défaut: 12) : ").strip() or 12)
                moteur_choix = input("🎚️  Moteur : 1=ACE-Step 1.5 (défaut), 2=MiniMax-Music3 : ").strip()
                params["moteur"] = "music3" if moteur_choix == "2" else "acestep"
                params["candidats"] = int(input("🎲 Nombre de candidats à générer (défaut: 3) : ").strip() or 3)
                params["lufs"] = float(input("🎚️  LUFS cible du bed (défaut: -30) : ").strip() or -30.0)
                analyse_choix = input("🧠 Activer la QA Music Flamingo ? (o/N) : ").strip().lower()
                params["analyse"] = analyse_choix in ("o", "oui", "y", "yes")

            elif wf_name == "voix_off":
                params["prompt"] = input(
                    "🎙️ Texte à lire (ou chemin d'un fichier .txt) : "
                ).strip()
                if not params["prompt"]:
                    continue
                params["voix_ref"] = input(
                    "🧬 Référence vocale à cloner (chemin WAV/MP3/M4A, vide = voix native) : "
                ).strip() or None
                moteur_defaut = "1" if params["voix_ref"] else "2"
                moteur_choix = input(
                    "🎚️  Moteur : 1=qwen3-tts (clonage+instruct, défaut avec réf), "
                    "2=VoxCPM2 (défaut sans réf), 3=Fish S2-Pro (balises expression) : "
                ).strip() or moteur_defaut
                params["moteur"] = {"1": "qwen3", "2": "voxcpm2", "3": "fish"}.get(moteur_choix, None)
                params["instruct"] = input(
                    "🎭 Consigne de style/émotion pour qwen3 (ex: 'energetic YouTube narrator', vide = aucune) : "
                ).strip() or None
                params["lufs_voix"] = float(input("🎚️ LUFS cible de la voix (défaut: -16) : ").strip() or -16.0)

            elif wf_name == "voix_robot":
                params["prompt"] = input(
                    "🤖 Texte anglais à lire : "
                ).strip()
                if not params["prompt"]:
                    continue
                params["robot_voice"] = input("🎚️ Voix Kokoro [défaut: af_heart] : ").strip() or "af_heart"
                params["robot_pitch"] = float(input("🎚️ Facteur de pitch [défaut: 1.3] : ").strip() or 1.30)
                params["robot_ringmod"] = float(input("🎚️ Ring modulation Hz [défaut: 120] : ").strip() or 120.0)
                params["robot_tempo"] = float(input("🎚️ atempo (débit) [défaut: 0.65] : ").strip() or 0.65)
                params["robot_gain"] = float(input("🎚️ Gain final dB [défaut: -4] : ").strip() or -4.0)

            elif wf_name == "chanson":
                params["prompt"] = input("🎵 Paroles (texte) ou chemin d'un fichier .txt : ").strip()
                if not params["prompt"]:
                    continue
                params["style_musique"] = input(
                    "🎼 Style musical EN (défaut : dark folk Vent-Gris) : "
                ).strip() or None
                params["duration"] = float(input("⏱️  Durée cible en secondes (défaut: 180) : ").strip() or 180.0)

            elif wf_name == "musique_adn":
                params["prompt"] = input(
                    "🧬 Style EN de la nouvelle musique (ex: 'German gothic rock 1990, dark wave, hypnotic tribal groove') : "
                ).strip()
                if not params["prompt"]:
                    continue
                params["input"] = input("🎵 Audio de référence (MP3/WAV) : ").strip()
                if not params["input"] or not os.path.exists(params["input"]):
                    print("❌ Référence introuvable.")
                    continue
                params["duration"] = float(input("⏱️  Durée en secondes (défaut: 60) : ").strip() or 60.0)
                params["tonalite"] = input("🎼 Forcer la tonalité (ex: 'C# minor', vide = détection auto) : ").strip() or None

            elif wf_name == "retrait_voix":
                params["input"] = input("🎧 Morceau source (MP3/WAV — le chant sera retiré) : ").strip()
                if not params["input"] or not os.path.exists(params["input"]):
                    print("❌ Fichier introuvable.")
                    continue
                params["output"] = input("💾 Nom de sortie (défaut : nom du fichier) : ").strip() or None

            elif wf_name == "audio_upscale":
                chemin = input("🔊 Fichier audio source à bande réduite (8/12/16/24 kHz) : ").strip()
                if not chemin or not os.path.exists(chemin):
                    print("❌ Fichier introuvable.")
                    continue
                params["input"] = chemin
                choix_v = input("🎚️ Variante : [1] speech — voix off (défaut)   [2] audio — musique : ").strip()
                params["upsr_variante"] = "audio" if choix_v == "2" else "speech"
                params["output"] = input("💾 Nom de sortie (défaut : nom du fichier) : ").strip() or None

            elif wf_name == "animal_godot":
                chemin = input("🐺 Blend d'animal riggé (ex. pack Quaternius) : ").strip()
                if not chemin or not os.path.exists(chemin):
                    print("❌ Fichier introuvable.")
                    continue
                params["input"] = chemin
                params["output"] = input("💾 GLB de sortie (défaut : <blend>_godot.glb) : ").strip() or None

            elif wf_name == "musique_essence":
                params["prompt"] = input(
                    "🧬 Style EN de la musique (ex: 'German gothic rock 1990, dark wave, hypnotic tribal groove') : "
                ).strip()
                if not params["prompt"]:
                    continue
                params["input"] = input("🎵 Audio de référence dont capter l'essence (MP3/WAV) : ").strip()
                if not params["input"] or not os.path.exists(params["input"]):
                    print("❌ Référence introuvable.")
                    continue
                params["duration"] = float(input("⏱️  Durée en secondes (défaut: 30) : ").strip() or 30.0)
                params["scale"] = float(input("🎚️  Échelle d'essence 0-1 (défaut: 0.45 ; plateau validé 0.40-0.45) : ").strip() or 0.45)
                brut = input("🎭 Garder la version brute avec la bave de chant ? (o/N) : ").strip().lower()
                params["keep_vocals"] = brut in ("o", "oui", "y", "yes")

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

            elif wf_name == "character_makeup":
                port = input("🖼️  Chemin vers le portrait de référence (ex: elian_portrait.png) : ").strip()
                if not port:
                    continue
                params["portrait"] = port
                nom = input("👤 Nom du personnage [défaut: extrait du portrait] : ").strip()
                if nom:
                    params["character"] = nom
                skin = input("🎨 Skin diffuse 3D existant (laisser vide pour auto-détection) : ").strip()
                if skin:
                    params["skin"] = skin
                blend = input("🎬 Scène .blend pour rendus de contrôle studio (laisser vide pour calque seul) : ").strip()
                if blend:
                    params["blend_file"] = blend

            elif wf_name == "monoplan_ia":
                params["prompt"] = input("🎬 Mouvement de caméra / scène EN (ex: slow zoom in on the artifact) : ").strip()
                if not params["prompt"]:
                    continue
                img = input("🖼️  Image d'amorce (laisser vide si réutilisation d'un monoplan existant) : ").strip()
                if img:
                    params["input"] = img
                else:
                    src = input("🎥 Webm monoplan déjà généré à réutiliser (--monoplan-source) : ").strip()
                    if not src or not os.path.exists(src):
                        print("❌ Il faut une image d'amorce ou un monoplan source existant.")
                        continue
                    params["monoplan_source"] = src
                nom_out = input("💾 Nom de sortie [défaut: auto] : ").strip()
                if nom_out:
                    params["output"] = nom_out

            elif wf_name == "h3_ref2va":
                params["input"] = input("🎥 Vidéo source (référence Ref2VA, mp4/webm) : ").strip()
                if not params["input"] or not os.path.exists(params["input"]):
                    print("❌ Fichier introuvable.")
                    continue
                params["prompt"] = input("🗣️  Description EN de la SUITE (ex: she smiles and waves goodbye) : ").strip()
                if not params["prompt"]:
                    continue
                # Mode turbo = recette validée (AGENTS.md : toujours le proposer)
                params["turbo"] = input("⚡ Mode turbo 8 steps (O/n, ~2x plus rapide) : ").strip().lower() not in ("n", "non", "no")

            elif wf_name == "outfit":
                char_name = input("👤 Personnage cible [marc_novice] : ").strip()
                if char_name:
                    params["character"] = char_name
                top = input("🧵 Tissu du haut EN [défaut: tunique médiévale beige] : ").strip()
                if top:
                    params["top"] = top

            elif wf_name == "character3d":
                port = input("🖼️  Portrait IA de référence (PNG) : ").strip()
                if not port or not os.path.exists(port):
                    print("❌ Portrait introuvable.")
                    continue
                params["portrait"] = port

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

