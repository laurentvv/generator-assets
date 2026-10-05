# GitHub Research — the ComfyUI ecosystem as a source of workflow ideas

**Date: 2026-09-09** • Method: `gh` search (account laurentvv) — topic `comfyui`,
galleries/awesome-lists, MiniMax-H3/Ref2VA ecosystem, Wan/LTX video, audio, 3D,
production pipelines, official `ComfyUI_examples`, ComfyUI 0.34 release notes.

**Context:** the `h3_ref2va` workflow (MEMORY_BANK §1.16) reproduces in the sd-cli CLI the mechanism
of the ComfyUI node « HR Endless Sampler » (hradec). Goal of this research: catalog the ComfyUI
techniques that can be copied/adapted to our 100% CLI Vulkan/GGUF stack (sd-cli, audio.cpp,
trellis.cpp, ffmpeg), and set up a dedicated watch source (added — see §9).

---

## TL;DR — adaptable ideas, by priority

| # | Idea | Source | Potential gain | Effort |
|---|---|---|---|---|
| 1 | **Ref2VA 8-step Turbo LoRA** (`minimax_h3_ref2v_turbo_8step_v1.0_768p_bf16.safetensors`) via `vid_gen`'s `--lora-model-dir` (the flag already exists!) | [lightx2v/Minimax-h3-Turbo](https://huggingface.co/lightx2v/Minimax-h3-Turbo) (1.3M downloads) | ~2.5× faster on h3_ref2va (8 steps instead of 20); 4 steps available for fl2v | Low (A/B to validate) |
| 2 | **Downscaled continuation reference**: decode the tail, resize to a 32 px-aligned canvas, re-encode as a smaller reference → less reference-attention VRAM → bigger chunks | HR Endless Sampler, param `video_continuation_res` | Longer 1080p chunks on 16 GB | Low (ffmpeg scale before `--ref-video`) |
| 3 | **Audio window that « reaches back »**: the audio reference must END at the junction and cover the audio already played (not restart) for true sound continuity | [ComfyUI-H3-Motion-Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context) (928★) | Musical continuity between chunks (to test on the 18-chunk loop) | Low (WAV cutting) |
| 4 | **Per-chunk prompts written by an LLM/VLM** that analyzes the frames already rendered (Gemma4 mechanism of the HR Endless Sampler); turnkey alternative: Prompt-Rewriter-LoRA (Qwen3.6-27B) | hradec + [lightx2v/MiniMax-H3-Prompt-Rewriter-LoRA](https://huggingface.co/lightx2v/MiniMax-H3-Prompt-Rewriter-LoRA) | Dramaturgical coherence of the endless loop | Medium (local llama.cpp/VLM) |
| 5 | **Bank of 634 full public H3 prompts** + 25 guides (gallery website) | [awesome-MiniMax-H3-cases](https://github.com/SkyNotSilent/awesome-MiniMax-H3-cases) (167★) → [gallery](https://h3-field-notes-production.up.railway.app/en/) | Immediately improve our H3 prompts | None (reading) |
| 6 | **Video FaceRefine**: per-frame face detection + tracking, full-frame crop, regeneration, recompositing (cut detection via PySceneDetect so as not to smooth across cuts) | [ComfyUI-H3-FaceRefine](https://github.com/Carasibana/ComfyUI-H3-FaceRefine) (355★) | Repair small/distant faces in H3 videos (YouTube channel) | Medium (ffmpeg crop + sd-cli img2img/ip_adapter) |
| 7 | **H3 for still images**: generate a short frame pack, decode, keep one frame (audio VAE unneeded) — with turbo LoRA = fast stills with character reference | [ComfyUI-MiniMax-H3-Image-Studio](https://github.com/astropuzzo/ComfyUI-MiniMax-H3-Image-Studio) (136★) | Reference-based image editing, character consistency | Low |
| 8 | **`production.json`-style production serialization**: state/approvals/stale/QC, routing by T2VA/I2VA/FL2VA/Ref2VA mode, semantic-reference vs keyframe distinction | [short-drama-production](https://github.com/suihe1/short-drama-production) (148★) | Orchestration framework for the YouTube channel (episode → shots → QC) | Medium |
| 9 | **LTX IC-LoRA** (depth/pose/edges/HDR/**DubIt**/upscaler/motion-track) — the sd-cli LoRA flag exists for `vid_gen` | [ComfyUI-LTXVideo](https://github.com/Lightricks/ComfyUI-LTXVideo) (4120★) | Camera/motion control and dubbing on LTX-2.5 | Medium (to test on GGUF Q4) |

---

## 1. MiniMax-H3 / Ref2VA — the most active ecosystem (everything created since July 2026)

### 1.1 Turbo LoRA — track no. 1 (immediate test possible)

- HF repo: `lightx2v/Minimax-h3-Turbo` (1.31M downloads, ♥876) — files:
  `fl2v_turbo_{4step v0.1→v1.2, 8step v1.0}` and **`ref2v_turbo_{4step v0.1, 8step v1.0}`**,
  variants `*_768p_bf16` and `_comfyui_bf16` (ranks resized for ComfyUI — take the
  **non-comfyui** ones for sd-cli). Mirrors: `larryvrh/MiniMax-H3-Turbo-Lora` (389k downloads),
  `drbaph/...-ComfyUI`, and a **merged model** `MATLOWAI/minimax-h3-fused-turbo-int8-convrot`
  (turbo already merged into the weights, no LoRA to load).
- Cross-benchmarks (Kablex): native dense H3 50 steps ≈ 650 s (RTX 4090); **dense turbo LoRA
  4 steps ≈ 190 s**; VSA 4 steps ≈ 72 s. On our RX 6950 XT (70 min per 22-frame chunk),
  moving 20 → 8 steps would be ~2.5×, 20 → 4 steps ~5× (4-step ref2v = immature v0.1,
  prefer 8-step v1.0).
- **sd-cli feasibility: OK in principle** — `sd-cli vid_gen` exposes `--lora-model-dir` and
  `--lora-apply-mode auto` (`at_runtime` mode on a quantized model). Invoke via the tag
  `<lora:nom:1.0>` in the prompt, as with images. Watch points: Q4_K_M base + bf16 LoRA
  (mandatory quality A/B vs current output), CFG probably to be lowered (≈1) as on the
  other turbos, 768p resolution for the `768p` variants.
- To be recorded per the AGENTS.md rule: test → submission for listening/validation → only
  then workflow + MEMORY_BANK.

### 1.2 HR Endless Sampler (hradec) — beyond what we reproduced

Our `h3_ref2va` reproduces the chaining; the original node does **more**, and these mechanisms are
transferable to our 18-chunk loop (commit 89a82ff, not yet run):

- **LLM planning**: Gemma4 12B QAT analyzes the full prompt + all the references,
  plans the action/timing of EACH chunk, then **analyzes the frames already rendered** and
  writes a small dedicated prompt per chunk (continuity/coherence). → On our side: llama.cpp + local GGUF VLM
  (we already have Qwen3-VL 32B for H3!). Or the dedicated LoRA `lightx2v/MiniMax-H3-Prompt-Rewriter-LoRA`
  (Qwen3.6-27B base, `infer.py` + `prompt_template.py` provided).
- `video_continuation`: 22 frames carried over from the previous chunk (min 5), passed to H3 as
  synchronized `<Video N>`/`<Audio N>` — matches our ffmpeg tail.
- **`video_continuation_res`**: reduces the size of the reference block (decode → resize canvas
  to 32 px-aligned → re-encode) to save reference-attention VRAM and allow
  bigger chunks; the audio and the boundary keyframe stay full resolution. → On our side:
  downscale the `--ref-video` frames via ffmpeg (`scale=` aligned 32) before passing them.
  **⚠️ Precision after reading the sd-cli sources (2026-09-09)**: sd-cli already resizes the
  reference toward a 768 px base nominal (ceiling 768×1344, aligned 32) and keeps the source
  size ONLY if smaller — prior downscaling therefore shrinks the reference latent only
  **below** that nominal (e.g. 4K × 0.15 → 576×320). Implemented as the `--ref-scale` option
  of the endless proto; a `--ref-video-res` flag on the sd-cli side would be cleaner (draft:
  `docs/brouillons_issues_sdcli.md`). Other source discovery: the reference folder is truncated
  17k+5 (12 → 5) and **only the first 5 frames are encoded** → `--ref-frames 5` in the proto
  puts the reference frames exactly on the junction (encode ÷ ~2.4).
- **Automatic boundary keyframe**: the last 5 frames of the previous chunk serve as a
  small junction keyframe (internal to the H3 latent — not reproducible in CLI as long as sd-cli
  does not expose anchoring, see §1.3).
- `gemma4_mtp`: 4-token MTP speculative decoding (performance of the « director » LLM) — relevant if we
  attach a llama.cpp.
- The project plans an **LTX 2.5 port** « in the near future » — to be followed (watch in place).

### 1.3 ComfyUI-H3-Motion-Context (NikoDemon80, 928★) — bit-exact chaining

Clean chaining: the tail of the previous clip is **sliced in the latent** (no
decode/resize/re-encode) → zero color drift/softening over long chains. On the audio side:
the anchor must **end at the junction and reach back into the audio already played** — that is the difference
between « the model continues the track » and « the model writes something that resembles it ».
It includes a « Seam Probe » that measures whether a junction is a true continuation. Requires ComfyUI
0.34+ (anchors at arbitrary frames `MiniMaxH3AddGuide`).
→ **Adaptable now**: the audio lesson (WAV window that reaches back) applies to our
`--ref-video-audio`. Latent slicing would require an sd-cli evolution (potential feature request
to open with leejet: « latent carry-over / tail slice for Ref2VA »).

### 1.4 Timestamped semantic references (ethanfel, 9★ but a clean idea)

`ComfyUI-MiniMaxH3-Timed-References`: presents images **to the Qwen text encoder only**
(semantic, no native reference slot, no VAE encoding) — `<Picture N>` untimed or
timed (« at 2 s, show the red car »), and even frames chosen from a video with their
real PTS. → A transferable prompt-engineering technique **if sd-cli someday exposes images
in the H3 prompt** (today our Qwen3-VL sees only the text); otherwise keep it as a
feature request. It is the right gesture for a « shooting plan »: timestamped intent images.

### 1.5 Hybrid Loader fl2va+ref2va (scottmudge, 165★)

Substantiated finding: the raw output of `ref2va` suffers from a confirmed training quality problem
(minimax), while `fl2va` is cleaner; >97% of the weights are identical, only the
`adaln_proj` (modality routing) differ. Community-validated recipe: **fl2va base +
overlay of only ref2va's `adaln_proj` (blocks 25–49)** = fl2va quality + reference capability.
→ On our side: offline fusion of the int8 safetensors (~19.5 GB each, mmap) then GGUF conversion
— heavy but feasible; to consider if ref2va quality blocks user validation.
(a community GGUF variant already visible on HF: `t8star/…DasiwaREF2VAHybridV1_0…`).

### 1.6 FaceRefine (Carasibana, 355★)

H3 renders faces poorly when the head is small in the frame (a resolution-independent
property). Pipeline: per-frame detection + tracking, normalized full-canvas crop, re-generation
by H3, recompositing; **hard-cut detection** (PySceneDetect) so as not to smooth across cuts.
→ CLI-adaptable: ffmpeg/opencv detect-crop-track + sd-cli (img2img + identity ip_adapter) +
ffmpeg overlay composite, per shot. Use case: YouTube channel (distant talking-head shots).

### 1.7 H3 for still images (astropuzzo, 136★)

Generates a short frame pack → decode → selects one frame: gives **T2I/I2I/reference-based
editing** at H3 quality (the audio VAE is not required). With turbo LoRA it is fast.
→ Adaptable: a short `vid_gen` run + ffmpeg extraction of the best frame; useful for images with
a consistent character reference ( channel thumbnails/visuals, stylized game assets).

### 1.8 H3 prompt tools (to read before the next video session)

- **awesome-MiniMax-H3-cases** (167★): web gallery of **1818 playable videos + 634 full public
  prompts + 25 practical guides** — the best source of H3 prompt grammar.
- `duckyshell/ComfyUI-MiniMaxH3-Prompt-Writer` (166★), `lololerigolo60/Minimax-H3-prompt-studio`
  (23★), `wodeshijie1234/faithful-h3-web` (15★): structured editors for T2VA/I2VA/FL2VA/L2VA/Ref2VA.
- `klfzqxs/ref2va-h3-video-optimizer` (11★): **hill-climbing prompt optimizer** — the LLM writes
  the script → translates it into a ref2va prompt → renders in ComfyUI → extracts frames/audio → the LLM grades → iterates
  (prompt = only variable, seed/params fixed). → Transferable with llama.cpp as judge
  (YouTube channel: shot-prompt improvement loop, controlled GPU budget).
- `seesee75-commits/ComfyUI-MiniMaxH3-Director` (285★), `j955229/…Motion-Director` (97★),
  `karuvanan/MiniMax-H3-Director-Cut-Studio` (112★): timeline/storyboard editors on top of
  H3 (Qwen3 TTS included in Director-Cut) — UX inspiration for a future `main.py -w episode`.

### 1.9 CUDA accelerations — NOT adaptable (note and ignore)

`Kablex/ComfyUI-Ref2VA-VSA` (91★, 75% sparse attention, 4 steps, 13.5 GB),
`Saganaki22/ComfyUI-VDN-H3` (198★, Video Delta Net), `ComfyUI-sol-attn`, DLSS5/NGX nodes.
All require CUDA/Triton kernels — outside the Vulkan scope. The only lesson worth keeping is
« 4–8 steps are enough » (see turbo LoRA).

## 2. Wan / LTX

- **VACE** (Wan 2.2): `vace_reference_to_video.json` in the official ComfyUI examples =
  all-in-one reference→video (control, editing, video inpainting). **sd-cli does not support
  VACE** → leejet feature request to open if Wan video editing is ever needed.
- Wan camera control: `camera_image_to_video_wan_example.json` (official examples).
- **LTX IC-LoRA** (official Lightricks repo, 4120★): LTX-2.3 distilled workflows with
  « In-Context » LoRAs — depth + pose + edges, **motion tracking**, **HDR**, **DubIt** (automatic
  dubbing), pixel spatial upscaler. The `--lora-model-dir` flag exists on sd-cli `vid_gen` →
  test an IC-LoRA on our LTX-2.5-Distilled Q4_K_M.
- `MajoorWaldi/ComfyUI-Majoor-OmniCam` (58★): camera layout/animation (inspiration for
  camera vocabulary in prompts).
- `kakachiex2/comfyui-ltx2-efficient` (25★): efficient low-VRAM LTX-2 sampler (reference for
  low-VRAM steps/CFG settings).

## 3. Audio / voice

- **MMAudio** (`hkchengrex/MMAudio`, 2268★ + kijai wrapper 574★): high-quality synchronized
  video→audio — would fill the silent Wan/LTX outputs (H3 Ref2VA has native audio, Wan/LTX do not).
  PyTorch: not GGUF/Vulkan → idea only (or audio.cpp watch for a possible family).
- **ACE-Step-ComfyUI** (official, 79★): cloud/local modes + **LLM-driven
  sample generation**. Notably: `hackall360/ACE-Step-ComfyUI-LoRa-Trainer` (5★) — **ACE-Step LoRA
  training**: a serious track for breaking the « pop ceiling » (§1.11 MEMORY_BANK) by training
  a gothic rock LoRA (requires PyTorch/GPU training — outside the current stack, to keep in reserve).
- **Breeze-TTS-2** nodes (Saganaki22, 66★): voice clone / voice design / bilingual direction.
- **LatentSync** (bytedance, 6056★): video lip-sync; `aigcpanel` (5533★): digital human
  (video+voice+cloning synthesis). For the YouTube channel if a virtual presenter becomes
  relevant (PyTorch, outside the stack — noted for the record).

## 4. 3D / characters

- **ComfyUI core 0.34 integrates TRELLIS2** (kijai PR #14718, with Pixal3d and Sam3d-body):
  confirmation that our TRELLIS.2 bet (trellis.cpp) is in the mainstream.
- **Photoshoot** (ralksta, 76★): « Person Builder » with 44 fields (body/face/hair/makeup/
  clothing) → compiled English prompt, then a **whole coherent series** (framings/poses/expressions
  vary, the person stays) + measured B&W/color style matrices. → Direct idea for a
  `portrait_serie` workflow: JSON character sheet → prompt compiler → N variations
  (Flux/SDXL + ip_adapter) — extends `rpg_portrait`/`character_makeup`/`turnaround3d`.
- `ComfyUI-3D-Pack` (3860★), `ComfyUI-Hunyuan3DWrapper` (1040★): image→3D ecosystem
  competing with/akin to TRELLIS — passive watch.

## 5. Production pipelines (YouTube channel)

- **Pixelle-Video** (ATH-MaaS, 27,930★): topic → script → AI illustrations/videos → voice-over →
  BGM → editing, in one click. Our equivalent exists as building blocks (`voix_off`, `music_bg`, `video`,
  `conform_youtube_hd`) — the architecture (sentence/scene splitting, visual templates, queue)
  is a good orchestration reference.
- **short-drama-production** (suihe1, 148★): a **traceable** production « skill »: `production.json`
  (tasks, approvals, failure causes, rough-cut, QC), `stale` propagation when an upstream asset
  changes, samples before paid generation, **T2VA/I2VA/FL2VA/Ref2VA routing** and the
  semantic-reference vs keyframe distinction. → Model for industrializing the channel (several dozen shots).
- **open-video** (117★): « Ollama for H3 » (install/pull/run) — keep the `--dry-run` idea
  (plan/validate without consuming GPU) that our workflows already have (`dry_run`): to be generalized.
- `reelforge` (60★): GitHub repo → finished vertical reel (source→video); `MeiGen-AI-Design-MCP`
  (1746★): video design MCP; `Calliope` (144★), `Mix-Studio` (282★): local studios.

## 6. Misc tooling

- **ComfyUI-to-Python-Extension** (2379★): translates a ComfyUI workflow into Python code — speeds up
  our « translations » of ComfyUI workflows → sd-cli recipes (like h3_ref2va).
- **LanPaint** (1386★): retraining-free inpainting for any SD model (video included) —
  depends on whether sd-cli someday adds H3 per-token masks (see §7).
- IC-Light (kijai, 1158★): object/character relighting — idea for game-asset packshots.
- SeedVR2 VideoUpscaler (2827★), GIMM-VFI (477★): video upscaling / interpolation (we have
  RIFE + sd-cli upscaling already — sufficient equivalents).
- Workflow galleries to mine: `ZHO-ZHO-ZHO/ComfyUI-Workflows-ZHO` (7802★),
  `yolain/ComfyUI-Yolain-Workflows` (2200★), official examples `ComfyUI_examples`
  (video/wan/ltxv/audio/3d… folders).

## 7. ComfyUI core v0.34 — signals of what sd-cli could add

Points relevant to us in the 2026-08-26 release notes:
`MiniMaxH3AddGuide` (image/audio anchors at arbitrary frames); **per-token noise masks for
video AND audio on H3** (= video+audio inpainting); H3 prompt embeddings (bypassing Qwen at
runtime); TRELLIS2/Pixal3d/Sam3d-body support; **Wan 3.0** partner nodes; HDR/AV1/mkv/webm
saving; « taeh3 » (H3 mini-VAE preview). Core releases = a good predictor of the
sd-cli evolutions to request/track.

## 8. Proposed actions (suggested order)

> **Progress point as of 2026-09-09 (evening)**: actions 1, 2(a+b), 3 and 4 done;
> remaining are 2(c) (per-VLM prompts) and 5 (medium term).

1. **8-step ref2v turbo LoRA test** (AGENTS rule: never a workflow before validation) —
   recipe: download `minimax_h3_ref2v_turbo_8step_v1.0_768p_bf16.safetensors` (parallel
   downloader if large), A/B same seed/params as §1.16 with `<lora:…:1.0>` + 8 steps + low CFG,
   submit to the user.
   ✅ **DONE — user-validated (« very good quality, sound very good ») → `--turbo` flag of the
   `h3_ref2va` workflow (38 min vs 70; MEMORY_BANK §1.16).**
2. Endless loop: integrate (a) downscaled 32 px-aligned reference, (b) audio window that
   « reaches back »,
   (c) per-chunk prompts by a local VLM (or Prompt-Rewriter-LoRA) before the 18-chunk go/no-go.
   ✅ **(a)+(b) DONE** — options `--ref-scale` / `--ref-frames` / `--ref-audio-sec` of
   `scripts/proto_endless_h3.py` (defaults = validated recipe; 3 × 2-chunk probe protocol
   in `docs/proto_endless_h3.md`). ⏳ **(c) remaining** (local VLM or Prompt-Rewriter-LoRA —
   the official grammar distilled in §1.16 is the direct complement).
3. Read the awesome-H3-cases gallery (634 prompts) and distill from it an H3 prompt mini-guide
   (FR → EN grammar) into MEMORY_BANK §1.16.
   ✅ **DONE** — the full official grammar distilled from the duckyshell Prompt-Writer guides
   (base + full-reference): mini-guide in MEMORY_BANK §1.16 (the web gallery itself does
   not give the grammar in plain form; it is the repo guides that carry it).
4. leejet feature requests (sd-cli): Ref2VA latent carry-over (tail slicing), semantic
   images in the Qwen H3 prompt, VACE Wan 2.2.
   ✅ **PUBLISHED on 2026-09-09** (after a zero-duplicate check):
   [#1951](https://github.com/leejet/stable-diffusion.cpp/issues/1951) (reference resolution +
   latent carry-over), [#1952](https://github.com/leejet/stable-diffusion.cpp/issues/1952)
   (Qwen TE semantic images), [#1953](https://github.com/leejet/stable-diffusion.cpp/issues/1953)
   (VACE Wan 2.2) — bodies archived in `docs/brouillons_issues_sdcli.md`.
5. Medium term: FaceRefine CLI; portrait_serie (Photoshoot inspiration);
   production.json (short-drama inspiration) for the channel.

## 9. Watch added (`scripts/veille_versions.py`, `comfyui` section)

New « ComfyUI ecosystem » source, 3 streams (same mechanism as the existing sources,
baseline on first run):
- **`comfyui-core`**: releases of `comfyanonymous/ComfyUI` (notes archived in
  `output/veille/notes/`) — flags new families/nodes (see §7);
- **`comfyui-<repo>`**: last commit of a curated list — `hradec/ComfyUI-HR-Endless-Sampler`,
  `NikoDemon80/ComfyUI-H3-Motion-Context`, `comfyanonymous/ComfyUI_examples`,
  `Lightricks/ComfyUI-LTXVideo`;
- **`comfyui-nouveaux-repos`**: diff of the top-starred `topic:comfyui` repos created in the
  last 45 days (≥20★) — detects new H3/node packs like the ones cited here.

## 10. 2026-09-22 — Evaluation of the 4 new repos flagged by the watch (`comfyui-nouveaux-repos`)

Rolling evaluation of the 4 repos surfaced by the 09/22 watch (stars as of 09/22);
verdict relative to our Vulkan CLI stack and to MEMORY_BANK.

### `ruashots/open-h3-ir` (60★) — ⭐ the only directly actionable idea

A **Context-IR compiler for MiniMax H3** — the layer MiniMax described as critical
(« H3-Context-IR is critical to the quality of the final output ») but **never open-sourced**:
it only existed through their hosted service. This project reimplements it locally and talks
to **any OpenAI-compatible endpoint** (llama.cpp server, Ollama, vLLM…), with no GPU
of its own (the LLM lives on the endpoint). What a Context-IR produces: a structured document
with named sections in a fixed order, each topic tied to a numbered image label, cut times
laid on a legal frame grid.

- **Direct connection** with our work: the H3 grammar distilled in MEMORY_BANK §1.16, and
  action (c) of the endless proto (§8: « local VLM or Prompt-Rewriter ») — open-h3-ir IS a
  ready-made H3 prompt-rewriter. The README describes the document format, usable
  even without installing the compiler (manual restructuring of our h3_ref2va prompts).
- **Possible action** (not urgent): test the Context-IR structure on our recipe
  h3_ref2va --turbo (A/B with the existing OmniCam/AICG3D protocol: same Flux anchor, same
  seed), as a possible prelude to a real local LLM coupling (qwentts server / llama.cpp) →
  automatic compiler. ComfyUI nodes in a separate repo (`ruashots/ComfyUI-OpenH3-IR`).

### `jplenio/ComfyUI-MiniMax-Music-Production-Toolkit` (61★) — ❌ core already closed on our side

ComfyUI music toolbox: generation (YuE2/MiniMax Music 3), **cover from the real score**
(SheetSage2 transcribes the melody/chords/sections of the source track → ABC rewrite with a
freedom slider → regeneration), enhancement (FlashSR), mastering, metadata/export.
- The **flagship feature (cover via score) = explicitly « cover territory, definitively
  rejected »** on our side (MEMORY_BANK §1.11: ACE-Step cover « the clone: horrible »,
  SA3 essence rejected; and the verbatim YuE2 verdict of 2026-09-13: « the coupling
  SheetSage2→ABC→cot=melody = cover territory, definitively rejected »). Do NOT propose
  a test — unless the user someday reopens the cover topic, in which case the
  « transcribe the real score BEFORE regenerating » approach is the only avenue that makes sense.
- The rest is covered or marginal: mastering = our FFmpeg loudnorm recipes (FFmpeg
  README), super-resolution = audio.cpp's `audiosr` family; metadata/cover art = out of
  scope. The music3/yue2/sheetsage2 families are already present in audio.cpp `model_specs` if
  needed.

### `Saganaki22/ComfyUI-Hyperflow` (55★) — 👁 watch, not actionable

ComfyUI port of the 8-step LoRA **HyperFlow from Video Rebirth** for MiniMax-H3 (video+audio):
rank-256 LoRA + **double `(t, r)` conditioning** per step (conditioned on the integrated
interval, `r = 1 - sigma_next`). Key points:
- Our validated turbo (`--turbo` h3_ref2va, MEMORY_BANK §1.16) = the **lightx2v** LoRA
  `minimax_h3_ref2v_turbo_8step_v1.0_768p_bf16` — ANOTHER 8-step LoRA, already validated.
- Without the `(t, r)` double conditioning (exclusive to the ComfyUI node), the standalone builds
  (HF `drbaph/MiniMax-H3-Turbo-Lora-ComfyUI`, 3.93 GB backbone / rank-20 ~318 MB) **become
  the published model** → no demonstrated advantage for sd-cli, which cannot do this
  conditioning. To re-examine if: ① Video Rebirth publishes a complete standalone path,
  ② sd-cli implements the (t, r) conditioning, ③ a lightx2v vs full
  HyperFlow quality comparison appears. The repo's `sol-attn` topic = an attention lead to watch as well.

### `mkamranr/reelforge` (66★) — out of scope here, 2 ideas for ai-doc2video

URL → vertical reel pipeline (LLM script → Fish-Speech TTS → storyboard → 1080×1920 render →
encode check), self-hosted. Vertical format = not our case (YouTube 4K landscape), but:
- ① **a master-conformance verification step before publishing** (H.264 High @4.1,
  CRF, AAC bitrate, target LUFS) — transferable as an FFmpeg/ffprobe check in the
  ai-doc2video chain (we already have the loudnorm recipes on the C:\ffmpeg side);
- ② the architecture of « each step produces a reviewable artifact before the next » —
  a pattern our endless proto comes close to, to keep in mind for long chains.
## 11. 2026-10-02 — The OFFICIAL template gallery as a mining source (`Comfy-Org/workflow_templates`)

User-shared link, triaged as the **canonical upstream feed** the §9 watch was missing: the
repo hosting every workflow shown in ComfyUI's template picker (1231★, pushed daily,
1 231 templates + subgraph blueprints + browsable site <https://comfy.org/workflows>).

**Method**: sparse clone (JSONs only) at `C:\IA\workflow_templates` —
`git clone --depth 1 --filter=blob:none --sparse` + `sparse-checkout set templates`.
Inventory: 690 workflow JSONs = **390 local** (the minable ones) + 300 `api_*` cloud nodes
(ByteDance/ElevenLabs/Bria… — out of scope, zero-cloud rule). Categories: image 80+,
video 130+, utility 48, **audio 40**, 3D 10, llm 4. Templates are ALSO the reference for
widget values (official-recommended params: e.g. the ACE-Step 1.5 turbo graph ships the
full `TextEncodeAceStepAudio1.5` payload: tags format, lyrics blocks, BPM, key, guidance
0.85/0.9, seed policy).

**Map of the families that touch OUR validated engines** (mining priorities):

| Family | Templates | Link to our stack |
|---|---|---|
| ACE-Step 1.5 | `audio_ace_step1_5_xl_{base,sft,turbo}`, `checkpoint`, **`split`, `split_4b, split_llm`** (subgraphs), `m2m_editing` (v1) | our `acestep` workflow = text2music only; the rejected edit/extract routes might be revived with the official graphs' exact params |
| Yue2 | `audio_yue2_text2music`, **`audio_yue2_music_cover`** | Yue2-3B installed; cover route = candidate for style transfer (gothic) |
| MiniMax-H3 | `h3_t2v` ×2, `h3_i2v` ×2 | our `h3_ref2va`/monoplan engine — compare conditioning params |
| Wan VACE | `wan_vace_14B_{t2v,v2v,ref2v,inpainting,outpainting,flf2v}` | our `video_vace` workflow; **flf2v** (first-last-frame) = the missing control we don't have |
| LTX-2 | `video_ltx_2_audio_to_video` | audio→video = inverse of our monoplan chain |
| Stable Audio 3 | `audio_stable_audio_3_medium{,_base}` | same models as our audio.cpp `stable_audio` (params comparison) |
| Chatterbox | `tts` + `dialog` + `multilingual` + **`vc`** (voice conversion) | character-voice pipeline candidate (vs rejected VeVo2) |
| 3D | `moge_{panorama,perspective}_to_mesh` (mono-geometry→mesh!), `pixal3d_trellis2_image_to_model` | TRELLIS.2 = our `mesh_ia` engine; moge = new capability class |
| Music video | `wan2_1_infinitetalk_music` | talking/singing head driven by an audio track — ai-doc2video hook |

**Next mining steps (on request)**: ① extract the ACE-Step 1.5 `split*`/`m2m_editing`
subgraph payloads → compare against audio.cpp's ace_step request-options; ② Wan VACE
`flf2v` graph → feasibility on sd-cli (first-last-frame conditioning flags?);
③ `moge` → check GGUF-ability. Repo updates daily — re-sync = `git pull` in the sparse
clone; no veille_versions.py source added (research source, not an update feed).

## 12. 2026-10-05 — Evaluation of the new repos flagged by the watch (lots 2026-10-04 + 2026-10-05)

Four `comfyui-nouveaux-repos` flags triaged together: the 2026-10-04 pair (reshot, Picxel) had
slipped through without evaluation and the 2026-10-05 pair (LoRAlab, Omnichar) replaced it in
`maj_en_attente.json`. Verdict for all four: **ideas only, no action now** — none is runnable on
the local stack (PyTorch/ComfyUI, NVIDIA CUDA), per the zero-PyTorch philosophy; concepts kept
for when a CLI/Vulkan equivalent exists.

| Repo | ★ | What it is | Verdict for our stack |
|---|---|---|---|
| [maosika-ai/reshot](https://github.com/maosika-ai/reshot) (10-04) | 47 | "Copy the shot, not the actors": video → depth map / OpenPose skeleton / canny lines, as control references for Seedance 2.0, H3 Fun ControlNet, Wan VACE — Apache-2.0 | Same family as TL;DR ideas #2/#6 (shot-derived conditioning). Depth/pose extraction feeding `vid_gen` control paths is an adaptable concept — revisit only if shot-driven motion control becomes a need. |
| [See-Sol-Lab/Picxel](https://github.com/See-Sol-Lab/Picxel) (10-04) | 38 | Reference images → pixel-art game assets, for indie devs | In scope for L'Héritier du Vide sprites, but ComfyUI/PyTorch. CLI equivalent = sd-cli img2img at low res + palette/upscale post-processing (ffmpeg). Idea noted. |
| [AcademiaSD/AcademiaSD_LoRAlab-TrainerStudio](https://github.com/AcademiaSD/AcademiaSD_LoRAlab-TrainerStudio) (10-05) | 51 | One-install LoRA trainer: **Qwen-Image 2.1**, FLUX.2 Klein 9B, Krea 2, Z-Image, Ideogram 4, Anima, SDXL (Pony/Illustrious/NoobAI), LTX 2.3, **MiniMax-H3** — NVIDIA 4-8 GB VRAM | Targets our exact ecosystems (freshly-merged qwen compositing, `h3_ref2va`) but PyTorch/CUDA-NVIDIA → unusable as-is on the RX 6950 XT. Concept kept: a self-trained compositing LoRA on our own cutouts; the philosophy-compliant path would be C++/Vulkan frozen-base training (cf. sa3.cpp v0.1.1's Vulkan BF16 OUT_PROD training support, same day). |
| [omnichar/ComfyUI-Omnichar](https://github.com/omnichar/ComfyUI-Omnichar) (10-05) | 40 | `.char` file format: exports refmode, LoRA adapters, guided prompts for a consistent character | A portable character-consistency bundle fits both the game (recurring characters) and the channel; sd-cli equivalent = a documented convention reusing the existing LoRA/prompt flags. Idea noted. |
