"""Hook SessionStart ZCode : injecte le journal de veille et les majs en attente dans la session.

Appelé automatiquement par ZCode à chaque démarrage de session sur ce workspace
(config : .zcode/config.json, événement SessionStart). Fait trois choses, sans
jamais bloquer la session (sortie vide et code 0 si rien à signaler) :
1. si la dernière veille date de plus de VEILLE_MAX_HEURES, relance
   scripts/veille_versions.py en arrière-plan (process détaché, sortie dans
   output/veille/veille_arriere_plan.log) — les nouveautés seront visibles
   dans la session suivante ;
2. injecte dans le contexte les mises à jour en attente (output/veille/
   maj_en_attente.json, maintenu par le script de veille — voir AGENTS.md)
   et les entrées des 7 derniers jours de docs/veille_journal.md ;
3. vérifie l'issue GitHub sd-cli #1946 (régression master-848, rollback du
   2026-09-07) : un unique appel API GitHub léger, et une alerte uniquement
   si l'issue a bougé (nouvelle réponse, changement d'état = correction
   potentielle à retenter). État connu : output/veille/issue_sdcli_1946.json.

Test manuel : uv run python scripts/hook_session_start.py
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

# Fenêtre de remontée et limites de taille pour ne pas gonfler le contexte
JOURNAI_MAX_JOURS = 7
ENTREE_MAX_CHARS = 400
TOTAL_MAX_CHARS = 4000
MAJ_MAX_ITEMS = 10
MAJ_ITEM_MAX_CHARS = 300
MAJ_MAX_CHARS = 1500
VEILLE_MAX_HEURES = 20  # au-delà, le hook relance la veille en arrière-plan

# Issue sd-cli à surveiller (régression master-848-9cdb6b6 : crash silencieux
# Flux + encodeurs séparés sur Vulkan/AMD ; contexte dans docs/veille_journal.md
# du 2026-09-07 et C:\SD\README.md). Ne plus surveiller qu'après installation
# d'une release corrigée (supprimer alors bloc + état + cette entrée AGENTS.md).
ISSUE_SDCLI_REPO = "leejet/stable-diffusion.cpp"
ISSUE_SDCLI_NUMERO = 1946
ISSUE_API_TIMEOUT = 5  # secondes ; le hook ne doit jamais bloquer la session
ISSUE_BLOC_MAX_CHARS = 900
COMMENTAIRE_MAX_CHARS = 280

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


def api_github(chemin: str) -> dict | list | None:
    """Appel GET non authentifié à l'API GitHub (dépôt public), None si indisponible."""
    url = f"https://api.github.com/{chemin}"
    try:
        requete = urllib.request.Request(
            url, headers={"Accept": "application/vnd.github+json",
                          "User-Agent": "generator-assets-veille"})
        with urllib.request.urlopen(requete, timeout=ISSUE_API_TIMEOUT) as reponse:
            return json.loads(reponse.read().decode("utf-8"))
    except (OSError, ValueError):
        return None


def bloc_issue_sdcli(projet: Path) -> str | None:
    """Surveille l'issue sd-cli #1946 (régression master-848) : alerte si elle a bougé.

    Un seul appel API (léger, timeout court, échec silencieux) par session ;
    l'état déjà vu est conservé dans output/veille/issue_sdcli_1946.json.
    Premier appel = initialisation silencieuse (l'état initial est connu).
    """
    etat_fichier = projet / "output" / "veille" / "issue_sdcli_1946.json"
    issue = api_github(f"repos/{ISSUE_SDCLI_REPO}/issues/{ISSUE_SDCLI_NUMERO}")
    if not isinstance(issue, dict) or "updated_at" not in issue:
        return None
    etat = {
        "derniere_activite_vue": issue["updated_at"],
        "commentaires_vue": int(issue.get("comments", 0)),
        "etat_issue": issue.get("state", "open"),
        "verifie_le": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    try:
        precedent = json.loads(etat_fichier.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        precedent = None
    try:
        etat_fichier.parent.mkdir(parents=True, exist_ok=True)
        etat_fichier.write_text(json.dumps(etat, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass
    if precedent is None:
        return None
    if (precedent.get("derniere_activite_vue") == etat["derniere_activite_vue"]
            and precedent.get("etat_issue") == etat["etat_issue"]):
        return None

    nouveautes = []
    if precedent.get("commentaires_vue") != etat["commentaires_vue"]:
        commentaires = api_github(
            f"repos/{ISSUE_SDCLI_REPO}/issues/{ISSUE_SDCLI_NUMERO}/comments?per_page=5")
        if isinstance(commentaires, list) and commentaires:
            extraits = []
            for commentaire in commentaires[-3:]:
                corps = " ".join((commentaire.get("body") or "").split())
                suite = "…" if len(corps) > COMMENTAIRE_MAX_CHARS else ""
                auteur = (commentaire.get("user") or {}).get("login", "?")
                extraits.append(f"« {corps[:COMMENTAIRE_MAX_CHARS]}{suite} » ({auteur})")
            nouveautes.append(f"{etat['commentaires_vue']} commentaire(s) — derniers : "
                              + " ; ".join(extraits))
    if etat["etat_issue"] == "closed" and precedent.get("etat_issue") != "closed":
        nouveautes.append("issue FERMÉE = correction probable → une release sd-cli postérieure "
                          "à master-848 devrait arriver dans la veille ; retenter la mise à jour "
                          "(smoke test Flux obligatoire, cf. C:\\SD\\README.md)")
    texte = (
        f"🚨 ISSUE SD-CLI #{ISSUE_SDCLI_NUMERO} (régression master-848, rollback du 2026-09-07) — "
        f"du mouvement depuis la dernière session ({' ; '.join(nouveautes) or 'activité mise à jour'}). "
        f"CONSIGNE : consulte l'issue https://github.com/{ISSUE_SDCLI_REPO}/issues/{ISSUE_SDCLI_NUMERO} "
        "(gh api ou WebFetch), résume les réponses à l'utilisateur ; si une release sd-cli postérieure "
        "à master-848 corrige le bug, propose la mise à jour selon le process AGENTS.md "
        "(JAMAIS sans son accord explicite)."
    )
    return texte[:ISSUE_BLOC_MAX_CHARS]


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
    parties = [b for b in (bloc_maj_en_attente(projet), bloc_issue_sdcli(projet),
                            bloc_journal(projet)) if b]
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
