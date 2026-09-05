# AGENTS.md — Conventions pour agents IA (dépôt generator-assets)

## 🎯 Contexte d'usage (buts finaux)

**Fabrique locale universelle de médias générés par IA — tout projet nécessitant image, son, vidéo ou musique.** Deux productions principales actuelles :
1. **Un jeu sous Godot** — assets générés : matériaux PBR, maillages, boucles musicales OGG (workflow `music_bg`), ambiances, sprites ;
2. **Une chaîne YouTube générée à 100 % en IA à partir de documentations sysadmin** — voix off (TTS) + lits musicaux −30 LUFS avec ducking automatique + vidéos IA (Wan/LTX/MiniMax-H3) + masters 4K conformés YouTube.

Tout nouveau besoin média (autre jeu, autre chaîne, habillage, démo…) est un cas d'usage légitime. Les composants doivent rester génériques et réutilisables ; toute évolution doit servir un projet concret (ou l'outillage qui les maintient : veille, docs, téléchargement).

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
- `docs/veille_journal.md` — **journal de veille** : chaque nouveauté de stack détectée par la
  veille y est consignée avec son impact projet. **À lire au démarrage d'une session** pour
  connaître les évolutions récentes des outils (nouveaux modèles disponibles, correctifs,
  changements cassants).
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

## 🔄 Process de mise à jour (à exécuter quand la veille signale une nouveauté)

Règles générales : **une seule mise à jour à la fois** • vérifier qu'aucun `audiocpp_cli.exe` /
`ffmpeg.exe` ne tourne avant de toucher aux binaires • tester après chaque mise à jour •
mettre à jour les README d'outils (voir §Documentation) • commit/push des fichiers du dépôt
(docs, uv.lock). Jamais de mise à jour en plein batch de génération.

| Composant | Procédure | Vérification post-maj | Rollback |
|---|---|---|---|
| **audio.cpp** | 1) Lire les notes archivées (`output/veille/notes/audio-cpp_<tag>.md`) — repérer nouvelles familles de modèles et correctifs `ace_step`. 2) `C:\audio-cpp\update.ps1` (sauvegarde auto + test `--list-devices` intégré). 3) `ls C:\audio-cpp\model_specs` → nouvelles familles ? | Smoke test : 1 génération 12 s `--family ace_step` turbo (`--model` = chemin du .gguf) ; comparer RTF | `C:\audio-cpp\backups\backup_<version>_<date>/` (3 dernières conservées) |
| **FFmpeg** | `MSYSTEM=UCRT64 /c/ffmpeg/msys64/usr/bin/bash.exe -lc 'cd /c/ffmpeg && bash update.sh'` (détecte, rebuild, teste AMF tout seul) | `ffmpeg -version` + une mesure `loudnorm` rapide (pipeline music_bg) | `C:\ffmpeg\dist.bak/` |
| **Paquets Python** | 1) `uv pip list --outdated` (revue rapide : rien de cassant ?). 2) `uv lock --upgrade && uv sync` | `uv run python -c "import core, workflows"` + `main.py --help` | `git checkout -- uv.lock && uv sync` |
| **Modèles GGUF (ACE-Step…)** | `uv run python scripts/download_acestep15_gguf.py <variante>` (si bridage CDN → `scripts/telecharger_gros_fichier_parallele.py`) | Smoke test 1 génération de la variante ; consigner taille/RTF dans MEMORY_BANK | Supprimer le .gguf (les autres variantes sont indépendantes) |
| **Python (interpréteur)** | Uniquement sur besoin explicite : `uv python install 3.12.x` puis mettre à jour `.python-version` | `uv sync` complet + import tests | Ancien interpréteur conservé par uv |
| **llama.cpp / autres** | Selon l'outil (repo dédié) ; même logique : notes → maj → smoke test → README | — | — |

Après TOUTE mise à jour : mettre à jour `C:\audio-cpp\README.md` / `C:\ffmpeg\README.md`
(section version + notes de release), `docs/MEMORY_BANK.md` si un écueil ou une perf change,
puis commit/push côté dépôt.
