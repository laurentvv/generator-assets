# Recherche GitHub — écosystème ComfyUI comme source d'idées de workflows

**Date : 2026-09-09** • Méthode : recherche `gh` (compte laurentvv) — topic `comfyui`,
galeries/awesome-lists, écosystème MiniMax-H3/Ref2VA, vidéo Wan/LTX, audio, 3D,
pipelines de production, exemples officiels `ComfyUI_examples`, release notes ComfyUI 0.34.

**Contexte :** le workflow `h3_ref2va` (MEMORY_BANK §1.16) reproduit en CLI sd-cli le mécanisme
du nœud ComfyUI « HR Endless Sampler » (hradec). Objectif de cette recherche : cataloguer les
techniques ComfyUI copiables/adaptables à notre stack 100 % CLI Vulkan/GGUF (sd-cli, audio.cpp,
trellis.cpp, ffmpeg), et poser une source de veille dédiée (ajoutée — cf. §9).

---

## TL;DR — idées adaptables, par priorité

| # | Idée | Source | Gain potentiel | Effort |
|---|---|---|---|---|
| 1 | **Turbo LoRA Ref2VA 8 steps** (`minimax_h3_ref2v_turbo_8step_v1.0_768p_bf16.safetensors`) via `--lora-model-dir` de `vid_gen` (le flag existe déjà !) | [lightx2v/Minimax-h3-Turbo](https://huggingface.co/lightx2v/Minimax-h3-Turbo) (dl 1,3 M) | ~2,5× plus rapide sur h3_ref2va (8 steps au lieu de 20) ; 4 steps dispo en fl2v | Faible (A/B à valider) |
| 2 | **Réf de continuation downscalée** : décoder la queue, réduire à un canvas aligné 32 px, ré-encoder comme réf plus petite → moins de VRAM réf-attention → chunks plus grands | HR Endless Sampler, param `video_continuation_res` | Chunks 1080p plus longs sur 16 Go | Faible (ffmpeg scale avant `--ref-video`) |
| 3 | **Fenêtre audio qui « remonte »** : la réf audio doit se TERMINER au raccord et englober le son déjà joué (pas redémarrer) pour une vraie continuité sonore | [ComfyUI-H3-Motion-Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context) (928★) | Continuité musicale entre chunks (à tester sur la boucle 18 chunks) | Faible (découpe WAV) |
| 4 | **Prompts par chunk écrits par un LLM/VLM** qui analyse les frames déjà rendues (mécanique Gemma4 du HR Endless Sampler) ; alternative clé en main : Prompt-Rewriter-LoRA (Qwen3.6-27B) | hradec + [lightx2v/MiniMax-H3-Prompt-Rewriter-LoRA](https://huggingface.co/lightx2v/MiniMax-H3-Prompt-Rewriter-LoRA) | Cohérence dramaturgique de la boucle sans fin | Moyen (llama.cpp/VLM local) |
| 5 | **Banque de 634 prompts H3 publics complets** + 25 guides (site web galerie) | [awesome-MiniMax-H3-cases](https://github.com/SkyNotSilent/awesome-MiniMax-H3-cases) (167★) → [galerie](https://h3-field-notes-production.up.railway.app/en/) | Améliorer immédiatement nos prompts H3 | Nul (lecture) |
| 6 | **FaceRefine vidéo** : détection + tracking visage par frame, crop plein cadre, régénération, recomposition (détection de cuts via PySceneDetect pour ne pas lisser à travers) | [ComfyUI-H3-FaceRefine](https://github.com/Carasibana/ComfyUI-H3-FaceRefine) (355★) | Réparer les visages petits/lointains des vidéos H3 (chaîne YouTube) | Moyen (ffmpeg crop + sd-cli img2img/ip_adapter) |
| 7 | **H3 pour images fixes** : générer un paquet de frames court, décoder, garder une frame (VAE audio inutile) — avec turbo LoRA = stills rapides avec réf personnage | [ComfyUI-MiniMax-H3-Image-Studio](https://github.com/astropuzzo/ComfyUI-MiniMax-H3-Image-Studio) (136★) | Édition d'image par référence, cohérence perso | Faible |
| 8 | **Sérialisation production type `production.json`** : état/approbations/stale/QC, routage par mode T2VA/I2VA/FL2VA/Ref2VA, distinction réf sémantique vs keyframe | [short-drama-production](https://github.com/suihe1/short-drama-production) (148★) | Cadre d'orchestration pour la chaîne YouTube (episode → shots → QC) | Moyen |
| 9 | **IC-LoRA LTX** (depth/pose/edges/HDR/**DubIt**/upscaler/motion-track) — le flag LoRA sd-cli existe pour `vid_gen` | [ComfyUI-LTXVideo](https://github.com/Lightricks/ComfyUI-LTXVideo) (4120★) | Contrôle caméra/mouvement et doublage sur LTX-2.5 | Moyen (à tester sur GGUF Q4) |

---

## 1. MiniMax-H3 / Ref2VA — l'écosystème le plus actif (tout créé depuis juillet 2026)

### 1.1 Turbo LoRA — la piste n° 1 (test immédiat possible)

- Repo HF : `lightx2v/Minimax-h3-Turbo` (1,31 M dl, ♥876) — fichiers :
  `fl2v_turbo_{4step v0.1→v1.2, 8step v1.0}` et **`ref2v_turbo_{4step v0.1, 8step v1.0}`**,
  variantes `*_768p_bf16` et `_comfyui_bf16` (rangs redimensionnés pour ComfyUI — prendre les
  **non-comfyui** pour sd-cli). Miroirs : `larryvrh/MiniMax-H3-Turbo-Lora` (389 k dl),
  `drbaph/...-ComfyUI`, et un **modèle fusionné** `MATLOWAI/minimax-h3-fused-turbo-int8-convrot`
  (turbo déjà fusionné dans les poids, pas de LoRA à charger).
- Benchmarks croisés (Kablex) : H3 dense natif 50 steps ≈ 650 s (RTX 4090) ; **turbo LoRA dense
  4 steps ≈ 190 s** ; VSA 4 steps ≈ 72 s. Sur notre RX 6950 XT (70 min/chunk de 22 frames),
  un passage 20 → 8 steps serait ~2,5×, 20 → 4 steps ~5× (4 steps ref2v = v0.1 immature,
  préférer 8 steps v1.0).
- **Faisabilité sd-cli : OK a priori** — `sd-cli vid_gen` expose `--lora-model-dir` et
  `--lora-apply-mode auto` (mode `at_runtime` sur modèle quantisé). Invoquer via balise
  `<lora:nom:1.0>` dans le prompt, comme en image. Points de vigilance : base Q4_K_M + LoRA bf16
  (A/B qualité obligatoire vs sortie actuelle), CFG probablement à baisser (≈1) comme sur les
  autres turbo, résolution 768p pour les variantes `768p`.
- À consigner selon la règle AGENTS.md : test → soumission à l'écoute/validation → seulement
  ensuite workflow + MEMORY_BANK.

### 1.2 HR Endless Sampler (hradec) — au-delà de ce qu'on a reproduit

Notre `h3_ref2va` reproduit le chaînage ; le nœud original fait **plus**, et ces mécanismes sont
transposables à notre boucle 18 chunks (commit 89a82ff, non lancée) :

- **Planification par LLM** : Gemma4 12B QAT analyse le prompt complet + toutes les références,
  planifie le minutage action/plan de CHAQUE chunk, puis **analyse les frames déjà rendues** et
  écrit un petit prompt dédié par chunk (continuité/cohérence). → Chez nous : llama.cpp + VLM GGUF
  local (on a déjà Qwen3-VL 32B pour H3 !). Ou LoRA dédiée `lightx2v/MiniMax-H3-Prompt-Rewriter-LoRA`
  (base Qwen3.6-27B, `infer.py` + `prompt_template.py` fournis).
- `video_continuation` : 22 frames portées du chunk précédent (min 5), passées à H3 comme
  `<Video N>`/`<Audio N>` synchronisés — correspond à notre queue ffmpeg.
- **`video_continuation_res`** : réduit la taille du bloc référence (decode → resize canvas
  aligné 32 px → re-encode) pour économiser la VRAM d'attention référence et permettre des
  chunks plus grands ; l'audio et la keyframe frontière restent pleine résolution. → Chez nous :
  downscaler les frames de `--ref-video` via ffmpeg (`scale=` aligné 32) avant de les passer.
- **Keyframe frontière automatique** : les 5 dernières frames du chunk précédent servent de
  petite keyframe de raccord (interne au latent H3 — non reproducible en CLI tant que sd-cli
  n'expose pas d'ancrage, cf. §1.3).
- `gemma4_mtp` : décodage spéculatif MTP 4 tokens (perf du « directeur » LLM) — pertinent si on
  adjoint un llama.cpp.
- Le projet prévoit un **port LTX 2.5** « in the near future » — à suivre (veille posée).

### 1.3 ComfyUI-H3-Motion-Context (NikoDemon80, 928★) — chaînage bit-exact

Le chaînage propre : la queue du clip précédent est **tranchée dans le latent** (pas de
decode/resize/re-encode) → zéro dérive couleur/adoucissement en chaîne longue. Côté audio :
l'ancre doit **se terminer au raccord et remonter dans le son déjà joué** — c'est la différence
entre « le modèle continue la piste » et « le modèle écrit quelque chose qui ressemble ».
Inclut un « Seam Probe » qui mesure si un raccord est une vraie continuation. Requiert ComfyUI
0.34+ (ancrages à frame arbitraire `MiniMaxH3AddGuide`).
→ **Adaptable maintenant** : la leçon audio (fenêtre WAV qui remonte) s'applique à notre
`--ref-video-audio`. Le tranchage latent nécessiterait une évolution sd-cli (feature request
potentielle à ouvrir chez leejet : « latent carry-over / tail slice pour Ref2VA »).

### 1.4 Références sémantiques horodatées (ethanfel, 9★ mais idée propre)

`ComfyUI-MiniMaxH3-Timed-References` : présente des images **au texte-encodeur Qwen seulement**
(sémantique, pas de slot référence natif, pas d'encodage VAE) — `<Picture N>` non horodaté ou
horodaté (« à 2 s, montre la voiture rouge »), et même des frames choisies d'une vidéo avec leurs
PTS réels. → Technique de prompt-engineering transposable **si sd-cli expose un jour des images
dans le prompt H3** (aujourd'hui notre Qwen3-VL ne voit que le texte) ; sinon à garder comme
feature request. C'est le bon geste pour « plan de tournage » : images de intentions horodatées.

### 1.5 Hybrid Loader fl2va+ref2va (scottmudge, 165★)

Constat étayé : la sortie brute de `ref2va` souffre d'un problème qualité d'entraînement confirmé
(minimax), alors que `fl2va` est plus propre ; >97 % des poids sont identiques, seuls les
`adaln_proj` (routage des modalités) diffèrent. Recette communautaire validée : **base fl2va +
overlay des seuls `adaln_proj` de ref2va (blocs 25–49)** = qualité fl2va + capacité référence.
→ Chez nous : fusion offline des safetensors int8 (~19,5 Go chacun, mmap) puis conversion GGUF
— lourd mais faisable ; à considérer si la qualité ref2va bloque la validation utilisateur.
(variante communautaire GGUF déjà visible sur HF : `t8star/…DasiwaREF2VAHybridV1_0…`).

### 1.6 FaceRefine (Carasibana, 355★)

H3 rend mal les visages quand la tête est petite dans le cadre (propriété indépendante de la
résolution). Pipeline : détection par frame + tracking, crop normalisé plein canvas, re-génération
par H3, recomposition ; **détection des cuts durs** (PySceneDetect) pour ne pas lisser à travers.
→ Adaptable CLI : ffmpeg/opencv detect-crop-track + sd-cli (img2img + ip_adapter identité) +
composite ffmpeg overlay, par shot. Cas d'usage chaîne YouTube (plans parlants éloignés).

### 1.7 H3 pour l'image fixe (astropuzzo, 136★)

Génère un paquet de frames court → décode → sélectionne une frame : donne du **T2I/I2I/édition
par référence** à la qualité H3 (le VAE audio n'est pas requis). Avec turbo LoRA c'est rapide.
→ Adaptable : `vid_gen` court + extraction ffmpeg de la meilleure frame ; utile pour images avec
référence personnage cohérente ( Thumbnails/visuels chaîne, assets jeu stylisés).

### 1.8 Outils prompt H3 (à lire avant la prochaine session vidéo)

- **awesome-MiniMax-H3-cases** (167★) : galerie web de **1818 vidéos jouables + 634 prompts
  publics complets + 25 guides pratiques** — la meilleure source de grammaire prompt H3.
- `duckyshell/ComfyUI-MiniMaxH3-Prompt-Writer` (166★), `lololerigolo60/Minimax-H3-prompt-studio`
  (23★), `wodeshijie1234/faithful-h3-web` (15★) : rédacteurs structurés T2VA/I2VA/FL2VA/L2VA/Ref2VA.
- `klfzqxs/ref2va-h3-video-optimizer` (11★) : **optimiseur hill-climbing de prompt** — LLM écrit
  le script → traduit en prompt ref2va → rend ComfyUI → extrait frames/audio → LLM note → itère
  (prompt = seule variable, seed/params fixes). → Transposable avec llama.cpp en juge
  (chaîne YouTube : boucle d'amélioration des prompts de plans, budget GPU maîtrisé).
- `seesee75-commits/ComfyUI-MiniMaxH3-Director` (285★), `j955229/…Motion-Director` (97★),
  `karuvanan/MiniMax-H3-Director-Cut-Studio` (112★) : éditeurs timeline/storyboard au-dessus de
  H3 (TTS Qwen3 inclus chez Director-Cut) — inspiration UX pour un futur `main.py -w episode`.

### 1.9 Accélérations CUDA — NON adaptables (noter et ignorer)

`Kablex/ComfyUI-Ref2VA-VSA` (91★, attention clairsemée 75 %, 4 steps, 13,5 Go),
`Saganaki22/ComfyUI-VDN-H3` (198★, Video Delta Net), `ComfyUI-sol-attn`, DLSS5/NGX nodes.
Toutes exigent kernels CUDA/Triton — hors champ Vulkan. Seule la leçon « 4–8 steps suffisent »
est à retenir (cf. turbo LoRA).

## 2. Wan / LTX

- **VACE** (Wan 2.2) : `vace_reference_to_video.json` dans les exemples officiels ComfyUI =
  référence→vidéo tout-en-un (contrôle, édition, inpainting vidéo). **sd-cli ne supporte pas
  VACE** → feature request leejet à ouvrir si besoin d'édition vidéo Wan.
- Contrôle caméra Wan : `camera_image_to_video_wan_example.json` (exemples officiels).
- **LTX IC-LoRA** (repo officiel Lightricks, 4120★) : workflows LTX-2.3 distilled avec LoRAs
  « In-Context » — depth + pose + edges, **motion tracking**, **HDR**, **DubIt** (doublage
  automatique), upscaler spatial pixel. Le flag `--lora-model-dir` existe sur `vid_gen` sd-cli →
  tester une IC-LoRA sur notre LTX-2.5-Distilled Q4_K_M.
- `MajoorWaldi/ComfyUI-Majoor-OmniCam` (58★) : mise en page/animation caméra (inspiration
  vocabulaire caméra pour prompts).
- `kakachiex2/comfyui-ltx2-efficient` (25★) : sampler efficace low-VRAM LTX-2 (référence de
  réglages steps/CFG basse VRAM).

## 3. Audio / voix

- **MMAudio** (`hkchengrex/MMAudio`, 2268★ + wrapper kijai 574★) : vidéo→audio synchronisé de
  haute qualité — comblerait les sorties Wan/LTX muettes (H3 Ref2VA a l'audio natif, pas Wan/LTX).
  PyTorch : pas GGUF/Vulkan → idée seulement (ou veille audio.cpp pour une éventuelle famille).
- **ACE-Step-ComfyUI** (officiel, 79★) : modes cloud/local + **génération d'échantillons pilotée
  LLM**. Surtout : `hackall360/ACE-Step-ComfyUI-LoRa-Trainer` (5★) — **entraînement de LoRA
  ACE-Step** : piste sérieuse pour casser le « plafond pop » (§1.11 MEMORY_BANK) en entraînant
  une LoRA gothic rock (nécessite PyTorch/GPU training — hors stack actuelle, à garder en réserve).
- **Breeze-TTS-2** nodes (Saganaki22, 66★) : voice clone / voice design / direction bilingue.
- **LatentSync** (bytedance, 6056★) : lip-sync vidéo ; `aigcpanel` (5533★) : digital human
  (synthèse vidéo+voix+clonage). Pour la chaîne YouTube si un présentateur virtuel devient
  pertinent (PyTorch, hors stack — noté pour mémoire).

## 4. 3D / personnages

- **ComfyUI core 0.34 intègre TRELLIS2** (PR kijai #14718, avec Pixal3d et Sam3d-body) :
  confirmation que notre pari TRELLIS.2 (trellis.cpp) est dans le courant principal.
- **Photoshoot** (ralksta, 76★) : « Person Builder » 44 champs (corps/visage/cheveux/makeup/
  vêtements) → prompt anglais compilé, puis **série entière cohérente** (cadrages/poses/expressions
  varient, la personne reste) + matrices de styles N&B/couleur mesurées. → Idée directe pour un
  workflow `portrait_serie` : ficher personnage JSON → compilateur prompt → N variations
  (Flux/SDXL + ip_adapter) — prolonge `rpg_portrait`/`character_makeup`/`turnaround3d`.
- `ComfyUI-3D-Pack` (3860★), `ComfyUI-Hunyuan3DWrapper` (1040★) : écosystème image→3D
  concurrent/homologue de TRELLIS — veille passive.

## 5. Pipelines de production (chaîne YouTube)

- **Pixelle-Video** (ATH-MaaS, 27 930★) : sujet → script → illustrations/vidéos IA → voix off →
  BGM → montage, en un clic. Notre équivalent existe en briques (`voix_off`, `music_bg`, `video`,
  `conform_youtube_hd`) — l'architecture (découpage par phrase/scène, gabarits visuels, file
  d'attente) est une bonne référence d'orchestration.
- **short-drama-production** (suihe1, 148★) : « skill » production **traçable** : `production.json`
  (tâches, approbations, causes d'échec, rough-cut, QC), propagation `stale` quand un actif amont
  change, échantillons avant génération payante, **routage T2VA/I2VA/FL2VA/Ref2VA** et distinction
  réf sémantique vs keyframe. → Modèle pour industrialiser la chaîne (plusieurs dizaines de plans).
- **open-video** (117★) : « Ollama pour H3 » (install/pull/run) — retenir l'idée `--dry-run`
  (planifier/valider sans consommer de GPU) que nos workflows ont déjà (`dry_run`) : à généraliser.
- `reelforge` (60★) : repo GitHub → reel vertical fini (source→vidéo) ; `MeiGen-AI-Design-MCP`
  (1746★) : MCP design vidéo ; `Calliope` (144★), `Mix-Studio` (282★) : studios locaux.

## 6. Divers outillage

- **ComfyUI-to-Python-Extension** (2379★) : traduit un workflow ComfyUI en code Python — accélère
  nos « traductions » de workflows ComfyUI → recettes sd-cli (comme h3_ref2va).
- **LanPaint** (1386★) : inpainting sans réentraînement pour tout modèle SD (dont vidéo) —
  dépend si sd-cli ajoute un jour les masques par token H3 (cf. §7).
- IC-Light (kijai, 1158★) : relighting d'objets/personnages — idée pour packshots assets jeu.
- SeedVR2 VideoUpscaler (2827★), GIMM-VFI (477★) : upscale vidéo / interpolation (nous avons
  déjà RIFE + upscale sd-cli — équivalents suffisants).
- Galeries de workflows à miner : `ZHO-ZHO-ZHO/ComfyUI-Workflows-ZHO` (7802★),
  `yolain/ComfyUI-Yolain-Workflows` (2200★), exemples officiels `ComfyUI_examples`
  (dossiers video/wan/ltxv/audio/3d…).

## 7. ComfyUI core v0.34 — signaux de ce que sd-cli pourrait ajouter

Points pertinents pour nous dans les release notes du 2026-08-26 :
`MiniMaxH3AddGuide` (ancres image/audio à frame arbitraire) ; **masques de bruit par token
vidéo ET audio sur H3** (= inpainting vidéo+audio) ; prompt embeddings H3 (contourner Qwen au
runtime) ; support TRELLIS2/Pixal3d/Sam3d-body ; nœuds partenaires **Wan 3.0** ; sauvegarde
HDR/AV1/mkv/webm ; « taeh3 » (mini-VAE preview H3). Les releases du cœur = bon prédicteur des
évolutions sd-cli à demander/suivre.

## 8. Actions proposées (ordre suggéré)

1. **Test turbo LoRA ref2v 8 steps** (règle AGENTS : jamais de workflow avant validation) —
   recette : télécharger `minimax_h3_ref2v_turbo_8step_v1.0_768p_bf16.safetensors` (downloader
   parallèle si gros), A/B même seed/params que §1.16 avec `<lora:…:1.0>` + steps 8 + CFG bas,
   soumettre à l'utilisateur.
2. Boucle endless : intégrer (a) réf downscalée alignée 32 px, (b) fenêtre audio « qui remonte »,
   (c) prompts par chunk par VLM local (ou Prompt-Rewriter-LoRA) avant le go/no-go 18 chunks.
3. Lire la galerie awesome-H3-cases (634 prompts) et en distiller une mini-guide prompt H3
   (FR → grammaire EN) dans MEMORY_BANK §1.16.
4. Feature requests leejet (sd-cli) : latent carry-over Ref2VA (tranchage queue), images
   sémantiques dans le prompt Qwen H3, VACE Wan 2.2.
5. Moyen terme : FaceRefine CLI ; portrait_serie (inspiration Photoshoot) ;
   production.json (inspiration short-drama) pour la chaîne.

## 9. Veille ajoutée (`scripts/veille_versions.py`, section `comfyui`)

Nouvelle source « écosystème ComfyUI », 3 volets (même mécanique que les sources existantes,
baseline au premier run) :
- **`comfyui-core`** : releases de `comfyanonymous/ComfyUI` (notes archivées dans
  `output/veille/notes/`) — signale nouvelles familles/nœuds (cf. §7) ;
- **`comfyui-<repo>`** : dernier commit d'une liste curatée — `hradec/ComfyUI-HR-Endless-Sampler`,
  `NikoDemon80/ComfyUI-H3-Motion-Context`, `comfyanonymous/ComfyUI_examples`,
  `Lightricks/ComfyUI-LTXVideo` ;
- **`comfyui-nouveaux-repos`** : diff du top étoiles des repos `topic:comfyui` créés sur les
  45 derniers jours (≥20★) — détecte les nouveaux packs H3/nodes comme ceux cités ici.
