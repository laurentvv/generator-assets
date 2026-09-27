"""ZCode SessionStart hook: injects the watch journal and the pending updates into the session.

Called automatically by ZCode at every session start on this workspace
(config: .zcode/config.json, SessionStart event). Does three things, without
ever blocking the session (empty output and code 0 if nothing to report):
1. if the last watch is older than VEILLE_MAX_HEURES, relaunches
   scripts/veille_versions.py in the background (detached process, output to
   output/veille/veille_arriere_plan.log) — new items will be visible
   in the next session;
2. injects into the context the pending updates (output/veille/
   maj_en_attente.json, maintained by the watch script — see AGENTS.md)
   and the entries of the last 7 days of docs/veille_journal.md;

Manual test: uv run python scripts/hook_session_start.py
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

# Reporting window and size limits to avoid inflating the context
JOURNAI_MAX_JOURS = 7
ENTREE_MAX_CHARS = 400
TOTAL_MAX_CHARS = 4000
MAJ_MAX_ITEMS = 10
MAJ_ITEM_MAX_CHARS = 300
MAJ_MAX_CHARS = 1500
VEILLE_MAX_HEURES = 20  # beyond that, the hook relaunches the watch in the background

# sd-cli issue to watch (regression master-848-9cdb6b6: silent crash of
# Flux + separate encoders on Vulkan/AMD; context in docs/veille_journal.md
# of 2026-09-07 and C:\SD\README.md). Stop watching only after installing
# a fixed release (then remove the block + state + this AGENTS.md entry).
ISSUE_API_TIMEOUT = 5  # seconds; the hook must never block the session
ISSUE_BLOC_MAX_CHARS = 900
COMMENTAIRE_MAX_CHARS = 280

# Journal header: entries in the form "- **YYYY-MM-DD • source • ..."
RE_ENTREE = re.compile(r"^- \*\*(\d{4}-\d{2}-\d{2})")


def projet_dir() -> Path:
    """Project directory: ZCODE_PROJECT_DIR variable provided by the hook, otherwise the script location."""
    env_dir = os.environ.get("ZCODE_PROJECT_DIR") or os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(env_dir) if env_dir else Path(__file__).resolve().parent.parent


def relancer_veille_si_necessaire(projet: Path) -> bool:
    """Relaunches the watch in the background if the last one is older than VEILLE_MAX_HEURES.

    The freshness of the last watch is read from the date of output/veille/rapports.log
    (appended at every run, even without new items). The process is detached: the
    session starts instantly, the full watch completes in the background.
    """
    marqueur = projet / "output" / "veille" / "rapports.log"
    if marqueur.is_file() and (time.time() - marqueur.stat().st_mtime) < VEILLE_MAX_HEURES * 3600:
        return False
    script = projet / "scripts" / "veille_versions.py"
    if not script.is_file():
        return False
    sortie = projet / "output" / "veille" / "veille_arriere_plan.log"
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) \
        | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        sortie.parent.mkdir(parents=True, exist_ok=True)
        with open(sortie, "ab") as log:
            subprocess.Popen([sys.executable, str(script)], cwd=str(projet),
                             stdout=log, stderr=subprocess.STDOUT,
                             creationflags=flags, close_fds=True)
    except OSError:
        return False
    return True


def bloc_maj_en_attente(projet: Path) -> str | None:
    """'Pending updates' block read from output/veille/maj_en_attente.json (no network access)."""
    fichier = projet / "output" / "veille" / "maj_en_attente.json"
    if not fichier.is_file():
        return None
    try:
        donnees = json.loads(fichier.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    items = donnees.get("items") or []
    if not items:
        return None
    lignes = []
    for item in items[:MAJ_MAX_ITEMS]:
        if item.get("details"):
            base = item["details"]
        elif item.get("installee") or item.get("disponible"):
            base = f"installed {item.get('installee', '?')} → available {item.get('disponible', '?')}"
            if item.get("action"):
                base += f" ; action: {item['action']}"
        else:
            base = json.dumps(item, ensure_ascii=False)
        if item.get("notes") and item["notes"] not in base:
            base += f" ; notes: {item['notes']}"
        lignes.append(f"- {item.get('source', '?')} : {base}"[:MAJ_ITEM_MAX_CHARS])
    texte = (
        f"⚠️ PENDING UPDATES (last detection {donnees.get('detecte_le', '?')}) — "
        "INSTRUCTION: mention them to the user in your very first reply (e.g. \"by the way, "
        "you have pending updates: …\"), even if their question is about something else, and "
        "offer to apply them following the \"🔄 Update process\" of AGENTS.md "
        "(one component at a time, NEVER without their explicit approval):\n" + "\n".join(lignes)
    )
    return texte[:MAJ_MAX_CHARS]


def api_github(chemin: str) -> dict | list | None:
    """Unauthenticated GET call to the GitHub API (public repo), None if unavailable."""
    url = f"https://api.github.com/{chemin}"
    try:
        requete = urllib.request.Request(
            url, headers={"Accept": "application/vnd.github+json",
                          "User-Agent": "generator-assets-veille"})
        with urllib.request.urlopen(requete, timeout=ISSUE_API_TIMEOUT) as reponse:
            return json.loads(reponse.read().decode("utf-8"))
    except (OSError, ValueError):
        return None


def extraire_entrees(journal: Path, limite: date) -> list[str]:
    """Returns the journal entries newer than the limit, truncated to ENTREE_MAX_CHARS."""
    entrees: list[str] = []
    courant: str | None = None
    for ligne in journal.read_text(encoding="utf-8").splitlines():
        match = RE_ENTREE.match(ligne)
        if match:
            if courant is not None:
                entrees.append(courant)
            courant = "" if date.fromisoformat(match.group(1)) < limite else ligne.strip()
        elif courant is not None:
            courant += " " + ligne.strip()
    if courant is not None:
        entrees.append(courant)
    return [e if len(e) <= ENTREE_MAX_CHARS else e[:ENTREE_MAX_CHARS].rstrip() + " […]" for e in entrees]


def bloc_journal(projet: Path) -> str | None:
    """'Watch journal' block: entries of the last JOURNAI_MAX_JOURS days."""
    journal = projet / "docs" / "veille_journal.md"
    if not journal.is_file():
        return None
    limite = date.today() - timedelta(days=JOURNAI_MAX_JOURS)
    entrees = extraire_entrees(journal, limite)
    if not entrees:
        return None
    return (
        f"Stack watch journal (last {JOURNAI_MAX_JOURS} days) — "
        f"full detail in docs/veille_journal.md:\n" + "\n".join(entrees)
    )


def main() -> int:
    projet = projet_dir()
    relancee = relancer_veille_si_necessaire(projet)
    parties = [b for b in (bloc_maj_en_attente(projet), bloc_journal(projet)) if b]
    if relancee:
        parties.insert(0, "🔁 Watch relaunched in the background (last check > 20 h) — "
                          "new items detected will be visible in the next session.")
    if not parties:
        return 0
    contexte = "\n\n".join(parties)
    if len(contexte) > TOTAL_MAX_CHARS:
        contexte = contexte[:TOTAL_MAX_CHARS].rstrip() + "\n[… see docs/veille_journal.md]"

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": contexte,
            }
        },
        sys.stdout,
        ensure_ascii=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
