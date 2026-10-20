# 👤 Canonical 3D Character Pipeline (MakeHuman & MPFB2)

> Complete autonomous pipeline from AI 2D portrait to rigged Blender/Godot 3D characters: YuNet anatomical extraction, SSS compensation, hm08 UV vector painting, Mixamo rigging, and modular quad wardrobe.
> Back to main: [README.md](../README.md) • Workflows reference: [workflows_reference.md](workflows_reference.md)

---

#### 2.1. `character3d` / `character_makeup` — 100% Automatic Pipeline: AI Portrait → Blender 3D Body (.blend, .glb, MakeUp, Shaders, Cycles Renders)

This workflow turns a 2D portrait into a complete 3D character for Godot 4 and Blender **automatically, with zero manual retouching**. It enforces the project's fundamental rule: **never paste the 2D portrait onto the mesh** — instead, AI vision extracts the anatomical features and signature of the avatar, paints them onto a layered vector ink layer, then assembles a native MPFB2 body, dressed, rigged and rendered.

##### 🖼️ Visual Output Produced by the Workflow (Use Case: Elian)

| 1. Source 2D Portrait | 2. hm08 UV MakeUp (2048²) | 3. Head Front (Cycles 85mm) | 4. Full Body (Cycles 55mm) |
| :---: | :---: | :---: | :---: |
| <img src="../docs/exemples/character_3d/elian_portrait.png" width="220" /> | <img src="../docs/exemples/character_3d/elian_makeup_ink.png" width="220" /> | <img src="../docs/exemples/character_3d/elian_tete_face.png" width="220" /> | <img src="../docs/exemples/character_3d/elian_perso_face.png" width="220" /> |
| *AI reference portrait (YuNet)* | *Multi-layer SSS vector ink layer* | *Studio render, no jaw bug* | *Full body + Robe + Mixamo rig* |

| 5. Head 3/4 Check (Cycles 85mm) | 6. Full Body 3/4 Check (Cycles 55mm) |
| :---: | :---: |
| <img src="../docs/exemples/character_3d/elian_tete_tiers.png" width="280" /> | <img src="../docs/exemples/character_3d/elian_perso_tiers.png" width="280" /> |
| *Orbit, nose-bridge and temple detail* | *Draped 3D silhouette & peasant shoes* |

##### 🔬 Detailed Pipeline Steps (High Precision)

1. **Anatomical & Colorimetric Vision Extraction (YuNet ONNX)**:
   * Detects key facial landmarks (pupils, eye corners, nose bridge and tip, lip corners, bounding box).
   * Computes the inter-pupillary distance (IPD) to calibrate adaptive sampling.
   * Measures under-eye fatigue contrast ($\Delta L^* = 70.6$), the dark-circle/cheek BGR ratio, temple hollowness and lip tint.
2. **Transfer to the 3D Skin Gamut & SSS Compensation**:
   * Cycles' *Subsurface Scattering* spreads the red component ~5× farther than green/blue. To avoid a flayed or flushed render, shadows are cooled and darkened (factor 0.82) with a subtle violaceous/anthracite core.
3. **Multi-Layer Vector Painting on the hm08 UV Map (2048×2048 RGBA)**:
   * Painting on the right facial island ($X \in [1450..2000], Y \in [800..1300]$, axial symmetry at $Y = 1058$):
     - *Layer 1 (Diffuse penumbra)*: orbits, hollow temples, nose bridge, cheek flush (Gaussian blur $\sigma = 14$).
     - *Layer 2 (Orbital crescent)*: intermediate sub-palpebral delineation ($\sigma = 8$).
     - *Layer 3 (Fatigue core)*: tear valley and deep orbital center ($\sigma = 5$).
     - *Layer 4 (Upper hollow)*: shadow under the palpebral arch ($\sigma = 5$).
     - *Layer 5 (Lips)*: soft natural tint ($\sigma = 6$).
   * Automatic generation of the official MPFB2 manifest (`.json`) and ink layer (`.png`) into the project and `%APPDATA%/.../mpfb/data/data/ink_layers/`.
4. **Shader & Eye Texture Customization**:
   * Iris adjustment (e.g. luminescent cyan/turquoise, sharp limbus, 0.06 emission) into `%APPDATA%/.../mpfb/data/data/eyes/materials/`.
5. **Automatic 3D Body Assembly in Blender (Headless `bpy`)**:
   * Instanciates the MPFB2 basemesh with canonical macro-parameters (`--age` and `--gender` exposed on the CLI; `height`, `weight`, `muscle` settable via batch JSON recipe).
   * Applies the `MAKESKIN` skin and immediately grafts the MakeUp ink layer.
   * **Prior grafting of the standard Mixamo armature (`HumanService.add_builtin_rig(human, "mixamo")`)**: mandatory step *before* clothing so MPFB detects the skeleton and automatically generates the `Armature` modifiers and weighted vertex groups on every garment piece.
   * Attaches the official quad assets (`HumanService.add_mhclo_asset`): eyes `low-poly.mhclo`, eyebrows `eyebrow001.mhclo`, tongue, teeth, dark short hair `short01.mhclo`, monk robe and peasant shoes (they automatically inherit the 52 Mixamo bones without tearing).
   * PBR shaders: procedural skin micro-relief (noise scale 180 + bump normal 0.15), charcoal-black eyebrows/hair `(0.015, 0.015, 0.018)`, wet eyes roughness 0.03.
   * Simultaneous export of the native **`.blend`** scene (100% parametric, editable human) and the game-optimized **`.glb`** (100% compatible with Godot's 49 Mixamo animations).
6. **Cycles Studio Check Renders (4 Automated Views)**:
   * Calibrated 3-point lighting (Key, Fill, Rim) with **`TRACK_TO`** constraints automatically aimed at the target.
   * 85mm head framing with **preventive disabling of garment MASK modifiers** (removes the truncated jaw/chin bug).
   * 55mm full-body framing with **exact trigonometric camera setback** from the vertical sensor in 896×1536 portrait ratio ($dist = (H \times 1.28) / (2 \tan \theta)$).
   * Cycles denoising enabled (`use_denoising = True`).

* **Inputs**: `--portrait` (or `-i, --input`), `--character` (name), `--age` (default 0.12), `--gender` (default 0.0), `--eye-color` (`cyan`), `--samples` (default 48).
* **Engines**: OpenCV YuNet ONNX, NumPy / PIL multi-layer raster, MakeHuman / MPFB2, Blender 5.2 Cycles headless.
* **Outputs**: `<character>_mpfb2.blend`, `<character>_mpfb2.glb`, `makeup/<character>_fatigue_ventgris.{png,json}`, `<character>_cyan_eye.png`, 4 `.png` renders (`tete_face`, `tete_tiers`, `perso_face`, `perso_tiers`).
* **Commandes CLI** :
  ```bash
  # 🚀 100% automatic generation: from 2D portrait to complete 3D body + 4 studio renders:
  uv run python main.py -w character3d --portrait "assets/portraits/elian_portrait.png" --character elian

  # Variant: fast generation with 16 Cycles samples:
  uv run python main.py -w character3d --portrait "assets/portraits/elian_portrait.png" --character elian --samples 16

  # Variant: generate the MakeUp ink layer only, without rebuilding the body:
  uv run python main.py -w character_makeup --portrait "assets/portraits/elian_portrait.png" --character elian --makeup-only
  ```

#### 2.3. `makehuman_clothes` — Modular Quad Wardrobe Generator
* **Process**:
  1. Takes a thematic clothing concept (e.g. *"medieval leather rogue armor"*).
  2. Generates pure seamless raw material PBR textures (leather, linen, iron rings) with 4K ESRGAN Vulkan upscaling.
  3. Leverages official MakeHuman helper quad geometries (`helper-tights`, `helper-skirt`) to maintain natural draping, open sleeves, and high boots.
  4. Automatically compiles `.mhclo` (barycentric coordinates), `.obj` (3D geometry), `.mhmat` (material descriptor), and `.thumb` (preview icon) files directly into `%APPDATA%/.../mpfb/data/clothes/`.
  5. Creates a test `.blend` scene with an avatar dressed in the new wardrobe with Cycles lighting.
* **Inputs**: `prompt` (clothing theme), `--parts` (`torso,pants,shoes`), `--mpfb-dir` (custom target path).
* **Engines**: Flux.1 Dev, ESRGAN 4K, MakeHuman barycentric binding compiler, Blender 5.x.
* **Outputs**: `.mhclo`, `.obj`, `.mhmat`, `.thumb` files per clothing item, plus test `.blend`.

##### 🖼️ Generated Quad Wardrobe & PBR Materials
| Tunic Albedo Texture | Shoes Albedo Texture | Dressed Avatar in Blender (Cycles) |
| :---: | :---: | :---: |
| <img src="../godot_assets/textures/marc_novice/top_rustic_medieval_beig_albedo.png" width="160" /> | <img src="../godot_assets/textures/marc_novice/shoes_dark_worn_medieval_l_albedo.png" width="160" /> | <img src="../godot_assets/marc_novice_render.png" width="160" /> |
| *Burlap tunic albedo (PBR)* | *Worn leather shoes (PBR)* | *Avatar wearing robe & shoes (.mhclo)* |

* **Example**:
  ```bash
  uv run python main.py -w makehuman_clothes "dark worn leather ranger armor" --parts "torso,pants,shoes" -o dark_ranger
  ```

#### 2.4. `outfit` — Automated UV Garment Retexturing
* **Process**:
  1. Inspects existing clothing meshes attached to a character in a Blender scene.
  2. Reads the original MakeHuman sewing pattern UV layouts (preserving 100% of seams, pockets, folds, and button placements).
  3. Generates seamless fabric/leather textures (Albedo, Normal, Roughness) via diffusion.
  4. Calls headless Blender to create independent material slots, applies the textures to the garment quad meshes, and updates the `.blend` file.
  5. Re-exports the production `.glb` model and renders an updated 3-point lighting beauty check.
* **Inputs**: `--character` (e.g. `marc_novice`), `--top` (description of top fabric), `--shoes` (description of footwear material).
* **Engines**: Flux.1 Dev Vulkan, Blender Headless CLI (`bpy`), PBR texture synthesis.
* **Outputs**: `godot_assets/textures/<character>/*`, updated `<character>.blend`, updated `<character>.glb`, `<character>_beauty_render.png`.

##### 🖼️ PBR Retexturing on Existing UV Patterns
| Retextured Albedo Pattern | Relief Normal Map | Cycles Studio Check Render |
| :---: | :---: | :---: |
| <img src="../godot_assets/textures/marc_novice/marc_peasant_worksuit_diffuse.png" width="160" /> | <img src="../godot_assets/textures/marc_novice/marc_peasant_worksuit_normal.png" width="160" /> | <img src="../godot_assets/marc_novice_beauty_render.png" width="160" /> |
| *UV pattern preserving seams and folds* | *Procedural weave relief* | *Marc Novice studio render with the new outfit* |

* **Example**:
  ```bash
  uv run python main.py -w outfit --character marc_novice --top "rough medieval beige burlap tunic" --shoes "dark worn leather boots"
  ```

#### 2.5. `pose_control` — OpenPose Skeleton Guidance & Rigged Godot Scenes
* **Process**:
  1. Queries the 18-point COCO OpenPose coordinate library for the chosen action pose (`idle`, `slash_attack`, `cast_spell`, `shield_block`, `jump`, `walk`).
  2. Renders the OpenPose colored bone skeleton stick-figure card.
  3. Uses the skeleton to guide character diffusion, locking the limbs and torso into the exact target posture.
  4. Removes the background cleanly via RMBG / BiRefNet.
  5. Computes dynamic 2D weapon and effect attachment points (hands, head, feet) from the pose keypoints.
  6. Automatically compiles a Godot 4 `.tscn` scene with a `Sprite2D` and hierarchical `Marker2D` nodes ready for attaching weapons or VFX.
* **Inputs**: `prompt`, `--pose` (`idle`, `slash_attack`, `cast_spell`, `shield_block`, `jump`, `walk`), `-s, --size`.
* **Engines**: OpenPose COCO 18-point mapper, Flux.1 / SDXL, Godot Scene Builder.
* **Outputs**: `_openpose_skeleton.png`, `_character.png`, `_character.tscn`, `_rig.json`.

##### 🖼️ COCO 18-Point Skeleton Pose Variations (`--pose`)
| `--pose idle` | `--pose slash_attack` | `--pose cast_spell` | `--pose shield_block` |
| :---: | :---: | :---: | :---: |
| <img src="../docs/exemples/workflows_2d/pose_idle_skeleton.png" width="140" /> | <img src="../docs/exemples/workflows_2d/pose_slash_attack_skeleton.png" width="140" /> | <img src="../docs/exemples/workflows_2d/pose_cast_spell_skeleton.png" width="140" /> | <img src="../docs/exemples/workflows_2d/pose_shield_block_skeleton.png" width="140" /> |
| *Neutral idle pose* | *Dynamic sword slash* | *Magic spellcasting* | *Defensive shield stance* |

* **Example**:
  ```bash
  uv run python main.py -w pose_control "shadow knight with a glowing sword" --pose slash_attack -o knight_slash
  ```

#### 2.6. `rpg_portrait` — Multi-Emotion Dialogue Character Sets
* **Process**:
  1. Takes a base character description or portrait image.
  2. Iterates across specified emotional states (*Neutral, Happy, Angry, Sad, Hurt, Surprised*), injecting calibrated emotional micro-descriptors while locking identity seeds.
  3. Removes background halos to isolate the character portraits.
  4. Combines the resulting portraits into a single reference contact sheet (`_portrait_grid.png`).
  5. Writes a Godot dialogue JSON manifest containing paths, emotional tags, and metadata ready for Dialogic or custom dialogue managers.
  6. Inputs: `prompt` or `-i, --input`, `--emotions` (default: `neutral,happy,angry,sad,hurt`), `-s, --size`.
* **Engines**: Flux.1 / SDXL Vulkan, BiRefNet / RMBG ONNX, JSON Manifest Generator.
* **Outputs**: individual emotion `.png` files, `_portrait_grid.png`, `_dialogue_manifest.json`.

##### 🖼️ RPG Multi-Emotion Dialogue Sheet (`_portrait_grid.png`)
| Consistent Expression Gallery (Dialogic / Godot Dialogue Manager) |
| :---: |
| <img src="../docs/exemples/workflows_2d/rpg_portrait_grid.png" width="100%" /> |
| *Expression variants with identity anchoring and JSON tagging for lip-sync and narrative branching* |

* **Example**:
  ```bash
  uv run python main.py -w rpg_portrait "dark sorceress with golden eyes" --emotions "neutral,happy,angry,sad,hurt" -o sorceress
  ```

#### 2.7. 👗 MakeHuman 3D Wardrobe Suite & Bilingual Semantic AI Router
* **Bilingual Semantic Router (177 3D Models)** (`core/clothes_catalog.py`):
  - Automatically indexes **177 MakeHuman 3D community assets** into [`data/clothes_catalog.json`](data/clothes_catalog.json) (monk robes, capes, plate armor, overalls, boots, beards, hairstyles).
  - The `aiguiller_modele_vetement(prompt, category, gender)` function semantically pairs natural language prompts in **English or French** (e.g. *"rustic medieval peasant tunic"*, *"monk robe"*, *"viking beard"*, *"heavy leather boots"*) with the ideal 3D base model.
  ```bash
  uv run python core/clothes_catalog.py
  ```
* **AI Retexturing on Canonical UV Sewing Patterns** (`scripts/retexture_uv_garment.py`):
  - Retextures official MakeHuman UV patterns directly (e.g. `male_worksuit01_diffuse.png`, `shoes01_diffuse.png`) to preserve 100% of underlying geometry, pocket seams, and button coordinates while converting blue denim to weathered burlap or aged leather with normal maps.
  ```bash
  uv run python scripts/retexture_uv_garment.py
  ```
* **External 3D Mesh to MakeClothes Compiler** (`scripts/makeclothes_from_mesh.py`):
  - Converts arbitrary quad meshes (`.obj`, `.glb`, `.fbx`) generated from 3D AI tools or sculpted in Blender into official MakeHuman `.mhclo` garments with automatic barycentric vertex binding.
  ```bash
  uv run python scripts/makeclothes_from_mesh.py --mesh "assets/models/cape.obj" --name "traveler_cape" --category "clothes"
  ```
* **Community Asset Pack Installer** (`scripts/install_asset_packs.py`):
  - Extracts and deploys MakeHuman Community zip archives directly into the active MPFB directory and updates the catalog.
  ```bash
  uv run python scripts/install_asset_packs.py
  ```

#### 2.8. 🗺️ MakeHuman Skin Synthesis & Anatomical Calibration
* **Complete MPFB Skin Pack Pipeline**:
  - Generates 2048×2048 diffuse skin maps (`diffuse.png`), PBR normal maps (`normal.png`), MakeHuman material definitions (`.mhmat`) with calibrated Subsurface Scattering (SSS) parameters, and UI thumbnail previews (`.thumb`).
* **Dedicated Scripts**:
  - `scripts/build_clean_marc_skin.py`: Generates seamless, homogeneous skin textures with dedicated colorimetry (e.g., cold winter complexion for Marc).
  - `scripts/align_marc_portrait_to_uv.py`: Projects 2D anatomical facial features (eyes, eyebrows, scars, lips) accurately onto standard MakeHuman hm08 UV layouts without seam tearing.

##### 🖼️ Canonical Skin Synthesis & Anatomical Detail
| Studio Face Close-Up | hm08 Diffuse Skin Texture (Marc) | Grey-Wind Skin Texture (Elian Child) |
| :---: | :---: | :---: |
| <img src="../godot_assets/marc_novice_face_closeup.png" width="160" /> | <img src="../godot_assets/skins/marc_novice/marc_novice_diffuse.png" width="160" /> | <img src="../godot_assets/skins/elian_enfant/elian_enfant_diffuse.png" width="160" /> |
| *Cycles render with Subsurface Scattering* | *Marc Novice 2048² hm08 UV texture* | *2048² cold grey-wind complexion texture* |
* **Deployment**:
  - Installs skin assets automatically into `%APPDATA%/Blender Foundation/Blender/5.2/mpfb/data/skins/<skin_name>/` and syncs them with Godot asset targets.

---
