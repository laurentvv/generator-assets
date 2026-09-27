import os
import sys
from pathlib import Path

# Ensure access to the 'core' package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import subprocess
import time
import cv2

for f in (sys.stdout, sys.stderr):
    if hasattr(f, 'reconfigure'):
        f.reconfigure(encoding='utf-8', errors='replace')

from core.config import DEFAULT_SD_CLI, DEFAULT_OUTPUT_DIR
from core.upscaler import upscale_video

SD_CLI = DEFAULT_SD_CLI
MODEL = r"C:\Modeles_LLM\wan2.1-t2v-14b-Q4_K_M.gguf"
VAE = r"C:\Modeles_LLM\wan_2.1_vae.safetensors"
T5 = r"C:\Modeles_LLM\umt5-xxl-encoder-Q4_K_M.gguf"
UPSCALER_MODEL = r"C:\Modeles_LLM\upscalers\4x-UltraSharp.pth"

OUTPUT_DIR = DEFAULT_OUTPUT_DIR
os.makedirs(OUTPUT_DIR, exist_ok=True)

FPS = 16
FRAMES_PER_PLAN = 33  # (33 - 1) % 4 == 0 (Wan 2.1 native format)
STEPS = 10
CFG_SCALE = 6.0
FLOW_SHIFT = 3.0

NEGATIVE_PROMPT = (
    "blurry, soft, hazy, out of focus, low quality, static, dull colors, greyish, "
    "noisy, distorted, deformed, artifacts, watermark, low resolution, ugly"
)

PLANS = [
    {
        "id": 1,
        "name": "plan_1_vol",
        "description": "Majestic flight at sunset",
        "prompt": (
            "Cinematic wide shot, colossal obsidian and gold dragon with radiant violet flame wings "
            "soaring gracefully above dark gothic castle spires at sunset, storm clouds, photorealistic, "
            "intricate obsidian dragon scales, glowing violet arcane eyes, dramatic lighting, 8k uhd, sharp focus, masterpiece"
        )
    },
    {
        "id": 2,
        "name": "plan_2_plongee",
        "description": "Dynamic dive toward the fortress",
        "prompt": (
            "Cinematic action tracking shot, the colossal obsidian and gold dragon diving steeply downwards "
            "towards dark medieval stone castle courtyard, wings folded back, trailing brilliant violet sparks and embers, "
            "photorealistic, sharp focus, 8k uhd, dramatic cinematic motion"
        )
    },
    {
        "id": 3,
        "name": "plan_3_atterrissage",
        "description": "Heavy landing on the tower and flame roar",
        "prompt": (
            "Cinematic close-up, the colossal obsidian and gold dragon lands heavily on ancient stone fortress battlement, "
            "sharp talons gripping dark stone, opening jaws and roaring fiercely with brilliant violet flame breath and flying embers, "
            "photorealistic, highly detailed dragon head, sharp focus, 8k uhd, masterpiece"
        )
    }
]


def extraire_derniere_trame(video_path: str, dest_png: str) -> str:
    """Extracts the last frame of a video to serve as the I2V initial condition of the next shot."""
    cap = cv2.VideoCapture(video_path)
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, count - 1))
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise RuntimeError(f"Unable to extract the last frame of {video_path}")
    cv2.imwrite(dest_png, frame)
    print(f"   📸 Transition frame captured: {dest_png} (frame {count}/{count})")
    return dest_png


def generer_plan(
    prompt: str,
    out_path: str,
    init_img: str = None,
    frames: int = FRAMES_PER_PLAN,
    fps: int = FPS,
    steps: int = STEPS
) -> str:
    """Generates a Wan 2.1 accelerated video shot under Vulkan."""
    cmd = [
        SD_CLI,
        "-M", "vid_gen",
        "--diffusion-model", MODEL,
        "--vae", VAE,
        "--t5xxl", T5,
        "-p", prompt,
        "-n", NEGATIVE_PROMPT,
        "-W", "832",
        "-H", "480",
        "--video-frames", str(frames),
        "--fps", str(fps),
        "--steps", str(steps),
        "--cfg-scale", str(CFG_SCALE),
        "--flow-shift", str(FLOW_SHIFT),
        "--diffusion-fa",
        "--temporal-tiling",
        "--vae-tiling",
        "--backend", "diffusion=vulkan0,te=cpu",
        "-o", out_path
    ]
    if init_img and os.path.exists(init_img):
        cmd.extend(["-i", init_img])

    mode = "I2V (smooth continuation)" if init_img else "T2V (lead-in)"
    print(f"\n🎬 [Wan 2.1 Vulkan - {mode}] {frames} frames @ {fps} fps (steps={steps})...")
    t0 = time.time()
    subprocess.run(cmd, check=True)
    duree = time.time() - t0
    print(f"   ✅ Shot finished in {duree:.1f}s ({duree / steps:.2f}s/step)")
    return out_path


def concatener_clips_fluide(clips: list, out_path: str, fps: float = 16.0) -> str:
    """
    Concatenates several video shots into one continuous sequence.
    Removes the first frame of subsequent shots (frame 0 = frame N-1 of the previous shot)
    to guarantee a perfect continuity without freeze or visual judder.
    """
    print(f"\n🔗 [Fluid Assembly] Concatenating {len(clips)} shots...")
    writer = None
    w, h = None, None
    total_written = 0

    for idx, clip_path in enumerate(clips):
        cap = cv2.VideoCapture(clip_path)
        if not cap.isOpened():
            print(f"⚠️ Unreadable clip: {clip_path}")
            continue

        clip_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if w is None:
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(out_path, fourcc, fps, (w, h))

        f_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            # For shots 2 and 3, skip frame 0 which duplicates the end of the previous shot
            if idx > 0 and f_idx == 0:
                f_idx += 1
                continue
            writer.write(frame)
            total_written += 1
            f_idx += 1
        cap.release()
        print(f"   Shot {idx + 1}/{len(clips)} assembled ({clip_frames} frames, written: {f_idx if idx == 0 else f_idx - 1})")

    if writer:
        writer.release()

    duree_sec = total_written / fps
    print(f"✅ Raw continuous video created: {out_path}")
    print(f"   Total duration: {duree_sec:.2f} seconds ({total_written} frames @ {fps} fps, {w}x{h})")
    return out_path


def generer_scene_godot(video_path: str, tscn_path: str):
    """Generates a Godot 4 scene ready to play the cinematic in a loop."""
    video_nom = os.path.basename(video_path)
    contenu = f"""[gd_scene load_steps=2 format=3 uid="uid://dragon_cinematic_player"]

[ext_resource type="VideoStreamTheora" path="res://{video_nom}" id="1_video"]

[node name="DragonCinematic" type="Control"]
layout_mode = 3
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2

[node name="VideoStreamPlayer" type="VideoStreamPlayer" parent="."]
layout_mode = 1
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2
stream = ExtResource("1_video")
autoplay = true
expand = true
loop = true
"""
    with open(tscn_path, "w", encoding="utf-8") as f:
        f.write(contenu)
    print(f"🎮 Godot 4 scene generated: {tscn_path}")


def main():
    print("=" * 80)
    print(" Advanced Video Pipeline: 3-Shot Chaining (T2V -> 2x I2V) + 4x-UltraSharp HD Upscale")
    print(" GPU: AMD Radeon RX 6950 XT (16 GB VRAM) - Vulkan 1.4 Native")
    print("=" * 80)

    clips_generes = []
    derniere_trame = None

    # Phases 1 & 2: generation of the 3 chained shots
    for plan in PLANS:
        pid = plan["id"]
        pname = plan["name"]
        pdesc = plan["description"]
        pprompt = plan["prompt"]
        out_clip = os.path.join(OUTPUT_DIR, f"dragon_{pname}.webm")

        print("\n=======================================================")
        print(f" Shot {pid}/3: {pdesc}")
        print("=======================================================")
        generer_plan(
            prompt=pprompt,
            out_path=out_clip,
            init_img=derniere_trame,
            frames=FRAMES_PER_PLAN,
            fps=FPS,
            steps=STEPS
        )
        clips_generes.append(out_clip)

        frame_png = os.path.join(OUTPUT_DIR, f"dragon_{pname}_transition.png")
        derniere_trame = extraire_derniere_trame(out_clip, frame_png)

    # Seamless 0-cut concatenation
    video_brute = os.path.join(OUTPUT_DIR, "dragon_sequence_6s_brute.mp4")
    concatener_clips_fluide(clips_generes, video_brute, fps=FPS)

    # Phase 3: 2x AI Super-Resolution (1664x960) via ESRGAN 4x-UltraSharp
    print("\n=======================================================")
    print(" Phase 3: AI HD Super-Resolution (ESRGAN 4x-UltraSharp Vulkan)")
    print("=======================================================")
    video_hd = os.path.join(OUTPUT_DIR, "dragon_sequence_6s_hd.mp4")
    t_up = time.time()
    upscale_video(
        video_input_path=video_brute,
        output_path=video_hd,
        facteur=2.0,
        mode="auto",
        upscale_model=UPSCALER_MODEL,
        sd_cli=SD_CLI
    )
    print(f"⏱️ HD upscaling finished in {time.time() - t_up:.1f}s")

    # Capture of an HD preview frame
    preview_png = os.path.join(OUTPUT_DIR, "dragon_sequence_6s_hd_preview.png")
    extraire_derniere_trame(video_hd, preview_png)

    # Generation of the Godot 4 template
    scene_godot = os.path.join(OUTPUT_DIR, "dragon_sequence_hd_player.tscn")
    generer_scene_godot(video_hd, scene_godot)

    print("\n" + "=" * 80)
    print("🎉 TOTAL SUCCESS: 6.06-second video sequence generated and upscaled to HD!")
    print(f"   Raw video:    {video_brute}")
    print(f"   HD video (1664x960): {video_hd}")
    print(f"   HD preview:   {preview_png}")
    print(f"   Godot 4 scene: {scene_godot}")
    print("=" * 80)


if __name__ == "__main__":
    main()
