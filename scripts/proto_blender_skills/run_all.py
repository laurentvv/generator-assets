"""Chasse aux workflows blender-skills — driver de la campagne de tests (2026-09-17).

Lance chaque prototype bpy dans Blender headless, collecte les marqueurs stdout,
encode le turntable en MP4 (ffmpeg) et assemble la planche de contact LODs (Pillow).
Les prototypes s'inspirent du pack blender-skills (arjun988, MIT) adaptés headless.

Usage : uv run python scripts/proto_blender_skills/run_all.py
"""

import json
import os
import shutil
import subprocess
import sys

RACINE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, RACINE)

from core.blender_ops import trouver_blender  # noqa: E402

OUT = os.path.join(RACINE, "output", "test_blender_skills")
SCRIPTS = os.path.join(RACINE, "scripts", "proto_blender_skills")
CASQUE = os.path.join(RACINE, "output", "trellis_smoke", "casque_512.glb")
BARIL = os.path.join(RACINE, "output", "blendkit", "wooden_barrel", "wooden_barrel.glb")
MARC = os.path.join(RACINE, "godot_assets", "marc_novice.glb")


def trouver_ffmpeg():
    for c in (shutil.which("ffmpeg"),
              r"C:\ffmpeg\dist\ffmpeg.exe", r"C:\ffmpeg\bin\ffmpeg.exe",
              r"C:\ffmpeg\ffmpeg.exe"):
        if c and os.path.exists(c):
            return c
    return None


TESTS = [
    ("audit_casque", "audit_scene.py", [CASQUE, os.path.join(OUT, "audit", "casque.json")], 300),
    ("audit_marc", "audit_scene.py", [MARC, os.path.join(OUT, "audit", "marc.json")], 300),
    ("turntable_casque", "turntable.py", [CASQUE, os.path.join(OUT, "turntable_casque"), "48", "800"], 900),
    ("lod_casque", "lod_chain.py", [CASQUE, os.path.join(OUT, "lod_casque"), "casque"], 600),
    ("collision_casque", "collision_proxy.py",
     [CASQUE, os.path.join(OUT, "collision", "casque_collision.glb"),
      os.path.join(OUT, "collision", "casque_collision_apercu.png")], 600),
    ("renommage_baril", "renommer_conventions.py",
     [BARIL, os.path.join(OUT, "renommage", "SM_Prop_Barrel_01.glb")], 300),
    ("scatter_barils", "scatter_props.py",
     [BARIL, os.path.join(OUT, "scatter_barils.png"), "40", "42", "0.5"], 600),
    ("beauty_casque", "beauty_render.py",
     [CASQUE, os.path.join(OUT, "beauty_casque.png"), "1200", "96"], 900),
    # --- vague 2 ---
    ("spritesheet3d_casque", "spritesheet3d.py",
     [CASQUE, os.path.join(OUT, "spritesheet3d_casque"), "512", "8"], 600),
    ("bake_ao_casque", "bake_ao.py",
     [CASQUE, os.path.join(OUT, "bake_ao", "T_Casque_AO.png"),
      os.path.join(OUT, "bake_ao", "casque_avec_ao.png")], 600),
    ("decoupe_baril", "decoupe_assets.py",
     [BARIL, os.path.join(OUT, "decoupe_baril")], 300),
    ("composite_beauty", "composite_beauty.py",
     [CASQUE, os.path.join(OUT, "beauty_casque_composite.png"), "1200"], 900),
    # --- vague 3 : styles & recettes matériaux (blender-skills anime/lowpoly/materials) ---
    # Leçon 2026-09-17 : blender headless sans blend sauvegardé AVALÉ les chemins
    # relatifs (rendus perdus sans erreur) → TOUJOURS chemins absolus via ce driver.
    ("style_toon", "styles_demo.py", [CASQUE, os.path.join(OUT, "style_toon.png"), "toon"], 300),
    ("style_psx", "styles_demo.py", [CASQUE, os.path.join(OUT, "style_psx.png"), "psx"], 300),
    ("style_wear", "styles_demo.py", [CASQUE, os.path.join(OUT, "style_wear.png"), "wear"], 300),
    ("style_rust", "styles_demo.py", [CASQUE, os.path.join(OUT, "style_rust.png"), "rust"], 300),
    ("style_moss", "styles_demo.py", [CASQUE, os.path.join(OUT, "style_moss.png"), "moss"], 300),
    ("style_water", "styles_demo.py", [CASQUE, os.path.join(OUT, "style_water.png"), "water"], 300),
    ("style_panel", "styles_demo.py", [CASQUE, os.path.join(OUT, "style_panel.png"), "panel"], 300),
    ("style_panel_baril", "styles_demo.py",
     [BARIL, os.path.join(OUT, "style_panel_baril.png"), "panel"], 300),
    ("cloth_sim", "cloth_sim.py", [os.path.join(OUT, "cloth_drap.png"), "40"], 600),
]


def lancer(blender, script, args, timeout):
    cmd = [blender, "--background", "--python", os.path.join(SCRIPTS, script), "--"] + args
    for dossier in {os.path.dirname(a) for a in args if a.endswith((".json", ".png", ".glb"))}:
        os.makedirs(dossier, exist_ok=True)
    try:
        proc = subprocess.run(cmd, cwd=RACINE, capture_output=True, text=True,
                              timeout=timeout, encoding="utf-8", errors="replace")
        marqueurs = [l for l in (proc.stdout or "").splitlines()
                     if any(m in l for m in ("_OK:", "_JSON:", "GPU indisponible"))]
        return proc.returncode == 0 and any("SUCCESS:" in l for l in (proc.stdout or "").splitlines()), marqueurs, proc
    except subprocess.TimeoutExpired:
        return False, [f"TIMEOUT après {timeout} s"], None


def encoder_turntable(dossier, fps=24):
    ffmpeg = trouver_ffmpeg()
    if not ffmpeg:
        return "ffmpeg introuvable, frames PNG conservées"
    sortie = os.path.join(dossier, "turntable.mp4")
    cmd = [ffmpeg, "-y", "-framerate", str(fps), "-i", os.path.join(dossier, "tt_%04d.png"),
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", sortie]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return sortie if proc.returncode == 0 else f"ffmpeg KO: {proc.stderr[-200:]}"


def atlas_spritesheet(dossier):
    """Assemble les sprites RGBA en atlas 4×2 + JSON de mapping (grille Godot)."""
    import glob
    import json as js
    from PIL import Image
    pngs = sorted(glob.glob(os.path.join(dossier, "sprite_*.png")))
    if not pngs:
        return "aucun sprite trouvé"
    with open(os.path.join(dossier, "spritesheet_infos.json"), encoding="utf-8") as f:
        infos = js.load(f)
    cols, lignes = 4, 2
    res = Image.open(pngs[0]).width
    atlas = Image.new("RGBA", (cols * res, lignes * res), (0, 0, 0, 0))
    for i, p in enumerate(pngs[:cols * lignes]):
        atlas.paste(Image.open(p), ((i % cols) * res, (i // cols) * res))
    sortie = os.path.join(dossier, "atlas_4x2.png")
    atlas.save(sortie)
    mapping = {f"case_{i}": {"angle_deg": infos["directions_deg"][i],
                             "x": (i % cols) * res, "y": (i // cols) * res}
               for i in range(min(len(pngs), cols * lignes))}
    with open(os.path.join(dossier, "atlas_mapping.json"), "w", encoding="utf-8") as f:
        js.dump(mapping, f, ensure_ascii=False, indent=2)
    return sortie


def planche_lods(dossier):
    from PIL import Image, ImageDraw
    vues = [os.path.join(dossier, f"vue_LOD{i}.png") for i in range(4)]
    with open(os.path.join(dossier, "lod_rapport.json"), encoding="utf-8") as f:
        rapport = json.load(f)
    images = [Image.open(v) for v in vues]
    marge, bandeau = 12, 44
    largeur = sum(im.width for im in images) + marge * 5
    hauteur = max(im.height for im in images) + bandeau + marge * 2
    planche = Image.new("RGB", (largeur, hauteur), (24, 24, 28))
    dessin = ImageDraw.Draw(planche)
    x = marge
    for i, (im, r) in enumerate(zip(images, rapport)):
        planche.paste(im, (x, bandeau + marge))
        dessin.text((x + 6, 12), f"LOD{r['lod']} — {r['triangles']:,} tris "
                    f"(x{r['ratio_cumulé']})", fill=(230, 230, 235))
        x += im.width + marge
    sortie = os.path.join(dossier, "planche_lods.png")
    planche.save(sortie)
    return sortie


def main():
    seuls = sys.argv[1:]
    blender = trouver_blender()
    if not blender:
        print("ERREUR: Blender introuvable (BLENDER_PATH / PATH / Program Files 4.0-5.2)")
        sys.exit(1)
    print(f"Blender : {blender}\nSorties : {OUT}\n")
    resultats = {}
    for nom, script, args, timeout in TESTS:
        if seuls and nom not in seuls:
            continue
        print(f"— {nom} ({script})…")
        ok, marqueurs, proc = lancer(blender, script, args, timeout)
        resultats[nom] = {"ok": ok, "marqueurs": marqueurs}
        for m in marqueurs:
            print(f"    {m[:250]}")
        if not ok and proc is not None:
            erreurs = [l for l in (proc.stderr or "").splitlines() if "Error" in l or "error" in l]
            print(f"    ECHEC (exit {proc.returncode}) — {erreurs[-3:] if erreurs else 'voir stderr'}")
    post = {}
    if resultats.get("turntable_casque", {}).get("ok"):
        post["turntable_mp4"] = str(encoder_turntable(os.path.join(OUT, "turntable_casque")))
        print(f"— turntable encodé : {post['turntable_mp4']}")
    if resultats.get("lod_casque", {}).get("ok"):
        try:
            post["planche_lods"] = str(planche_lods(os.path.join(OUT, "lod_casque")))
            print(f"— planche LODs : {post['planche_lods']}")
        except Exception as e:  # noqa: BLE001
            post["planche_lods"] = f"échec assemblage : {e}"
    if resultats.get("spritesheet3d_casque", {}).get("ok"):
        try:
            post["atlas_sprites"] = str(atlas_spritesheet(os.path.join(OUT, "spritesheet3d_casque")))
            print(f"— atlas sprites : {post['atlas_sprites']}")
        except Exception as e:  # noqa: BLE001
            post["atlas_sprites"] = f"échec assemblage : {e}"
    with open(os.path.join(OUT, "resume_campagne.json"), encoding="utf-8") as f:
        resume = json.load(f) if not seuls else {"tests": {}, "post": {}}
    resume["tests"].update(resultats)
    resume["post"].update(post)
    with open(os.path.join(OUT, "resume_campagne.json"), "w", encoding="utf-8") as f:
        json.dump(resume, f, ensure_ascii=False, indent=2)
    print("\n=== RÉSUMÉ ===")
    for nom, r in resultats.items():
        print(f"  {'✅' if r['ok'] else '❌'} {nom}")
    print(f"\nRésumé JSON : {os.path.join(OUT, 'resume_campagne.json')}")


if __name__ == "__main__":
    main()
