"""Filesystem layout and path safety for the web UI.

All runtime state lives under output/_webui/ (already git-ignored): SQLite
database, per-job logs, uploads, thumbnail cache. File serving is restricted
to the allowed roots below with an explicit traversal guard.
"""

import os
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_CHECK_CHARGE = REPO_ROOT / "scripts" / "check_charge_systeme.py"

# Overridable for tests (tmp dirs) without touching the real output tree.
DATA_DIR = Path(os.environ.get("WEBUI_DATA_DIR") or (REPO_ROOT / "output" / "_webui"))
DB_PATH = DATA_DIR / "factory.db"
LOG_DIR = DATA_DIR / "logs"
UPLOAD_DIR = DATA_DIR / "uploads"
THUMB_DIR = DATA_DIR / "thumbs"

# Roots the UI may read/serve files from (inputs + generated assets).
ALLOWED_ROOTS: tuple[Path, ...] = (
    REPO_ROOT / "output",
    REPO_ROOT / "godot_assets",
)


def ensure_dirs() -> None:
    for directory in (DATA_DIR, LOG_DIR, UPLOAD_DIR, THUMB_DIR):
        directory.mkdir(parents=True, exist_ok=True)


class UnsafePath(Exception):
    """A user-provided path escapes the allowed roots."""


def resolve_allowed(raw: str) -> Path:
    """Resolve a user-provided path against the allowed roots.

    Accepts absolute paths inside the roots, or repo-relative paths. Raises
    UnsafePath on traversal attempts or paths outside the roots. Existence is
    NOT checked here (callers decide whether a missing file is an error).
    """
    if not raw or not isinstance(raw, str):
        raise UnsafePath("empty path")
    candidate = Path(raw)
    if candidate.is_absolute():
        candidates = [candidate]
    else:
        # Repo-relative (the normal case, e.g. "output/x.png"), relative to an
        # allowed root, or relative to a root's parent. Deduplicated; the
        # containment check below is what actually guards.
        candidates = [
            REPO_ROOT / candidate,
            *(root / candidate for root in ALLOWED_ROOTS),
            *(root.parent / candidate for root in ALLOWED_ROOTS),
        ]

    def _inside(path: Path) -> bool:
        for root in ALLOWED_ROOTS:
            root_resolved = root.resolve()
            if path == root_resolved or path.is_relative_to(root_resolved):
                return True
        return False

    fallback: Optional[Path] = None
    seen: set = set()
    for cand in candidates:
        resolved = cand.resolve()
        if resolved in seen or not _inside(resolved):
            continue
        seen.add(resolved)
        if resolved.exists():
            return resolved
        if fallback is None:
            fallback = resolved
    if fallback is not None:
        return fallback  # inside a root but missing — callers decide (404)
    raise UnsafePath(f"path outside allowed roots: {raw}")


def relpath_for(path: Path) -> str:
    """Posix-style path relative to the repo root, for /files?p= URLs."""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()
