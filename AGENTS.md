# AGENTS.md — Conventions pour agents IA (dépôt generator-assets)

## 📚 Documentation des outils locaux : À MAINTENIR SYSTÉMATIQUEMENT

Les outils installés hors du dépôt possèdent des **README personnalisés** (écrits pour ce poste,
pas les README GitHub d'origine). **Toute nouvelle connaissance sur ces outils doit y être
consignée immédiatement** (nouvelle version installée, commande validée, écueil rencontré,
benchmark mesuré) :

| Fichier | Outil | Contenu |
|---|---|---|
| `C:\audio-cpp\README.md` | audio.cpp (Vulkan) | Version installée + notes de release, familles de modèles (ace_step, minimax_music3…), commandes validées, écueils (`--model` = chemin du .gguf, q8_0 ace_step KO, paquets XL sur ModelScope), scripts de mise à jour |
| `C:\ffmpeg\README.md` | FFmpeg 9.0.1 (build custom) | Optimisations machine (AMF, SVT-AV1, libfdk-aac), recettes validées (bed −30 LUFS loudnorm 2 passes, ducking sidechaincompress, OGG), rebuild MSYS2 |

Ne pas confondre avec les README de dépôts clonés (ex. `C:\llama.cpp\README.md` = README GitHub,
ne pas modifier). Autres emplacements d'outils : `C:\SD` (sd-cli), `C:\Modeles_LLM` (modèles GGUF).

## 🗂️ Documentation du dépôt

- `README.md` — catalogue des workflows et statuts (mettre à jour à chaque évolution).
- `docs/MEMORY_BANK.md` — **banque mémoire des stacks validées et écueils** (une section par
  domaine, ex. §1.10 Music3, §1.11 ACE-Step) : y consigner tout apprentissage opérationnel.
- `docs/Générateurs Musique en Boucle.md` — analyse de fond + implémentation retenue.

## 🔧 Règles du dépôt

- Environnement : `uv` (Python 3.11+), Windows, Git Bash. Commandes : `uv run python main.py -w <workflow>`.
- Philosophie : **moteurs C++ Vulkan + GGUF, zéro PyTorch** (sd-cli, llama.cpp, audio.cpp).
- GPU : AMD RX 6950 XT 16 Go (RDNA2, pas de CUDA) — tout nouveau moteur doit tourner en Vulkan/CPU.
- Code : docstrings et logs en français, identifiants en anglais, prompts modèles en anglais.
- Gros téléchargements HF/ModelScope : `scripts/telecharger_gros_fichier_parallele.py <url> <dest>`
  (contourne le bridage CDN mono-connexion, ~10× plus rapide).
- Veille versions (audio.cpp, FFmpeg, Python, paquets, modèles GGUF, llama.cpp) :
  `uv run python scripts/veille_versions.py` — état dans `output/veille/`, rapport uniquement
  (jamais de mise à jour automatique). Automatisation quotidienne 9 h planifiée côté session
  (titre « Veille quotidienne des versions … »).
