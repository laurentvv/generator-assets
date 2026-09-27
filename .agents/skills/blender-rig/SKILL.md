---
name: blender-rig
description: Local AI rigging and animation in Blender via MCP (port 9876) — build an agentic Rigify rig on a bare mesh (human or quadruped), animate with procedural FK, generate AI text→motion mocap (Kimodo CPU), export a Godot game-ready GLB with AN_* clips, and render MP4 control clips (multi-view captures). Use this skill when the user wants to rig, skin, animate a character or animal, generate AI mocap, export an animated asset to Godot, or run the full "mesh → rig → animation → GLB" pipeline — but NOT for a simple static asset (generator-assets is enough).
---

# blender-rig — local AI rigging & animation (Blender MCP)

Validated chain from the 2026-09-18 campaign (MEMORY_BANK §1.28): **mesh → agentic Rigify
rig → animation (procedural FK or native/Kimodo mocap) → verified Godot GLB**.
Golden rule from user verdicts: **native/natural mocap on a textured character = the
standard**; procedural FK = ambiance loops; inter-rig retarget and mocap dressing =
PARKED (functional, not visually retained).

## 1. Setup — driving Blender from the agent

1. Blender GUI launched with MCP autostart:
   `blender.exe --python scripts/proto_rig/demarrer_blender_mcp.py`
   (BlenderMCP v1.5 addon already installed — socket localhost:9876).
2. Direct client (protocol: 1 JSON per connection):
   `uv run python scripts/proto_rig/blender_client.py --ping|--code <py>|--screenshot out.png`
3. Verification loop = **multi-view captures**:
   `uv run python scripts/proto_rig/capture_multivues.py <name> [-t 1100]`
   (front/¾/side/back, auto-framing, offscreen GPU — works with the window in the
   background). Always verify visually after each step.

## 2. Agentic rigging (human and quadruped)

Proven recipe (human 410 bones, wolf 823 bones):

1. **Measure the mesh** in slices (height, shoulders, hips, neck —
   Z positions, X/Y widths): the fit is geometric, not by eye.
2. **Meta-rig**: human = `armature_human_metarig_add`; quadrupeds = Rigify ships
   **wolf / cat / horse / shark / bird** + `basic_quadruped`
   (`armature_wolf_metarig_add` etc.).
3. **Fit**: uniform scale + repositioning of key bones in EDIT mode
   (systematic align_roll), **slight elbow/knee bend mandatory** (straight
   limbs = Rigify `compute_pole_angle` crash).
4. **Facial rig**: either kept (wolf, 823 bones), or removed + `use_head`/`neck_pos`
   parameters on the spine bone (otherwise no head deform bone —
   workaround: `use_deform` controls + manual vertex groups, fragile).
5. `pose.rigify_generate` — **never from a hidden meta-rig** (AssertionError
   `__duplicate_rig`); the result object ≠ metarig → rename it.
6. **Weights**: `parent_set(type='ARMATURE_AUTO')` on the mesh.
7. **Test poses** + multi-view captures before validating.

## 3. Animation

- **Procedural FK** (validated: wolf trot "OK"): switch limbs to FK
  (`['IK_FK'] = 1.0` on the `*_parent` bones, keyframed) — otherwise the FK
  controls are inert; **limit the switch to limbs** (torso switched = shoulder
  blob). Proven axes: arms Z ∓1.35 = lower (L/R mirror), thighs X for stride.
  **Fixed side camera** for locomotion (3/4 front view kills readability).
  Render: `rendre_clip.py --fixe [--profil] --boucle`.
- **Native pack mocap** (validated "perfect"): render the pack's rig with its
  native actions — do not retarget without need (tried: below the bar).
- **AI Kimodo mocap** (`C:\IA\kimodo`, text→BVH CPU 50 s): validated engine,
  BVH delivered. Dressing on a mesh = PARKED (vertex group conflicts);
  `TEXT_ENCODERS_DIR` + NousResearch mirror + MinGW DLL required (details §1.28).
- **Inter-rig retarget** (`retarget_quaternius.py`): world deltas → local basis,
  DEF constraints muted, purge by difference — PARKED (amplitude below native).

## 4. Godot game-ready export

```bash
uv run python main.py -w animal_godot -i <packed_animal.blend> -o <output.glb> [--animal-prefixe AN_]
```

Purges pack parasites (Camera/Cube/Light), clips renamed `AN_*` (one per native
action), export `export_animation_mode='ACTIONS'`, **verified by re-import**
(bones + clips + meshes). Delivered example:
`output/test_rig/loup_quaternius_godot.glb` (51 bones, 12 clips, CC0).

## 5. Critical pitfalls (full history in MEMORY_BANK §1.28)

- `libraries.load` does NOT instantiate into the scene → **link explicitly to
  `scene.collection`**, otherwise neither animation nor constraints evaluated.
- Legacy 2.79 actions under Blender 5.2: evaluate fcurves by hand
  (`channelbag.fcurves[i].evaluate(f)`) — `frame_set` does not play them.
- GLB import: local matrices ROTATED (Y-up) → geometric offsets in world space
  via inverse of `matrix_world`; `bound_box` is a lazy cache.
- Retarget: quaternions in local basis (`rest⁻¹ @ frame`), never armature space;
  object deletions by BEFORE/AFTER DIFFERENCE (never by name proximity).
- `read_factory_settings` in MCP cuts the socket response; headless
  exports/imports: direct `select_set` (`select_all` = missing context);
  engine enum = `BLENDER_EEVEE`; `origin_set` without `mode` argument.
