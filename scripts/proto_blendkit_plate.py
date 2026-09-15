"""Test Blendkit headless : scene CC0 -> plaque 1080p (NON valide, pas un workflow).

Execute DANS Blender en mode background :
  blender.exe --background --python scripts/proto_blendkit_plate.py -- <out_dir> <search_json> <asset_index> [engine]

engine = eevee (defaut) | cycles | workbench. La cle API du compte connecte est lue
dans les preferences de l'addon avant toute reinitialisation, jamais logguee.
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
        raise RuntimeError("aucun fichier .blend dans cet asset")
    if os.path.isfile(blend_path) and os.path.getsize(blend_path) > 0:
        log(f".blend déjà en cache: {blend_path}")
        return
    req = urllib.request.Request(
        f"{BLENDERKIT_API}/downloads/{blend_file['id']}/?scene_uuid={uuid_mod.uuid4()}",
        headers={"Authorization": f"Bearer {api_key}", **UA},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        dl = json.load(r)
    signed_url = dl.get("filePath")
    if not signed_url:
        raise RuntimeError(f"pas de filePath dans la réponse: {str(dl)[:200]}")
    log("téléchargement de la scène en cours...")
    req_file = urllib.request.Request(signed_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req_file, timeout=1800) as r, open(blend_path, "wb") as f:
        f.write(r.read())
    log(f".blend téléchargé: {os.path.getsize(blend_path) / 1e6:.1f} Mo")


def choisir_engine(scene: bpy.types.Scene, souhaite: str) -> str:
    """Affecte le moteur demande ; l'enum RNA ne listant pas tout, on teste l'affectation."""
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
    except Exception as e:  # noqa: BLE001 - on garde CPU en dernier recours
        log(f"config GPU impossible ({e}), Cycles en CPU")


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
        log("ERREUR: aucune clé API (compte non connecté ?)")
        return 2
    log(f"clé API lue ({len(api_key)} caractères, masquée)")

    with open(search_json_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    asset = meta["results"][asset_index]
    log(f"scène cible: {asset['displayName']} (license={asset['license']})")

    blend_path = os.path.join(out_dir, "source_scene.blend")
    telecharger_scene(api_key, asset, blend_path)

    bpy.ops.wm.open_mainfile(filepath=blend_path)
    scene = bpy.context.scene
    log(
        f"scène ouverte: {len(bpy.data.objects)} objets, {len(bpy.data.cameras)} caméras, "
        f"{len(bpy.data.lights)} lumières, animations={len(bpy.data.actions)}"
    )

    cams = [o for o in bpy.data.objects if o.type == "CAMERA"]
    if not cams:
        log("ERREUR: aucune caméra dans la scène")
        return 4
    log(f"caméras: {[c.name for c in cams]}")

    # Les scènes anciennes crament en Standard : AgX + exposure négative pour la sonde
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
    log(f"moteur: {engine}")
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
        log(f"caméra choisie: {cams[0].name}")
    else:
        log(f"caméra de la scène: {scene.camera.name}")

    scene.render.filepath = os.path.join(out_dir, "plaque_1080p.png")
    bpy.ops.render.render(write_still=True)
    log(f"rendu OK -> {scene.render.filepath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
