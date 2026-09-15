"""Test Blendkit headless : telechargement CC0 + export GLB (NON valide, pas un workflow).

Execute DANS Blender en mode background :
  blender.exe --background --python scripts/proto_blendkit_test.py -- <out_dir> <search_json> <asset_index>

La cle API du compte connecte est lue depuis les preferences de l'addon Blendkit
et ne quitte jamais ce processus (jamais affichee, jamais ecrite sur disque).
"""

import bpy
import json
import os
import sys
import urllib.request

BLENDERKIT_API = "https://www.blenderkit.com/api/v1"
ADDON_MODULE = "bl_ext.user_default.blenderkit"


def log(message: str) -> None:
    print(f"[proto_blendkit] {message}", flush=True)


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1 :]
    out_dir = argv[0]
    search_json_path = argv[1]
    asset_index = int(argv[2])
    os.makedirs(out_dir, exist_ok=True)

    # 1) Cle API du compte connecte (lecture seule, jamais logguee)
    prefs = bpy.context.preferences.addons.get(ADDON_MODULE)
    api_key = getattr(prefs.preferences, "api_key", "") if prefs else ""
    if not api_key:
        log("ERREUR: aucune cle API dans les preferences de l'addon Blendkit (compte non connecte ?)")
        return 2
    log(f"cle API lue depuis les preferences ({len(api_key)} caracteres, masquee)")

    # 2) Choix de l'asset dans les resultats de recherche
    with open(search_json_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    asset = meta["results"][asset_index]
    log(f"asset cible: {asset['displayName']} (license={asset['license']}, baseId={asset['assetBaseId']})")

    blend_file = next((f_ for f_ in asset["files"] if f_["fileType"] == "blend"), None)
    if blend_file is None:
        log("ERREUR: aucun fichier .blend dans cet asset")
        return 2

    # 3) URL signée via l'endpoint authentifié (scene_uuid au format UUID requis)
    import uuid as uuid_mod

    req = urllib.request.Request(
        f"{BLENDERKIT_API}/downloads/{blend_file['id']}/?scene_uuid={uuid_mod.uuid4()}",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        dl = json.load(r)
    signed_url = dl.get("filePath")
    if not signed_url:
        log(f"ERREUR: pas de filePath dans la réponse ({str(dl)[:200]})")
        return 3
    log(f"URL signée obtenue ({dl.get('fileType')})")

    # 4) Téléchargement du .blend (URL signée, sans auth ; UA navigateur exigée par le CDN)
    blend_path = os.path.join(out_dir, "source.blend")
    if os.path.isfile(blend_path) and os.path.getsize(blend_path) > 0:
        log(f".blend déjà en cache: {blend_path}")
    else:
        log("téléchargement du .blend en cours...")
        req_file = urllib.request.Request(signed_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req_file, timeout=600) as r, open(blend_path, "wb") as f:
            f.write(r.read())
        log(f".blend téléchargé: {os.path.getsize(blend_path) / 1e6:.1f} Mo -> {blend_path}")

    # 5) Scene vide (prefs en memoire reinitialisees : la cle est deja lue)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    # 6) Append des objets du .blend source (materiaux et images suivent les objets)
    with bpy.data.libraries.load(blend_path, link=False) as (src, dst):
        dst.objects = src.objects
    imported = []
    for obj in dst.objects:
        if obj is not None:
            scene.collection.objects.link(obj)
            imported.append(obj)
    meshes = [o for o in imported if o.type == "MESH"]
    if not meshes:
        log("ERREUR: aucun maillage importe")
        return 4
    faces = sum(len(o.data.polygons) for o in meshes)
    mats = {m.name for o in meshes for m in o.data.materials if m}
    log(f"import OK: {len(imported)} objets, {len(meshes)} maillages, {faces} faces, materiaux={sorted(mats)}")

    # 7) Camera auto-framee sur l'englobant global (fit FOV 50mm avec marge)
    from mathutils import Vector

    pts = [o.matrix_world @ Vector(corner) for o in meshes for corner in o.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    center = (mn + mx) / 2
    radius = (mx - mn).length / 2
    import math

    half_fov = math.radians(40 / 2)  # lentille 50mm, capteur 36mm -> ~40 deg horizontal
    distance = radius / math.sin(half_fov) * 1.25
    direction = Vector((1.0, -1.0, 0.7)).normalized()
    cam_data = bpy.data.cameras.new("Cam")
    cam_obj = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam_obj)
    cam_obj.location = center + direction * distance
    look = (center - cam_obj.location).to_track_quat("-Z", "Y")
    cam_obj.rotation_euler = look.to_euler()
    cam_data.clip_end = 1000.0
    scene.camera = cam_obj

    # Fond neutre gris pour le preview
    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.35, 0.35, 0.35, 1)
    scene.world = world

    # 8) Rendu de controle Workbench (textures visibles, pas besoin de lumieres)
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "TEXTURE"
    scene.render.resolution_x = 800
    scene.render.resolution_y = 800
    scene.render.filepath = os.path.join(out_dir, "apercu_workbench.png")
    bpy.ops.render.render(write_still=True)
    log("rendu de controle Workbench OK")

    # 9) Export GLB (toute la scene)
    glb_path = os.path.join(out_dir, "asset.glb")
    bpy.ops.export_scene.gltf(filepath=glb_path, export_format="GLB")
    log(f"export GLB: {os.path.getsize(glb_path) / 1e6:.1f} Mo -> {glb_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
