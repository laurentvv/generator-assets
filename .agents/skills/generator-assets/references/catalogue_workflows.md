# Reference catalog of the 40 workflows

Source of truth: `docs/workflows_reference.md` (exhaustive inputs/outputs/options,
mathematical specifications) and `README.md` (visual showcase). This file is the condensed cheat sheet for choosing and launching — if an option is
missing here, it is in `docs/workflows_reference.md`.

All commands: `uv run python main.py -w <workflow> …` from the repository root.
Guardrail reminder: `scripts/check_charge_systeme.py` before any heavy generation • English
prompt • fixed `--seed` • only one heavy generation at a time.

---

## 1. 3D geometry & PBR textures

| Workflow | Use | Key inputs | Outputs |
| :--- | :--- | :--- | :--- |
| `material3d` | Complete PBR pack (albedo, DeepBump normal, roughness, height, AO, ORM) + Godot `.tres` | `prompt` or `-i`, `-s` (512/1024/2048), `--pbr-engine` | `_albedo/_normal/_rough/_height/_ao/_orm.png`, `_material.tres`, `_preview3x3.png` |
| `mesh3d` | Parametric Blender 3D mesh (embedded PBR texture) | `prompt` or `-i`, `--shape` (tile/cube/pillar/cylinder/sphere/card/cutout) | `_3d_<shape>.glb` + PBR maps |
| `mesh_ia` | **AI 3D object with real volume** — engine `--mesh-moteur`: `trellis` (TRELLIS.2-4B, default) or `pixal3d` (TRELLIS.2 fine-tune, pixel-aligned projection: flat/saturated colors + crisp lettering in ONE pass, no repaint; VALIDATED 2026-10-02 « super » on the helmet; 512 ≈ 14 min = +32 % vs trellis; weights `vegax87/Pixal3D` 5 GGUF 11.0 GB same dir; `--fov` optional, default 49.13°) | from prompt (chains `generate`) or image `-i`; `--res` (512 iteration ~11-14 min / 1024 master ~55 min), `--faces-cible` (Godot decimation, e.g. 30000), `--mesh-moteur`, `--fov`, `--seed` | `<name>_<res>.glb`, `_jeu.glb` (if decimation), control contact sheet, `_infos.json` |
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
| `qwen_image` | **Qwen-Image-2.1 photorealistic T2I + compositing** — in-image text rendering, RGBA via prompt; `--qwen-turbo` = official 8-step distilled checkpoint (USER VALIDATED 2026-10-11 "Atomic très bien": AtomicChat sd.cpp-native Q8_0, same TE/VAE, forces 8 steps / CFG 1.0 / custom sigmas — do not pass `--steps`/`--cfg-scale`; avoid the unsloth quant, 876-1352 s boot tax on step 1 of every run); `-i` + `-l` = product-cutout blend with contact shadow (VALIDATED 2026-10-05: white-keyed cutout paste REQUIRED — a white box survives img2img; trigger `pengyu` first, strength 0.65, LoRA `Qwenimag21_c2-st2000`, 448/448 tensors; compositing quality under turbo untested; RESEARCH license: personal/non-commercial ONLY, no production consumers; no model-level NSFW filter, adults only) | `prompt`, `--qwen-turbo`, `--negative-prompt[-file]`, `--width/--height` (%32, default 1152×640), `--steps` (40; 24 in img2img), `--cfg-scale` (6.0), `--seed`, `-i/--input`, `--strength` (0.65), `-l/--lora`, `--lora-dir` | `<name>_qwen21.png` (turbo: ~2 min; base: ~16 min @40 steps t2i, ~6.8 min img2img leg) |
| `spritesheet` | Aligned multi-angle sheet + JSON atlas | `prompt`, `-s`, `--columns` | `_spritesheet.png`, `_atlas.json` |
| `variations` | Elemental variants (fire/ice/poison…) | `prompt` or `-i`, `--themes` | `<base>_<theme>.png` |
| `tileable` | Seamless tileable texture + 3×3 check | `prompt`, `-s` | `_tile.png`, `_preview3x3.png` |
| `pixelart` | Retro palette quantization | `-i` or `prompt`, `--palette` (pico8/endesga32/gameboy), `--grid-size` | `_pixelart_<palette>.png` |
| `ui_9slice` | 9-patch frames/buttons | `prompt` or `-i`, `--margin`/`--auto-margin` | `.png`, `_stylebox.tres`, `_ninepatch.tscn` |
| `autotile_pack` | 47-tile Wang autotile atlas + TileSet | `--biome-a`, `--biome-b`, `-s` | `_atlas.png`, `_tileset.tres` |
| `rembg` | Neural cutout (BiRefNet/RMBG-1.4) | `-i` (required) | `_rembg.png` |
| `miniature` | **YouTube thumbnail via PhotoCraft headless** (Craft suite, `D:\CraftApps\photocraft`) — center-crop to 16:9, bottom gradient band, title/subtitle as REAL text layers (size/color/tracking). Requires `python D:\GIT\craft-suite\manage_craft_suite.py install photocraft`. Env `PHOTOCRAFT_CLI` overrides the exe path | `-i` (required), `--titre` (required at runtime), `--sous-titre`, `--couleur-titre` (#ffe066), `--couleur-sous-titre` (#ffffff), `--taille-titre` (88), `--taille-sous-titre` (34), `--bandeau` (0.55), `--width/--height` (1280×720) | `<name>_miniature.jpg` (q90) |
| `carte_fin` | **YouTube end card via PhotoCraft headless** — fond image (recentré + voile) ou couleur pleine, typographie CTA centrée | `-i/--fond` (optionnel, image), `--texte-principal` (ABONNE-TOI), `--texte-secondaire`, `--couleur-principal` (#7fdcff), `--couleur-secondaire` (#ffffff), `--taille-principal` (120), `--taille-secondaire` (40), `--voile` (0.45), `--width/--height` (1280×720) | `<base>_carte_fin.jpg` (q90) |
| `filigrane_batch` | **Batch watermark + conversion via PhotoCraft headless** — filigrane texte en coin (alpha `#rrggbbaa`), format, long side | `-i` (fichier ou dossier), `--filigrane` (@ ai-doc2video), `--position` (bas-droite…), `--couleur-filigrane` (#ffffffb0), `--taille-filigrane` (28), `--marge` (24), `--format-sortie` (jpg), `--width/--height` (long side) | `<name>_filigrane.<fmt>` |
| `icone_jeu` | **Icône vectorielle jeu via VectorCraft headless** — fond + forme centrée, export **SVG + PNG** (net à toute échelle Godot) | `--forme` (hexagone · cercle · carre · etoile), `--couleur-fond` (#1a1f2e), `--couleur-forme` (#7fdcff), `--taille` (256) | `icone_<forme>_<taille>.svg` + `.png` |
| `doc_texte` | **Texte/Markdown → PDF via WordCraft headless** (scripts, notes d'émission, dossiers) | `-i` (.md/.txt/.html/.tex/.rtf) | `<name>_wordcraft.pdf` |
| `classeur_donnees` | **CSV/TSV/JSON → vrai classeur XLSX via GridCraft headless** (benchmarks, veille) | `-i` (.csv/.tsv/.json) | `<name>.xlsx` |
| `titre_anime` | **Frame de titre 1920×1080 via EffectCraft MCP** (comp + calque texte, session persistante) | `--texte` (GENERATOR-ASSETS), `--teinte` (#7fdcff), `--taille-texte` (120), `--couleur-fond-ecran` (#10131c) | `titre_<texte>.png` |
| `maquette_ui` | **Wireframe UI sombre 1280×720 via FigCraft headless** (header + zone principale + panneau) | `--libelle` (Maquette) | `maquette_<libelle>.png` + `.fig` |
| `photo_develop` | **Développement photo via LightCraft headless** (import → exposition optionnelle → develop.auto → JPEG) | `-i`, `--exposition` (EV), `--long-cote` (1600) | `<name>_developpe.jpg` |
| `son_convertir` | **Conversion audio via SoundCraft headless** (WAV + normalisation/resample/bit-depth) | `-i`, `--normaliser`, `--frequence` (Hz), `--profondeur-bits` (16/24/32f) | `<name>_conforme.wav` |
| `planche_pdf` | **Épreuve A4 via DesignCraft headless** (une image posée sur page A4 → PDF print-ready) | `-i` (image) | `<name>_planche.pdf` |
| `projet_montage` | **Bin rough-cut via FilmCraft headless** (nouveau projet + import médias + save `.fcproj`) | `-i` (fichier média ou dossier) | `<name>_montage.fcproj` |
| `rapport_deck` | **Rapport de benchmarks → PDF via DeckCraft headless** — JSON de mesures (`label/valeur/unite` ou `section/lignes`) → slide titre + **slide graphique** (insert.chart colonnes si ≥2 valeurs numériques) + slides résumé → PDF | `--donnees` (JSON, requis), `--titre`, `--sous-titre` | `rapport_<base>.pdf` |
| `ocr_pdf` | **PDF → texte via PdfCraft headless** — couche texte native d'abord, OCR de repli pour les scans (**en seul en 0.9.0**, limite upstream) | `-i` (PDF ou dossier), `--language` (en), `--forcer-ocr`, `--timeout-ocr` (900) | `<name>.txt` (UTF-8) |
| `prepa_i2v` | **I2V keyframe preparation via PhotoCraft headless** — centered crop to target ratio + lanczos resample (no upscale unless `--width/--height` given). Accepts a file or a directory | `-i` (file or dir), `--ratio` (16:9 · 9:16 · 1:1 · 4:3 · 3:4 · 21:9), `--format-sortie` (png), `--width/--height` (long side only, one at a time) | `<name>_i2v.png` |
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
| `acestep_cover` | Re-style an existing track, duration locked (ACE-Step 1.5 turbo `cover` route, CPU — VALIDATED 2026-10-02 "correct" on the gothic reference; strength knobs proven inert on turbo, source auto-converted 48 kHz stereo) | `-p` style (EN, required), `--audio` source (required, shared flag), `--seed` (42), `--cover-threads` (20), `-o` | `music_cover/<name>.wav` (48 kHz stereo = source duration) + `.mp3` |
| `retrait_voix` | Vocal removal / stems (HTDemucs Vulkan) or SAM Audio text-prompted separation (`--music-backend sam`, CPU — target = `"the singing voice"`) | `-i` track, `--music-backend` (vulkan/cpu/auto/sam) | `instrumental.wav/.mp3`, `stems/` (htdemucs) ; `voix.wav`, `sam/` (sam, dir `<name>_sam`) |
| `voix_off` | Expressive FR voice-over, cloned from a reference | text or `.txt`, `--voix-ref`, `--moteur` (qwen3/voxcpm2/fish/drama3/kitten2 zero-shot 24 kHz), `--instruct`, `--lufs-voix` (−16) | `voix_off_brut_final.wav` (−16 LUFS) + `.mp3` |
| `voix_robot` | EN robot voice — frozen VALIDATED recipe (kokoro `af_heart`, pitch 1.30, ringmod 120 Hz, tempo 0.65, gain −4 dB) | EN text or `.txt`, `--robot-*` (defaults = validated recipe) | `.wav`, `.mp3`, `_brut.wav` |
| `voix_conversion` | Re-voice a recording in another voice (Chatterbox standard q8_0 `vc` task, Vulkan — VALIDATED 2026-10-02 "voix anglaise bien"; Turbo variant = TTS-only trap; output 24 kHz mono dialogue-grade) | `--audio` source (required, shared flag), `--voice-ref` target voice (required), `-o` | `voix_conversion/<name>.wav` (24 kHz mono) |
| `voix_perso` | EN character voice — raw Kokoro preset (`--kokoro-voice`, lang auto a\*/b\*) or Qwen3 VoiceDesign (`--instruct`, qwentts.cpp, `--lang English`, seed 42) + validated post chains `--pitch-ratio`/`--whisper`/`--hollow` (VALIDATED 2026-09-27 on the novel2video-ai pilot cast: am_onyx, am_michael, VoiceDesign ×0.90 child, hollow Void) | EN text or `.txt`, engine = `--kokoro-voice` XOR `--instruct`, `--pitch-ratio` (1.0), `--whisper`, `--hollow`, `--brut` (skip −16 LUFS), `--seed` (42), `--lufs-voix` | `<name>_brut.wav` → `<name>.wav` (post) → `<name>_final.wav` (−16 LUFS) + `.mp3` |
| `audio_upscale` | Audio super-resolution → 48 kHz (UniverSR) — VALIDATED 16k voice ("perfect") and 24k music ("very good") | `-i` band-limited audio, `--upsr-variante` (speech default / audio), `--upsr-rate` (0 = auto), `--seed` (42) | `<name>_48k.wav` (mono) + `.mp3` |
| `tts_dialogue` | Emotional lines + Godot lip-sync visemes | `prompt` (character), `--emotions`, `--pitch` | `.wav/.ogg` per emotion, `_dialogue_manifest.json` |

Key statuses: ACE-Step = validated default music engine (~42 s / 28 s); song validated (~15 min /
4 min); SA3 essence validated (scale 0.40-0.45, seed 42); voix_off validated on 4 engines
(production = Apache-2.0: qwen3/voxcpm2 + Drama 3 Community License < USD 500k/yr — the only
commercially usable Fish engine, 16 GB profile `cpu_expert_layers=24`); voix_robot validated
(17 trials); audio_upscale
validated but **CPU-only RTF ~13 + mono output** (refuse > 24 kHz). **Playful/subjective → always
have it listened to before industrializing.** Dark rock music: known instrumental realism ceiling
(MEMORY_BANK §1.11/§1.22) — minimal descriptions, imposed minor key.

## 5. AI video (sd-cli Vulkan) & utilities

| Workflow | Use | Key inputs | Outputs |
| :--- | :--- | :--- | :--- |
| `video` | T2V / I2V / FLF2V (`--end-img`) / V2V video — Wan 2.1/2.2, LTX-2.5, .webm + Godot scene | `prompt`, `-i`, `--frames` (33), `--fps` (24) | `_vid.webm`, `_player.tscn` |
| `video_vace` | **Motion-locked video**: appearance from ref image (`-i`) + motion from control frames (`--control-video`, skeletons/pose/depth PNGs) — Wan 2.1 14B VACE **LightX2V distilled** (VALIDATED 2026-10-01 "très bien"; plain 20-step recipe REJECTED "nul"). 13 frames @ 16 fps 832×480, 8 steps, cfg 1.0, seed 42, `--offload-to-cpu --vae-on-cpu` baked in (~28 min/clip) | `-i` ref image (required), `--control-video` frames dir (required), `prompt` (motion), `--frames/--fps/--steps/--cfg-scale/--seed` overridable | `_vace.webm` |
| `video_multishot` | **Native multishot video**: several named cuts + continuous soundtrack in ONE LTX-2.5 T2V generation (VALIDATED 2026-10-02 "super": hard cut lands, appearance held, soundtrack generated). 65 frames @ 24 fps 832×480 (1+8k rule, max 81), 8 steps official sigmas, cfg 1.0, `--max-vram 10`, audio VAE, NO negative prompt, pinned LTX binary `DEFAULT_SD_CLI_LTX` 6b3edaa (#1976). ~10 min/clip. Prompt = shots in order + named cut + audio bed (docs.ltx.io rules) | `prompt` (required), `--frames` (65), `--fps` (24), `--seed` (42), `-o` | `_multishot.webm` (VP8 + PCM) |
| `monoplan_ia` | **Single-shot cinematic plan** from image (LTX-2.5 + mci slow-mo + pure zoom) — validated, YouTube hooks | `prompt`, `-i` (or `--monoplan-source`), `--monoplan-frames` (65, max ~81; must be 1 + multiple of 8), `--monoplan-duration` (10 s), `--zoom-debut/--zoom-fin`, `--4k` (3840×2160 AMF master), `--ambiance`, `--carton-titre "LINE1\|LINE2"` | `_1080p.mp4` or `_4k.mp4`, `_avec_ambiance.mp4`, `_final_titre.mp4` |
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

**⚠️ sd-cli build pitfall (state 2026-10-23, MEMORY_BANK §1.16-1.19)**: MiniMax-H3 runs on the
main build again (`C:\SD\`, master-995+) — upstream #1976 (54 segments + OOM at submit, broken
window 864→990) is fixed by #2181 (ggml small-BAR heap mask), validated on the workflow full
path 10-23 (36.2 min exit 0; the stock 54-segment plan is expected and survives). **LTX-2.5 production routes
still require the parallel build** `C:\SD-6b3edaa\` (master-841): the 33 f planner refusal
cleared on 995 (10-23 probe) but the 65 f routes are not yet re-validated there: for `monoplan_ia` / `video_multishot`, prefix
`SD_CLI_PATH="C:\SD-6b3edaa\sd-cli.exe"` (or `--sd-cli`). `h3_ref2va` needs NO override (main
build default). Reliable video on the main build: Wan T2V/I2V ≤ ~20 frames with
`--vae-on-cpu`. Video ESRGAN upscale (`scripts/upscale_video_ai.py`) remains validated. **Always
re-check this state in MEMORY_BANK before a video render.**

## Maintenance (interactive menu 33-35, outside generation)

`update_sd` / `update_llama` / `update_vulkan`: update/Vulkan-compilation managers — but the
official process goes through `scripts/veille_versions.py` + user agreement (see `AGENTS.md` §
Watch & updates). Never automatic updates.
