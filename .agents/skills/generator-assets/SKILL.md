---
name: generator-assets
description: Génère tout média avec la fabrique locale generator-assets (moteurs C++ Vulkan/GGUF, zéro PyTorch, zéro cloud) — images 2D, sprites, textures PBR, meshes 3D .glb, objets IA image→3D (TRELLIS.2), skyboxes 360°, personnages MakeHuman, boucles musicales, voix off TTS, voix robot, SFX, ambiances, vidéo IA (Wan/LTX/MiniMax-H3) et upscaling 4K, via `uv run python main.py -w <workflow>`. Utiliser ce skill dès que l'utilisateur veut créer, générer ou produire n'importe quel asset média (image, texture, matériau, modèle 3D, personnage, musique, son, voix, vidéo) dans ce dépôt ou depuis un dépôt consommateur (ai-doc2video, video-analys-ia), ou demande ce que la fabrique sait faire — même s'il ne nomme aucun workflow. Fournit la table de routage besoin→workflow, les garde-fous obligatoires (contrôle de charge système avant génération lourde, prompts en anglais, seed fixée) et les recettes validées.
---

# generator-assets — générer des médias avec la fabrique locale

Ce dépôt est une **fabrique locale universelle de médias IA** : 40 workflows orchestrés par un CLI unique,
exécutés par des moteurs C++/GGUF Vulkan (sd-cli, llama.cpp, audio.cpp, trellis.cpp, FFmpeg) — aucune
dépendance cloud ni CUDA. Ta mission quand ce skill se déclenche : traduire un besoin média en **la bonne
commande de workflow**, en respectant les garde-fous, puis livrer les fichiers produits.

## 1. Comment lancer un workflow

Toujours depuis la racine du dépôt (`C:\GIT\generator-assets`) :

```bash
uv run python main.py -w <workflow> "<prompt ou args>" [options]
```

- `-o <nom>` : nom de base des sorties (sinon dérivé du prompt) ;
- `--seed <N>` : graine fixe pour la reproductibilité A/B ;
- `uv run python main.py --check` : vérifie que les moteurs et modèles sont détectés ;
- `uv run python main.py --interactive` : console interactive (menu 40 workflows) pour exploration humaine ;
- les sorties atterrissent dans `output/<workflow>/<nom>/` (ou `godot_assets/` pour les anciens workflows 2D).

Le détail complet de chaque workflow (entrées, sorties, options, exemples) est dans
[`references/catalogue_workflows.md`](references/catalogue_workflows.md) — à consulter dès que le routage
ci-dessous ne suffit pas (options précises, durées, formats produits).

## 2. Garde-fous AVANT de lancer une génération

Ces règles viennent de `AGENTS.md` et d'incidents réels — elles ne sont pas décoratives :

1. **Contrôle de charge système avant toute génération lourde** (tout ce qui passe par sd-cli vidéo,
   audio.cpp ou trellis.cpp : `video`, `monoplan_ia`, `h3_ref2va`, `music_bg`, `chanson`, `sfx` IA,
   `musique_*`, `voix_*`, `mesh_ia`…) :
   ```bash
   uv run python scripts/check_charge_systeme.py
   ```
   Exit 1 = machine occupée → **on attend un créneau libre, on ne lance pas** (incident documenté :
   RTF mesuré 3,3× trop lent à cause d'une contention GPU).
2. **Une seule génération lourde à la fois** — GPU AMD RX 6950 XT 16 Go, les moteurs se battent pour la VRAM.
3. **Prompts des modèles toujours en anglais** (les descriptions d'images, musique, vidéo, voix — même si
   l'utilisateur parle français, la commande porte un prompt anglais).
4. **Toujours fixer `--seed`** pour pouvoir reproduire/comparer.
5. Ne jamais lancer de génération en plein batch en cours, et ne jamais tuer un `audiocpp_cli.exe` /
   `ffmpeg.exe` / `sd-cli.exe` qui tourne.

Contrat des dépôts consommateurs (ai-doc2video, video-analys-ia) : ils appellent ce CLI en subprocess
`check=True` depuis ce répertoire, avec charge vérifiée + prompt anglais + seed fixée. Toute évolution du
CLI doit préserver ce contrat.

## 3. Routage besoin → workflow

### 🎨 Image 2D, sprites, UI (moteur Flux.1 Dev / SDXL Vulkan)

| Besoin | Workflow | Exemple |
| :--- | :--- | :--- |
| Asset 2D isolé (item, monstre, décor, fond) | `generate` | `-w generate "healing potion, dark fantasy game icon" -t prop -o potion` |
| Planche de sprites multi-angles d'un personnage | `spritesheet` | `-w spritesheet "goblin scout" -o gobelin` |
| Variantes thématiques (feu/glace/poison…) | `variations` | `-w variations "elemental sword" --themes fire,ice` |
| Texture raccordable (tuile TileMap) | `tileable` | `-w tileable "mossy cobblestone floor"` |
| Pixel art rétro (Pico-8, Endesga-32…) | `pixelart` | `-w pixelart -i image.png --palette pico8` |
| Cadres/boutons 9-patch | `ui_9slice` | `-w ui_9slice "stone dialog frame"` |
| Atlas autotile 47 tuiles Wang | `autotile_pack` | `-w autotile_pack "cave walls"` |
| Détourage propre (fond transparent) | `rembg` | `-w rembg -i image.png` |
| Upscale 2x/4x/4K ESRGAN | `upscale` | `-w upscale -i image.png --scale 4` |
| Pack JSON de générations en série | `batch` | `-w batch --recipe recette.json` |

### 🧱 Textures PBR & 3D (Flux + DeepBump + Blender + TRELLIS.2)

| Besoin | Workflow | Exemple |
| :--- | :--- | :--- |
| Pack matériau PBR complet + `.tres` Godot | `material3d` | `-w material3d "ancient gothic stone tile with purple runes" -s 1024` |
| Mesh 3D paramétrique `.glb` (dalle, coffre, pilier…) | `mesh3d` | `-w mesh3d "ornate iron chest" --shape cube` |
| **Objet 3D IA volume réel** depuis prompt ou image | `mesh_ia` | `-w mesh_ia "obsidian dragon skull" --res 512` ou `-i casque.png` |
| Skybox 360° équirectangulaire + IBL | `skybox` | `-w skybox "purple cosmic nebula"` |
| Modèle 3D voxel pour GridMap | `voxel3d` | `-w voxel3d -i sprite.png --grid-size 32` |
| **Animal riggé packé animé pour Godot** (Quaternius, packs mocap) | `animal_godot` | `-w animal_godot -i loup.blend -o loup_godot.glb` — skill dédié `blender-rig` si rigging/animation IA |
| Fiche orthogonale pour modéliser dans Blender | `turnaround3d` | `-w turnaround3d "dwarven warrior"` |
| Flowmap eau/lave + shader Godot | `flowmap` | `-w flowmap "lava river" --angle 45` |
| Prop CC0 standard ou plaque décor (YouTube) | `asset_blendkit` | `-w asset_blendkit --query "wooden barrel" --list-assets` |

**`mesh_ia` (TRELLIS.2) — recette** : itérer à `--res 512` (~11 min), master à `--res 1024` (~55 min) ;
`--faces-cible 30000` pour un prop Godot (10 000 = prop standard, 2-3 000 = clutter répété). Depuis un
prompt, `mesh_ia` chaîne automatiquement `generate` (image → détourage → 3D). Chaque sortie inclut une
**planche de contrôle** (4 vues EEVEE) — la regarder avant de livrer, jamais de GLB non vu.

**Prérequis 3D** : ces workflows passent par **Blender headless** — obligatoire pour `mesh3d`, `voxel3d`,
`asset_blendkit` et toute la suite MakeHuman (qui exige en plus l'addon MPFB2) ; optionnel pour `mesh_ia`
(décimation/planche sautées si Blender absent). Résolution de l'exécutable : `BLENDER_PATH` → PATH →
`C:\Program Files\Blender Foundation\Blender 4.0…5.2` ; `--check` le détecte. Standards game-ready Godot
(budgets tris, nommage `SM_`/`MAT_`/`T_`, ratios LOD, texel density, collision `-colonly`, checklist de
validation, écueils MPFB/BlendKit) : [`references/pipeline_3d_blender.md`](references/pipeline_3d_blender.md).

### 👤 Personnages humanoïdes (MakeHuman / MPFB2)

| Besoin | Workflow |
| :--- | :--- |
| Portrait 2D → corps 3D complet (.blend/.glb, makeup, rig Mixamo, rendus Cycles) | `character3d` / `character_makeup` |
| Vêtements modulairesquad MakeHuman depuis un thème | `makehuman_clothes` |
| Recoloration/retexturation de la garde-robe d'un personnage existant | `outfit` |
| Sprite guidé par pose OpenPose + scène Godot riggée | `pose_control` |
| Galerie de portraits multi-émotions pour dialogues RPG | `rpg_portrait` |

→ Le guide détaillé (règles absolues UV/`.mhclo`, catalogue bilingue 177 modèles) est dans
[`GUIDE_AGENT_IA_HABILLAGE.md`](../../../GUIDE_AGENT_IA_HABILLAGE.md) — le lire pour tout travail MakeHuman.

### 🔊 Audio, musique, voix (audio.cpp / qwentts.cpp / FFmpeg)

| Besoin | Workflow | Exemple |
| :--- | :--- | :--- |
| Boucle musicale de fond (bed −30 LUFS, jeu ou voix off YouTube) | `music_bg` | `-w music_bg "dark ambient drone, 70 BPM" --bpm 70` |
| Chanson complète AVEC paroles | `chanson` | `-w chanson --paroles "..." --style "synthpop"` |
| Nouvelle musique avec l'ADN d'une référence (BPM/tonalité imposés) | `musique_adn` | `-w musique_adn --reference morceau.wav` |
| Musique à l'essence d'une référence (SA3 init_audio) | `musique_essence` | `-w musique_essence --reference morceau.wav` |
| Retrait du chant / séparation de stems | `retrait_voix` | `-w retrait_voix -i morceau.wav` |
| Voix off expressive FR (clonage qwen3-tts/VoxCPM2/Fish) | `voix_off` | `-w voix_off --texte "..." --voix narrator_fr` |
| Voix de robot EN (recette validée kokoro + ringmod) | `voix_robot` | `-w voix_robot --texte "..."` |
| Super-résolution audio → 48 kHz (voix 16k / musique 24k) | `audio_upscale` | `-w audio_upscale -i voix_16k.wav --upsr-variante speech` |
| Voix de personnage émotionnelle + lip-sync Godot | `tts_dialogue` | `-w tts_dialogue --texte "..." --emotion angry` |
| Bruitage SFX (procédural ou IA) | `sfx` | `-w sfx "sword swing whoosh"` |
| Ambiance sonore bouclable sans couture | `audio_ambience` | `-w audio_ambience "forest night, wind"` |

**Recettes audio validées** : `music_bg` → `[Instrumental]` (pas de voix) pour des lits instrumentaux ;
la sortie production est un bed −30 LUFS avec ducking possible ; `voix_robot` = recette fixe validée
(kokoro `af_heart`, pitch +30 %, ringmod 120 Hz, atempo 0,65, gain −4 dB) — ne pas improviser d'autres
réglages sans accord utilisateur ; `audio_upscale` = UniverSR CPU validé voix (« parfait même ») et
musique (« très bien ») — **lent (RTF ~13) et sortie MONO**, refuser les entrées > 24 kHz (déjà pleine
bande).

### 🎬 Vidéo IA (Wan 2.1/2.2, LTX-2.5, MiniMax-H3 — sd-cli Vulkan)

| Besoin | Workflow | Exemple |
| :--- | :--- | :--- |
| Plan cinématique depuis une image fixe (slow-mo, zoom conçu) | `monoplan_ia` | `-w monoplan_ia -i frame.png --prompt "camera slowly pans..."` |
| Vidéo depuis prompt ou image (Wan/LTX, .webm) | `video` | `-w video "cyberpunk street, neon rain"` |
| **Continuer une vidéo existante, image + SON** (MiniMax-H3 Ref2VA) | `h3_ref2va` | `-w h3_ref2va -i clip.webm --prompt "..." --turbo` |
| Interpolation 60 fps (RIFE) | `rife_interp` | `-w rife_interp -i clip.webm` |
| Planche de particules VFX 4×4 | `vfx_flipbook` | `-w vfx_flipbook "fire explosion"` |
| Boucle de texture/shader animée | `anim_loop` | `-w anim_loop -i texture.png` |
| Cohérence de style entre assets (IP-Adapter) | `ip_adapter` | `-w ip_adapter -i reference.png` |

**`h3_ref2va` : TOUJOURS `--turbo`** (LoRA distillé 8 steps, validé utilisateur : ~38 min au lieu de ~70 min
pour 22 frames, qualité ≥ baseline). Le mode 20 steps ne sert qu'en A/B qualité sur demande explicite.
Les masters YouTube 4K passent par `scripts/conform_youtube_hd.py`.

**⚠️ Écueil vidéo courant (état 23/09/2026 — vérifier `docs/MEMORY_BANK.md` §1.16-1.19 avant tout rendu
vidéo, cela évolue avec les maj sd-cli)** : la sd-cli installée (`C:\SD\`, master-899) **casse MiniMax-H3**
(régression mémoire amont : 51 segments au lieu de 2, OOM au submit ~5 min — inchangée de master-864 à 899,
issue #1976 ouverte) ; **LTX-2.5 passe le benchmark T2V 33 trames sur 899 uniquement avec une VRAM bureau
basse (machine rebootée, marge ~120 Mo fragile)** et son I2V 65 trames n'y est pas retesté. La build
parallèle de production reste `C:\SD-6b3edaa\` (master-841, dernière validée pour LTX/H3) :
```bash
# monoplan_ia : préfixer SD_CLI_PATH (résolu via core/config.py) :
SD_CLI_PATH="C:\SD-6b3edaa\sd-cli.exe" uv run python main.py -w monoplan_ia ... 
```
Pour `h3_ref2va`, la production passe également par la build 6b3edaa (le workflow peut appeler
`C:\SD\sd-cli.exe` en dur → utiliser `--sd-cli` ou la commande brute documentée en MEMORY_BANK §1.16).
Vidéo fiable sur master-899 : **Wan T2V/I2V ≤ ~20 trames avec `--vae-on-cpu`** (workflow `video`,
validé 23/09). Règle : **toute matrice/validation sd-cli tourne sur machine fraîchement rebootée**
(un verdict LTX/H3 peut dépendre de la VRAM détenue par le bureau).

## 4. Durées et attentes (RX 6950 XT, ordre de grandeur)

| Génération | Durée typique |
| :--- | :--- |
| Image Flux 1024² | ~1-2 min |
| `music_bg` boucle 30 s | ~1-3 min |
| `mesh_ia` res 512 / res 1024 | ~11 min / ~55 min |
| `monoplan_ia` plan 5 s | ~10-30 min |
| `h3_ref2va` 22 frames turbo | ~38 min |

Préviens l'utilisateur de la durée avant de lancer ; propose une itération basse résolution quand elle existe.

## 5. Après la génération

- Livrer les chemins de fichiers produits (pas juste « c'est fait ») + la graine utilisée ;
- **Rendu subjectif (musique, voix, esthétique) : soumettre systématiquement à l'écoute/validation de
  l'utilisateur** avant toute industrialisation ;
- Règle du dépôt : un test validé par l'utilisateur devient un workflow ; un test non validé se consigne
  dans `docs/MEMORY_BANK.md` — on ne crée jamais de workflow pour une recette non validée ;
- Écueil opérationnel rencontré → le consigner dans `docs/MEMORY_BANK.md` (section du domaine concerné).

## 6. Pour aller plus loin

| Question | Où chercher |
| :--- | :--- |
| Détail complet d'un workflow (entrées/sorties/options/exemples) | [`references/catalogue_workflows.md`](references/catalogue_workflows.md) |
| Standards 3D game-ready (budgets, nommage, LOD, checklist), prérequis Blender/MPFB/BlendKit, écueils | [`references/pipeline_3d_blender.md`](references/pipeline_3d_blender.md) |
| Doc de référence, showcases, procédures d'installation | [`README.md`](../../../README.md) § 📦 Complete Workflow Catalog |
| Habillage/texturation MakeHuman | [`GUIDE_AGENT_IA_HABILLAGE.md`](../../../GUIDE_AGENT_IA_HABILLAGE.md) |
| Stacks validées & écueils par domaine | [`docs/MEMORY_BANK.md`](../../../docs/MEMORY_BANK.md) |
| Conventions dépôt, veille, process de mise à jour moteurs | [`AGENTS.md`](../../../AGENTS.md) |
| Moteurs locaux (versions, commandes validées) | `C:\SD\README.md`, `C:\audio-cpp\README.md`, `C:\ffmpeg\README.md`, `C:\trellis\README.md` |
