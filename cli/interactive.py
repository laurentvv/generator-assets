#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Interactive console for workflow selection and parameterization."""

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


# Maintenance entries: outside the workflow registry (routed to cli.maintenance)
_ENTREES_MAINTENANCE = [
    ("update_sd", "🔄 Update & Vulkan Build Manager (stable-diffusion.cpp)"),
    ("update_llama", "🦙 Update & Vulkan Build Manager (llama.cpp)"),
    ("update_vulkan", "⚡ Complete Vulkan AI Suite (SD + LLaMA + GPU Diagnostics)"),
]


def construire_menu() -> dict:
    """Builds the interactive menu from the registry (single source: WorkflowRegistry).

    Order = registration order; emoji and description are carried by the class.
    A registered workflow therefore ALWAYS shows up in the menu (tested by
    tests/test_cli_contract.py). The maintenance managers close the menu.
    """
    menu = {}
    for i, (nom, desc) in enumerate(WorkflowRegistry.list_all().items(), start=1):
        emoji = getattr(WorkflowRegistry.get(nom), "emoji", "")
        menu[str(i)] = (nom, f"{emoji} {desc}".strip() if emoji else desc)
    for j, (nom, libelle) in enumerate(_ENTREES_MAINTENANCE, start=len(menu) + 1):
        menu[str(j)] = (nom, libelle)
    return menu


def lancer_mode_interactif(config: dict):
    """Interactive console interface allowing any workflow to be run."""
    print("\n" + "=" * 65)
    print(" ⚔️  Generator Assets - Godot 2D & 3D Workflows Console ⚔️ ")
    print("=" * 65)

    verifier_prerequis(config)

    menu_workflows = construire_menu()

    while True:
        try:
            print("\n--- Choose a Workflow ['q' to quit] ---")
            for k, (_, desc) in menu_workflows.items():
                print(f"  [{k.rjust(2)}] {desc}")

            choix = input("\n👉 Choice (1-42) [default: 1] : ").strip()
            if choix.lower() == 'q':
                print("👋 Goodbye!")
                break

            wf_name, _ = menu_workflows.get(choix, ("generate", ""))
            if wf_name in ("update_sd", "update_llama", "update_vulkan"):
                # Maintenance managers: outside the workflow registry,
                # direct dispatch to their dedicated branch below.
                wf_instance = None
            else:
                wf_cls = WorkflowRegistry.get(wf_name)
                wf_instance = wf_cls(config)

            params = {"output_dir": config.get("output_dir", DEFAULT_OUTPUT_DIR)}

            # Detection of the available LoRAs
            loras_dispos = lister_loras()
            if loras_dispos and wf_name in ["generate", "mesh3d", "material3d", "skybox", "turnaround3d", "spritesheet", "variations"]:
                print("\n🧩 LoRAs detected:")
                for idx, lora in enumerate(loras_dispos, 1):
                    print(f"   [{idx}] {lora['name']} ({lora['size_mb']} MB)")
                choix_l = input("Apply LoRAs? (e.g. '1:0.8, 2:1.0' or leave empty) : ").strip()
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
                        # If LoRAs are selected, switch to JuggernautXL (SDXL)
                        modele_jugg = resoudre_sd_model("juggernaut")
                        if modele_jugg and os.path.exists(modele_jugg):
                            self_sd = config.get("sd_model", "")
                            if "flux" in self_sd.lower():
                                config["sd_model"] = modele_jugg
                                print("   🚀 Automatic switch to SDXL Juggernaut for compatibility with your LoRAs.")
                        print(f"   ➔ LoRAs enabled: {', '.join(loras_choisis)}")

            if wf_name == "generate":
                concept = input("💡 Asset concept: ").strip()
                if not concept:
                    continue
                type_a = input("📂 Type [1: Item, 2: Character, 3: Prop] (default: 1) : ").strip()
                type_map = {"1": "item", "2": "character", "3": "prop"}
                params["prompt"] = concept
                params["type"] = type_map.get(type_a, "item")
                params["output"] = input(f"💾 File name [default: {slugifier_texte(concept)}] : ").strip()
                up = input("🔍 Enable automatic 4K AI upscaling (1024 -> 4096 px)? (y/N) [default: N] : ").strip().lower()
                if up in ("o", "oui", "y", "yes"):
                    params["upscale"] = True
                    params["factor"] = 4.0

            elif wf_name == "mesh3d":
                chemin = input("🖼️  Existing 2D texture or asset (or leave empty to generate) : ").strip()
                if chemin and os.path.exists(chemin):
                    params["input"] = chemin
                else:
                    params["prompt"] = input("💡 Description of the 3D object or material: ").strip()
                print("📐 3D Shape: [1] Tile/Floor (tile)  [2] Cube/Chest (cube)  [3] Pillar (pillar)  [4] Sphere (sphere)  [5] 3D Sprite Card (card)")
                choix_s = input("Choice (1-5) [default: 1] : ").strip()
                s_map = {"1": "tile", "2": "cube", "3": "pillar", "4": "sphere", "5": "card"}
                params["shape"] = s_map.get(choix_s, "tile")

            elif wf_name == "mesh_ia":
                chemin = input("🖼️  Object image (or leave empty to generate from a prompt) : ").strip()
                if chemin and os.path.exists(chemin):
                    params["input"] = chemin
                else:
                    params["prompt"] = input("💡 Description of the 3D object (e.g. war helmet in dark steel) : ").strip()
                    if not params["prompt"]:
                        continue
                print("🧊 Resolution: [1] 512 — fast ~11 min (iteration)   [2] 1024 — quality ~55 min (master)")
                choix_r = input("Choice (1-2) [default: 1] : ").strip()
                params["res"] = 1024 if choix_r == "2" else 512
                faces = input("📉 Game GLB face target (e.g. 30000; empty = no reduction, full master) : ").strip()
                if faces:
                    params["faces_cible"] = int(faces)

            elif wf_name == "asset_blendkit":
                params["query"] = input("🔎 Blendkit keywords (e.g. wooden barrel / tunnel studio) : ").strip()
                if not params["query"]:
                    continue
                choix_m = input("📂 Mode: [1] Godot .glb prop   [2] scenery plate for the chain (default: 1) : ").strip()
                params["mode"] = "plate" if choix_m == "2" else "prop"
                idx = input("🔢 Result index (list shown before choice; default: 0) : ").strip()
                if idx.isdigit():
                    params["index"] = int(idx)

            elif wf_name == "material3d":
                chemin = input("🖼️  Existing texture (or leave empty to generate from a prompt) : ").strip()
                if chemin and os.path.exists(chemin):
                    params["input"] = chemin
                else:
                    params["prompt"] = input("🧱 Description of the 3D material (e.g. medieval cobblestones with moss) : ").strip()
                params["size"] = int(input("📐 Material resolution [512, 1024, 2048] (default: 1024) : ").strip() or 1024)

            elif wf_name == "skybox":
                params["prompt"] = input("🌌 360° sky description (e.g. dark fantasy storm sky with purple nebula) : ").strip()
                if not params["prompt"]:
                    continue

            elif wf_name == "turnaround3d":
                params["prompt"] = input("📐 Character / monster concept for 3D modeling: ").strip()
                if not params["prompt"]:
                    continue

            elif wf_name == "upscale":
                chemin = input("🖼️  Source image path (e.g. godot_assets/casque.png) : ").strip()
                if not os.path.exists(chemin):
                    print(f"❌ File not found: {chemin}")
                    continue

                upscalers = lister_upscalers()
                if upscalers:
                    print("\n🚀 Available AI Upscaler models:")
                    for idx, u in enumerate(upscalers, 1):
                        print(f"   [{idx}] {u['name']} ({u['size_mb']} MB)")
                    choix_u = input("Choose an AI model (number or leave empty for default) : ").strip()
                    if choix_u.isdigit() and 1 <= int(choix_u) <= len(upscalers):
                        params["upscale_model"] = upscalers[int(choix_u) - 1]["path"]

                facteur = input("🔍 Upscaling factor [2, 4] (default: 2) : ").strip() or "2"
                params["input"] = chemin
                params["factor"] = float(facteur)

            elif wf_name == "spritesheet":
                concept = input("💡 Character/entity concept: ").strip()
                if not concept:
                    continue
                params["prompt"] = concept
                params["size"] = int(input("📐 Cell size [default: 256] : ").strip() or 256)

            elif wf_name == "variations":
                chemin = input("🖼️  Base image (or leave empty to start from text) : ").strip()
                if chemin and os.path.exists(chemin):
                    params["input"] = chemin
                else:
                    params["prompt"] = input("💡 Base concept: ").strip()
                themes = input("🎨 Comma-separated themes (e.g. fire,ice,lightning) : ").strip()
                if themes:
                    params["themes"] = themes

            elif wf_name == "tileable":
                concept = input("🧱 Floor type / tileable texture: ").strip()
                if not concept:
                    continue
                params["prompt"] = concept

            elif wf_name == "pixelart":
                chemin = input("🖼️  Source image to pixelate (or leave empty to generate) : ").strip()
                if chemin and os.path.exists(chemin):
                    params["input"] = chemin
                else:
                    params["prompt"] = input("💡 Concept to generate as pixel art: ").strip()
                pal = input("🎨 Palette [pico8, gameboy, endesga32] (default: pico8) : ").strip() or "pico8"
                params["palette"] = pal
                params["grid_size"] = int(input("🔲 Pixel grid resolution [32, 64] (default: 64) : ").strip() or 64)

            elif wf_name == "batch":
                fichier = input("📄 Path to the recipe JSON file (e.g. recipes/dark_fantasy_armory.json) : ").strip()
                if not os.path.exists(fichier):
                    print(f"❌ File not found: {fichier}")
                    continue
                params["file"] = fichier

            elif wf_name == "ip_adapter":
                chemin = input("🖼️  Reference image (or leave empty to generate from a prompt) : ").strip()
                if chemin and os.path.exists(chemin):
                    params["input"] = chemin
                else:
                    params["prompt"] = input("💡 Reference concept: ").strip()
                items = input("📦 Comma-separated consistent items (e.g. sword,shield,potion,helmet) : ").strip()
                if items:
                    params["themes"] = items

            elif wf_name == "anim_loop":
                params["prompt"] = input("💡 VFX loop type (e.g. portal vortex, magic fire, waterfall) : ").strip() or "portal"
                print("🌀 Effect type: [1] Portal (portal)  [2] Flames (fire)  [3] Waterfall (waterfall)  [4] Nebula (nebula)")
                choix_v = input("Choice (1-4) [default: 1] : ").strip()
                v_map = {"1": "portal", "2": "fire", "3": "waterfall", "4": "nebula"}
                params["vfx_type"] = v_map.get(choix_v, "portal")
                params["frames"] = int(input("🎞️  Number of frames [8, 16, 24] (default: 16) : ").strip() or 16)

            elif wf_name == "pose_control":
                params["prompt"] = input("💡 Character concept: ").strip()
                print("🕺 Pose: [1] Stance (idle)  [2] Attack (slash_attack)  [3] Spell (cast_spell)  [4] Shield (shield_block)  [5] Jump (jump)  [6] Run (walk)")
                choix_p = input("Choice (1-6) [default: 1] : ").strip()
                p_map = {"1": "idle", "2": "slash_attack", "3": "cast_spell", "4": "shield_block", "5": "jump", "6": "walk"}
                params["pose"] = p_map.get(choix_p, "idle")

            elif wf_name == "tts_dialogue":
                params["prompt"] = input("🎙️  Character name / Identifier: ").strip() or "guerriere_sanctuaire"
                params["emotions"] = input("🎭 Comma-separated emotions (default: neutral,happy,angry,sad,hurt) : ").strip() or "neutral,happy,angry,sad,hurt"

            elif wf_name == "audio_ambience":
                params["prompt"] = input("🌌 Ambience type (dungeon, forest, storm, space, campfire) : ").strip() or "dungeon"
                params["duration"] = float(input("⏱️  Duration in seconds (default: 8.0) : ").strip() or 8.0)

            elif wf_name == "music_bg":
                params["prompt"] = input(
                    "🎵 Musical bed description in English (default: discreet minimal techno) : "
                ).strip() or None
                params["duration"] = float(input("⏱️  Loop duration in seconds (default: 12) : ").strip() or 12)
                moteur_choix = input("🎚️  Engine: 1=ACE-Step 1.5 (default), 2=MiniMax-Music3 : ").strip()
                params["moteur"] = "music3" if moteur_choix == "2" else "acestep"
                params["candidats"] = int(input("🎲 Number of candidates to generate (default: 3) : ").strip() or 3)
                params["lufs"] = float(input("🎚️  Bed target LUFS (default: -30) : ").strip() or -30.0)
                analyse_choix = input("🧠 Enable Music Flamingo QA? (y/N) : ").strip().lower()
                params["analyse"] = analyse_choix in ("o", "oui", "y", "yes")

            elif wf_name == "voix_off":
                params["prompt"] = input(
                    "🎙️ Text to read (or path of a .txt file) : "
                ).strip()
                if not params["prompt"]:
                    continue
                params["voix_ref"] = input(
                    "🧬 Voice reference to clone (WAV/MP3/M4A path, empty = native voice) : "
                ).strip() or None
                moteur_defaut = "1" if params["voix_ref"] else "2"
                moteur_choix = input(
                    "🎚️  Engine: 1=qwen3-tts (cloning+instruct, default with ref), "
                    "2=VoxCPM2 (default without ref), 3=Fish S2-Pro (expression tags) : "
                ).strip() or moteur_defaut
                params["moteur"] = {"1": "qwen3", "2": "voxcpm2", "3": "fish"}.get(moteur_choix, None)
                params["instruct"] = input(
                    "🎭 Style/emotion instruction for qwen3 (e.g. 'energetic YouTube narrator', empty = none) : "
                ).strip() or None
                params["lufs_voix"] = float(input("🎚️ Voice target LUFS (default: -16) : ").strip() or -16.0)

            elif wf_name == "voix_robot":
                params["prompt"] = input(
                    "🤖 English text to read : "
                ).strip()
                if not params["prompt"]:
                    continue
                params["robot_voice"] = input("🎚️ Kokoro voice [default: af_heart] : ").strip() or "af_heart"
                params["robot_pitch"] = float(input("🎚️ Pitch factor [default: 1.3] : ").strip() or 1.30)
                params["robot_ringmod"] = float(input("🎚️ Ring modulation Hz [default: 120] : ").strip() or 120.0)
                params["robot_tempo"] = float(input("🎚️ atempo (rate) [default: 0.65] : ").strip() or 0.65)
                params["robot_gain"] = float(input("🎚️ Final gain dB [default: -4] : ").strip() or -4.0)

            elif wf_name == "chanson":
                params["prompt"] = input("🎵 Lyrics (text) or path of a .txt file: ").strip()
                if not params["prompt"]:
                    continue
                params["style_musique"] = input(
                    "🎼 Music style EN (default: dark folk Grey Wind) : "
                ).strip() or None
                params["duration"] = float(input("⏱️  Target duration in seconds (default: 180) : ").strip() or 180.0)

            elif wf_name == "musique_adn":
                params["prompt"] = input(
                    "🧬 Music style EN for the new track (e.g. 'German gothic rock 1990, dark wave, hypnotic tribal groove') : "
                ).strip()
                if not params["prompt"]:
                    continue
                params["input"] = input("🎵 Reference audio (MP3/WAV) : ").strip()
                if not params["input"] or not os.path.exists(params["input"]):
                    print("❌ Reference not found.")
                    continue
                params["duration"] = float(input("⏱️  Duration in seconds (default: 60) : ").strip() or 60.0)
                params["tonalite"] = input("🎼 Force the key (e.g. 'C# minor', empty = auto-detect) : ").strip() or None

            elif wf_name == "retrait_voix":
                params["input"] = input("🎧 Source track (MP3/WAV — vocals will be removed) : ").strip()
                if not params["input"] or not os.path.exists(params["input"]):
                    print("❌ File not found.")
                    continue
                params["output"] = input("💾 Output name (default: file name) : ").strip() or None

            elif wf_name == "audio_upscale":
                chemin = input("🔊 Source audio file with reduced bandwidth (8/12/16/24 kHz) : ").strip()
                if not chemin or not os.path.exists(chemin):
                    print("❌ File not found.")
                    continue
                params["input"] = chemin
                choix_v = input("🎚️ Variant: [1] speech — voice-over (default)   [2] audio — music : ").strip()
                params["upsr_variante"] = "audio" if choix_v == "2" else "speech"
                params["output"] = input("💾 Output name (default: file name) : ").strip() or None

            elif wf_name == "animal_godot":
                chemin = input("🐺 Rigged animal Blend (e.g. Quaternius pack) : ").strip()
                if not chemin or not os.path.exists(chemin):
                    print("❌ File not found.")
                    continue
                params["input"] = chemin
                params["output"] = input("💾 Output GLB (default: <blend>_godot.glb) : ").strip() or None

            elif wf_name == "musique_essence":
                params["prompt"] = input(
                    "🧬 Music style EN (e.g. 'German gothic rock 1990, dark wave, hypnotic tribal groove') : "
                ).strip()
                if not params["prompt"]:
                    continue
                params["input"] = input("🎵 Reference audio whose essence to capture (MP3/WAV) : ").strip()
                if not params["input"] or not os.path.exists(params["input"]):
                    print("❌ Reference not found.")
                    continue
                params["duration"] = float(input("⏱️  Duration in seconds (default: 30) : ").strip() or 30.0)
                params["scale"] = float(input("🎚️  Essence scale 0-1 (default: 0.45; validated plateau 0.40-0.45) : ").strip() or 0.45)
                brut = input("🎭 Keep the raw version with the vocal bleed? (y/N) : ").strip().lower()
                params["keep_vocals"] = brut in ("o", "oui", "y", "yes")

            elif wf_name == "video":
                params["prompt"] = input("🎬 Video concept / action (e.g. mystic waterfall in a lush jungle) : ").strip()
                if not params["prompt"]:
                    continue
                img_init = input("🖼️  Initial image for Image-to-Video (or leave empty for Text-to-Video) : ").strip()
                if img_init and os.path.exists(img_init):
                    params["input"] = img_init
                    img_fin = input("🖼️  Final image (leave empty for I2V, specify for FLF2V) : ").strip()
                    if img_fin and os.path.exists(img_fin):
                        params["end_img"] = img_fin
                params["frames"] = int(input("🎞️  Number of frames [17, 33, 49, 81] (default: 33) : ").strip() or 33)
                params["fps"] = int(input("⏱️  FPS rate (default: 24) : ").strip() or 24)
                nom_out = input("💾 Video file name [default: auto] : ").strip()
                if nom_out:
                    params["output"] = nom_out

            elif wf_name == "character_makeup":
                port = input("🖼️  Path to the reference portrait (e.g. elian_portrait.png) : ").strip()
                if not port:
                    continue
                params["portrait"] = port
                nom = input("👤 Character name [default: extracted from the portrait] : ").strip()
                if nom:
                    params["character"] = nom
                skin = input("🎨 Existing 3D diffuse skin (leave empty for auto-detection) : ").strip()
                if skin:
                    params["skin"] = skin
                blend = input("🎬 .blend scene for studio control renders (leave empty for layer only) : ").strip()
                if blend:
                    params["blend_file"] = blend

            elif wf_name == "monoplan_ia":
                params["prompt"] = input("🎬 Camera move / scene EN (e.g. slow zoom in on the artifact) : ").strip()
                if not params["prompt"]:
                    continue
                img = input("🖼️  Seed image (leave empty to reuse an existing monoplan) : ").strip()
                if img:
                    params["input"] = img
                else:
                    src = input("🎥 Already-generated monoplan webm to reuse (--monoplan-source) : ").strip()
                    if not src or not os.path.exists(src):
                        print("❌ A seed image or an existing source monoplan is required.")
                        continue
                    params["monoplan_source"] = src
                nom_out = input("💾 Output name [default: auto] : ").strip()
                if nom_out:
                    params["output"] = nom_out

            elif wf_name == "h3_ref2va":
                params["input"] = input("🎥 Source video (Ref2VA reference, mp4/webm) : ").strip()
                if not params["input"] or not os.path.exists(params["input"]):
                    print("❌ File not found.")
                    continue
                params["prompt"] = input("🗣️  NEXT action description EN (e.g. she smiles and waves goodbye) : ").strip()
                if not params["prompt"]:
                    continue
                # Turbo mode = validated recipe (AGENTS.md: always offer it)
                params["turbo"] = input("⚡ 8-step turbo mode (Y/n, ~2x faster) : ").strip().lower() not in ("n", "non", "no")

            elif wf_name == "outfit":
                char_name = input("👤 Target character [marc_novice] : ").strip()
                if char_name:
                    params["character"] = char_name
                top = input("🧵 Top garment fabric EN [default: beige medieval tunic] : ").strip()
                if top:
                    params["top"] = top

            elif wf_name == "character3d":
                port = input("🖼️  Reference AI portrait (PNG) : ").strip()
                if not port or not os.path.exists(port):
                    print("❌ Portrait not found.")
                    continue
                params["portrait"] = port

            elif wf_name == "update_sd":
                from pathlib import Path
                import scripts.update_sd_cpp as sd_up
                print("\n🔄 stable-diffusion.cpp manager (Vulkan):")
                print("   [1] Check versions (local vs remote)")
                print("   [2] Download the latest official GitHub Vulkan release (Fast)")
                print("   [3] Build natively from sources with Vulkan (CMake + MSVC)")
                print("   [4] Restore a previous backup")
                choix_sd = input("Choice (1-4) [default: 1] : ").strip() or "1"
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
                print("\n🦙 llama.cpp manager (Vulkan):")
                print("   [1] Check versions (local vs remote)")
                print("   [2] Download the latest official GitHub Vulkan release (Fast)")
                print("   [3] Build natively from sources with Vulkan (CMake + MSVC)")
                print("   [4] Restore a previous backup")
                choix_l = input("Choice (1-4) [default: 1] : ").strip() or "1"
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
                print("   [1] Check the state of the whole Vulkan AI suite (SD + LLaMA)")
                print("   [2] Update all engines (official Vulkan releases)")
                print("   [3] Rebuild all engines natively (CMake + MSVC + Vulkan)")
                print("   [4] Restore previous backups")
                choix_v = input("Choice (1-4) [default: 1] : ").strip() or "1"
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
            print("\n👋 Stop requested.")
            break
        except Exception as e:
            print(f"❌ An error occurred: {e}")

