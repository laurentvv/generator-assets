"""Watch (veille) data for the /veille page — READ-ONLY, report only.

The AGENTS.md watch rule is strict: the watch reports, it never updates.
This module only READS the artifacts scripts/veille_versions.py maintains:
  output/veille/maj_en_attente.json  (pending update items)
  output/veille/etat.json            (per-component installed vs upstream-seen)
  docs/veille_journal.md             (append-only journal, newest first)
  output/veille/notes/*.md           (per-update detailed notes)
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List

VEILLE_DIR = Path(__file__).resolve().parent.parent / "output" / "veille"
PENDING_PATH = VEILLE_DIR / "maj_en_attente.json"
STATE_PATH = VEILLE_DIR / "etat.json"
NOTES_DIR = VEILLE_DIR / "notes"
JOURNAL_PATH = Path(__file__).resolve().parent.parent / "docs" / "veille_journal.md"


def pending() -> Dict[str, Any]:
    data: Dict[str, Any] = {"detecte_le": None, "items": [], "count": 0}
    try:
        raw = json.loads(PENDING_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return data
    data["detecte_le"] = raw.get("detecte_le")
    items = raw.get("items") or []
    data["items"] = items
    data["count"] = len(items)
    return data


def _component_rows(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for name, info in state.items():
        if not isinstance(info, dict):
            continue
        installed = info.get("installee") or info.get("installe")
        seen = info.get("derniere_vue") or info.get("derniere_prerelease_vue")
        if installed is None and seen is None and not info.get("obsolete"):
            continue  # inventory-only entries (gguf file lists, repo maps)
        rows.append({
            "name": name,
            "installed": installed,
            "seen": seen,
            "obsolete": info.get("obsolete") or [],
            # seen != installed only means a newer upstream was VIEWED (report),
            # not that an update is approved — the AGENTS rule stays: never auto-update.
            "upstream_newer": bool(installed and seen and seen != installed),
        })
    rows.sort(key=lambda row: row["name"])
    return rows


def state() -> Dict[str, Any]:
    try:
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"rows": [], "detecte_le": None}
    return {"rows": _component_rows(raw), "detecte_le": None}


def journal_entries(limit: int = 14) -> List[Dict[str, str]]:
    """Parse the newest-first journal bullets: `- **<title>** — <body>`."""
    try:
        text = JOURNAL_PATH.read_text(encoding="utf-8")
    except OSError:
        return []
    entries: List[Dict[str, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- **"):
            continue
        body_part = stripped[len("- **"):]
        closing = body_part.find("**")
        if closing == -1:
            continue
        title = body_part[:closing].strip()
        body = body_part[closing + len("**"):].lstrip(" —-:").strip()
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})", title)
        entries.append({
            "title": title,
            "date": date_match.group(1) if date_match else "",
            "body": body,
        })
        if len(entries) >= limit:
            break
    return entries


def notes(limit: int = 60) -> List[Dict[str, Any]]:
    if not NOTES_DIR.exists():
        return []
    files = []
    for file in NOTES_DIR.glob("*.md"):
        try:
            stat = file.stat()
        except OSError:
            continue
        rel = file.relative_to(NOTES_DIR.parent.parent.parent).as_posix()
        files.append({"name": file.name, "rel": rel, "mtime": stat.st_mtime})
    files.sort(key=lambda item: -item["mtime"])
    return files[:limit]
