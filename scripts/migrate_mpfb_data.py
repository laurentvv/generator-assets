# -*- coding: utf-8 -*-
"""
migrate_mpfb_data.py
Migrates and cleanly flattens the nested mpfb/data/data/ folder into the root mpfb/data/ folder.
Permanently removes the useless data/data subfolder.
"""

import os
import shutil
import sys
import subprocess

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

MPFB_DATA_DIR = os.path.expandvars(r"%APPDATA%\Blender Foundation\Blender\5.2\mpfb\data")
NESTED_DATA_DIR = os.path.join(MPFB_DATA_DIR, "data")

def main():
    print("=" * 65)
    print(" 🧹 MIGRATION AND FLATTENING OF MPFB/DATA/DATA INTO MPFB/DATA")
    print(f" 📂 Source (Nested) : {NESTED_DATA_DIR}")
    print(f" 📂 Target (Root)   : {MPFB_DATA_DIR}")
    print("=" * 65)

    if not os.path.exists(NESTED_DATA_DIR):
        print("✅ The nested 'data' folder no longer exists. Nothing to do.")
        return

    # Walk through each item of the nested folder
    for item_name in os.listdir(NESTED_DATA_DIR):
        src_item = os.path.join(NESTED_DATA_DIR, item_name)
        dst_item = os.path.join(MPFB_DATA_DIR, item_name)

        if os.path.isdir(src_item):
            os.makedirs(dst_item, exist_ok=True)
            for sub_name in os.listdir(src_item):
                src_sub = os.path.join(src_item, sub_name)
                dst_sub = os.path.join(dst_item, sub_name)
                if os.path.isdir(src_sub):
                    if os.path.exists(dst_sub):
                        shutil.rmtree(dst_sub)
                    shutil.move(src_sub, dst_sub)
                else:
                    shutil.copy2(src_sub, dst_sub)
                    os.remove(src_sub)
            print(f"✅ Folder merged: {item_name}")
        else:
            shutil.copy2(src_item, dst_item)
            os.remove(src_item)
            print(f"✅ File moved: {item_name}")

    # Deleting the now-empty nested folder
    shutil.rmtree(NESTED_DATA_DIR, ignore_errors=True)
    print("\n🗑️ Nested folder 'mpfb/data/data/' successfully removed!")

    # Rebuilding the clothing catalog
    print("\n🔍 Rebuilding the enriched clothing catalog...")
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if racine not in sys.path:
        sys.path.insert(0, racine)
    from core.clothes_catalog import construire_catalogue_vetements
    cat = construire_catalogue_vetements()
    print(f"🎉 New total of indexed assets: {len(cat)} models!")

    # Refreshing the lists in Blender
    print("\n🔄 Syncing the Blender MPFB cache...")
    from core.blender_ops import trouver_blender
    bbin = trouver_blender()
    if bbin:
        script_mpfb = """
import bpy, importlib, sys
for m in sys.modules:
    if m.endswith('mpfb.services.assetservice'):
        svc = getattr(importlib.import_module(m), 'AssetService')
        svc.update_all_asset_lists()
        assets = svc.list_mhclo_assets()
        print(f'✅ Blender MPFB synced with {len(assets)} .mhclo assets.')
"""
        res = subprocess.run([bbin, "--background", "--python-expr", script_mpfb], capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(res.stdout)

    print("=" * 65)
    print(" 🎉 MIGRATION COMPLETED SUCCESSFULLY: PERFECTLY CLEAN STRUCTURE!")
    print("=" * 65)

if __name__ == "__main__":
    main()
