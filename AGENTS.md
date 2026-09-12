# AGENTS.md — Conventions pour agents IA (dépôt generator-assets)

## 🎯 Contexte d'usage (buts finaux)

**Fabrique locale universelle de médias générés par IA — tout projet nécessitant image, son, vidéo ou musique.** Deux productions principales actuelles :
1. **Un jeu sous Godot** — assets générés : matériaux PBR, maillages, objets 3D IA image→GLB (workflow `mesh_ia`, TRELLIS.2), boucles musicales OGG (workflow `music_bg`), ambiances, sprites ;
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
| `C:\SD\README.md` | sd-cli / stable-diffusion.cpp (Vulkan) | Release (commit) installée, familles de modèles (Flux, SDXL+LoRAs, Wan 2.1/2.2, LTX-2.5, MiniMax-H3, upscalers), commandes validées (img/vid_gen/upscale), procédure maj + rollback |
| `C:\trellis\README.md` | trellis.cpp (Vulkan) | Version installée (`version.json`, lu par la veille), GGUF TRELLIS.2 requis (10 fichiers, 16,4 Go, `C:\Modeles_LLM\trellis2-gguf`), commandes validées (image → GLB PBR, workflow `mesh_ia`), perfs mesurées (512 = ~11 min, 1024 = ~55 min), procédure maj + rollback |

Ne pas confondre avec les README de dépôts clonés (ex. `C:\llama.cpp\README.md` = README GitHub,
ne pas modifier). Autres emplacements d'outils : `C:\SD` (sd-cli), `C:\Modeles_LLM` (modèles GGUF),
`C:\IA\qwentts.cpp` (qwen-tts — **géré par CE dépôt** (récupéré d'`ai-doc2video` le 2026-09-12 soir) :
`uv run python scripts/manage_qwentts.py --check|--models|--update|--backup|--rollback` — maj git,
sauvegardes `C:\IA\qwentts_backups` (5 conservées), build Vulkan, smoke test, rollback auto ;
ne jamais modifier le clone à la main ; notes dans MEMORY_BANK §1.20).

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
- **Avant tout lancement de génération lourde** (audio.cpp, sd-cli, trellis.cpp) :
  `uv run python scripts/check_charge_systeme.py` — vérifie CPU/GPU/RAM/VRAM (exit 1 =
  machine occupée → attendre un créneau libre, jamais lancer sur une machine chargée ; cf.
  smoke test v0.7.3 du 2026-09-08 : RTF mesuré 3,3× trop lent à cause d'une contention GPU).
  Seuils ajustables (`--cpu-threshold`, `--gpu-threshold`, `--ram-threshold`, `--vram-threshold`, `--duration`).
- Code : docstrings et logs en français, identifiants en anglais, prompts modèles en anglais.
- Gros téléchargements HF/ModelScope : `scripts/telecharger_gros_fichier_parallele.py <url> <dest>`
  (contourne le bridage CDN mono-connexion, ~10× plus rapide).
- Veille versions (audio.cpp, sd-cli, trellis.cpp + GGUF TRELLIS.2 sur HF, FFmpeg, Python,
  paquets, modèles GGUF + org audio-cpp sur HF, **nouveaux modèles LLM/VLM GGUF tendance
  sur HF** (top trending en diff, baseline 2026-09-07), llama.cpp, **sa3.cpp** (port C++/GGML
  de Stable Audio 3 — Vulkan, zéro PyTorch — releases en info, pas installé ; famille
  stable_audio déjà couverte par audio.cpp), **outils système versionnés**
  (SDK Vulkan LunarG — prérequis de tous les builds natifs, détection via
  sdk.lunarg.com ; Blender — pipeline skins MPFB ; Godot — moteur du jeu ;
  uv ; CMake — alertes info une seule fois par version amont, jamais de maj
  automatique), **écosystème ComfyUI**
  (releases du cœur + commits de repos clés H3/LTX + nouveaux repos topic:comfyui en diff,
  baseline 2026-09-09 — source d'idées de workflows, rapport de recherche :
  `docs/recherche_comfyui_2026-09-09.md`)) : `uv run python scripts/veille_versions.py` — état dans
  `output/veille/`, rapport uniquement (jamais de mise à jour automatique). Déclenchement
  **automatique à l'ouverture de session** (pas de cron) : le hook SessionStart relance la
  veille en arrière-plan si la dernière date de plus de 20 h (fraîcheur lue sur la date de
  `output/veille/rapports.log`, log de fond : `output/veille/veille_arriere_plan.log`) ;
  le script alimente `output/veille/maj_en_attente.json`. Lancement manuel toujours
  possible à la demande : « lance la veille » en session.
- Hook SessionStart ZCode (`.zcode/config.json` → `scripts/hook_session_start.py`) : à chaque
  nouvelle session du projet, les entrées des 7 derniers jours de `docs/veille_journal.md`
  sont injectées automatiquement dans le contexte, ainsi que les mises à jour en attente
  lues dans `output/veille/maj_en_attente.json` (voir 🔄 Process de mise à jour) et le
  **statut de l'issue sd-cli [#1946](https://github.com/leejet/stable-diffusion.cpp/issues/1946)**
  (régression master-848 rollbackée le 2026-09-07 — un appel API GitHub léger par session,
  alerte uniquement si réponses/changement d'état ; état vu : `output/veille/issue_sdcli_1946.json`).
  Validé en session réelle le 2026-09-07 ; premier usage : approuver le hook via la bannière
  « Review » (gate de confiance des hooks de scope projet). Test manuel :
  `uv run python scripts/hook_session_start.py`. À supprimer une fois une release sd-cli
  corrigée installée (fonction `bloc_issue_sdcli` + état + cette mention).
- 🎯 **Instruction permanente (2026-09-07) : dès que la veille signale un NOUVEAU modèle de
  musique/audio potentiellement compatible, lancer le test sans attendre d'accord** (sources :
  section veille `hf-modeles-gguf` pipeline `text-to-audio`, nouvelles familles dans audio.cpp,
  miroir ModelScope). Recette de test de référence : candidat gothic rock 30 s — description
  sobre « German gothic rock 1990, dark wave, hypnotic tribal groove, deep pulsing bass,
  chiming chorus guitars », 83 BPM + « C# minor » imposés (`--request-option`), graine 42
  (exemples : `output/test_acestep_sft/`). Téléchargement via le downloader parallèle si gros
  fichier. Soumettre à l'écoute utilisateur, consigner le verdict dans MEMORY_BANK (statut
  « testé, non validé » — jamais de workflow avant validation, cf. règle ci-dessus).
  Contexte : plafond réalisme instrumental rock d'ACE-Step (§1.11) ; objectif = un moteur
  musical GGUF Vulkan rendant basse/batterie/guitares crédibles.
- 🛡️ **Modèles : vérifier la retéléchargeabilité AVANT toute suppression dans `C:\Modeles_LLM`,
  et si l'accord utilisateur n'est pas 100 % explicite (ambiguïté possible), REFORMULER la liste
  validée avant d'exécuter** (incident 2026-09-08 : consigne mal interprétée → 4 modèles supprimés
  au lieu de 0, heureusement restaurés depuis HF).
  Lister tous les repos de l'org, pas seulement le repo principal — certains modèles vivent dans
  des repos dédiés hors `audio.cpp-gguf` (ex. `audio-cpp/MiniMax-Music3-GGUF`,
  `audio-cpp/VibeVoice-7B-GGUF`) :
  `curl -s "https://huggingface.co/api/models?author=audio-cpp"` (+ miroir ModelScope au besoin).
  En cas de doute, demander. Fichiers irremplaçables (retirés de partout) : **aucun à ce jour**
  (constat 2026-09-06 ; tenir cette liste à jour si la veille signale un retrait réel).
- 🧩 **Tout test réalisé avec l'utilisateur et VALIDÉ par l'utilisateur doit devenir un workflow**
  (`main.py -w <nom>`) : encapsuler la recette gagnante (code dans `core/` + `workflows/`,
  enregistrement, README §Workflows, MEMORY_BANK) — jamais la laisser en script autonome ou
  commande CLI ad hoc. Réciproque : **ne PAS créer de workflow pour un test non validé** —
  le consigner d'abord dans MEMORY_BANK (statut « testé, non validé ») et attendre la
  validation utilisateur (ex. essence SA3 / cover ACE-Step, en attente le 2026-09-06).
- ⚡ **`h3_ref2va` : TOUJOURS utiliser/proposer le mode `--turbo`** (LoRA distillé 8 steps,
  VALIDÉ utilisateur le 2026-09-09 — « très bonne qualité, son très bien » : ~38 min vs
  ~70 min pour 22 frames, sampling −64 %, raccord référence ≥ baseline ; MEMORY_BANK §1.16).
  La recette de base 20 steps (sans `--turbo`) ne sert qu'en A/B qualité ou sur demande
  explicite. `scripts/proto_endless_h3.py` (boucle 18 chunks, NON validée) l'utilise déjà :
  ~11,5 h au lieu de ~21 h, et le raccord chunk→chunk est le point critique à juger en premier.

## 🔄 Process de mise à jour (à exécuter quand la veille signale une nouveauté)

Règles générales : **une seule mise à jour à la fois** • vérifier qu'aucun `audiocpp_cli.exe` /
`ffmpeg.exe` ne tourne avant de toucher aux binaires • tester après chaque mise à jour •
mettre à jour les README d'outils (voir §Documentation) • commit/push des fichiers du dépôt
(docs, uv.lock). Jamais de mise à jour en plein batch de génération.

📝 **Suivi des majs en attente** (`output/veille/maj_en_attente.json`) : fichier maintenu par
le script de veille (`_sauver_maj_en_attente`) — une nouveauté y entre au moment de sa
détection et disparaît automatiquement quand la version installée rattrape la dernière vue ;
l'agent peut aussi y retirer une entrée refusée, appliquée ou devenue obsolète.
**Instruction permanente (2026-09-11) : dès qu'une maj listée est appliquée en session
(ou devient obsolète), retirer IMMÉDIATEMENT son entrée de ce fichier** — sinon le hook
SessionStart la resignale à chaque session et redemande à l'utilisateur une maj déjà
faite — **et consigner l'application dans `docs/veille_journal.md` avec les infos de
version complètes** (avant→après, commit, résultat de la vérification post-maj).
Lisible à chaque session
via le hook SessionStart, qui le signale à l'agent ; cela ne change rien à la règle :
**jamais de mise à jour sans accord explicite**. Quand une session y voit des nouveautés
absentes de `docs/veille_journal.md`, les y ajouter (format journal, avec détail du
changelog depuis les notes archivées) puis commit/push (docs uniquement).

| Composant | Procédure | Vérification post-maj | Rollback |
|---|---|---|---|
| **audio.cpp** | 1) Lire les notes archivées (`output/veille/notes/audio-cpp_<tag>.md`) — repérer nouvelles familles de modèles et correctifs `ace_step`. 2) `C:\audio-cpp\update.ps1` (sauvegarde auto + test `--list-devices` intégré). 3) `ls C:\audio-cpp\model_specs` → nouvelles familles ? | Smoke test : 1 génération 12 s `--family ace_step` turbo (`--model` = chemin du .gguf) ; comparer RTF | `C:\audio-cpp\backups\backup_<version>_<date>/` (3 dernières conservées) |
| **sd-cli** | 1) Lire les notes archivées (`output/veille/notes/sd-cli_<tag>.md`). 2) Télécharger l'asset `sd-master-<sha>-bin-win-vulkan-x64.zip` de la release GitHub. 3) Sauvegarder `.exe`/`.dll` dans `C:\SD\backups\` puis extraire par-dessus `C:\SD\`. | Smoke test : 1 image Flux steps 4 + `sd-cli.exe --version` (nouveau commit) | `C:\SD\backups\backup_<date>/` |
| **FFmpeg** | `MSYSTEM=UCRT64 /c/msys64/usr/bin/bash.exe -lc 'cd /c/ffmpeg && bash update.sh'` (détecte, rebuild, teste AMF tout seul ; MSYS2 déplacé de `C:\ffmpeg\msys64` vers `C:\msys64` le 2026-09-09, `C:\msys64\ucrt64\bin` au PATH utilisateur) | `ffmpeg -version` + une mesure `loudnorm` rapide (pipeline music_bg) | `C:\ffmpeg\dist.bak/` |
| **Paquets Python** | 1) `uv pip list --outdated` (revue rapide : rien de cassant ?). 2) `uv lock --upgrade && uv sync` | `uv run python -c "import core, workflows"` + `main.py --help` | `git checkout -- uv.lock && uv sync` |
| **Modèles GGUF (ACE-Step…)** | `uv run python scripts/download_acestep15_gguf.py <variante>` (si bridage CDN → `scripts/telecharger_gros_fichier_parallele.py`) | Smoke test 1 génération de la variante ; consigner taille/RTF dans MEMORY_BANK | Supprimer le .gguf (les autres variantes sont indépendantes) |
| **qwentts.cpp** | Veille commits amont (source `qwentts.cpp`) → sur 🆕 et accord utilisateur : `uv run python scripts/manage_qwentts.py --update` (backup binaire + git pull + build Vulkan + smoke test + rollback auto intégrés). Modèles : `--models` / `--download-model <fichier> [--force]` (catalogue HF `Serveurperso/Qwen3-TTS-GGUF`) | `uv run python scripts/manage_qwentts.py --check` (git/binaires/modèles/sauvegardes) ; `--models --verify-hash` si modèles touchés | `uv run python scripts/manage_qwentts.py --rollback [nom]` (sauvegardes `C:\IA\qwentts_backups`, 5 conservées) |
| **Python (interpréteur)** | Uniquement sur besoin explicite : `uv python install 3.12.x` puis mettre à jour `.python-version` | `uv sync` complet + import tests | Ancien interpréteur conservé par uv |
| **llama.cpp / autres** | Selon l'outil (repo dédié) ; même logique : notes → maj → smoke test → README | — | — |

Après TOUTE mise à jour : mettre à jour `C:\audio-cpp\README.md` / `C:\ffmpeg\README.md` /
`C:\SD\README.md` (section version + notes de release), `docs/MEMORY_BANK.md` si un écueil
ou une perf change, **`scripts/engines_manifest.json`** (épinglage des installateurs
`scripts/install_windows.ps1` et `scripts/install_unix.sh` : nouvelle version épinglée ou
retour à `latest` selon le cas, par plateforme),
puis commit/push côté dépôt.
