# 🤖 Guide Agent IA : Pipeline d'Habillage & Texturation 3D MakeHuman / MPFB

Ce document est destiné aux **Agents IA de codage** et développeurs. Il décrit l'architecture et les bonnes pratiques pour l'habillage 3D et la texturation des personnages MakeHuman / MPFB dans Blender et Godot 4.

---

## 🎯 Architecture & Principes Fondamentaux

### 1. Structure d'un Vêtement MakeHuman
Un vêtement MakeHuman est un système 3D complet composé de :
- **Maillage 3D (`.obj`)** : Géométrie 3D avec un dépliage UV spécifique (patron de couture 2D : face, dos, manches, poches).
- **Lien Barycentrique (`.mhclo`)** : Lie chaque sommet du vêtement aux sommets du corps humain pour s'adapter à toutes les morphologies sans collision.
- **Descripteur de Matériau (`.mhmat`)** : Configuration des shaders et textures.
- **Cartes de Textures UV (`_diffuse.png`, `_normal.png`)** : Patrons de couture 2D peints avec détails localisés (coutures, boutons, poches, boucles).

---

## 🛠️ Méthode Canonique de Personnalisation : Transformation de Patrons UV

Pour créer de nouvelles tenues (ex: tenue médiévale, armure de cuir, bure de moine) :

### ⚠️ Règle Absolue : Ne Jamais Projeter d'Illustration 2D Plate
- Ne pas coller une image 2D vue de face sur un vêtement 3D (risque de fausses mains, ceintures étirées sur le dos et les fesses).
- Ne jamais écraser les fichiers MakeHuman originaux dans `%APPDATA%\...\mpfb\data\data\clothes`.

### ✅ Le Workflow Validé (`scripts/retexture_uv_garment.py`) :
1. **Partir du vrai patron UV MakeHuman** (`male_worksuit01_diffuse.png`, `shoes01_diffuse.png`, etc.).
2. **Conserver 100% de la disposition UV** : Les poches, boutons, bretelles et découpes restent exactement à leurs coordonnées.
3. **Transformer la matière** : Conversion du tissu (ex: denim bleu -> toile de jute beige/chanvre médiéval, boucles métalliques -> fer forgé/bronze).
4. **Générer la Normal Map PBR** : Création du micro-relief des mailles et coutures.
5. **Sauvegarder dans le projet** : Isolation des assets dans `godot_assets/textures/<nom_personnage>/`.
6. **Assigner dans Blender** : Création d'un matériau PBR indépendant et export GLB automatique pour Godot 4.

```bash
uv run python scripts/retexture_uv_garment.py
```

---

## 🗄️ Base de Données & Aiguillage IA Bilingue (FR / EN) (`core/clothes_catalog.py`)

Le module [`core/clothes_catalog.py`](file:///C:/GIT/generator-assets/core/clothes_catalog.py) scanne tous les dossiers de vêtements MakeHuman et construit une base de données JSON enrichie de mots-clés sémantiques **en français et en anglais** :
- **Fichier Catalogue** : [`data/clothes_catalog.json`](file:///C:/GIT/generator-assets/data/clothes_catalog.json) (**177 modèles 3D indexés** avec tags, genres, catégories, barbes, robes de moine, capes, armures, bottes, chemises, chapeaux, chemins `.mhclo`, `.obj`, et patrons `.png`).
- **Aiguilleur IA Sémantique Bilingue** : La fonction `aiguiller_modele_vetement(prompt, category, gender)` associe automatiquement n'importe quel concept en **anglais ou français** (ex: *"rustic medieval peasant overalls"*, *"monk robe"*, *"viking beard"*, *"heavy leather boots"*, *"veste chic femme"*) au meilleur modèle 3D existant.

Pour reconstruire ou rafraîchir l'index du catalogue :
```bash
uv run python core/clothes_catalog.py
```

---

## 🚀 Commandes CLI Disponibles

### 1. Workflow Outfit 100% Automatisé (`main.py -w outfit`)
Génère et applique des matières sans raccord (Albedo + Normal + Roughness) sur les vêtements d'un personnage :
```bash
uv run python main.py -w outfit --character marc_novice --top "rustic medieval beige burlap tunic" --shoes "dark worn medieval leather boots"
```

### 2. Compilation MakeClothes Universelle (`makeclothes_from_mesh.py`)
Compile n'importe quel maillage 3D externe (issu d'une IA 3D ou modélisé en Quads) en asset MakeHuman officiel :
```bash
uv run python scripts/makeclothes_from_mesh.py --mesh "assets/models/cape.obj" --name "cape_voyageur" --category "clothes"
```

### 3. Pipeline Complet Personnage Canonique (`character_pipeline.py`)
Génère la peau propre avec cicatrices/cernes organiques, construit la morphologie MakeHuman, exporte le `.blend` et `.glb` :
```bash
uv run python scripts/character_pipeline.py --portrait "assets/portraits/marc_portrait.png" --recipe-script "poc_3d/create_marc_mpfb2.py" --name marc_novice
```

---

## 📂 Organisation des Fichiers

| Asset | Emplacement | Description |
| :--- | :--- | :--- |
| **Scène Blender Éditables** | `godot_assets/<nom_perso>.blend` | Scène complète avec entité MakeHuman dynamique et shaders PBR. |
| **Export Godot 4** | `godot_assets/<nom_perso>.glb` | Modèle de jeu optimisé prêt pour l'intégration Godot 4. |
| **Textures Personnalisées** | `godot_assets/textures/<nom_perso>/` | Diffuse UV, Normal Maps et textures de tissus isolées. |
| **Rendu Studio de Validation** | `godot_assets/<nom_perso>_beauty_render.png` | Rendu Cycles sous éclairage 3 points calibré. |
