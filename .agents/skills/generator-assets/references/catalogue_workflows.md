# Catalogue de référence des 40 workflows

Source de vérité : `README.md` § « 📦 Complete Workflow Catalog » (entrées/sorties/options exhaustives,
showcases). Ce fichier est l'aide-mémoire condensé pour choisir et lancer — si une option manque ici,
elle est dans le README.

Toutes les commandes : `uv run python main.py -w <workflow> …` depuis la racine du dépôt.
Rappel garde-fous : `scripts/check_charge_systeme.py` avant toute génération lourde • prompt anglais •
`--seed` fixée • une seule génération lourde à la fois.

---

## 1. 3D géométrie & textures PBR

| Workflow | Usage | Entrées clés | Sorties |
| :--- | :--- | :--- | :--- |
| `material3d` | Pack PBR complet (albedo, normal DeepBump, roughness, height, AO, ORM) + `.tres` Godot | `prompt` ou `-i`, `-s` (512/1024/2048), `--pbr-engine` | `_albedo/_normal/_rough/_height/_ao/_orm.png`, `_material.tres`, `_preview3x3.png` |
| `mesh3d` | Mesh 3D paramétrique Blender (texture PBR embarquée) | `prompt` ou `-i`, `--shape` (tile/cube/pillar/cylinder/sphere/card/cutout) | `_3d_<shape>.glb` + maps PBR |
| `mesh_ia` | **Objet 3D IA volume réel** (TRELLIS.2-4B) depuis prompt (chaîne `generate`) ou image `-i` | `--res` (512 itération ~11 min / 1024 master ~55 min), `--faces-cible` (décimation Godot, ex. 30000), `--seed` | `<nom>_<res>.glb`, `_jeu.glb` (si décimation), planche de contrôle, `_infos.json` |
| `voxel3d` | Modèle voxel (.glb, couleurs de sommets) pour GridMap | `-i` ou `prompt`, `--grid-size`, `--voxel-depth` | `_voxel.glb` |
| `skybox` | Panorama 360° équirectangulaire 2:1 + IBL | `prompt`, `-s`/`--width --height`, `-l 360RedmondResized:1.0` | `_sky.png`, `_sky_env.tres` |
| `turnaround3d` | Fiche de modélisation orthogonale (face + profil, guides) | `prompt`, `-s`, `--seed` | `_front.png`, `_side.png`, `_model_sheet.png` |
| `flowmap` | Carte de flux vectoriel + shader eau/lave Godot | `--angle`, `--flow-type` (river/vortex/radial/optical), `--turbulence`, `--mode-2d` | `_flowmap.png`, `_water.gdshader`, `_material.tres` |
| `asset_blendkit` | Props CC0 Blendkit (.glb Godot) ou plaque décor rendue Cycles (compositing YouTube) | `--query`, `--list-assets`, `--index`, `--mode prop\|plate`, `--resolution` (2K défaut) | `<asset>.glb`+`apercu.png` ou `plaque.png` |

`mesh_ia` — choix de `--faces-cible` : 30000 = objet héros proche, 10000 = prop standard, 2000-3000 =
clutter répété, ≥8000 si silhouette très courbée. Itérer à 512, master à 1024.

**Prérequis 3D** : §1 passe par Blender headless (bloquant pour `mesh3d`/`voxel3d`/`asset_blendkit`,
optionnel pour `mesh_ia` — décimation + planche de contrôle) ; §2 exige Blender + addon MPFB2
(data dir `%APPDATA%\Blender Foundation\Blender\5.2\mpfb\data\data`, surcharge `MPFB_DATA_DIR`) ;
`asset_blendkit` exige l'addon BlenderKit connecté une fois en GUI. Standards game-ready Godot,
checklist de validation et écueils détaillés : [`pipeline_3d_blender.md`](pipeline_3d_blender.md).

## 2. Personnages humanoïdes (MakeHuman / MPFB2)

| Workflow | Usage | Entrées clés | Sorties |
| :--- | :--- | :--- | :--- |
| `character3d` | Portrait 2D → corps 3D complet (makeup hm08, rig Mixamo, habits, rendus Cycles) | `--portrait`, `--character`, `--age`, `--gender`, `--eye-color`, `--samples` | `.blend`, `.glb`, makeup ink, 4 rendus PNG |
| `character_makeup` | Couche MakeUp uniquement (sans reconstruire le corps) | `--portrait`, `--character`, `--makeup-only` | ink layer `.png`+`.json` |
| `makehuman_clothes` | Garde-robe modulaire depuis un thème (`.mhclo` barycentrique) | `prompt`, `--parts` (torso,pants,shoes) | `.mhclo/.obj/.mhmat/.thumb` + scène test |
| `outfit` | Retexturation PBR de vêtements existants (patrons UV préservés) | `--character`, `--top`, `--shoes` | textures + `.blend`/`.glb` mis à jour + rendu |
| `pose_control` | Sprite guidé par squelette OpenPose + scène Godot riggée | `prompt`, `--pose` (idle/slash_attack/cast_spell/shield_block/jump/walk) | `_skeleton.png`, `_character.png`, `.tscn`, `_rig.json` |
| `rpg_portrait` | Galerie de portraits multi-émotions + manifeste dialogues | `prompt` ou `-i`, `--emotions` | PNG par émotion, `_portrait_grid.png`, `_dialogue_manifest.json` |

⚠️ Règles absolues MakeHuman : jamais d'illustration 2D plaquée, jamais écraser les originaux dans
`%APPDATA%\...\mpfb\data` → lire `GUIDE_AGENT_IA_HABILLAGE.md`. Catalogue bilingue 177 modèles :
`core/clothes_catalog.py` (`aiguiller_modele_vetement`).

## 3. 2D sprites, tuiles & UI

| Workflow | Usage | Entrées clés | Sorties |
| :--- | :--- | :--- | :--- |
| `generate` | Asset 2D isolé détouré centré Godot | `prompt`, `-t` (item/character/prop/tile), `-i` (img2img), `--upscale`, `-l "lora:poids"` | `.png` transparent |
| `spritesheet` | Planche multi-angles alignée + atlas JSON | `prompt`, `-s`, `--columns` | `_spritesheet.png`, `_atlas.json` |
| `variations` | Variantes élémentaires (feu/glace/poison…) | `prompt` ou `-i`, `--themes` | `<base>_<theme>.png` |
| `tileable` | Texture raccordable sans couture + vérif 3×3 | `prompt`, `-s` | `_tile.png`, `_preview3x3.png` |
| `pixelart` | Quantization palette rétro | `-i` ou `prompt`, `--palette` (pico8/endesga32/gameboy), `--grid-size` | `_pixelart_<palette>.png` |
| `ui_9slice` | Cadres/boutons 9-patch | `prompt` ou `-i`, `--margin`/`--auto-margin` | `.png`, `_stylebox.tres`, `_ninepatch.tscn` |
| `autotile_pack` | Atlas autotile 47 tuiles Wang + TileSet | `--biome-a`, `--biome-b`, `-s` | `_atlas.png`, `_tileset.tres` |
| `rembg` | Détourage neuronal (BiRefNet/RMBG-1.4) | `-i` (requis) | `_rembg.png` |
| `batch` | Génération en série depuis un JSON | `--recipe <fichier.json>` | selon recette |

LoRAs disponibles : `-l "game_icon_diablo_style:0.8"` (bascule auto SDXL Juggernaut) — liste complète
`python main.py --list-loras`.

## 4. Audio, voix & musique (audio.cpp Vulkan)

| Workflow | Usage | Entrées clés | Sorties |
| :--- | :--- | :--- | :--- |
| `sfx` | Bruitages IA/procéduraux | `prompt` (EN), type d'effet | `_sfx.wav`, `_sfx.ogg` |
| `audio_ambience` | Ambiances bouclables sans couture | `prompt` (EN) | `_ambience.wav` |
| `music_bg` | **Boucles musicales beds** (ACE-Step 1.5 défaut, ou Music3) : boucle parfaite + bed −30 LUFS + recette ducking | `prompt` (EN), `--duration` (12 s), `--candidats` (3), `--force-bpm`/`--tonalite`, `--variante` (turbo/xl-turbo/xl-sft), `--moteur music3`, `--lufs` | `candidats/`, `<name>_bed.wav` (−30 LUFS), `.ogg`, `ECOUTE_cand<N>_boucle_x3.mp3`, `recette_mixage_voix.txt` |
| `chanson` | Chanson complète AVEC paroles (ACE-Step xl-turbo) | paroles (texte ou `.txt`, balises `[Verse]`…), `--style-musique` (EN), `--duration`, `--langue` (fr) | `.wav` + `.mp3` |
| `musique_adn` | Nouvelle musique avec BPM + tonalité de la référence, imposés au planificateur | `prompt` sobre (EN), `-i` référence, `--duration`, `--tonalite`, `--lyrics` | `.wav` + `.mp3` |
| `musique_essence` | Musique à l'essence d'une référence (SA3 Medium `init_audio` + retrait voix) | `prompt` sobre (EN), `-i` référence, `--scale` (0.45 validé), `--seed` (42), `--keep-vocals` | `instrumental.wav/.mp3`, `brut.wav`, `stems/` |
| `retrait_voix` | Retrait du chant / stems (HTDemucs) | `-i` morceau | `instrumental.wav/.mp3`, `stems/` |
| `voix_off` | Voix off expressive FR, clonage depuis une référence | texte ou `.txt`, `--voix-ref`, `--moteur` (qwen3/voxcpm2/fish), `--instruct`, `--lufs-voix` (−16) | `voix_off_brut_final.wav` (−16 LUFS) + `.mp3` |
| `voix_robot` | Voix robot EN — recette VALIDÉE figée (kokoro `af_heart`, pitch 1.30, ringmod 120 Hz, tempo 0.65, gain −4 dB) | texte EN ou `.txt`, `--robot-*` (défauts = recette validée) | `.wav`, `.mp3`, `_brut.wav` |
| `audio_upscale` | Super-résolution audio → 48 kHz (UniverSR) — VALIDÉE voix 16k (« parfait même ») et musique 24k (« très bien ») | `-i` audio bande réduite, `--upsr-variante` (speech défaut / audio), `--upsr-rate` (0 = auto), `--seed` (42) | `<nom>_48k.wav` (mono) + `.mp3` |
| `tts_dialogue` | Répliques émotionnelles + visèmes lip-sync Godot | `prompt` (perso), `--emotions`, `--pitch` | `.wav/.ogg` par émotion, `_dialogue_manifest.json` |

Statuts clés : ACE-Step = moteur musical défaut validé (~42 s / 28 s) ; chanson validée (~15 min / 4 min) ;
essence SA3 validée (scale 0.40-0.45, seed 42) ; voix_off validée sur 3 moteurs (production = Apache-2.0 :
qwen3/voxcpm2) ; voix_robot validée (17 essais) ; audio_upscale validé mais **CPU seul RTF ~13 + sortie
mono** (refuser > 24 kHz). **Ludique/subjectif → toujours faire écouter avant
d'industrialiser.** Musique rock sombre : plafond réalisme instrumental connu (MEMORY_BANK §1.11/§1.22) —
descriptions sobres, tonalité mineure imposée.

## 5. Vidéo IA (sd-cli Vulkan) & utilitaires

| Workflow | Usage | Entrées clés | Sorties |
| :--- | :--- | :--- | :--- |
| `video` | Vidéo T2V / I2V / FLF2V (`--end-img`) / V2V — Wan 2.1/2.2, LTX-2.5, .webm + scène Godot | `prompt`, `-i`, `--frames` (33), `--fps` (24) | `_vid.webm`, `_player.tscn` |
| `monoplan_ia` | **Plan cinématique monopratique** depuis image (LTX-2.5 + ralenti mci + zoom pur) — validé, hooks YouTube | `prompt`, `-i` (ou `--monoplan-source`), `--monoplan-frames` (65, max ~81), `--monoplan-duration` (10 s), `--zoom-debut/--zoom-fin`, `--4k` (master 3840×2160 AMF), `--ambiance`, `--carton-titre "LIGNE1\|LIGNE2"` | `_1080p.mp4` ou `_4k.mp4`, `_avec_ambiance.mp4`, `_final_titre.mp4` |
| `h3_ref2va` | **Continuation vidéo+audio** (MiniMax-H3 Ref2VA, webm avec son) — **toujours `--turbo`** | `-i` vidéo source (requise), `prompt` (mentionner `<Video 1>`/`<Audio 1>`), `--ref-frames` (12), `--frames` (22/39/56), `--turbo`, `--max-vram` (10) | `.webm` (VP8 + audio), `<name>_ref/` |
| `rife_interp` | Interpolation de frames 2×/4× (60 fps) | `-i`, `--columns`, `--factor` | `_rife_<N>x.png` |
| `vfx_flipbook` | Planche de particules 4×4 + scène GPUParticles | `prompt`, `--vfx-type`, `--mode-2d` | `_flipbook.png`, `_vfx.tscn` |
| `anim_loop` | Boucle de texture/shader animée sans reset | `prompt`, `--frames`, `--fps` | `_spritesheet.png`, `_loop.gdshader`, `.tres` |
| `ip_adapter` | Verrouillage de style entre assets | `-i` référence | assets cohérents |
| `upscale` | Upscale ESRGAN 2×/4×/4K (alpha préservé) | `-i`, `--scale` | PNG agrandi |

Perfs vidéo (RX 6950 XT) : `monoplan_ia` ~15 min (65 f, 8 steps) + ~3 min post ; ~18 min en 4K natif.
`h3_ref2va` 22 frames ~38 min turbo (~70 min sans). Plafond LTX ≈ 81 frames @ 832×480 (au-delà :
device-lost → reboot avant d'incriminer la recette). Masters YouTube : 4K obligatoire (VP09/AV01),
`scripts/conform_youtube_hd.py`, upscale vidéo `scripts/upscale_video_ai.py`.

**⚠️ Écueil build sd-cli (état sept. 2026, MEMORY_BANK §1.16-1.19)** : LTX-2.5 ET MiniMax-H3 sont cassés
sur la sd-cli installée (`C:\SD\`, master-864 — OOM `ltxav workspace capacity check` / 51 segments) ;
dernière build vidéo validée = **6b3edaa (master-841)**, installée en parallèle dans `C:\SD-6b3edaa\`.
Pour `monoplan_ia` : préfixer `SD_CLI_PATH="C:\SD-6b3edaa\sd-cli.exe"` (ou `--sd-cli`). Pour
`h3_ref2va` : production via la build parallèle (commande brute en §1.16 si le workflow appelle le
binaire en dur). Sur master-864, seule vidéo fiable : Wan T2V/I2V ≤ ~20 trames `--vae-on-cpu`.
L'upscale ESRGAN vidéo (`scripts/upscale_video_ai.py`) reste validé sur master-864. **Toujours
revérifier cet état dans MEMORY_BANK avant un rendu vidéo.**

## Maintenance (menu interactif 33-35, hors génération)

`update_sd` / `update_llama` / `update_vulkan` : gestionnaires de maj/compilation Vulkan — mais le process
officiel passe par `scripts/veille_versions.py` + accord utilisateur (voir `AGENTS.md` § Process de mise
à jour). Jamais de maj automatique.
