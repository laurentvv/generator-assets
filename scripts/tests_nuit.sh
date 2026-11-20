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

SHUTDOWN=0
for a in "$@"; do case "$a" in
  --shutdown) SHUTDOWN=1 ;;
  *) echo "unknown option: $a (supported: --shutdown)"; exit 1 ;;
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
      --audio "$REPO/output/test_flashhead_v094/english_12s.wav" \
      --text "$(cat "$REPO/output/test_flashhead_v094/english.txt")" \
      --seed 42 \
      --out-dir "$OUT/qwen3_align_v095/"
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
    planche "$OUT/fruc_vs_mci/fruc_48fps.mp4" "$OUT/fruc_vs_mci/planche.png" || true
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
      [ "$id" = "llama_b12590_smoke" ]   && [ -f "$OUT/llama_b12590_smoke/ts.txt" ] && ev="ts.txt — generation t/s vs band 181-217 (b12590 installed 11-20, smoke was deferred)"
      [ "$id" = "sam_vulkan_v095" ]      && [ -f "$OUT/sam_vulkan_v095/target.wav" ] && ev="target.wav + residual.wav — SAM on Vulkan v0.9.5 (version-bound retest, rule 11-05)"
      [ "$id" = "flashhead_v095_probe" ] && ev="does v0.9.5 carry Vulkan IM2COL_3D? (blocked on 0.9.4; FAIL+IM2COL_3D = still blocked)"
      [ "$id" = "qwen3_align_v095" ]     && [ -f "$OUT/qwen3_align_v095/target.json" -o -f "$OUT/qwen3_align_v095/segments.json" ] && ev="alignment segments json — subtitle-timing capability probe (0.6B q8_0 downloaded)"
      [ "$id" = "fruc_vs_mci" ]          && ev="fruc_48fps.mp4 — expected NVIDIA-only (NV optical flow); any AMD output = surprise datapoint vs mci/aobmc ralenti"
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
    *) log "[?] unknown queue id: $id — ignored" ;;
  esac
  if [ -s "$OUT/gate_last.log" ] && grep -q "DO NOT launch" "$OUT/gate_last.log"; then
    log "Gate refused — aborting the queue for tonight (markers keep progress)."
    break
  fi
done < "$QUEUE"

rapport
log "=== Night queue run finished ==="
if [ "$SHUTDOWN" -eq 1 ]; then
  log "Shutdown scheduled in 300 s (abort within the grace window: shutdown /a)"
  /c/Windows/System32/shutdown.exe /s /t 300 /c "tests_nuit: run termine, arret programme (annuler: shutdown /a)"
fi
exit 0
