# PLAN.md — Audit architecture & plan d'action (generator-assets)

> Audit réalisé le 2026-09-24 sur `claude/peaceful-galileo-7ecsdr` (HEAD `0ff10a0`), sans modification de code.
> Périmètre lu : `main.py`, `workflows/` (43 workflows enregistrés), `core/` (32 modules), `scripts/` (≈120 fichiers),
> `pyproject.toml`, `uv.lock`, `.gitignore`, `scripts/engines_manifest.json`, installateurs, hook SessionStart,
> `README.md`, `AGENTS.md`, `.agents/skills/generator-assets/`, `python_health_report.md`.
> Vérifications exécutées : `ruff check` (284 alertes, dont 176 F401), `main.py --list-workflows`, `main.py --check`,
> et une reproduction à l'exécution du bug des valeurs par défaut CLI (voir P0 ci-dessous).
> Écosystème de référence : application CLI Python 3.12 gérée par `uv`, qui pilote des moteurs C++ externes
> (sd-cli, audio.cpp, trellis.cpp, llama.cpp, Blender, FFmpeg) en sous-processus.

---

## 1. Diagnostic

**Bloquant (bugs avérés, contrat consommateurs à risque)**
- `main.py:675-690` : des valeurs par défaut argparse **globales** (`--duration 2.0`, `--frames 16`, `--fps 12.0`) écrasent celles des workflows, parce que `main.py:959-1086` transmet toujours la clé, même à `None` ou à sa valeur par défaut. Reproduit à l'exécution : `-w chanson paroles.txt` donne une chanson de **2 s** au lieu de 180 s ; `-w video --frames 25` sort en **12 fps** au lieu de 24. Même défaut pour `music_bg`, `musique_adn`, `musique_essence`, `audio_ambience`, `h3_ref2va` et `sfx`.
- `main.py:128-130` : les entrées 33 à 35 du menu interactif (`update_sd`, `update_llama`, `update_vulkan`) appellent `WorkflowRegistry.get()` avant leur branche dédiée. Elles lèvent donc toujours `ValueError` et ne s'exécutent jamais.
- `core/config.py:148` + `core/diffusion.py:87` et `core/upscaler.py:40-41` : sortie fixe `temp_render.png` / `temp_esrgan_*.png` dans le répertoire courant. Deux appels parallèles (`ai-doc2video` + `video-analys-ia`) se marchent dessus. Si sd-cli ne produit rien, une ancienne image passe le contrôle `os.path.exists`.
- `workflows/batch.py:68-80` : les erreurs par asset sont avalées, et le code retour vaut 0 même quand 0/N asset réussit. Les consommateurs en `check=True` ne voient rien.

**Important (dette structurelle)**
- `main.py` fait 1 102 lignes : `lancer_mode_interactif` a une complexité cyclomatique de 69 (rang F), la table des 149 arguments argparse est plate et le dict de ~150 clés est recopié à la main. Le menu interactif et le registre divergent : 4 workflows manquent au menu (`h3_ref2va`, `monoplan_ia`, `outfit`, `character3d`) et le prompt affiche « Choix (1-37) » pour 42 entrées.
- Couches inversées : du code de production importe des scripts ad hoc, par exemple `core/cinema.py:221`, `workflows/musique_adn.py:17` et `workflows/outfit.py:194`. De plus, `core/render_medieval_themes.py` et `core/render_morphology_tests.py` sont des expériences rangées dans `core/`.
- Chemins Windows codés en dur hors de `core/config.py`, dont un profil utilisateur (`C:\Users\laurent\...`) : `core/mpfb_ops.py:307`, `core/render_*.py`, `core/voix_robot.py:29-37`, `workflows/character_makeup.py:85`, `core/cinema.py:320`. Cela contredit `scripts/install_unix.sh`. Par ailleurs, `scripts/check_charge_systeme.py` repose sur PowerShell/WMI seulement (exit 2 sous Linux et macOS, ce qui casse le contrat consommateur).
- **Zéro test automatisé, zéro CI, zéro outillage dev** déclaré dans `pyproject.toml` (ni ruff, ni pytest). Les 9 fichiers `scripts/test_*.py` sont des scripts Blender manuels.
- Artefacts lourds versionnés : `godot_assets/` (234 fichiers, ~300 Mo, et répertoire de sortie **par défaut** via `DEFAULT_OUTPUT_DIR`), `scratch/` et `test_output_clothes/`, suivis malgré `.gitignore`. Le dossier `.git` pèse 277 Mo.

**Mineur**
- La documentation diverge : 43 workflows enregistrés, contre « 40 » dans `SKILL.md` et « 36 » dans `README.md:1628`. Python est annoncé en « 3.11+ » dans `AGENTS.md:81` mais exige `>=3.12` dans `pyproject.toml`. La description de `pyproject.toml` se limite à « Assets 2D & 3D pour Godot ». `huggingface_hub` est importé mais non déclaré.
- Aucune journalisation structurée : 148 `print()` dans `core/`, `workflows/` et `main.py`, et 29 `except Exception` larges. Le stderr Blender est capturé puis perdu (`core/blender_ops.py:186,308`).
- Aucune vérification d'intégrité (SHA-256) des binaires téléchargés par `scripts/install_windows.ps1`, `scripts/install_unix.sh` et `scripts/engines_manifest.json`.

---

## 2. Checklist de Refactoring

### 2.1 Bugs CLI et contrat d'appel (priorité absolue)
- [ ] [P0] `main.py:675-690, 959-1086` — Passer les arguments spécifiques à un workflow en `default=None` (`--duration`, `--frames`, `--fps`, `--pitch`, `--lufs`, `--factor`…) et ne construire `params` qu'avec les clés **non `None`** (`{k: v for k, v in ... if v is not None}`), pour que chaque workflow applique son propre défaut.
- [ ] [P0] `workflows/generate.py:34`, `workflows/tileable.py:32`, `workflows/spritesheet.py:40`, `workflows/variations.py:46`, `workflows/sfx.py:37`, `workflows/audio_ambience.py:55`, `workflows/anim_loop.py:39-40`, `workflows/video.py:49-50` — Remplacer le motif `params.get(k, défaut)`, inopérant quand la clé existe avec la valeur `None`, par `params.get(k) or défaut`, ou mieux par un accès typé (voir 2.2).
- [ ] [P0] `main.py:128-130` — Traiter `update_sd`, `update_llama` et `update_vulkan` **avant** `WorkflowRegistry.get()` (ou les sortir du dict des workflows) pour réparer les entrées 33 à 35 du menu.
- [ ] [P0] `workflows/batch.py:68-80` + `main.py:1089-1099` — Renvoyer un statut d'échec et sortir en code ≠ 0 quand `completed < total` (option `--continue-on-error` pour garder le mode tolérant), avec la liste des assets en échec.
- [ ] [P0] `core/diffusion.py:87-168`, `core/upscaler.py:40-80`, `core/config.py:148` — Remplacer `TEMP_IMAGE` et `temp_esrgan_*.png` par des fichiers `tempfile.mkstemp()` / `TemporaryDirectory()` uniques par appel. Supprimer la sortie avant le lancement de sd-cli, pour qu'une image obsolète ne soit jamais relue, puis charger avec `Image.open(...).copy()` et nettoyer.
- [ ] [P1] `core/blender_ops.py:181,303`, `core/mesh_ia.py:262` — Même correction pour `temp_blender_*.py` et `_reduction.py`, écrits dans le cwd ou le dossier de sortie : passer par `tempfile`.
- [ ] [P1] `tests/test_cli_contract.py` (nouveau) — Figer le contrat consommateurs par des tests : codes retour, `--seed` transmis, défauts effectifs par workflow (garde-fou contre la régression ci-dessus).

### 2.2 Structure des modules et du point d'entrée
- [ ] [P1] `main.py` — Découper en `cli/parser.py` (sous-commandes argparse ou groupes par famille : image, audio, vidéo, 3D, maintenance), `cli/interactive.py` et `cli/maintenance.py` (`--update-*`). Cible : aucune fonction au-dessus de 15 de complexité cyclomatique.
- [ ] [P1] `workflows/base.py` — Ajouter à chaque workflow une déclaration de paramètres (dataclass `Params` ou `add_arguments(parser)`), pour générer à la fois l'argparse, le menu interactif et la doc. Le dict manuel de 150 clés de `main.py` disparaît.
- [ ] [P1] `main.py:75-122` — Générer le menu interactif depuis `WorkflowRegistry.list_all()` (ordre et catégorie portés par un attribut de classe), pour intégrer d'office `h3_ref2va`, `monoplan_ia`, `outfit` et `character3d`, et supprimer le texte « (1-37) ».
- [ ] [P1] `core/cinema.py:221`, `workflows/musique_adn.py:17`, `workflows/outfit.py:194`, `main.py:462-503, 862-920` — Déplacer `upscale_video_ai`, `generer_depuis_reference.{convertir_en_wav, detecter_tonalite}`, `character_pipeline.etape_3_rendre_validation` et les gestionnaires `update_*` dans `core/` (ou `maintenance/`). `core/` et `workflows/` ne doivent plus importer `scripts/`.
- [ ] [P1] `core/render_medieval_themes.py`, `core/render_morphology_tests.py` — Sortir ces expériences de `core/` (vers `scripts/proto_*` ou suppression) ; elles embarquent des chemins `C:\GIT\...` et `C:\Users\laurent\...`.
- [ ] [P1] `workflows/__init__.py` — Remplacer les 43 imports explicites et le `__all__` incomplet (sans `AnimalGodotWorkflow`) par une découverte automatique (`pkgutil.iter_modules`) ou un registre paresseux (nom → `module:Classe`). Cela réduit aussi le démarrage (~2,9 s mesurées pour `import workflows`, dominées par `scipy.signal` via `core/audio_ops.py`).
- [ ] [P1] `core/clothes_catalog.py:22` + 40 scripts de `scripts/` — Supprimer les `sys.path.insert` : déclarer les paquets dans `pyproject.toml` (`[tool.uv] package = true` ou `packages = ["core", "workflows"]`) et lancer les scripts avec `uv run python -m scripts.xxx`.
- [ ] [P2] `scripts/` — Trier les ≈120 scripts en trois zones : `scripts/maintenance/` (veille, installation, qwentts, téléchargements), `scripts/proto/` (tests non validés) et `archive/`, ou suppression (one-shots `debug_*`, `*_marc_*`, `*_vent_gris*` déjà encapsulés en workflows). Factoriser le boilerplate Blender dupliqué (156 blocs R0801 selon `python_health_report.md`) dans un `core/blender_runtime.py`.

### 2.3 Configuration et portabilité
- [ ] [P1] `core/mpfb_ops.py:307`, `core/render_morphology_tests.py:24,41`, `core/render_medieval_themes.py:17-24`, `workflows/character_makeup.py:85`, `core/voix_robot.py:29-37`, `core/cinema.py:320-321`, `core/blender_ops.py:21-27` — Centraliser tous les chemins dans `core/config.py` via des variables d'environnement. Dériver `MODELE_KOKORO` de `DEFAULT_MODEL_DIR`, résoudre le dossier MPFB avec `%APPDATA%` ou `~/.config/blender`, et trouver Blender avec `shutil.which` puis des globs par OS.
- [ ] [P1] `core/config.py` — Charger un fichier `.env` local optionnel (celui produit par `scripts/install_unix.sh`) et publier un `.env.example` qui liste les ~40 variables `*_PATH` et `*_DIR` supportées.
- [ ] [P1] `scripts/check_charge_systeme.py` — Ajouter un backend Linux/macOS (`/proc/stat`, `/proc/meminfo`, `vulkaninfo` ou `amdgpu_top`, `radeontop`), et à défaut renvoyer un code documenté « mesure indisponible ». Aujourd'hui l'exit 2 casse les consommateurs en `check=True`.
- [ ] [P1] `core/config.py:479` (`verifier_prerequis`) — Étendre `--check` à audio.cpp, trellis-cli, FFmpeg, Blender et aux modèles vidéo et musique ; aujourd'hui seule la pile Flux est vérifiée. Ajouter `--check <workflow>` pour ne contrôler que les prérequis d'un workflow donné.

### 2.4 Gestion des erreurs et sous-processus
- [ ] [P1] `core/` (nouveau `core/process.py`) — Créer un helper unique `run_engine(cmd, timeout, log_path, check=True)` qui journalise la commande, capture stdout et stderr dans un fichier de log, lève une exception typée (`EngineError` avec le code et la fin du stderr) et applique un `timeout` systématique. Aujourd'hui `core/diffusion.py:165,274,408` et `core/upscaler.py:61` n'ont aucun timeout.
- [ ] [P1] `core/blender_ops.py:186,308`, `core/mpfb_ops.py:297,502,1067,1298`, `core/animal_godot.py:85` — Afficher ou journaliser le stderr Blender en cas d'échec. La variable `res` est actuellement capturée puis ignorée, et `CalledProcessError` ne montre pas le stderr.
- [ ] [P1] `core/blender_ops.py:116-300`, `core/mpfb_ops.py:103,348,874,1134` — Ne plus interpoler des chemins ou des noms (`nom_base` vient de `-o`, non assaini) dans du source Python généré par f-string. Passer les paramètres en JSON via `sys.argv` après `--`, ce qui évite l'injection et la casse des guillemets dans les chemins.
- [ ] [P1] `core/image_ops.py:111`, `core/segmentation.py:93`, `core/pbr_deep.py:134`, `core/llm.py:103` — Restreindre les `except Exception` de repli silencieux (IA → floodfill, LLM → prompt brut) aux exceptions attendues, et remonter le repli dans le résultat du workflow (`"fallback": "floodfill"`).
- [ ] [P2] `core/cinema.py:499,527,535`, `core/image_ops.py:352`, `core/pose_ops.py:155,205` — Corriger les alertes ruff B023 (closure sur variable de boucle), B905 (`zip` sans `strict`) et B007.

### 2.5 Tests et qualité
- [ ] [P1] `pyproject.toml` — Ajouter un `[dependency-groups] dev = ["pytest", "ruff", "pytest-cov"]` et une section `[tool.ruff]` (select `E,F,B,UP,S603` ; exclude `.agents`).
- [ ] [P1] `tests/unit/` (nouveau) — Tester unitairement les fonctions pures déjà isolées : `core/music_ai.py` (`fabriquer_boucle_*`, `estimer_bpm`, `verifier_boucle`, `construire_recette_ducking`), `core/loop_ops.py`, `core/autotile_builder.py`, `core/shader_maps.py`, `core/config.slugifier_texte` et les résolveurs, ainsi que `core/clothes_catalog.aiguiller_modele_vetement` (complexité 34).
- [ ] [P1] `tests/integration/` (nouveau) — Remplacer sd-cli, audiocpp_cli, trellis-cli et Blender par de faux exécutables (scripts Python qui écrivent un PNG, WAV ou GLB factice), désignés par les variables `*_PATH`. Exécuter chaque workflow de bout en bout sans GPU pour valider le câblage des paramètres et des sorties.
- [ ] [P1] `.github/workflows/ci.yml` (nouveau) — Faire tourner `uv sync --frozen`, `ruff check` et `pytest` sur `windows-latest` et `ubuntu-latest`, sans GPU, grâce aux faux exécutables.
- [ ] [P2] Tout le dépôt — Lancer `ruff check --fix` (218 corrections automatiques, dont 176 imports inutilisés), puis traiter manuellement E402, E741 et F841.
- [ ] [P2] `core/`, `workflows/` — Compléter les annotations de type (`Optional` explicite pour `config: Dict = None` dans `workflows/base.py:20`) et vérifier avec `mypy --strict` sur `core/config.py`, `workflows/base.py` et le nouveau `core/process.py`.

### 2.6 Dépendances et sécurité de la chaîne d'approvisionnement
- [ ] [P1] `scripts/engines_manifest.json`, `scripts/install_windows.ps1:79-159`, `scripts/install_unix.sh:285-290` — Ajouter un champ `sha256` par asset épinglé et le vérifier avant l'extraction. Le calculer dans `scripts/veille_versions.py` lors de la validation d'une version (le digest des assets de release est exposé par l'API GitHub).
- [ ] [P1] `pyproject.toml` — Déclarer `huggingface_hub` (importé par `scripts/download_wan22_i2v_models.py`), en groupe optionnel `tools`, ou migrer ce script vers `scripts/telecharger_gros_fichier_parallele.py`. Aligner `requires-python` avec `AGENTS.md`.
- [ ] [P2] `scripts/download_gemma4_gguf.py:14-34` — Ne plus passer le jeton HF en argument de `curl` (visible dans la liste des processus) : utiliser `requests` avec un en-tête, ou `huggingface_hub`, qui lit le jeton tout seul.
- [ ] [P2] `scripts/install_unix.sh:121` — Remplacer `curl … | sh` pour uv par un téléchargement vérifié, ou documenter l'alternative `pipx install uv`.
- [ ] [P2] `scripts/veille_versions.py` — Authentifier les appels à l'API GitHub (`GITHUB_TOKEN` optionnel), pour passer de 60 à 5 000 requêtes par heure, et signaler explicitement les réponses 403 de dépassement de quota au lieu de conclure « pas de nouveauté ».

### 2.7 Hygiène du dépôt
- [ ] [P1] `core/config.py:135` — Faire pointer `DEFAULT_OUTPUT_DIR` vers `output/` (ignoré par git) et garder `godot_assets/` pour les assets de référence validés. Aujourd'hui chaque génération atterrit dans un dossier versionné.
- [ ] [P1] `godot_assets/`, `docs/exemples/` — Passer les binaires (PNG, GLB, blend, MP4, OGG) sous Git LFS, ou les sortir du dépôt, pour stopper la croissance de `.git` (277 Mo).
- [ ] [P2] `scratch/`, `test_output_clothes/`, `idee/HSEGjdLakAA4S5t.jpg` — `git rm --cached` les fichiers suivis malgré `.gitignore`.
- [ ] [P2] Racine — Déplacer `paroles_*.txt` vers `data/paroles/`, `flux1-dev-Q6_K.gguf.md` vers `docs/modeles/` et `python_health_report.md` vers `docs/audits/`.
- [ ] [P2] `.agents/skills/generator-assets-workspace/` — Purger le workspace d'évaluation (27 fichiers), comme `AGENTS.md` l'autorise.

### 2.8 Observabilité
- [ ] [P1] `workflows/base.py:23-24` — Faire passer `BaseWorkflow.log` par `logging` : handler console avec emojis inchangé, plus un handler fichier `output/logs/<date>_<workflow>.log`. Ajouter `--verbose/--quiet` et `--log-json` pour les consommateurs.
- [ ] [P1] `main.py:1089-1099` — Journaliser la trace complète (`logger.exception`) au lieu du seul `str(e)`, et distinguer les codes retour : 1 = erreur workflow, 2 = prérequis manquant, 3 = machine occupée, 4 = entrée invalide.
- [ ] [P2] `workflows/base.py` — Mesurer la durée de chaque étape (context manager `self.step("diffusion")`) et l'ajouter au résultat. Les métriques RTF et temps sont aujourd'hui relevées à la main dans `MEMORY_BANK.md`.

### 2.9 Documentation
- [ ] [P1] `README.md` (2 029 lignes, 161 Ko) — Scinder en un README court (pitch, installation, 10 commandes clés) et un dossier `docs/workflows/<nom>.md` par workflow, **générés** depuis les métadonnées du registre (voir 2.2), pour supprimer la dérive du nombre de workflows (43, 40 ou 36).
- [ ] [P1] `.agents/skills/generator-assets/SKILL.md:8,24`, `references/catalogue_workflows.md`, `README.md:84,1628` — Corriger les compteurs de workflows et ajouter un test (`tests/test_docs_sync.py`) qui vérifie que chaque nom du registre apparaît dans `SKILL.md` et dans `catalogue_workflows.md`.
- [ ] [P2] `AGENTS.md:81` vs `pyproject.toml:6` — Aligner la version de Python ; mettre à jour la `description` de `pyproject.toml` (fabrique média image, vidéo, audio, 3D) et le lien « PRs Welcome » (`github.com/votre-compte/...`) de `README.md`.
- [ ] [P2] `scripts/hook_session_start.py:36-44` — Supprimer les constantes mortes de surveillance de l'issue #1946 (bloc retiré le 2026-09-13 selon `AGENTS.md`).

---

## 3. Checklist de Nouvelles Fonctionnalités

### 3.1 Contrat machine pour les consommateurs : `--json` + résultat structuré
- [ ] Ajouter l'option globale `--json` (`main.py`) : le dernier message sur stdout est un objet JSON `{status, workflow, outputs:[…], seed, duration_s, fallbacks:[…], warnings:[…]}`, et les logs humains passent sur stderr.
- [ ] Normaliser le `dict` renvoyé par chaque `BaseWorkflow.run()` avec un `WorkflowResult` (dataclass) : `outputs` en liste de chemins absolus, `seed` effectivement utilisée, `status`.
- [ ] Documenter les codes retour stables (0, 1, 2, 3, 4) dans `README.md` et `SKILL.md`.
- [ ] Ajouter `--list-workflows --json`, qui expose le schéma des paramètres de chaque workflow (nom, type, défaut, obligatoire).
- [ ] Tests de contrat dans `tests/test_cli_contract.py`, et une note de migration pour `ai-doc2video/generator_assets_bridge.py` et `video-analys-ia/generer_assets_ia.py`.

**Approche technique** — Les deux consommateurs appellent déjà le CLI en sous-processus avec `check=True`. Aujourd'hui ils doivent deviner les chemins de sortie à partir de `-o` et analyser les logs à emojis. Il suffit d'ajouter un `WorkflowResult` dans `workflows/base.py`, que `main.py` sérialise quand `--json` est actif. Les workflows existants gardent leur `dict` : un adaptateur `WorkflowResult.from_legacy(dict)` récupère les clés `*_path`, `wav`, `mp3` et `files`, ce qui permet une migration progressive. Déplacer les `print` vers stderr passe par le chantier `logging` (2.8). Alternative écartée : un serveur HTTP ou MCP local. Il ajouterait une surface d'exposition réseau et un processus résident, contraires à la philosophie « CLI ultra-légère », alors que le contrat sous-processus suffit aux deux dépôts.

### 3.2 Verrou GPU et file d'attente locale des générations lourdes
- [ ] Créer `core/gpu_lock.py` : un verrou inter-processus (fichier `output/.gpu.lock` via `msvcrt.locking` sous Windows et `fcntl.flock` sous Unix) qui enregistre PID, workflow et heure de début.
- [ ] Déclarer `heavy = True` sur les workflows GPU (`video`, `monoplan_ia`, `h3_ref2va`, `music_bg`, `chanson`, `mesh_ia`, `generate`…). `BaseWorkflow` prend alors le verrou et lance `check_charge_systeme` automatiquement, comme le fait déjà `workflows/h3_ref2va.py:38-93`, au lieu de s'en remettre à la discipline des consommateurs.
- [ ] Options `--wait[=MAX_S]` (attendre le verrou et un créneau libre, avec un nouveau contrôle de charge toutes les N secondes) et `--no-gate` (forçage explicite, journalisé).
- [ ] Ajouter la commande `main.py --queue add|list|run` : une file persistante `output/queue.jsonl` consommée séquentiellement. Elle remplace à terme `scripts/run_overnight_batch.py`, `run_overnight_all_sota.py` et `run_benchmarks_chained.py`.
- [ ] Tests : deux processus concurrents → le second attend ou sort en code 3 ; un verrou orphelin (PID mort) est récupéré.

**Approche technique** — `AGENTS.md` impose « jamais lancer sur une machine chargée ». Pourtant, seul `h3_ref2va` applique la règle dans le code, alors que trois sources (deux dépôts consommateurs et les scripts de nuit) partagent une seule RX 6950 XT de 16 Go, avec des marges VRAM d'environ 120 Mo sur LTX. Un verrou fichier reste sans dépendance, fonctionne sous Windows comme sous Unix et survit aux plantages grâce à la vérification du PID. La file JSONL est traitée par le même `main.py` : une tâche = un appel `WorkflowRegistry.get(...).run(params)`, qui réutilise la sérialisation de paramètres de 3.1. Alternatives écartées : Celery/Redis ou un démon, trop lourds pour un poste unique ; une simple boucle d'attente dans les consommateurs, qui ne protège pas des lancements manuels ni des scripts de nuit.

### 3.3 Manifeste de provenance et de reproductibilité par asset
- [ ] Écrire, à côté de chaque livrable, un fichier `<asset>.provenance.json` : workflow, paramètres effectifs (après défauts), prompt final (après LLM), seed, modèles utilisés (chemin, taille, SHA-256 mis en cache), versions des moteurs (`sd-cli --version`, `version.json` de trellis, tag audio.cpp, commit qwentts), durée par étape et replis déclenchés.
- [ ] Ajouter `main.py --replay <fichier.provenance.json>`, qui relance exactement la même génération (A/B après une mise à jour de moteur) et compare le hash ou une métrique de similarité.
- [ ] Ajouter `main.py --provenance-report <dossier>`, qui agrège les manifestes d'un rendu YouTube en un encart « contenu généré par IA » (modèles, licences) prêt à coller dans la description.
- [ ] Mettre en cache les empreintes des gros GGUF dans `output/.model_hashes.json` (clé : chemin, taille et mtime) pour ne pas re-hacher 16 Go à chaque appel.
- [ ] Tests : la génération avec de faux moteurs produit un manifeste valide contre un schéma JSON ; `--replay` reconstruit les mêmes `params`.

**Approche technique** — Le dépôt suit déjà la reproductibilité à la main : seeds imposées, matrices de non-régression sd-cli dans `MEMORY_BANK.md`, épinglages dans `scripts/engines_manifest.json`, `empreinte_fichier` dans `core/music_ai.py:675`. Le manifeste industrialise cette pratique. Il s'écrit dans `BaseWorkflow` après `run()`, à partir du `WorkflowResult` (3.1) et des durées d'étapes (2.8). Les versions des moteurs sont lues via les fonctions de détection déjà présentes dans `scripts/veille_versions.py`, à déplacer dans `core/engines.py`. Cela sert la chaîne YouTube (transparence IA, traçabilité des licences de modèles) comme le jeu Godot (régénérer un asset identique après une mise à jour). Alternatives écartées : les métadonnées embarquées (PNG tEXt, tags ID3), non homogènes entre PNG, GLB, OGG et MP4 et perdues au transcodage ; une base SQLite, excessive tant que le besoin reste « un fichier par asset ».
