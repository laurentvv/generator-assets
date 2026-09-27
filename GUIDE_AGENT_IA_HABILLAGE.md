# 🤖 AI Agent Guide: MakeHuman / MPFB 3D Outfitting & Texturing Pipeline

This document is intended for **AI coding agents** and developers. It describes the architecture and best practices for 3D outfitting and texturing of MakeHuman / MPFB characters in Blender and Godot 4.

---

## 🎯 Architecture & Core Principles

### 1. Structure of a MakeHuman Garment
A MakeHuman garment is a complete 3D system made of:
- **3D Mesh (`.obj`)**: 3D geometry with a specific UV unwrap (2D sewing pattern: front, back, sleeves, pockets).
- **Barycentric Link (`.mhclo`)**: Ties each garment vertex to the vertices of the human body so it fits every body shape without collision.
- **Material Descriptor (`.mhmat`)**: Shader and texture configuration.
- **UV Texture Maps (`_diffuse.png`, `_normal.png`)**: 2D sewing patterns painted with localized details (seams, buttons, pockets, buckles).

---

## 🛠️ Canonical Customization Method: UV Pattern Transformation

To create new outfits (e.g. medieval outfit, leather armor, monk's habit):

### ⚠️ Absolute Rule: Never Project a Flat 2D Illustration
- Do not paste a front-view 2D image onto a 3D garment (risk of phantom hands, belts stretched across the back and buttocks).
- Never overwrite the original MakeHuman files in `%APPDATA%\...\mpfb\data\data\clothes`.

### ✅ The Validated Workflow (`scripts/retexture_uv_garment.py`):
1. **Start from the real MakeHuman UV pattern** (`male_worksuit01_diffuse.png`, `shoes01_diffuse.png`, etc.).
2. **Keep 100% of the UV layout**: Pockets, buttons, straps and cutouts stay exactly at their coordinates.
3. **Transform the material**: Fabric conversion (e.g. blue denim -> beige burlap/medieval hemp, metal buckles -> wrought iron/bronze).
4. **Generate the PBR Normal Map**: Creation of the micro-relief of the weave and seams.
5. **Save into the project**: Assets isolated in `godot_assets/textures/<nom_personnage>/`.
6. **Assign in Blender**: Creation of an independent PBR material and automatic GLB export for Godot 4.

```bash
uv run python scripts/retexture_uv_garment.py
```

---

## 🗄️ Database & Bilingual AI Routing (FR / EN) (`core/clothes_catalog.py`)

The [`core/clothes_catalog.py`](file:///C:/GIT/generator-assets/core/clothes_catalog.py) module scans all MakeHuman clothing folders and builds a JSON database enriched with semantic keywords **in both French and English**:
- **Catalog File**: [`data/clothes_catalog.json`](file:///C:/GIT/generator-assets/data/clothes_catalog.json) (**177 indexed 3D models** with tags, genders, categories, beards, monk robes, capes, armors, boots, shirts, hats, `.mhclo` and `.obj` paths, and `.png` patterns).
- **Bilingual Semantic AI Router**: The `aiguiller_modele_vetement(prompt, category, gender)` function automatically matches any concept in **English or French** (e.g. *"rustic medieval peasant overalls"*, *"monk robe"*, *"viking beard"*, *"heavy leather boots"*, *"veste chic femme"*) to the best existing 3D model.

To rebuild or refresh the catalog index:
```bash
uv run python core/clothes_catalog.py
```

---

## 🚀 Available CLI Commands

### 1. 100% Automated Outfit Workflow (`main.py -w outfit`)
Generates and applies seamless materials (Albedo + Normal + Roughness) on a character's garments:
```bash
uv run python main.py -w outfit --character marc_novice --top "rustic medieval beige burlap tunic" --shoes "dark worn medieval leather boots"
```

### 2. Universal MakeClothes Compilation (`makeclothes_from_mesh.py`)
Compiles any external 3D mesh (from a 3D AI or modeled in Quads) into an official MakeHuman asset:
```bash
uv run python scripts/makeclothes_from_mesh.py --mesh "assets/models/cape.obj" --name "cape_voyageur" --category "clothes"
```

### 3. Complete Canonical Character Pipeline (`character_pipeline.py`)
Generates clean skin with organic scars/dark circles, builds the MakeHuman morphology, exports the `.blend` and `.glb`:
```bash
uv run python scripts/character_pipeline.py --portrait "assets/portraits/marc_portrait.png" --recipe-script "poc_3d/create_marc_mpfb2.py" --name marc_novice
```

---

## 📂 File Organization

| Asset | Location | Description |
| :--- | :--- | :--- |
| **Editable Blender Scenes** | `godot_assets/<nom_perso>.blend` | Full scene with dynamic MakeHuman entity and PBR shaders. |
| **Godot 4 Export** | `godot_assets/<nom_perso>.glb` | Optimized game model ready for Godot 4 integration. |
| **Custom Textures** | `godot_assets/textures/<nom_perso>/` | Diffuse UV, Normal Maps and isolated fabric textures. |
| **Validation Studio Render** | `godot_assets/<nom_perso>_beauty_render.png` | Cycles render under calibrated 3-point lighting. |
