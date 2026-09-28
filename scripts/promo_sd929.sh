#!/usr/bin/env bash
# promo_sd929.sh — promote sd-cli master-929-3f8527a to production C:\SD (backup first).
# Run ONLY after the matrix verdict is green (Flux OK, LTX identical machine-state failure
# documented, Wan 929 within ±15 % of the 09/24 fresh-boot reference).
set -eu

SRC=/c/SD-929
DST=/c/SD
BK="$DST/backups/backup_20260928_master929"

echo "1) backup current production (master-908)"
mkdir -p "$BK"
cp -p "$DST"/sd-cli.exe "$DST"/sd-server.exe "$DST"/*.dll "$DST"/*.txt "$BK/" 2>/dev/null
[ -f "$DST"/sd-master-88411ef-bin-win-vulkan-x64.zip ] && \
  mv "$DST"/sd-master-88411ef-bin-win-vulkan-x64.zip "$BK/"
ls "$BK" | head -20

echo "2) copy master-929 binaries over production"
cp -p "$SRC"/sd-cli.exe "$SRC"/sd-server.exe "$SRC"/*.dll "$SRC"/*.txt "$DST/"

echo "3) verify"
"$DST/sd-cli.exe" --version

echo "4) remove the parallel install (duplicate, trellis-081 precedent)"
rm -rf "$SRC"

echo "PROMOTION DONE — rollback: copy back from $BK"
