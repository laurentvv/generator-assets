#!/usr/bin/env bash
# proto_ab_trellis_v081.sh — A/B perf trellis v0.6.0 (production C:\trellis) vs v0.8.1 prebuilt (C:\trellis-081)
#
# Context: +51 % regression of v0.8.0 confirmed by a clean A/B on the night of 24→25/09 → rollback to v0.6.0.
# v0.8.1 (released on 25/09) = retopology packaging, prebuilt announced with no functional change
# → control A/B requested by the user on 25/09 ("prepare the test and I'll reboot before you run it").
#
# RUN AFTER REBOOT (clean machine):
#   cd /c/GIT/generator-assets && bash scripts/proto_ab_trellis_v081.sh
#
# Idempotent: each leg already completed (GLB + duree.txt present) is skipped — can be re-run as-is.
# Legs STRICTLY sequential (rule: never 2 GPU jobs in parallel), seed 42 on both sides.
set -u

REPO=/c/GIT/generator-assets
IMG="$REPO/godot_assets/casque.png"
MODELES="C:/Modeles_LLM/trellis2-gguf"
OUTROOT="$REPO/output/trellis_ab_v081"
RES=512
SEED=42
BASELINE_S=644   # v0.6.0, clean matrix of 24/09 (same image, same resolution)

leg() {
  local label="$1" bindir="$2"
  local outdir="$OUTROOT/$label"
  local glb="$outdir/casque_${label}.glb"
  echo ""
  echo "================ LEG $label ($bindir) ================"
  if [ -f "$glb" ] && [ -f "$outdir/duree.txt" ]; then
    echo "[$label] already done ($(cat "$outdir/duree.txt")s) — skip"
    return 0
  fi
  mkdir -p "$outdir"
  cd "$REPO" || return 1
  echo "[$label] check_charge_systeme…"
  if ! uv run python scripts/check_charge_systeme.py; then
    echo "[$label] loaded machine — ABORT. Run the script again later (completed legs are kept)."
    return 1
  fi
  local t0 t1 rc
  t0=$(date +%s)
  (cd "$bindir" && ./trellis-cli.exe -i "$IMG" -o "$glb" -m "$MODELES" --res "$RES" --seed "$SEED") \
    > "$outdir/run.log" 2>&1
  rc=$?
  t1=$(date +%s)
  echo "$((t1-t0))" > "$outdir/duree.txt"
  echo "[$label] rc=$rc duration=$((t1-t0))s (v0.6.0 reference of 24/09: ${BASELINE_S}s)"
  if [ "$rc" -ne 0 ]; then
    echo "[$label] FAILURE — $outdir/run.log (last 10 lines):"
    tail -10 "$outdir/run.log"
    return 1
  fi
  ls -la "$outdir" | grep -E "glb|ply|png"
  return 0
}

echo "A/B trellis $RES px — image $(basename "$IMG") — seed $SEED"
echo "Outputs: $OUTROOT"

leg v060 /c/trellis      ; r1=$?
leg v081 /c/trellis-081  ; r2=$?

echo ""
echo "================ SUMMARY ================"
for label in v060 v081; do
  glb="$OUTROOT/$label/casque_${label}.glb"
  if [ -f "$glb" ] && [ -f "$OUTROOT/$label/duree.txt" ]; then
    echo "$label: $(cat "$OUTROOT/$label/duree.txt")s — GLB $(du -h "$glb" | cut -f1) — $glb"
  else
    echo "$label: incomplete"
  fi
done
echo ""
echo "Verdict: v081 ≈ v060 (±15 %) → upgrade production to v0.8.1 (backup + version.json + README)."
echo "         v081 ~ +50 % (like v0.8.0) → keep v0.6.0, purge the watch entry (wait for a real perf fix)."
echo "         In both cases: ALSO compare the render of the 2 GLBs (geometry/textures) before verdict."
[ "$r1" -eq 0 ] && [ "$r2" -eq 0 ] || exit 1
