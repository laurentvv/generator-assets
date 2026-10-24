"""Curated UI layer on top of the introspected workflow registry.

Pure data, no imports: introspection.py merges this with the live registry and
the argparse surface. Unknown dests (workflow evolution) are ignored with a
warning — a workflow missing from WORKFLOW_META falls back to its family
defaults, so adding a workflow never breaks the UI.

Sources of the curated values: docs/MEMORY_BANK.md validated recipes and
README workflow catalogue (2026-10-11).
"""

# ---------------------------------------------------------------- families --

FAMILIES = [
    {"key": "images",     "label": "Images 2D & UI",        "icon": "🖼️"},
    {"key": "textures3d", "label": "Textures, 3D & Skies",  "icon": "🧱"},
    {"key": "characters", "label": "Characters & Wardrobe", "icon": "🧍"},
    {"key": "video",      "label": "Video",                 "icon": "🎬"},
    {"key": "voice",      "label": "Voice & TTS",           "icon": "🗣️"},
    {"key": "music",      "label": "Music & SFX",           "icon": "🎵"},
    {"key": "utils",      "label": "Utilities",             "icon": "⚡"},
]

# workflow name -> family (every registry workflow must map; fallback: utils).
WORKFLOW_FAMILY = {
    "generate": "images", "qwen_image": "images", "moss_image": "images", "spritesheet": "images",
    "autotile_pack": "images", "tileable": "images", "pixelart": "images",
    "variations": "images", "ui_9slice": "images", "rembg": "images",
    "rpg_portrait": "images", "ip_adapter": "images",
    "miniature": "images", "carte_fin": "images", "icone_jeu": "images",
    "titre_anime": "images", "planche_pdf": "images", "maquette_ui": "images",
    "doc_texte": "utils", "classeur_donnees": "utils", "photo_develop": "utils",
    "filigrane_batch": "images",
    "prepa_i2v": "video", "ocr_pdf": "utils", "rapport_deck": "utils", "son_convertir": "voice", "projet_montage": "video",
    "material3d": "textures3d", "mesh3d": "textures3d", "mesh_ia": "textures3d",
    "voxel3d": "textures3d", "skybox": "textures3d", "turnaround3d": "textures3d",
    "flowmap": "textures3d", "asset_blendkit": "textures3d",
    "character3d": "characters", "character_makeup": "characters",
    "makehuman_clothes": "characters", "outfit": "characters",
    "pose_control": "characters", "animal_godot": "characters",
    "video": "video", "video_vace": "video", "video_multishot": "video",
    "h3_ref2va": "video", "monoplan_ia": "video", "rife_interp": "video",
    "vfx_flipbook": "video", "anim_loop": "video",
    "voix_off": "voice", "voix_perso": "voice", "voix_robot": "voice",
    "voix_conversion": "voice", "tts_dialogue": "voice", "audio_upscale": "voice",
    "music_bg": "music", "chanson": "music", "musique_adn": "music",
    "musique_essence": "music", "acestep_cover": "music", "retrait_voix": "music",
    "sfx": "music", "audio_ambience": "music",
    "upscale": "utils", "batch": "utils",
}

# Shared argparse dests surfaced per family (besides prompt/output handled
# globally). Engine override dests are never shown (see HIDDEN_DESTS).
SHARED_BY_FAMILY = {
    "images": ["seed", "steps", "guidance", "size", "input", "loras", "strength"],
    "textures3d": ["seed", "steps", "guidance", "size", "input", "loras", "samples"],
    "characters": ["seed", "steps", "guidance", "input", "samples", "emotions"],
    "video": ["seed", "frames", "fps", "width", "height", "input", "cfg_scale"],
    "voice": ["seed", "duration", "input", "emotions"],
    "music": ["seed", "duration", "input"],
    "utils": ["seed", "input", "factor"],
}

# Never shown in the UI (expert engine plumbing; core/config.py env overrides
# are the sanctioned way to change these).
HIDDEN_DESTS = {
    "llama_cli", "llm_model", "sd_cli", "sd_model", "clip_l", "t5xxl", "vae",
    "backend", "threads", "style", "tolerance", "use_llm", "no_llm",
    "output_dir", "lora_dir", "upscale_model", "upscale", "upscale_mode",
    "verbose", "interactive", "workflow", "prompt_flag", "list_workflows",
    "list_loras", "list_upscalers", "check", "update_sd", "update_llama",
    "update_vulkan", "sd_install_dir", "sd_source_dir", "llama_install_dir",
    "llama_source_dir", "no_preview", "preview",
}

# Dest -> widget override (inferred widget otherwise, see introspection.py).
WIDGET_OVERRIDES = {
    "seed": "seed",
    "loras": "loras",
    "lyrics": "textarea",
    "prompt_file": "path",
    "recipe": "path",
    "file": "path",
}

# Dest groups that act as an input media path (picker + upload widget).
INPUT_PATH_DESTS = {
    "input": "image", "end_img": "image", "control_video": "folder",
    "portrait": "image", "audio": "audio", "voix_ref": "audio",
    "voice_ref": "audio", "ref_audio": "audio", "monoplan_source": "video",
    "negative_prompt_file": "file", "file": "file", "recipe": "file",
}

# ------------------------------------------------------------- workflows ----

# name -> {primary, estimate, heavy, presets, warnings}
# primary: dests shown in the main Parameters section (family shared dests
# come on top; everything else falls into Advanced).
WORKFLOW_META = {
    "generate": {
        "primary": ["type", "segmenter"],
        "estimate": "≈1–3 min (Flux Vulkan)",
        "presets": [
            {"name": "Item cutout (default recipe)", "values": {"type": "item", "segmenter": "auto"}},
            {"name": "Character sprite", "values": {"type": "character"}},
        ],
    },
    "qwen_image": {
        "primary": ["qwen_turbo", "negative_prompt", "width", "height"],
        "estimate": "≈2 min turbo · ≈16 min base",
        "presets": [
            {"name": "Turbo validated 2026-10-11 (~123 s)", "values": {"qwen_turbo": True, "seed": 42}},
            {"name": "Base 40 steps CFG 6", "values": {"steps": 40, "cfg_scale": 6.0, "width": 1152, "height": 640}},
        ],
        "warnings": [
            "RESEARCH license — personal / non-commercial use only.",
            "turbo: steps/CFG are forced (8 / 1.0) — leave them unset.",
        ],
    },
    "moss_image": {
        "primary": ["width", "height"],
        "estimate": "≈36 min @1024² (USB disk-bound load + 42.5-43 s/step)",
        "presets": [
            {"name": "Validated 2026-10-24 (1024², 50 steps, CFG 3)", "values": {"seed": 42}},
        ],
        "warnings": [
            "Small secondary text garbles (documented base weakness).",
            r"Models live on D:\Modeles_LLM (USB HDD) — cold load ≈ 28 min; env MOSS_IMAGE_*_PATH to repoint.",
        ],
    },
    "spritesheet": {"primary": ["columns"], "estimate": "≈3–6 min"},
    "autotile_pack": {"primary": ["biome_a", "biome_b"], "estimate": "≈5–10 min"},
    "tileable": {"primary": [], "estimate": "≈2 min"},
    "pixelart": {"primary": ["palette", "grid_size"], "estimate": "seconds (CPU)", "heavy": False},
    "variations": {"primary": ["themes"], "estimate": "≈1 min/variant"},
    "ui_9slice": {"primary": ["margin", "auto_margin"], "estimate": "≈2 min"},
    "rembg": {"primary": ["segmenter"], "estimate": "seconds (CPU)", "heavy": False},
    "rpg_portrait": {"primary": ["emotions"], "estimate": "≈1 min/emotion"},
    "ip_adapter": {"primary": ["items"], "estimate": "≈1 min/item"},
    "material3d": {"primary": ["pbr_engine", "normal_strength"], "estimate": "≈3–8 min"},
    "mesh3d": {"primary": ["shape", "samples"], "estimate": "≈2–5 min (Blender)"},
    "mesh_ia": {
        "primary": ["res", "faces_cible", "mesh_moteur", "fov"],
        "estimate": "512 ≈11–14 min · 1024 ≈55 min",
        "presets": [
            {"name": "Iteration 512 (fast look)", "values": {"res": 512}},
            {"name": "Master 1024 (hero asset)", "values": {"res": 1024}},
            {"name": "Game prop, decimated 10k faces", "values": {"res": 512, "faces_cible": 10000}},
            {"name": "Pixal3D flat colors (validated)", "values": {"mesh_moteur": "pixal3d", "res": 512}},
        ],
    },
    "voxel3d": {"primary": ["grid_size", "voxel_depth", "voxel_scale"], "estimate": "seconds (CPU)", "heavy": False},
    "skybox": {"primary": ["width", "height"], "estimate": "≈4–8 min (2:1)"},
    "turnaround3d": {"primary": [], "estimate": "≈2× image"},
    "flowmap": {"primary": ["angle", "flow_type", "turbulence"], "estimate": "seconds (CPU)", "heavy": False},
    "asset_blendkit": {"primary": ["query", "asset_type", "mode", "licence", "index"], "estimate": "download + render"},
    "character3d": {"primary": ["portrait", "character", "age", "gender", "eye_color", "makeup_only"], "estimate": "10–25 min (Blender)"},
    "character_makeup": {"primary": ["portrait", "makeup_only"], "estimate": "≈5–15 min"},
    "makehuman_clothes": {"primary": ["parts", "mpfb_dir"], "estimate": "≈3–10 min"},
    "outfit": {"primary": ["character", "top", "shoes"], "estimate": "≈10 min"},
    "pose_control": {"primary": ["pose"], "estimate": "≈3 min"},
    "animal_godot": {"primary": ["animal_prefixe", "animal_actions"], "estimate": "≈5–10 min"},
    "video": {
        "primary": ["flow_shift", "end_img", "control_video"],
        "estimate": "10–40 min (model-dependent)",
        "warnings": ["Wan: ≤ 20 frames + vae-on-cpu on the current sd-cli build (MEMORY_BANK)."],
    },
    "video_vace": {
        "primary": [],
        "estimate": "≈28 min (validated recipe)",
        "presets": [
            {"name": "Validated 13f @16fps 832×480", "values": {"frames": 13, "fps": 16, "cfg_scale": 1.0, "seed": 42}},
        ],
    },
    "video_multishot": {
        "primary": [],
        "estimate": "≈10 min (65 frames)",
        "warnings": ["LTX-2.5: frames = 1 + multiple of 8, max 81; CFG ≤ 1.5; no negative prompt."],
    },
    "h3_ref2va": {
        "primary": ["turbo", "ref_frames", "ref_audio", "max_vram", "dry_run"],
        "estimate": "≈38 min turbo · ≈70 min base (22 frames)",
        "presets": [{"name": "Turbo (mandatory, validated §1.16)", "values": {"turbo": True}}],
        "warnings": ["Always --turbo (validated 2026-09-09, ~2× faster)."],
    },
    "monoplan_ia": {
        "primary": ["monoplan_frames", "monoplan_duration", "zoom_debut", "zoom_fin", "ambiance", "monoplan_source", "carton_titre", "upscale_4k"],
        "estimate": "≈15 min 1080p · ≈18 min 4K",
        "presets": [
            {"name": "Cinematic default (65f)", "values": {"monoplan_frames": 65}},
            {"name": "4K YouTube master", "values": {"monoplan_frames": 65, "upscale_4k": True}},
        ],
        "warnings": ["LTX-2.5: frames = 1 + multiple of 8.", "Prompt should include an audio sentence (LTX rule)."],
    },
    "rife_interp": {"primary": ["factor", "columns"], "estimate": "seconds–minutes (CPU)", "heavy": False},
    "vfx_flipbook": {"primary": ["vfx_type", "frames"], "estimate": "≈5 min"},
    "anim_loop": {"primary": ["mode_2d", "frames", "fps"], "estimate": "seconds (CPU)", "heavy": False},
    "voix_off": {"primary": ["moteur", "voix_ref", "instruct", "lufs_voix"], "estimate": "≈1–2 min"},
    "voix_perso": {"primary": ["kokoro_voice", "instruct", "pitch_ratio", "whisper", "hollow", "brut"], "estimate": "≈1–2 min"},
    "voix_robot": {"primary": ["robot_voice", "robot_pitch", "robot_ringmod", "robot_tempo", "robot_gain"], "estimate": "≈1 min", "warnings": ["Defaults are the FROZEN validated recipe — don't improvise (§1.25)."]},
    "voix_conversion": {"primary": ["audio", "voice_ref"], "estimate": "≈1–2 min"},
    "tts_dialogue": {"primary": ["emotions", "pitch"], "estimate": "≈1 min/line"},
    "audio_upscale": {"primary": ["upsr_variante", "upsr_rate"], "estimate": "CPU RTF ~13 (minutes)", "warnings": ["Mono output; refuses input > 24 kHz (§1.27)."]},
    "music_bg": {
        "primary": ["moteur", "variante", "lufs", "loop_mode", "candidats", "force_bpm", "tonalite", "mesure", "lyrics", "analyse"],
        "estimate": "≈5–15 min (× candidates)",
        "presets": [
            {"name": "Game bed −30 LUFS (validated)", "values": {"lufs": -30, "loop_mode": "percussive", "candidats": 3}},
            {"name": "Gothic rock 83 BPM C# minor", "values": {"force_bpm": 83, "tonalite": "C# minor", "lufs": -30}},
        ],
    },
    "chanson": {"primary": ["style_musique", "langue", "lyrics"], "estimate": "≈15 min / 4-min song"},
    "musique_adn": {"primary": ["langue", "negatif"], "estimate": "≈5–15 min"},
    "musique_essence": {"primary": ["scale", "keep_vocals"], "estimate": "≈10 min", "warnings": ["scale plateau 0.40–0.45 (validated)."]},
    "acestep_cover": {"primary": ["audio", "cover_threads"], "estimate": "CPU RTF ~2.6"},
    "retrait_voix": {"primary": ["music_backend"], "estimate": "≈2–5 min"},
    "sfx": {"primary": ["sfx_engine", "duration"], "estimate": "ia ≈1 min · procedural seconds"},
    "audio_ambience": {"primary": ["ambience_type", "duration"], "estimate": "seconds (CPU)", "heavy": False},
    "upscale": {"primary": ["factor"], "estimate": "≈1–4 min"},
    "batch": {"primary": ["file", "continue_on_error"], "estimate": "depends on recipe"},
}

# Workflows that skip the system load gate (pure CPU, seconds): derived from
# WORKFLOW_META[...]["heavy"] is False; this list is the authoritative default.
LIGHT_DEFAULTS = {
    "pixelart", "flowmap", "voxel3d", "rembg", "audio_ambience", "anim_loop",
    "rife_interp",
}

# Family-level standing notices (shown on every workflow of the family).
FAMILY_WARNINGS = {
    "images": ["Prompt in English (repo rule)."],
    "textures3d": ["Prompt in English (repo rule)."],
    "characters": ["Prompt in English (repo rule)."],
    "video": ["Prompt in English (repo rule)."],
    "voice": ["Text input is French for voix_off/chanson — English for voix_perso/voix_robot (§1.13)."],
    "music": ["Prompt in English (repo rule)."],
}

# Rough default durations used for the queue ETA badge (seconds, turbo-ish).
ESTIMATE_SECONDS = {
    "pixelart": 5, "flowmap": 5, "voxel3d": 10, "rembg": 15, "audio_ambience": 10,
    "anim_loop": 20, "rife_interp": 60, "sfx": 60, "tts_dialogue": 60,
    "voix_off": 90, "voix_perso": 90, "voix_robot": 60, "voix_conversion": 90,
    "generate": 120, "tileable": 120, "variations": 120, "ui_9slice": 120,
    "spritesheet": 240, "ip_adapter": 120, "rpg_portrait": 180, "material3d": 300,
    "mesh3d": 180, "skybox": 360, "turnaround3d": 240, "upscale": 120,
    "qwen_image": 130, "makehuman_clothes": 300, "outfit": 600, "pose_control": 180,
    "animal_godot": 420, "vfx_flipbook": 300, "music_bg": 600, "musique_adn": 600,
    "musique_essence": 600, "retrait_voix": 180, "acestep_cover": 480,
    "character_makeup": 600, "character3d": 900, "asset_blendkit": 600,
    "video_multishot": 600, "monoplan_ia": 900, "video": 1500, "video_vace": 1680,
    "h3_ref2va": 2280, "mesh_ia": 700, "batch": 600, "audio_upscale": 600,
    "chanson": 900,
}
