"""LEG 3a - Blender headless: bake a deterministic procedural crystal-on-rock
asset and export it as GLB for the raylib turntable renderer.

Usage (from repo root):
    uv run python scripts/proto_raylib/bake_gem_blender.py [output.glb]

Determinism: vertex jitter uses random.seed(42); no clock, no UI state.
Pattern follows core/mesh_ia.py: blender --background --factory-startup
--python <tmp> -- <args-after-->. Absolute paths only (MEMORY lesson 1.26).
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.blender_ops import trouver_blender  # noqa: E402

DEFAULT_OUT = os.path.abspath("output/test_raylib/turntable/gem_blender.glb")

# bpy script executed inside Blender. Arguments after "--" land in sys.argv[-2:].
BPY_SCRIPT = r"""
import bpy
import random
import sys

out_glb = sys.argv[-1]

bpy.ops.wm.read_factory_settings(use_empty=True)
random.seed(42)

# ---- pedestal: subdivided cube with deterministic vertex jitter ----
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 0.28))
bpy.ops.object.modifier_add(type='SUBSURF')
ped = bpy.context.active_object
ped.name = "SM_crystal_rock"
ped.modifiers["Subdivision"].levels = 3
bpy.ops.object.modifier_apply(modifier="Subdivision")
ped.scale = (1.5, 1.5, 0.56)
bpy.ops.object.transform_apply(scale=True)
for v in ped.data.vertices:
    flat_top = 1.0 - min(v.co.z + 0.5, 1.0)  # top face stays flatter
    d = 0.09 * flat_top
    v.co.x += random.uniform(-d, d)
    v.co.y += random.uniform(-d, d)
    v.co.z += random.uniform(-d * 0.5, d * 0.5)
for poly in ped.data.polygons:
    poly.use_smooth = True

rock_mat = bpy.data.materials.new("MAT_crystal_rock")
rock_mat.use_nodes = True
bsdf = rock_mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.045, 0.045, 0.052, 1.0)
bsdf.inputs["Roughness"].default_value = 0.92
ped.data.materials.append(rock_mat)

# ---- crystal gem: elongated icosphere, emissive violet-cyan ----
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.42, location=(0.0, 0.0, 0.82))
gem = bpy.context.active_object
gem.name = "SM_crystal_gem"
gem.scale = (0.9, 0.9, 1.65)
gem.rotation_euler = (0.0, 0.0, 0.26)
bpy.ops.object.transform_apply(rotation=True, scale=True)
for poly in gem.data.polygons:
    poly.use_smooth = True

gem_mat = bpy.data.materials.new("MAT_crystal_gem")
gem_mat.use_nodes = True
bsdf = gem_mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.45, 0.15, 0.85, 1.0)
bsdf.inputs["Roughness"].default_value = 0.06
bsdf.inputs["Metallic"].default_value = 0.15
for emissive in ("Emission Color", "Emission"):
    if emissive in bsdf.inputs:
        bsdf.inputs[emissive].default_value = (0.25, 0.75, 1.0, 1.0)
        break
for strength in ("Emission Strength", "Emission"):
    if strength in bsdf.inputs and strength != emissive:
        bsdf.inputs[strength].default_value = 1.6
for trans in ("Transmission Weight", "Transmission"):
    if trans in bsdf.inputs:
        bsdf.inputs[trans].default_value = 0.6
gem.data.materials.append(gem_mat)

# ---- export GLB (Godot-style: +Y up, selection only) ----
for obj in (ped, gem):
    obj.select_set(True)
bpy.ops.export_scene.gltf(
    filepath=out_glb,
    export_format='GLB',
    use_selection=True,
)
print("SUCCESS: " + out_glb)
"""


def main() -> int:
    out = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    os.makedirs(os.path.dirname(out), exist_ok=True)

    blender = trouver_blender()
    if not blender:
        print("ERROR: Blender binary not found (BLENDER_PATH / PATH / Program Files)")
        return 1

    # absolute temp path (MEMORY 1.26: relative paths silently lost headless)
    tmp = os.path.join(tempfile.gettempdir(), "proto_raylib_bake_gem.py")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(BPY_SCRIPT)

    import subprocess
    cmd = [blender, "--background", "--factory-startup", "--python", tmp, "--", out]
    print("BAKE_GEM: running Blender headless...")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    tail = (proc.stdout or "").strip().splitlines()[-6:]
    for line in tail:
        print("  | " + line)
    if proc.returncode != 0:
        print(f"ERROR: Blender exited {proc.returncode}")
        print((proc.stderr or "")[-800:])
        return 1
    if not os.path.exists(out) or os.path.getsize(out) == 0:
        print("ERROR: GLB missing/empty after bake")
        return 1
    print(f"BAKE_GEM OK: {out} ({os.path.getsize(out)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
