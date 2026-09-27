# 📦 Complete Guide to AI Video Models & Download (SOTA 2026)
### Workstation: AMD Radeon RX 6950 XT (16 GB VRAM) • Vulkan 1.4 • Windows 11
### Central model directory: `C:\Modeles_LLM\`

This guide details each model of the AI video pipeline, its architectural role, its VRAM/RAM memory footprint, its official sources (HuggingFace) and the automated scripts to download them with resume-on-disconnect.

---

## 📑 Table of Contents
1. [Overview and Location](#vue-densemble)
2. [1. LTX-2.5 Distilled (15B Audio + Video) — Main Model](#1-ltx-25-distilled)
3. [2. Wan 2.1 (14B Flagship & Fast 1.3B)](#2-wan-21)
4. [3. Wan 2.2 MoE (Dual-DiT 28B Photorealistic)](#3-wan-22-moe)
5. [4. MiniMax-H3 (32B Hailuo AI Audio + Video)](#4-minimax-h3)
6. [5. AI 4K Super-Resolution Model (4x-UltraSharp)](#5-super-resolution-4k)
7. [All-in-One Download Script](#script-tout-en-un)

---

<span id="vue-densemble"></span>
## 📂 Overview & `C:\Modeles_LLM\` Directory Tree

All models must be placed in the single folder `C:\Modeles_LLM\` (and its `upscalers\` subfolder) to be recognized by `sd-cli.exe` and all our scripts:

```text
C:\Modeles_LLM\
├── LTX-2.5-Distilled-Q4_K_M.gguf                (15.08 GB - DiT LTX-2.5)
├── gemma4-12b-with-proj-ltx-2.5-Q5_K_M.gguf      (8.86 GB  - Gemma 4 12B Encoder)
├── ltx-2.5-video-vae-conv-bf16.safetensors       (1.45 GB  - Video Decoder VAE)
├── ltx-2.5-audio-vae-bf16.safetensors            (364 MB   - Audio Decoder VAE)
├── wan2.1-t2v-14b-Q4_K_M.gguf                   (10.12 GB - DiT Wan 2.1 14B)
├── wan2.1_t2v_1.3b-q8_0.gguf                    (1.47 GB  - DiT Wan 2.1 1.3B Fast)
├── Wan2.2-T2V-A14B-LowNoise-Q4_K_M.gguf          (9.84 GB  - DiT Wan 2.2 MoE Low)
├── Wan2.2-T2V-A14B-HighNoise-Q4_K_M.gguf         (9.84 GB  - DiT Wan 2.2 MoE High)
├── umt5-xxl-encoder-Q4_K_M.gguf                  (3.44 GB  - UMT5-XXL Text Encoder)
├── wan_2.1_vae.safetensors                       (242 MB   - Wan 2.x Video VAE)
├── MiniMax-H3-Q4_K_M.gguf                        (9.22 GB  - DiT MiniMax Hailuo)
├── Qwen3-VL-32B-Instruct-Q4_K_M.gguf             (18.6 GB  - Qwen3-VL Encoder)
└── upscalers/
    └── 4x-UltraSharp.pth                         (64 MB    - 4K ESRGAN Super-Resolution)
```

---

<span id="1-ltx-25-distilled"></span>
## 👑 1. LTX-2.5 Distilled (15B Audio + Video)

The fastest production flagship and the only one natively generating **image + synchronized stereo sound**.

### Components & HuggingFace Sources:
| File | Size | Role | HuggingFace Source |
| :--- | :--- | :--- | :--- |
| `LTX-2.5-Distilled-Q4_K_M.gguf` | 15.08 GB | Spatio-temporal DiT diffusion (8 steps) | [`city96/LTX-Video-gguf`](https://huggingface.co/city96/LTX-Video-gguf) |
| `gemma4-12b-with-proj-ltx-2.5-Q5_K_M.gguf` | 8.86 GB | Gemma 4 multimodal LLM text encoder | [`elix3r/gemma4-12b-with-proj-ltx-2.5-GGUF`](https://huggingface.co/elix3r/gemma4-12b-with-proj-ltx-2.5-GGUF) *(gated repo, HF token required)* |
| `ltx-2.5-video-vae-conv-bf16.safetensors` | 1.45 GB | Convolutional Video VAE | [`Lightricks/LTX-Video`](https://huggingface.co/Lightricks/LTX-Video) |
| `ltx-2.5-audio-vae-bf16.safetensors` | 364 MB | Native stereo Audio VAE (48 kHz binaural) | [`Lightricks/LTX-Video`](https://huggingface.co/Lightricks/LTX-Video) |

### Automated download commands:
```powershell
# 1. Download the LTX-2.5 diffusion model:
python scripts/download_ltx25.py

# 2. Download the Gemma 4 12B encoder (requires being logged in to HF or the HF_TOKEN variable):
python scripts/download_gemma4_gguf.py

# 3. Download the Video and Audio VAEs:
python scripts/download_ltx25_vaes.py
```

---

<span id="2-wan-21"></span>
## 🏛️ 2. Wan 2.1 (14B Flagship & Fast 1.3B)

Alibaba's reference model for 3D geometry, isometric structures, fine textures and spatial physics.

### Components & HuggingFace Sources:
| File | Size | Role | HuggingFace Source |
| :--- | :--- | :--- | :--- |
| `wan2.1-t2v-14b-Q4_K_M.gguf` | 10.12 GB | 14B Flagship DiT diffusion | [`city96/Wan2.1-T2V-14B-gguf`](https://huggingface.co/city96/Wan2.1-T2V-14B-gguf) |
| `wan2.1_t2v_1.3b-q8_0.gguf` | 1.47 GB | Fast 1.3B DiT diffusion (quick tests) | [`city96/Wan2.1-T2V-1.3B-gguf`](https://huggingface.co/city96/Wan2.1-T2V-1.3B-gguf) |
| `umt5-xxl-encoder-Q4_K_M.gguf` | 3.44 GB | UMT5-XXL text encoder (shared by Wan 2.1 & 2.2) | [`city96/Wan2.1-T2V-14B-gguf`](https://huggingface.co/city96/Wan2.1-T2V-14B-gguf) |
| `wan_2.1_vae.safetensors` | 242 MB | 3D temporal Video VAE (shared by Wan 2.1 & 2.2) | [`Wan-AI/Wan2.1-T2V-14B`](https://huggingface.co/Wan-AI/Wan2.1-T2V-14B) |

### Automated download commands:
```powershell
# Wan 2.1 14B Cinema Studio pack:
.\scripts\download_video_models.ps1 -Model 14b

# Wan 2.1 1.3B Ultra-Fast pack:
.\scripts\download_video_models.ps1 -Model 1.3b
```

---

<span id="3-wan-22-moe"></span>
## 💎 3. Wan 2.2 MoE (Dual-DiT 28B Photorealistic)

The most advanced architecture for absolute photoreal sharpness, using two specialized DiT experts (High Noise and Low Noise).

### Components & HuggingFace Sources:
| File | Size | Role | HuggingFace Source |
| :--- | :--- | :--- | :--- |
| `Wan2.2-T2V-A14B-HighNoise-Q4_K_M.gguf` | 9.84 GB | DiT MoE expert for high frequencies / coarse structure | [`Wan-AI/Wan2.2-T2V-A14B-GGUF`](https://huggingface.co/Wan-AI/Wan2.2-T2V-A14B-GGUF) |
| `Wan2.2-T2V-A14B-LowNoise-Q4_K_M.gguf` | 9.84 GB | DiT MoE expert for micro-details and finishing | [`Wan-AI/Wan2.2-T2V-A14B-GGUF`](https://huggingface.co/Wan-AI/Wan2.2-T2V-A14B-GGUF) |
| `umt5-xxl-encoder-Q4_K_M.gguf` | 3.44 GB | Encoder shared with Wan 2.1 | Same as Wan 2.1 |
| `wan_2.1_vae.safetensors` | 242 MB | VAE shared with Wan 2.1 | Same as Wan 2.1 |

### Automated download commands:
```powershell
python scripts/download_wan22_official.py
```

### 🎬 Wan 2.2 I2V MoE (Image-to-Video 28B):
To animate an existing image with the power of the Wan 2.2 MoE:
| File | Size | Role | HuggingFace Source |
| :--- | :--- | :--- | :--- |
| `Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf` | 8.99 GB | DiT MoE I2V expert composition/motion | [`QuantStack/Wan2.2-I2V-A14B-GGUF`](https://huggingface.co/QuantStack/Wan2.2-I2V-A14B-GGUF) |
| `Wan2.2-I2V-A14B-LowNoise-Q4_K_M.gguf` | 8.99 GB | DiT MoE I2V expert temporal micro-textures | [`QuantStack/Wan2.2-I2V-A14B-GGUF`](https://huggingface.co/QuantStack/Wan2.2-I2V-A14B-GGUF) |
| `clip_vision_h.safetensors` | 1.26 GB | Visual image encoder (CLIP-ViT) | [`Comfy-Org/Wan_2.1_ComfyUI_repackaged`](https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged) |

```powershell
# Automated download of Wan 2.2 I2V MoE:
python scripts/download_wan22_i2v_models.py
```

---

<span id="4-minimax-h3"></span>
## 🐉 4. MiniMax-H3 (32B Hailuo AI Audio + Video)

The titan model from Hailuo AI, remarkable for its DiT sampling speed (16.9s/step) and its ability to generate synchronized monsters, flames and roars.

### Components & HuggingFace Sources:
| File | Size | Role | HuggingFace Source |
| :--- | :--- | :--- | :--- |
| `MiniMax-H3-Q4_K_M.gguf` | 9.22 GB | DiT FL2VA diffusion | [`MiniMax-AI/MiniMax-H3-GGUF`](https://huggingface.co/MiniMax-AI/MiniMax-H3-GGUF) |
| `Qwen3-VL-32B-Instruct-Q4_K_M.gguf` | 18.6 GB | Qwen3-VL multimodal encoder (loaded in CPU RAM) | [`Qwen/Qwen3-VL-32B-GGUF`](https://huggingface.co/Qwen) |

### Automated download commands:
```powershell
python scripts/download_minimax_h3.py
```

---

<span id="5-super-resolution-4k"></span>
## 🔍 5. AI 4K Super-Resolution Model (4x-UltraSharp)

Essential for **4K Master YouTube publishing**. Rebuilds edges and micro-textures frame by frame on Vulkan.

### Component & Location:
| File | Size | Role | Location |
| :--- | :--- | :--- | :--- |
| `4x-UltraSharp.pth` | 64 MB | High-fidelity ESRGAN neural network | `C:\Modeles_LLM\upscalers\4x-UltraSharp.pth` |

*Direct link: [`Kim2091/4x-UltraSharp`](https://huggingface.co/Kim2091/4x-UltraSharp)*

---

---

## 🎵 6. MiniMax-Music3 GGUF (Text-to-Music Generation)

Music generation engine of the `music_bg` workflow: songs and instrumentals up to 5 minutes,
32 kHz stereo output, run via **audio.cpp** (C++ GGUF Vulkan engine, same philosophy as
sd-cli and llama.cpp — no PyTorch, AMD GPU used).

### Components & HuggingFace Sources:
| File | Size | Role | Location |
| :--- | :--- | :--- | :--- |
| `language_model_q4_0.gguf` | 6.01 GB | Global 8B LLM (musical structure, Qwen3) | `C:\Modeles_LLM\MiniMax-Music3-GGUF\` |
| `rvq_depth_decoder_q8_0.gguf` | 0.70 GB | RVQ decoder (acoustic codebooks) | `C:\Modeles_LLM\MiniMax-Music3-GGUF\` |
| `transformer_q4_0.gguf` | 1.40 GB | Flow Matching 2.4B | `C:\Modeles_LLM\MiniMax-Music3-GGUF\` |
| `condition_encoder.gguf` | 101 MB | Text conditioning encoder | `C:\Modeles_LLM\MiniMax-Music3-GGUF\` |
| `vocoder.gguf` | 217 MB | Flow-VAE → waveform | `C:\Modeles_LLM\MiniMax-Music3-GGUF\` |
| `config/` + `tokenizer/` | ~12 MB | Runtime configs + tokenizer | `C:\Modeles_LLM\MiniMax-Music3-GGUF\` |

The **audio.cpp** runtime (Windows x64 Vulkan release, ~53 MB) installs into `C:\audio-cpp\`
(`audiocpp_cli.exe`, overridable via `AUDIOCPP_PATH`).

### Automated download command:

```powershell
uv run python scripts/download_music3_gguf.py
```

*Sources: [`audio-cpp/MiniMax-Music3-GGUF`](https://huggingface.co/audio-cpp/MiniMax-Music3-GGUF) •
[audio.cpp (GitHub)](https://github.com/0xShug0/audio.cpp) •
[`MiniMaxAI/MiniMax-Music3`](https://huggingface.co/MiniMaxAI/MiniMax-Music3)*

### 📜 License & YouTube best practices:
- **MiniMax-Music3 community license** (MIT-type): **commercial use allowed** below $20 M annual
  revenue; the "MiniMax-Music3" attribution is required on products/services exposing the model.
- The AUP asks to **disclose AI-generated content** published publicly → add a line
  in the YouTube description: *"Music: AI-generated (MiniMax-Music3)"*.
- Measured VRAM peak ~9.8 GiB (Q4_0/Q8_0 mix, 30 s) → within the 16 GB budget of the RX 6950 XT.

### 🧠 Optional module: Music Flamingo (music QA via llama.cpp)

Music **understanding** model (NVIDIA, Audio Flamingo 3 backbone) used by `music_bg --analyse`
for loop QA (BPM, instrumental, "unobtrusive in background" verdict) via `llama-cli` + audio mmproj.

| File | Size | Location |
| :--- | :--- | :--- |
| `music-flamingo-hf.Q4_K_M.gguf` | 4.8 GB | `C:\Modeles_LLM\music-flamingo\` |
| `music-flamingo-hf.mmproj-f16.gguf` | 1.4 GB | `C:\Modeles_LLM\music-flamingo\` |

```powershell
uv run python scripts/download_music_flamingo.py
```

⚠️ **NVIDIA OneWay Noncommercial license**: non-commercial use only (internal analysis,
never distributed) — which is why this module is optional and disabled by default.

*Sources: [`mradermacher/music-flamingo-hf-GGUF`](https://huggingface.co/mradermacher/music-flamingo-hf-GGUF) •
[NVIDIA/audio-flamingo](https://github.com/NVIDIA/audio-flamingo)*

<span id="script-tout-en-un"></span>
## 🚀 Automated Global Download

To bring down the entire state-of-the-art model pack in a single resilient script (with resume on disconnect and progress bar):

```powershell
python scripts/download_all_sota_models.py
```
