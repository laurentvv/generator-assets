# 🧪 H3 Ref2VA "endless" prototype — long video sequence by chunks

> **Status: PREPARED, NOT LAUNCHED, NOT VALIDATED.** This document describes the
> multi-chunk MiniMax-H3 Ref2VA loop prototype (CLI twin of the ComfyUI node
> [HR-Endless-Sampler](https://github.com/hradec/ComfyUI-HR-Endless-Sampler)).
> The unit brick (1 chunk) is **validated** → `h3_ref2va` workflow, launched by this
> prototype in `--turbo` mode (distilled 8-step LoRA, validated 2026-09-09 — ~38 min/chunk,
> better reference splice; MEMORY_BANK §1.16). **The loop itself has never been judged**: chunk→chunk
> splices are the unvalidated point. Will become a workflow only after
> user validation of the result (AGENTS.md rule).
>
> **Integrated levers (2026-09-09, defaults = validated recipe — to probe, not to deploy)**:
> `--ref-audio-sec` ("reaching-back" audio window cut from the full timeline —
> Motion-Context lesson) • `--ref-frames` (5 = ref frames exactly on the splice,
> cf. sd-cli truncation 12→5 first frames) • `--ref-scale` (ref downscale, active
> only under the nominal sd-cli size 768×432). Detail: MEMORY_BANK §1.16.

## 📏 What it produces (measured estimates, RX 6950 XT / 16 GB / 31.8 GB RAM, turbo mode)

| Window | Expected result |
|---|---|
| **24 h** | ~34-36 chunks of 22 frames → **31-33 s of continuous video with audio** (864×480, webm) |
| ~1 h 15 | 2 chunks → enough to judge **the first splice** (recommended as a 1st step) |

Cost of one chunk in turbo (~38 min, validated 2026-09-09): reference VAE encoding
~14.5 min (CPU/swap) • Qwen3-VL ~1.5 min • 8-step sampling ~18 min (134 s/step,
graph-cut) • decoding ~4.2 min. (Base 20-step recipe: ~70 min/chunk — see
MEMORY_BANK §1.16 for the A/B.)

**Turbo bonus for THIS loop**: the reference splice is **better** than in the base
recipe (frame 1 nearly identical to the ref's last frame — the critical point
of chunk→chunk chaining). The proto's #1 risk is reduced.

**Levers integrated into the proto (options, not validated — A/B to do on 2 chunks before generalizing)**:

| Option | Default (= validated recipe) | Variant to probe | Expected effect |
|---|---|---|---|
| `--ref-audio-sec` | 0.5 | 4-6 | Audio window ending at the splice, cut from the timeline (source + played chunks) → the model "continues the track" instead of writing one that resembles it (Motion-Context lesson). Chunk→chunk musical continuity. |
| `--ref-frames` | 12 | 5 | sd-cli only encodes the 5 FIRST frames of the folder (17k+5 truncation): providing exactly 5 puts them on the splice + ref VAE encoding ÷ ~2.4 (chunk ~30 min). |
| `--ref-scale` | 1.0 | 0.15 (4K) / 0.85 (864-wide) | 32 px-aligned ref downscale — only has an effect UNDER sd-cli's internal nominal size (768×432): smaller ref latent → cheaper attention (equivalent of `video_continuation_res`). Softer ref. |

**Remaining levers outside the proto**: output resolution ÷2 → ~45-60 s/24 h •
**64 GB RAM = the real unlock** (end of the VAE swap + GPU-resident DiT
→ chunk ~10-15 min → **1.5-2.5 min/24 h**). Comparison: Wan 2.2 over 24 h ≈ 6-9 min
but independent shots, without continuity nor audio.

## 🚀 Launch (when decided, FREE machine)

```bash
# 1. Check the load (AGENTS.md rule) — exit 1 = wait
uv run python scripts/check_charge_systeme.py

# 2. Launch the detached loop (survives session close)
mkdir -p output/endless_dragon_24h
nohup uv run python scripts/proto_endless_h3.py --output-dir output/endless_dragon_24h \
  > output/endless_dragon_24h/boucle.log 2>&1 & disown
```

The script (`scripts/proto_endless_h3.py`): 18-prompt storyboard editable at the top
of the file (walk → fire → take-off → lake → cliffs → cave → treasure → sleep),
pre-extraction of each chunk's reference (frames + WAV via ffmpeg, passed to the
workflow as a frames folder + `--ref-audio`), automatic resume at the first missing
chunk, 3 attempts/chunk spaced 15 min apart
(absorbs a refusing check_charge), 23 h window (`--deadline-min`), final automatic
concat (`endless_final.webm`, `-c copy`).

## 👀 Monitoring & stop

```bash
tail -f output/endless_dragon_24h/boucle.log      # live journal
ls output/endless_dragon_24h/chunk_*.webm         # progress (1 chunk ≈ 38 min in turbo)
```

**Go/no-go criterion (1st splice, ~1 h 15)**: extract the last frame of chunk_01 and
the first of chunk_02 — if the dragon mutates or clearly jumps, stop (no point
burning 11 h on a drift). Micro-jumps are possible: Ref2VA in CLI has no boundary
keyframe (incompatible with `--init-img`), the reference alone carries the continuity.
**Suggested protocol**: probe the 3 variants of the table above on 2 chunks each
(3 × ~1 h 15) — configs: (a) default, (b) `--ref-audio-sec 5`, (c) `--ref-frames 5
--ref-audio-sec 5` — judge the splices (eye + ear) and launch the 18 chunks
only with the winning config.

**Emergency stop** (everything already generated is kept):
```bash
powershell -NoProfile -Command 'Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "proto_endless_h3|h3_ref2va" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }; Get-Process sd-cli -ErrorAction SilentlyContinue | Stop-Process -Force'
```

## ✅ After a conclusive run

1. Judge `endless_final.webm` (eye + ear, video AND audio continuity across splices).
2. Record the verdict in MEMORY_BANK §1.16 (chunk count, observed drift, timings).
3. If validated → turn the loop into a `video_endless` workflow (AGENTS.md: every
   validated test becomes a workflow); if not validated → note the pitfalls and levers.
