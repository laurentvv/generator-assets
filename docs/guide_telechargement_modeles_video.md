# 📦 Guide Complet des Modèles Vidéo IA & Téléchargement (SOTA 2026)
### Station de travail : AMD Radeon RX 6950 XT (16 Go VRAM) • Vulkan 1.4 • Windows 11
### Répertoire central des modèles : `C:\Modeles_LLM\`

Ce guide détaille chaque modèle du pipeline vidéo IA, son rôle architectural, son empreinte mémoire VRAM/RAM, ses sources officielles (HuggingFace) et les scripts automatisés pour les télécharger avec reprise sur coupure.

---

## 📑 Sommaire
1. [Vue d'ensemble et Emplacement](#vue-densemble)
2. [1. LTX-2.5 Distilled (15B Audio + Vidéo) — Modèle Principal](#1-ltx-25-distilled)
3. [2. Wan 2.1 (14B Flagship & 1.3B Rapide)](#2-wan-21)
4. [3. Wan 2.2 MoE (Dual-DiT 28B Photoréaliste)](#3-wan-22-moe)
5. [4. MiniMax-H3 (32B Hailuo AI Audio + Vidéo)](#4-minimax-h3)
6. [5. Modèle de Super-Résolution IA 4K (4x-UltraSharp)](#5-super-resolution-4k)
7. [Script Tout-en-Un de Téléchargement](#script-tout-en-un)

---

<span id="vue-densemble"></span>
## 📂 Vue d'ensemble & Arborescence `C:\Modeles_LLM\`

Tous les modèles doivent être placés dans le dossier unique `C:\Modeles_LLM\` (et son sous-dossier `upscalers\`) pour être reconnus par `sd-cli.exe` et l'ensemble de nos scripts :

```text
C:\Modeles_LLM\
├── LTX-2.5-Distilled-Q4_K_M.gguf                (15.08 Go - DiT LTX-2.5)
├── gemma4-12b-with-proj-ltx-2.5-Q5_K_M.gguf      (8.86 Go  - Encodeur Gemma 4 12B)
├── ltx-2.5-video-vae-conv-bf16.safetensors       (1.45 Go  - VAE Décodeur Vidéo)
├── ltx-2.5-audio-vae-bf16.safetensors            (364 Mo   - VAE Décodeur Audio)
├── wan2.1-t2v-14b-Q4_K_M.gguf                   (10.12 Go - DiT Wan 2.1 14B)
├── wan2.1_t2v_1.3b-q8_0.gguf                    (1.47 Go  - DiT Wan 2.1 1.3B Rapide)
├── Wan2.2-T2V-A14B-LowNoise-Q4_K_M.gguf          (9.84 Go  - DiT Wan 2.2 MoE Low)
├── Wan2.2-T2V-A14B-HighNoise-Q4_K_M.gguf         (9.84 Go  - DiT Wan 2.2 MoE High)
├── umt5-xxl-encoder-Q4_K_M.gguf                  (3.44 Go  - Encodeur Texte UMT5-XXL)
├── wan_2.1_vae.safetensors                       (242 Mo   - VAE Vidéo Wan 2.x)
├── MiniMax-H3-Q4_K_M.gguf                        (9.22 Go  - DiT MiniMax Hailuo)
├── Qwen3-VL-32B-Instruct-Q4_K_M.gguf             (18.6 Go  - Encodeur Qwen3-VL)
└── upscalers/
    └── 4x-UltraSharp.pth                         (64 Mo    - Super-Résolution 4K ESRGAN)
```

---

<span id="1-ltx-25-distilled"></span>
## 👑 1. LTX-2.5 Distilled (15B Audio + Vidéo)

Le fleuron de production le plus rapide et le seul générant nativement **image + son stéréo synchronisé**.

### Composants & Sources HuggingFace :
| Fichier | Taille | Rôle | Source HuggingFace |
| :--- | :--- | :--- | :--- |
| `LTX-2.5-Distilled-Q4_K_M.gguf` | 15.08 Go | Diffusion spatio-temporelle DiT (8 steps) | [`city96/LTX-Video-gguf`](https://huggingface.co/city96/LTX-Video-gguf) |
| `gemma4-12b-with-proj-ltx-2.5-Q5_K_M.gguf` | 8.86 Go | Encodeur texte LLM Gemma 4 multimodal | [`elix3r/gemma4-12b-with-proj-ltx-2.5-GGUF`](https://huggingface.co/elix3r/gemma4-12b-with-proj-ltx-2.5-GGUF) *(repo gated, token HF requis)* |
| `ltx-2.5-video-vae-conv-bf16.safetensors` | 1.45 Go | VAE Vidéo convolutionnel | [`Lightricks/LTX-Video`](https://huggingface.co/Lightricks/LTX-Video) |
| `ltx-2.5-audio-vae-bf16.safetensors` | 364 Mo | VAE Audio stéréo natif (binaural 48 kHz) | [`Lightricks/LTX-Video`](https://huggingface.co/Lightricks/LTX-Video) |

### Commandes de téléchargement automatisé :
```powershell
# 1. Télécharger le modèle de diffusion LTX-2.5 :
python scripts/download_ltx25.py

# 2. Télécharger l'encodeur Gemma 4 12B (nécessite d'être connecté à HF ou variable HF_TOKEN) :
python scripts/download_gemma4_gguf.py

# 3. Télécharger les VAEs Vidéo et Audio :
python scripts/download_ltx25_vaes.py
```

---

<span id="2-wan-21"></span>
## 🏛️ 2. Wan 2.1 (14B Flagship & 1.3B Rapide)

Le modèle de référence d'Alibaba pour la géométrie 3D, les structures isométriques, les textures fines et la physique spatiale.

### Composants & Sources HuggingFace :
| Fichier | Taille | Rôle | Source HuggingFace |
| :--- | :--- | :--- | :--- |
| `wan2.1-t2v-14b-Q4_K_M.gguf` | 10.12 Go | Diffusion DiT 14B Flagship | [`city96/Wan2.1-T2V-14B-gguf`](https://huggingface.co/city96/Wan2.1-T2V-14B-gguf) |
| `wan2.1_t2v_1.3b-q8_0.gguf` | 1.47 Go | Diffusion DiT 1.3B Rapide (tests rapides) | [`city96/Wan2.1-T2V-1.3B-gguf`](https://huggingface.co/city96/Wan2.1-T2V-1.3B-gguf) |
| `umt5-xxl-encoder-Q4_K_M.gguf` | 3.44 Go | Encodeur de texte UMT5-XXL (partagé Wan 2.1 & 2.2) | [`city96/Wan2.1-T2V-14B-gguf`](https://huggingface.co/city96/Wan2.1-T2V-14B-gguf) |
| `wan_2.1_vae.safetensors` | 242 Mo | VAE Vidéo temporel 3D (partagé Wan 2.1 & 2.2) | [`Wan-AI/Wan2.1-T2V-14B`](https://huggingface.co/Wan-AI/Wan2.1-T2V-14B) |

### Commandes de téléchargement automatisé :
```powershell
# Pack Wan 2.1 14B Cinéma Studio :
.\scripts\download_video_models.ps1 -Model 14b

# Pack Wan 2.1 1.3B Ultra-Rapide :
.\scripts\download_video_models.ps1 -Model 1.3b
```

---

<span id="3-wan-22-moe"></span>
## 💎 3. Wan 2.2 MoE (Dual-DiT 28B Photoréaliste)

L'architecture la plus avancée pour le piqué photoréaliste absolu, utilisant deux experts DiT spécialisés (High Noise et Low Noise).

### Composants & Sources HuggingFace :
| Fichier | Taille | Rôle | Source HuggingFace |
| :--- | :--- | :--- | :--- |
| `Wan2.2-T2V-A14B-HighNoise-Q4_K_M.gguf` | 9.84 Go | Expert DiT MoE hautes fréquences / gros œuvre | [`Wan-AI/Wan2.2-T2V-A14B-GGUF`](https://huggingface.co/Wan-AI/Wan2.2-T2V-A14B-GGUF) |
| `Wan2.2-T2V-A14B-LowNoise-Q4_K_M.gguf` | 9.84 Go | Expert DiT MoE micro-détails et finitions | [`Wan-AI/Wan2.2-T2V-A14B-GGUF`](https://huggingface.co/Wan-AI/Wan2.2-T2V-A14B-GGUF) |
| `umt5-xxl-encoder-Q4_K_M.gguf` | 3.44 Go | Encodeur partagé avec Wan 2.1 | Idem Wan 2.1 |
| `wan_2.1_vae.safetensors` | 242 Mo | VAE partagé avec Wan 2.1 | Idem Wan 2.1 |

### Commandes de téléchargement automatisé :
```powershell
python scripts/download_wan22_official.py
```

---

<span id="4-minimax-h3"></span>
## 🐉 4. MiniMax-H3 (32B Hailuo AI Audio + Vidéo)

Le modèle titan de Hailuo AI, remarquable pour sa vitesse d'échantillonnage DiT (16.9s/step) et sa capacité à générer des monstres, flammes et rugissements synchronisés.

### Composants & Sources HuggingFace :
| Fichier | Taille | Rôle | Source HuggingFace |
| :--- | :--- | :--- | :--- |
| `MiniMax-H3-Q4_K_M.gguf` | 9.22 Go | Diffusion DiT FL2VA | [`MiniMax-AI/MiniMax-H3-GGUF`](https://huggingface.co/MiniMax-AI/MiniMax-H3-GGUF) |
| `Qwen3-VL-32B-Instruct-Q4_K_M.gguf` | 18.6 Go | Encodeur multimodal Qwen3-VL (chargé en RAM CPU) | [`Qwen/Qwen3-VL-32B-GGUF`](https://huggingface.co/Qwen) |

### Commandes de téléchargement automatisé :
```powershell
python scripts/download_minimax_h3.py
```

---

<span id="5-super-resolution-4k"></span>
## 🔍 5. Modèle de Super-Résolution IA 4K (4x-UltraSharp)

Essentiel pour la **diffusion YouTube Master 4K**. Reconstitue les arêtes et les micro-textures trame par trame sur Vulkan.

### Composant & Emplacement :
| Fichier | Taille | Rôle | Emplacement |
| :--- | :--- | :--- | :--- |
| `4x-UltraSharp.pth` | 64 Mo | Réseau de neurones ESRGAN haute fidélité | `C:\Modeles_LLM\upscalers\4x-UltraSharp.pth` |

*Lien direct : [`Kim2091/4x-UltraSharp`](https://huggingface.co/Kim2091/4x-UltraSharp)*

---

<span id="script-tout-en-un"></span>
## 🚀 Téléchargement Global Automatisé

Pour rapatrier l'intégralité du pack de modèles de pointe en un seul script résilient (avec reprise en cas de déconnexion et barre de progression) :

```powershell
python scripts/download_all_sota_models.py
```
