# -*- coding: utf-8 -*-
"""
install_asset_packs.py
Extrait et installe tous les packs d'assets MakeHuman / MPFB (.zip) depuis C:\\tmp\\a
dans le répertoire de données MPFB, puis reconstruit l'index et le catalogue de vêtements.
"""

import glob
import os
import shutil
import sys
import zipfile

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

SOURCE_DIR = r"C:\tmp\a"
TARGET_DATA_DIR = os.path.expandvars(r"%APPDATA%\Blender Foundation\Blender\5.2\mpfb\data\data")

def main():
    print("=" * 65)
    print(" 📦 EXTRACTION & INSTALLATION DES PACKS D'ASSETS MAKEHUMAN")
    print(f" 📂 Source : {SOURCE_DIR}")
    print(f" 📂 Cible  : {TARGET_DATA_DIR}")
    print("=" * 65)

    os.makedirs(TARGET_DATA_DIR, exist_ok=True)
    zip_files = glob.glob(os.path.join(SOURCE_DIR, "*.zip"))

    if not zip_files:
        print("❌ Aucun fichier .zip trouvé dans C:\\tmp\\a")
        return

    print(f"📦 {len(zip_files)} packs d'assets détectés.")
    
    total_extracted_files = 0
    for i, zpath in enumerate(zip_files, 1):
        zname = os.path.basename(zpath)
        try:
            with zipfile.ZipFile(zpath, "r") as zf:
                file_list = zf.namelist()
                print(f"[{i}/{len(zip_files)}] 📥 Extraction de '{zname}' ({len(file_list)} fichiers)...")
                zf.extractall(TARGET_DATA_DIR)
                total_extracted_files += len(file_list)
        except Exception as e:
            print(f"⚠️ Erreur lors de l'extraction de {zname}: {e}")

    print(f"\n🎉 Extraction terminée : {total_extracted_files} fichiers installés avec succès !")

    # Reconstruction du catalogue JSON bilingue
    print("\n🔍 Reconstruction du catalogue de vêtements enrichi (FR / EN)...")
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if racine not in sys.path:
        sys.path.insert(0, racine)
    from core.clothes_catalog import construire_catalogue_vetements
    cat = construire_catalogue_vetements()
    print(f"🎉 Nouveau total d'assets indexés dans le catalogue : {len(cat)} modèles de vêtements/chaussures/chapeaux !")

    # Actualisation des caches MPFB dans Blender
    print("\n🔄 Actualisation des listes d'assets MPFB dans Blender...")
    from core.blender_ops import trouver_blender
    blender_bin = trouver_blender()
    if blender_bin:
        script_mpfb = """
import bpy, importlib, sys
for m in sys.modules:
    if m.endswith('mpfb.services.assetservice'):
        svc = getattr(importlib.import_module(m), 'AssetService')
        svc.update_all_asset_lists()
        print('✅ Cache MPFB synchronisé dans Blender.')
"""
        import subprocess
        subprocess.run([blender_bin, "--background", "--python-expr", script_mpfb], capture_output=True, text=True, encoding="utf-8", errors="replace")

    print("=" * 65)
    print(" ✅ INSTALLATION ET INDEXATION COMPLÈTES !")
    print("=" * 65)

if __name__ == "__main__":
    main()
