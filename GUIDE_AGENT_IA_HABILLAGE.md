# 🤖 Guide Agent IA : Pipeline d'Habillage de Personnages 3D MakeHuman / MPFB

Ce document est destiné aux **Agents IA de codage** et développeurs externes. Il décrit le fonctionnement de la fonctionnalité d'habillage 3D automatique, sa finalité, son architecture ainsi que l'ensemble des commandes associées pour l'exécuter et l'étendre.

---

## 🎯 À quoi sert la Feature ?

Cette fonctionnalité permet de **générer par IA des tenues 3D complètes (Haut, Bas, Chaussures)** avec textures PBR haute résolution (2K/4K) et d'**habiller automatiquement des personnages MakeHuman / MPFB dans Blender** avec les garanties suivantes :

1. **Adaptation Morphologique Dynamique Universelle** : Les vêtements s'adaptent instantanément à toutes les morphologies (**Homme adulte**, **Femme adulte**, **Enfant**, corpulence, musculature) sans déformation ni pénétration de maillage.
2. **Objets 3D 100% Indépendants** : Les 3 pièces de vêtements sont créées sous forme d'objets Blender distincts (`Torso`, `Pants`, `Shoes`), avec leurs propres modificateurs (Solidify, Subsurf) et matériaux PBR Principled BSDF, séparés du maillage `Human`.
3. **Préservation Anatomique Totale (8398 sommets)** : Le masque sous les vêtements préserve l'intégralité du visage, de la tête, du cou, des oreilles, des lèvres, des poignets, des paumes et de l'ensemble des 10 doigts.
4. **Intégration Bibliothèque MPFB 1-Clic** : Enregistrement automatique dans le catalogue de pack `packs/generator_assets.json` pour un affichage direct avec vignettes dans le panneau Blender **MPFB > Apply assets > Clothes library**.

---

## 🛠️ Répertoire des Commandes CLI

### 1. Génération d'une Tenue Complète (Workflow Principal)
Génère les textures PBR (Diffuse + Normal Map) via Flux.1 / SDXL, effectue l'upscaling 4x (4x-UltraSharp Vulkan) et compile les fichiers d'habillage :
```bash
uv run python main.py -w makehuman_clothes --theme "<nom_du_theme>" --prompt "<description_textuelle_des_tissus_et_matériaux>"
```
*Exemple pour une tenue de paysan médiéval :*
```bash
uv run python main.py -w makehuman_clothes --theme "peasant" --prompt "rustic beige burlap tunic and brown hemp trousers"
```

---

### 2. Validation Multi-Morphologies (Homme, Femme, Enfant)
Exécute l'habillage en mode headless dans Blender sur 3 gabarits distincts et produit les rendus studio 3/4 :
```bash
# Tester le thème Paysan :
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --python run_peasant_morph_test.py

# Tester le thème Armure de Cuir :
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --python run_leather_armor_morph_test.py

# Tester le thème Armure d'Acier :
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --python run_steel_knight_morph_test.py
```

---

### 3. Rendu Studio 4 Angles (Face, 3/4, Dos, Profil)
Génère une scène studio complète avec éclairage 3 points et produit les 4 vues orthogonales/perspectives :
```bash
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --python core/render_medieval_themes.py
```

---

### 4. Enregistrement & Synchronisation dans la Bibliothèque MPFB
Inscrit automatiquement un nouveau vêtement dans le catalogue Blender MPFB :
```bash
uv run python -c "from core.mpfb_ops import enregistrer_asset_dans_pack_mpfb; enregistrer_asset_dans_pack_mpfb('<nom_asset>', '<torso|pants|shoes>', author='AI-Generator')"
```

---

## 📂 Organisation des Fichiers & Données de Sortie

| Type d'Asset | Emplacement | Description |
| :--- | :--- | :--- |
| **Textures PBR Générées** | `godot_assets/medieval_<theme>_<part>_diffuse.png`<br>`godot_assets/medieval_<theme>_<part>_normal.png` | Textures 2048×2048 upscalées avec 4x-UltraSharp. |
| **Rendus Morphologies** | `godot_assets/renders_morphologies/medieval_<theme>_<morphologie>.png` | Rendus studio HD pour Homme, Femme et Enfant. |
| **Rendus Multi-Angles** | `godot_assets/renders_medieval_<theme>/medieval_<theme>_<angle>.png` | Vues studio 4 angles (`front`, `three_quarter`, `back`, `profile`). |
| **Scène 3D Blender** | `godot_assets/renders_medieval_<theme>/medieval_<theme>_personnage_habille.blend` | Fichier `.blend` complet avec objets 3D indépendants et matériaux PBR. |
| **Bibliothèque MPFB** | `%APPDATA%\Blender Foundation\Blender\5.2\mpfb\data\packs\generator_assets.json` | Catalogue de pack JSON pour affichage dans l'interface Blender. |
