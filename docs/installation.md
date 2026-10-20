# ⚡ Installation & System Setup Guide

> Comprehensive installation guide, system requirements, engine locations, and model pack management for **Generator Assets**.
> Back to main: [README.md](../README.md)

---

### 🚀 One-Command Install

One script per OS family, same behavior: `uv sync` • the five C++ engines from their **official upstream releases** at pinned known-good versions • a standard FFmpeg build • model packs `base,onnx,upscalers` (~11 GB) • final `main.py --check`.

| OS | Command | GPU backend |
| :--- | :--- | :--- |
| **Windows 10/11** | `powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1` | Vulkan |
| **Linux x64** | `bash scripts/install_unix.sh` | Vulkan (Mesa/RADV drivers for AMD) |
| **macOS** | `bash scripts/install_unix.sh` | Metal — no Vulkan needed |

```bash
git clone https://github.com/votre-compte/generator-assets.git
cd generator-assets

# Windows (PowerShell) :
powershell -ExecutionPolicy Bypass -File scripts\install_windows.ps1
# Linux / macOS (bash) :
bash scripts/install_unix.sh
```

Options are the same on both scripts (`-Flag` on Windows, `--flag` on Unix): `-DryRun`/`--dry-run` resolves every download URL via the GitHub API and installs nothing • `-Engines`/`--engines "sd-cli,ffmpeg"` • `-Packs`/`--packs "video"` or `-SkipModels`/`--skip-models` (pick your [model packs](#3-download-the-ai-models)) • `-Force`/`--force` re-installs existing engines • `-Prefix "D:\"`/`--prefix ~/ga` moves the engines root. On Linux/macOS the installer symlinks the CLIs into `~/.local/bin` and writes `<prefix>/env.sh` — source it in your `~/.bashrc`/`~/.zshrc` (it sets `SD_CLI_PATH`, `LLAMA_CLI_PATH`, `AUDIOCPP_PATH`, `TRELLIS_CLI_PATH`, `FFMPEG_PATH`, `MODEL_DIR`, the same variables [core/config.py](../core/config.py) reads on Windows defaults).

Support matrix (every binary is the upstream project's own official release; versions pinned in [`scripts/engines_manifest.json`](../scripts/engines_manifest.json) — the repo publishes **pinned version references, not binaries**):

| Engine | Windows | Linux | macOS |
| :--- | :---: | :---: | :--- |
| sd-cli — stable-diffusion.cpp | ✅ Vulkan | ✅ Vulkan | ✅ arm64 (Metal) |
| llama.cpp | ✅ Vulkan | ✅ Vulkan | ✅ arm64 & x64 (Metal) |
| audio.cpp | ✅ Vulkan | ✅ Vulkan | ✅ arm64 & x64 (Metal) |
| trellis.cpp | ✅ Vulkan | ✅ Vulkan | ❌ no official build — compile from source |
| FFmpeg | [BtbN](https://github.com/BtbN/FFmpeg-Builds/releases) build | [BtbN](https://github.com/BtbN/FFmpeg-Builds/releases) build | Homebrew |

`sd-cli` is deliberately pinned to `master-841-6b3edaa`: later masters ship an unresolved VRAM-management regression ([#1946](https://github.com/leejet/stable-diffusion.cpp/issues/1946), fix PR still unmerged).

### 🧭 Optional: the Craft suite (thumbnails, typography, MCP apps)

The `miniature` (YouTube thumbnail with real typography) and `prepa_i2v` (I2V keyframe
preparation) workflows drive the **headless PhotoCraft engine** of the open-source
[Craft App Suite](https://getartcraft.com/apps) (pure-Rust desktop apps by the ArtCraft
team). Everything else in this factory is engine-local — this component is optional and
installed separately:

```bash
# anywhere you like — a dedicated manager repo (keep it, it also handles updates)
git clone <your-fork-or-copy-of-the-manager-repo> craft-suite
python craft-suite/manage_craft_suite.py install photocraft # portable x64 build, SHA256-verified
#                                              install --all  = the whole 13-app suite
```

- Default install root: `D:\CraftApps` — change `target_root` in the manager's `apps.json`
  (or pass `--target`). Override the engine path for the workflows with `PHOTOCRAFT_CLI`.
- Versions are **pinned** in `apps.json` (the validated ones); `status` shows upstream
  releases, `update <app>` shows the changelog and installs side-by-side with rollback,
  `prune` cleans old versions after validation — report-only watch, update on explicit GO.
- The stack watch (`scripts/veille_versions.py`) picks it up automatically when the manager
  lives at `D:\GIT\craft-suite` (override with the `CRAFT_SUITE_DIR` environment variable).
- 12 of the 13 apps also expose **MCP servers** (`<app>-cli mcp`) — the manager repo ships
  `mcp_probe.py` to inventory them.
### 🧰 Provisioning & Maintenance Scripts

| Script | Purpose |
| :--- | :--- |
| [`scripts/install_windows.ps1`](../scripts/install_windows.ps1) / [`scripts/install_unix.sh`](../scripts/install_unix.sh) | One-command installers (above) |
| [`scripts/engines_manifest.json`](../scripts/engines_manifest.json) | Pinned known-good engine versions — single source of truth for both installers |
| `scripts/update_sd_cpp.ps1` (+`.py`) | sd-cli Vulkan updater: latest official binaries or native CMake build, with backups & rollback (see [dedicated section](#sd-cpp-update)) |
| `scripts/update_llama_cpp.ps1` (+`.py`) | llama.cpp updater (same check/download/build/rollback pattern) |
| `scripts/update_vulkan_stack.ps1` (+`.py`) | Updates both engines in one go |
| [`scripts/manage_qwentts.py`](../scripts/manage_qwentts.py) | qwentts.cpp TTS engine manager (`C:\IA\qwentts.cpp`): safe git update (backup → pull → Vulkan build → smoke test → auto-rollback), binary backups (rotation 5) & GGUF model integrity vs HuggingFace (`--check`, `--models`, `--update`, `--backup`, `--rollback`) |
| [`scripts/download_models.py`](../scripts/download_models.py) | Model pack downloader (`--pack base,onnx,upscalers,video,video-14b,all`) |
| [`scripts/telecharger_gros_fichier_parallele.py`](../scripts/telecharger_gros_fichier_parallele.py) | Parallel downloader for throttled HF/ModelScope files (~10× faster) |
| [`scripts/check_charge_systeme.py`](../scripts/check_charge_systeme.py) | CPU/GPU/RAM/VRAM load gate to run before heavy generations |

---

### 1. Prerequisites
* **Windows 10/11, Linux x64 or macOS** (Apple Silicon recommended) — bash on Linux/macOS, Git Bash on Windows; [**uv**](https://docs.astral.sh/uv/) is auto-installed by the scripts above and Python ≥ 3.12 is pulled automatically by `uv sync`.
* A **GPU with Vulkan** (Windows/Linux) or **Metal** (macOS) — validated on an AMD RX 6950 XT 16 GB; there is **no CUDA dependency anywhere** (the whole AI stack runs through C++/GGML engines). 16 GB VRAM comfortably covers Flux + video workflows; 8-12 GB cards should stick to the light packs (SDXL, Wan 2.1 1.3B).
* The **C++/GGUF engines**, installed outside the repository (standalone executables, not pip packages — every path is overridable via environment variables such as `SD_CLI_PATH`, `LLAMA_CLI_PATH`, `AUDIOCPP_PATH`, `FFMPEG_PATH`). The installer fetches each one from its official release:

| Engine | Default Location | Role |
| :--- | :--- | :--- |
| [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp) | `C:\SD\sd-cli.exe` | Image & video diffusion (Flux.1, SDXL, Wan 2.1/2.2, LTX-2.5, MiniMax-H3) |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | `C:\llama.cpp\llama-cli.exe` | Local LLM Art Director (`--use-llm`), Music Flamingo QA |
| [audio.cpp](https://github.com/0xShug0/audio.cpp) | `C:\audio-cpp\audiocpp_cli.exe` | Music & SFX generation (MiniMax-Music3, ACE-Step 1.5, Stable Audio 3) |
| [trellis.cpp](https://github.com/pwilkin/trellis.cpp) | `C:\trellis\` | AI image→3D volumetric meshes (TRELLIS.2, workflow `mesh_ia`) |
| FFmpeg ([standard BtbN build](https://github.com/BtbN/FFmpeg-Builds/releases)) | `C:\ffmpeg\dist\bin\ffmpeg.exe` | Audio conform, loudnorm, ducking, OGG/WebM muxing |
| [Blender 5.x](https://www.blender.org/download/) | standard install | Headless meshing, decimation, control renders (`bpy`) — install manually |

> 🔒 **Why doesn't this repo publish its own binaries?** Every engine above ships official Vulkan binaries that work on any Windows x64 machine with an AMD/NVIDIA/Intel GPU — the installer simply pins known-good versions. The one binary compiled locally on the dev workstation, the custom FFmpeg build, **cannot and should not be redistributed**: it enables `libfdk-aac`, which makes it *nonfree* under the FFmpeg license, and it is tuned for one machine (`--cpu=native`, AMD AMF for RDNA2). A **standard build covers 100 % of this repository's recipes** (loudnorm 2-pass, `sidechaincompress` ducking, OGG Vorbis, x264 — verified in the codebase); only optional GPU-accelerated *video encoding* (AMF/NVENC) would justify a local source build via MSYS2 (recipe documented on the dev workstation in `C:\ffmpeg\README.md`).
>
> Each of these tools also has a **custom local README** on the workstation (`C:\SD\README.md`, `C:\audio-cpp\README.md`, `C:\ffmpeg\README.md`, `C:\trellis\README.md`) documenting installed versions, validated commands and pitfalls. `sd-cli` can be installed/updated in one command via the [built-in Vulkan updater](#sd-cpp-update).

---

### 2. Clone & Setup the Virtual Environment
*Manual route — the [one-command installer](#-one-command-install) above already does this.*

This project is optimized for [**uv**](https://docs.astral.sh/uv/) for near-instant package installation:

```bash
git clone https://github.com/votre-compte/generator-assets.git
cd generator-assets

# Synchronize dependencies with uv:
uv sync
```

*(Alternatively, standard pip — dependencies are declared in [`pyproject.toml`](pyproject.toml): `python -m venv .venv && .venv\Scripts\activate && pip install -e .`)*

---

### 3. Download the AI Models

All model weights live **outside the repository**, in a single folder: `C:\Modeles_LLM` (override it with the `MODEL_DIR` environment variable).

> 🧭 **Where are model paths configured?** In a single Python module — [`core/config.py`](../core/config.py) — not in a JSON/YAML file. Every model path is a constant with its own environment-variable override (`SD_MODEL_PATH`, `WAN_MODEL_PATH`, `H3_REF2VA_MODEL_PATH`, `MUSIC3_MODEL_DIR`, `ACESTEP15_MODEL_DIR`, …). The download scripts below write exactly to these default locations, so a fresh install works out of the box.

**📦 Download manager** (skips files already present, resumes partial downloads via curl):

```bash
uv run python scripts/download_models.py --pack base       # Image core: Flux.1 Dev Q6_K + CLIP-L + T5-XXL + VAE + LFM2.5 LLM (~10 GB)
uv run python scripts/download_models.py --pack onnx       # Light ONNX models: RMBG-1.4, DeepBump, RIFE
uv run python scripts/download_models.py --pack upscalers  # ESRGAN upscalers (4x-UltraSharp, RealESRGAN ×2)
uv run python scripts/download_models.py --pack video      # Wan 2.1 1.3B light video pack (~5 GB)
uv run python scripts/download_models.py --pack video-14b  # Wan 2.1 14B studio video pack (~25 GB)
uv run python scripts/download_models.py --pack all        # Everything above
```

**Per-family packs** (each family has its dedicated script):

| Domain | Models | Download |
| :--- | :--- | :--- |
| Image 2D core | Flux.1 Dev Q6_K, CLIP-L, T5-XXL, VAE `ae.safetensors`, LFM2.5-8B | `scripts/download_models.py --pack base` |
| Video DiT | Wan 2.2 MoE, MiniMax-H3 (FL2VA + Ref2VA), LTX-2.5 | `scripts/download_wan22*.py`, `scripts/download_minimax_h3.py`, `scripts/download_ltx25*.py` |
| Music & SFX | MiniMax-Music3, ACE-Step 1.5 | `scripts/download_music3_gguf.py`, `scripts/download_acestep15_gguf.py <variante>` |
| Image→3D | TRELLIS.2 GGUF (10 files, ~16.4 GB → `C:\Modeles_LLM\trellis2-gguf`) | manual — procedure in `C:\trellis\README.md` |
| SDXL styles | `juggernautXL_ragnarok.safetensors` | manual — Civitai (account required) |
| LoRAs | Diablo, Dungeon, 360°, space… | manual — see [`loras/`](loras/) / `C:\Modeles_LLM\loras` |

> 💡 **Large downloads**: Hugging Face / ModelScope throttle single connections — use the parallel downloader (~10× faster): `uv run python scripts/telecharger_gros_fichier_parallele.py <url> <destination>`.
>
> ⚠️ **Licensing**: the Flux.1 Dev Q6_K GGUF is fetched from the `city96` mirror but remains under the [FLUX.1-dev Non-Commercial License](https://huggingface.co/black-forest-labs/FLUX.1-dev) (the official repository is gated).

---

### 4. Verify System Requirements & Paths
Check that your local executables (`sd-cli.exe`, `llama-cli.exe`, Blender) and model checkpoints are detected:

```bash
uv run python main.py --check
```

---

### 5. Launch the Interactive Console
```bash
uv run python main.py --interactive
```

### 6. Launch the Web Console (factory console)
```bash
uv run python -m server          # → http://127.0.0.1:8765 (localhost only)
```

Full-Python web UI (**FastAPI + Jinja2 + HTMX**, zero Node/npm) piloting the whole
factory from a browser: auto-generated forms for **all 64 workflows** (introspected
live from the workflow registry — new workflows appear automatically), curated recipe
presets (turbo, LUFS beds, LTX frame rules…), a **serialized run queue** (one heavy
GPU job at a time, automatic `check_charge_systeme` load gate), live log/progress
streaming (SSE), source-image uploads with a file picker over `output/` +
`godot_assets/`, and a multi-media **library** (masonry gallery, thumbnails, audio
waveforms, video preview, send-to-workflow actions), and a read-only **Models** page
(expected models from `core/config.py` with present/missing + sizes, workflow→model
dependency strip, active env overrides, LoRA/upscaler listings, optional disk
inventory — no add/remove: the AGENTS.md restatement rule applies), a read-only
**Veille** page (pending updates, installed-vs-upstream component versions, journal
feed, update notes — report only, never auto-update) and a **Jobs** history page
(status filters, stop/retry, raw logs). Runtime state lives
in `output/_webui/` (SQLite + logs + uploads, git-ignored). The engines are still
invoked exactly through the frozen CLI subprocess contract — the UI adds zero PyTorch,
zero cloud.

---
