# 🔄 Vulkan Engine Update & Build Automation

> Official build, update, and rollback procedures for stable-diffusion.cpp, llama.cpp, and the unified Vulkan stack.
> Back to main: [README.md](../README.md)

---

### 🛠️ Operating Modes

The script [`scripts/update_sd_cpp.py`](../scripts/update_sd_cpp.py) and its PowerShell launcher [`scripts/update_sd_cpp.ps1`](../scripts/update_sd_cpp.ps1) offer two complementary approaches:

| Mode | Option | Description | Estimated Time |
| :--- | :--- | :--- | :--- |
| **🔍 Check** | `--check` | Compares the local version (`sd-cli.exe --version`) with the latest official GitHub release and the latest `master` commit. | ~1 second |
| **🚀 Fast Download** | `--download` | Directly downloads the official pre-compiled Windows x64 Vulkan binaries (`sd-*-bin-win-vulkan-x64.zip`) from GitHub Releases, creates a timestamped backup and deploys into `C:\SD`. | ~5 seconds |
| **⚙️ Native Vulkan Build** | `--build` | Clones/updates the Git repository with recursive submodules, configures CMake with the Vulkan SDK and builds natively with Visual Studio (MSVC) in multi-threaded Release mode. | ~2 to 5 minutes |
| **⏪ Restore** | `--rollback` | Instantly restores the latest archived backup from `C:\SD\backups\` in case of incompatibility or regression. | ~2 seconds |

---

### 💻 Command-Line Usage

#### 1. Via PowerShell (Recommended on Windows)
```powershell
# 1. Check whether an update is available
.\scripts\update_sd_cpp.ps1 -Check

# 2. Fast update via the official Vulkan release
.\scripts\update_sd_cpp.ps1 -Download

# 3. Full native build from Git sources with Vulkan
.\scripts\update_sd_cpp.ps1 -Build -Clean

# 4. If needed: restore the previous version
.\scripts\update_sd_cpp.ps1 -Rollback
```

#### 2. Via the Unified `main.py` CLI
```bash
# Check
uv run python main.py --update-sd check

# Download the latest Vulkan release
uv run python main.py --update-sd download

# Native build from sources
uv run python main.py --update-sd build

# Restore the backup
uv run python main.py --update-sd rollback
```

#### 3. Via the Dedicated Python Script
```bash
uv run python scripts/update_sd_cpp.py --check
uv run python scripts/update_sd_cpp.py --download
uv run python scripts/update_sd_cpp.py --build --jobs 16
uv run python scripts/update_sd_cpp.py --list-backups
```

#### 4. From the Interactive Console
Run `uv run python main.py --interactive` then pick:
`[33] 🔄 Vulkan Update & Build Manager (stable-diffusion.cpp)`.

---

### 🛡️ Safety & Automatic Backup System

Every update operation (whether by download or build) automatically creates a timestamped backup archive of all executables (`sd-cli.exe`, `sd-server.exe`) and dynamic libraries (`ggml-vulkan.dll`, `stable-diffusion.dll`, `webm.dll`, etc.) into:
```text
C:\SD\backups\backup_YYYYMMDD_HHMMSS\
```
You can list backups with `--list-backups` and roll back to the previous state at any time via `--rollback`.

---

### 🦙 llama.cpp Vulkan Automation & Build

The optional text enrichment / art-direction module (`--use-llm`) relies on [**llama.cpp**](https://github.com/ggml-org/llama.cpp). To guarantee instant LLM inference on GPU without requiring proprietary NVIDIA CUDA drivers, `llama.cpp` runs with the **Vulkan** backend (`ggml-vulkan.dll`), fully harnessing **AMD Radeon (RX 6000 / 7000 / 8000)**, **Intel Arc** and **NVIDIA GeForce** GPUs.

The script [`scripts/update_llama_cpp.py`](../scripts/update_llama_cpp.py) and its launcher [`scripts/update_llama_cpp.ps1`](../scripts/update_llama_cpp.ps1) handle updates and native builds:

#### 1. llama.cpp usage commands:
```powershell
# Version check (local vs remote)
.\scripts\update_llama_cpp.ps1 -Check

# Fast download of the latest official Vulkan release (e.g. b10797)
.\scripts\update_llama_cpp.ps1 -Download

# Full native build with Vulkan (CMake + MSVC)
.\scripts\update_llama_cpp.ps1 -Build -Clean

# Restore the previous backup
.\scripts\update_llama_cpp.ps1 -Rollback
```

#### 2. Via the Unified CLI:
```bash
uv run python main.py --update-llama check
uv run python main.py --update-llama download
uv run python main.py --update-llama build
uv run python main.py --update-llama rollback
```

---

### ⚡ Complete Vulkan Suite: Unified Manager (SD + LLaMA + GPU)

To administer your entire Vulkan AI ecosystem in a single command, the script [`scripts/update_vulkan_stack.py`](../scripts/update_vulkan_stack.py) and its launcher [`scripts/update_vulkan_stack.ps1`](../scripts/update_vulkan_stack.ps1) simultaneously orchestrate:
1. **Vulkan hardware diagnostics** (AMD Radeon / NVIDIA / Intel GPU detection, API and driver version).
2. Inspection or update of **stable-diffusion.cpp** (`C:\SD`).
3. Inspection or update of **llama.cpp** (`C:\llama.cpp`).

```powershell
# Full GPU diagnostic and check of both engines
.\scripts\update_vulkan_stack.ps1 -Check

# Synchronized update of the 2 engines via official Vulkan releases
.\scripts\update_vulkan_stack.ps1 -Download

# Full native rebuild of the 2 engines with Vulkan
.\scripts\update_vulkan_stack.ps1 -Build -Clean

# Global backup restoration
.\scripts\update_vulkan_stack.ps1 -Rollback
```

Or directly from the main CLI:
```bash
uv run python main.py --update-vulkan check
uv run python main.py --update-vulkan download
uv run python main.py --update-vulkan build
```

---

