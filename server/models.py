"""Model inventory backing the /models page — READ-ONLY by design.

Aggregates the model constants declared in core/config.py (expected files:
present/missing + size), a raw disk inventory of the model directories, the
existing LoRA/upscaler scanners, active .env overrides and a curated
workflow -> models map. Deletion/download actions are deliberately NOT
offered here: AGENTS.md rules require restatement + re-downloadability
checks before touching anything under the model directories (incident
2026-09-08).
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

MODEL_EXTENSIONS = {".gguf", ".safetensors", ".onnx", ".pth", ".bin"}

# (section, core.config constant name, human label) — order = display order.
MODEL_CONSTANTS = [
    ("LLM enrichment", "DEFAULT_LLM_MODEL", "LLM prompt enrichment (llama.cpp)"),
    ("Images — Flux / SDXL", "DEFAULT_SD_MODEL", "FLUX.1-dev GGUF"),
    ("", "DEFAULT_CLIP_L", "CLIP-L text encoder"),
    ("", "DEFAULT_T5XXL", "T5-XXL text encoder"),
    ("", "DEFAULT_VAE", "Flux VAE (ae.safetensors)"),
    ("", "DEFAULT_SDXL_MODEL", "SDXL checkpoint"),
    ("", "DEFAULT_CONTROLNET_POSE", "ControlNet OpenPose (xinsir SDXL)"),
    ("Images — Qwen-Image-2.1", "DEFAULT_QWEN_IMAGE21_MODEL", "Qwen-Image-2.1 DiT GGUF"),
    ("", "DEFAULT_QWEN_IMAGE21_LLM", "Qwen-Image LLM encoder"),
    ("", "DEFAULT_QWEN_IMAGE21_VAE", "Qwen-Image VAE"),
    ("", "DEFAULT_QWEN_IMAGE21_TURBO_MODEL", "Turbo distilled Q8_0 (validated 2026-10-11)"),
    ("Video — Wan 2.1", "DEFAULT_WAN_MODEL", "Wan 2.1 T2V 1.3B GGUF"),
    ("", "DEFAULT_WAN_VAE", "Wan VAE"),
    ("", "DEFAULT_WAN_T5XXL", "UMT5-XXL encoder"),
    ("Video — VACE", "DEFAULT_VACE_MODEL", "Wan VACE distilled GGUF"),
    ("", "DEFAULT_VACE_T5XXL", "VACE T5-XXL encoder"),
    ("Video — MiniMax-H3", "DEFAULT_H3_REF2VA_MODEL", "H3 Ref2VA DiT GGUF"),
    ("", "DEFAULT_H3_VIDEO_VAE", "H3 video VAE"),
    ("", "DEFAULT_H3_AUDIO_VAE", "H3 audio VAE"),
    ("", "DEFAULT_H3_LLM", "H3 LLM"),
    # NB: DEFAULT_H3_REF2VA_TURBO_LORA is a LoRA NAME resolved by sd-cli's own
    # lora lookup, not a filesystem path — deliberately not listed here.
    ("Music — audio.cpp", "DEFAULT_MUSIC3_DIR", "MiniMax Music3 GGUF folder"),
    ("", "DEFAULT_MUSIC3_LM", "Music3 language model"),
    ("", "DEFAULT_ACESTEP15_DIR", "ACE-Step 1.5 GGUF folder"),
    ("", "DEFAULT_MUSIC_FLAMINGO_DIR", "Music Flamingo folder (QA)"),
    ("", "DEFAULT_MUSIC_FLAMINGO_LM", "Flamingo language model"),
    ("", "DEFAULT_MUSIC_FLAMINGO_MMPROJ", "Flamingo mmproj"),
    ("ONNX — CPU utilities", "DEFAULT_RMBG_MODEL", "RMBG-1.4 cutout (rembg)"),
    ("", "DEFAULT_DEEPBUMP_MODEL", "DeepBump PBR normals (material3d)"),
    ("", "DEFAULT_RIFE_MODEL", "RIFE frame interpolation"),
    ("", "DEFAULT_YUNET_MODEL", "YuNet face detection (makeup)"),
    ("Upscale", "DEFAULT_ESRGAN_MODEL", "RealESRGAN x4 anime (default)"),
]

# workflow -> core.config constant names it depends on (main ones; the
# workflow's own docs remain the source of truth for optional branches).
WORKFLOW_MODEL_MAP = {
    "generate": ["DEFAULT_SD_MODEL", "DEFAULT_CLIP_L", "DEFAULT_T5XXL", "DEFAULT_VAE", "DEFAULT_SDXL_MODEL"],
    "qwen_image": ["DEFAULT_QWEN_IMAGE21_MODEL", "DEFAULT_QWEN_IMAGE21_LLM", "DEFAULT_QWEN_IMAGE21_VAE", "DEFAULT_QWEN_IMAGE21_TURBO_MODEL"],
    "pose_control": ["DEFAULT_CONTROLNET_POSE"],
    "rembg": ["DEFAULT_RMBG_MODEL"],
    "material3d": ["DEFAULT_DEEPBUMP_MODEL"],
    "rife_interp": ["DEFAULT_RIFE_MODEL"],
    "character_makeup": ["DEFAULT_YUNET_MODEL"],
    "upscale": ["DEFAULT_ESRGAN_MODEL"],
    "video": ["DEFAULT_WAN_MODEL", "DEFAULT_WAN_VAE", "DEFAULT_WAN_T5XXL"],
    "video_vace": ["DEFAULT_VACE_MODEL", "DEFAULT_VACE_T5XXL"],
    "h3_ref2va": ["DEFAULT_H3_REF2VA_MODEL", "DEFAULT_H3_VIDEO_VAE", "DEFAULT_H3_AUDIO_VAE", "DEFAULT_H3_LLM"],
    "music_bg": ["DEFAULT_ACESTEP15_DIR", "DEFAULT_MUSIC3_DIR"],
    "chanson": ["DEFAULT_ACESTEP15_DIR"],
    "musique_adn": ["DEFAULT_ACESTEP15_DIR"],
    "musique_essence": ["DEFAULT_MUSIC3_DIR"],
}


def _config():
    from core import config as engine_config

    return engine_config


def _path_of(constant: str) -> Optional[Path]:
    value = getattr(_config(), constant, None)
    return Path(str(value)) if value else None


def _under(child: Path, parent: Optional[Path]) -> bool:
    if not parent:
        return False
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (ValueError, OSError):
        return False


def expected_models() -> List[Dict[str, Any]]:
    """Curated constants -> sections with present/missing + size."""
    sections: List[Dict[str, Any]] = []
    model_dir = _path_of("DEFAULT_MODEL_DIR")
    for section, constant, label in MODEL_CONSTANTS:
        path = _path_of(constant)
        present = bool(path and path.exists())
        size = 0
        if present:
            if path.is_dir():
                for file in path.rglob("*"):
                    if file.is_file():
                        try:
                            size += file.stat().st_size
                        except OSError:
                            pass
            else:
                try:
                    size = path.stat().st_size
                except OSError:
                    size = 0
        custom = bool(path and not _under(path, model_dir))
        item = {"label": label, "constant": constant, "path": str(path) if path else "—",
                "present": present, "size": size, "custom": custom, "is_dir": bool(path and path.is_dir())}
        if section:
            sections.append({"section": section, "items": [item]})
        elif sections:
            sections[-1]["items"].append(item)
    return sections


def workflow_dependencies() -> List[Dict[str, Any]]:
    """Workflow -> model constants presence, for the dependency strip."""
    catalog_names = _catalog_names()
    presence: Dict[str, bool] = {}
    for _, constant, _ in MODEL_CONSTANTS:
        path = _path_of(constant)
        presence[constant] = bool(path and path.exists())
    rows = []
    for workflow, constants in WORKFLOW_MODEL_MAP.items():
        rows.append({
            "workflow": workflow,
            "in_ui": workflow in catalog_names,
            "models": [{"constant": constant, "present": presence.get(constant, False)} for constant in constants],
        })
    rows.sort(key=lambda row: (not row["in_ui"], row["workflow"]))
    return rows


def _catalog_names() -> set:
    try:
        from server import introspection

        return set(introspection.workflow_names())
    except Exception:  # noqa: BLE001 — the page must render even mid-refactor
        return set()


def active_env_overrides() -> List[Dict[str, str]]:
    """Active env overrides, parsed from core/config.py source.

    Matches `CONSTANT = os.getenv("ENV_NAME", ...)` (including the multi-line
    parenthesized form — \\s spans newlines) and reports the ones actually set
    in the environment (charger_env has already merged .env into os.environ
    at import time).
    """
    config_file = Path(_config().__file__)
    try:
        source = config_file.read_text(encoding="utf-8")
    except OSError:
        return []
    overrides: Dict[str, str] = {}
    for match in re.finditer(
        r"^(DEFAULT_\w+)\s*=\s*\w+\.getenv\(\s*[\"']([A-Z0-9_]+)[\"']", source, re.MULTILINE
    ):
        constant, env_name = match.group(1), match.group(2)
        if env_name in os.environ:
            overrides[constant] = env_name
    return [{"constant": constant, "env": env_name, "value": os.environ[env_name]}
            for constant, env_name in sorted(overrides.items())]


def scan_roots() -> List[Path]:
    """Model directories to inventory: MODEL_DIR + any other root a constant points into."""
    roots = []
    model_dir = _path_of("DEFAULT_MODEL_DIR")
    if model_dir and model_dir.exists():
        roots.append(model_dir)
    for _, constant, _ in MODEL_CONSTANTS:
        path = _path_of(constant)
        if not path:
            continue
        base = path if path.is_dir() else path.parent
        candidate = base
        # Keep the closest existing ancestor (bounded walk-up, Windows-safe).
        while not candidate.exists() and candidate != candidate.parent:
            candidate = candidate.parent
        if candidate.exists() and model_dir and not candidate.is_relative_to(model_dir) and candidate not in roots:
            roots.append(candidate)
    return roots


def inventory() -> Dict[str, Any]:
    """Raw disk inventory of the scan roots (files with model extensions)."""
    import psutil

    folders: List[Dict[str, Any]] = []
    for root in scan_roots():
        files = []
        total = 0
        for file in root.rglob("*"):
            if not file.is_file() or file.suffix.lower() not in MODEL_EXTENSIONS:
                continue
            try:
                stat = file.stat()
            except OSError:
                continue
            total += stat.st_size
            files.append({"path": file.relative_to(root).as_posix(), "size": stat.st_size})
        files.sort(key=lambda item: -item["size"])
        free = psutil.disk_usage(str(root)).free
        folders.append({"root": str(root), "files": files, "total": total,
                        "count": len(files), "free": free,
                        "free_gb": round(free / (1 << 30))})
    return {"folders": folders}


def loras() -> List[Dict[str, Any]]:
    return list(_config().lister_loras())


def upscalers() -> List[Dict[str, Any]]:
    return list(_config().lister_upscalers())
