# Pipeline 3D : Blender headless → GLB → Godot

Prérequis, standards game-ready et écueils pour tout asset 3D produit par la fabrique
(`mesh3d`, `mesh_ia`, `voxel3d`, `asset_blendkit`, suite MakeHuman `character3d`/`makehuman_clothes`/`outfit`).
Standards adaptés du pack blender-skills (arjun988, MIT) — seule la partie moteur-agnostique a été
reprise : ici tout est **headless CLI** (`blender --background --python`), pas d'addon MCP.
Les budgets sont des ordres de grandeur « AAA-informed », à ajuster par projet.

## 1. Prérequis (bloquants selon le workflow)

| Composant | Requis par | Détail |
| :--- | :--- | :--- |
| **Blender 4.0→5.2** | `mesh3d`, `voxel3d`, `asset_blendkit` (bloquant) ; `mesh_ia` (optionnel : décimation + planche de contrôle sautées silencieusement si absent) ; suite MakeHuman (bloquant) | Résolution `core/blender_ops.py::trouver_blender()` : env `BLENDER_PATH` → `blender` dans le PATH → `C:\Program Files\Blender Foundation\Blender 4.0…5.2\blender.exe`. `uv run python main.py --check` le détecte |
| **Addon MPFB2** | `character3d`, `character_makeup`, `makehuman_clothes`, `outfit` | Extension `bl_ext.user_default.mpfb` installée dans Blender ; data dir `%APPDATA%\Blender Foundation\Blender\5.2\mpfb\data\data` (surcharge env `MPFB_DATA_DIR`, cf. `core/config.py`) |
| **Addon BlenderKit connecté** | `asset_blendkit` | Login fait **une fois en GUI** (la clé API n'est lisible que dans le processus Blender, jamais hors process) ; le code force la licence CC0 |

Blender est toujours invoqué en subprocess headless avec scripts bpy générés (`--background --python`) ;
le succès se détecte par marqueurs stdout (`SUCCESS:`, `RENDERS_RESULT_JSON:`) — toujours vérifier les
fichiers de sortie annoncés, pas seulement le code retour.

## 2. Standards game-ready (cible Godot 4)

### Unités, axes, échelle
- **1 unité Blender = 1 mètre** ; exporter en **GLB, +Y up** (déjà le cas : `export_yup=True` côté MPFB,
  GLB partout ailleurs).
- Vérifier l'échelle à l'import Godot avec un repère connu (porte ≈ 2 m de haut, sol à y = 0).

### Nommage (préfixes moteur)
| Type | Préfixe | Exemple |
| :--- | :--- | :--- |
| Mesh | `SM_` | `SM_Weapon_Rifle_A`, `SM_Prop_Crate_Wood_01` |
| Matériau | `MAT_` | `MAT_Metal_Painted_Red` |
| Texture | `T_` | `T_Console_BC`, `T_Console_N`, `T_Console_ORM` |
| Animation | `AN_` | `AN_Door_Open` |
| Armature | `ARM_` | `ARM_Robot_Loader` |

Règles : PascalCase + underscores, `_01` (pas `_1`), descriptif (pas `SM_Thing`), **≤ 64 caractères**.
Suffixes textures : `_BC` albedo, `_N` normal, `_ORM` packé (R=AO, G=Roughness, B=Metallic), `_E` émission.
NB : les sorties `material3d` du dépôt utilisent leurs propres suffixes (`_albedo/_normal/_orm…`) —
renommer vers la convention ci-dessus au moment d'intégrer dans le jeu.

**Collision Godot** : à l'import GLB, Godot 4 génère automatiquement les formes de collision pour les
nœuds suffixés `-col`, `-colonly` (trimesh), `-convcol`, `-convcolonly` (convexe) — pas la convention
`COL_`/`UCX_` (Unreal). Pour un prop décoratif simple, préférer un `-convcolonly` sur un proxy basse
définition plutôt que la trimesh complète.

### Budgets triangles
| Catégorie | Tier | Tris |
| :--- | :--- | :--- |
| Props | Héros (tenu, gros plan) | 15 000–50 000 |
| Props | Standard (scène, moyenne distance) | 5 000–15 000 |
| Props | Arrière-plan / clutter | 500–5 000 |
| Props | Petit (pièces, débris) | 100–500 |
| Personnages | Héros | 50 000–100 000 |
| Personnages | NPC | 20 000–40 000 |
| Personnages | Foule | 5 000–10 000 |
| Environnement | Mur modulaire 2 m / dalle sol | 200–800 / 100–400 |
| Environnement | Bâtiment héros / rocher héros | 5 000–20 000 / 1 000–5 000 |
| Environnement | Arbre réaliste / stylisé | 5 000–15 000 / 200–2 000 |

Mapping direct sur `mesh_ia --faces-cible` : **30000 = prop héros, 10000 = prop standard,
2 000–3 000 = clutter répété, ≥ 8000 si silhouette très courbée**. Style lowpoly : −50 à −90 %.

Si au-dessus du budget : supprimer les faces internes/non visibles, passer le détail en normal map,
créer une chaîne LOD avant validation finale.

### LOD
| LOD | % tris | Distance |
| :--- | :--- | :--- |
| LOD0 | 100 % | 0–10 m |
| LOD1 | 50 % | 10–25 m |
| LOD2 | 25 % | 25–50 m |
| LOD3 | 10 % | 50 m+ |

Dans ce dépôt, la décimation passe par `mesh_ia --faces-cible` (Decimate **COLLAPSE**, delimiters
`SHARP`/`UV` — préserve les UV). En Blender manuel : `planar` convient au hard-surface, `collapse`
à l'organique. Nommage `SM_Asset_LOD0…LOD3`.

### Textures & matériaux
| Tier | Résolution | Texel density |
| :--- | :--- | :--- |
| Héros | 2048–4096 | 512–1024 px/m |
| Standard | 1024–2048 | 256–512 px/m |
| Arrière-plan | 512–1024 | 128–256 px/m |

Texel density = résolution ÷ taille physique (m) — ex. 1024 px sur 2 m = 512 px/m ; rester cohérent
entre assets d'une même scène. Matériaux par asset : héros 3–5, standard 1–2, kit modulaire 1 (atlas).
Le pipeline du dépôt produit du **Principled BSDF** → converti nativement en PBR glTF/Godot ;
le packing ORM attendu est R=AO, G=Roughness, B=Metallic.

## 3. Checklist de validation avant livraison (headless)

1. **Regarder l'asset** — jamais livrer un GLB non vu : planche de contrôle `mesh_ia` (4 vues orbitales
   EEVEE 900²), rendus Cycles `character3d`, aperçu `asset_blendkit`. Rendu subjectif → soumettre à
   l'utilisateur (règle du dépôt).
2. **Auditer** : nb de triangles vs budget (`--faces-cible` réellement appliqué ?), nb de matériaux,
   échelle, pas de normales inversées visibles sur la planche.
3. **Test d'import Godot** : échelle correcte (repère connu), matériaux importés (StandardMaterial3D),
   collision si requise (`-colonly`), silhouette lisible à distance de gameplay, animations en clips
   nommés si applicable.

Rapport type : statut PASS/FAIL, polycount (vs budget), nb matériaux, dimensions, problème(s) trouvé(s)
+ correctif appliqué, vues vérifiées.

## 4. Écueils consolidés (Blender / MPFB / BlendKit)

- **Ordre rig Mixamo AVANT les `.mhclo`** : sinon les vêtements ne sont pas skinnés (`creer_corps_personnage_mpfb`
  garantit l'ordre — le respecter dans tout script dérivé).
- **Area lights** : ajouter des contraintes `TRACK_TO` vers la cible (elles pointent en −Z par défaut).
- **Rendus de tête MPFB** : désactiver les modificateurs MASK « delete » avant le rendu.
- **UV visage MakeHuman (hm08)** : l'îlot visage vit dans X ∈ [1450..2000] — ne pas le déplacer lors des
  calques d'encre MakeUp.
- **BlendKit headless** : le daemon local de l'addon est inutilisable en `--background` → passer par
  `scripts/blendkit_blender_job.py` ; lire la clé API dans les préférences **avant** `read_factory_settings`
  (qui les réinitialise) ; chemins **absolus** dans le job JSON ; EEVEE sature certaines scènes →
  basculer le rendu en Cycles HIP.
- **Blender absent** : `mesh_ia` rend `None` silencieusement pour la décimation/planche (non bloquant) —
  vérifier que les sorties attendues existent avant d'annoncer la livraison.

## 5. Brief mini avant tout asset 3D jeu (pattern « director »)

Quatre questions avant de lancer — elles déterminent workflow et budget :
1. **Type** : prop / personnage / environnement / voxel ?
2. **Tier** : héros (gros plan), standard (scène), arrière-plan (clutter) ? → budget tris + textures §2.
3. **Cible** : jeu Godot (GLB + standards §2) ou rendu YouTube (qualité brute, budgets souples) ?
4. **Animé/riggé** ? → rig nécessaire (`character3d`), clips `AN_*`, prévoir marge de topo sur les zones
   de déformation.

Chaîne typique prop héros : `generate` (concept) → `mesh_ia --res 512` itération (~11 min) →
`mesh_ia --res 1024` master (~55 min) → `--faces-cible 30000` → checklist §3. Après validation
utilisateur, la recette devient workflow (règle du dépôt).
