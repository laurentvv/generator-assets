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

### 🎵 1.10. Génération Musicale IA : MiniMax-Music3 GGUF via audio.cpp (Vulkan) — moteur alternatif

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

### 🎵 1.11. Génération Musicale IA : ACE-Step 1.5 Turbo GGUF — moteur PAR DÉFAUT depuis le 2026-09-05

* **Validation Utilisateur** : comparatif A/B sur le même prompt tech (3 candidats par moteur) → *« c encore mieux que l'autre !! »*. ACE-Step promu défaut (`--moteur acestep` implicite) ; Music3 reste via `--moteur music3`.
* **Stack** : `audiocpp_cli.exe` (audio.cpp v0.7.2, famille `ace_step`) + paquet monolithique `audio-cpp/audio.cpp-gguf → ACE-Step1.5-GGUF/turbo/ace-step-1.5-turbo-bf16.gguf` (**9,4 Gio**, tout embarqué : DiT turbo + LM planner 1.7B + text encoder Qwen3 + VAE, `embedded_sidecars=true`) dans `C:\Modeles_LLM\ACE-Step1.5-GGUF\`. Licence **MIT** (aucune mention obligatoire). Zéro PyTorch.
* **CLI** : `audiocpp_cli --task gen --family ace_step --model <chemin/vers/le.gguf> --backend vulkan --task-route text2music --text "<desc>" --duration-seconds 28 --num-inference-steps 8 [--seed N] [--lyrics "..."] [--request-option bpm=126] --out out.wav`. **`--model` doit pointer le .gguf LUI-MÊME** : le dossier donne une erreur trompeuse (`source 'safetensors'... missing lm_chat_template`). `--lyrics` omis = instrumental natif. Turbo distillé : 8 pas suffisent. BPM/tonalité/signature imposables (`--request-option bpm= / keyscale= / timesignature=`).
* **Perf Vulkan (RX 6950 XT)** : ~42 s par génération de 28 s (RTF ~1,5) — **~36× plus rapide que Music3** (RTF 55,8). Sortie native **48 kHz stéréo** (aucun rééchantillonnage).
* ⚠️ **q8_0 non fonctionnel** pour cette famille (`docs/gguf.md` audio.cpp : « planner sampling can fail » — « found no valid token ») → **bf16 obligatoire** (d'où 9,4 Gio au lieu de 6,2).
* ⚠️ **Fondu de sortie structurel** : le modèle termine chaque morceau par un fade de ~4-6 s (jusqu'à −62 dB). Première itération : coutures Δ62 dB. Correctifs (dans `core/music_ai.py`, profitent aux deux moteurs) : recherche de boucle **restreinte à la zone d'énergie stable** (`_zone_stable`) + marge de génération **+8 s** pour acestep (+3 s music3) dans le workflow. Résultat : coutures 0,4-3,0 dB.
* ⚠️ **Bridage CDN Hugging Face** : curl mono-connexion tombe de 18 Mo/s à ~0,6 Mo/s après quelques Gio (3 h restantes pour 9,4 Gio). Contournement : téléchargeur parallèle par segments HTTP Range, 10 connexions (`scratch/telecharger_acestep_parallele.py`) → **~112 Mo/s**, reprise sur segments, préfixe curl réutilisé. À réutiliser pour tout gros fichier HF.
* **Variantes XL (DiT 4B, testées le 2026-09-06)** : `--variante xl-turbo` — paquets **absents de HF** (seuls turbo/base y sont), hébergés sur le **miroir ModelScope** `HereIsMark/audio.cpp-gguf` (miroir fidèle : turbo identique octet pour octet). `xl-turbo-bf16.gguf` = 14,23 Gio dans `xl-turbo/`. Exige `--load-option ace_step.dit_model_path=acestep-v15-xl-turbo` (paquets spécifiques à une variante — câblé dans `generer_musique_acestep(variante=...)`). Perf Vulkan : **~92 s par candidat de 28 s (RTF ~3,3)** vs 42 s pour le turbo 2B → **~2,2× plus lent**. Tient en VRAM 16 Go avec `mem_saver` (aucun OOM). Run comparatif même prompt : coutures 2,0/11,4/4,3 dB (cand_1 promue), 80-120 BPM. `xl-sft` (CFG, 25 pas par défaut dans le workflow) non testé — installable : `uv run python scripts/download_acestep15_gguf.py xl-sft`. Installateur variantes : `download_acestep15_gguf.py [turbo|xl-turbo|xl-sft|tout]`.
* **Chanson complète avec paroles (validée le 2026-09-06)** : « La Symphonie du Silence » puis « Le Neuvième Fils » (univers Vent-Gris, paroles utilisateur) — validation utilisateur : *« c'est incroyable »* / *« chanson très bien également »*. 240-260 s, paroles FR via `--lyrics` + `--language fr` (param `langue` de `generer_musique_acestep`), balises de structure `[Intro]/[Verse]/[Chorus]/[Bridge]/[Outro]` respectées, xl-turbo, **~850-925 s de génération (RTF ~3,5-3,9)**. Le retry Vulkan automatique a sauvé le 2e morceau (1re tentative morte par reset pilote AMD — l'écueil §1.10 se confirme sur les longues durées). Nettoyage des paroles indispensable : retirer toute citation/annotation (sinon chantée). Script générique : `scripts/generer_chanson_acestep.py paroles.txt --duree 240`. Routes d'édition (repaint/cover/lego/extract) toujours non testées.
* **⚠️ Statut « clonage de musique » (générer depuis un audio de référence) : NON VALIDÉ à ce jour (clarifié le 2026-09-06)** — contrairement à ce qu'un audit hâtif a laissé entendre. ① SA3 `init_audio` : testé (RTF 0,25, BPM suivi 83,4 vs 83,3) mais **qualité « small » jugée insuffisante par l'utilisateur** — outil prometteur, pas production. ② Route cover ACE-Step : une cover générée (« Love Like Blood » → dark folk) mais **jamais validée à l'écoute**. Pas de workflow avant validation (règle AGENTS.md). Chansons avec paroles et ADN-BPM/tonalité, eux, SONT validés → workflows dédiés.
* **Workflows intégrés le 2026-09-06 (règle AGENTS.md : test validé ⇒ workflow)** : ① `main.py -w chanson "<paroles ou .txt>" [--style-musique "<EN>"] [--duration 180]` — recette chansons exacte (xl-turbo par défaut, langue fr, balises structure, style Vent-Gris par défaut). ② `main.py -w musique_adn "<style EN sobre>" -i <référence> [--duration 60] [--tonalite] [--negatif] [--lyrics paroles.txt]` — détection BPM+tonalité auto imposée au planner (test : 83 BPM + C# minor retrouvés sur llb_extrait_30s) ; corrige au passage un piège du script : le suffixe « completely instrumental » n'est plus ajouté quand des paroles sont fournies. ⚠️ Piège argparse réglé : `--variante` default None + repli par workflow (xl-turbo chanson/adn, turbo music_bg) sinon le défaut du flag écrasait la recette validée.
* **Routes audio-conditionnées (cover/repaint/lego/extract) — ⚠️ Vulkan bloqué, CPU requis (diagnostiqué le 2026-09-06)** : ces routes chargent le **VAE encoder** dont le graphe exige un buffer unique de ~4,5-4,8 Gio. Or le pilote AMD Windows plafonne la taille d'un buffer Vulkan à 4 Gio (`maxBufferSize`, VK_KHR_maintenance4 / Vulkan 1.3 — limite **par buffer**, pas la VRAM totale) → « Requested buffer size exceeds device buffer size limit » immédiat, la VRAM reste quasi vide dans le moniteur. La taille du buffer est fixe (30 s de source a demandé PLUS que 60 s : 4,84 vs 4,52 Gio) → raccourcir l'audio ne sert à rien. Le XL OOM même avant l'encoder (14 Gio + graphs > 16 Go). **Solution validée : `--backend cpu --threads 20`** — cover 30 s en 77 s (RTF 2,58) sur turbo 2B. Première utilisation : cover « Love Like Blood » (groupe allemand de rock gothique) → dark folk Vent-Gris.
* **Pipeline « ADN depuis référence » (2026-09-06, nuit — carte honnête des essais)** : `scripts/generer_depuis_reference.py <audio> --style "<EN>" [--tonalite] [--negatif] [--avec-paroles]` — BPM + tonalité auto (ou forcés) imposés au planner. **Seule version validée par l'utilisateur : `llb_xl_adn.mp3`** (45 s, C# mineur détecté sur extrait 30 s, description SOBRE « German gothic rock 1990, dark wave, hypnotic tribal groove, deep pulsing bass, chiming chorus guitars », xl-turbo). **Tout ce qui a été « amélioré » ensuite a été rejeté** : tonalité full-track D# majeur → « gentil/pop » ; basse poussée (« dominant bass leading ») → 73 % basse, « POP pire qu'avant » ; agressivité punk → 163 BPM ; probe mineur + négatif dur + mastering compressé −12 LUFS → « loupé aussi ». **Leçons** : ① le mode MAJEUR sonne pop quoi qu'on fasse — toujours vérifier/imposer mineur pour du rock sombre ; ② les superlatifs du style (« dominant », « hard-hitting ») sont pris trop au pied de la lettre → descriptions sobres ; ③ la sensibilité compositionnelle du planner penche pop ; pistes non testées : modèle **base** (CFG, contrôle fin), **repaint** sur l'original lui-même, itérations à graines autour de la recette gagnante `llb_xl_adn`. SA3 `init_audio` : échelle utile ≈ 0,7 (0,2-0,45 = copie quasi littérale avec chant fantôme, ≥0,85 = ancre perdue, 0,7 = pulse conservé mais qualité « small » jugée insuffisante).
* **Comparatif mesuré (même prompt, 3 candidats)** : Music3 → coutures ≤ 0,3 dB, ~25 min/candidat, 32→48 kHz ; ACE-Step turbo 2B → coutures ≤ 3 dB (0,4 promu), ~42 s/candidat, 48 kHz natif, meilleur à l'écoute (jugement utilisateur) ; ACE-Step xl-turbo 4B → coutures ≤ 4,3 dB (2,0 promu), ~92 s/candidat, 48 kHz natif (écoute comparative à valider par l'utilisateur).
* **Édition** : routes `--task-route complete|lego|extract|cover|repaint` (+ `--audio`, `--repaint-start/end`) non testées à ce jour — stems/repaint documentés dans `docs/models/ace_step.md` du dépôt audio.cpp.

### 🎵 1.12. MusicGen Melody Large (Meta, 2024) — testé le 2026-09-06, NON RETENU

* **Motif du test** : demande d'évaluation de `facebook/musicgen-melody-large` (2,62 Md params, avril 2024, text2music + conditionnement mélodie par chroma 12 bins).
* **Faisabilité philosophie dépôt (C++ Vulkan + GGUF, zéro PyTorch) : ❌ impossible**. audio.cpp v0.7.2 n'a **aucune famille musicgen** (model_specs + CHANGELOG + dépôts GGUF HF `audio-cpp/audio.cpp-gguf` et miroir ModelScope vérifiés — le seul tensor « musicgen » est un encodeur de style interne à ControlFoley). Aucun GGUF valide sur HF : `yyang12/MusicgenV1-f16-gguf` = archi llama/chat (conversion sans rapport), `mradermacher/music_generation_model-GGUF` = merge llama MIDI-texte. **Seule voie locale : transformers (PyTorch CPU)** — test fait en venv isolé jetable `C:\temp\mgt` (torch 2.14+cpu, transformers 5.16.1), modèle safetensors f32 9,8 Gio dans `C:\Modeles_LLM\musicgen-melody-large` (téléchargé via hf_transfer multi-connexions).
* **Perf mesurées (i7-13700KF, 20 threads, CPU, f32)** : text2music **RTF 11,60** (10 s en 115 s) ; avec chroma **RTF 11,89**. Modèle chargé en <1 s (mmap). Sortie **32 kHz mono** PCM16, très chaude (−8,4 LUFS, **+1,5 dBTP** → limiteur obligatoire avant tout usage). Comparaison : ACE-Step turbo RTF 1,5 Vulkan 48 kHz stéréo → **~8× plus lent, qualité inférieure attendue (modèle 2024)**.
* **⚠️ Régression silencieuse transformers v5 : le conditionnement mélodie est INOPÉRANT**. Triple preuve : ① kwarg `melody` (API v4) **ignoré sans erreur** (l'argument v5 est `audio`) ; ② A/B même graine + 2 mélodies différentes (LLB vs symphonie) → **sorties bit-identiques** (diff 0,0) ; ③ chroma réelle vs chroma nulle injectées manuellement dans `generate()` → identiques aussi (le code de `modeling_musicgen_melody` référence `input_features` mais la boucle `generate()` v5 ne l'utilise pas). Métrique cohérente : cosinus chroma sortie vs référence 0,140 pour un plancher de bruit à 0,118. **MusicgenMelody en v5 = text2music pur** ; tester la mélodie sérieusement exigerait transformers 4.x (non fait — voir verdict).
* **⚠️ Bug transformers v5 n°2** : `MusicgenMelodyFeatureExtractor` appelle `torchaudio.functional.resample` sur une **liste** → `AttributeError` dès que l'audio n'est pas à 32 kHz. Contournement : rééchantillonner soi-même (`rolloff=0.945, lowpass_filter_width=24`) et passer `sampling_rate=32000`.
* **Licence ⚠️ : CC-BY-NC 4.0 (non commercial)** — incompatible avec une chaîne YouTube monétisée, contrairement à ACE-Step (MIT) et MiniMax-Music3. Seconde raison bloquante, indépendante de la technique.
* **Verdict : NON RETENU, aucune intégration.** Plus lent, mono 32 kHz, licence NC, pas de route GGUF, et son seul atout différenciant (calage sur mélodie) est cassé dans transformers v5 — besoin déjà couvert localement par SA3 `init_audio` (essence de référence, RTF 0,25, Vulkan) et ACE-Step route cover (CPU, RTF 2,58). À retester uniquement si ① audio.cpp ajoute une famille musicgen-GGUF, ou ② transformers corrige la régression melody en v5.
* **Nettoyage fait le 2026-09-06 sur décision utilisateur** (« on oublie ») : modèle 9,8 Gio + venv + artéfacts d'écoute supprimés (~13,3 Gio libérés). Le modèle est retéléchargeable à tout moment (`snapshot_download('facebook/musicgen-melody-large')` avec hf_transfer) si un retest devient pertinent (voir conditions ci-dessus).
* **Leçon transverse** : kwargs inconnus **ignorés silencieusement** par les processors transformers v5 (« will be ignored » en warning) — toujours vérifier par A/B (même graine, entrée changée) qu'un conditionnement atteint vraiment le modèle.

### 🎙️ 1.13. Voix off TTS + clonage vocal français — 3 moteurs GGUF testés le 2026-09-06 (chaîne YouTube)

* **Besoin** : cloner une voix française (référence 11,8 s de l'utilisateur, `output/comparatif_tts/ref_voix_laurent.wav`) puis lui faire lire des textes **avec expression**. Stack 100 % locale conforme philosophie : `audiocpp_cli` (v0.7.2, Vulkan) + paquets GGUF q8_0 monolithiques dans `C:\Modeles_LLM\`.
* **Paquets installés** : `Qwen3-TTS-12Hz-1.7B-Base-GGUF` (2,51 Gio), `VoxCPM2-GGUF` (2,75 Gio), `Fish-Audio-S2-Pro-GGUF` (5,88 Gio) + **bonus** `Qwen3-ASR-0.6B-GGUF` (1,07 Gio) pour transcrire la référence (voir écueil ③).
* **Commandes validées** :
  ```powershell
  # Zéro-shot (fish / voxcpm2 uniquement) :
  audiocpp_cli --task tts --family fish_audio --model <fish q8_0.gguf> --backend vulkan --metrics --text "<FR>" --out out.wav
  audiocpp_cli --task tts --family voxcpm2  --model <voxcpm2 q8_0.gguf> --backend vulkan --metrics --language French --text "<FR>" --out out.wav
  # Clonage (les 3) :
  #   qwen3 : --voice-ref ref.wav --reference-text "<transcript de ref>" [--instruct "<style/émotion>"] --language French
  #   fish  : --voice-ref ref.wav --reference-text "<transcript>" (+ balises expression DANS le texte : [whisper] [excited] [pause]…)
  #   voxcpm2 : --voice-ref ref.wav (transcript NON requis)
  # ASR (transcription d'une référence) :
  audiocpp_cli --task asr --family qwen3_asr --model <qwen3-asr-0.6b-q8_0.gguf> --backend vulkan --language fr --audio ref.wav
  ```
* **Perf Vulkan (RX 6950 XT)** : RTF fish 1,46 / voxcpm2 1,68 sur ~7 s de parole (chargement inclus). Sorties **mono** : fish 44,1 kHz • voxcpm2 48 kHz • qwen3 24 kHz (limite qualité HF — à réserver intermédiaire, rééchantillonner).
* **Expression** : fish = **balises inline libres dans le texte** (`[whisper]`, `[excited]`, `[pause]`… 15 000 tags, la plus riche) ; qwen3 = `--instruct "<instruction style/émotion>"` ; voxcpm2 = non testé. Voix design (voix décrite plutôt que clonée) dispo : `--task vdes` (paquet qwen3 VoiceDesign séparé, non installé).
* **⚠️ Écueils** : ① qwen3-TTS **Base** = pas de zéro-shot (« requires voice clone reference audio ») ET **transcript obligatoire** (« ICL mode requires reference text ») ; ② fish = zéro-shot OK mais **transcript obligatoire pour le clonage** (« inline reference audio requires reference_text ») ; ③ pas de transcript sous la main → transcription ASR locale (qwen3-asr 0.6B) : pipeline complet autonome validé (m4a → wav mono ffmpeg → ASR → clone). Voix de référence : enregistrement smartphone m4a 48 k stéréo converti `ffmpeg -ac 1 pcm_s16le` — suffisant.
* **Licences** : qwen3-tts/qwen3-asr **Apache-2.0** ✓ production chaîne OK • voxcpm2 **Apache-2.0** ✓ • fish s2-pro **Research License = commercial payant** ⚠️ (référence qualité uniquement, pas de production chaîne sans licence).
* **À écouter** (`output/comparatif_tts/ECOUTE_*.mp3`) : `ref_voix_laurent` (original) vs `qwen_fr_clone_laurent` (instruct présentateur), `voxcpm2_fr_clone_laurent` (transcript-free), `fish_fr_clone_laurent` (balises whisper/excited) + `*_sans_ref` pour le timbre natif fish/voxcpm2. Phrase test identique pour tous : « Trois heures du matin, le serveur principal s'effondre… ». **Validation utilisateur en attente** — voxcpm2 rend la phrase en 4,6 s vs ~6 s ailleurs (débit rapide ou troncature ? à l'écoute).
* **⚠️ Niveau de la référence** : l'enregistrement smartphone mesurait **−39,3 LUFS** (crêtes −16,5 dBTP → seulement 15 dB de marge). Référence normalisée en **−18 LUFS / −1,5 dBTP** (`ffmpeg -af "loudnorm=I=-18:TP=-1.5:LRA=7"` — LRA 2,5 LU donc gain quasi linéaire, sans dénaturer la voix) → `ref_voix_laurent_norm.wav`, clones relancés en `*_v2.wav`. **Règle future : viser −18/−20 LUFS à la capture (micro près de la bouche), et vérifier le niveau AVANT tout clonage** (`ffmpeg -af volumedetect`). Sorties v2 mesurées ~−19 à −20 dB moyen.
* **Validation utilisateur (2026-09-06)** : *« franchement les 3 sont bien »* — qwen3-tts, VoxCPM2 et Fish S2-Pro jugés tous bons à l'écoute sur le clonage FR avec expression. **Choix production chaîne = licence** : qwen3-tts et VoxCPM2 (Apache-2.0) libres d'usage ; Fish réservé à la référence qualité (commercial payant). Détail différenciant si besoin trancher : voxcpm2 = 48 kHz natif (meilleure bande passante), qwen3 = `--instruct` (direction d'expression la plus souple), fish = balises inline les plus riches.
* **Workflow intégré le 2026-09-06** : `main.py -w voix_off "<texte ou fichier.txt>" --voix-ref <wav/mp3/m4a> [--instruct "…"] [--moteur qwen3|voxcpm2|fish] [--lufs-voix -16]` — pipeline complet : contrôle du niveau de la référence (seuil −26 dB moyen → normalisation auto −18 LUFS), transcription ASR auto (qwen3-asr) si le moteur l'exige, génération, finalisation −16 LUFS + MP3. Sorties `output/voix_off/<nom>/`. Testé fin à fin sur qwen3 (**RTF 0,64** Vulkan, chargements compris) et fish. Code : `core/voix_off.py` + `workflows/voix_off.py`. Note : la finalisation loudnorm linéaire (TP −3) peut plafonner à ~−19 LUFS sur les voix très crêtées — sans conséquence derrière un bed à −30 LUFS.
* **Non testés** : stabilité sur textes longs (chunking `--text-chunk-size` fish 200 cars), voix design `--task vdes`, chatterbox (anglais seulement), omnivoice (600+ langues, licence à vérifier), qualité 1.7B CustomVoice qwen3.

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

