#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Blendkit worker executed INSIDE Blender in background mode.

Reads a JSON job file (written by core/blendkit.py), downloads the asset
via the Blendkit API with the connected account key (read from the addon
preferences, never logged), then:
  - "prop" mode  : append of the objects -> GLB export + Workbench control render;
  - "plate" mode : opening of the scene -> Cycles/EEVEE render (compositing plate).

Call:
  blender.exe --background --python scripts/blendkit_blender_job.py -- <job.json>

The worker writes <job_dir>/resultat.json (status + info) and logs with the
[blendkit_workflow] prefix.
"""

import bpy
import json
import math
import os
import sys
import urllib.request
import uuid as uuid_mod

BLENDERKIT_API = "https://www.blenderkit.com/api/v1"
UA_NAVIGATEUR = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def log(message: str) -> None:
    print(f"[blendkit_workflow] {message}", flush=True)


def lire_cle_api(module_addon: str) -> str:
    prefs = bpy.context.preferences.addons.get(module_addon)
    return getattr(prefs.preferences, "api_key", "") if prefs else ""


def telecharger_blend(api_key: str, file_id: str, cache_path: str, no_cache: bool) -> str:
    """Downloads the asset .blend (authenticated endpoint -> signed URL), with cache."""
    if not no_cache and os.path.isfile(cache_path) and os.path.getsize(cache_path) > 0:
        log(f".blend already cached: {cache_path}")
        return cache_path
    req = urllib.request.Request(
        f"{BLENDERKIT_API}/downloads/{file_id}/?scene_uuid={uuid_mod.uuid4()}",
        headers={"Authorization": f"Bearer {api_key}", **UA_NAVIGATEUR},
    )
    with urllib.request.urlopen(req, timeout=60) as reponse:
        dl = json.load(reponse)
    url_signee = dl.get("filePath")
    if not url_signee:
        raise RuntimeError(f"no filePath in the download response: {str(dl)[:200]}")
    log("downloading the asset…")
    req_fichier = urllib.request.Request(url_signee, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req_fichier, timeout=1800) as reponse, open(cache_path, "wb") as f:
        f.write(reponse.read())
    log(f".blend downloaded: {os.path.getsize(cache_path) / 1e6:.1f} MB")
    return cache_path


# ---------------------------------------------------------------- "prop" mode

def importer_objets(chemin_blend: str) -> list:
    with bpy.data.libraries.load(chemin_blend, link=False) as (src, dst):
        dst.objects = src.objects
    scene = bpy.context.scene
    importes = []
    for obj in dst.objects:
        if obj is not None:
            scene.collection.objects.link(obj)
            importes.append(obj)
    return importes


def cadrer_camera(scene: bpy.types.Scene, meshes: list) -> None:
    from mathutils import Vector

    points = [o.matrix_world @ Vector(corner) for o in meshes for corner in o.bound_box]
    mn = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    mx = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    centre = (mn + mx) / 2
    rayon = (mx - mn).length / 2
    demi_fov = math.radians(20.0)  # 50 mm lens, 36 mm sensor
    distance = (rayon / math.sin(demi_fov)) * 1.25 if rayon > 0 else 4.0
    direction = Vector((1.0, -1.0, 0.7)).normalized()
    donnees = bpy.data.cameras.new("CamControle")
    cam = bpy.data.objects.new("CamControle", donnees)
    scene.collection.objects.link(cam)
    cam.location = centre + direction * distance
    cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
    donnees.clip_end = 1000.0
    scene.camera = cam


def executer_mode_prop(job: dict, chemin_blend: str, resultat: dict) -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    importes = importer_objets(chemin_blend)
    meshes = [o for o in importes if o.type == "MESH"]
    if not meshes:
        raise RuntimeError("no imported mesh")
    faces = sum(len(o.data.polygons) for o in meshes)
    materiaux = sorted({m.name for o in meshes for m in o.data.materials if m})
    log(f"import OK: {len(importes)} objects, {len(meshes)} meshes, {faces} faces")
    resultat.update(objets=len(importes), maillages=len(meshes), faces=faces, materiaux=materiaux)

    cadrer_camera(scene, meshes)
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "TEXTURE"
    scene.render.resolution_x = 800
    scene.render.resolution_y = 800
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = job["prop"]["apercu"]
    bpy.ops.render.render(write_still=True)
    resultat["apercu"] = job["prop"]["apercu"]
    log("Workbench control render OK")

    glb = job["prop"]["glb"]
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB")
    resultat["glb"] = glb
    resultat["glb_mo"] = round(os.path.getsize(glb) / 1e6, 1)
    log(f"GLB export: {resultat['glb_mo']} MB -> {glb}")


# ---------------------------------------------------------------- "plate" mode

def configurer_cycles_gpu(scene: bpy.types.Scene) -> str:
    """Enables Cycles GPU acceleration (HIP/Vulkan/CUDA depending on availability); returns the detail."""
    detail = "CPU"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for dtype in ("HIP", "VULKAN", "CUDA", "OPTIX", "NONE"):
            try:
                prefs.compute_device_type = dtype
                break
            except TypeError:
                continue
        prefs.get_devices()
        actifs = []
        for d in prefs.devices:
            d.use = d.type != "CPU"
            if d.use:
                actifs.append(f"{d.name} ({d.type})")
        scene.cycles.device = "GPU"
        detail = ", ".join(actifs) or "CPU"
    except Exception as e:  # noqa: BLE001 - CPU as last resort
        log(f"GPU config impossible ({e}), Cycles on CPU")
    return detail


def executer_mode_plate(job: dict, chemin_blend: str, resultat: dict) -> None:
    bpy.ops.wm.open_mainfile(filepath=chemin_blend)
    scene = bpy.context.scene
    resultat["objets"] = len(bpy.data.objects)
    resultat["lumieres"] = len(bpy.data.lights)
    log(f"scene opened: {resultat['objets']} objects, {resultat['lumieres']} lights")

    options = job["plate"]
    cams = [o for o in bpy.data.objects if o.type == "CAMERA"]
    if not cams:
        raise RuntimeError("no camera in the scene (render a prop in prop mode, or pick another scene)")
    nom_demande = options.get("camera")
    if nom_demande:
        cam = next((c for c in cams if c.name == nom_demande), None)
        if cam is None:
            raise RuntimeError(f"camera '{nom_demande}' not found; available: {[c.name for c in cams]}")
        scene.camera = cam
    elif scene.camera is None:
        scene.camera = cams[0]
    resultat["camera"] = scene.camera.name
    log(f"camera: {resultat['camera']}")

    vt = scene.view_settings
    transform_demande = options.get("view_transform") or "AgX"
    for nom in (transform_demande, "AgX", "Filmic", "Standard"):
        if nom in [i.identifier for i in vt.bl_rna.properties["view_transform"].enum_items]:
            vt.view_transform = nom
            break
    vt.exposure = float(options.get("exposure", -1.0))
    resultat["view_transform"] = vt.view_transform
    log(f"colorimetry: {vt.view_transform}, exposure {vt.exposure}")

    scene.render.resolution_x = int(options.get("width", 1920))
    scene.render.resolution_y = int(options.get("height", 1080))
    scene.render.resolution_percentage = int(options.get("percentage", 100))
    resultat["resolution"] = (
        f"{scene.render.resolution_x * scene.render.resolution_percentage // 100}"
        f"x{scene.render.resolution_y * scene.render.resolution_percentage // 100}"
    )
    log(f"effective resolution: {resultat['resolution']}")

    moteur_demande = options.get("engine", "cycles")
    if moteur_demande == "eevee":
        scene.render.engine = "BLENDER_EEVEE"  # incomplete RNA enum: direct assignment
    if scene.render.engine == "CYCLES":
        resultat["gpu"] = configurer_cycles_gpu(scene)
        scene.cycles.samples = int(options.get("samples", 48))
        log(f"Cycles GPU: {resultat['gpu']} | samples {scene.cycles.samples}")
    else:
        log("engine: EEVEE")
    resultat["engine"] = scene.render.engine

    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = options["png"]
    bpy.ops.render.render(write_still=True)
    resultat["png"] = options["png"]
    resultat["png_mo"] = round(os.path.getsize(options["png"]) / 1e6, 1)
    log(f"render OK: {resultat['png_mo']} MB -> {options['png']}")


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1 :]
    with open(argv[0], "r", encoding="utf-8") as f:
        job = json.load(f)
    dossier = os.path.dirname(argv[0])
    resultat = {"ok": False}

    try:
        api_key = lire_cle_api(job.get("addon_module", "bl_ext.user_default.blenderkit"))
        if not api_key:
            raise RuntimeError(
                "no API key in the Blendkit addon preferences "
                "(open Blender in GUI, log in to Blendkit, then rerun)"
            )
        log(f"API key read ({len(api_key)} characters, masked)")
        chemin_blend = telecharger_blend(
            api_key, job["download"]["file_id"], job["download"]["cache"], job["download"].get("no_cache", False)
        )
        if job["mode"] == "prop":
            executer_mode_prop(job, chemin_blend, resultat)
        else:
            executer_mode_plate(job, chemin_blend, resultat)
        resultat["ok"] = True
    except Exception as e:  # noqa: BLE001 - the error is sent back to the workflow
        resultat["erreur"] = str(e)
        log(f"ERROR: {e}")

    with open(os.path.join(dossier, "resultat.json"), "w", encoding="utf-8") as f:
        json.dump(resultat, f, ensure_ascii=False, indent=1)
    return 0 if resultat["ok"] else 3


if __name__ == "__main__":
    sys.exit(main())
