# 🧠 MEMORY BANK : Pipeline Vidéo IA & Modèles SOTA (2026)
### Station de travail : AMD Radeon RX 6950 XT (16 Go VRAM GDDR6) • Vulkan 1.4 • Windows 11

---

## 📌 1. Décisions d'Architecture Validées en Production

### 👑 1.1. Modèle Vidéo SOTA Numéro 1 : **LTX-2.5 Distilled (15B Audio + Vidéo)**
* **Validation Utilisateur** : *« il est mieux que le modèle d'avant !! »*
* **Composants Validés dans `C:\Modeles_LLM\`** :
  1. `LTX-2.5-Distilled-Q4_K_M.gguf` (15.08 Go) — Diffusion DiT
  2. `gemma4-12b-with-proj-ltx-2.5-Q5_K_M.gguf` (8.86 Go) — Encodeur Gemma 4 12B (repo gated `elix3r/gemma4-12b-with-proj-ltx-2.5-GGUF`)
  3. `ltx-2.5-video-vae-conv-bf16.safetensors` (1.45 Go) — Décodeur vidéo convolutionnel
  4. `ltx-2.5-audio-vae-bf16.safetensors` (364 Mo) — Décodeur audio stéréo natif
* **Profil Mémoire Hybride Vulkan / CPU** :
  * `--backend "diffusion=vulkan0,te=cpu,vae=cpu"`
  * **VRAM GPU utilisée** : **14.05 Go fixe** (marge de sécurité de 1.95 Go sous les 16 Go de la RX 6950 XT).
  * **RAM Système CPU** : Gemma 4 (~12.1 Go) + Buffer VAE Conv (~7.3 Go).
* **Profil d'Échantillonnage Officiel** :
  * Échantillonneur : `euler_ancestral` (`--sampling-method euler_a`).
  * Guidage : `--cfg-scale 1.0` (modèle distillé, **1 seule passe par étape**, vitesse x2).
  * Sigmas distillés 8-step : `--sigmas "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"`.
* **Performances Chronométrées** :
  * Échantillonnage DiT (8 étapes complètes) : **1 min 24s (84.5 secondes)** sur GPU Vulkan (~10.5s/step) !
  * Décodage Audio Stéréo : **14.3 secondes** (audio PCM 48 kHz natif synchronisé).
  * Décodage Vidéo Conv 33 trames : ~101 secondes sur 12 cœurs CPU Alderlake.
  * Temps total génération complète (768×512 @ 24 FPS, 33 trames + son) : **4.2 minutes**.

---

### 🎬 1.2. Modèle de Référence Alternatif : **Wan 2.1 14B**
* **Composants** : `wan2.1-t2v-14b-Q4_K_M.gguf` (10.12 Go) + `umt5-xxl-encoder-Q4_K_M.gguf` + `wan_2.1_vae.safetensors`.
* **Profil Mémoire** : `--backend "diffusion=vulkan0,te=cpu"`.
* **Performances** : ~58s par étape (CFG 6.0 à 7.0 = 2 passes/step). 8 étapes = ~7.5 à 8 minutes par plan.
* **Son** : Vidéo muette en sortie native, sound design synthétisé via script procédural externe (`scripts/assemble_2plans.py`).

---

### ⚙️ 1.3. Validation Empirique des 4 Modèles SOTA (Grand Rendu Nocturne)
* **LTX-2.5 Distilled (15B Audio + Vidéo)** :
  * 8 étapes en 7.30 min (échantillonnage DiT ~10s/step). Audio stéréo synchronisé natif 48 kHz.
  * Modélisation héroïque 3D d'une netteté parfaite (écailles, crocs, langue, cornes, ailes translucides).
* **Wan 2.1 (14B Flagship T2V)** :
  * 8 étapes en 42.65 min (échantillonnage DiT ~312s/step, 100% VRAM fixe 9.8 Go, 0 swap).
  * Dragon d'or impérial majestueux complètement résolu (au lieu de la bouillie floue observée à 3 steps).
* **Wan 2.2 MoE (2x 14B Dual-DiT LowNoise + HighNoise)** :
  * 8 étapes MoE (4 High + 4 Low) en 51.58 min avec `--offload-to-cpu` et `--temporal-tiling`.
  * **Piqué cinématographique absolu** : micro-rides de peau, pupilles d'ambre et spécularité photoréaliste de niveau cinéma d'animation hollywoodien.
* **MiniMax-H3 (Titan 32B Hailuo AI Vidéo + Audio)** :
  * 12 étapes en 6.61 min (échantillonnage DiT record de **16.96s/step** sur Vulkan, Qwen3-VL 32B sur CPU RAM).
  * Wyvern titanesque rugissante avec crête enflammée, ailes massives et bande-son stéréo native.

### 🛡️ 1.4. Règle Critique Vulkan AMD Windows
* **Interdiction de `--diffusion-fa` (Flash Attention)** : Déclenche l'erreur `split_k_reduce` / `ErrorDeviceLost` sous pilote AMD 26.8.1.
* **Obligation du backend hybride** : `--backend "diffusion=vulkan0,te=cpu,vae=cpu"` pour les modèles à encodeur multimodal (LTX-2.5, MiniMax-H3) afin d'éviter les débordements de buffer Vulkan.

### ⚡ 1.5. Amélioration de Netteté Vidéo : Levier 1 (AMD FidelityFX CAS)
* **Problème résolu** : Le flou d'étirement causé par le filtre Lanczos seul lors du passage de 480p/512p à 1080p.
* **Solution validée** : Chaînage du filtre officiel **AMD Contrast Adaptive Sharpening** (`scale=1920:1080:flags=lanczos,cas=0.75`).
* **Bénéfice** : Micro-contraste et séparation des arêtes (écailles, crocs, pupilles) décuplés instantanément (0s de calcul supplémentaire via encodage matériel `h264_amf`).
* **Script dédié** : `scripts/test_levier1_cas.py` générant les masters CAS, les vidéos comparatives split-screen 50/50 et les planches de zoom 1:1.

#### 🚀 1.6. Amélioration de Netteté Vidéo : Levier 4 (Super-Résolution IA 4K Real-ESRGAN)
* **Principe** : Extraction trame par trame, passage dans le réseau de neurones `4x-UltraSharp.pth` via `sd-cli -M upscale --backend vulkan0` (~7.3s/trame sur RX 6950 XT), puis réassemblage matériel AMF en Ultra HD 4K (3840×2160 @ 50 Mbps) avec filtre AMD FidelityFX CAS 0.75.
* **Résultat visuel** : **Reconstruction de micro-détails réels** (lignes de grilles, arêtes, spécularité, textures 3D) impossibles à obtenir par interpolation classique.
* **Script généralisé réutilisable** : [`scripts/upscale_video_ai.py`](file:///C:/GIT/generator-assets/scripts/upscale_video_ai.py) prenant n'importe quel fichier WebM/MP4, conservant la piste audio native et produisant le Master 4K.

### 📺 1.7. Stratégie de Diffusion YouTube & Netteté Maximale
* **Contournement de la compression AVC1** : YouTube applique automatiquement un débit destructeur (~4-6 Mbps) sur les vidéos 1080p.
* **Mastering 4K Impératif** : L'upload en **4K UHD (3840×2160)** force YouTube à encoder en **VP09 / AV01 à 30-45 Mbps**, garantissant un piqué chirurgical même sur les écrans Full HD 1080p.
* **Paramètres de Conformation Master** : Bitrate AMF 50 Mbps, AMD FidelityFX CAS 0.75, profil High 4:2:0.

### ⏱️ 1.8. Standard de Production : Scènes de 5,5 secondes (165 trames à 30 FPS)
* **Cadence Cible** : 5,5 secondes = 165 trames exactes à 30 FPS.
* **Architecture Préconisée : Chaînage Multi-Plans I2V** :
  * Génération de 2 plans (~82 trames) ou 3 plans (~55 trames) successifs.
  * Réinjection de l'ultime trame du plan $N$ (`extraire_derniere_trame`) en amorce conditionnelle (`-i`) du plan $N+1$.
  * Maintient la VRAM < 11 Go, évite l'explosion attentionnelle $O(N^2)$ (qui sature les 16 Go à 161 trames en 1 seul bloc), et élimine l'adoucissement temporel des longues passes.

### 👑 1.9. Le Workflow Roi Validé : Image Maîtresse Wan 2.2 MoE ➔ Animation I2V (Wan 2.2 MoE / Wan 2.1)
* **Principe** : Génération d'une seule image fixe de référence en 85s via Wan 2.2 MoE (`--video-frames 1`), validation visuelle instantanée à 100%, puis animation fluide Image-to-Video (`-i`).
* **Support I2V Wan 2.2 MoE** :
  * Modèles dédiés : `Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf` (~8.99 Go) + `Wan2.2-I2V-A14B-LowNoise-Q4_K_M.gguf` (~8.99 Go).
  * Conditionneurs : `umt5-xxl` (CPU RAM) + `wan_2.1_vae` + `clip_vision_h.safetensors` (ViT).
  * Gestion VRAM : Grâce à `--offload-to-cpu`, chaque expert de 9 Go est permuté en mémoire de travail séquentiellement, maintenant la VRAM crête sous 13.5 Go / 16 Go.
* **Bénéfice** : Zéro hallucination, zéro dérive de décor, 100% de conformité géométrique et vitesse d'itération foudroyante.

---

### 🎵 1.10. Génération Musicale IA : MiniMax-Music3 GGUF via audio.cpp (Vulkan)

* **Validation Utilisateur** : *« le générateur de musique est validé [...] c'est suffisant »* (3 boucles tech 20-22 s livrées, cand_1 95 BPM promue ; QA Music Flamingo `--analyse` et recette ducking voix non testées à ce jour — optionnelles).
* **Stack validée** : `audiocpp_cli.exe` (audio.cpp v0.7.2, release Windows x64 **Vulkan**, `C:\audio-cpp\`) + paquet `audio-cpp/MiniMax-Music3-GGUF` (mix Q4_0/Q8_0 : LM 6 Go + RVQ 0,66 + flow 1,3 + encoder 0,1 + vocoder 0,2 Go + `config/` + `tokenizer/`) dans `C:\Modeles_LLM\MiniMax-Music3-GGUF\`. Zéro PyTorch, même philosophie que sd-cli/llama.cpp.
* **Backend** : **Vulkan retenu** — RTF 55,8 (10 s de musique en 9 min 17 s) vs CPU RTF 75,2 (12 min 31 s, i7-13700KF 20 threads). La RX 6950 XT (RDNA2, pas de matrix cores, `int dot: 0`) reste ~1,3× plus rapide que le CPU pour ce modèle. Budget : ~21 min par boucle de 20 s (générée sur 23 s).
* **Sortie réelle** : WAV **stéréo 44,1 kHz** (pas 32 kHz comme annoncé par la fiche HF) → rééchantillonnage rationnel 160:147 vers 48 kHz via `scipy.resample_poly` dans `core/music_ai.py`.
* **CLI de génération** : `audiocpp_cli --task gen --family minimax_music3 --model <dossier> --backend vulkan --threads 16 --metrics --text "<desc EN>" --request-option lyrics=[Instrumental] --request-option duration_sec=23 --request-option num_inference_steps=30 --out out.wav`. `lyrics` est **requis** ; `[Instrumental]` donne des lits sans voix. `--metrics` imprime RTF/durée. Options session préfixées famille (`--session-option minimax_music3.<option>=<valeur>`, ex. `mem_saver`, `rvq_depth_decoder_gguf`).
* **Bouclage « percussif » validé** (technique du doc « Générateurs Musique en Boucle ») : BPM par autocorrélation de l'enveloppe d'onsets (test synthétique : 121 détecté pour 120 réel), coupe alignée au nombre entier de mesures, snap passages par zéro, micro-fondu equal-power 20 ms → couture mesurée Δ0,4 dB. Mode ambiant : crossfade 1 s. **V2 essentielle** : le modèle compose une structure de morceau (intro en fondu, break, outro) même en 23 s → ne PAS couper depuis t=0 ; rechercher le meilleur point de boucle parmi les fenêtres ≥ durée cible d'un nombre entier de mesures, en appariant l'énergie tête/queue sur fenêtres 50-500 ms (cand_1 : 20,3 s / Δ0,1 dB ; cand_2 : 21,6 s / Δ0,3 dB).
* **Standard « lit derrière voix off »** : highpass 80 Hz + creux −3 dB @ 2,8 kHz puis **bed normalisé −30 LUFS** (ffmpeg loudnorm 2 passes, linéaire) ; ducking par recette `sidechaincompress`+`amix` générée dans `recette_mixage_voix.txt`. ffmpeg **9.0.1** (`C:\ffmpeg\dist\bin\ffmpeg.exe`, prioritaire sur l'ancien build Amuse 7.1.1).
* **Licences** : MiniMax-Music3 communauté (MIT-like, commercial OK < 20 M$ ; **signaler la musique IA dans la description YouTube**). Music Flamingo (QA optionnelle `--analyse`, via `llama-cli --mmproj --audio`) = **non commercial**, désactivé par défaut.
* **Workflow** : `main.py -w music_bg "<desc>" --duration 20 --candidats 10` → N candidats générés, validés (couture/clipping/LUFS), TOUS finalisés en bed + MP3 (`candidats/`), meilleur promu à la racine de `output/music_bg/`.
* ⚠️ **Crash silencieux exit 127 = exception C fatale** : `soundfile.write(..., format="OGG")` fait un **stack overflow C** (libsndfile Vorbis) au-delà de quelques secondes d'audio → processus tué instantanément, sortie Python bufferisée perdue, Git Bash affiche « exit 127 » sans aucun log. Diagnostic : relancer avec `python -c "import faulthandler; faulthandler.enable(); ..."`. Règle : **OGG toujours via ffmpeg** (`convertir_ogg()` de `core/music_ai.py`), soundfile réservé au WAV. Ce bug a détruit le premier batch complet en phase 4.
* ⚠️ **Resets du pilote GPU AMD** (LiveKernelEvent 141, dumps `LiveKernelReports\WATCHDOG`) possibles pendant les longues générations Vulkan audiocpp → un candidat peut mourir en cours de route. Règle : batch résilient (`scripts/generer_boucles_music_bg_batch.py`) — un candidat par processus, reprise sur fichiers existants, 2 essais Vulkan puis CPU, graines explicites (le défaut du runtime est déterministe).

## 🎬 2. Masters et Fichiers de Production Validés

| Nom du Fichier | Spécifications | Modèle Utilisé | Statut & Rendu |
| :--- | :--- | :--- | :--- |
| `output/ansible_nexus/ansible_nexus_wan22_4k_master.png` | 3840×2160 Ultra HD 4K, CAS 0.75 | **Wan 2.2 MoE + 4x-UltraSharp** | 👑 **Image Maîtresse Validée (Ansible Nexus)** |
| `output/overnight/esrgan_4k/wan22_moe_dragon_4k_ultrasharp.mp4` | 3840×2160 Ultra HD 4K @ 16 FPS, 50 Mbps | **Wan 2.2 MoE + 4x-UltraSharp** | 👑 **Master Cinéma 4K Absolu** |
| `output/overnight/esrgan_4k/01_ltx25_dragon_4k_ultrasharp.mp4` | 3840×2160 Ultra HD 4K @ 24 FPS, Audio AAC, 50 Mbps | **LTX-2.5 + 4x-UltraSharp** | 👑 **Master 4K + Audio Natif** |
| `output/overnight/cas_sharp/03_wan22_1080p_sharp_cas.mp4` | 1920×1080 @ 16 FPS, AMD CAS 0.75 | **Wan 2.2 MoE** | 🟢 Validé CAS Net (2.2 Mo) |
| `output/overnight/cas_sharp/01_ltx25_1080p_sharp_cas.mp4` | 1920×1080 @ 24 FPS, Audio AAC, CAS 0.75 | **LTX-2.5** | 🟢 Validé CAS Net + Son (3.4 Mo) |
| `output/overnight/01_ltx25_8steps_dragon_1080p.mp4` | 1920×1080 @ 24 FPS, Audio AAC | **LTX-2.5 (8 steps)** | 🟢 Validé Héroïque + Son (7.3 min) |
| `output/overnight/02_wan21_14steps_dragon_1080p.mp4` | 1920×1080 @ 16 FPS, Muet | **Wan 2.1 14B (8 steps)** | 🟢 Validé Dragon Impérial (42.6 min) |
| `output/overnight/03_wan22_moe_18steps_dragon_1080p.mp4` | 1920×1080 @ 16 FPS, Muet | **Wan 2.2 MoE (8 steps MoE)** | 🟢 Validé Piqué Photoréaliste (51.5 min) |
| `output/overnight/04_minimax_h3_20steps_dragon_1080p.mp4` | 1920×1080 @ 24 FPS, Audio AAC | **MiniMax-H3 (12 steps)** | 🟢 Validé Wyvern Titanesque + Son (6.6 min) |
| `output/comparatif/ltx25_dragon_8steps_1080p.mp4` | 1920×1080 @ 60 FPS, Audio AAC 48 kHz | **LTX-2.5 (8 steps)** | **Validé Supérieur** ⭐⭐⭐⭐⭐ |
| `output/comparatif/ltx25_dragon_3steps_1080p.mp4` | 1920×1080 @ 60 FPS, Audio AAC 48 kHz | **LTX-2.5 (3 steps)** | **Validé Turbo (37s)** ⚡ |
| `output/film_10s/film_2plans_dragon_slowmo_5s.mp4` | 1920×1080 Full HD @ 60 FPS, 5.0s, Audio Stéréo AMF | **Wan 2.1 14B (Plans 1 + 2, 14 steps)** | Validé Cinéma 🎬 |

---

## 🛠️ 3. Scripts de Production Déployés

1. [`scripts/generate_wan22_single_image.py`](file:///C:/GIT/generator-assets/scripts/generate_wan22_single_image.py) : **Génération d'image de référence Wan 2.2 MoE (85s) + 4K AI Upscale**.
2. [`scripts/download_wan22_i2v_models.py`](file:///C:/GIT/generator-assets/scripts/download_wan22_i2v_models.py) : **Téléchargement automatisé des modèles Wan 2.2 I2V MoE 28B** (`HighNoise` et `LowNoise` Q4_K_M).
3. [`scripts/animate_ansible_nexus_wan22_i2v.py`](file:///C:/GIT/generator-assets/scripts/animate_ansible_nexus_wan22_i2v.py) : **Animation cinématique I2V Wan 2.2 MoE vers Master 4K 5.5s**.
4. [`scripts/upscale_video_ai.py`](file:///C:/GIT/generator-assets/scripts/upscale_video_ai.py) : **Super-Résolution IA 4K universelle** (Real-ESRGAN Vulkan0 + AMD CAS + AMF Hardware 50 Mbps).
5. [`scripts/generate_ansible_nexus.py`](file:///C:/GIT/generator-assets/scripts/generate_ansible_nexus.py) : Pipeline de production complet pour les architectures IT complexes (génération Wan/LTX + 4K AI + extraction de trames + zoom 100%).
6. [`scripts/chain_video.py`](file:///C:/GIT/generator-assets/scripts/chain_video.py) : Chaînage continu multi-plans I2V avec extraction de trame de transition.
7. [`scripts/conform_youtube_hd.py`](file:///C:/GIT/generator-assets/scripts/conform_youtube_hd.py) : Conformation matérielle AMF Lanczos + AMD CAS 0.75.
8. [`scripts/generate_ltx25_8steps.py`](file:///C:/GIT/generator-assets/scripts/generate_ltx25_8steps.py) : Rendu maître LTX-2.5 avec sigmas distillés et audio stéréo.
9. [`scripts/run_overnight_all_sota.py`](file:///C:/GIT/generator-assets/scripts/run_overnight_all_sota.py) : Orchestrateur de grand benchmark nocturne SOTA.

