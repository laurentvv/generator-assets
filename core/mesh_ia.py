#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 3D objects from an image: TRELLIS.2-4B GGUF via trellis.cpp (Vulkan backend).

Validated by the user on 2026-09-06 on the repo helmet:
res 512 = 10 min 44 s (144 k faces GLB, 1024 atlas), res 1024 = 55 min 10 s
(293 k faces GLB, 2048 atlas). Tool installed in C:\\trellis (dedicated README),
f16 GGUF in C:\\Modeles_LLM\\trellis2-gguf (see MEMORY_BANK §1.14).

Pipeline: PNG image (background-removed ideally — alpha is kept by trellis)
→ trellis-cli → PBR GLB (+ .ply + _base.png atlas) → Blender control renders
(4 studio orbital views) → 2×3 recap board.
"""

import os
import tempfile
import time
from string import Template
from typing import Any, Dict, List, Optional, Tuple

from core.config import DEFAULT_MODEL_DIR
from core.process import EngineError, run_engine

TRELLIS_CLI = os.getenv("TRELLIS_CLI_PATH", r"C:\trellis\trellis-cli.exe")
TRELLIS_MODELES_DIR = os.getenv("TRELLIS_MODELES_DIR", os.path.join(DEFAULT_MODEL_DIR, "trellis2-gguf"))
TRELLIS_GGUF_REQUIS = [
    "ss_flow.gguf", "ss_dec.gguf",
    "shape_flow_512.gguf", "shape_flow_1024.gguf", "shape_dec.gguf",
    "tex_flow_512.gguf", "tex_flow_1024.gguf", "tex_dec.gguf",
    "dinov3.gguf", "birefnet.gguf",
]

# Pixal3D backend (TRELLIS.2 fine-tune, same engine + shared decoders):
# 5 dedicated GGUFs in the SAME models dir — vegax87/Pixal3D (11.0 GB total).
PIXAL3D_GGUF_REQUIS = [
    "pixal3d_ss_flow.gguf", "pixal3d_shape_flow_512.gguf",
    "pixal3d_shape_flow_1024.gguf", "pixal3d_tex_flow_1024.gguf",
    "pixal3d_naf.gguf",
]

# Realistic RX 6950 XT budget (RDNA2, no Vulkan matrix cores) for user help.
DUREES_ESTIMEES = {512: "~11 min", 1024: "~55 min", 1536: "~2 h (not measured)"}


def verifier_trellis(moteur: str = "trellis") -> Tuple[bool, List[str]]:
    """Checks trellis-cli.exe and the required GGUFs. Returns (ok, missing).

    `moteur="pixal3d"` additionally requires the 5 Pixal3D flow GGUFs.
    """
    manquants: List[str] = []
    if not os.path.exists(TRELLIS_CLI):
        manquants.append(f"trellis-cli not found: {TRELLIS_CLI}")
    for f in TRELLIS_GGUF_REQUIS:
        if not os.path.exists(os.path.join(TRELLIS_MODELES_DIR, f)):
            manquants.append(os.path.join(TRELLIS_MODELES_DIR, f))
    if moteur == "pixal3d":
        for f in PIXAL3D_GGUF_REQUIS:
            if not os.path.exists(os.path.join(TRELLIS_MODELES_DIR, f)):
                manquants.append(os.path.join(TRELLIS_MODELES_DIR, f))
    return (not manquants), manquants


def generer_mesh_trellis(
    image_path: str,
    output_dir: str,
    nom_base: str,
    res: int = 512,
    seed: Optional[int] = None,
    texture: bool = True,
    gpu: int = 0,
    moteur: str = "trellis",
    fov: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Runs trellis-cli (Vulkan): image → PBR GLB + .ply + _base.png atlas preview.

    `res`: 512 (iteration, ~11 min) or 1024 (master, ~55 min) or 1536 (not measured).
    `seed`: None/-
    → automatic trellis seed. Progress is displayed live (steps 1/6 → 6/7).
    `moteur`: "trellis" (TRELLIS.2, default) | "pixal3d" — TRELLIS.2 fine-tune
    with pixel-aligned projection conditioning: flat/saturated colors and crisp
    lettering in ONE pass (no separate repaint stage). USER VALIDATED 2026-10-02
    ("super") on the repo helmet, 512 = ~14 min (+32 % vs TRELLIS.2 — the NAF
    upsampler runs 20 forwards per flow step instead of 12). MEMORY_BANK §1.14.
    `fov`: horizontal field of view in degrees — Pixal3D only (MoGe-2 camera
    estimation is not ported; default None → the engine's 49.13° upstream
    default). A wrong FOV shows as silhouette drift/thickness, not a crash.
    """
    ok, manquants = verifier_trellis(moteur=moteur)
    if not ok:
        raise EnvironmentError(
            "Missing TRELLIS.2 components: " + " ; ".join(manquants)
            + " — see C:\\trellis\\README.md (install) and MEMORY_BANK §1.14."
        )

    glb_path = os.path.join(output_dir, f"{nom_base}_{res}.glb")
    commande = [
        TRELLIS_CLI,
        "-i", image_path,
        "-o", glb_path,
        "--models", TRELLIS_MODELES_DIR,
        "--res", str(res),
    ]
    if moteur == "pixal3d":
        commande += ["--model", "pixal3d"]
    if fov is not None:
        commande += ["--fov", str(float(fov))]
    if seed is not None and seed >= 0:
        commande += ["-s", str(seed)]
    if not texture:
        commande.append("--no-texture")
    commande += ["--gpu", str(gpu)]

    t0 = time.time()
    # Uncaptured output: trellis displays its progress bar live.
    # 7200 s: measured marks 512 = ~11 min, 1024 = ~55 min (MEMORY_BANK), ×2 margin
    run_engine(commande, capture=False, check=True, timeout=7200, etiquette="trellis-cli")
    duree = time.time() - t0

    if not os.path.exists(glb_path):
        raise RuntimeError(f"trellis-cli did not produce {glb_path}")

    retour: Dict[str, Any] = {"glb": glb_path, "res": res, "duree_s": duree, "seed": seed}
    ply = os.path.splitext(glb_path)[0] + ".ply"
    base = os.path.splitext(glb_path)[0] + "_base.png"
    if os.path.exists(ply):
        retour["ply"] = ply
    if os.path.exists(base):
        retour["base_png"] = base
    return retour


# Blender control-render script (4 orbital views + studio lighting, EEVEE).
# $entree / $prefixe substitution via string.Template (the script contains f-strings).
_SCRIPT_RENDU = Template(r'''import math
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
glb_in, out_prefix = argv[0], argv[1]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb_in)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
assert meshes, "no mesh in the GLB"

bpy.ops.object.select_all(action="DESELECT")
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
bpy.ops.object.origin_set(type="ORIGIN_CENTER_OF_MASS", center="BOUNDS")


def bbox_monde():
    pts = []
    for o in meshes:
        for c in o.bound_box:
            pts.append(o.matrix_world @ Vector(c))
    return pts


# Normalization: max dimension brought to 2.0, base set at z=0.
pts = bbox_monde()
max_dim = max(max(p.x for p in pts) - min(p.x for p in pts),
              max(p.y for p in pts) - min(p.y for p in pts),
              max(p.z for p in pts) - min(p.z for p in pts))
scale = 2.0 / max(max_dim, 1e-9)
for o in meshes:
    o.scale = (o.scale.x * scale, o.scale.y * scale, o.scale.z * scale)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
pts = bbox_monde()
min_z = min(p.z for p in pts)
for o in meshes:
    o.location.z -= min_z
bpy.context.view_layer.update()

cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 50
cam = bpy.data.objects.new("Cam", cam_data)
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam


def area_light(nom, energie, taille, loc):
    ld = bpy.data.lights.new(nom, type="AREA")
    ld.energy = energie
    ld.size = taille
    lo = bpy.data.objects.new(nom, ld)
    lo.location = loc
    bpy.context.scene.collection.objects.link(lo)
    return lo


key = area_light("Cle", 400, 3, (3.5, -3.5, 3.5))
fill = area_light("Contre", 150, 4, (-4, -1, 2))
rim = area_light("Fond", 250, 3, (0, 5, 4))
for lo in (key, fill, rim):
    d = Vector((0, 0, 1)) - lo.location
    lo.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

monde = bpy.data.worlds.new("Monde")
monde.use_nodes = True
bg = monde.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.32, 0.33, 0.36, 1.0)
bg.inputs[1].default_value = 0.8
bpy.context.scene.world = monde

scn = bpy.context.scene
for moteur in ("BLENDER_EEVEE_NEXT_RENDER", "BLENDER_EEVEE_RENDER", "BLENDER_EEVEE"):
    try:
        scn.render.engine = moteur
        break
    except TypeError:
        continue
try:
    scn.eevee.taa_render_samples = 48
except AttributeError:
    pass
scn.render.resolution_x = 900
scn.render.resolution_y = 900

rayon, elev = 4.0, math.radians(20)
for i, az in enumerate((25, 115, 205, 295)):
    a = math.radians(az)
    cam.location = (rayon * math.cos(a) * math.cos(elev),
                    rayon * math.sin(a) * math.cos(elev),
                    rayon * math.sin(elev) + 1.0)
    d = Vector((0, 0, 1.0)) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    scn.render.filepath = f"{out_prefix}_vue{i}.png"
    bpy.ops.render.render(write_still=True)
    print(f"[rendu] vue {i} (azimut {az} deg) -> {scn.render.filepath}")
print("[rendu] TERMINE")
''')


# Blender mesh reduction script (UV/SHARP delimited Decimate collapse,
# PBR materials kept) then GLB re-export.
_SCRIPT_REDUCTION = Template(r'''import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
glb_in, glb_out, faces_cible = argv[0], argv[1], int(argv[2])

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb_in)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
assert meshes, "no mesh in the GLB"
total_avant = sum(len(m.data.polygons) for m in meshes)
print(f"[reduction] faces before: {total_avant}")

if faces_cible > 0 and total_avant > faces_cible:
    ratio = max(faces_cible / total_avant, 0.01)
    for o in meshes:
        mod = o.modifiers.new("Decimate", type="DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.ratio = ratio
        mod.delimit = {"SHARP", "UV"}
    for o in meshes:
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.modifier_apply(modifier="Decimate")
    total_apres = sum(len(m.data.polygons) for m in meshes)
    print(f"[reduction] faces after: {total_apres} (target {faces_cible}, ratio {ratio:.4f})")
else:
    print("[reduction] already below target, no decimation")

bpy.ops.object.select_all(action="DESELECT")
for o in meshes:
    o.select_set(True)
bpy.ops.export_scene.gltf(filepath=glb_out, export_format="GLB", use_selection=True)
print("[reduction] export OK -> " + glb_out)
''')


def reduire_mesh_blender(glb_path: str, glb_sortie: str, faces_cible: int) -> Optional[Dict[str, Any]]:
    """
    Decimates a GLB toward ~faces_cible faces (Blender headless, UV/SHARP delimited
    Decimate collapse, PBR textures kept) and re-exports as a separate GLB.

    Returns {"glb": ..., "faces_avant": N, "faces_apres": N} or None on failure
    (non-blocking: the master GLB remains usable).
    """
    from core.blender_ops import trouver_blender

    blender = trouver_blender()
    if not blender:
        print("⚠️ Blender not found: mesh reduction skipped.")
        return None

    # Unique temp script (tempfile): no more _reduction.py written into the
    # output folder (collision between parallel runs + pollution).
    descripteur, script = tempfile.mkstemp(suffix=".py", prefix="ga_reduction_")
    os.close(descripteur)
    with open(script, "w", encoding="utf-8") as f:
        f.write(_SCRIPT_REDUCTION.substitute())

    try:
        proc = run_engine(
            [blender, "--background", "--python", script, "--", glb_path, glb_sortie, str(int(faces_cible))],
            check=False, timeout=600, etiquette="blender reduction",
        )
    except EngineError:
        print("⚠️ Blender reduction timed out (10 min): skipped.")
        return None
    finally:
        if os.path.exists(script):
            try:
                os.remove(script)
            except OSError:
                pass

    if not os.path.exists(glb_sortie):
        print(f"⚠️ Blender reduction failed: {(proc.stderr or '')[-500:]}")
        return None

    import re as _re
    m_avant = _re.search(r"faces before: (\d+)", proc.stdout or "")
    m_apres = _re.search(r"faces after: (\d+)", proc.stdout or "")
    return {
        "glb": glb_sortie,
        "faces_avant": int(m_avant.group(1)) if m_avant else None,
        "faces_apres": int(m_apres.group(1)) if m_apres else None,
    }


def rendre_controle_blender(glb_path: str, output_dir: str, nom_base: str) -> List[str]:
    """
    Renders 4 orbital views of the GLB (Blender headless EEVEE). Returns the PNGs
    produced (empty list if Blender is unavailable or the render failed — non-blocking).
    """
    from core.blender_ops import trouver_blender

    blender = trouver_blender()
    if not blender:
        print("⚠️ Blender not found: control renders skipped.")
        return []

    script = os.path.join(output_dir, "_rendu_controle.py")
    with open(script, "w", encoding="utf-8") as f:
        f.write(_SCRIPT_RENDU.substitute(entree=glb_path, prefixe=os.path.join(output_dir, nom_base)))

    prefixe = os.path.join(output_dir, nom_base)
    try:
        proc = run_engine(
            [blender, "--background", "--python", script, "--", glb_path, prefixe],
            check=False, timeout=600, etiquette="blender control renders",
        )
    except EngineError:
        print("⚠️ Blender control render timed out (10 min): skipped.")
        return []

    vues: List[str] = []
    for i in range(4):
        p = f"{prefixe}_vue{i}.png"
        if os.path.exists(p):
            vues.append(p)
    if len(vues) < 4:
        print(f"⚠️ Incomplete Blender renders ({len(vues)}/4): {proc.stderr[-500:] if proc.stderr else ''}")
    return vues


def assembler_planche(
    source_png: str,
    vues: List[str],
    base_png: Optional[str],
    sortie: str,
    taille: int = 900,
) -> str:
    """2×3 recap board: source, 4 views, atlas texture."""
    from PIL import Image, ImageDraw, ImageFont

    def charge(p: str) -> "Image.Image":
        im = Image.open(p).convert("RGB")
        im.thumbnail((taille, taille))
        fond = Image.new("RGB", (taille, taille), (24, 24, 28))
        fond.paste(im, ((taille - im.width) // 2, (taille - im.height) // 2))
        return fond

    panneaux_haut = [charge(source_png)] + [charge(v) for v in vues[:2]]
    panneaux_bas = [charge(v) for v in vues[2:4]]
    panneaux_bas.append(charge(base_png) if base_png and os.path.exists(base_png)
                        else Image.new("RGB", (taille, taille), (24, 24, 28)))

    titres_haut = ["Source (2D input)", "Azimuth view 25 deg", "Azimuth view 115 deg"]
    titres_bas = ["Azimuth view 205 deg", "Azimuth view 295 deg",
                  "PBR base texture" if base_png and os.path.exists(base_png) else "(no texture)"]

    marge, barre = 12, 56
    planche = Image.new("RGB", (3 * taille + 4 * marge, 2 * (taille + barre) + 3 * marge), (16, 16, 20))
    draw = ImageDraw.Draw(planche)
    try:
        fonte = ImageFont.truetype("C:/Windows/Fonts/seguisb.ttf", 30)
    except OSError:
        fonte = ImageFont.load_default()
    for ligne, (panneaux, titres) in enumerate(((panneaux_haut, titres_haut), (panneaux_bas, titres_bas))):
        for col in range(3):
            x = marge + col * (taille + marge)
            y = marge + ligne * (taille + barre + marge)
            planche.paste(panneaux[col], (x, y))
            draw.text((x + 10, y + taille + 10), titres[col], fill=(230, 230, 235), font=fonte)
    planche.save(sortie)
    return sortie
