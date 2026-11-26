# 3D pipeline: Blender headless → GLB → Godot

Prerequisites, game-ready standards and pitfalls for any 3D asset produced by the factory
(`mesh3d`, `mesh_ia`, `voxel3d`, `asset_blendkit`, MakeHuman suite
`character3d`/`makehuman_clothes`/`outfit`). Standards adapted from the blender-skills pack
(arjun988, MIT) — only the engine-agnostic part was retained: here everything is **headless CLI**
(`blender --background --python`), no MCP addon. The budgets are "AAA-informed" orders of
magnitude, to be adjusted per project.

## 1. Prerequisites (blocking depending on the workflow)

| Component | Required by | Detail |
| :--- | :--- | :--- |
| **Blender 4.0→5.2** | `mesh3d`, `voxel3d`, `asset_blendkit` (blocking); `mesh_ia` (optional: decimation + control contact sheet silently skipped if absent); MakeHuman suite (blocking) | Resolution `core/blender_ops.py::trouver_blender()`: env `BLENDER_PATH` → `blender` in the PATH → `C:\Program Files\Blender Foundation\Blender 4.0…5.2\blender.exe`. `uv run python main.py --check` detects it |
| **MPFB2 addon** | `character3d`, `character_makeup`, `makehuman_clothes`, `outfit` | Extension `bl_ext.user_default.mpfb` installed in Blender; data dir `%APPDATA%\Blender Foundation\Blender\5.2\mpfb\data\data` (env override `MPFB_DATA_DIR`, cf. `core/config.py`) |
| **BlenderKit addon connected** | `asset_blendkit` | Login done **once in the GUI** (the API key is only readable inside the Blender process, never out of process); the code forces the CC0 license |
| **Falling Leaves addon** | (GUI only — autumn foliage ambience plates, no workflow) | Extension `bl_ext.user_default.falling_leaves` v1.7.0 (GPL-3.0+, official platform) installed 2026-11-17, smoke-tested (MEMORY_BANK §1.64). **BUG: `add_wind` resets Leaf Count to 25 — apply wind first or re-apply settings after**; wind strength on the `Wind_FallingLeaves` field, not the panel props |

Blender is always invoked as a headless subprocess with generated bpy scripts
(`--background --python`); success is detected via stdout markers (`SUCCESS:`,
`RENDERS_RESULT_JSON:`) — always check the announced output files, not only the return code.

## 2. Game-ready standards (Godot 4 target)

### Units, axes, scale
- **1 Blender unit = 1 meter**; export as **GLB, +Y up** (already the case: `export_yup=True` on
  the MPFB side, GLB everywhere else).
- Check the scale at Godot import with a known reference (door ≈ 2 m tall, floor at y = 0).

### Naming (engine prefixes)
| Type | Prefix | Example |
| :--- | :--- | :--- |
| Mesh | `SM_` | `SM_Weapon_Rifle_A`, `SM_Prop_Crate_Wood_01` |
| Material | `MAT_` | `MAT_Metal_Painted_Red` |
| Texture | `T_` | `T_Console_BC`, `T_Console_N`, `T_Console_ORM` |
| Animation | `AN_` | `AN_Door_Open` |
| Armature | `ARM_` | `ARM_Robot_Loader` |

Rules: PascalCase + underscores, `_01` (not `_1`), descriptive (not `SM_Thing`), **≤ 64
characters**. Texture suffixes: `_BC` albedo, `_N` normal, `_ORM` packed (R=AO, G=Roughness,
B=Metallic), `_E` emission. NB: this repo's `material3d` outputs use their own suffixes
(`_albedo/_normal/_orm…`) — rename to the convention above when integrating into the game.

**Godot collision**: at GLB import, Godot 4 automatically generates collision shapes for nodes
suffixed `-col`, `-colonly` (trimesh), `-convcol`, `-convcolonly` (convex) — not the `COL_`/`UCX_`
convention (Unreal). For a simple decorative prop, prefer `-convcolonly` on a low-poly proxy
rather than the full trimesh.

### Triangle budgets
| Category | Tier | Tris |
| :--- | :--- | :--- |
| Props | Hero (held, close-up) | 15,000–50,000 |
| Props | Standard (scene, medium distance) | 5,000–15,000 |
| Props | Background / clutter | 500–5,000 |
| Props | Small (pieces, debris) | 100–500 |
| Characters | Hero | 50,000–100,000 |
| Characters | NPC | 20,000–40,000 |
| Characters | Crowd | 5,000–10,000 |
| Environment | 2 m modular wall / floor slab | 200–800 / 100–400 |
| Environment | Hero building / hero rock | 5,000–20,000 / 1,000–5,000 |
| Environment | Realistic / stylized tree | 5,000–15,000 / 200–2,000 |

Direct mapping onto `mesh_ia --faces-cible`: **30000 = hero prop, 10000 = standard prop,
2,000–3,000 = repeated clutter, ≥ 8000 if the silhouette is highly curved**. Lowpoly style: −50
to −90%.

If over budget: remove internal/non-visible faces, move detail to the normal map, build a LOD
chain before final validation.

### LOD
| LOD | % tris | Distance |
| :--- | :--- | :--- |
| LOD0 | 100% | 0–10 m |
| LOD1 | 50% | 10–25 m |
| LOD2 | 25% | 25–50 m |
| LOD3 | 10% | 50 m+ |

In this repo, decimation goes through `mesh_ia --faces-cible` (Decimate **COLLAPSE**, delimiters
`SHARP`/`UV` — preserves UVs). In manual Blender: `planar` suits hard-surface, `collapse` for
organic. Naming `SM_Asset_LOD0…LOD3`.

### Textures & materials
| Tier | Resolution | Texel density |
| :--- | :--- | :--- |
| Hero | 2048–4096 | 512–1024 px/m |
| Standard | 1024–2048 | 256–512 px/m |
| Background | 512–1024 | 128–256 px/m |

Texel density = resolution ÷ physical size (m) — e.g. 1024 px over 2 m = 512 px/m; stay
consistent across assets in the same scene. Materials per asset: hero 3–5, standard 1–2, modular
kit 1 (atlas). The repo pipeline produces **Principled BSDF** → natively converted to glTF/Godot
PBR; the expected ORM packing is R=AO, G=Roughness, B=Metallic.

## 3. Pre-delivery validation checklist (headless)

1. **Look at the asset** — never deliver an unseen GLB: `mesh_ia` control contact sheet (4 EEVEE
   orbital views 900²), `character3d` Cycles renders, `asset_blendkit` preview. Subjective
   render → submit to the user (repo rule).
2. **Audit**: triangle count vs budget (was `--faces-cible` really applied?), material count,
   scale, no visible inverted normals on the sheet.
3. **Godot import test**: correct scale (known reference), imported materials
   (StandardMaterial3D), collision if required (`-colonly`), readable silhouette at gameplay
   distance, animations as named clips if applicable.

Typical report: PASS/FAIL status, polycount (vs budget), material count, dimensions, issue(s)
found + fix applied, views checked.

## 4. Consolidated pitfalls (Blender / MPFB / BlendKit)

- **Mixamo rig order BEFORE the `.mhclo`**: otherwise the clothes are not skinned
  (`creer_corps_personnage_mpfb` guarantees the order — respect it in any derived script).
- **Area lights**: add `TRACK_TO` constraints toward the target (they point in −Z by default).
- **MPFB head renders**: disable the "delete" MASK modifiers before rendering.
- **MakeHuman face UVs (hm08)**: the face island lives in X ∈ [1450..2000] — do not move it
  during MakeUp ink layers.
- **Headless BlendKit**: the addon's local daemon is unusable with `--background` → go through
  `scripts/blendkit_blender_job.py`; read the API key from the preferences **before**
  `read_factory_settings` (which resets them); **absolute** paths in the job JSON; EEVEE
  saturates some scenes → switch the render to Cycles HIP.
- **Blender absent**: `mesh_ia` silently returns `None` for decimation/contact sheet
  (non-blocking) — check that the expected outputs exist before announcing delivery.

## 5. Mini brief before any 3D game asset ("director" pattern)

Four questions before launching — they determine workflow and budget:
1. **Type**: prop / character / environment / voxel?
2. **Tier**: hero (close-up), standard (scene), background (clutter)? → triangle + texture
   budget §2.
3. **Target**: Godot game (GLB + §2 standards) or YouTube render (raw quality, flexible
   budgets)?
4. **Animated/rigged?** → rig required (`character3d`), `AN_*` clips, plan topology margin on
   the deformation zones.

Typical hero-prop chain: `generate` (concept) → `mesh_ia --res 512` iteration (~11 min) →
`mesh_ia --res 1024` master (~55 min) → `--faces-cible 30000` → §3 checklist. After user
validation, the recipe becomes a workflow (repo rule).

## 6. IA-mesh finish pipeline (concepts from AssetFurnace — inspiration, not adoption)

Source: [Bingeljell/image-to-3dlab](https://github.com/Bingeljell/image-to-3dlab) ("AssetFurnace",
Apache-2.0, eval 2026-11-26): an orchestrator turning prompt/image into a rigged + animated GLB.
**Not runnable here** — every 3D backend it drives needs Metal / CUDA-Linux / HIP-Linux (RDNA3),
and its TRELLIS.2/Hunyuan paths are PyTorch + CUDA-only extensions (flash-attn, nvdiffrast,
spconv). Only the *pipeline concepts* below are ported, as headless bpy steps applied to the raw
GLB our own Vulkan engines emit (`trellis-cli` = pwilkin/trellis.cpp `C:\trellis`; Pixal3D fork =
raven38/pixal3d.cpp `C:\pixal3d`, SV mode `--sv-image RGBA.png -m <sv-set-dir>`, FOV 20° gauge,
seed 42).

1. **Pixel Match (source-pixel reprojection)** — AssetFurnace paints every mesh surface visible
   from the source image with the image's *real pixels* (text/logos/faces stay sharp where the
   texture-flow repaint would blur them). Port: bake the source RGBA onto the GLB atlas from the
   front gauge camera (SV = FOV 20°, mesh_scale 1.0; bpy camera + `object.bake` diffuse), keep the
   flow-textured output as the occluded-region fallback. Highest value on heraldry/face details
   for game assets (evaluated per asset — flat 2D sprites may not benefit).
2. **Finish (retopo + texture compression)** — engines already quadric-decimate (300k @1024
   default; `--decim` legacy grid alternative). For game tiers add a Blender Decimate pass to the
   §2 budget, and drop the atlas a tier for standard/background assets (2048→1024); GLB textures
   are already WebP-compressed by trellis-cli (`--webp on` default) — keep `gltfpack` in mind for
   split props.
3. **Auto-rig + animation presets** — AssetFurnace's SkinTokens + 21 presets are model-based (not
   portable). Our chain stays MPFB/`character3d` for humanoids; for props/creatures, watch
   upstream trellis.cpp (multiview merges landed upstream 2026-11-24) before hand-rigging. GLB
   animations land as `AN_*` clips (§2).
4. **Prop sheets** — one concept image → several props with LODs: decompose on the 2D side first
   (qwen_edit_2511 object isolation, same family as the n2m sprite pipeline), then one engine run
   per prop with the §2 tier budgets.
5. **Provenance** — AssetFurnace emits a `.provenance.json` per run (hashes, settings, license
   class). Our equivalent: the workflow journal + night-run legs already record seed/res/weights;
   keep recording the engine commit (version.json discipline) next to each delivered GLB.

Status: concepts recorded 2026-11-26; none promoted to a workflow yet — each needs a validated
bpy recipe on a real asset before adoption (repo rule).
