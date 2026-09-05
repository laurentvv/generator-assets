---
audit:
  date: 2026-09-03 15:12
  grade: F
metrics:
  ruff: 189
  vulture: 133
  hotspots_cd: 35
  hotspots_ef: 3
  avg_mi: 64.7
  duplication: 156
  sloc: 10602
  ruff_density: 17.8
  vulture_density: 12.5
---

# Python Health Report — generator-assets

Generated on 2026-09-03 15:12 by python-health-audit (v2).

## 1. Executive Summary
- Global grade: F
- Reason: Grade F assigned — 1 F-rank hotspot (`lancer_mode_interactif` in `main.py`, cyclomatic complexity 69) and 156 duplicated blocks (R0801) concentrated in `scripts/`, despite an average MI of 64.7 and Ruff density at 17.8/kLOC (D-level).

## 2. Dead Code
### 2.1 Local — Ruff
189 findings:

| Rule | Count | Meaning |
|------|-------|---------|
| F401 | 145 | unused import |
| F541 | 13 | f-string without placeholders |
| E402 | 13 | module-level import not at top |
| E741 | 9 | ambiguous variable name (l, I, O) |
| F841 | 5 | local variable assigned but never used |
| E401 | 3 | multiple imports on one line |
| F811 | 1 | redefinition of unused name |

All F401/F841 are mechanically fixable; no auto-fix applied per audit policy.

### 2.2 Global — Vulture
133 entries at confidence ≥ 60 %. Highest-signal examples:

| Location | Symbol | Confidence |
|----------|--------|------------|
| core/mpfb_ops.py:74 | unused function `verifier_mpfb_disponible` | 60 % |
| core/audio_ops.py:81 | unused variable `freq_env` | 60 % |
| core/audio_ops.py:247 | unused variable `f3` | 60 % |
| core/autotile_builder.py:17 | unused variable `radius` | 100 % |
| core/blender_ops.py:206 | unused variable `epaisseur` | 100 % |
| core/clothes_catalog.py:242 | unused variable `item_id` | 60 % |

> ⚠️ Vulture produces false positives by construction (global static
> detection). Verify each entry before removal.

## 3. Complexity Hotspots (Radon)
38 blocks ranked C or worse (29 C, 6 D, 2 E, 1 F). Worst first:

| Rank | File:Line | Block | cc |
|------|-----------|-------|----|
| **F** | main.py:62 | `lancer_mode_interactif` | **69** |
| E | core/clothes_catalog.py:79 | `construire_catalogue_vetements` | 35 |
| E | core/clothes_catalog.py:207 | `aiguiller_modele_vetement` | 34 |
| D | main.py:292 | `main` | 29 |
| D | core/llm.py:18 | `construire_prompt_coherant` | 28 |
| D | core/render_morphology_tests.py:36 | `render_theme_morphologies` | 28 |
| D | core/render_medieval_themes.py:17 | `render_outfit_theme` | 25 |
| D | workflows/makehuman_clothes.py:31 | `MakeHumanClothesWorkflow` (+ `run`, cc 24) | 25 |

## 4. Code Duplication (Pylint)
156 duplicated blocks (R0801), concentrated in `scripts/`:

- `scripts/test_bake_and_render.py` ↔ `scripts/test_clean_render.py`, `scripts/test_soft_face.py`, `scripts/test_marc_clean_morphology.py` (setup/bake/render boilerplate, up to ~50 identical lines per pair)
- `scripts/blender_bake_projection.py` ↔ `scripts/blender_camera_project_face.py` (Blender env setup)

## 5. Recommended Action Plan
1. **Split `lancer_mode_interactif` (main.py:62, cc 69, rank F)** — decompose into per-mode handlers; it is the single largest crash-risk and the only F-rank block in the codebase.
2. **Factor the Blender script boilerplate in `scripts/`** — a shared `setup_render_env()` / `bake_and_report()` helper would eliminate the bulk of the 156 R0801 duplications (test_bake_and_render, test_soft_face, test_clean_render…).
3. **Purge the 145 unused imports (F401)** — purely mechanical cleanup that removes 77 % of Ruff findings in one pass.

*Audit scope note: `scripts/test_*.py` are files inside `scripts/`, not the `tests/` directory — the `tests/` exclusion does not apply to them, and their duplication is counted as real debt.*
