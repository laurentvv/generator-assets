"""Hook SessionStart ZCode : injecte le journal de veille et les majs en attente dans la session.

Appelé automatiquement par ZCode à chaque démarrage de session sur ce workspace
(config : .zcode/config.json, événement SessionStart). Fait deux choses, sans
jamais bloquer la session (sortie vide et code 0 si rien à signaler) :
1. si la dernière veille date de plus de VEILLE_MAX_HEURES, relance
   scripts/veille_versions.py en arrière-plan (process détaché, sortie dans
   output/veille/veille_arriere_plan.log) — les nouveautés seront visibles
   dans la session suivante ; sinon aucun accès réseau ;
2. injecte dans le contexte les mises à jour en attente (output/veille/
   maj_en_attente.json, maintenu par le script de veille — voir AGENTS.md)
   et les entrées des 7 derniers jours de docs/veille_journal.md.

Test manuel : uv run python scripts/hook_session_start.py
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

# Fenêtre de remontée et limites de taille pour ne pas gonfler le contexte
JOURNAI_MAX_JOURS = 7
ENTREE_MAX_CHARS = 400
TOTAL_MAX_CHARS = 4000
MAJ_MAX_ITEMS = 10
MAJ_ITEM_MAX_CHARS = 300
MAJ_MAX_CHARS = 1500
VEILLE_MAX_HEURES = 20  # au-delà, le hook relance la veille en arrière-plan

# En-tête du journal : entrées sous forme « - **AAAA-MM-JJ • source • ... »
RE_ENTREE = re.compile(r"^- \*\*(\d{4}-\d{2}-\d{2})")


def projet_dir() -> Path:
    """Répertoire du projet : variable ZCODE_PROJECT_DIR fournie par le hook, sinon emplacement du script."""
    env_dir = os.environ.get("ZCODE_PROJECT_DIR") or os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(env_dir) if env_dir else Path(__file__).resolve().parent.parent


def relancer_veille_si_necessaire(projet: Path) -> bool:
    """Relance la veille en arrière-plan si la dernière date de plus de VEILLE_MAX_HEURES.

    Le frais de la dernière veille se lit sur la date de output/veille/rapports.log
    (appendu à chaque run, même sans nouveauté). Le process est détaché : la
    session démarre instantanément, la veille complète en tâche de fond.
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
    """Bloc « mises à jour en attente » lu depuis output/veille/maj_en_attente.json (aucun accès réseau)."""
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
            base = f"installée {item.get('installee', '?')} → disponible {item.get('disponible', '?')}"
            if item.get("action"):
                base += f" ; action : {item['action']}"
        else:
            base = json.dumps(item, ensure_ascii=False)
        if item.get("notes") and item["notes"] not in base:
            base += f" ; notes : {item['notes']}"
        lignes.append(f"- {item.get('source', '?')} : {base}"[:MAJ_ITEM_MAX_CHARS])
    texte = (
        f"⚠️ MISES À JOUR EN ATTENTE (dernière détection {donnees.get('detecte_le', '?')}) — "
        "CONSIGNE : mentionne-les à l'utilisateur dès ta première réponse (ex. « au passage, "
        "tu as des majs en attente : … »), même si sa question porte sur autre chose, et "
        "propose de les appliquer selon le process « 🔄 Process de mise à jour » d'AGENTS.md "
        "(une composante à la fois, JAMAIS sans son accord explicite) :\n" + "\n".join(lignes)
    )
    return texte[:MAJ_MAX_CHARS]


def extraire_entrees(journal: Path, limite: date) -> list[str]:
    """Retourne les entrées du journal postérieures à la limite, tronquées à ENTREE_MAX_CHARS."""
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
    """Bloc « journal de veille » : entrées des JOURNAI_MAX_JOURS derniers jours."""
    journal = projet / "docs" / "veille_journal.md"
    if not journal.is_file():
        return None
    limite = date.today() - timedelta(days=JOURNAI_MAX_JOURS)
    entrees = extraire_entrees(journal, limite)
    if not entrees:
        return None
    return (
        f"Journal de veille de la stack ({JOURNAI_MAX_JOURS} derniers jours) — "
        f"détail complet dans docs/veille_journal.md :\n" + "\n".join(entrees)
    )


def main() -> int:
    projet = projet_dir()
    relancee = relancer_veille_si_necessaire(projet)
    parties = [b for b in (bloc_maj_en_attente(projet), bloc_journal(projet)) if b]
    if relancee:
        parties.insert(0, "🔁 Veille relancée en arrière-plan (dernière vérification > 20 h) — "
                          "les nouveautés détectées seront visibles dans la prochaine session.")
    if not parties:
        return 0
    contexte = "\n\n".join(parties)
    if len(contexte) > TOTAL_MAX_CHARS:
        contexte = contexte[:TOTAL_MAX_CHARS].rstrip() + "\n[… voir docs/veille_journal.md]"

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
