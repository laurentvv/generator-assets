# AGENTS.md — generator-assets (fabrique média IA locale)

> Instructions pour tout agent IA de codage travaillant dans ce dépôt.
> Structure : **bloc commun** (délimité, resynchronisable) + **spécifique projet** (libre).

<!-- BEGIN:agents-commun v1.0 — bloc partagé entre dépôts (agents-kit). Ne pas éditer à la main : resynchroniser via scripts/sync_agents.py -->
<!-- Le script remplace uniquement ce qui se trouve entre les marqueurs BEGIN/END ; tout le contenu spécifique du dépôt est préservé -->

## §1 Environnement

- Machine : **Windows 11**. Shell du dépôt : **Git Bash** *(adapter au §7 si PowerShell 7 — n'utiliser QUE les commandes du shell déclaré)*.
- Python : **`uv` uniquement** — jamais `pip install`, jamais `requirements.txt` (`uv add` / `uv run`).
- Chemins machine : jamais en dur dans le code — passer par la configuration du projet (config.py / .env / section dédiée).
- Contexte long (architecture, leçons détaillées, écosystème) : voir `PROJECT_MEMORY.md` ou `docs/` du dépôt — AGENTS.md reste volontairement court.

## §2 État sur disque = source de vérité

Ne jamais se fier à la seule fenêtre de contexte : elle s'altère, se compresse, s'efface. L'état du travail vit dans **quatre fichiers** (défaut : racine du dépôt ; variantes admises si déclarées au §7 : `.agents/`, `memory-bank/`). À chaque initialisation, plantage ou redémarrage : les lire pour reconstruire son état de façon déterministe.

| Fichier | Rôle | Cycle de vie |
|---|---|---|
| `feature_list.json` | Fonctionnalités **actives** (pending / in_progress) uniquement. | Mis à jour à chaque changement de statut ; les `completed` partent en `feature_list_archive.json` (garder court — lu chaque session). |
| `contract.md` | Contrat de validation : assertions strictes et testables (15-30 critères). | **Figé** avant la première ligne de code ; plus modifiable par le générateur. |
| `progress.md` | Tableau de bord du sprint en cours (objectif + jalons). | Mis à jour à la fin de chaque itération. |
| `log.md` | Journal chronologique **append-only**. | Une entrée au début et à la fin de chaque action. |

**Formats** :

`feature_list.json` — `"status"` ∈ `pending | in_progress | completed` (+ extensions projet autorisées, ex. `awaiting_playtest` — les déclarer au §7) :

```json
{ "features": [ { "id": "F-01", "name": "…", "description": "périmètre technique",
  "status": "pending | in_progress | completed", "dependencies": [] } ] }
```

`log.md` — **budget ~200 caractères par entrée** (le détail va dans le commit) :

```markdown
## [AAAA-MM-JJ] init | Initialisation du workspace et négociation du contrat.md
## [AAAA-MM-JJ] gen  | Écriture du script principal et génération des structures JSON.
## [AAAA-MM-JJ] eval | Échec de la validation du contrat sur le critère 2.
```

`type` ∈ `init | gen | eval | fix | sync | done | err` (+ extensions projet).

**Rotation du log** (budget contexte) : `log.md` ne contient que le mois courant. Au changement de mois (ou au-delà de ~150 Ko), déplacer l'historique vers `docs/journal/log_AAAA-MM[_JJ-JJ].md` — rien n'est effacé, l'archive reste grepable. **Au bootstrap : ne lire que `log.md` (court) ; les archives uniquement par `grep` ciblé.** *Variante B (à déclarer au §7) : historisation événementielle en base (DuckDB/SQLite) à la place du fichier plat — même discipline, zéro journal .md.*

## §3 Boucle d'exécution

1. **Bootstrap** — vérifier les 4 fichiers ; absents → les créer ; présents → les lire (budget : actives de `feature_list.json`, `progress.md`, `contract.md`, `log.md` en entier). Ne PAS lire les archives sauf `grep` ciblé.
2. **Action** — avant d'exécuter une tâche, écrire la ligne dans `log.md`.
3. **Gate** — une vérification statique en échec **interdit** la synchronisation du ledger (compiler/linter au vert d'abord — ne jamais annoncer « check OK » sans l'avoir lancé).
4. **Synchronisation** — après chaque écriture ou test, mettre à jour le fichier de statut associé.
5. **Erreurs** — en cas d'exception ou d'interruption, l'état valide = dernière entrée du `log.md` + assertions de `progress.md`.

## §4 Git & livraison

- **Jamais de travail ni de push direct sur `main`** : branche `feat/…` ou `fix/…` avant toute modification.
- Une fois la PR soumise : **s'arrêter** (pas de boucle d'attente) ; merge uniquement sur instruction explicite.
- **Jamais `git reset --hard` sur un working tree vivant** — annulation d'un commit de test : `git reset --soft HEAD~1` puis purge ciblée.
- Push uniquement sur demande explicite de l'utilisateur.
- **Checklist avant commit** : tests/linters au vert · aucun secret dans le diff · doc maintenue à jour · ledger synchronisé.

## §5 Sécurité & intégrité

- **Aucun secret** dans le code, les commits, les logs ni l'écran (chemins utilisateur, e-mails, jetons) → env vars / figurants fictifs.
- **Jamais supprimer** les fichiers d'état, bases, archives ou données métier. Toute suppression ambiguë : **reformuler la liste** à l'utilisateur et faire confirmer AVANT d'exécuter.
- **Jamais éteindre/redémarrer/mettre en veille la machine** sans demande formelle explicite.
- **Actions irréversibles ou externes** (publication, upload, écriture PROD, envoi de messages) : générer d'abord les artefacts de contrôle, puis attendre l'accord explicite dans le chat.

## §6 Vérité & validation

- « Vérifié » = **exécuté réellement** (exit 0) ou **inspecté visuellement** (capture/rendu regardés) — jamais déduit du code, des intentions ou des logs.
- Toute affirmation factuelle (chiffre, couleur, présence d'un asset) est étayée par une mesure ou une capture conservée en preuve.
- Après une correction : re-valider par le **chemin complet réel**, pas par un harnais qui le court-circuite.
- Documentation : toute évolution de comportement → mettre à jour la doc maintenue du dépôt avant de clore la tâche.

<!-- END:agents-commun -->

---

## §7 Spécifique projet

### Mission / périmètre

**Fabrique locale universelle de médias générés par IA** — tout projet nécessitant image, son, vidéo ou musique. Productions principales : le jeu Godot *L'Héritier du Vide* (PBR, maillages IA `mesh_ia`/TRELLIS.2, boucles OGG `music_bg`) et la chaîne YouTube d'`ai-doc2video` (TTS, lits musicaux −30 LUFS, vidéos Wan/LTX/MiniMax-H3, masters 4K). Tout nouveau besoin média est un cas d'usage légitime ; les composants restent génériques et réutilisables, toute évolution sert un projet concret (ou l'outillage de maintenance : veille, docs, téléchargement).

### Emplacements déclarés (écarts au commun)

- **Ledger non instancié** : mémoire opérationnelle = `docs/MEMORY_BANK.md` (stacks validées + écueils, une section par domaine) + `docs/veille_journal.md` — écart déclaré.
- Shell : Git Bash · `uv run python main.py -w <workflow>`.

### Écosystème — consommateurs (contrat implicite à préserver)

| Consommateur | Comment il appelle | Usage |
|---|---|---|
| `C:\GIT\ai-doc2video` | `generator_assets_bridge.py` (subprocess CLI) | `monoplan_ia` (hooks), `sfx`, **maintenance qwentts** (`scripts/manage_qwentts.py` — ce dépôt GÈRE `C:\IA\qwentts.cpp` depuis le 2026-09-12 : maj git, backups `C:\IA\qwentts_backups` ×5, build Vulkan, smoke test, rollback auto ; jamais modifier le clone à la main) |
| `C:\GIT\video-analys-ia` | `generer_assets_ia.py` (pattern du bridge) | stickers de substitution, I2V d'une frame, monoplans |

Contrat : `scripts/check_charge_systeme.py` exécuté **avant toute génération vidéo** (exit 1 = on ne lance pas) · prompts **en anglais** · `--seed` fixé (A/B reproductible) · subprocess `check=True` depuis ce répertoire.

### Commandes clés

```bash
uv run python main.py -w <workflow>                        # exécution d'un workflow
uv run python scripts/check_charge_systeme.py             # CPU/GPU/RAM/VRAM AVANT génération lourde
uv run python scripts/veille_versions.py                  # veille (état output/veille/, rapport seul)
uv run python scripts/manage_qwentts.py --check           # santé du moteur TTS
uv run python scripts/telecharger_gros_fichier_parallele.py <url> <dest>   # gros téléchargements HF (~10×)
```

### Invariants métier (à ne jamais casser)

- **Philosophie : moteurs C++ Vulkan + GGUF, zéro PyTorch** (sd-cli, llama.cpp, audio.cpp, trellis.cpp). GPU AMD RX 6950 XT 16 Go (RDNA2, **pas de CUDA**) — tout nouveau moteur doit tourner Vulkan/CPU.
- **Avant tout lancement lourd** (audio.cpp, sd-cli, trellis.cpp) : `check_charge_systeme.py` (RTF mesuré 3,3× trop lent sur GPU en contention, 2026-09-08). Jamais sur une machine chargée.
- **README personnalisés des outils hors dépôt à maintenir systématiquement** (toute nouvelle connaissance y est consignée immédiatement) : `C:\audio-cpp\README.md` · `C:\ffmpeg\README.md` · `C:\SD\README.md` · `C:\trellis\README.md` (ne pas confondre avec les README de clones tiers, ex. `C:\llama.cpp`).
- **Skill** `.agents/skills/generator-assets/` : à maintenir en sync avec le catalogue réel (nouveau workflow/option/recette → `SKILL.md` + `references/catalogue_workflows.md` ; pipeline 3D → `references/pipeline_3d_blender.md` ; écueil majeur → bloc écueils, retiré quand résolu).
- **Code** : docstrings/logs en français, identifiants en anglais, prompts EN. Diagnostic via `logging` (`core.journal.configurer_journal()`) ; `print()` réservé aux sorties utilisateur.
- **Modèles `C:\Modeles_LLM`** : vérifier la retéléchargeabilité AVANT toute suppression (lister TOUTE l'org : `curl -s "https://huggingface.co/api/models?author=audio-cpp"`) ; accord ambigu → **reformuler la liste** avant d'exécuter (incident 2026-09-08 : 4 modèles supprimés au lieu de 0).
- **Tout test VALIDÉ par l'utilisateur devient un workflow** (`main.py -w`, code `core/`+`workflows/`, README, MEMORY_BANK, skill) ; réciproquement : jamais de workflow pour un test non validé (statut « testé, non validé » dans MEMORY_BANK).
- **`h3_ref2va` : toujours `--turbo`** (VALIDÉ 2026-09-09, ~38 min vs ~70 min pour 22 frames) ; base 20 steps seulement en A/B ou demande explicite.

### Veille & mises à jour

- **Veille automatique à l'ouverture de session** (hook SessionStart ZCode, relance si > 20 h) : audio.cpp, sd-cli, trellis.cpp + GGUF HF, FFmpeg, Python, paquets, LLM/VLM GGUF tendance, llama.cpp, sa3.cpp, outils système versionnés, écosystème ComfyUI. Rapport seul — **jamais de mise à jour automatique**.
- **Instruction permanente (2026-09-07)** : dès que la veille signale un NOUVEAU modèle musique/audio compatible, **lancer le test sans attendre** (recette gothic rock 30 s, 83 BPM C# minor, graine 42) puis soumettre à l'écoute ; verdict dans MEMORY_BANK.
- **`output/veille/maj_en_attente.json`** : une maj appliquée/obsolète → retirer IMMÉDIATEMENT son entrée + consigner dans `docs/veille_journal.md` (avant→après, commit, vérification). Sinon le hook la resignale à chaque session.
- **Process de maj** : une seule à la fois · aucun binaire en cours (`audiocpp_cli.exe`/`ffmpeg.exe`) · smoke test après · maj des README d'outils + skill + `scripts/engines_manifest.json` (épinglage installateurs) · commit/push docs. Procédures détaillées et rollbacks par composant : tableau dans l'historique git de ce fichier (ex. `C:\audio-cpp\update.ps1`, `C:\SD\backups\`, `manage_qwentts.py --rollback`).

### Pièges & leçons (format daté)

- **[2026-09-08] suppression de modèles** — consigne ambiguë mal interprétée : reformulation obligatoire avant exécution.
- **[2026-09-08] contention GPU** — RTF 3,3× dégradé sur machine chargée : gate charge système avant toute génération.

### Renvois

- `README.md` (catalogue des workflows) · `docs/MEMORY_BANK.md` · `docs/veille_journal.md` (à lire au démarrage) · skill `.agents/skills/generator-assets/`.
