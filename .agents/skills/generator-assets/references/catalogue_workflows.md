# Reference catalog of the 40 workflows

Source of truth: `README.md` § "📦 Complete Workflow Catalog" (exhaustive inputs/outputs/options,
showcases). This file is the condensed cheat sheet for choosing and launching — if an option is
missing here, it is in the README.

All commands: `uv run python main.py -w <workflow> …` from the repository root.
Guardrail reminder: `scripts/check_charge_systeme.py` before any heavy generation • English
prompt • fixed `--seed` • only one heavy generation at a time.

---

## 1. 3D geometry & PBR textures

| Workflow | Use | Key inputs | Outputs |
| :--- | :--- | :--- | :--- |
| `material3d` | Complete PBR pack (albedo, DeepBump normal, roughness, height, AO, ORM) + Godot `.tres` | `prompt` or `-i`, `-s` (512/1024/2048), `--pbr-engine` | `_albedo/_normal/_rough/_height/_ao/_orm.png`, `_material.tres`, `_preview3x3.png` |
| `mesh3d` | Parametric Blender 3D mesh (embedded PBR texture) | `prompt` or `-i`, `--shape` (tile/cube/pillar/cylinder/sphere/card/cutout) | `_3d_<shape>.glb` + PBR maps |
| `mesh_ia` | **AI 3D object with real volume** (TRELLIS.2-4B) from prompt (chains `generate`) or image `-i` | `--res` (512 iteration ~11 min / 1024 master ~55 min), `--faces-cible` (Godot decimation, e.g. 30000), `--seed` | `<name>_<res>.glb`, `_jeu.glb` (if decimation), control contact sheet, `_infos.json` |
| `voxel3d` | Voxel model (.glb, vertex colors) for GridMap | `-i` or `prompt`, `--grid-size`, `--voxel-depth` | `_voxel.glb` |
| `animal_godot` | **Rigged packed animal (.blend) → Godot game-ready GLB** (VALIDATED 2026-09-18: native gallop "perfect") | `-i` rigged blend, `--animal-prefixe` (AN_), `--animal-actions` (filter) | `<blend>_godot.glb` (bones + AN_* clips checked) |
| `skybox` | 2:1 equirectangular 360° panorama + IBL | `prompt`, `-s`/`--width --height`, `-l 360RedmondResized:1.0` | `_sky.png`, `_sky_env.tres` |
| `turnaround3d` | Orthogonal modeling sheet (front + side, guides) | `prompt`, `-s`, `--seed` | `_front.png`, `_side.png`, `_model_sheet.png` |
| `flowmap` | Vector flow map + Godot water/lava shader | `--angle`, `--flow-type` (river/vortex/radial/optical), `--turbulence`, `--mode-2d` | `_flowmap.png`, `_water.gdshader`, `_material.tres` |
| `asset_blendkit` | CC0 BlendKit props (Godot .glb) or Cycles-rendered décor plate (YouTube compositing) | `--query`, `--list-assets`, `--index`, `--mode prop\|plate`, `--resolution` (2K default) | `<asset>.glb`+`apercu.png` or `plaque.png` |

`mesh_ia` — choosing `--faces-cible`: 30000 = close-up hero object, 10000 = standard prop,
2000-3000 = repeated clutter, ≥8000 if the silhouette is highly curved. Iterate at 512, master
at 1024.

**3D prerequisites**: §1 goes through Blender headless (blocking for
`mesh3d`/`voxel3d`/`asset_blendkit`, optional for `mesh_ia` — decimation + control contact
sheet); §2 requires Blender + MPFB2 addon (data dir
`%APPDATA%\Blender Foundation\Blender\5.2\mpfb\data\data`, override `MPFB_DATA_DIR`);
`asset_blendkit` requires the BlenderKit addon connected once in the GUI. Godot game-ready
standards, validation checklist and detailed pitfalls: [`pipeline_3d_blender.md`](pipeline_3d_blender.md).

## 2. Humanoid characters (MakeHuman / MPFB2)

| Workflow | Use | Key inputs | Outputs |
| :--- | :--- | :--- | :--- |
| `character3d` | 2D portrait → full 3D body (hm08 makeup, Mixamo rig, clothes, Cycles renders) | `--portrait`, `--character`, `--age`, `--gender`, `--eye-color`, `--samples` | `.blend`, `.glb`, makeup ink, 4 PNG renders |
| `character_makeup` | MakeUp layer only (without rebuilding the body) | `--portrait`, `--character`, `--makeup-only` | ink layer `.png`+`.json` |
| `makehuman_clothes` | Modular wardrobe from a theme (barycentric `.mhclo`) | `prompt`, `--parts` (torso,pants,shoes) | `.mhclo/.obj/.mhmat/.thumb` + test scene |
| `outfit` | PBR retexturing of existing clothes (UV patterns preserved) | `--character`, `--top`, `--shoes` | textures + updated `.blend`/`.glb` + render |
| `pose_control` | OpenPose skeleton-guided sprite (**real ControlNet** conditioning since 26/09: xinsir SDXL, strength 0.9; prompt-only fallback if the model is missing) + rigged Godot scene | `prompt`, `--pose` (idle/slash_attack/cast_spell/shield_block/jump/walk) | `_openpose_skeleton.png`, sprite `.png`, `.tscn`, `_rig.json` |
| `rpg_portrait` | Multi-emotion portrait gallery + dialogue manifest | `prompt` or `-i`, `--emotions` | PNG per emotion, `_portrait_grid.png`, `_dialogue_manifest.json` |

⚠️ Absolute MakeHuman rules: never a plastered 2D illustration, never overwrite the originals in
`%APPDATA%\...\mpfb\data` → read `GUIDE_AGENT_IA_HABILLAGE.md`. Bilingual 177-model catalog:
`core/clothes_catalog.py` (`aiguiller_modele_vetement`).

## 3. 2D sprites, tiles & UI

| Workflow | Use | Key inputs | Outputs |
| :--- | :--- | :--- | :--- |
| `generate` | Isolated 2D cutout asset, centered, Godot-ready | `prompt`, `-t` (item/character/prop/tile), `-i` (img2img), `--upscale`, `-l "lora:weight"` | transparent `.png` |
| `spritesheet` | Aligned multi-angle sheet + JSON atlas | `prompt`, `-s`, `--columns` | `_spritesheet.png`, `_atlas.json` |
| `variations` | Elemental variants (fire/ice/poison…) | `prompt` or `-i`, `--themes` | `<base>_<theme>.png` |
| `tileable` | Seamless tileable texture + 3×3 check | `prompt`, `-s` | `_tile.png`, `_preview3x3.png` |
| `pixelart` | Retro palette quantization | `-i` or `prompt`, `--palette` (pico8/endesga32/gameboy), `--grid-size` | `_pixelart_<palette>.png` |
| `ui_9slice` | 9-patch frames/buttons | `prompt` or `-i`, `--margin`/`--auto-margin` | `.png`, `_stylebox.tres`, `_ninepatch.tscn` |
| `autotile_pack` | 47-tile Wang autotile atlas + TileSet | `--biome-a`, `--biome-b`, `-s` | `_atlas.png`, `_tileset.tres` |
| `rembg` | Neural cutout (BiRefNet/RMBG-1.4) | `-i` (required) | `_rembg.png` |
| `batch` | Batch generation from a JSON | `--recipe <file.json>` (default: stop at the first error, exit ≠ 0; `--continue-on-error` = full batch + failures listed) | per recipe |

Available LoRAs: `-l "game_icon_diablo_style:0.8"` (auto-switches to SDXL Juggernaut) — full list
`python main.py --list-loras`.

## 4. Audio, voice & music (audio.cpp Vulkan)

| Workflow | Use | Key inputs | Outputs |
| :--- | :--- | :--- | :--- |
| `sfx` | AI/procedural sound effects | `prompt` (EN), effect type | `_sfx.wav`, `_sfx.ogg` |
| `audio_ambience` | Seamless loopable ambiances | `prompt` (EN) | `_ambience.wav` |
| `music_bg` | **Music bed loops** (ACE-Step 1.5 default, or Music3): perfect loop + −30 LUFS bed + ducking recipe | `prompt` (EN), `--duration` (12 s), `--candidats` (3), `--force-bpm`/`--tonalite`, `--variante` (turbo/xl-turbo/xl-sft), `--moteur music3`, `--lufs` | `candidats/`, `<name>_bed.wav` (−30 LUFS), `.ogg`, `ECOUTE_cand<N>_boucle_x3.mp3`, `recette_mixage_voix.txt` |
| `chanson` | Complete song WITH lyrics (ACE-Step xl-turbo) | lyrics (text or `.txt`, `[Verse]`… tags), `--style-musique` (EN), `--duration`, `--langue` (fr) | `.wav` + `.mp3` |
| `musique_adn` | New music with the reference's BPM + key, imposed on the planner | minimal `prompt` (EN), `-i` reference, `--duration`, `--tonalite`, `--lyrics` | `.wav` + `.mp3` |
| `musique_essence` | Music with the essence of a reference (SA3 Medium `init_audio` + vocal removal) | minimal `prompt` (EN), `-i` reference, `--scale` (0.45 validated), `--seed` (42), `--keep-vocals` | `instrumental.wav/.mp3`, `brut.wav`, `stems/` |
| `retrait_voix` | Vocal removal / stems (HTDemucs Vulkan) or SAM Audio text-prompted separation (`--music-backend sam`, CPU — target = `"the singing voice"`) | `-i` track, `--music-backend` (vulkan/cpu/auto/sam) | `instrumental.wav/.mp3`, `stems/` (htdemucs) ; `voix.wav`, `sam/` (sam, dir `<name>_sam`) |
| `voix_off` | Expressive FR voice-over, cloned from a reference | text or `.txt`, `--voix-ref`, `--moteur` (qwen3/voxcpm2/fish), `--instruct`, `--lufs-voix` (−16) | `voix_off_brut_final.wav` (−16 LUFS) + `.mp3` |
| `voix_robot` | EN robot voice — frozen VALIDATED recipe (kokoro `af_heart`, pitch 1.30, ringmod 120 Hz, tempo 0.65, gain −4 dB) | EN text or `.txt`, `--robot-*` (defaults = validated recipe) | `.wav`, `.mp3`, `_brut.wav` |
| `voix_perso` | EN character voice — raw Kokoro preset (`--kokoro-voice`, lang auto a\*/b\*) or Qwen3 VoiceDesign (`--instruct`, qwentts.cpp, `--lang English`, seed 42) + validated post chains `--pitch-ratio`/`--whisper`/`--hollow` (VALIDATED 2026-09-27 on the novel2video-ai pilot cast: am_onyx, am_michael, VoiceDesign ×0.90 child, hollow Void) | EN text or `.txt`, engine = `--kokoro-voice` XOR `--instruct`, `--pitch-ratio` (1.0), `--whisper`, `--hollow`, `--brut` (skip −16 LUFS), `--seed` (42), `--lufs-voix` | `<name>_brut.wav` → `<name>.wav` (post) → `<name>_final.wav` (−16 LUFS) + `.mp3` |
| `audio_upscale` | Audio super-resolution → 48 kHz (UniverSR) — VALIDATED 16k voice ("perfect") and 24k music ("very good") | `-i` band-limited audio, `--upsr-variante` (speech default / audio), `--upsr-rate` (0 = auto), `--seed` (42) | `<name>_48k.wav` (mono) + `.mp3` |
| `tts_dialogue` | Emotional lines + Godot lip-sync visemes | `prompt` (character), `--emotions`, `--pitch` | `.wav/.ogg` per emotion, `_dialogue_manifest.json` |

Key statuses: ACE-Step = validated default music engine (~42 s / 28 s); song validated (~15 min /
4 min); SA3 essence validated (scale 0.40-0.45, seed 42); voix_off validated on 3 engines
(production = Apache-2.0: qwen3/voxcpm2); voix_robot validated (17 trials); audio_upscale
validated but **CPU-only RTF ~13 + mono output** (refuse > 24 kHz). **Playful/subjective → always
have it listened to before industrializing.** Dark rock music: known instrumental realism ceiling
(MEMORY_BANK §1.11/§1.22) — minimal descriptions, imposed minor key.

## 5. AI video (sd-cli Vulkan) & utilities

| Workflow | Use | Key inputs | Outputs |
| :--- | :--- | :--- | :--- |
| `video` | T2V / I2V / FLF2V (`--end-img`) / V2V video — Wan 2.1/2.2, LTX-2.5, .webm + Godot scene | `prompt`, `-i`, `--frames` (33), `--fps` (24) | `_vid.webm`, `_player.tscn` |
| `monoplan_ia` | **Single-shot cinematic plan** from image (LTX-2.5 + mci slow-mo + pure zoom) — validated, YouTube hooks | `prompt`, `-i` (or `--monoplan-source`), `--monoplan-frames` (65, max ~81), `--monoplan-duration` (10 s), `--zoom-debut/--zoom-fin`, `--4k` (3840×2160 AMF master), `--ambiance`, `--carton-titre "LINE1\|LINE2"` | `_1080p.mp4` or `_4k.mp4`, `_avec_ambiance.mp4`, `_final_titre.mp4` |
| `h3_ref2va` | **Video+audio continuation** (MiniMax-H3 Ref2VA, webm with sound) — **always `--turbo`** | `-i` source video (required), `prompt` (mention `<Video 1>`/`<Audio 1>`), `--ref-frames` (12), `--frames` (22/39/56), `--turbo`, `--max-vram` (10) | `.webm` (VP8 + audio), `<name>_ref/` |
| `rife_interp` | 2×/4× frame interpolation (60 fps) | `-i`, `--columns`, `--factor` | `_rife_<N>x.png` |
| `vfx_flipbook` | 4×4 particle sheet + GPUParticles scene | `prompt`, `--vfx-type`, `--mode-2d` | `_flipbook.png`, `_vfx.tscn` |
| `anim_loop` | Animated texture/shader loop without reset | `prompt`, `--frames`, `--fps` | `_spritesheet.png`, `_loop.gdshader`, `.tres` |
| `ip_adapter` | Style locking across assets | `-i` reference | consistent assets |
| `upscale` | ESRGAN 2×/4×/4K upscale (alpha preserved) | `-i`, `--scale` | upscaled PNG |

Video performance (RX 6950 XT): `monoplan_ia` ~15 min (65 f, 8 steps) + ~3 min post; ~18 min in
native 4K. `h3_ref2va` 22 frames ~38 min turbo (~70 min without). LTX ceiling ≈ 81 frames @
832×480 (beyond: device-lost → reboot before blaming the recipe). YouTube masters: 4K mandatory
(VP09/AV01), `scripts/conform_youtube_hd.py`, video upscale `scripts/upscale_video_ai.py`.

**⚠️ sd-cli build pitfall (state Sept. 2026, MEMORY_BANK §1.16-1.19)**: MiniMax-H3 is broken on
the installed sd-cli (`C:\SD\`, master-908 — 54 segments + OOM at submit, unchanged from
master-864 to 908 despite upstream fix #1900); LTX-2.5 only passes the 33-frame T2V benchmark
there with low desktop VRAM (rebooted machine, fragile ~120 MB margin) and its 65-frame I2V has
not been retested there; last validated video build = **6b3edaa (master-841)**, installed in
parallel in `C:\SD-6b3edaa\`. For `monoplan_ia`: prefix
`SD_CLI_PATH="C:\SD-6b3edaa\sd-cli.exe"` (or `--sd-cli`). For `h3_ref2va`: production through
the parallel build (raw command in §1.16 if the workflow calls the binary hard-coded). On
master-908, the only reliable video: Wan T2V/I2V ≤ ~20 frames with `--vae-on-cpu`. Video ESRGAN
upscale (`scripts/upscale_video_ai.py`) remains validated. **Always re-check this state in
MEMORY_BANK before a video render.**

## Maintenance (interactive menu 33-35, outside generation)

`update_sd` / `update_llama` / `update_vulkan`: update/Vulkan-compilation managers — but the
official process goes through `scripts/veille_versions.py` + user agreement (see `AGENTS.md` §
Watch & updates). Never automatic updates.
