#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Video : Génération de cinématiques, clips animés et VFX vidéo (.webm) pour Godot 4.
Exploite l'accélération matérielle Vulkan de stable-diffusion.cpp (Wan 2.1 / Wan 2.2, LTX-2.3 / LTX-2.5, MiniMax-H3).

Supporte :
  • T2V (Text-to-Video) : Génération de vidéo à partir d'une description textuelle.
  • I2V (Image-to-Video) : Animation d'une image fixe (--input).
  • FLF2V (First & Last Frame) : Interpolation fluide entre deux images clés (--input et --end-img).
  • V2V (Video Control) : Transfert de style / guidage par dossier de trames (--control-video).
"""

import os
from pathlib import Path
from typing import Any, Dict

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.diffusion import generer_video_vulkan
from core.upscaler import upscale_video
from workflows.base import BaseWorkflow, WorkflowRegistry


@WorkflowRegistry.register
class VideoWorkflow(BaseWorkflow):
    """Génération de cinématiques et clips vidéo (.webm) via stable-diffusion.cpp sous Vulkan."""

    name = "video"
    description = "Génération vidéo IA native (.webm) via Wan 2.1 / LTX / MiniMax sous Vulkan (T2V, I2V, FLF2V)"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        prompt = params.get("prompt")
        if not prompt:
            raise ValueError("Le paramètre 'prompt' est requis pour le workflow video.")

        output_dir = params.get("output_dir", DEFAULT_OUTPUT_DIR)
        os.makedirs(output_dir, exist_ok=True)

        nom_base = params.get("output") or f"{slugifier_texte(prompt)}_vid"
        if not nom_base.lower().endswith(".webm") and not nom_base.lower().endswith(".mp4"):
            video_output_path = os.path.join(output_dir, f"{nom_base}.webm")
        else:
            video_output_path = os.path.join(output_dir, nom_base)

        input_img = params.get("input")
        end_img = params.get("end_img")
        control_dir = params.get("control_video")

        frames = int(params.get("frames", 33)) or 33
        fps = int(params.get("fps", 24)) or 24
        width = int(params.get("width", 832)) or 832
        height = int(params.get("height", 480)) or 480
        steps = int(params.get("steps", 20)) or 20
        cfg_scale = float(params.get("cfg_scale", 6.0))
        flow_shift = float(params.get("flow_shift", 3.0))

        self.log(f"Lancement de la génération vidéo ({frames} trames @ {fps} fps, résolution {width}x{height})...")

        video_path = generer_video_vulkan(
            prompt=prompt,
            sd_cli=self.config.get("sd_cli"),
            model_path=params.get("diffusion_model"),
            vae_path=params.get("vae"),
            t5xxl_path=params.get("t5xxl"),
            high_noise_model_path=params.get("high_noise_model"),
            video_frames=frames,
            fps=fps,
            width=width,
            height=height,
            steps=steps,
            cfg_scale=cfg_scale,
            flow_shift=flow_shift,
            seed=int(params.get("seed", -1)),
            negative_prompt=params.get("negative_prompt"),
            init_img=input_img,
            end_img=end_img,
            control_video_dir=control_dir,
            backend=self.config.get("backend", "diffusion=vulkan0,te=cpu"),
            threads=int(self.config.get("threads", 16)),
            output_path=video_output_path
        )

        # Génération facultative d'une ressource / script Godot 4 VideoStreamPlayer
        godot_scene_path = os.path.splitext(video_output_path)[0] + "_player.tscn"
        try:
            rel_video_name = os.path.basename(video_output_path)
            contenu_tscn = f"""[gd_scene format=3 uid="uid://video_{slugifier_texte(prompt)}"]

[node name="VideoPlayer" type="VideoStreamPlayer"]
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2
autoplay = true
loop = true
expand = true
# Chargez votre ressource vidéo WebM / Theora :
# stream = ExtResource("res://assets/{rel_video_name}")
"""
            with open(godot_scene_path, "w", encoding="utf-8") as f:
                f.write(contenu_tscn)
        except Exception:
            pass

        # Super-résolution IA optionnelle post-génération (--upscale)
        upscaled_video_path = None
        if params.get("upscale"):
            facteur_up = float(params.get("factor", 2.0))
            self.log(f"🚀 [Post-Processing] Upscaling IA de la vidéo ({facteur_up}x) via ESRGAN / Lanczos...")
            upscale_out = os.path.splitext(video_output_path)[0] + f"_upscaled_{int(facteur_up)}x.mp4"
            try:
                upscaled_video_path = upscale_video(
                    video_input_path=video_output_path,
                    output_path=upscale_out,
                    facteur=facteur_up,
                    mode=params.get("mode", "auto"),
                    upscale_model=params.get("upscale_model"),
                    sd_cli=self.config.get("sd_cli"),
                    backend=self.config.get("backend", "diffusion=vulkan0,te=cpu"),
                    log_fn=self.log
                )
            except Exception as e:
                self.log(f"Avertissement lors de l'upscaling vidéo post-génération : {e}", emoji="⚠️")

        return {
            "prompt": prompt,
            "video_path": video_path,
            "upscaled_video_path": upscaled_video_path,
            "godot_scene": godot_scene_path if os.path.exists(godot_scene_path) else None,
            "frames": frames,
            "fps": fps,
            "resolution": f"{width}x{height}",
            "status": "success"
        }
