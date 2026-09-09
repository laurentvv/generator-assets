# Brouillons de feature requests — leejet/stable-diffusion.cpp

**Statut : BROUILLONS — ne PAS publier sans accord explicite de l'utilisateur**
(publication = action externe). Cible : `leejet/stable-diffusion.cpp` (issues).
Issus de `docs/recherche_comfyui_2026-09-09.md` §8 (action 4) + lecture des sources
sd-cli (comportement Ref2VA, cf. MEMORY_BANK §1.16).

⚠️ Avant publication : la version installée ici est `master-841` (rollback de la
régression #1946, coupable `462d675` isolé par bisect le 2026-09-08) — mettre à jour
les mentions de version le jour où une release corrigée est installée, et vérifier
que les points n'ont pas déjà été traités entre-temps.

---

## Brouillon 1 — Ref2VA: reference resolution control + latent tail carry-over for long-video chaining

**Title:** MiniMax-H3 Ref2VA: expose reference video resolution (+ long-term: latent tail carry-over for chunk chaining)

Hi, I generate long videos with the MiniMax-H3 Ref2VA model entirely through `sd-cli -M vid_gen --ref-video <frames_dir> --ref-video-audio <wav>` on Vulkan (RX 6950 XT): the tail of chunk N (last frames + audio, extracted with ffmpeg) becomes the reference of chunk N+1 — the CLI equivalent of hradec's ComfyUI "HR Endless Sampler" node. It works well, thanks for the great H3 support!

Two things would make chaining cheaper/seamless:

1. **Reference resolution control.** As far as I can read in the source, ref-video frames are resized to a nominal size based on 768 px (aspect kept, capped 768×1344, aligned 32; the source size is kept only if *smaller*). There is no way to deliberately encode the reference *below* that nominal size. ComfyUI's HR Endless Sampler has `video_continuation_res` (decode → resize → re-encode the continuation block) exactly to shrink the reference latent: less ref-attention VRAM, bigger chunks, faster VAE encode (on CPU backends this is significant). Would you consider a `--ref-video-res WxH` (or a scale factor) that clamps the reference to a user-chosen size? (Going *up* from a small source is already possible implicitly; the ask is going *down* on purpose.)

2. *(harder, long-term)* **Latent tail carry-over.** Chaining currently re-encodes the reference each chunk (decode → resize → encode), so a tiny generation loss sits at every seam and can accumulate over very long chains. ComfyUI-H3-Motion-Context slices the previous chunk's tail *in latent space* (bit-exact, zero drift). I understand this may not fit the CLI pipeline (the ref would have to skip the VAE encode stage entirely), but I'd like to put it on the radar — even a "reuse previous output latents as reference" hook would remove seams completely.

Happy to A/B test patches on this machine (Vulkan, 16 GB VRAM) — the single-chunk recipe is validated and documented on our side.

---

## Brouillon 2 — Images sémantiques (horodatées) dans le prompt via le text-encoder Qwen

**Title:** MiniMax-H3: feed reference images to the Qwen text encoder (semantic/timed `<Picture N>`), separate from VAE-encoded references

ComfyUI has a technique (ethanfel's `ComfyUI-MiniMaxH3-Timed-References`) where images are presented **only to the Qwen text encoder** as `<Picture N>` — semantic slots, no VAE encoding, optionally *timestamped* ("at 2.0 s, show the red car"), including frames picked from a video with their real PTS. It enables "shot-planning" prompts: a storyboard of timed intentions, distinct from the native VAE-encoded `<Video 1>` reference.

In `sd-cli`, as far as I can tell, the `--llm` Qwen3-VL GGUF only receives text today (images only flow through `--ref-image`/`--ref-video` → VAE). Would you consider an optional `--prompt-image <file>[:seconds]` that injects images into the text-encoder pass as vision tokens with `<Picture N>` tags?

Open question on my side: does the `qwen3vl_32b_minimax_h3` GGUF keep the vision projector usable (or is it text-only after quant/adaptation)? If mmproj weights are needed, I can test that path. Use case: multi-shot H3 videos planned as a timed storyboard without burning native reference slots.

---

## Brouillon 3 — Support VACE (Wan 2.2)

**Title:** Wan 2.2 VACE support in vid_gen (reference-to-video / video editing)

ComfyUI's official examples now include `vace_reference_to_video.json` for Wan 2.2 — VACE covers reference-to-video, video editing and video inpainting in one model, which complements the already-excellent Wan t2v/i2v support in sd-cli (Wan 2.1/2.2 MoE are validated daily on this machine).

Would VACE weights be in scope for `vid_gen` (GGUF quants of the VACE-enabled Wan 2.2 + the extra reference/control inputs)? Even a narrow subset (reference-to-video) would unlock controlled video generation on Vulkan. I can help test.

---

### Rappel process (une fois publiées)

- Référencer les issues ouvertes dans `docs/recherche_comfyui_2026-09-09.md` §8 et
  `docs/MEMORY_BANK.md` §1.16 (liens + numéros) ; suivre les réponses via la veille
  (mécanique issue sd-cli #1946 du hook SessionStart si pertinent).
