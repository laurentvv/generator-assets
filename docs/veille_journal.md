# 🔭 Journal de veille — évolutions de la stack

Journal alimenté par la veille quotidienne (9 h — `scripts/veille_versions.py`).
**But : garder les agents IA au courant** des nouveautés de la stack locale
(audio.cpp, FFmpeg, Python/paquets, modèles GGUF, llama.cpp) pour en tirer
parti dans le projet. Toute nouveauté pertinente y est consignée avec son
impact projet ; les écueils et stacks validées restent dans `MEMORY_BANK.md`.

Format : `AAAA-MM-JJ • source • changement • impact projet / action`

---

- **2026-09-06 • ace-step/audio.cpp • routes audio-conditionnées (cover/repaint/lego/extract) bloquées sur Vulkan** : le VAE encoder exige un buffer unique de ~4,5-4,8 Gio, au-dessus de la limite `maxBufferSize` (4 Gio) du pilote AMD Windows — limite **par buffer** (VK_KHR_maintenance4), pas de VRAM totale (d'où aucun pic VRAM visible). Buffer de taille fixe, indépendante de la durée de la source. **Workaround validé : `--backend cpu --threads 20`** (cover 30 s en 77 s, RTF 2,58, turbo 2B). Test réel : cover « Love Like Blood » (Killing Joke) réinterprété en dark folk Vent-Gris. **Impact projet : réinterprétations calées sur un audio existant = CPU obligatoire pour l'instant** ; si une future release audio.cpp/ggml splitte ce buffer ou si le pilote AMD relève la limite → retester en Vulkan.
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
