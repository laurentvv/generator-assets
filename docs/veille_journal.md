# 🔭 Journal de veille — évolutions de la stack

Journal alimenté par la veille quotidienne (9 h — `scripts/veille_versions.py`).
**But : garder les agents IA au courant** des nouveautés de la stack locale
(audio.cpp, FFmpeg, Python/paquets, modèles GGUF, llama.cpp) pour en tirer
parti dans le projet. Toute nouveauté pertinente y est consignée avec son
impact projet ; les écueils et stacks validées restent dans `MEMORY_BANK.md`.

Format : `AAAA-MM-JJ • source • changement • impact projet / action`

---

- **2026-09-06 • TTS • clonage vocal français validé sur 3 moteurs GGUF (détails §1.13 MEMORY_BANK)** : qwen3-tts 1.7B / VoxCPM2 / Fish S2-Pro testés avec la voix de l'utilisateur (11,8 s) — Vulkan, RTF 1,5-1,7, mono (44,1/48/24 kHz). Écueils : qwen3 Base et fish exigent le transcript de la référence (contourné par transcription locale qwen3-asr 0.6B, bonus réutilisable sous-titres) ; voxcpm2 clone sans transcript. Expression : fish = balises inline `[whisper]/[excited]` (le plus riche, mais licence commerciale payante), qwen3 = `--instruct`. **Impact projet : voix off chaîne = qwen3-tts (Apache-2.0) en piste sérieuse, à valider à l'écoute** ; 12,5 Gio de modèles installés dans `C:\Modeles_LLM\`.
- **2026-09-06 • veille • angle mort sd-cli corrigé + watch org audio-cpp ajouté** : `veille_versions.py` surveille désormais **sd-cli/stable-diffusion.cpp** (commit local via `sd-cli.exe --version` vs tag de release `leejet/stable-diffusion.cpp` — état actuel : commit `6b3edaa` = release `master-841-6b3edaa` du 30/08, **à jour**) et **toute l'org audio-cpp sur HF** (nouveaux repos dédiés + nouveaux fichiers de `audio.cpp-gguf`, suite au rectificatif MiniMax-Music3). Création de `C:\SD\README.md` (modèle audio-cpp/FFmpeg : release, familles modèles, commandes validées img/vid_gen/upscale, maj+rollback) ; AGENTS.md mis à jour (veille, tableau maj, table doc).
- **2026-09-06 • audio-cpp • RECTIFICATIF : MiniMax-Music3-GGUF n'a PAS disparu — repo dédié** (l'alerte précédente était fausse). L'org `audio-cpp` héberge **3 repos** : `audio.cpp-gguf` (collection principale), **`MiniMax-Music3-GGUF`** (toutes variantes q4_0/**q4_k**/q8_0/bf16 — plus que la copie locale) et `VibeVoice-7B-GGUF` (7B absent du repo principal). **Leçon : pour juger de la retéléchargeabilité d'un modèle, lister TOUS les repos de l'org (`https://huggingface.co/api/models?author=audio-cpp`), pas seulement l'arborescence d'`audio.cpp-gguf`.** La règle AGENTS.md « vérifier avant suppression » reste pertinente ; liste des irremplaçables : **vide à ce jour**. Inventaire du même jour : musique = ace_step/minimax_music3/**heartmula**/**midashenglm_gen**/stable_audio (dont **Medium**, défaut de spec, jamais testé) ; sep = htdemucs/bs_roformer/mel_band_roformer ; veille **sd-cli/stable-diffusion.cpp absent de `veille_versions.py`** (angle mort à combler).
- **2026-09-06 • test HF • `facebook/musicgen-melody-large` testé → NON RETENU (détails §1.12 MEMORY_BANK)** : aucune route GGUF/audio.cpp (famille inexistante, aucun GGUF valide sur HF/ModelScope) → test via transformers 5.16.1 CPU en venv isolé. RTF 11,6, 32 kHz mono, licence **CC-BY-NC** ( incompatible chaîne monétisée), et **régression v5 : conditionnement mélodie inopérant** (A/B même graine → sorties bit-identiques ; kwargs v4 ignorés silencieusement + bug resample). **Impact projet : aucun changement de stack** — musique = ACE-Step 1.5 (MIT, RTF 1,5) ; essence de référence = SA3 init_audio. Modèle 9,8 Gio supprimé le jour même sur décision utilisateur après écoute (retest possible si audio.cpp ajoute musicgen-GGUF ou si transformers v5 corrige la régression melody).
- **2026-09-06 • stable_audio/SA3 • nouveau moteur « essence d'une référence » validé** : Stable Audio 3 small-music f16 (2,2 Gio, HF audio.cpp-gguf) — mode `init_audio` = conditionnement stylistique par audio, **fonctionne sur Vulkan à RTF 0,25** (pas de limite buffer contrairement aux routes audio d'ace_step). Fidélité mesurée : BPM 83,4 vs 83,3 sur la référence, énergie suivie. **Impact projet : « se caler sur un type de musique en audio » → SA3 init_audio est l'outil dédié** (ACE-Step reste pour chansons avec paroles). À écouter : `output/music_chanson/llb_sa3_essence.mp3`.
- **2026-09-06 • ace-step/audio.cpp • routes audio-conditionnées (cover/repaint/lego/extract) bloquées sur Vulkan** : le VAE encoder exige un buffer unique de ~4,5-4,8 Gio, au-dessus de la limite `maxBufferSize` (4 Gio) du pilote AMD Windows — limite **par buffer** (VK_KHR_maintenance4), pas de VRAM totale (d'où aucun pic VRAM visible). Buffer de taille fixe, indépendante de la durée de la source. **Workaround validé : `--backend cpu --threads 20`** (cover 30 s en 77 s, RTF 2,58, turbo 2B). Test réel : cover « Love Like Blood » (groupe allemand) réinterprété en dark folk Vent-Gris. **Impact projet : réinterprétations calées sur un audio existant = CPU obligatoire pour l'instant** ; si une future release audio.cpp/ggml splitte ce buffer ou si le pilote AMD relève la limite → retester en Vulkan.
- **2026-09-06 • veille • mise en place du système** : script `scripts/veille_versions.py`
  (audio.cpp, FFmpeg, Python, paquets uv, paquets GGUF ACE-Step HF, repo ACE-Step-1.5,
  llama.cpp ; notes de release archivées dans `output/veille/notes/`), automatisation
  quotidienne 9 h, process de mise à jour documenté dans `AGENTS.md`. Baseline : audio.cpp
  v0.7.2, FFmpeg 9.0.1, Python 3.12.9, ACE-Step repo v0.1.8, llama.cpp v0.4.0.
- **2026-09-06 • paquets-python • protobuf 7.36.0 → 7.36.1** (release v36.1 du 31/08) :
  optimisation du chemin d'analyse Python pur pour les noms d'enum JSON personnalisés +
  tests ; C# (alias d'enum) et Rust (refactor crates) touchés. **Impact projet : aucun**
  (dépendance transitive, rien de cassant) — appliqué et vérifié (`fcfaeb0`).
- **2026-09-06 • à surveiller • paquets GGUF ACE-Step sur HF** : les variantes XL
  (xl-turbo, xl-sft) n'y sont toujours PAS (uniquement sur le miroir ModelScope
  `HereIsMark/audio.cpp-gguf`). Si un jour elles apparaissent sur HF, préférer HF
  (miroir officiel audio-cpp). Le script de veille liste les fichiers ACE-Step du repo HF.
