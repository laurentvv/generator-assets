"""Transcode a GLB with EXT_texture_webp (TRELLIS output) into a raylib-
friendly GLB with PNG textures, via headless Blender (webp decode support).

Usage (from repo root):
    uv run python scripts/proto_raylib/gltf_webp_to_png.py <in.glb> <out.glb>
"""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.blender_ops import trouver_blender  # noqa: E402

BPY_SCRIPT = r"""
import bpy
import sys

src, dst = sys.argv[-2], sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
bpy.ops.export_scene.gltf(filepath=dst, export_format='GLB',
                          export_image_format='PNG')
print("SUCCESS: " + dst)
"""


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: gltf_webp_to_png.py <in.glb> <out.glb>")
        return 2
    src, dst = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    os.makedirs(os.path.dirname(dst), exist_ok=True)

    blender = trouver_blender()
    if not blender:
        print("ERROR: Blender binary not found")
        return 1

    tmp = os.path.join(tempfile.gettempdir(), "proto_raylib_webp_transcode.py")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(BPY_SCRIPT)

    cmd = [blender, "--background", "--factory-startup", "--python", tmp, "--", src, dst]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        print(f"ERROR: Blender exited {proc.returncode}")
        print((proc.stderr or "")[-600:])
        return 1
    if not os.path.exists(dst) or os.path.getsize(dst) == 0:
        print("ERROR: output GLB missing/empty")
        return 1
    print(f"TRANSCODE OK: {dst} ({os.path.getsize(dst)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
