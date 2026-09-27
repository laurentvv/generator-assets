# -*- coding: utf-8 -*-
"""
install_asset_packs.py
Extracts and installs all the MakeHuman / MPFB asset packs (.zip) from C:\\tmp\\a
into the MPFB data directory, then rebuilds the index and the clothing catalogue.
"""

import glob
import os
import sys
import zipfile

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

SOURCE_DIR = r"C:\tmp\a"
TARGET_DATA_DIR = os.path.expandvars(r"%APPDATA%\Blender Foundation\Blender\5.2\mpfb\data\data")

def main():
    print("=" * 65)
    print(" 📦 EXTRACTION & INSTALLATION OF THE MAKEHUMAN ASSET PACKS")
    print(f" 📂 Source: {SOURCE_DIR}")
    print(f" 📂 Target : {TARGET_DATA_DIR}")
    print("=" * 65)

    os.makedirs(TARGET_DATA_DIR, exist_ok=True)
    zip_files = glob.glob(os.path.join(SOURCE_DIR, "*.zip"))

    if not zip_files:
        print("❌ No .zip file found in C:\\tmp\\a")
        return

    print(f"📦 {len(zip_files)} asset packs detected.")

    total_extracted_files = 0
    for i, zpath in enumerate(zip_files, 1):
        zname = os.path.basename(zpath)
        try:
            with zipfile.ZipFile(zpath, "r") as zf:
                file_list = zf.namelist()
                print(f"[{i}/{len(zip_files)}] 📥 Extracting '{zname}' ({len(file_list)} files)...")
                zf.extractall(TARGET_DATA_DIR)
                total_extracted_files += len(file_list)
        except Exception as e:
            print(f"⚠️ Error while extracting {zname}: {e}")

    print(f"\n🎉 Extraction finished: {total_extracted_files} files installed successfully!")

    # Rebuild of the bilingual JSON catalogue
    print("\n🔍 Rebuilding the enriched clothing catalogue (FR / EN)...")
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if racine not in sys.path:
        sys.path.insert(0, racine)
    from core.clothes_catalog import construire_catalogue_vetements
    cat = construire_catalogue_vetements()
    print(f"🎉 New total of indexed assets in the catalogue: {len(cat)} clothing/shoe/hat items!")

    # Refreshing the MPFB caches in Blender
    print("\n🔄 Refreshing the MPFB asset lists in Blender...")
    from core.blender_ops import trouver_blender
    blender_bin = trouver_blender()
    if blender_bin:
        script_mpfb = """
import bpy, importlib, sys
for m in sys.modules:
    if m.endswith('mpfb.services.assetservice'):
        svc = getattr(importlib.import_module(m), 'AssetService')
        svc.update_all_asset_lists()
        print('✅ MPFB cache synchronized in Blender.')
"""
        import subprocess
        subprocess.run([blender_bin, "--background", "--python-expr", script_mpfb], capture_output=True, text=True, encoding="utf-8", errors="replace")

    print("=" * 65)
    print(" ✅ INSTALLATION AND INDEXING COMPLETE!")
    print("=" * 65)

if __name__ == "__main__":
    main()
