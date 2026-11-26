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
# Shutdown: `bash scripts/tests_nuit.sh --shutdown` schedules a Windows shutdown
# 300 s after the queue ends (user rule 2026-11-20: don't leave the PC running
# all night for nothing). OPT-IN only — a plain run NEVER touches the machine
# state. Abort within the grace window: `shutdown /a`.
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
SD6B="C:/SD-6b3edaa/sd-cli.exe"   # LTX/H3 production build (master-841) — MEMORY_BANK §1.17
mkdir -p "$OUT"
cd "$REPO" || exit 1

# Shutdown at queue end = DEFAULT (user rule 2026-11-24: never idle post-queue,
# FAIL legs don't stop the queue). Opt out for one night with --no-shutdown.
SHUTDOWN=1
for a in "$@"; do case "$a" in
  --no-shutdown) SHUTDOWN=0 ;;
  --shutdown) SHUTDOWN=1 ;;
  *) echo "unknown option: $a (supported: --shutdown | --no-shutdown)"; exit 1 ;;
esac; done

log() { echo "[$(date +%H:%M:%S)] $*"; }

gate() {
  uv run python scripts/check_charge_systeme.py > "$OUT/gate_last.log" 2>&1
  if [ $? -ne 0 ]; then
    log "GATE refused — machine busy, clean stop (resume next night)."
    return 1
  fi
  return 0
}

planche() { # contact sheet for the morning verdict; 3rd arg = sampling fps (default 30 =
  # first 20 frames, right for <2 s clips; pass ~7 to span a full 65-frame clip)
  local webm="$1" png="$2" fps="${3:-30}"
  ffmpeg -y -loglevel error -i "$webm" -vf "fps=$fps,scale=320:-1,tile=5x4" -frames:v 1 "$png" 2>/dev/null
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

# substat <leg-dir>: PASS/FAIL/- from markers — status line for compound-leg SUBSTATUS.txt
substat() {
  [ -f "$1/DONE" ] && echo "PASS" && return 0
  [ -f "$1/FAIL" ] && echo "FAIL" || echo "-"
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
  # 10-01 fix: the leg launched WITHOUT -p (workflow requirement: sequel description
  # with <Video 1>) — 1 s FAIL, no datapoint. Prompt = the validated P1 recipe
  # (output/test_p1_final/h3_run.log, Sep 25) WITHOUT the manual LoRA tag (--turbo appends it).
  run_leg h3_turbo_929 \
    uv run python main.py -w h3_ref2va \
      -i output/test_p1_final/h3_source_avec_audio.mp4 \
      -p "the camera continues its slow push-in on the helmet, dust motes drifting, <Video 1>" \
      --turbo
}

leg_h3_turbo_945() {
  # #2103 candidate-fix probe (10-07): SAME factory full path as h3_turbo_929 but with
  # SD_CLI_LTX_PATH overridden to the NEW master-945 binary (C:\SD) — 945 carries the
  # first H3-path commit since 908 (keep MiniMax-H3 VAE weights resident across temporal
  # chunks). The 929 datapoint is already covered upstream (issue #1976 comment 10-02).
  # PASS  = #2103 kills the 54-segment OOM → revalidate output vs 6b3edaa, then repoint
  #         DEFAULT_SD_CLI_LTX (6b3edaa retirement path).
  # FAIL with the ErrorOutOfDeviceMemory signature = #1976 stays open, 6b3edaa stays
  #         production (note: the nebkmb 24 GB 3090 datapoint predicts this outcome).
  # ~38 min (--turbo, §7 invariant).
  export SD_CLI_LTX_PATH="C:/SD/sd-cli.exe"
  run_leg h3_turbo_945 \
    uv run python main.py -w h3_ref2va \
      -i output/test_p1_final/h3_source_avec_audio.mp4 \
      -p "the camera continues its slow push-in on the helmet, dust motes drifting, <Video 1>" \
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
    mkdir -p "$OUT/lightx2v_vace"
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

# ------------------------------------------------- audio.cpp v0.9.0 legs (added 10/01)
# The 09/30 update was installed with the GPU busy (user "GPU: OCCUPE que CPU"): binary
# verified only (--version + --list-devices). These legs are the deferred smoke set.

leg_acestep90_12s() {
  # audio.cpp v0.9.0 ace_step smoke — 12 s turbo on Vulkan (same protocol as the 09/25
  # hotfix smoke). PR #737 claims -63% VRAM, +16% Vulkan speed. Reference ace_step RTFs
  # on 12 s turbo: v0.8.1 3.25-3.85 intra-day, hotfix 3.82/3.53 (same-day A/B averages
  # 3.68 vs 3.32). Verdict rule (MEMORY_BANK §1.10): same-day A/B only if the number
  # looks like a regression vs that range; a single clean number in/below range = PASS.
  run_leg acestep90_12s \
    C:/audio-cpp/audiocpp_cli.exe --task gen --family ace_step \
      --model "$MODELES/ACE-Step1.5-GGUF/turbo/ace-step-1.5-turbo-bf16.gguf" \
      --backend vulkan --task-route text2music \
      --text "gothic rock, 83 BPM, C sharp minor, distorted guitars, dark atmosphere, high quality" \
      --duration-seconds 12 --num-inference-steps 8 --seed 42 \
      --out "$OUT/acestep90_12s/smoke90_12s.wav"
}

leg_dance_sheet_v2() {
  # Dance sheet v2 chain (19-11 user verdict on v1: "la tete est horrible") — the
  # §1.55 contract-grade item, retooled: 16 poses dual-ref (head-only identity patch
  # + framing lock; probed 19-11: 512² dual-ref 14 s/it on-device, 640² hybrid
  # 58 s/it REJECTED) -> stitch 2048² -> amorce v3 -> monoplan clip v2 -> identity
  # grid (4 frames). ~55 min total. Morning verdict required on sheet + mp4 + grid.
  # Machine-local chain (output/ is git-ignored): explicit existence check so a
  # fresh clone logs a clear reason instead of a bare rc=127 FAIL (review 11-20).
  local chain="output/test_dance_sheet_m1106/night_dance_v2.sh"
  if [ ! -f "$chain" ]; then
    log "[dance_sheet_v2] machine-local chain script missing ($chain) — skip, no marker"
    return 0
  fi
  run_leg dance_sheet_v2 bash "$chain"
}

# ------------------------------------------------- IndexTTS2.5 slot campaign legs (added 11-20)
# Queued 11-15 (user "ajoute ça au test de nuit"), implemented 11-20: first IndexTTS2.5
# datapoints — 0 verdicts, never tested. q8_0 GGUF on disk 11-15 (byte-verified); audio.cpp
# v0.9.5 family index_tts2 (model_specs/index_tts2.json: v2.5 variant = multilingual
# tiktoken, languages zh/en/ja/es/ar). 11-20 wiring smoke: voice_ref is MANDATORY (upstream
# zero-shot design, no built-in voices — refusal "IndexTTS2 request requires --voice-ref"
# without one), Vulkan gen exit 0, RTF ~11 incl. load on a 1-sentence text.
# fr_probe = GAP datapoint (fr NOT in the spec language list) — a FAIL marker here is the
# EXPECTED recorded outcome, not a regression. Morning listening verdict on the wavs.

leg_indextts25_en_tts() {
  # EN zero-shot TTS, neutral synthetic reference — quality + RTF datapoint.
  run_leg indextts25_en_tts \
    C:/audio-cpp/audiocpp_cli.exe --task tts --family index_tts2 \
      --model "$MODELES/IndexTTS2.5-GGUF/index-tts2_5-q8_0.gguf" \
      --backend vulkan \
      --voice-ref "$REPO/output/comparatif_tts/ref_voix_synth.wav" \
      --text "The night factory hums quietly while the last render finishes. A new voice steps out of the silence, steady and clear, ready to read the script." \
      --language en --seed 42 --metrics \
      --out "$OUT/indextts25_en_tts/indextts25_en_tts.wav"
}

leg_indextts25_en_clone() {
  # EN clone on the user reference — same text + seed as en_tts -> direct timbre A/B.
  run_leg indextts25_en_clone \
    C:/audio-cpp/audiocpp_cli.exe --task tts --family index_tts2 \
      --model "$MODELES/IndexTTS2.5-GGUF/index-tts2_5-q8_0.gguf" \
      --backend vulkan \
      --voice-ref "$REPO/output/comparatif_tts/ref_voix_laurent.wav" \
      --text "The night factory hums quietly while the last render finishes. A new voice steps out of the silence, steady and clear, ready to read the script." \
      --language en --seed 42 --metrics \
      --out "$OUT/indextts25_en_clone/indextts25_en_clone.wav"
}

leg_indextts25_fr_probe() {
  # FR probe = gap datapoint (fr unsupported per spec): expected clean refusal (FAIL marker
  # = recorded outcome). If audio comes out anyway, it goes to the morning listening verdict.
  run_leg indextts25_fr_probe \
    C:/audio-cpp/audiocpp_cli.exe --task tts --family index_tts2 \
      --model "$MODELES/IndexTTS2.5-GGUF/index-tts2_5-q8_0.gguf" \
      --backend vulkan \
      --voice-ref "$REPO/output/comparatif_tts/ref_voix_laurent.wav" \
      --text "La nuit, la fabrique ronronne doucement pendant que le dernier rendu se termine. Une nouvelle voix sort du silence, posée et claire, prête à lire le script." \
      --language fr --seed 42 --metrics \
      --out "$OUT/indextts25_fr_probe/indextts25_fr_probe.wav"
}

leg_dance_sheet_workflow() {
  # §6 real-path closure (11-20): the dance_sheet WORKFLOW port must re-run the
  # chain through the factory full path once — the validated 11-20 night run
  # went through the machine-local scripts, not through this port. Defaults
  # carry the machine-local refs/prompts (--dance-dir). ~55 min.
  run_leg dance_sheet_workflow \
    uv run python main.py -w dance_sheet -o dance_workflow_nuit --seed 42
}

leg_sam_vulkan_retest() {
  # SAM Audio Vulkan retest on v0.9.0 (native #711). 09/28 on the scratch build: fixed
  # encoder buffer 2.58/3.73 GB > AMD driver buffer limit -> ErrorOutOfDeviceMemory.
  # PASS would unlock sam on Vulkan (faster than the CPU recipe RTF 2.9); OOM = the
  # buffer is still monolithic upstream (informative, reclassified machine-state).
  run_leg sam_vulkan_retest \
    C:/audio-cpp/audiocpp_cli.exe --task s2s --family sam_audio \
      --model "$MODELES/SAM-Audio-GGUF/sam-audio-small-q8_0.gguf" \
      --backend vulkan --audio output/test_sam_audio/sample_chanson_30s.wav \
      --text "the singing voice" --seed 42 \
      --out-dir "$OUT/sam_vulkan_retest/"
  if [ -f "$OUT/sam_vulkan_retest/FAIL" ] && grep -q "ErrorOutOfDeviceMemory" "$OUT/sam_vulkan_retest/run.log" 2>/dev/null; then
    mv "$OUT/sam_vulkan_retest/FAIL" "$OUT/sam_vulkan_retest/FAIL_MACHINE_STATE"
    log "[sam_vulkan_retest] OOM signature still present on v0.9.0 → FAIL_MACHINE_STATE (buffer still monolithic)"
  fi
}

leg_sam_cpu_929() {
  # Validation run for the BINAIRE_SAM_AUDIO switch (scratch fd1733e → production v0.9.0):
  # CPU recipe, exact 09/28 protocol (30 s excerpt, small-q8_0, 16 threads, seed 42,
  # RTF reference 2.9). PASS = the switch is authorized in the next day session, followed
  # by a full-path `retrait_voix --music-backend sam` revalidation (§6 rule).
  run_leg sam_cpu_929 \
    C:/audio-cpp/audiocpp_cli.exe --task s2s --family sam_audio \
      --model "$MODELES/SAM-Audio-GGUF/sam-audio-small-q8_0.gguf" \
      --backend cpu --threads 16 --audio output/test_sam_audio/sample_chanson_30s.wav \
      --text "the singing voice" --seed 42 \
      --out-dir "$OUT/sam_cpu_929/"
}

# ------------------------------------------------- LTX-2.5 docs-comparison legs (added 10-01)
# From the docs.ltx.io crawl (MEMORY_BANK §1.33). Queued ONLY on an explicit user "go GPU"
# (the 02:30 automation was REMOVED 10-01 on user request): append the ids to queue.txt.
# Binary = 6b3edaa (LTX production build); recipe = the validated monoplan §1.17 constants
# (8 steps, euler_a, LTX distilled sigmas, cfg 1.0, --max-vram 10, te/vae on CPU), T2V (no -i).

leg_ltx_multishot() {
  # Official "native multishot": several cuts in ONE generation with audio continuity —
  # targets our chained-2-shot sound seams (§1.17). Verdict: does the named hard cut appear
  # (planche), is the soundtrack continuous (ffprobe + listen)? 65 f = 1+64 (official rule).
  run_leg ltx_multishot \
    "$SD6B" -M vid_gen \
      --diffusion-model "$MODELES/LTX-2.5-Distilled-Q4_K_M.gguf" \
      --vae "$MODELES/ltx-2.5-video-vae-conv-bf16.safetensors" \
      --audio-vae "$MODELES/ltx-2.5-audio-vae-bf16.safetensors" \
      --llm "$MODELES/gemma4-12b-with-proj-ltx-2.5-Q5_K_M.gguf" \
      -p "A weathered lighthouse keeper in a navy wool coat stands on a storm-battered stone pier at dusk, waves exploding against the rocks below as he lifts a battered brass lantern. A hard cut transitions to a close-up of the lantern: the flame trembles in the wind, sea spray drifting past his grey beard as he stares out at the dark water. The storm ambience continues across the cut, with crashing waves, distant thunder and a low mournful cello." \
      -W 832 -H 480 --video-frames 65 --fps 24 \
      --steps 8 --sigmas "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0" \
      --sampling-method euler_a --cfg-scale 1.0 \
      --diffusion-fa --max-vram 10 --seed 42 \
      --backend "diffusion=vulkan0,te=cpu,vae=cpu" -v \
      -o "$OUT/ltx_multishot/multishot_65f.webm"
  if [ -f "$OUT/ltx_multishot/DONE" ]; then
    planche "$OUT/ltx_multishot/multishot_65f.webm" "$OUT/ltx_multishot/planche.png" 7 || true
  fi
}

leg_ltx_upscale_base() {
  # 33 f baseline (identical prompt/seed to both upscaler probes) for the detail A/B.
  run_leg ltx_upscale_base \
    "$SD6B" -M vid_gen \
      --diffusion-model "$MODELES/LTX-2.5-Distilled-Q4_K_M.gguf" \
      --vae "$MODELES/ltx-2.5-video-vae-conv-bf16.safetensors" \
      --llm "$MODELES/gemma4-12b-with-proj-ltx-2.5-Q5_K_M.gguf" \
      -p "A colossal golden dragon with shimmering scales soaring through sunset clouds, volumetric rays, cinematic wide shot, high quality" \
      -W 832 -H 480 --video-frames 33 --fps 24 \
      --steps 8 --sigmas "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0" \
      --sampling-method euler_a --cfg-scale 1.0 \
      --diffusion-fa --max-vram 10 --seed 42 \
      --backend "diffusion=vulkan0,te=cpu,vae=cpu" -v \
      -o "$OUT/ltx_upscale_base/base_33f.webm"
}

leg_ltx_upscale_spatial() {
  # LTX spatial latent upscale — DOCUMENTED IMPLEMENTED upstream (sd-cli docs/ltx2.md @ HEAD
  # 3f8527a): model-backed x2 latent upsampler between the low-res pass and the hi-res refine
  # pass; -W/-H = pre-upscale size, output is 2x. Wiring: file under --hires-upscalers-dir,
  # name without path/extension in --hires-upscaler, plus --hires --hires-steps N.
  # Probe on our 6b3edaa build (master-841): does it already wire the LTX upscaler?
  # File gate-protected on Lightricks/LTX-2.5 (401 with our token; the public "ungate" mirror
  # is private): download fails cleanly until the gate is accepted once on the model page.
  local up="$MODELES/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors"
  if [ ! -f "$up" ]; then
    log "[ltx_upscale_spatial] downloading the latent spatial upscaler (HF gate: Lightricks/LTX-2.5)…"
    mkdir -p "$OUT/ltx_upscale_spatial"
    curl -sL --fail -C - \
      -H "Authorization: Bearer $(cat "$HOME/.cache/huggingface/token" 2>/dev/null)" \
      "https://huggingface.co/Lightricks/LTX-2.5/resolve/main/latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors" \
      -o "$up" || {
        log "[ltx_upscale_spatial] download 401/failed — accept the HF gate once on the model page, then delete the FAIL marker"
        touch "$OUT/ltx_upscale_spatial/FAIL"
        return 0
      }
  fi
  run_leg ltx_upscale_spatial \
    "$SD6B" -M vid_gen \
      --diffusion-model "$MODELES/LTX-2.5-Distilled-Q4_K_M.gguf" \
      --vae "$MODELES/ltx-2.5-video-vae-conv-bf16.safetensors" \
      --llm "$MODELES/gemma4-12b-with-proj-ltx-2.5-Q5_K_M.gguf" \
      -p "A colossal golden dragon with shimmering scales soaring through sunset clouds, volumetric rays, cinematic wide shot, high quality" \
      -W 832 -H 480 --video-frames 33 --fps 24 \
      --steps 8 --sigmas "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0" \
      --sampling-method euler_a --cfg-scale 1.0 \
      --hires-upscalers-dir "$MODELES" \
      --hires-upscaler "ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0" \
      --hires --hires-steps 4 \
      --diffusion-fa --max-vram 10 --seed 42 \
      --backend "diffusion=vulkan0,te=cpu,vae=cpu" -v \
      -o "$OUT/ltx_upscale_spatial/spatial_33f.webm"
}

leg_ltx33_929_paramsdisk() {
  # #1976 fit probe (added after the sd-cli docs crawl): the 929 memory manager stages the
  # 14.4 GB LTX DiT params onto Vulkan0 device memory then refuses the workspace (need 908 MB
  # / 776 free). docs/performance.md advertises `--params-backend disk` = "reduce both VRAM
  # and RAM usage". If LTX 33f PASSES on the 929 binary with disk params, LTX could return to
  # the main build (6b3edaa retirement path). Same quick 2-step matrix command as ltx33_929.
  run_leg ltx33_929_paramsdisk \
    "$SD" -M vid_gen \
      --diffusion-model "$MODELES/LTX-2.5-Distilled-Q4_K_M.gguf" \
      --vae "$MODELES/ltx-2.5-video-vae-conv-bf16.safetensors" \
      --llm "$MODELES/gemma4-12b-with-proj-ltx-2.5-Q5_K_M.gguf" \
      -p "A colossal golden dragon with shimmering scales soaring through sunset clouds, volumetric rays, cinematic wide shot, high quality" \
      -W 768 -H 512 --video-frames 33 --fps 24 \
      --steps 2 --sampling-method euler_a --cfg-scale 1.0 \
      --diffusion-fa --seed 42 -t 12 \
      --params-backend disk \
      --backend "diffusion=vulkan0,te=cpu" -v \
      -o "$OUT/ltx33_929_paramsdisk/ltx33_paramsdisk.webm"
}

leg_heartmula_gothic() {
  # STANDING INSTRUCTION 2026-09-07 UNBLOCKED (10-02): HeartMuLa-oss-3B was rejected 09/28
  # (torch-only path) with the note "if a GGUF/engine path appears, the gothic test triggers".
  # audio.cpp v0.9.0 ships a native `heartmula` family + audio-cpp GGUF; q8_0 (7.13 GiB)
  # downloaded to C:\Modeles_LLM\HeartMuLa-GGUF\. Recipe = the standing gothic rock test
  # (30 s, 83 BPM, C# minor, seed 42) — lyrics rebuilt (the 09/28 txt files did not survive
  # the scratch cleanup); tags follow the audio.cpp free-form comma format.
  # 10-02 retry: first attempt failed at codec graph creation — the decoder graph for the
  # default 29.76 s chunk wants ONE 5.55 GB Vulkan buffer, above the AMD driver allocation
  # limit (even a 2.56 GB block refused). Fix (documented, music_generation.md): shrink the
  # codec detokenization chunk to 8 s (buffer ~1.5 GB, ~4 chunks for 30 s — seams possible,
  # note in the listening verdict) + mem_saver to drop staged state between AR/codec phases.
  # 10-02 verdict: REJECTED by the user ("pop moderne donc pas top" — the gothic tags are
  # not followed); leg DONE, no retry planned (MEMORY_BANK §1.34).
  run_leg heartmula_gothic \
    C:/audio-cpp/audiocpp_cli.exe --task gen --family heartmula \
      --model "$MODELES/HeartMuLa-GGUF/heartmula-q8_0.gguf" \
      --backend vulkan \
      --text "gothic rock song, dark and haunting, heavy reverb" \
      --lyrics "[verse] Cold winds arise where light has died, an heir awakes in silent tide [chorus] Rise, heir of the void, the night is thine, the empty crown will be thy sign" \
      --request-option "tags=gothic rock, 83 bpm, c sharp minor, distorted guitars, dark atmosphere" \
      --request-option codec_duration_sec=8 \
      --session-option heartmula.mem_saver=true \
      --duration-seconds 30 \
      --seed 42 \
      --out "$OUT/heartmula_gothic/heartmula_gothic_30s.wav"
}

# ------------------------------------------------- probes 11-20 soir (sweep MEMORY_BANK)
# Version-bound retests + new-capability probes flagged by the 11-20 watch sweep.

leg_llama_b12590_smoke() {
  # llama.cpp b12590 was installed 11-20 (49th always-follow) with the smoke
  # DEFERRED on a red gate (victoria3 game). Historical band for generation
  # t/s = 181-217 (LFM2.5-8B-A1B Q6_K, -ngl 99 -st). ~3 min.
  run_leg llama_b12590_smoke \
    C:/llama.cpp/llama-cli.exe -m "C:/Modeles_LLM/LFM2.5-8B-A1B-Q6_K.gguf" \
      -p "The quick brown fox jumps over the lazy dog" -st -n 40 -ngl 99 \
      < /dev/null
  grep -oE "[0-9.]+ tokens per second" "$OUT/llama_b12590_smoke/run.log" 2>/dev/null | tail -2 > "$OUT/llama_b12590_smoke/ts.txt" || true
}

leg_h3image_smoke() {
  # MiniMax-H3-Image — RETRY 11-22 (GO user « Lance run de nuit »). The 11-21 night run
  # killed t2i + edit mid/after load: the leg downloaded to D: and ran from there — DiT
  # segmented prefetch read 11.36 GB at 5 MB/s (2048 s, D: USB HDD signature) and both
  # legs died right at/after load completion with no OS-level crash event. Rule
  # 2026-11-14 violated by the original leg. Fix = ONE factor changed: stage all 3 files
  # to C: NVMe (rule 2026-11-14), recipe otherwise VERBATIM (seed 42, deterministic).
  # baseline_qwen (DONE 11-21, C: NVMe models) stays the A/B reference. If verbatim t2i
  # still dies (fast this time = observable memory/Vulkan signature), a 4th sub-leg
  # retries t2i with --offload-to-cpu as the diagnostic variant.
  local D=D:/Modeles_LLM/MiniMax-H3-Image-GGUF
  local STAGE=C:/Modeles_LLM/MiniMax-H3-Image-GGUF
  mkdir -p "$STAGE"
  local free_kb need_kb=32000000
  free_kb=$(df --output=avail /c | tail -1 | tr -dc '0-9')
  if [ -z "$free_kb" ] || [ "$free_kb" -lt "$need_kb" ]; then
    log "[h3image_smoke] ABORT staging: C: free $((free_kb/1024)) MB < 32 GB required"
    return 1
  fi
  for f in minimax_h3_image_pruned-UD-Q3_K_XL.gguf qwen3vl_32b_minimax_h3-Q4_K_M.gguf h3_image_vae.safetensors; do
    if [ ! -f "$STAGE/$f" ]; then
      log "[h3image_smoke] staging D:→C: $f (~15 min, D: is a USB HDD)"
      cp "$D/$f" "$STAGE/$f" || { log "[h3image_smoke] staging FAILED for $f"; return 1; }
    fi
  done
  log "[h3image_smoke] staging OK (C: NVMe)"
  local PROMPT="A gothic cathedral at night lit by blue moonlight, heavy rain, dramatic volumetric fog, weathered stone gargoyles, cinematic composition, high detail"
  run_leg h3image_t2i "$SD" \
    --diffusion-model "$STAGE/minimax_h3_image_pruned-UD-Q3_K_XL.gguf" \
    --vae "$STAGE/h3_image_vae.safetensors" \
    --llm "$STAGE/qwen3vl_32b_minimax_h3-Q4_K_M.gguf" \
    -p "$PROMPT" -W 1024 -H 1024 --cfg-scale 1.0 --steps 6 \
    --sampling-method euler --sigmas minimax-h3-image --rng cpu --seed 42 \
    --output "$OUT/h3image_smoke/h3_t2i_1024.png"
  run_leg h3image_baseline_qwen "$SD" \
    --diffusion-model "$MODELES/qwen-image-2.1-UC-Q8_0.gguf" \
    --llm "$MODELES/Qwen3VL-8B-Instruct-Q4_K_M.gguf" \
    --vae "$MODELES/qwen_image_2.1_vae_bf16.safetensors" \
    -p "$PROMPT" -W 1024 -H 1024 --cfg-scale 6.0 --steps 40 \
    --sampling-method euler --rng cpu --seed 42 \
    --output "$OUT/h3image_smoke/qwen_t2i_1024.png"
  run_leg h3image_edit "$SD" \
    --diffusion-model "$STAGE/minimax_h3_image_pruned-UD-Q3_K_XL.gguf" \
    --vae "$STAGE/h3_image_vae.safetensors" \
    --llm "$STAGE/qwen3vl_32b_minimax_h3-Q4_K_M.gguf" \
    -r output/test_media_export_port/input/sticker_sain.png \
    -p "Edit <Picture 1>: replace the on-image text with SANTE CHECK, keep the original illustration style, colors and layout" \
    -W 1024 -H 1024 --cfg-scale 1.0 --steps 6 \
    --sampling-method euler --sigmas minimax-h3-image --rng cpu --seed 42 \
    --output "$OUT/h3image_smoke/h3_edit_sticker.png"
  if [ ! -f "$OUT/h3image_t2i/DONE" ]; then
    log "[h3image_smoke] verbatim t2i failed again — diagnostic variant --offload-to-cpu"
    run_leg h3image_t2i_offload "$SD" \
      --diffusion-model "$STAGE/minimax_h3_image_pruned-UD-Q3_K_XL.gguf" \
      --vae "$STAGE/h3_image_vae.safetensors" \
      --llm "$STAGE/qwen3vl_32b_minimax_h3-Q4_K_M.gguf" \
      --offload-to-cpu \
      -p "$PROMPT" -W 1024 -H 1024 --cfg-scale 1.0 --steps 6 \
      --sampling-method euler --sigmas minimax-h3-image --rng cpu --seed 42 \
      --output "$OUT/h3image_smoke/h3_t2i_1024_offload.png"
  fi
  echo "t2i=$(substat $OUT/h3image_t2i) baseline=$(substat $OUT/h3image_baseline_qwen) edit=$(substat $OUT/h3image_edit) t2i_offload=$(substat $OUT/h3image_t2i_offload)" > "$OUT/h3image_smoke/SUBSTATUS.txt"
  touch "$OUT/h3image_smoke/DONE"
}

inkling_srv_attempt() { # $1 = --n-cpu-moe value (or "none") — fork Vulkan llama-server.
  # §1.41 (11-21): the ONLY working fork path = llama-server + --no-mmproj-offload (fork
  # llama-mtmd-cli crashes at threadpool init, Vulkan AND CPU). Starts the server, waits
  # for "server is listening", runs the 2 QA fixtures, greps t/s, kills the server.
  # rc!=0 = attempt failed (next staged attempt takes over).
  local NM="$1"
  local SRV=/c/llama-cpp-unsloth-b12588/llama-server.exe
  local LD="$OUT/inkling_ad_q4k"
  local LOGF="$LD/server_moe${NM}.log"
  local ARGS=(-m "$INK_MODEL" --mmproj "$INK_MM" --no-mmproj-offload -ngl 99 -c 8192 --port 8490 --host 127.0.0.1 --temp 0.0)
  [ "$NM" != "none" ] && ARGS+=(--n-cpu-moe "$NM")
  "$SRV" "${ARGS[@]}" > "$LOGF" 2>&1 &
  local SPID=$!
  local up=0 i
  for i in $(seq 1 36); do
    kill -0 $SPID 2>/dev/null || break
    grep -q "server is listening" "$LOGF" 2>/dev/null && { up=1; break; }
    sleep 5
  done
  local RC=0
  if [ "$up" -eq 0 ]; then
    log "[inkling_ad_q4k] fork server did not start (moe=$NM) — tail:"
    tail -5 "$LOGF" | sed 's/^/    /'
    RC=1
  else
    INK_DEST="$LD" INK_PORT=8490 uv run python - <<'PYEOF' || RC=1
import base64, json, time, urllib.request, os
from pathlib import Path
dest = Path(os.environ["INK_DEST"])
jobs = [
    ("planche_byte10", Path("C:/GIT/ai-doc2video/.worktrees/byte-stories/branding/mascot/planche_mascotte_byte_10poses.png"),
     "Describe this contact sheet briefly. Then read ALL visible on-screen text exactly as written, including any French words."),
    ("moss_typo", Path("output/test_m1106/moss_1106.png"),
     "What text is written on this image? Read it exactly, character by character."),
]
ok = True
for name, img, prompt in jobs:
    b64 = base64.b64encode(img.read_bytes()).decode()
    body = json.dumps({"model": "inkling", "temperature": 0.0, "max_tokens": 300,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": prompt}]}]}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{os.environ['INK_PORT']}/v1/chat/completions",
                                 data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            out = json.load(r)
        msg = out["choices"][0]["message"]
        text = msg.get("content") or msg.get("reasoning_content", "")
        wall = time.time() - t0
        (dest / f"adq4k_{name}.log").write_text(f"wall={wall:.1f}s\n---CONTENT---\n{text}\n", encoding="utf-8")
        print(f"OK {name} wall={wall:.1f}s")
    except Exception as e:
        ok = False
        (dest / f"adq4k_{name}.FAIL").write_text(f"after {time.time()-t0:.1f}s: {e}", encoding="utf-8")
        print(f"FAIL {name}: {e}")
raise SystemExit(0 if ok else 1)
PYEOF
    grep -E "prompt_eval time|eval time|tokens per second" "$LOGF" | tail -8 > "$LD/ts_moe${NM}.txt" 2>/dev/null || true
    kill $SPID 2>/dev/null
    sleep 2
    kill -9 $SPID 2>/dev/null
  fi
  return $RC
}

leg_inkling_ad_q4k() {
  # Inkling-2-Mini — re-test of the NEW AD-Q4_K quant (user request 11-22 « Ajoute le
  # test du nouveau modele C:\Modeles_LLM\Inkling-2-Mini » — 16.53 GB + mmproj F16,
  # downloaded 11-22 01:07, ALREADY on C: NVMe = no staging needed). Prior art §1.41
  # (11-21): UD-Q3_K_XL tested → quality TIE with Qwen3VL-8B but cost ×5-6 (planche
  # 363 s / 5.89 t/s vision, mmproj CPU + looped arch) → NOT promoted; mainline
  # b12606/b12608 REFUSE the unsloth quants (pre-#32704 re-share, #32704 absent from
  # b12608). Tonight's questions: ① does mainline b12608 accept the AD-Q4_K layout?
  # ② fork Vulkan path (known-good): staged --n-cpu-moe 8→16→24 (16.53 GB > 16 GB VRAM,
  # experts to CPU) — quality datapoint on a higher-fidelity quant, SAME fixtures +
  # SAME prompts as 11-21 = comparable (Q3_K_XL: planche 363 s; Qwen3VL-8B: 69.5 s).
  local INKC=C:/Modeles_LLM/Inkling-2-Mini
  INK_MODEL="$INKC/Inkling-2-Mini-AD-Q4_K.gguf"
  INK_MM="$INKC/mmproj-Inkling-2-Mini-F16.gguf"
  mkdir -p "$OUT/inkling_ad_q4k"
  if [ ! -f "$INK_MODEL" ] || [ ! -f "$INK_MM" ]; then
    # 11-22 triage moved the folder cold to D: — re-stage D:→C: identical structure
    # (zero config change) per the triage policy, moss-leg staging pattern.
    local INKD=D:/Modeles_LLM/Inkling-2-Mini
    local free_kb need_kb=18000000
    free_kb=$(df --output=avail /c | tail -1 | tr -dc '0-9')
    if [ -z "$free_kb" ] || [ "$free_kb" -lt "$need_kb" ]; then
      log "[inkling_ad_q4k] ABORT staging: C: free $((free_kb/1024)) MB < 18 GB required"
      return 1
    fi
    mkdir -p "$INKC"
    for f in "$(basename "$INK_MODEL")" "$(basename "$INK_MM")"; do
      if [ ! -f "$INKD/$f" ]; then log "[inkling_ad_q4k] ABORT: $f missing on D: too"; return 1; fi
      log "[inkling_ad_q4k] staging D:→C: $f (~17 GB USB HDD, ~5-20 min)"
      cp "$INKD/$f" "$INKC/$f" || { log "[inkling_ad_q4k] staging FAILED for $f"; return 1; }
    done
    log "[inkling_ad_q4k] staging OK (C: NVMe)"
  fi
  # Phase A — mainline b12608 load probe (typo fixture, staged --n-cpu-moe 16 because
  # 16.53 GB > 16 GB VRAM: an arch refusal and a VRAM overflow must stay distinguishable)
  run_leg inkling_ad_mainline /c/llama.cpp/llama-mtmd-cli.exe \
    -m "$INK_MODEL" --mmproj "$INK_MM" --n-cpu-moe 16 \
    --image output/test_m1106/moss_1106.png --temp 0.0 -n 260 -c 8192 \
    -p "What text is written on this image? Read it exactly, character by character."
  if [ -f "$OUT/inkling_ad_mainline/DONE" ]; then
    # mainline accepts the AD layout → complete the fixture pair on mainline, fork not needed
    run_leg inkling_ad_planche_mainline /c/llama.cpp/llama-mtmd-cli.exe \
      -m "$INK_MODEL" --mmproj "$INK_MM" --n-cpu-moe 16 \
      --image "C:/GIT/ai-doc2video/.worktrees/byte-stories/branding/mascot/planche_mascotte_byte_10poses.png" \
      --temp 0.0 -n 260 -c 8192 \
      -p "Describe this contact sheet briefly. Then read ALL visible on-screen text exactly as written, including any French words."
  else
    # Phase B — fork Vulkan llama-server, staged expert offload
    run_leg inkling_ad_srv_moe8  inkling_srv_attempt 8   || true
    if [ ! -f "$OUT/inkling_ad_srv_moe8/DONE" ]; then
      run_leg inkling_ad_srv_moe16 inkling_srv_attempt 16  || true
    fi
    if [ ! -f "$OUT/inkling_ad_srv_moe8/DONE" ] && [ ! -f "$OUT/inkling_ad_srv_moe16/DONE" ]; then
      run_leg inkling_ad_srv_moe24 inkling_srv_attempt 24  || true
    fi
  fi
  echo "mainline=$(substat $OUT/inkling_ad_mainline) planche_mainline=$(substat $OUT/inkling_ad_planche_mainline) srv_moe8=$(substat $OUT/inkling_ad_srv_moe8) srv_moe16=$(substat $OUT/inkling_ad_srv_moe16) srv_moe24=$(substat $OUT/inkling_ad_srv_moe24)" > "$OUT/inkling_ad_q4k/SUBSTATUS.txt"
  touch "$OUT/inkling_ad_q4k/DONE"
}

leg_sous_titres_smoke() {
  # PR #44 §6 real-path closure (pending since the 11-22 merge — gate was red ×3 at
  # merge time on user GPU workload 90-99.7 %; commands verbatim from the PR body).
  # align mode on the validated ono clip: expect EXACTLY the 15 transcript words,
  # timestamps ≈ words_v2_ono.json (§1.68). + asr mode on the dylan 16.16 s clip
  # (> 15 s = Silero VAD chunking exercised, word-exact transcript §1.68).
  run_leg sous_titres_smoke_align \
    uv run python main.py -w sous_titres \
      --audio output/test_forced_aligner_20261121/qwentts_ono_anna.wav \
      -p "L'héritier du vide s'éveille sous la forteresse, et le vent gris hurle dans les remparts." \
      -o smoke_ono_align
  run_leg sous_titres_smoke_asr \
    uv run python main.py -w sous_titres --st-mode asr \
      --audio output/test_forced_aligner_20261121/qwentts_dylan_long.wav \
      -o smoke_dylan_asr
  for f in output/sous_titres/smoke_ono_align.srt output/sous_titres/smoke_ono_align_words.json \
           output/sous_titres/smoke_dylan_asr.srt output/sous_titres/smoke_dylan_asr_words.json \
           output/sous_titres/smoke_dylan_asr_transcript.txt; do
    [ -f "$f" ] && cp "$f" "$OUT/sous_titres_smoke_align/" 2>/dev/null
  done
  echo "align=$(substat $OUT/sous_titres_smoke_align) asr=$(substat $OUT/sous_titres_smoke_asr)" > "$OUT/sous_titres_smoke/SUBSTATUS.txt"
  touch "$OUT/sous_titres_smoke/DONE"
}

leg_sweep_1116() {
  # master-1116 pin validation (GO user 22-11 soir): the archs NOT covered by the day
  # smokes (SDXL/qwen done). Flux = the 1063-era flags verbatim; moss = factory t2i
  # (untested arch since 1106); upscale = esrgan; music_bg = ace-step via audio.cpp
  # 0.9.6 (doubles as the audio.cpp factory validation); h3 video = the PROD workflow
  # real path (~17 min, 66-67 s/it band). Evidence per sub-leg in output/tests_nuit/.
  run_leg sweep_flux_1116 "$SD" \
    -m "$MODELES/flux1-dev-Q6_K.gguf" \
    --vae "$MODELES/ae.safetensors" \
    --clip_l "$MODELES/clip_l.safetensors" \
    --t5xxl "$MODELES/t5xxl_fp16.safetensors" \
    -p "a gothic cathedral at night lit by blue moonlight, heavy rain, dramatic volumetric fog, cinematic composition, high detail" \
    -W 1024 -H 1024 --steps 4 --cfg-scale 1.0 --guidance 3.5 \
    --vae-tiling --sampling-method euler --rng cpu --seed 42 \
    --output "$OUT/sweep_1116/flux_1024.png"
  run_leg sweep_moss_1116 \
    uv run python main.py -w moss_image \
    -p "a weathered medieval bronze shield with the text MOSS engraved, game asset, centered" \
    -o nuit_moss_1116
  run_leg sweep_upscale_1116 \
    uv run python main.py -w upscale \
    -i output/test_m1116/sdxl_smoke_2.png --upscale -o nuit_upscale_1116
  run_leg sweep_music_1116 \
    uv run python main.py -w music_bg -o nuit_music_1116
  run_leg sweep_h3video_1116 \
    uv run python main.py -w h3_ref2va \
    -i output/test_p1_final/h3_source_avec_audio.mp4 \
    -p "the camera continues its slow push-in on the helmet, dust motes drifting, <Video 1>" \
    --turbo
  echo "flux=$(substat $OUT/sweep_flux_1116) moss=$(substat $OUT/sweep_moss_1116) upscale=$(substat $OUT/sweep_upscale_1116) music=$(substat $OUT/sweep_music_1116) h3video=$(substat $OUT/sweep_h3video_1116)" > "$OUT/sweep_1116/SUBSTATUS.txt"
  touch "$OUT/sweep_1116/DONE"
}

leg_inkling_q4_unsloth() {
  # Inkling quality Q4 (GO user 22-11 soir — the morning "wait for #32704" decision is
  # settled: b12633 carries the fix and the unsloth mainline Q3 layout validated 10/10
  # this evening at 39.1 s/planche). This leg downloads the unsloth Mainline_Support
  # UD-Q4_K_XL (17.63 GB, KLD 0.0107 / 98.0% top-token) and runs the SAME 2 fixtures
  # = the Q4-vs-Q3 quality datapoint for the fleet decision.
  local DQ=D:/Modeles_LLM/Inkling-2-Mini-Mainline
  mkdir -p "$DQ" "$OUT/inkling_q4"
  if [ ! -f "$DQ/Inkling-2-Mini-UD-Q4_K_XL.gguf" ]; then
    log "[inkling_q4] download unsloth Mainline_Support UD-Q4_K_XL (17.63 GB)"
    uv run python scripts/telecharger_gros_fichier_parallele.py \
      "https://huggingface.co/unsloth/Inkling-2-Mini-GGUF/resolve/main/Mainline_Support/Inkling-2-Mini-UD-Q4_K_XL.gguf_file" \
      "$DQ/Inkling-2-Mini-UD-Q4_K_XL.gguf" || return 1
  fi
  INK_MODEL="$DQ/Inkling-2-Mini-UD-Q4_K_XL.gguf" \
  INK_MM="D:/Modeles_LLM/Inkling-2-Mini/mmproj-Inkling-2-Mini-F16.gguf" \
  PROBE_OUT="$OUT/inkling_q4" \
  INK_TAG="q4" \
  bash output/tests_nuit/probe_inkling_mainline_srv.sh
  touch "$OUT/inkling_q4/DONE"
}

leg_build_validation_html() {
  # Regenerate the validation page AFTER the night legs so the morning verdict page
  # includes tonight's evidence (Inkling #32704 readings, qwen 1116 render, sweep).
  run_leg build_validation_html \
    uv run --no-project python -I output/tests_nuit/build_validation_html_20261122.py
}

leg_sweep1116_fix() {
  # Morning-of-11-23 repairs for the 11-22 night sweep failures (all planning errors,
  # no 1116 regression proven): (a) flux = --clip-l/--distilled-guidance-scale renamed
  # --clip_l/--guidance in 1116 (#2396 CLI break) — retry already measured 27.74 s PASS
  # in the 11-23 day window (output/test_m1116/flux_1024_retry.png), recorded here as a
  # 2 s marker leg for the report. (b) moss = Vulkan device-lost at VAE decode on the
  # FIRST moss run since the 1091 sweep (lesson 11-05: never diagnose a regression from
  # a first failure) — clean re-run; the workflow stages its own NVMe copies. (c) music
  # = ACE-Step moved cold to D: by the 11-22 triage and music_bg has NO NVMe staging —
  # this leg stages it back to C: first (self-contained).
  mkdir -p "$OUT/sweep_1116"
  echo "flux retry 27.74s PASS (flags --clip_l + --guidance), evidence output/test_m1116/flux_1024_retry.png" > "$OUT/sweep_1116/flux_retry.txt"
  run_leg sweep_music_1116_retry bash -c '
    set -e
    if [ ! -f /c/Modeles_LLM/ACE-Step1.5-GGUF/turbo/ace-step-1.5-turbo-bf16.gguf ]; then
      echo "[staging] ACE-Step D:->C: (~24 GB, USB ~15 min)"
      rm -rf /c/Modeles_LLM/ACE-Step1.5-GGUF
      cp -a /d/Modeles_LLM/ACE-Step1.5-GGUF /c/Modeles_LLM/
    fi
    cd /c/GIT/generator-assets
    uv run python main.py -w music_bg -o nuit_music_1116
  '
  run_leg sweep_moss_1116_retry \
    uv run python main.py -w moss_image \
    -p "a weathered medieval bronze shield with the text MOSS engraved, game asset, centered" \
    -o nuit_moss_1116_retry
  echo "music=$(substat $OUT/sweep_music_1116_retry) moss=$(substat $OUT/sweep_moss_1116_retry)" > "$OUT/sweep_1116/SUBSTATUS.txt"
  touch "$OUT/sweep_1116/DONE"
}

leg_h3video_1106_ab() {
  # The 11-22 night h3video leg PASSED but at 1934 s (32.2 min) vs the 17-min band
  # (1039-1078 s) measured on 1050/1063 warm-machine runs. One factor changed since:
  # the binary 1063->1116. This leg A/Bs the SAME workflow on the 1106 backup binary
  # in the CURRENT machine state (lesson 10-11: re-run the OLD binary before calling
  # it a regression). Swap-in guarded, ALWAYS restored (trap + post-check).
  local OLD=/c/SD/backups/backup_20261116_195416/sd-cli.exe
  local CUR=/c/SD/sd-cli.exe
  local SAVE=/c/SD/sd-cli_1116_ab_save.exe
  if [ ! -f "$OLD" ]; then log "[h3video_1106_ab] ABORT: 1106 backup binary missing"; return 1; fi
  run_leg h3video_1106_run bash -c "
    set -e
    cp \"$CUR\" \"$SAVE\"
    cp \"$OLD\" \"$CUR\"
    trap 'cp \"$SAVE\" \"$CUR\" 2>/dev/null' EXIT
    cd /c/GIT/generator-assets
    uv run python main.py -w h3_ref2va \
      -i output/test_p1_final/h3_source_avec_audio.mp4 \
      -p 'the camera continues its slow push-in on the helmet, dust motes drifting, <Video 1>' \
      --turbo -o nuit_h3_1106_ab
    cp \"$SAVE\" \"$CUR\"
    trap - EXIT
  "
  if ! cmp -s "$CUR" /c/SD/sd-cli.exe 2>/dev/null; then :; fi
  if [ -f "$SAVE" ] && ! cmp -s "$CUR" "$SAVE"; then
    cp "$SAVE" "$CUR"
    log "[h3video_1106_ab] binary RESTORED to 1116 (guard fired)"
  fi
  rm -f "$SAVE"
  mkdir -p "$OUT/h3video_1106_ab"
  local d1116 d1106
  d1116=$(cat "$OUT/sweep_h3video_1116/duree.txt" 2>/dev/null || echo "?")
  d1106=$(cat "$OUT/h3video_1106_run/duree.txt" 2>/dev/null || echo "?")
  echo "h3_1116=${d1116}s h3_1106=${d1106}s (band 1050/1063: 1039-1078s warm) — 1116 >1.5x slower = real regression to report upstream; parity = the 11-22 night was machine-state" > "$OUT/h3video_1106_ab/SUMMARY.txt"
  cat "$OUT/h3video_1106_ab/SUMMARY.txt"
}

leg_moss_4step_lora() {
  # §1.45 follow-up — user 23-11 « mets ça pour la nuit »: lvladikov/MOSS-SFT-Distill-4step-LoRA
  # (eDMD + small adversarial critic distilling the 50-step CFG-3 teacher into 4 steps at CFG 1;
  # rank 64, 252 modules, Apache-2.0, chk00030000). SHA256 verified vs upstream checkpoint_info.md
  # (51fb026b...). A/B seed 42 @1024² vs the validated 50-step baseline (§1.45 recipe verbatim:
  # euler, CFG 3.0, --fa, all resident — do NOT offload). Prior art: DMD-8step 27-10 = LoRA
  # at_runtime costs ~3.1x per step on the q8_0 base → expected wall gain ~÷4 (4 steps), NOT the
  # ÷14 CUDA claim. Gotchas: (1) the trained sigma schedule (1.0/0.910/0.717/0.024) has no sd-cli
  # preset — euler default instead (the DMD 8-step tolerated the same mismatch); (2) strength 1.0
  # STRICT (above doubles edges); (3) exact/diffusers-key variant used with --lora-apply-mode auto
  # (HyperFlow A/B precedent 10-20); if 0 tensors match, the morning retry uses the _comfyui file
  # (same tensors, alpha ×1.12 = ComfyUI compensation — the exact file is the right one for sd-cli).
  # Staging D:→C: per rule 2026-11-14 (~16 GB; the factory _tmp_moss dir holds the WRONG base —
  # UD-Q4_K_XL DiT from the 11-22 sweep, not the validated Q8_0). Staged files stay on C: for the
  # morning verdict loop; cleanup decided with the user verdict.
  local D=D:/Modeles_LLM
  local STAGE=C:/Modeles_LLM/moss-4step
  mkdir -p "$STAGE/lora" "$OUT/moss_4step_lora"
  local free_kb need_kb=20000000
  free_kb=$(df --output=avail /c | tail -1 | tr -dc '0-9')
  if [ -z "$free_kb" ] || [ "$free_kb" -lt "$need_kb" ]; then
    log "[moss_4step_lora] ABORT staging: C: free $((free_kb/1024)) MB < 20 GB required"
    return 1
  fi
  for f in MOSS-Image-SFT-Q8_0.gguf Qwen3.5-9B-Q8_0.gguf moss_image_vae_flux2.safetensors moss_image_tokenizer.json; do
    if [ ! -f "$STAGE/$f" ]; then
      log "[moss_4step_lora] staging D:→C: $f (~10 min, D: is a USB HDD)"
      cp "$D/$f" "$STAGE/$f" || { log "[moss_4step_lora] staging FAILED for $f"; return 1; }
    fi
  done
  if [ ! -f "$D/moss-4step-lora/moss_sft_4step_rank_64_lora.safetensors" ]; then
    log "[moss_4step_lora] ABORT: LoRA missing on D: (downloaded 23-11, sha256 51fb026b)"; return 1
  fi
  cp "$D/moss-4step-lora/moss_sft_4step_rank_64_lora.safetensors" "$STAGE/lora/"
  log "[moss_4step_lora] staging OK (C: NVMe)"
  local PROMPT="a weathered medieval bronze shield with the text MOSS engraved, game asset, centered"
  local COMMON="--diffusion-model $STAGE/MOSS-Image-SFT-Q8_0.gguf --llm $STAGE/Qwen3.5-9B-Q8_0.gguf --vae $STAGE/moss_image_vae_flux2.safetensors --tokenizer $STAGE/moss_image_tokenizer.json -W 1024 -H 1024 -s 42 --fa"
  # leg 1 — baseline: validated 50-step teacher (§1.45), seed 42 (~36 min)
  run_leg moss4_base50 "$SD" $COMMON \
    -p "$PROMPT" --cfg-scale 3.0 --sampling-method euler --steps 50 \
    --output "$OUT/moss_4step_lora/moss4_base50.png"
  # leg 2 — LoRA 4 steps CFG 1 (card recipe; strength 1.0 strict) (~3-9 min)
  run_leg moss4_lora_step4 "$SD" $COMMON \
    --lora-model-dir "$STAGE/lora" --lora-apply-mode auto \
    -p "$PROMPT <lora:moss_sft_4step_rank_64_lora:1>" \
    --cfg-scale 1.0 --sampling-method euler --steps 4 \
    --output "$OUT/moss_4step_lora/moss4_lora_step4.png"
  # leg 3 — fallback 8 steps CFG 1 (card: "also runs at 6/8 steps") — quality fallback
  # if the euler-default 4-step sigma mismatch degrades vs the trained schedule
  run_leg moss4_lora_step8 "$SD" $COMMON \
    --lora-model-dir "$STAGE/lora" --lora-apply-mode auto \
    -p "$PROMPT <lora:moss_sft_4step_rank_64_lora:1>" \
    --cfg-scale 1.0 --sampling-method euler --steps 8 \
    --output "$OUT/moss_4step_lora/moss4_lora_step8.png"
  # A/B planche for the morning verdict (3-up side-by-side; non-fatal if ffmpeg fails)
  ffmpeg -y -loglevel error \
    -i "$OUT/moss_4step_lora/moss4_base50.png" \
    -i "$OUT/moss_4step_lora/moss4_lora_step4.png" \
    -i "$OUT/moss_4step_lora/moss4_lora_step8.png" \
    -filter_complex "[0][1][2]hstack=3" \
    "$OUT/moss_4step_lora/moss4_planche_ab.png" || true
}

leg_sweep_1127() {
  # master-1127 pin validation (GO user 25-11 "Go tout"): the day smoke on 1127 covered
  # the moss real path ONLY (output/test_m1127_moss_lora/) — lesson 10-30: a binary update
  # whose smokes don't span ALL archs must run the missing archs' real paths. This leg
  # spans SDXL / qwen turbo / flux / upscale / music / LTX 33f + h3video --turbo, the
  # latter doubling as the issue #2417 datapoint on 1127 (DiT expected still ~130 s/it
  # until an upstream fix; the 1050/1063 healthy band is 66.5-67.05 s/it).
  mkdir -p "$OUT/sweep_1127"
  run_leg sweep_sdxl_1127 "$SD" \
    -m "$MODELES/juggernautXL_ragnarok.safetensors" \
    -p "a gothic cathedral at night lit by blue moonlight, dramatic volumetric fog, cinematic composition, high detail" \
    -W 512 -H 512 --steps 20 --cfg-scale 7 \
    --sampling-method euler_a --rng cpu --seed 42 \
    --output "$OUT/sweep_1127/sdxl_512.png"
  run_leg sweep_qwen_1127 \
    uv run python main.py -w qwen_image --qwen-turbo \
    -p 'a cinematic movie poster, bold typography reading "The Sleeping Dragon", a coiled dragon silhouette under the title, dramatic lighting' \
    --seed 42 -o nuit_qwen_1127
  run_leg sweep_flux_1127 "$SD" \
    -m "$MODELES/flux1-dev-Q6_K.gguf" \
    --vae "$MODELES/ae.safetensors" \
    --clip_l "$MODELES/clip_l.safetensors" \
    --t5xxl "$MODELES/t5xxl_fp16.safetensors" \
    -p "a gothic cathedral at night lit by blue moonlight, heavy rain, dramatic volumetric fog, cinematic composition, high detail" \
    -W 1024 -H 1024 --steps 4 --cfg-scale 1.0 --guidance 3.5 \
    --vae-tiling --sampling-method euler --rng cpu --seed 42 \
    --output "$OUT/sweep_1127/flux_1024.png"
  run_leg sweep_upscale_1127 \
    uv run python main.py -w upscale \
    -i output/test_m1116/sdxl_smoke_2.png --upscale -o nuit_upscale_1127
  run_leg sweep_music_1127 \
    uv run python main.py -w music_bg -o nuit_music_1127
  run_leg sweep_ltx33_1127 \
    "$SD" -M vid_gen \
      --diffusion-model "$MODELES/LTX-2.5-Distilled-Q4_K_M.gguf" \
      --vae "$MODELES/ltx-2.5-video-vae-conv-bf16.safetensors" \
      --llm "$MODELES/gemma4-12b-with-proj-ltx-2.5-Q5_K_M.gguf" \
      -p "Cinematic wide tracking shot, a colossal golden dragon with shimmering scales soaring majestically through sunset clouds, volumetric rays, high quality, 8k" \
      -W 768 -H 512 --video-frames 33 --fps 24 \
      --steps 2 --sampling-method euler_a --cfg-scale 1.0 \
      --diffusion-fa --seed 42 -t 12 \
      --backend "diffusion=vulkan0,te=cpu" -v \
      -o "$OUT/sweep_1127/ltx33_nuit.webm"
  run_leg sweep_h3video_1127 \
    uv run python main.py -w h3_ref2va \
    -i output/test_p1_final/h3_source_avec_audio.mp4 \
    -p "the camera continues its slow push-in on the helmet, dust motes drifting, <Video 1>" \
    --turbo -o nuit_h3_1127
  echo "sdxl=$(substat $OUT/sweep_sdxl_1127) qwen=$(substat $OUT/sweep_qwen_1127) flux=$(substat $OUT/sweep_flux_1127) upscale=$(substat $OUT/sweep_upscale_1127) music=$(substat $OUT/sweep_music_1127) ltx33=$(substat $OUT/sweep_ltx33_1127) h3video=$(substat $OUT/sweep_h3video_1127)" > "$OUT/sweep_1127/SUBSTATUS.txt"
  touch "$OUT/sweep_1127/DONE"
}

leg_sam_vulkan_v095() {
  # SAM Audio Vulkan — version-bound retest (rule 2026-11-05): the
  # FAIL_MACHINE_STATE verdict was measured on v0.9.0 (09-28, monolithic
  # encoder buffer > AMD driver limit); audio.cpp is now v0.9.5 (11-14).
  # PASS = SAM on Vulkan unlocked (CPU recipe RTF 2.9 reference). ~3 min.
  run_leg sam_vulkan_v095 \
    C:/audio-cpp/audiocpp_cli.exe --task s2s --family sam_audio \
      --model "$MODELES/SAM-Audio-GGUF/sam-audio-small-q8_0.gguf" \
      --backend vulkan --audio output/test_sam_audio/sample_chanson_30s.wav \
      --text "the singing voice" --seed 42 \
      --out-dir "$OUT/sam_vulkan_v095/"
  if [ -f "$OUT/sam_vulkan_v095/FAIL" ] && grep -q "ErrorOutOfDeviceMemory" "$OUT/sam_vulkan_v095/run.log" 2>/dev/null; then
    mv "$OUT/sam_vulkan_v095/FAIL" "$OUT/sam_vulkan_v095/FAIL_MACHINE_STATE"
    log "[sam_vulkan_v095] OOM signature still present on v0.9.5 → FAIL_MACHINE_STATE"
  fi
}

leg_flashhead_v095_probe() {
  # SoulX-FlashHead talking-portrait — version-bound retest: BLOCKED on v0.9.4
  # (Vulkan IM2COL_3D missing at ltx_video_vae.encode, §MEMORY_BANK) and the
  # re-test trigger is "next audio.cpp release". Cheap 3 s probe: the failure
  # signature (IM2COL_3D or progress) answers whether v0.9.5 carries it.
  # Assets kept on disk from the 0.9.4 test (portrait + 12 s wav). ~3 min.
  run_leg flashhead_v095_probe \
    C:/audio-cpp/audiocpp_cli.exe --task sfx --family soulx_flashhead \
      --model "$MODELES/SoulX-FlashHead-GGUF/SoulX-FlashHead-Lite-Q8_0.gguf" \
      --backend vulkan \
      --request-option "reference_image_file=$REPO/output/test_flashhead_v094/portrait.png" \
      --request-option "height=512" --request-option "width=512" \
      --request-option "seed=42" \
      --audio "$REPO/output/test_flashhead_v094/english_12s.wav" \
      --out-dir "$OUT/flashhead_v095_probe/"
  if [ -f "$OUT/flashhead_v095_probe/FAIL" ] && grep -q "IM2COL_3D" "$OUT/flashhead_v095_probe/run.log" 2>/dev/null; then
    log "[flashhead_v095_probe] IM2COL_3D still missing on v0.9.5 — stays blocked, marker kept as datapoint"
  fi
}

leg_qwen3_align_v095() {
  # Qwen3-ForcedAligner 0.6B — NEW capability probe: the family spec ships in
  # audio.cpp v0.9.5 (qwen3_forced_aligner.json, task align) and the GGUFs
  # landed in the audio.cpp-gguf monorepo on 11-20 (watch). Forced alignment =
  # doc2video subtitle timing. Download q8_0 (~1.1 GB) then align the 0.9.4
  # demo transcript against its wav. ~10 min.
  local gguf="$MODELES/Qwen3-ForcedAligner-0.6B-GGUF/qwen3-forced-aligner-0.6b-q8_0.gguf"
  mkdir -p "$MODELES/Qwen3-ForcedAligner-0.6B-GGUF" "$OUT/qwen3_align_v095"
  if [ ! -f "$gguf" ]; then
    log "[qwen3_align_v095] downloading the q8_0 aligner (~1.1 GB)…"
    uv run python scripts/telecharger_gros_fichier_parallele.py \
      "https://huggingface.co/audio-cpp/audio.cpp-gguf/resolve/main/Qwen3-ForcedAligner-0.6B-GGUF/qwen3-forced-aligner-0.6b-q8_0.gguf" \
      "$gguf" > "$OUT/qwen3_align_v095/download.log" 2>&1 \
      || { log "[qwen3_align_v095] download failed (transient?) — no marker, retry next night"; return 0; }
  fi
  run_leg qwen3_align_v095 \
    C:/audio-cpp/audiocpp_cli.exe --task align --family qwen3_forced_aligner \
      --model "$gguf" \
      --backend vulkan \
      --audio "$REPO/output/test_flashhead_v094/english.wav" \
      --text "$(cat "$REPO/output/test_flashhead_v094/english.txt")" \
      --language en \
      --seed 42 \
      --out-dir "$OUT/qwen3_align_v095/" \
      --words-out "$OUT/qwen3_align_v095/words.json" \
      --segments-out "$OUT/qwen3_align_v095/segments.json"
}

leg_fruc_vs_mci() {
  # ffmpeg 9.1 new filter fruc_vulkan (frame-rate up-conversion). EXPECTED to
  # fail on AMD: it drives the Vulkan NV optical flow extension (NVIDIA
  # hardware path) — the honest datapoint documents whether ANY fruc mode runs
  # on RDNA2. Baseline for comparison: the mci/aobmc ralenti master 11-20.
  # ~5 min.
  run_leg fruc_vs_mci \
    C:/ffmpeg/dist/bin/ffmpeg.exe -y -v error \
      -i "$REPO/output/dance_m1106v2_brut.webm" \
      -vf "fruc_vulkan=fps=48" -an \
      -c:v libx264 -preset fast \
      "$OUT/fruc_vs_mci/fruc_48fps.mp4"
  if [ -f "$OUT/fruc_vs_mci/DONE" ]; then
    planche "$OUT/fruc_vs_mci/fruc_48fps.mp4" "$OUT/fruc_vs_mci/planche.png" 7 || true
  fi
}

# ------------------------------------------------- LLM leg (added 23-11 soir, GO user « si des tests llm ajoute les à la nuit »)

leg_llm_lfm3_17b() {
  # LFM3-1.7B (LiquidAI) — hottest text LLM of the HF GGUF trending (445k dl, ♥330),
  # arch `lfm3` PRESENT in the b12651 binary (7 string hits in llama.dll). Two open
  # questions: ① does the fresh binary load and run the new family at speed (smoke
  # recipe identical to the LFM2.5 smoke: -ngl 99 -st -n 40; reference band 181-217
  # t/s on the 8B-A1B MoE)? ② translate-path candidate: LFM2.5-8B-A1B Q6_K drives
  # trad-fr-to-en (/translate :8077) — can a 1.7B dense model produce a usable FR→EN
  # translation at temp 0? Side-by-side output texts for the MORNING USER VERDICT
  # (text quality = eye judgment, not a marker). Q8_0 = near-lossless reference quant
  # (~1.9 GB, small candidate → straight to C:, no D: master yet). Skipped by triage
  # tonight: CCORE-Web-Coder (no local code-LLM need), LingSante-3.1-flash (0 dl),
  # Llama-3.1-8B (2024, nothing to gain), Qwen3.8-27B-NVFP4-QAD (NVFP4 CUDA/HIP-first,
  # RDNA2 Vulkan undemonstrated + >16 GB VRAM offload + no need).
  local G=C:/Modeles_LLM/LFM3-1.7B-GGUF/LFM3-1.7B-Q8_0.gguf
  local BASE=C:/Modeles_LLM/LFM2.5-8B-A1B-Q6_K.gguf
  mkdir -p "$OUT/llm_lfm3_17b" "$(dirname "$G")"
  if [ ! -f "$G" ]; then
    log "[llm_lfm3_17b] downloading LFM3-1.7B-Q8_0…"
    uv run python scripts/telecharger_gros_fichier_parallele.py \
      "https://huggingface.co/LiquidAI/LFM3-1.7B-GGUF/resolve/main/LFM3-1.7B-Q8_0.gguf" "$G" \
      > "$OUT/llm_lfm3_17b/download.log" 2>&1 || { log "[llm_lfm3_17b] download failed (transient) — no marker, retry next night"; return 0; }
  fi
  # ① smoke + throughput (band reference: LFM2.5-8B-A1B 181-217 t/s generation)
  run_leg lfm3_smoke /c/llama.cpp/llama-cli.exe -m "$G" -ngl 99 -st -n 40 \
    -p "Write a one-sentence haiku about autumn rain."
  # ② FR→EN side-by-side vs the production translate engine, identical prompt, temp 0
  #    (task text written to a file: real French accents + apostrophe survive the quoting)
  local TF="$OUT/llm_lfm3_17b/task.txt"
  printf '%s' "Translate this French sentence to English. Output only the translation: Le vieux forgeron dort debout près de la forge abandonnée, la main encore nouée autour du marteau de fer qui l'a ruiné." > "$TF"
  run_leg lfm3_fr2en  bash -c "cat '$TF' | /c/llama.cpp/llama-cli.exe -m '$G'    -ngl 99 -st -n 200 --temp 0 > '$OUT/llm_lfm3_17b/fr2en_lfm3.txt' 2>&1"
  run_leg lfm25_fr2en bash -c "cat '$TF' | /c/llama.cpp/llama-cli.exe -m '$BASE' -ngl 99 -st -n 200 --temp 0 > '$OUT/llm_lfm3_17b/fr2en_lfm25.txt' 2>&1"
  echo "smoke=$(substat $OUT/lfm3_smoke) fr2en_lfm3=$(substat $OUT/lfm3_fr2en) fr2en_lfm25=$(substat $OUT/lfm25_fr2en)" > "$OUT/llm_lfm3_17b/SUBSTATUS.txt"
  touch "$OUT/llm_lfm3_17b/DONE"
}

# --------------------------------------- Craft suite legs (added 23-11 soir, GO user « n'hésite pas ajouter des tests »)

leg_craft_designcraft_sheet() {
  # designcraft 0.21.1 update test — the NEW `place.contactSheet` command (File › Place
  # Contact Sheet, released in 0.21.0): file.new → place.load (3 deterministic frames
  # extracted in-leg from our dance webm) → place.contactSheet → export PNG. Morning
  # comparison vs the ffmpeg montage built in-leg (feature test + planche-pattern §1.55
  # comparison at the eye). Paths resolved with sort -V (lexical sort would pick 0.9.0
  # over 0.25.x — the 10-22 manager bug, same class). App updated tonight 0.20.1→0.21.1.
  local DC=$(ls -d D:/CraftApps/designcraft/designcraft-*-windows-x64-portable 2>/dev/null | sort -V | tail -1)
  local F="$OUT/craft_designcraft_sheet"
  # craft CLIs are Windows apps: JSON-embedded POSIX paths (/c/...) defeat the MSYS
  # argument conversion (night 23-11: os error 3) — embed cygpath -m (C:/) forms only.
  local FW=$(cygpath -m "$F")
  mkdir -p "$F"
  if [ ! -d "$DC" ]; then log "[craft_designcraft_sheet] ABORT: designcraft install dir not found"; return 1; fi
  local SRC="$REPO/output/dance_m1106v2_brut.webm"
  if [ ! -f "$SRC" ]; then log "[craft_designcraft_sheet] ABORT: source webm missing ($SRC)"; return 1; fi
  C:/ffmpeg/dist/bin/ffmpeg.exe -y -loglevel error \
    -ss 0.5  -i "$SRC" -frames:v 1 "$F/frame_a.png" \
    -ss 1.5  -i "$SRC" -frames:v 1 "$F/frame_b.png" \
    -ss 2.5  -i "$SRC" -frames:v 1 "$F/frame_c.png" \
    || { log "[craft_designcraft_sheet] ABORT: frame extraction failed"; return 1; }
  run_leg dc_sheet "$DC/designcraft-cli.exe" run \
    --cmd 'file.new={}' \
    --cmd "place.load={\"files\":[{\"path\":\"$FW/frame_a.png\"},{\"path\":\"$FW/frame_b.png\"},{\"path\":\"$FW/frame_c.png\"}]}" \
    --cmd 'place.contactSheet={"columns":3,"rows":1,"gutter":6,"margin":36}' \
    --scale 3 \
    --all-pages "$FW/pages"
  # contactSheet appends its page AFTER the initial blank page (verified 24-11: 2 pages,
  # content on page-002, images anchored low on the portrait page — plain --export would
  # grab the blank page 1). The ffmpeg hstack montage below stays the reference for tight
  # planches; the verdict was: feature functional, ffmpeg hstack better suited for ours.
  if [ -f "$FW/pages/page-002.png" ]; then cp "$FW/pages/page-002.png" "$FW/sheet_designcraft.png"; fi
  # ffmpeg reference montage of the same 3 frames (side-by-side for the morning verdict)
  if [ -f "$F/sheet_designcraft.png" ]; then
    C:/ffmpeg/dist/bin/ffmpeg.exe -y -loglevel error \
      -i "$F/frame_a.png" -i "$F/frame_b.png" -i "$F/frame_c.png" -filter_complex \
      "[0][1][2]hstack=inputs=3" "$F/sheet_ffmpeg_ref.png" || true
  fi
}

leg_craft_effectcraft_smoke() {
  # effectcraft 0.25.1 update test — the rebuilt caching + relocated media libraries:
  # import OUR webm (VP9/Matroska = one of the 0.25.1 decode-fix areas) and render it.
  # CLI sessions are stateless (every invocation = fresh project, verified 23-11), so the
  # whole chain MUST stay in ONE `run`: comp.new {open:true} (active comp) → file.import
  # {addToComp:true} → renderQueue.add → renderQueue.render (engine command; the `render`
  # CLI subcommand cannot see a comp created in the same invocation). Dry-run validated
  # 23-11: statusLabel Done + webm content = our dance video. App updated tonight
  # 0.24.1→0.25.1.
  local EC=$(ls -d D:/CraftApps/effectcraft/effectcraft-*-windows-x64-portable 2>/dev/null | sort -V | tail -1)
  local F="$OUT/craft_effectcraft_smoke"
  # Windows-form paths in JSON (POSIX /c/... gets taken literally: the 23-11 render
  # wrote to C:\c\GIT\... — output resolved, import path unreliable; cygpath -m fixes both)
  local FW=$(cygpath -m "$F")
  mkdir -p "$F"
  if [ ! -d "$EC" ]; then log "[craft_effectcraft_smoke] ABORT: effectcraft install dir not found"; return 1; fi
  local SRC="$REPO/output/dance_m1106v2_brut.webm"
  local SRCW=$(cygpath -m "$SRC")
  if [ ! -f "$SRC" ]; then log "[craft_effectcraft_smoke] ABORT: source webm missing ($SRC)"; return 1; fi
  run_leg ec_import_render "$EC/effectcraft-cli.exe" run \
    comp.new '{"name":"ec_import_test","width":1920,"height":1080,"frameRate":24,"duration":4,"open":true}' \
    file.import "{\"paths\":[\"$SRCW\"],\"addToComp\":true}" \
    renderQueue.add "{\"comp\":\"ec_import_test\",\"format\":\"webm\",\"output\":\"$FW/ec_dance_2s.webm\",\"start\":0,\"end\":2}" \
    renderQueue.render '{}'
  if [ -f "$F/ec_dance_2s.webm" ]; then
    C:/ffmpeg/dist/bin/ffmpeg.exe -y -loglevel error -ss 1 -i "$F/ec_dance_2s.webm" \
      -frames:v 1 "$F/ec_render_frame.png" || true
  fi
}

# --------------------------------------- n2m sprites leg (added 25-11 soir, GO user « ajoute ça au run de nuit »)
leg_n2m_sprites_1125() {
  # Real-path validation of novel2manga `n2m sprites` (VNCCS Emotion-Studio port, branch
  # feat/n2m-sprites commit b85e576, suite 48/48 green): 2 characters x 2 states = 4 edit
  # legs on the qwen_edit_2511 backend (8 steps, 768^2, approved sheet as Picture-1 ref,
  # internal load gate per run). Outputs RGBA cast/sprites/<id>/<state>.png + manifest +
  # contact sheets (copied into the leg dir below). Expected ~15-25 min. Resume-safe
  # (existing outputs are skipped, so a partial night rerun continues cleanly).
  run_leg n2m_sprites_1125 bash -c '
    cd /d/GIT/novel2manga || exit 1
    uv run n2m sprites --project projects/heritier_du_vide --char elian_child --states normal,froid \
      && uv run n2m sprites --project projects/heritier_du_vide --char valeran --states normal,colere
  '
  if [ -f "$OUT/n2m_sprites_1125/DONE" ]; then
    cp /d/GIT/novel2manga/projects/heritier_du_vide/cast/sprites/_review/*_contact.png \
      "$OUT/n2m_sprites_1125/" 2>/dev/null || true
    cp /d/GIT/novel2manga/projects/heritier_du_vide/cast/sprites/manifest.json \
      "$OUT/n2m_sprites_1125/" 2>/dev/null || true
  fi
}

leg_n2m_sprites_fix_1126() {
  # Real-path re-validation of the sprite matte fix (novel2manga 7859c47, local-only
  # branch merged fast-forward into feat/n2m-sprites — repo has no remote, no PR):
  # the 25-11 night sprites carried a white enclosed-background notch above the skull
  # on the 2 emotion sprites (pocket between hair spikes touching the top edge,
  # missed by the 8 fixed border seeds). The fix scans the top edge + upper 40% of
  # the side edges per pixel; bottom/lower sides stay unseeded (crop lines — the
  # screentone weave touches them, offline re-key proved keying them eats the
  # fabric: semi-alpha 3% -> 22%). --overwrite forces regeneration through the
  # fixed matte; contact sheets copied for the morning verdict.
  run_leg n2m_sprites_fix_1126 bash -c '
    cd /d/GIT/novel2manga || exit 1
    uv run n2m sprites --project projects/heritier_du_vide --char elian_child --states normal,froid --overwrite \
      && uv run n2m sprites --project projects/heritier_du_vide --char valeran --states normal,colere --overwrite
  '
  if [ -f "$OUT/n2m_sprites_fix_1126/DONE" ]; then
    cp /d/GIT/novel2manga/projects/heritier_du_vide/cast/sprites/_review/*_contact.png \
      "$OUT/n2m_sprites_fix_1126/" 2>/dev/null || true
  fi
}

leg_hyperflow_h3_ab() {
  # A/B on the h3 Ref2VA PROD path (issue #2417 datapoint + speed candidate): leg A =
  # validated turbo recipe verbatim as a direct sd-cli call (baseline pruned Q4_K_M DiT
  # + 8-step turbo LoRA, euler default schedule) vs legs B4/B6/B8 = VideoRebirthAI
  # hyperflow-flash 14B Q4_K_M GGUF with the native sd-cli sigma presets
  # hyperflow-h3-flash-4/6/8 (CFG 1). Shared fixture: 12-frame tail @24fps + WAV
  # extracted ONCE from the shared source (verbatim logic of workflows/h3_ref2va.py),
  # same seed 42, same prompt. Decision input: wall-time per leg + 4-up mid-frame
  # planche; HyperFlow enters the PROD recipes only if quality holds at 4-6 steps.
  # Download is resume-safe (-C -) and gated on size; checkpoints license on the HF
  # card (read at the morning verdict — courtesy credit per the 2026-11-23 rule).
  local AB=/c/GIT/generator-assets/output/tests_nuit/hyperflow_h3_ab
  mkdir -p "$AB/fixture" "$AB"
  # shared fixture: last 0.5 s = 12 frames @24 fps + paired WAV (ffmpeg -sseof)
  run_leg hyperflow_fixture /c/ffmpeg/dist/bin/ffmpeg.exe -y -loglevel error \
    -sseof -0.5 -i "C:/GIT/generator-assets/output/test_p1_final/h3_source_avec_audio.mp4" \
    -vf fps=24 "$AB/fixture/frame_%04d.png"
  run_leg hyperflow_fixture_audio /c/ffmpeg/dist/bin/ffmpeg.exe -y -loglevel error \
    -sseof -0.5 -i "C:/GIT/generator-assets/output/test_p1_final/h3_source_avec_audio.mp4" \
    -vn -acodec pcm_s16le "$AB/fixture/ref_audio.wav"
  # B DiT download (~9.22 GB, resume-safe; skipped when already complete)
  run_leg hyperflow_dl bash -c '
    F="C:/Modeles_LLM/minimax_h3_ref2va_hyperflow_flash_14b-Q4_K_M.gguf"
    if [ -f "$F" ] && [ "$(stat -c%s "$F")" -gt 9000000000 ]; then echo "already staged"; exit 0; fi
    curl -L -C - --retry 3 -o "$F" \
      "https://huggingface.co/VideoRebirthAI/hyperflow-h3-flash/resolve/main/ref2va_gguf/minimax_h3_ref2va_hyperflow_flash_14b-Q4_K_M.gguf"
  '
  local PROMPT="the camera continues its slow push-in on the helmet, dust motes drifting, <Video 1>"
  # NOTE: -p is NOT part of COMMON — an unquoted $PROMPT inside a space-joined var
  # would word-split at the first space (prompt truncated, stray positional args).
  local COMMON="-M vid_gen --vae $MODELES/minimax_h3_video_vae_fp16.safetensors --audio-vae $MODELES/minimax_h3_audio_vae_fp32.safetensors --llm $MODELES/qwen3vl_32b_minimax_h3-Q2_K_M.gguf --ref-video $AB/fixture --ref-video-audio $AB/fixture/ref_audio.wav --video-frames 22 --fps 24 --cfg-scale 1.0 --sampling-method euler --diffusion-fa --offload-to-cpu --rng cpu --max-vram 10 --backend diffusion=vulkan0,te=cpu,vae=cpu -v"
  # leg A — validated turbo baseline (8-step LoRA, default schedule) (~17-32 min, #2417)
  run_leg h3_ab_turbo "$SD" $COMMON \
    --diffusion-model "$MODELES/minimax_h3_ref2va_pruned-Q4_K_M.gguf" \
    --lora-model-dir "$MODELES/loras" --lora-apply-mode auto \
    -p "$PROMPT <lora:minimax_h3_ref2v_turbo_8step_v1.0_768p_bf16:1>" \
    --steps 8 -o "$AB/h3_turbo_8step.webm"
  # legs B — hyperflow-flash native presets (CFG 1): decisive 4-step first, then 6/8
  run_leg h3_ab_hf4 "$SD" $COMMON \
    --diffusion-model "C:/Modeles_LLM/minimax_h3_ref2va_hyperflow_flash_14b-Q4_K_M.gguf" \
    -p "$PROMPT" \
    --sigmas hyperflow-h3-flash-4 --steps 4 -o "$AB/hyperflow_4step.webm"
  run_leg h3_ab_hf6 "$SD" $COMMON \
    --diffusion-model "C:/Modeles_LLM/minimax_h3_ref2va_hyperflow_flash_14b-Q4_K_M.gguf" \
    -p "$PROMPT" \
    --sigmas hyperflow-h3-flash-6 --steps 6 -o "$AB/hyperflow_6step.webm"
  run_leg h3_ab_hf8 "$SD" $COMMON \
    --diffusion-model "C:/Modeles_LLM/minimax_h3_ref2va_hyperflow_flash_14b-Q4_K_M.gguf" \
    -p "$PROMPT" \
    --sigmas hyperflow-h3-flash-8 --steps 8 -o "$AB/hyperflow_8step.webm"
  # 4-up mid-frame planche (non-fatal: morning verdict also reads the webms directly)
  run_leg hyperflow_planche bash -c '
    AB=/c/GIT/generator-assets/output/tests_nuit/hyperflow_h3_ab
    cd "$AB" || exit 1
    i=0
    for v in h3_turbo_8step hyperflow_4step hyperflow_6step hyperflow_8step; do
      i=$((i+1))
      ffmpeg -y -loglevel error -i "$v.webm" -vf "select=eq(n\\,12)" -vsync 0 "planche_$v.png" || exit 1
    done
    ffmpeg -y -loglevel error \
      -i planche_h3_turbo_8step.png -i planche_hyperflow_4step.png \
      -i planche_hyperflow_6step.png -i planche_hyperflow_8step.png \
      -filter_complex "[0][1][2][3]hstack=4" planche_ab.png || exit 1
    echo "turbo=$(stat -c%s h3_turbo_8step.webm) hf4=$(stat -c%s hyperflow_4step.webm) hf6=$(stat -c%s hyperflow_6step.webm) hf8=$(stat -c%s hyperflow_8step.webm)" > webm_sizes.txt
  '
  echo "fixture=$(substat $OUT/hyperflow_fixture) audio=$(substat $OUT/hyperflow_fixture_audio) dl=$(substat $OUT/hyperflow_dl) turbo=$(substat $OUT/h3_ab_turbo) hf4=$(substat $OUT/h3_ab_hf4) hf6=$(substat $OUT/h3_ab_hf6) hf8=$(substat $OUT/h3_ab_hf8) planche=$(substat $OUT/hyperflow_planche)" > "$OUT/hyperflow_h3_ab/SUBSTATUS.txt"
  touch "$OUT/hyperflow_h3_ab/DONE"
}

leg_moss_prompt_ab() {
  # fisher-moss methodology A/B on the moss_image real path (4-step LoRA default,
  # seed 42): A = plain one-liner prompt as a user would type, B = structured
  # expansion following the OpenMOSS prompt-skill methodology (lock subject/action
  # -> composition skeleton -> bind character/props/hands -> space/materials/
  # lighting -> output language; Work-Fisher/fisher-moss-prompt-expander, Apache-2.0,
  # adapted from the official OpenMOSS/MOSS-Image prompt skill). Question: does the
  # methodology measurably improve moss composition quality? Comparative 2-up plate
  # for the morning verdict; if B wins, fold the methodology into the skill refs.
  local PROMPT_A="a knight standing in a misty pine forest at dawn"
  local PROMPT_B="Perched on a moss-covered boulder at the edge of a clearing, one armored knight stands at rest, three-quarter view from the waist up, centered composition with the knight as the sole visual focus. The knight wears a weathered steel breastplate over a quilted gambeson, a heavy travel cloak drawn over the left shoulder and clasped by a plain iron brooch at the collarbone; the right gauntlet rests on the pommel of a longsword planted point-down between two tree roots. Gnarled pine trunks rise in layered ranks behind the knight, their silhouettes dissolving into banks of pale morning fog; thin shafts of golden dawn light slant through the canopy from the upper left, catching fine dust motes and glinting softly along the beveled edges of the breastplate. The forest floor is carpeted with wet moss and fallen needles, dark and saturated in shadow, luminous where the light pools. Cinematic depth of field, volumetric lighting, high detail."
  mkdir -p "$OUT/moss_prompt_ab"
  run_leg moss_ab_base uv run python main.py -w moss_image \
    -p "$PROMPT_A" --seed 42 -o nuit_moss_ab_base
  run_leg moss_ab_method uv run python main.py -w moss_image \
    -p "$PROMPT_B" --seed 42 -o nuit_moss_ab_method
  run_leg moss_ab_planche bash -c '
    cd /c/GIT/generator-assets/output || exit 1
    ffmpeg -y -loglevel error \
      -i nuit_moss_ab_base.png -i nuit_moss_ab_method.png \
      -filter_complex "[0][1]hstack=2" tests_nuit/moss_prompt_ab/planche_ab.png || exit 1
  '
  echo "base=$(substat $OUT/moss_ab_base) method=$(substat $OUT/moss_ab_method) planche=$(substat $OUT/moss_ab_planche)" > "$OUT/moss_prompt_ab/SUBSTATUS.txt"
  touch "$OUT/moss_prompt_ab/DONE"
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
      id="${id%$'\r'}"   # queue.txt edited from Windows tools carries CRLF
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
      [ "$id" = "h3_turbo_945" ]     && ev="output/h3_ref2va/ — PASS = #2103 kills the #1976 OOM on 945 (revalidate vs 6b3edaa); OOM signature = 6b3edaa stays"
      [ "$id" = "lightx2v_vace" ]    && [ -f "$OUT/lightx2v_vace/lightx2v_i2v_knight.webm" ] && ev="planche.png + webm"
      [ "$id" = "acestep90_12s" ]    && [ -f "$OUT/acestep90_12s/smoke90_12s.wav" ] && ev="smoke90_12s.wav + RTF in run.log (ref range 3.25-3.85)"
      [ "$id" = "sam_vulkan_retest" ] && [ -f "$OUT/sam_vulkan_retest/target.wav" ] && ev="target.wav + residual.wav — SAM works on VULKAN"
      [ "$id" = "sam_cpu_929" ]      && [ -f "$OUT/sam_cpu_929/target.wav" ] && ev="target.wav + residual.wav + RTF in run.log (ref 2.9)"
      [ "$id" = "ltx_multishot" ]        && [ -f "$OUT/ltx_multishot/multishot_65f.webm" ] && ev="planche.png + webm — cut visible? audio continuous?"
      [ "$id" = "ltx_upscale_base" ]     && [ -f "$OUT/ltx_upscale_base/base_33f.webm" ] && ev="base_33f.webm (A/B reference for the 2 upscaler probes)"
      [ "$id" = "ltx_upscale_spatial" ]  && [ -f "$OUT/ltx_upscale_spatial/spatial_33f.webm" ] && ev="spatial_33f.webm — vs base (2x latent detail?)"
      [ "$id" = "ltx33_929_paramsdisk" ] && [ -f "$OUT/ltx33_929_paramsdisk/ltx33_paramsdisk.webm" ] && ev="ltx33_paramsdisk.webm — LTX fit on 929 with --params-backend disk (#1976)"
      [ "$id" = "heartmula_gothic" ]     && [ -f "$OUT/heartmula_gothic/heartmula_gothic_30s.wav" ] && ev="heartmula_gothic_30s.wav — USER LISTENING VERDICT (standing gothic recipe)"
      [ "$id" = "indextts25_en_tts" ]   && [ -f "$OUT/indextts25_en_tts/indextts25_en_tts.wav" ] && ev="indextts25_en_tts.wav — listening verdict + RTF datapoint (synth ref)"
      [ "$id" = "indextts25_en_clone" ] && [ -f "$OUT/indextts25_en_clone/indextts25_en_clone.wav" ] && ev="indextts25_en_clone.wav — timbre vs ref_voix_laurent.wav + A/B vs en_tts (same text/seed)"
      [ "$id" = "indextts25_fr_probe" ] && ev="expected-FAIL datapoint (fr outside the spec languages) — wav if generated"
      [ "$id" = "dance_sheet_workflow" ] && ev="output/dance_workflow_nuit_2048.png + _4.0s_1080p.mp4 + _grille_identite.png — §6 real-path closure of the workflow port (chain validated 11-20 via machine-local scripts)"
      [ "$id" = "llama_b12590_smoke" ]   && [ -s "$OUT/llama_b12590_smoke/ts.txt" ] && ev="ts.txt — generation t/s vs band 181-217 (b12590 installed 11-20, smoke was deferred)"
      [ "$id" = "sam_vulkan_v095" ]      && [ -f "$OUT/sam_vulkan_v095/target.wav" ] && ev="target.wav + residual.wav — SAM on Vulkan v0.9.5 (version-bound retest, rule 11-05)"
      [ "$id" = "flashhead_v095_probe" ] && ev="does v0.9.5 carry Vulkan IM2COL_3D? (blocked on 0.9.4; FAIL+IM2COL_3D = still blocked)"
      [ "$id" = "qwen3_align_v095" ]     && [ -f "$OUT/qwen3_align_v095/words.json" ] && ev="words.json + segments.json — subtitle-timing capability probe (0.6B q8_0, 42 s demo transcript)"
      [ "$id" = "fruc_vs_mci" ]          && ev="fruc_48fps.mp4 — expected NVIDIA-only (NV optical flow); if run.log shows a FRAMES-CONTEXT error instead of NV, follow-up = hwupload,fruc_vulkan,hwdownload before concluding AMD can't"
      [ "$id" = "h3image_smoke" ]        && [ -f "$OUT/h3image_smoke/SUBSTATUS.txt" ] && ev="11-22 retry, ONE factor changed = C: NVMe staging (11-21 died on the D: 5 MB/s DiT prefetch). sub-legs: $(cat "$OUT/h3image_smoke/SUBSTATUS.txt" 2>/dev/null) — morning verdict = PNG side-by-side (qwen_t2i_1024.png DONE 11-21 = deterministic seed-42 A/B ref); sub-logs in output/tests_nuit/<sub>/run.log"
      [ "$id" = "inkling_ad_q4k" ]       && [ -f "$OUT/inkling_ad_q4k/SUBSTATUS.txt" ] && ev="AD-Q4_K (16.53 GB, user DL 11-22) vs the §1.41 Q3_K_XL datapoint (363 s / 5.89 t/s; Qwen3VL-8B ref 69.5 s) — $(cat "$OUT/inkling_ad_q4k/SUBSTATUS.txt" 2>/dev/null); fixture answers + t/s in output/tests_nuit/inkling_ad_q4k/"
      [ "$id" = "sous_titres_smoke" ]    && [ -f "$OUT/sous_titres_smoke/SUBSTATUS.txt" ] && ev="PR #44 §6 real-path closure: align ono (expect 15 words ≈ words_v2_ono.json) + asr dylan long (VAD chunking) — $(cat "$OUT/sous_titres_smoke/SUBSTATUS.txt" 2>/dev/null); srt+words.json in output/tests_nuit/sous_titres_smoke_align/"
      [ "$id" = "n2m_sprites_1125" ]     && [ -f "$OUT/n2m_sprites_1125/elian_child_contact.png" ] && ev="elian_child_contact.png + valeran_contact.png (RGBA contact sheets) + manifest.json — USER EYE VERDICT: alpha busts readable, identity vs the 11-16 sheets, froid/colere actually expressed"
      echo "| $id | $st | $du | $ev |"
    done < "$QUEUE"
    echo ""
    echo "Gate log (last): \`output/tests_nuit/gate_last.log\` — per-leg logs in \`output/tests_nuit/<id>/run.log\`."
  } > "$f"
  log "Report written: $f"
}

# ---------------------------------------------------------------- main

if [ ! -f "$QUEUE" ]; then
  printf '# Overnight test queue (one id per line)\n# acestep90_12s | sam_vulkan_retest | sam_cpu_929 | wan_i2v_929 | vace_knight | ltx33_929 | h3_turbo_929 | monoplan65_929 | lightx2v_vace\n' > "$QUEUE"
fi

log "=== Night test queue run — queue: $QUEUE ==="
while read -r id; do
  id="${id%$'\r'}"   # queue.txt edited from Windows tools carries CRLF (11-20: all ids "unknown" without this)
  case "$id" in ""|\#*) continue;; esac
  case "$id" in
    wan_i2v_929)        leg_wan_i2v_929 ;;
    vace_knight)        leg_vace_knight ;;
    ltx33_929)          leg_ltx33_929 ;;
    h3_turbo_929)       leg_h3_turbo_929 ;;
    h3_turbo_945)       leg_h3_turbo_945 ;;
    monoplan65_929)     leg_monoplan65_929 ;;
    lightx2v_vace)      leg_lightx2v_vace ;;
    acestep90_12s)      leg_acestep90_12s ;;
    sam_vulkan_retest)  leg_sam_vulkan_retest ;;
    sam_cpu_929)        leg_sam_cpu_929 ;;
    ltx_multishot)        leg_ltx_multishot ;;
    ltx_upscale_base)     leg_ltx_upscale_base ;;
    ltx_upscale_spatial)  leg_ltx_upscale_spatial ;;
    ltx33_929_paramsdisk) leg_ltx33_929_paramsdisk ;;
    heartmula_gothic)     leg_heartmula_gothic ;;
    indextts25_en_tts)    leg_indextts25_en_tts ;;
    indextts25_en_clone)  leg_indextts25_en_clone ;;
    indextts25_fr_probe)  leg_indextts25_fr_probe ;;
    dance_sheet_v2)       leg_dance_sheet_v2 ;;
    dance_sheet_workflow) leg_dance_sheet_workflow ;;
    llama_b12590_smoke)   leg_llama_b12590_smoke ;;
    sam_vulkan_v095)      leg_sam_vulkan_v095 ;;
    flashhead_v095_probe) leg_flashhead_v095_probe ;;
    qwen3_align_v095)     leg_qwen3_align_v095 ;;
    fruc_vs_mci)          leg_fruc_vs_mci ;;
    h3image_smoke)        leg_h3image_smoke ;;
    inkling_ad_q4k)       leg_inkling_ad_q4k ;;
    sous_titres_smoke)    leg_sous_titres_smoke ;;
    sweep_1116)           leg_sweep_1116 ;;
    inkling_q4_unsloth)   leg_inkling_q4_unsloth ;;
    build_validation_html) leg_build_validation_html ;;
    sweep1116_fix)        leg_sweep1116_fix ;;
    h3video_1106_ab)      leg_h3video_1106_ab ;;
    moss_4step_lora)      leg_moss_4step_lora ;;
    sweep_1127)           leg_sweep_1127 ;;
    llm_lfm3_17b)         leg_llm_lfm3_17b ;;
    craft_designcraft_sheet) leg_craft_designcraft_sheet ;;
    craft_effectcraft_smoke) leg_craft_effectcraft_smoke ;;
    n2m_sprites_1125)       leg_n2m_sprites_1125 ;;
    n2m_sprites_fix_1126)   leg_n2m_sprites_fix_1126 ;;
    hyperflow_h3_ab)        leg_hyperflow_h3_ab ;;
    moss_prompt_ab)         leg_moss_prompt_ab ;;
    *) log "[?] unknown queue id: $id — ignored" ;;
  esac
  if [ -s "$OUT/gate_last.log" ] && grep -q "DO NOT launch" "$OUT/gate_last.log"; then
    log "Gate refused — aborting the queue for tonight (markers keep progress)."
    break
  fi
done < "$QUEUE"

rapport

# Runner-level HTML rebuild (option A, GO user 11-24): the dated builder runs HERE,
# after the loop — NOT as a queue leg. The 11-24 incident had the re-armed marker
# consumed mid-queue by a duplicate queue line, so the page never rebuilt. Latest
# dated builder wins (ls -t). Non-fatal: a builder failure must not block shutdown.
BUILDER=$(ls -t "$OUT"/build_validation_html_*.py 2>/dev/null | head -1)
if [ -n "$BUILDER" ]; then
  # PR #48 finding #2 (superseded PR, proven nuance): pass the REPO-RELATIVE path to
  # uv — an absolute /c/... argv into a native exe relies on MSYS path conversion,
  # which MSYS2_ARG_CONV_EXCL/MSYS_NO_PATHCONV would suppress. cwd = $REPO here.
  REL_BUILDER=${BUILDER#"$REPO"/}
  log "Rebuilding validation page via $REL_BUILDER"
  uv run python "$REL_BUILDER" > "$OUT/build_validation_html_runner.log" 2>&1 \
    || log "HTML rebuild failed (non-fatal) — log: $OUT/build_validation_html_runner.log"
fi

log "=== Night queue run finished ==="
powershell -NoProfile -Command "try { (New-Object Media.SoundPlayer 'C:\Windows\Media\Windows Notify System Generic.wav').PlaySync() } catch { [console]::beep(800,300) }" 2>/dev/null || true
if [ "$SHUTDOWN" -eq 1 ]; then
  log "Shutdown scheduled in 300 s (abort within the grace window: shutdown /a)"
  # PowerShell route: the MSYS path translation silently mangled /s /t /c on 11-22
  # (the shutdown never fired) — powershell.exe receives the argv unmangled.
  powershell -NoProfile -Command "shutdown.exe /s /t 300 /c 'tests_nuit: run termine, arret programme (annuler: shutdown /a)'"
fi
exit 0
