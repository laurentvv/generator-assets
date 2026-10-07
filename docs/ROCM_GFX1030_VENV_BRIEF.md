# Prompt brief: proven ROCm PyTorch environment for this machine (gfx1030 / RX 6950 XT)

> Paste this file as the kickoff message for an agent session in this repo.
> Source of every claim below: ella-swap (`C:/GIT/ella-swap`, AGENTS.md §7 lessons +
> `docs/EMV3_PATCHES.md`), measured 2026-10-05 → 2026-10-07. Nothing here is guessed.

## Machine & GPU reality

- Windows 11, Git Bash shell, `uv` only (never `pip install`, never `requirements.txt`).
- GPU: **AMD Radeon RX 6950 XT** (RDNA2, gfx1030, 16 GB VRAM). **NO CUDA** — never suggest
  CUDA wheels, Colab, or flash-attn. Native **ROCm on Windows** works (validated path below).

## The proven environment (reference install)

`C:/GIT/ella-swap/tools/rocm_venv_emv3` — verified versions on 2026-10-07:

| Package | Version |
|---|---|
| python | 3.10.21 |
| torch | **2.11.0+rocm7.13.0** (HIP visible on the 6950 XT) |
| torchvision | 0.26.0+rocm7.13.0 |
| transformers | 4.57.1 |
| diffusers | 0.35.0 |
| huggingface-hub | 0.36.2 |
| accelerate | 1.15.0 |
| safetensors | 0.8.0 |
| numpy | 2.2.6 |

Wheels come from AMD's index: `uv pip install --index-url https://repo.amd.com/rocm/whl/gfx103X-all <pkg>`
(the `rocm-sdk-libraries-gfx103x-all==7.13.0` SDK is pulled in automatically with torch).
Newer 2.10/2.11 wheels live on the same index — prefer them over the old 2.9.1.

**That reference venv is PRODUCTION (ella-swap EchoMimicV3 renders). Do NOT install anything
into it. For a new engine here, create its own `uv` venv with the same recipe** — expect
~4-5 GB per venv (the torch ROCm wheel dominates).

## What it can run

Any PyTorch model that (a) fits 16 GB planned in **bf16**, and (b) has no hard CUDA-only
dependency. Proven or plausible on this card:

- Image generation/edit: SDXL, Flux (incl. GGUF quants), Qwen-Image-Edit-2511 (recipe already
  proven on this machine), diffusion-based upscalers.
- Face restoration: Real-ESRGAN (proven via `sd-cli.exe`), GFPGAN, CodeFormer.
- Audio/video utils: RIFE interpolation, Demucs stems, Whisper (PyTorch builds), Chatterbox
  (official python), wav2vec-style audio encoders.
- Talking heads: EchoMimicV3-Flash-pro in production (36 min per 6 s @ 512², 8 steps).
  Other 1.3B-class audio-driven models are in scope; 14B models are NOT (bf16 ≈ 28 GB).

## Hard blockers (do not retry, they are paid-for lessons)

- **flash-attn, xformers, bitsandbytes, triton, DeepSpeed, apex**: CUDA-only binaries — a model
  that hard-requires them is dead on RDNA2. Many models merely *optionally* use them; strip the
  requirement instead of installing.
- **No FP8/WMMA on RDNA2**: translate every "FP8 ~11 GB" recipe to bf16 (~2× weights) before
  planning VRAM.
- **`torch.distributed` does not exist** in the Windows ROCm wheel: guard `dist.is_available()`
  in vendored code that imports it at module level.

## Measured traps (each one caused a real failure before being fixed)

1. **WDDM commit wall**: GPU allocations consume *system commit* (RAM + pagefile), not just
   VRAM — an OOM with 9+ GiB VRAM "free" is usually commit exhaustion. Check commit before big
   loads (abort < ~14 GiB available for 1.3B-class loads). Load checkpoints with
   `torch.load(..., mmap=True, weights_only=True)`; never `pipeline.to(device)` a pipeline
   holding a T5+CLIP on 16 GB — place modules individually; `del state_dict; gc.collect()`
   right after each load.
2. **diffusers >= 0.34 moved `load_model_dict_into_meta`** from `diffusers.models.modeling_utils`
   to `diffusers.models.model_loading_utils` — vendored upstream loaders fail the import
   *silently* and fall back to full fp32 materialization (~45 GB commit spike). Add the import
   fallback + `accelerate` (needed for `init_empty_weights`), and materialize any meta-device
   keys the checkpoint does not cover.
3. **SDPA is math-only** in the Windows ROCm wheel (no flash/efficient/cuDNN backends):
   long-sequence attention materializes B×H×Q×K (67.7 GiB at 512²×150f). Chunk the queries
   (2048-token steps — proven patch in ella-swap `tools/EchoMimicV3/src/wan_transformer3d_audio_2512.py`).
4. **MIOpen**: the first run of each new network pays kernel tuning (expect minutes); on cache
   corruption after an OOM you get `hipErrorInvalidImage` → wipe `%TEMP%/MIOpenConvDirUni-*.cli`.
   Set `MIOPEN_FIND_MODE=FAST` for steady-state runs.
5. **NEVER run a VAE decode on the GPU on this machine**: it hard-freezes the entire PC
   (system freeze, not a process crash). Decode in an isolated fresh CPU process, always.
6. Rich progress bars crash logged runs on cp1252 → `export PYTHONIOENCODING=utf-8 PYTHONUTF8=1`
   before any redirected run. Other useful vars: `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`,
   `OPENBLAS_NUM_THREADS=8`, `OMP_NUM_THREADS=16`.
7. Do not trust memorized VRAM/speed claims (and treat AI deep-research tables as leads, not
   facts): fetch the upstream docs/model card first (§6), then measure on this card.

## Method for adopting a new engine (kept short on purpose)

1. `docs-fishing` first: upstream repo docs + model card, pinned commit, into `scratch/`.
2. Own `uv` venv → AMD index wheels + the pins above → import check printed at the end of setup.
3. Smoke test at the smallest resolution/step count; measure VRAM + commit + wall time per step.
4. Gate = command exit 0 + ffprobe/file facts + visual inspection of the output. Report
   done / verified / not verified — never "should work".
