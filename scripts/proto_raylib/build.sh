#!/usr/bin/env bash
# Build the raylib test-campaign prototypes (MSYS2 UCRT64 toolchain, raylib 6.2).
# Usage: bash scripts/proto_raylib/build.sh
# Run built executables with /c/msys64/ucrt64/bin first on PATH (runtime DLLs).
set -euo pipefail
cd "$(dirname "$0")"

GCC=/c/msys64/ucrt64/bin/gcc.exe
CFLAGS="-O2 -Wall -std=c99"
LIBS="-L/c/msys64/ucrt64/lib -lraylib -lopengl32 -lgdi32 -lwinmm"

mkdir -p ../../output/test_raylib
for src in smoke.c tex_proc.c fond_shader.c turntable.c; do
  [ -f "$src" ] || continue
  echo "[build] $src"
  "$GCC" $CFLAGS "$src" -o "${src%.c}.exe" $LIBS
done
echo "BUILD OK"
