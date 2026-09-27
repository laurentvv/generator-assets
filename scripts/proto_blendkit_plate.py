"""Headless Blendkit test: CC0 scene -> 1080p plate (NOT validated, not a workflow).

Run INSIDE Blender in background mode:
  blender.exe --background --python scripts/proto_blendkit_plate.py -- <out_dir> <search_json> <asset_index> [engine]

engine = eevee (default) | cycles | workbench. The connected account's API key is read
from the addon preferences before any reinitialization, never logged.
"""

import bpy
import json
import os
import sys
import urllib.request
import uuid as uuid_mod

BLENDERKIT_API = "https://www.blenderkit.com/api/v1"
ADDON_MODULE = "bl_ext.user_default.blenderkit"
UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def log(message: str) -> None:
    print(f"[proto_blendkit_plate] {message}", flush=True)


def telecharger_scene(api_key: str, asset: dict, blend_path: str) -> None:
    blend_file = next((f_ for f_ in asset["files"] if f_["fileType"] == "blend"), None)
    if blend_file is None:
        raise RuntimeError("no .blend file in this asset")
    if os.path.isfile(blend_path) and os.path.getsize(blend_path) > 0:
        log(f".blend already cached: {blend_path}")
        return
    req = urllib.request.Request(
        f"{BLENDERKIT_API}/downloads/{blend_file['id']}/?scene_uuid={uuid_mod.uuid4()}",
        headers={"Authorization": f"Bearer {api_key}", **UA},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        dl = json.load(r)
    signed_url = dl.get("filePath")
    if not signed_url:
        raise RuntimeError(f"no filePath in the response: {str(dl)[:200]}")
    log("downloading the scene...")
    req_file = urllib.request.Request(signed_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req_file, timeout=1800) as r, open(blend_path, "wb") as f:
        f.write(r.read())
    log(f".blend downloaded: {os.path.getsize(blend_path) / 1e6:.1f} MB")


def choisir_engine(scene: bpy.types.Scene, souhaite: str) -> str:
    """Assigns the requested engine; the RNA enum not listing everything, we test the assignment."""
    for candidat in (souhaite, "CYCLES", "BLENDER_EEVEE", "BLENDER_WORKBENCH"):
        if not candidat:
            continue
        try:
            scene.render.engine = candidat
            return scene.render.engine
        except (TypeError, RuntimeError):
            continue
    return scene.render.engine


def configurer_cycles_gpu(scene: bpy.types.Scene) -> None:
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for dtype in ("HIP", "VULKAN", "CUDA", "OPTIX", "NONE"):
            try:
                prefs.compute_device_type = dtype
                break
            except TypeError:
                continue
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type != "CPU"
            log(f"device cycles: {d.name} ({d.type}) use={d.use}")
        scene.cycles.device = "GPU"
    except Exception as e:  # noqa: BLE001 - CPU kept as a last resort
        log(f"GPU config impossible ({e}), Cycles on CPU")


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1 :]
    out_dir, search_json_path, asset_index = argv[0], argv[1], int(argv[2])
    engine_souhaite = argv[3] if len(argv) > 3 else "eevee"
    mode = "final"
    if engine_souhaite == "probe":
        mode = "probe"
        engine_souhaite = argv[4] if len(argv) > 4 else "eevee"
    os.makedirs(out_dir, exist_ok=True)

    prefs = bpy.context.preferences.addons.get(ADDON_MODULE)
    api_key = getattr(prefs.preferences, "api_key", "") if prefs else ""
    if not api_key:
        log("ERROR: no API key (account not signed in?)")
        return 2
    log(f"API key read ({len(api_key)} characters, masked)")

    with open(search_json_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    asset = meta["results"][asset_index]
    log(f"target scene: {asset['displayName']} (license={asset['license']})")

    blend_path = os.path.join(out_dir, "source_scene.blend")
    telecharger_scene(api_key, asset, blend_path)

    bpy.ops.wm.open_mainfile(filepath=blend_path)
    scene = bpy.context.scene
    log(
        f"scene opened: {len(bpy.data.objects)} objects, {len(bpy.data.cameras)} cameras, "
        f"{len(bpy.data.lights)} lights, animations={len(bpy.data.actions)}"
    )

    cams = [o for o in bpy.data.objects if o.type == "CAMERA"]
    if not cams:
        log("ERROR: no camera in the scene")
        return 4
    log(f"cameras: {[c.name for c in cams]}")

    # Old scenes burn in Standard: AgX + negative exposure for the probe
    vt = scene.view_settings
    for name in ("AgX", "Filmic", "Standard"):
        if name in [i.identifier for i in vt.bl_rna.properties["view_transform"].enum_items]:
            vt.view_transform = name
            break
    vt.exposure = -1.0
    log(f"view transform: {vt.view_transform}, exposure {vt.exposure}")

    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080

    engine = choisir_engine(scene, {"eevee": "BLENDER_EEVEE", "cycles": "CYCLES", "workbench": "BLENDER_WORKBENCH"}.get(engine_souhaite, ""))
    log(f"engine: {engine}")
    scene.render.engine = engine
    if engine == "CYCLES":
        configurer_cycles_gpu(scene)
        scene.cycles.samples = 96
    if "EEVEE" in engine:
        eevee = getattr(scene, "eevee", None)
        if eevee and hasattr(eevee, "taa_render_samples"):
            eevee.taa_render_samples = 64

    if mode == "probe":
        scene.render.resolution_x = 960
        scene.render.resolution_y = 540
        for cam in cams:
            scene.camera = cam
            scene.render.filepath = os.path.join(out_dir, f"probe_{cam.name.replace('.', '_')}.png")
            bpy.ops.render.render(write_still=True)
            log(f"probe OK -> {scene.render.filepath}")
        return 0

    if scene.camera is None:
        scene.camera = cams[0]
        log(f"chosen camera: {cams[0].name}")
    else:
        log(f"scene camera: {scene.camera.name}")

    scene.render.filepath = os.path.join(out_dir, "plaque_1080p.png")
    bpy.ops.render.render(write_still=True)
    log(f"render OK -> {scene.render.filepath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
