#!/usr/bin/env bash
# tests_nuit.sh — overnight test queue (generator-assets)
#
# Purpose: run the long test legs that the 1 h/day rule (AGENTS.md §7, user rule
# 2026-09-28) excludes from day windows — "except at night". Runs ONLY on an idle
# machine (check_charge_systeme gate before every leg; clean stop + resume next night).
#
# Idempotent: per-leg markers in output/tests_nuit/<id>/ (DONE / FAIL / FAIL_MACHINE_STATE).
#   - DONE              → skipped forever (results kept on disk)
#   - FAIL              → skipped next nights (deterministic failure; delete the marker to retry)
#   - FAIL_MACHINE_STATE→ skipped (known machine-state signature, e.g. LTX Vulkan_Host margin)
# Reset a leg = delete its marker file.
#
# Queue: output/tests_nuit/queue.txt (one test id per line, '#' = comment).
# Empty/exhausted queue → the run is a fast no-op.
#
# Report: output/tests_nuit/RAPPORT.md (rewritten at the end of each run).
# Called nightly by the "Tests de nuit" automation (02:30).

set -u
REPO=/c/GIT/generator-assets
OUT="$REPO/output/tests_nuit"
QUEUE="$OUT/queue.txt"
MODELES="C:/Modeles_LLM"
SD="C:/SD/sd-cli.exe"
mkdir -p "$OUT"
cd "$REPO" || exit 1

log() { echo "[$(date +%H:%M:%S)] $*"; }

gate() {
  uv run python scripts/check_charge_systeme.py > "$OUT/gate_last.log" 2>&1
  if [ $? -ne 0 ]; then
    log "GATE refused — machine busy, clean stop (resume next night)."
    return 1
  fi
  return 0
}

planche() { # contact sheet for the morning verdict: ALL frames (clips are <2 s) tiled 5x4
  local webm="$1" png="$2"
  ffmpeg -y -loglevel error -i "$webm" -vf "fps=30,scale=320:-1,tile=5x4" -frames:v 1 "$png" 2>/dev/null
}

# run_leg <id> <command...>: gate + execute + time + markers.
#   rc 0 = leg done (pass or fail recorded), rc 2 = gate refused (abort the queue).
run_leg() {
  local id="$1"; shift
  local d="$OUT/$id"
  mkdir -p "$d"
  [ -f "$d/DONE" ] && { log "[$id] already DONE — skip"; return 0; }
  [ -f "$d/FAIL" ] && { log "[$id] FAIL marker — skip (delete the marker to retry)"; return 0; }
  [ -f "$d/FAIL_MACHINE_STATE" ] && { log "[$id] known machine-state failure — skip"; return 0; }
  log "[$id] gate…"
  if ! gate; then return 2; fi
  local t0 t1
  t0=$(date +%s)
  log "[$id] START"
  "$@" > "$d/run.log" 2>&1
  local rc=$?
  t1=$(date +%s)
  echo $((t1-t0)) > "$d/duree.txt"
  if [ $rc -eq 0 ]; then
    touch "$d/DONE"
    log "[$id] PASS ($((t1-t0))s)"
  else
    touch "$d/FAIL"
    log "[$id] FAIL rc=$rc ($((t1-t0))s) — log: $d/run.log (tail:)"
    tail -3 "$d/run.log" | sed 's/^/    /'
  fi
  return 0
}

# ---------------------------------------------------------------- legs (implementations)

leg_wan_i2v_929() {
  # Wan I2V crashed 0xC0000409 on 6b3edaa (09/25) — never retested since. If green on
  # the 929 production binary, the video-analys-ia consumer path is unblocked.
  run_leg wan_i2v_929 \
    uv run python main.py -w video \
      -i output/test_vace/ref_chevalier_832x480.png \
      -p "a medieval heraldic knight in engraved armor running through a misty forest, cinematic lighting, high quality" \
      --frames 17 -o nuit_wan_i2v_929
  if [ -f "$OUT/wan_i2v_929/DONE" ]; then
    planche output/video/nuit_wan_i2v_929.webm "$OUT/wan_i2v_929/planche.png" || true
  fi
}

leg_vace_knight() {
  # I2V + VACE on Wan 2.1 14B Q3_K_S offload — recette MEMORY_BANK §1.28 + knight
  # reference (appearance lock). Expected ~52-60 min. Morning verdict required.
  run_leg vace_knight \
    "$SD" -M vid_gen \
      --diffusion-model "$MODELES/Wan2.1_14B_VACE-Q3_K_S.gguf" \
      --vae "$MODELES/wan_2.1_vae.safetensors" \
      --t5xxl "$MODELES/umt5-xxl-encoder-Q4_K_M.gguf" \
      -i output/test_vace/ref_chevalier_832x480.png \
      --control-video output/test_vace/skeletons \
      -p "a medieval heraldic knight in engraved armor running through a misty forest, cinematic lighting, high quality" \
      -W 832 -H 480 --video-frames 13 --fps 16 --steps 20 --cfg-scale 6.0 \
      --sampling-method euler --diffusion-fa --offload-to-cpu --vae-on-cpu --seed 42 \
      -t 16 --backend vulkan -v \
      -o "$OUT/vace_knight/vace_i2v_knight.webm"
  if [ -f "$OUT/vace_knight/DONE" ]; then
    planche "$OUT/vace_knight/vace_i2v_knight.webm" "$OUT/vace_knight/planche.png" || true
  fi
}

leg_ltx33_929() {
  # LTX 33f leg that failed identically on BOTH builds during the 09/28 matrix
  # (desktop VRAM margin). Night attempt on the (theoretically lighter) desktop.
  run_leg ltx33_929 \
    "$SD" -M vid_gen \
      --diffusion-model "$MODELES/LTX-2.5-Distilled-Q4_K_M.gguf" \
      --vae "$MODELES/ltx-2.5-video-vae-conv-bf16.safetensors" \
      --llm "$MODELES/gemma4-12b-with-proj-ltx-2.5-Q5_K_M.gguf" \
      -p "Cinematic wide tracking shot, a colossal golden dragon with shimmering scales soaring majestically through sunset clouds, volumetric rays, high quality, 8k" \
      -W 768 -H 512 --video-frames 33 --fps 24 \
      --steps 2 --sampling-method euler_a --cfg-scale 1.0 \
      --diffusion-fa --seed 42 -t 12 \
      --backend "diffusion=vulkan0,te=cpu" -v \
      -o "$OUT/ltx33_929/ltx33_nuit.webm"
  if [ -f "$OUT/ltx33_929/FAIL" ] && grep -q "ErrorOutOfDeviceMemory" "$OUT/ltx33_929/run.log" 2>/dev/null; then
    mv "$OUT/ltx33_929/FAIL" "$OUT/ltx33_929/FAIL_MACHINE_STATE"
    log "[ltx33_929] OOM signature → reclassified FAIL_MACHINE_STATE"
  fi
}

leg_h3_turbo_929() {
  # H3 turbo on the 929 production binary — #1976 datapoint refresh (expected broken:
  # 54 segments). Factory full path (§6 rule). ~38 min.
  run_leg h3_turbo_929 \
    uv run python main.py -w h3_ref2va \
      -i output/test_p1_final/h3_source_avec_audio.mp4 \
      --turbo
}

leg_monoplan65_929() {
  # Conditional: the monoplan 65-frame LTX leg OOM'd on 908 (09/25) — only meaningful
  # if the night LTX 33f attempt PASSED on this machine state.
  if [ ! -f "$OUT/ltx33_929/DONE" ]; then
    log "[monoplan65_929] conditional on ltx33_929 PASS — not met, skip (no marker)"
    return 0
  fi
  run_leg monoplan65_929 \
    uv run python main.py -w monoplan_ia -o nuit_monoplan65_929
}

leg_lightx2v_vace() {
  # Optional closing leg: distilled VACE (4-8 steps) — download if absent, then a fast
  # 8-step I2V+VACE run with the knight reference. Quant resolved from the HF repo.
  local gguf="$MODELES/Wan2.1_14B_LightX2V_StepCfgDistill_VACE-Q3_K_S.gguf"
  if [ ! -f "$gguf" ]; then
    log "[lightx2v_vace] resolving the distilled VACE quant on HF…"
    local url
    url=$(curl -s "https://huggingface.co/api/models/QuantStack/Wan2.1_T2V_14B_LightX2V_StepCfgDistill_VACE-GGUF/tree/main" \
      | grep -oE '"path": *"[^"]*(Q3_K_S|Q4_K_S)\.gguf"' | head -1 | cut -d'"' -f4)
    if [ -z "$url" ]; then
      log "[lightx2v_vace] quant not found on HF (repo name changed?) — FAIL marker"
      mkdir -p "$OUT/lightx2v_vace"; touch "$OUT/lightx2v_vace/FAIL"
      return 0
    fi
    log "[lightx2v_vace] downloading $url…"
    uv run python scripts/telecharger_gros_fichier_parallele.py \
      "https://huggingface.co/QuantStack/Wan2.1_T2V_14B_LightX2V_StepCfgDistill_VACE-GGUF/resolve/main/$url" "$gguf" \
      > "$OUT/lightx2v_vace/download.log" 2>&1 || { log "[lightx2v_vace] download failed (transient?) — no marker, retry next night"; return 0; }
  fi
  run_leg lightx2v_vace \
    "$SD" -M vid_gen \
      --diffusion-model "$gguf" \
      --vae "$MODELES/wan_2.1_vae.safetensors" \
      --t5xxl "$MODELES/umt5-xxl-encoder-Q4_K_M.gguf" \
      -i output/test_vace/ref_chevalier_832x480.png \
      --control-video output/test_vace/skeletons \
      -p "a medieval heraldic knight in engraved armor running through a misty forest, cinematic lighting, high quality" \
      -W 832 -H 480 --video-frames 13 --fps 16 --steps 8 --cfg-scale 1.0 \
      --sampling-method euler --diffusion-fa --offload-to-cpu --vae-on-cpu --seed 42 \
      -t 16 --backend vulkan -v \
      -o "$OUT/lightx2v_vace/lightx2v_i2v_knight.webm"
  if [ -f "$OUT/lightx2v_vace/DONE" ]; then
    planche "$OUT/lightx2v_vace/lightx2v_i2v_knight.webm" "$OUT/lightx2v_vace/planche.png" || true
  fi
}

# ---------------------------------------------------------------- report

rapport() {
  local f="$OUT/RAPPORT.md"
  {
    echo "# 🌙 Night test report — $(date '+%Y-%m-%d %H:%M')"
    echo ""
    echo "| leg | status | duration | evidence |"
    echo "|---|---|---|---|"
    while read -r id; do
      case "$id" in ""|\#*) continue;; esac
      local st="-" du="-" ev="-"
      [ -f "$OUT/$id/DONE" ] && st="✅ PASS"
      [ -f "$OUT/$id/FAIL" ] && st="❌ FAIL"
      [ -f "$OUT/$id/FAIL_MACHINE_STATE" ] && st="⏸️ machine-state"
      [ -f "$OUT/$id/duree.txt" ] && du="$(cat "$OUT/$id/duree.txt")s"
      [ "$id" = "vace_knight" ]      && [ -f "$OUT/vace_knight/vace_i2v_knight.webm" ] && ev="planche.png + webm"
      [ "$id" = "wan_i2v_929" ]      && [ -f "output/video/nuit_wan_i2v_929.webm" ] && ev="output/video/nuit_wan_i2v_929.webm"
      [ "$id" = "ltx33_929" ]        && [ -f "$OUT/ltx33_929/ltx33_nuit.webm" ] && ev="ltx33_nuit.webm"
      [ "$id" = "monoplan65_929" ]   && ev="output/monoplan_ia/"
      [ "$id" = "h3_turbo_929" ]     && ev="output/h3_ref2va/ (expect #1976 signature)"
      [ "$id" = "lightx2v_vace" ]    && [ -f "$OUT/lightx2v_vace/lightx2v_i2v_knight.webm" ] && ev="planche.png + webm"
      echo "| $id | $st | $du | $ev |"
    done < "$QUEUE"
    echo ""
    echo "Gate log (last): \`output/tests_nuit/gate_last.log\` — per-leg logs in \`output/tests_nuit/<id>/run.log\`."
  } > "$f"
  log "Report written: $f"
}

# ---------------------------------------------------------------- main

if [ ! -f "$QUEUE" ]; then
  printf '# Overnight test queue (one id per line)\n# wan_i2v_929 | vace_knight | ltx33_929 | h3_turbo_929 | monoplan65_929 | lightx2v_vace\n' > "$QUEUE"
fi

log "=== Night test queue run — queue: $QUEUE ==="
while read -r id; do
  case "$id" in ""|\#*) continue;; esac
  case "$id" in
    wan_i2v_929)    leg_wan_i2v_929 ;;
    vace_knight)    leg_vace_knight ;;
    ltx33_929)      leg_ltx33_929 ;;
    h3_turbo_929)   leg_h3_turbo_929 ;;
    monoplan65_929) leg_monoplan65_929 ;;
    lightx2v_vace)  leg_lightx2v_vace ;;
    *) log "[?] unknown queue id: $id — ignored" ;;
  esac
  if [ -s "$OUT/gate_last.log" ] && grep -q "DO NOT launch" "$OUT/gate_last.log"; then
    log "Gate refused — aborting the queue for tonight (markers keep progress)."
    break
  fi
done < "$QUEUE"

rapport
log "=== Night queue run finished ==="
exit 0
