---
name: generator-assets
description: Generates any media with the local generator-assets factory (C++ Vulkan/GGUF engines, zero PyTorch, zero cloud) — 2D images, sprites, PBR textures, 3D meshes .glb, AI image→3D objects (TRELLIS.2), 360° skyboxes, MakeHuman characters, music loops, TTS voice-over, robot voice, SFX, ambiances, AI video (Wan/LTX/MiniMax-H3) and 4K upscaling, via `uv run python main.py -w <workflow>`. Use this skill whenever the user wants to create, generate or produce any media asset (image, texture, material, 3D model, character, music, sound, voice, video) in this repository or from a consumer repository (ai-doc2video, video-analys-ia), or asks what the factory can do — even if they name no workflow. Provides the need→workflow routing table, the mandatory guardrails (system load check before heavy generation, English prompts, fixed seed) and the validated recipes.
---

# generator-assets — generate media with the local factory

This repository is a **universal local AI media factory**: 40 workflows orchestrated by a single CLI,
executed by C++/GGUF Vulkan engines (sd-cli, llama.cpp, audio.cpp, trellis.cpp, FFmpeg) — no cloud or
CUDA dependency. Your mission when this skill triggers: translate a media need into **the right
workflow command**, respecting the guardrails, then deliver the produced files.

## 1. How to launch a workflow

Always from the repository root (`C:\GIT\generator-assets`):

```bash
uv run python main.py -w <workflow> "<prompt or args>" [options]
```

- `-o <name>`: base name of the outputs (otherwise derived from the prompt);
- `--seed <N>`: fixed seed for A/B reproducibility;
- `uv run python main.py --check`: checks that engines and models are detected;
- `uv run python main.py --interactive`: interactive console (40-workflow menu) for human exploration;
- outputs land in `output/` (or its `<workflow>/` subfolder — since 2026-09-25 the default is `output/` everywhere; `godot_assets/` = validated reference assets only).

The full detail of each workflow (inputs, outputs, options, examples) is in
[`references/catalogue_workflows.md`](references/catalogue_workflows.md) — consult it as soon as the
routing below is not enough (precise options, durations, produced formats).

## 2. Guardrails BEFORE launching a generation

These rules come from `AGENTS.md` and real incidents — they are not decorative:

1. **System load check before any heavy generation** (anything that goes through sd-cli video,
   audio.cpp or trellis.cpp: `video`, `monoplan_ia`, `h3_ref2va`, `music_bg`, `chanson`, AI `sfx`,
   `musique_*`, `voix_*`, `mesh_ia`…):
   ```bash
   uv run python scripts/check_charge_systeme.py
   ```
   Exit 1 = machine busy → **wait for a free slot, do not launch** (documented incident:
   measured RTF 3.3× too slow because of GPU contention).
2. **Only one heavy generation at a time** — AMD RX 6950 XT 16 GB GPU, the engines fight for VRAM.
3. **Model prompts always in English** (image, music, video, voice descriptions — even if
   the user speaks French, the command carries an English prompt).
4. **Always set `--seed`** so you can reproduce/compare.
5. Never launch a generation while a batch is running, and never kill a running
   `audiocpp_cli.exe` / `ffmpeg.exe` / `sd-cli.exe`.

Contract of the consumer repositories (ai-doc2video, video-analys-ia): they call this CLI as a
subprocess with `check=True` from this directory, with load checked + English prompt + fixed seed.
Any CLI evolution must preserve this contract.

## 3. Need → workflow routing

### 🎨 2D image, sprites, UI (Flux.1 Dev / SDXL Vulkan engine)

| Need | Workflow | Example |
| :--- | :--- | :--- |
| Isolated 2D asset (item, monster, scenery, background) | `generate` | `-w generate "healing potion, dark fantasy game icon" -t prop -o potion` |
| Multi-angle sprite sheet of a character | `spritesheet` | `-w spritesheet "goblin scout" -o goblin` |
| Thematic variants (fire/ice/poison…) | `variations` | `-w variations "elemental sword" --themes fire,ice` |
| Tileable texture (TileMap tile) | `tileable` | `-w tileable "mossy cobblestone floor"` |
| Retro pixel art (Pico-8, Endesga-32…) | `pixelart` | `-w pixelart -i image.png --palette pico8` |
| 9-patch frames/buttons | `ui_9slice` | `-w ui_9slice "stone dialog frame"` |
| 47-tile Wang autotile atlas | `autotile_pack` | `-w autotile_pack "cave walls"` |
| Clean cutout (transparent background) | `rembg` | `-w rembg -i image.png` |
| 2x/4x/4K ESRGAN upscale | `upscale` | `-w upscale -i image.png --scale 4` |
| JSON pack of batch generations | `batch` | `-w batch --recipe recipe.json` |

### 🧱 PBR textures & 3D (Flux + DeepBump + Blender + TRELLIS.2)

| Need | Workflow | Example |
| :--- | :--- | :--- |
| Complete PBR material pack + Godot `.tres` | `material3d` | `-w material3d "ancient gothic stone tile with purple runes" -s 1024` |
| Parametric 3D mesh `.glb` (slab, chest, pillar…) | `mesh3d` | `-w mesh3d "ornate iron chest" --shape cube` |
| **AI 3D object with real volume** from prompt or image | `mesh_ia` | `-w mesh_ia "obsidian dragon skull" --res 512` or `-i helmet.png` |
| 360° equirectangular skybox + IBL | `skybox` | `-w skybox "purple cosmic nebula"` |
| Voxel 3D model for GridMap | `voxel3d` | `-w voxel3d -i sprite.png --grid-size 32` |
| **Rigged packed animated animal for Godot** (Quaternius, mocap packs) | `animal_godot` | `-w animal_godot -i wolf.blend -o wolf_godot.glb` — dedicated skill `blender-rig` for AI rigging/animation |
| Orthogonal sheet to model in Blender | `turnaround3d` | `-w turnaround3d "dwarven warrior"` |
| Water/lava flowmap + Godot shader | `flowmap` | `-w flowmap "lava river" --angle 45` |
| Standard CC0 prop or décor plate (YouTube) | `asset_blendkit` | `-w asset_blendkit --query "wooden barrel" --list-assets` |

**`mesh_ia` (TRELLIS.2) — recipe**: iterate at `--res 512` (~11 min), master at `--res 1024`
(~55 min); `--faces-cible 30000` for a Godot prop (10,000 = standard prop, 2-3,000 = repeated
clutter). From a prompt, `mesh_ia` automatically chains `generate` (image → cutout → 3D). Each
output includes a **control contact sheet** (4 EEVEE views) — look at it before delivering, never
ship an unseen GLB.

**3D prerequisites**: these workflows go through **Blender headless** — mandatory for `mesh3d`,
`voxel3d`, `asset_blendkit` and the whole MakeHuman suite (which additionally requires the MPFB2
addon); optional for `mesh_ia` (decimation/contact sheet skipped if Blender is absent). Executable
resolution: `BLENDER_PATH` → PATH → `C:\Program Files\Blender Foundation\Blender 4.0…5.2`; `--check`
detects it. Godot game-ready standards (triangle budgets, `SM_`/`MAT_`/`T_` naming, LOD ratios,
texel density, `-colonly` collision, validation checklist, MPFB/BlendKit pitfalls):
[`references/pipeline_3d_blender.md`](references/pipeline_3d_blender.md).

### 👤 Humanoid characters (MakeHuman / MPFB2)

| Need | Workflow |
| :--- | :--- |
| 2D portrait → full 3D body (.blend/.glb, makeup, Mixamo rig, Cycles renders) | `character3d` / `character_makeup` |
| Modular quad MakeHuman clothing from a theme | `makehuman_clothes` |
| Recolor/retexture of an existing character's wardrobe | `outfit` |
| OpenPose-guided sprite (real ControlNet, validated 26/09) + rigged Godot scene | `pose_control` |
| Multi-emotion portrait gallery for RPG dialogs | `rpg_portrait` |

**Validated pose/animation recipe (2026-09-26, MEMORY_BANK §1.29)**: `pose_control` now
**REALLY** conditions generation on the skeleton via **ControlNet OpenPose SDXL xinsir**
(`C:\Modeles_LLM\controlnet_openpose_sdxl_xinsir.safetensors`, 2.5 GB, `--control-strength 0.9`,
upstream prerequisite PR #1752 present in our pinned binaries) — if the file is missing, automatic
prompt-only fallback. For a **character animation** (multi-frame sprite): choreography of a GLB
rig → COCO keypoints per frame (Blender headless, scripts `scripts/proto_anim_controlnet/`),
frame-by-frame generation with **txt2img + ControlNet 1.0 + IP-Adapter Plus 0.45 on ONE appearance
reference aligned with the prompt**. ⚠️ Measured pitfalls: star-pattern img2img (init = frame 0)
**anchors the pose** (at 0.55 the character stops moving — use txt2img + IP-Adapter); **too-strong
IP-Adapter (≥ 0.7) also crushes the pose** (convergence towards the reference's pose → motionless
character) → stay ≤ 0.5 for a dynamic action; choose a **cyclic choreography, readable from the
side** (Run > Punch — a FRONT-view attack is foreshortened, nearly static 2D skeleton); non-cyclic
loop → assemble as a ping-pong GIF. Cost: ~50 s/frame at 768×1024, VRAM ~9 GB.

→ The detailed guide (absolute UV/`.mhclo` rules, bilingual 177-model catalog) is in
[`GUIDE_AGENT_IA_HABILLAGE.md`](../../../GUIDE_AGENT_IA_HABILLAGE.md) — read it for any MakeHuman
work.

### 🔊 Audio, music, voice (audio.cpp / qwentts.cpp / FFmpeg)

| Need | Workflow | Example |
| :--- | :--- | :--- |
| Background music loop (−30 LUFS bed, game or YouTube voice-over) | `music_bg` | `-w music_bg "dark ambient drone, 70 BPM" --bpm 70` |
| Complete song WITH lyrics | `chanson` | `-w chanson --paroles "..." --style "synthpop"` |
| New music with the DNA of a reference (imposed BPM/key) | `musique_adn` | `-w musique_adn --reference track.wav` |
| Music with the essence of a reference (SA3 init_audio) | `musique_essence` | `-w musique_essence --reference track.wav` |
| Vocal removal / stem separation | `retrait_voix` | `-w retrait_voix -i track.wav` |
| Expressive FR voice-over (qwen3-tts/VoxCPM2/Fish cloning) | `voix_off` | `-w voix_off --texte "..." --voix narrator_fr` |
| EN robot voice (validated kokoro + ringmod recipe) | `voix_robot` | `-w voix_robot --texte "..."` |
| Audio super-resolution → 48 kHz (16k voice / 24k music) | `audio_upscale` | `-w audio_upscale -i voice_16k.wav --upsr-variante speech` |
| Emotional character voice + Godot lip-sync | `tts_dialogue` | `-w tts_dialogue --texte "..." --emotion angry` |
| SFX sound effect (procedural or AI) | `sfx` | `-w sfx "sword swing whoosh"` |
| Seamless loopable sound ambiance | `audio_ambience` | `-w audio_ambience "forest night, wind"` |

**Validated audio recipes**: `music_bg` → `[Instrumental]` (no vocals) for instrumental beds; the
production output is a −30 LUFS bed with possible ducking; `voix_robot` = fixed validated recipe
(kokoro `af_heart`, pitch +30%, ringmod 120 Hz, atempo 0.65, gain −4 dB) — do not improvise other
settings without user agreement; `audio_upscale` = UniverSR CPU validated for voice ("perfect") and
music ("very good") — **slow (RTF ~13) and MONO output**, refuse inputs > 24 kHz (already full
band).

### 🎬 AI video (Wan 2.1/2.2, LTX-2.5, MiniMax-H3 — sd-cli Vulkan)

| Need | Workflow | Example |
| :--- | :--- | :--- |
| Cinematic shot from a still image (slow-mo, designed zoom) | `monoplan_ia` | `-w monoplan_ia -i frame.png --prompt "camera slowly pans..."` |
| Video from prompt or image (Wan/LTX, .webm) | `video` | `-w video "cyberpunk street, neon rain"` |
| **Continue an existing video, image + SOUND** (MiniMax-H3 Ref2VA) | `h3_ref2va` | `-w h3_ref2va -i clip.webm --prompt "..." --turbo` |
| 60 fps interpolation (RIFE) | `rife_interp` | `-w rife_interp -i clip.webm` |
| 4×4 VFX particle sheet | `vfx_flipbook` | `-w vfx_flipbook "fire explosion"` |
| Animated texture/shader loop | `anim_loop` | `-w anim_loop -i texture.png` |
| Style consistency across assets (IP-Adapter) | `ip_adapter` | `-w ip_adapter -i reference.png` |

**`h3_ref2va`: ALWAYS `--turbo`** (distilled 8-step LoRA, user-validated: ~38 min instead of
~70 min for 22 frames, quality ≥ baseline). The 20-step mode is only for explicit quality A/B
requests. 4K YouTube masters go through `scripts/conform_youtube_hd.py`.

**⚠️ Common video pitfall (state as of 2026-09-24 — check `docs/MEMORY_BANK.md` §1.16-1.19 before
any video render, this evolves with sd-cli updates)**: the installed sd-cli (`C:\SD\`, master-908)
**breaks MiniMax-H3** (upstream memory regression: 54 segments instead of 2, OOM at submit ~4 min —
upstream fix #1900 of master-908 changed the splitting (51→54) without fixing it, unchanged from
master-864 to 908, issue #1976 open); **LTX-2.5 passes the 33-frame T2V benchmark on 908 only with
a low desktop VRAM footprint (rebooted machine, fragile ~120 MB margin)** and its 65-frame I2V has
not been retested there. The parallel production build remains `C:\SD-6b3edaa\` (master-841, last
validated for LTX/H3):
```bash
# monoplan_ia: prefix SD_CLI_PATH (resolved via core/config.py):
SD_CLI_PATH="C:\SD-6b3edaa\sd-cli.exe" uv run python main.py -w monoplan_ia ... 
```
For `h3_ref2va`, production also goes through the 6b3edaa build (the workflow may call
`C:\SD\sd-cli.exe` hard-coded → use `--sd-cli` or the raw command documented in MEMORY_BANK
§1.16). Reliable video on master-908: **Wan T2V/I2V ≤ ~20 frames with `--vae-on-cpu`** (`video`
workflow, validated 23-24/09). Rule: **any sd-cli matrix/validation runs on a freshly rebooted
machine** (an LTX/H3 verdict can depend on the VRAM held by the desktop).

## 4. Durations and expectations (RX 6950 XT, order of magnitude)

| Generation | Typical duration |
| :--- | :--- |
| Flux image 1024² | ~1-2 min |
| `music_bg` 30 s loop | ~1-3 min |
| `mesh_ia` res 512 / res 1024 | ~11 min / ~55 min |
| `monoplan_ia` 5 s shot | ~10-30 min |
| `h3_ref2va` 22 frames turbo | ~38 min |

Warn the user about the duration before launching; propose a low-resolution iteration when one
exists.

## 5. After generation

- Deliver the produced file paths (not just "it's done") + the seed used;
- **Subjective rendering (music, voice, aesthetics): systematically submit for user
  listening/validation** before any industrialization;
- Repository rule: a user-validated test becomes a workflow; a non-validated test is recorded in
  `docs/MEMORY_BANK.md` — never create a workflow for a non-validated recipe;
- Operational pitfall encountered → record it in `docs/MEMORY_BANK.md` (section of the relevant
  domain).

## 6. Going further

| Question | Where to look |
| :--- | :--- |
| Full workflow detail (inputs/outputs/options/examples) | [`references/catalogue_workflows.md`](references/catalogue_workflows.md) |
| Game-ready 3D standards (budgets, naming, LOD, checklist), Blender/MPFB/BlendKit prerequisites, pitfalls | [`references/pipeline_3d_blender.md`](references/pipeline_3d_blender.md) |
| Reference doc, showcases, installation procedures | [`README.md`](../../../README.md) § 📦 Complete Workflow Catalog |
| MakeHuman clothing/texturing | [`GUIDE_AGENT_IA_HABILLAGE.md`](../../../GUIDE_AGENT_IA_HABILLAGE.md) |
| Validated stacks & pitfalls per domain | [`docs/MEMORY_BANK.md`](../../../docs/MEMORY_BANK.md) |
| Repository conventions, watch, engine update process | [`AGENTS.md`](../../../AGENTS.md) |
| Local engines (versions, validated commands) | `C:\SD\README.md`, `C:\audio-cpp\README.md`, `C:\ffmpeg\README.md`, `C:\trellis\README.md` |
