# -*- coding: utf-8 -*-
"""
register_peasant_pack.py
1. Copie tous les pack JSONs dans MPFB data/packs et data/data/packs.
2. Crée les assets officiels MakeHuman de vêtements de paysan médiéval :
   - paysan_medieval_worksuit (.mhclo, .obj, .mhmat, .thumb, _diffuse.png, _normal.png)
   - paysan_medieval_shoes (.mhclo, .obj, .mhmat, .thumb, _diffuse.png, _normal.png)
3. Les enregistre dans generator_assets.json pour affichage 1-clic avec vignettes dans Blender MPFB.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from PIL import Image

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

MPFB_DATA_DIR = os.path.expandvars(r"%APPDATA%\Blender Foundation\Blender\5.2\mpfb\data")
PACKS_DIR_1 = os.path.join(MPFB_DATA_DIR, "packs")
PACKS_DIR_2 = os.path.join(MPFB_DATA_DIR, "data", "packs")
CLOTHES_DIR = os.path.join(MPFB_DATA_DIR, "data", "clothes")

SRC_WS_DIFF = r"C:\GIT\generator-assets\godot_assets\textures\marc_novice\marc_peasant_worksuit_diffuse.png"
SRC_WS_NORM = r"C:\GIT\generator-assets\godot_assets\textures\marc_novice\marc_peasant_worksuit_normal.png"
SRC_SH_DIFF = r"C:\GIT\generator-assets\godot_assets\textures\marc_novice\marc_peasant_shoes_diffuse.png"
SRC_SH_NORM = r"C:\GIT\generator-assets\godot_assets\textures\marc_novice\marc_peasant_shoes_normal.png"

SYS_WS_DIR = os.path.join(MPFB_DATA_DIR, "data", "clothes", "male_worksuit01")
SYS_SH_DIR = os.path.join(MPFB_DATA_DIR, "data", "clothes", "shoes01")

def main():
    print("=" * 65)
    print(" 👗 INSTALLATION DE LA TENUE DE PAYSAN MÉDIÉVAL DANS MPFB")
    print("=" * 65)

    os.makedirs(PACKS_DIR_1, exist_ok=True)
    os.makedirs(PACKS_DIR_2, exist_ok=True)

    # 1. Synchroniser tous les packs JSON entre les dossiers packs
    for json_file in Path(PACKS_DIR_2).glob("*.json"):
        shutil.copyfile(str(json_file), os.path.join(PACKS_DIR_1, json_file.name))
    for json_file in Path(PACKS_DIR_1).glob("*.json"):
        shutil.copyfile(str(json_file), os.path.join(PACKS_DIR_2, json_file.name))
    print(f"✅ Packs JSON synchronisés dans : {PACKS_DIR_1} et {PACKS_DIR_2}")

    # 2. Créer l'asset 'paysan_medieval_worksuit'
    ws_dest_dir = os.path.join(CLOTHES_DIR, "paysan_medieval_worksuit")
    os.makedirs(ws_dest_dir, exist_ok=True)

    # Copie du maillage 3D propre et du .mhclo
    shutil.copyfile(os.path.join(SYS_WS_DIR, "male_worksuit01.obj"), os.path.join(ws_dest_dir, "paysan_medieval_worksuit.obj"))
    
    # Adapter le fichier .mhclo
    with open(os.path.join(SYS_WS_DIR, "male_worksuit01.mhclo"), "r", encoding="utf-8") as f:
        mhclo_content = f.read()
    mhclo_content = mhclo_content.replace("male_worksuit01.obj", "paysan_medieval_worksuit.obj")
    mhclo_content = mhclo_content.replace("male_worksuit01.mhmat", "paysan_medieval_worksuit.mhmat")
    mhclo_content = mhclo_content.replace("name male_worksuit01", "name paysan_medieval_worksuit")
    with open(os.path.join(ws_dest_dir, "paysan_medieval_worksuit.mhclo"), "w", encoding="utf-8") as f:
        f.write(mhclo_content)

    # Textures UV
    shutil.copyfile(SRC_WS_DIFF, os.path.join(ws_dest_dir, "paysan_medieval_worksuit_diffuse.png"))
    shutil.copyfile(SRC_WS_NORM, os.path.join(ws_dest_dir, "paysan_medieval_worksuit_normal.png"))

    # Fichier .mhmat
    mhmat_ws = """# Material Paysan Medieval Worksuit
name paysan_medieval_worksuit
tag MakeHuman(TM)
ambientColor 1.0 1.0 1.0
diffuseColor 1.0 1.0 1.0
specularColor 0.05 0.05 0.05
shininess 0.15
opacity 1.0
transparent False
castShadows True
receiveShadows True
diffuseTexture paysan_medieval_worksuit_diffuse.png
normalmapTexture paysan_medieval_worksuit_normal.png
normalmapIntensity 1.0
shader shaders/glsl/litsphere
shaderConfig ambientOcclusion True
shaderConfig normal True
shaderConfig bump False
shaderConfig spec True
shaderConfig diffuse True
"""
    with open(os.path.join(ws_dest_dir, "paysan_medieval_worksuit.mhmat"), "w", encoding="utf-8") as f:
        f.write(mhmat_ws)

    # Vignette .thumb (128x128)
    thumb_ws = Image.open(SRC_WS_DIFF).resize((128, 128), Image.Resampling.LANCZOS)
    thumb_ws.save(os.path.join(ws_dest_dir, "paysan_medieval_worksuit.thumb"), format="PNG")
    print("✅ Asset 'paysan_medieval_worksuit' créé avec succès !")

    # 3. Créer l'asset 'paysan_medieval_shoes'
    sh_dest_dir = os.path.join(CLOTHES_DIR, "paysan_medieval_shoes")
    os.makedirs(sh_dest_dir, exist_ok=True)

    shutil.copyfile(os.path.join(SYS_SH_DIR, "shoes01.obj"), os.path.join(sh_dest_dir, "paysan_medieval_shoes.obj"))
    
    with open(os.path.join(SYS_SH_DIR, "shoes01.mhclo"), "r", encoding="utf-8") as f:
        mhclo_sh = f.read()
    mhclo_sh = mhclo_sh.replace("shoes01.obj", "paysan_medieval_shoes.obj")
    mhclo_sh = mhclo_sh.replace("shoes01.mhmat", "paysan_medieval_shoes.mhmat")
    mhclo_sh = mhclo_sh.replace("name shoes01", "name paysan_medieval_shoes")
    with open(os.path.join(sh_dest_dir, "paysan_medieval_shoes.mhclo"), "w", encoding="utf-8") as f:
        f.write(mhclo_sh)

    shutil.copyfile(SRC_SH_DIFF, os.path.join(sh_dest_dir, "paysan_medieval_shoes_diffuse.png"))
    shutil.copyfile(SRC_SH_NORM, os.path.join(sh_dest_dir, "paysan_medieval_shoes_normal.png"))

    mhmat_sh = """# Material Paysan Medieval Shoes
name paysan_medieval_shoes
tag MakeHuman(TM)
ambientColor 1.0 1.0 1.0
diffuseColor 1.0 1.0 1.0
specularColor 0.1 0.1 0.1
shininess 0.25
opacity 1.0
transparent False
castShadows True
receiveShadows True
diffuseTexture paysan_medieval_shoes_diffuse.png
normalmapTexture paysan_medieval_shoes_normal.png
normalmapIntensity 1.0
shader shaders/glsl/litsphere
shaderConfig ambientOcclusion True
shaderConfig normal True
shaderConfig bump False
shaderConfig spec True
shaderConfig diffuse True
"""
    with open(os.path.join(sh_dest_dir, "paysan_medieval_shoes.mhmat"), "w", encoding="utf-8") as f:
        f.write(mhmat_sh)

    thumb_sh = Image.open(SRC_SH_DIFF).resize((128, 128), Image.Resampling.LANCZOS)
    thumb_sh.save(os.path.join(sh_dest_dir, "paysan_medieval_shoes.thumb"), format="PNG")
    print("✅ Asset 'paysan_medieval_shoes' créé avec succès !")

    # 4. Enregistrer dans generator_assets.json
    for pack_dir in [PACKS_DIR_1, PACKS_DIR_2]:
        pfile = os.path.join(pack_dir, "generator_assets.json")
        pdata = {}
        if os.path.exists(pfile):
            try:
                with open(pfile, "r", encoding="utf-8") as f:
                    pdata = json.load(f)
            except Exception:
                pdata = {}
        
        pdata["paysan_medieval_worksuit"] = {
            "author": "Generator Assets AI",
            "category": "Clothes",
            "changed": "2026-08-27",
            "created": "2026-08-27",
            "description": "Tunique et Salopette de paysan medieval en toile de jute rustique",
            "license": "CC0",
            "original_author": "MakeHuman Community",
            "original_source": "http://www.makehumancommunity.org",
            "source": "Generator-Assets",
            "thumbnail": "paysan_medieval_worksuit.thumb",
            "type": "clothes"
        }
        pdata["paysan_medieval_shoes"] = {
            "author": "Generator Assets AI",
            "category": "Clothes",
            "changed": "2026-08-27",
            "created": "2026-08-27",
            "description": "Chaussures medievales en cuir vieilli et patine",
            "license": "CC0",
            "original_author": "MakeHuman Community",
            "original_source": "http://www.makehumancommunity.org",
            "source": "Generator-Assets",
            "thumbnail": "paysan_medieval_shoes.thumb",
            "type": "clothes"
        }
        with open(pfile, "w", encoding="utf-8") as f:
            json.dump(pdata, f, indent=4, ensure_ascii=False)

    # 5. Mettre à jour le catalogue local
    print("\n🔍 Actualisation du catalogue de vêtements...")
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if racine not in sys.path:
        sys.path.insert(0, racine)
    from core.clothes_catalog import construire_catalogue_vetements
    cat = construire_catalogue_vetements()
    print(f"🎉 Nouveau total d'assets indexés : {len(cat)} modèles !")

    # 6. Actualiser le cache MPFB dans Blender
    from core.blender_ops import trouver_blender
    bbin = trouver_blender()
    if bbin:
        cmd = [bbin, "--background", "--python-expr", "import bpy, importlib, sys; [(importlib.import_module(m).AssetService.update_all_asset_lists(), print('✅ MPFB synchronisé')) for m in sys.modules if m.endswith('mpfb.services.assetservice')]"]
        subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")

    print("=" * 65)
    print(" 🎉 TOUS LES VÊTEMENTS SONT DISPONIBLES DANS BLENDER MPFB !")
    print("=" * 65)

if __name__ == "__main__":
    main()
