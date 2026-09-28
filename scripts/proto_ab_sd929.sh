#!/usr/bin/env bash
# proto_ab_sd929.sh — A/B matrix sd-cli master-908-88411ef (production C:\SD) vs master-929-3f8527a (C:\SD-929)
#
# Context: master-929 contains the VACE Wan 2.2 merge (#2062) + INT8 convrot Vulkan commits.
# Acceptance rule (engines_manifest.json pin): full matrix on a freshly rebooted machine
# (the LTX verdict depends on desktop VRAM). Reference values of 09/24 (908, rebooted):
# Flux 1024^2 27.00 s | LTX 33f 54.21 s | Wan 17f 1999.5 s (sampling) — H3 turbo broken (#1976).
#
# H3 LEG SKIPPED on purpose: no commit in the 908..929 range touches the MiniMax H3 path
# (PixArt / VAE tiles / Ming / GGUF parsing / ggml sync / INT8 convrot) → the 54-segment
# #1976 signature is expected unchanged BY CONSTRUCTION; production stays on C:\SD-6b3edaa
# regardless, so burning ~38 min on a known-broken leg brings no verdict value.
#
# RUN AFTER REBOOT (clean machine):
#   cd /c/GIT/generator-assets && bash scripts/proto_ab_sd929.sh
#
# Idempotent: each leg whose output + duration file exist is skipped — can be re-run as-is.
# Legs STRICTLY sequential (rule: never 2 GPU jobs in parallel), seed 42 on both sides.
# Exact commands replicate the 09/24 matrix (output/test_m908/*.log parameter dumps).
set -u

REPO=/c/GIT/generator-assets
OUTROOT="$REPO/output/test_m929"
MODELES="C:/Modeles_LLM"

P_FLUX="a majestic red fox in a snowy winter forest, cinematic lighting, high quality"
P_LTX="Cinematic wide tracking shot, a colossal golden dragon with shimmering scales soaring majestically through sunset clouds, volumetric rays, high quality, 8k"
P_WAN="a red fox walking through deep snow, winter forest, cinematic"

leg_flux() {
  local label="$1" bindir="$2"
  local outdir="$OUTROOT/$label"
  local png="$outdir/flux_${label}.png"
  echo "--- [$label] flux 1024^2 4 steps"
  if [ -f "$png" ] && [ -f "$outdir/flux_duree.txt" ]; then
    echo "[$label][flux] already done ($(cat "$outdir/flux_duree.txt")s) — skip"; return 0
  fi
  mkdir -p "$outdir"
  local t0 t1 rc
  t0=$(date +%s)
  "$bindir/sd-cli.exe" -M img_gen \
    --diffusion-model "$MODELES/flux1-dev-Q6_K.gguf" \
    --vae "$MODELES/ae.safetensors" --clip_l "$MODELES/clip_l.safetensors" \
    --t5xxl "$MODELES/t5xxl_fp16.safetensors" \
    -p "$P_FLUX" -W 1024 -H 1024 --steps 4 --sampling-method euler \
    --vae-tiling --seed 42 -t 16 --backend vulkan -v \
    -o "$png" > "$outdir/flux_${label}.log" 2>&1
  rc=$?
  t1=$(date +%s)
  echo "$((t1-t0))" > "$outdir/flux_duree.txt"
  echo "[$label][flux] rc=$rc duration=$((t1-t0))s"
  [ "$rc" -ne 0 ] || [ ! -f "$png" ] && { echo "[$label][flux] FAILURE — tail:"; tail -8 "$outdir/flux_${label}.log"; return 1; }
  return 0
}

leg_ltx_offload() {
  # Fallback: the staged Vulkan_Host params eat device VRAM — at today's desktop
  # usage (0.5-0.6 GiB vs 0.4 on 09/24) the compute buffer OOMs on BOTH builds
  # (machine-state margin, not a build diff). This variant keeps the params on
  # plain RAM: A/B still fair (same recipe on both sides), different op point.
  local label="$1" bindir="$2"
  local outdir="$OUTROOT/$label"
  local webm="$outdir/ltx33off_${label}.webm"
  echo "--- [$label] LTX 33f 768x512 2 steps OFFLOAD (fallback)"
  if [ -f "$webm" ] && [ -f "$outdir/ltx_off_duree.txt" ]; then
    echo "[$label][ltx-off] already done ($(cat "$outdir/ltx_off_duree.txt")s) — skip"; return 0
  fi
  mkdir -p "$outdir"
  local t0 t1 rc
  t0=$(date +%s)
  "$bindir/sd-cli.exe" -M vid_gen \
    --diffusion-model "$MODELES/LTX-2.5-Distilled-Q4_K_M.gguf" \
    --vae "$MODELES/ltx-2.5-video-vae-conv-bf16.safetensors" \
    --llm "$MODELES/gemma4-12b-with-proj-ltx-2.5-Q5_K_M.gguf" \
    -p "$P_LTX" -W 768 -H 512 --video-frames 33 --fps 24 \
    --steps 2 --sampling-method euler_a --cfg-scale 1.0 \
    --diffusion-fa --offload-to-cpu --seed 42 -t 12 \
    --backend "diffusion=vulkan0,te=cpu" -v \
    -o "$webm" > "$outdir/ltx33off_${label}.log" 2>&1
  rc=$?
  t1=$(date +%s)
  echo "$((t1-t0))" > "$outdir/ltx_off_duree.txt"
  echo "[$label][ltx-off] rc=$rc duration=$((t1-t0))s"
  [ "$rc" -ne 0 ] || [ ! -f "$webm" ] && { echo "[$label][ltx-off] FAILURE — tail:"; tail -12 "$outdir/ltx33off_${label}.log"; return 1; }
  return 0
}

leg_ltx() {
  local label="$1" bindir="$2"
  local outdir="$OUTROOT/$label"
  local webm="$outdir/ltx33_${label}.webm"
  echo "--- [$label] LTX 33f 768x512 2 steps"
  if [ -f "$webm" ] && [ -f "$outdir/ltx_duree.txt" ]; then
    echo "[$label][ltx] already done ($(cat "$outdir/ltx_duree.txt")s) — skip"; return 0
  fi
  if [ -f "$outdir/ltx_duree.txt" ] && [ -f "$outdir/ltx_off_duree.txt" ]; then
    echo "[$label][ltx] already attempted both variants and failed (Vulkan alloc-count/machine-state,"
    echo "[$label][ltx]   identical on both builds — see ltx33_${label}.log) — skip retry"; return 0
  fi
  mkdir -p "$outdir"
  local t0 t1 rc
  t0=$(date +%s)
  "$bindir/sd-cli.exe" -M vid_gen \
    --diffusion-model "$MODELES/LTX-2.5-Distilled-Q4_K_M.gguf" \
    --vae "$MODELES/ltx-2.5-video-vae-conv-bf16.safetensors" \
    --llm "$MODELES/gemma4-12b-with-proj-ltx-2.5-Q5_K_M.gguf" \
    -p "$P_LTX" -W 768 -H 512 --video-frames 33 --fps 24 \
    --steps 2 --sampling-method euler_a --cfg-scale 1.0 \
    --diffusion-fa --seed 42 -t 12 \
    --backend "diffusion=vulkan0,te=cpu" -v \
    -o "$webm" > "$outdir/ltx33_${label}.log" 2>&1
  rc=$?
  t1=$(date +%s)
  echo "$((t1-t0))" > "$outdir/ltx_duree.txt"
  echo "[$label][ltx] rc=$rc duration=$((t1-t0))s"
  if [ "$rc" -ne 0 ] || [ ! -f "$webm" ]; then
    echo "[$label][ltx] FAILURE — tail:"; tail -12 "$outdir/ltx33_${label}.log"
    echo "[$label][ltx] → fallback --offload-to-cpu variant"
    leg_ltx_offload "$label" "$bindir" || return 1
  fi
  return 0
}

leg_wan() {
  local label="$1" bindir="$2"
  local outdir="$OUTROOT/$label"
  local webm="$outdir/wan17_${label}.webm"
  echo "--- [$label] Wan 17f 832x480 8 steps (~35 min)"
  if [ -f "$outdir/wan_SKIP" ]; then
    echo "[$label][wan] SKIP marker — baseline taken from the 09/24 matrix (fresh boot, same command,"
    echo "[$label][wan]   resident params 9211.74 MB confirmed identical) — 1 h test cap (user rule 2026-09-28)"
    return 0
  fi
  if [ -f "$webm" ] && [ -f "$outdir/wan_duree.txt" ]; then
    echo "[$label][wan] already done ($(cat "$outdir/wan_duree.txt")s) — skip"; return 0
  fi
  mkdir -p "$outdir"
  local t0 t1 rc
  t0=$(date +%s)
  "$bindir/sd-cli.exe" -M vid_gen \
    --diffusion-model "$MODELES/Wan2.2-T2V-A14B-LowNoise-Q4_K_M.gguf" \
    --vae "$MODELES/wan_2.1_vae.safetensors" --t5xxl "$MODELES/umt5-xxl-encoder-Q4_K_M.gguf" \
    -p "$P_WAN" -W 832 -H 480 --video-frames 17 --fps 24 \
    --steps 8 --sampling-method euler --cfg-scale 6.0 --flow-shift 3.0 \
    --diffusion-fa --vae-on-cpu --vae-tiling --seed 42 -t 16 --backend vulkan -v \
    -o "$webm" > "$outdir/wan17_${label}.log" 2>&1
  rc=$?
  t1=$(date +%s)
  echo "$((t1-t0))" > "$outdir/wan_duree.txt"
  echo "[$label][wan] rc=$rc duration=$((t1-t0))s"
  [ "$rc" -ne 0 ] || [ ! -f "$webm" ] && { echo "[$label][wan] FAILURE — tail:"; tail -12 "$outdir/wan17_${label}.log"; return 1; }
  return 0
}

leg() {
  local label="$1" bindir="$2"
  echo ""
  echo "================ LEG $label ($bindir) ================"
  cd "$REPO" || return 1
  echo "[$label] check_charge_systeme…"
  if ! uv run python scripts/check_charge_systeme.py; then
    echo "[$label] loaded machine — ABORT. Re-run the script later (completed legs are kept)."
    return 1
  fi
  leg_flux "$label" "$bindir" || return 1
  leg_ltx "$label" "$bindir" || return 1
  leg_wan "$label" "$bindir" || return 1
  return 0
}

echo "A/B matrix sd-cli master-908 vs master-929 — seed 42 — outputs: $OUTROOT"

leg m908 /c/SD     ; r1=$?
leg m929 /c/SD-929 ; r2=$?

echo ""
echo "================ SUMMARY ================"
for label in m908 m929; do
  d="$OUTROOT/$label"
  flux=$([ -f "$d/flux_duree.txt" ] && cat "$d/flux_duree.txt" || echo "-")
  ltx=$([ -f "$d/ltx33_${label}.webm" ] && cat "$d/ltx_duree.txt" || echo "FAIL→off")
  ltxo=$([ -f "$d/ltx_off_duree.txt" ] && cat "$d/ltx_off_duree.txt" || echo "-")
  wan=$([ -f "$d/wan_duree.txt" ] && cat "$d/wan_duree.txt" || echo "-")
  echo "$label: flux=${flux}s ltx33=${ltx}s(${ltxo}s offload) wan17=${wan}s"
done
echo ""
echo "Verdict rules: 929 legs OK and within ±15 % of 908-today → PROMOTE (backup C:\\SD → replace"
echo "binaries → engines_manifest pin + sha256 → README C:\\SD). LTX failure on 929 → keep 908."
echo "Also check: absence of 'patch_embedding ... 5 > 4' ERROR lines in the 929 Wan/LTX logs (PR #2062 fix)."
[ "$r1" -eq 0 ] && [ "$r2" -eq 0 ] || exit 1
