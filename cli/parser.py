#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Builds the CLI argument parser and the workflow parameters."""

import argparse
from workflows.base import WorkflowRegistry
from core.config import (
    DEFAULT_BACKEND,
    DEFAULT_CLIP_L,
    DEFAULT_LLAMA_CLI,
    DEFAULT_LLM_MODEL,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_SD_CLI,
    DEFAULT_SD_MODEL,
    DEFAULT_STYLE_ANCHOR,
    DEFAULT_T5XXL,
    DEFAULT_THREADS,
    DEFAULT_VAE,
)

# ==============================================================================
def construire_parseur() -> argparse.ArgumentParser:
    """Builds the CLI argument parser (extracted from main for testability of the consumer contract)."""
    parser = argparse.ArgumentParser(
        prog="generator-assets",
        description="⚔️ AI Workflow System for Godot 2D & 3D Assets (Flux.1 Vulkan + LoRAs + PBR Materials + Blender Mesh GLB + ESRGAN Upscale).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
3D & 2D Workflow Examples:
  # 1. PBR Meshed 3D Model via Blender (Cube, Tile, Pillar, Sphere, Card)
  python main.py -w mesh3d "ancient chest adorned with dark steel runes" --shape cube
  python main.py -w mesh3d -i godot_assets/casque.png --shape card -o casque_3d

  # 1b. Volumetric AI 3D Object from an image or a prompt (TRELLIS.2 GGUF, Vulkan)
  python main.py -w mesh_ia -i godot_assets/casque.png --res 512
  python main.py -w mesh_ia "dragon skull carved in obsidian" --res 1024

  # 2. Complete PBR 3D Material Pack (Albedo, Normal, Roughness, ORM, Height + Godot .tres)
  python main.py -w material3d "dark stone slabs with purple runes and moss" -s 1024

  # 3. 360° Equirectangular Skybox for 3D Lighting & Sky
  python main.py -w skybox "dark fantasy night sky with purple nebula and moons"

  # 4. 3D Modeling Turnaround Sheet for Blender (calibrated Front + Profile)
  python main.py -w turnaround3d "shadow knight in full plate armor"

  # 5. AI Upscaling of a texture to 4K with an ESRGAN model
  python main.py -w upscale -i godot_assets/casque.png --upscale-model anime --factor 4

  # Diagnostics
  python main.py --list-workflows
  python main.py --list-upscalers
  python main.py --list-loras
  python main.py --check
  python main.py --interactive
        """
    )

    # Main parameters
    parser.add_argument(
        "prompt",
        nargs="?",
        default=None,
        help="Concept or textual description of the asset."
    )
    parser.add_argument(
        "-w", "--workflow",
        default="generate",
        help="Workflow name: generate, mesh3d, mesh_ia, material3d, skybox, turnaround3d, upscale, spritesheet, variations, tileable, pixelart, batch."
    )
    parser.add_argument(
        "-p", "--prompt",
        dest="prompt_flag",
        help="Alternative description via flag."
    )
    parser.add_argument(
        "-i", "--input",
        dest="input",
        help="Path of the source image for mesh3d, upscale, material3d, pixelart or variations."
    )
    parser.add_argument(
        "-t", "--type",
        choices=["item", "character", "prop", "tile", "1", "2", "3"],
        default="item",
        help="Asset type: item (default), character, prop, tile."
    )
    parser.add_argument(
        "--shape",
        choices=["tile", "cube", "pillar", "cylinder", "sphere", "card", "cutout"],
        default="tile",
        help="3D geometric shape for the mesh3d workflow (default: 'tile')."
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file name without extension."
    )
    parser.add_argument(
        "-d", "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Destination folder for the Godot assets (default: '{DEFAULT_OUTPUT_DIR}')."
    )
    parser.add_argument(
        "-s", "--size",
        type=int,
        default=None,
        help="Final square resolution in pixels."
    )

    # LoRA & Upscaler management
    groupe_ia_ext = parser.add_argument_group("LoRAs & Upscalers")
    groupe_ia_ext.add_argument(
        "-l", "--lora",
        action="append",
        dest="loras",
        help="Applies a LoRA in the form 'name:weight' (e.g. -l 'pixel_art:0.8'). Repeatable."
    )
    groupe_ia_ext.add_argument(
        "--lora-dir",
        help="Folder containing the LoRA files (.safetensors)."
    )
    groupe_ia_ext.add_argument(
        "--upscale-model",
        help="Name or path of the ESRGAN upscaling model (e.g. 'anime', 'ultrasharp', '4x-UltraSharp.pth')."
    )
    groupe_ia_ext.add_argument(
        "--upscale",
        action="store_true",
        help="Enables automatic AI upscaling (ESRGAN 4x or Lanczos) after generation."
    )

    # Options shared across workflow families (§2.2 audit keystone): each
    # flag below is read by workflows from DIFFERENT families (2D,
    # video/3D, audio, character) — no single owner, so it stays in the
    # flat table. Any mono-workflow or intra-family flag now lives in the
    # PARAMETRES of its class ("Options per Workflow" group below).
    groupe_wf = parser.add_argument_group("Options shared across workflow families")
    groupe_wf.add_argument("--factor", type=float, default=None, help="Upscaling factor for upscale or interpolation (e.g. 2.0, 4.0; default: workflow-specific — 2.0, or 4.0 when AI upscale is active for generate).")
    groupe_wf.add_argument("--mode", choices=["prop", "plate"], default="prop", help="asset_blendkit: prop = Godot .glb + Workbench preview | plate = Cycles/EEVEE scenery render for the chain (default: prop).")
    groupe_wf.add_argument("--columns", type=int, default=4, help="Number of columns for the sprite sheet.")
    groupe_wf.add_argument("--frames", type=int, default=None, help="Number of animation frames (video, vfx_flipbook, rife_interp, anim_loop, h3_ref2va; default: workflow-specific — e.g. 33 for video, 22 for h3_ref2va, 16 for anim_loop).")
    groupe_wf.add_argument("--emotions", default="neutral,happy,angry,sad,hurt", help="Comma-separated list of emotions for rpg_portrait and tts_dialogue.")
    groupe_wf.add_argument("--fps", type=float, default=None, help="FPS rate for anim_loop (workflow default: 12.0) and video (workflow default: 24).")
    groupe_wf.add_argument("--samples", type=int, default=48, help="Number of Cycles render samples for Blender (default: 48).")
    groupe_wf.add_argument("--width", type=int, default=None, help="Custom width in pixels (skybox: 2:1 panorama, video).")
    groupe_wf.add_argument("--height", type=int, default=None, help="Custom height in pixels (skybox: 2:1 panorama, video).")
    # Options declared by the workflows themselves (§2.2 audit keystone): each
    # class exposes PARAMETRES (see workflows/base.py). Migration COMPLETE — the
    # 5 families (monoplan, audio, video/3D, character, 2D) have left the flat
    # table, which now only keeps cross-family options. Aggregate CLI
    # surface unchanged (consumer contract, frozen by tests/surface_cli.json).
    groupe_declares = parser.add_argument_group("Options per Workflow (declared by the workflows)")
    for declaration in WorkflowRegistry.parametres_declares():
        d = dict(declaration)
        flags = d.pop("flags")
        groupe_declares.add_argument(*flags, **d)

    # General rendering parameters
    groupe_ia = parser.add_argument_group("AI & Rendering Parameters")
    groupe_ia.add_argument("--use-llm", action="store_true", default=False, help="Enables enrichment by local LLM (disabled by default).")
    groupe_ia.add_argument("--no-llm", action="store_true", default=False, help="Disables LLM enrichment (default behavior).")
    groupe_ia.add_argument("--strength", type=float, default=0.55, help="Img2Img denoising strength (default: 0.55).")
    groupe_ia.add_argument("--steps", type=int, default=25, help="Number of Flux diffusion steps (default: 25).")
    groupe_ia.add_argument("--guidance", type=float, default=3.5, help="Flux guidance (default: 3.5).")
    groupe_ia.add_argument("--cfg-scale", type=float, default=1.0, help="CFG scale (default: 1.0).")
    groupe_ia.add_argument("--seed", type=int, default=-1, help="Random seed (-1 for random).")
    groupe_ia.add_argument("--tolerance", type=int, default=60, help="Flood-fill cutout tolerance (default: 60).")
    groupe_ia.add_argument("--style", default=DEFAULT_STYLE_ANCHOR, help="Custom visual style guide.")

    # Utility modes
    parser.add_argument("--interactive", action="store_true", help="Starts the interactive session.")
    parser.add_argument("--verbose", action="store_true", help="Detailed logging (DEBUG): engine commands, full tracebacks.")
    parser.add_argument("--check", action="store_true", help="Checks the presence of the executables and models.")
    parser.add_argument("--list-workflows", action="store_true", help="Shows the list of available workflows.")
    parser.add_argument("--list-loras", action="store_true", help="Shows the list of installed LoRAs.")
    parser.add_argument("--list-upscalers", action="store_true", help="Shows the list of installed upscaling models.")
    parser.add_argument(
        "--update-sd",
        nargs="?",
        const="check",
        choices=["check", "download", "build", "rollback", "list-backups"],
        help="Manages the update and Vulkan build of stable-diffusion.cpp (check, download, build, rollback, list-backups)."
    )
    parser.add_argument("--sd-install-dir", help="Installation folder of stable-diffusion.cpp (default: C:\\SD).")
    parser.add_argument("--sd-source-dir", help="Git source folder for the Vulkan build (default: C:\\GIT\\stable-diffusion.cpp).")
    parser.add_argument(
        "--update-llama",
        nargs="?",
        const="check",
        choices=["check", "download", "build", "rollback", "list-backups"],
        help="Manages the update and Vulkan build of llama.cpp (check, download, build, rollback, list-backups)."
    )
    parser.add_argument("--llama-install-dir", help="Installation folder of llama.cpp (default: C:\\llama.cpp).")
    parser.add_argument("--llama-source-dir", help="Git source folder for the Vulkan build (default: C:\\GIT\\llama.cpp).")
    parser.add_argument(
        "--update-vulkan",
        "--update-all",
        dest="update_vulkan",
        nargs="?",
        const="check",
        choices=["check", "download", "build", "rollback"],
        help="Manages the complete update of the whole Vulkan AI Suite (stable-diffusion.cpp + llama.cpp)."
    )

    # Paths
    groupe_chemins = parser.add_argument_group("Paths & Executables")
    groupe_chemins.add_argument("--llama-cli", default=DEFAULT_LLAMA_CLI, help="Path to llama-cli.exe")
    groupe_chemins.add_argument("--llm-model", default=DEFAULT_LLM_MODEL, help="Path to the LLM GGUF model")
    groupe_chemins.add_argument("--sd-cli", default=DEFAULT_SD_CLI, help="Path to sd-cli.exe")
    groupe_chemins.add_argument("--sd-model", default=DEFAULT_SD_MODEL, help="Path to flux1-dev GGUF")
    groupe_chemins.add_argument("--clip-l", default=DEFAULT_CLIP_L, help="Path to clip_l.safetensors")
    groupe_chemins.add_argument("--t5xxl", default=DEFAULT_T5XXL, help="Path to t5xxl_fp16.safetensors")
    groupe_chemins.add_argument("--vae", default=DEFAULT_VAE, help="Path to ae.safetensors")
    groupe_chemins.add_argument("--backend", default=DEFAULT_BACKEND, help="sd-cli backend")
    groupe_chemins.add_argument("--threads", type=int, default=DEFAULT_THREADS, help="CPU threads for encoders")

    return parser


def surface_cli(parseur: argparse.ArgumentParser) -> list:
    """Stable signature of the argparse surface (consumer contract freeze).

    One entry per option: sorted flags, dest, action class, default, sorted
    choices, nargs, type name. The help is deliberately excluded (cosmetic).
    String defaults are normalized to "posix" (backslashes → slashes):
    os.path.join produces OS-dependent paths for the same value
    (C:\\x\\y on Windows, C:\\x/y on Linux) and the freeze must stay comparable
    from one platform to another (ubuntu + windows CI).
    Feeds the freeze test tests/test_cli_contract.py: any drift in dest,
    default or type breaks the consumer repositories' contract
    (ai-doc2video, video-analys-ia) without the anti-duplicate test seeing it.
    """
    entrees = []
    for action in parseur._actions:
        default = action.default
        if isinstance(default, str):
            default = default.replace("\\", "/")
        entrees.append([
            sorted(action.option_strings),
            action.dest,
            type(action).__name__,
            repr(default),
            sorted(action.choices) if action.choices is not None else None,
            action.nargs,
            getattr(action.type, "__name__", None) if action.type is not None else None,
        ])
    entrees.sort(key=lambda e: (e[1], e[0]))
    return entrees


def construire_params(args: argparse.Namespace, prompt_texte: str) -> dict:
    """Builds the workflow parameters from the CLI arguments.

    Generic: starts from vars(args) (argparse dest == params key) and only
    forwards the keys actually provided (non None) — when an option is not
    passed, each workflow applies its own default (consumer contract,
    see tests/test_cli_contract.py). The few derived keys (normalized type,
    LLM, preview, portrait) are handled explicitly below; the CLI control
    keys (engine paths, list/check/update-* flags) never enter it.
    """
    params = vars(args).copy()

    for cle in (
        "workflow", "prompt_flag", "interactive", "check", "verbose", "list_workflows",
        "list_loras", "list_upscalers",
        "update_sd", "sd_install_dir", "sd_source_dir",
        "update_llama", "llama_install_dir", "llama_source_dir",
        "update_vulkan",
        "llama_cli", "llm_model", "sd_cli", "sd_model", "clip_l", "t5xxl",
        "vae", "backend", "threads", "style", "no_preview",
    ):
        params.pop(cle, None)

    params["prompt"] = prompt_texte
    params["type"] = {"1": "item", "2": "character", "3": "prop"}.get(args.type, args.type)
    params["preview"] = not args.no_preview
    params["no_llm"] = True if args.no_llm else not args.use_llm
    params["use_llm"] = args.use_llm and not args.no_llm
    params["sans_llm"] = True if args.no_llm else not args.use_llm
    params["portrait"] = args.portrait or args.input

    return {cle: valeur for cle, valeur in params.items() if valeur is not None}

