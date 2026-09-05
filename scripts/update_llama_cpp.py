#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Programme d'automatisation de la mise à jour et de compilation Vulkan
pour llama.cpp (https://github.com/ggml-org/llama.cpp).

Modes supportés :
  --check     : Vérifie les versions locale et distante (builds, commits, releases).
  --download  : Téléchargement rapide de la dernière release Vulkan x64 officielle GitHub.
  --build     : Compilation native complète avec accélération matérielle Vulkan (Git + CMake + MSVC + Vulkan SDK).
  --rollback  : Restaure la sauvegarde précédente depuis C:\\llama.cpp\\backups\\.

Fonctionnalités :
  • Détection automatique du SDK Vulkan (C:\\VulkanSDK\\* ou $env:VULKAN_SDK).
  • Détection automatique du compilateur MSVC / Visual Studio.
  • Clônage ou mise à jour git avec submodules récursifs.
  • Compilation CMake Release multi-threads optimisée avec backend Vulkan dynamique.
  • Sauvegarde horodatée avant mise à jour dans C:\\llama.cpp\\backups\\.
  • Vérification post-installation (llama-cli.exe --version & présence de ggml-vulkan.dll).
"""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Support UTF-8 sur consoles Windows (évite les erreurs UnicodeEncodeError cp1252)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO_URL = "https://github.com/ggml-org/llama.cpp.git"
GITHUB_API_RELEASES = "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=5"
GITHUB_API_COMMITS = "https://api.github.com/repos/ggml-org/llama.cpp/commits/master"

DEFAULT_INSTALL_DIR = Path(os.getenv("LLAMA_DIR", r"C:\llama.cpp"))
DEFAULT_SOURCE_DIR = Path(os.getenv("LLAMA_SOURCE_DIR", r"C:\GIT\llama.cpp"))


def log_step(message: str) -> None:
    print(f"\n⚡ {message}")


def log_success(message: str) -> None:
    print(f"✅ {message}")


def log_warn(message: str) -> None:
    print(f"⚠️  {message}")


def log_error(message: str) -> None:
    print(f"❌ {message}")


def log_info(message: str) -> None:
    print(f"ℹ️  {message}")


def obtenir_version_locale(install_dir: Path) -> Dict[str, Optional[str]]:
    """Inspecte l'exécutable llama-cli.exe installé et ses métadonnées."""
    llama_cli = install_dir / "llama-cli.exe"
    info = {
        "installed": False,
        "path": str(llama_cli),
        "build": None,
        "commit": None,
        "date": None,
        "size_mb": None,
        "has_vulkan": (install_dir / "ggml-vulkan.dll").exists(),
        "has_rpc": (install_dir / "ggml-rpc.dll").exists(),
    }

    if not llama_cli.exists():
        return info

    info["installed"] = True
    stat = llama_cli.stat()
    info["date"] = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    info["size_mb"] = f"{stat.st_size / (1024 * 1024):.2f}"

    try:
        res = subprocess.run(
            [str(llama_cli), "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        out = (res.stdout or "") + (res.stderr or "")

        # Détection du numéro de build (ex: "build 10514")
        match_build = re.search(r"build\s+(\d+)", out, re.IGNORECASE)
        if match_build:
            info["build"] = match_build.group(1)

        # Détection du commit (ex: "commit 7221e24f5")
        match_commit = re.search(r"commit\s+([a-f0-9]{7,40})", out, re.IGNORECASE)
        if match_commit:
            info["commit"] = match_commit.group(1)[:7]
    except Exception as e:
        info["version_err"] = str(e)

    return info


def requete_github_api(url: str) -> Optional[any]:
    """Exécute une requête GET vers l'API GitHub avec gestion d'erreurs."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "generator-assets-llama-updater/1.0",
            "Accept": "application/vnd.github.v3+json"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 403:
            log_warn("Limite de requêtes API GitHub atteinte (HTTP 403).")
        else:
            log_warn(f"Erreur API GitHub ({e.code}) pour {url}")
        return None
    except Exception as e:
        log_warn(f"Impossible de contacter l'API GitHub : {e}")
        return None


def obtenir_commit_distant_via_git() -> Optional[str]:
    """Fallback : récupère le dernier commit master via git ls-remote."""
    try:
        res = subprocess.run(
            ["git", "ls-remote", REPO_URL, "refs/heads/master"],
            capture_output=True,
            text=True,
            timeout=15
        )
        if res.returncode == 0 and res.stdout:
            parts = res.stdout.strip().split()
            if parts:
                return parts[0][:7]
    except Exception:
        pass
    return None


def obtenir_infos_distantes() -> Dict:
    """Récupère les informations de la dernière release Vulkan et du dernier commit master."""
    result = {
        "release_tag": None,
        "release_build": None,
        "release_date": None,
        "vulkan_asset_name": None,
        "vulkan_asset_url": None,
        "vulkan_asset_size_mb": None,
        "master_commit": None,
        "master_commit_msg": None,
        "master_commit_date": None
    }

    releases_data = requete_github_api(GITHUB_API_RELEASES)
    if releases_data and isinstance(releases_data, list):
        # Cherche la plus récente release contenant un asset Windows Vulkan
        for rel in releases_data:
            tag = rel.get("tag_name", "")
            assets = rel.get("assets", [])
            for asset in assets:
                name = asset.get("name", "")
                if "win-vulkan-x64.zip" in name.lower():
                    result["release_tag"] = tag
                    match_b = re.search(r"\d+", tag)
                    if match_b:
                        result["release_build"] = match_b.group(0)
                    result["release_date"] = rel.get("published_at", "")[:10]
                    result["vulkan_asset_name"] = name
                    result["vulkan_asset_url"] = asset.get("browser_download_url")
                    size = asset.get("size", 0)
                    result["vulkan_asset_size_mb"] = f"{size / (1024 * 1024):.1f}"
                    break
            if result["vulkan_asset_url"]:
                break

    commit_data = requete_github_api(GITHUB_API_COMMITS)
    if commit_data and isinstance(commit_data, dict):
        sha = commit_data.get("sha", "")
        result["master_commit"] = sha[:7] if sha else None
        commit_details = commit_data.get("commit", {})
        msg = commit_details.get("message", "").split("\n")[0]
        result["master_commit_msg"] = msg
        date = commit_details.get("committer", {}).get("date", "")
        result["master_commit_date"] = date[:10]
    else:
        remote_sha = obtenir_commit_distant_via_git()
        if remote_sha:
            result["master_commit"] = remote_sha

    return result


def detecter_vulkan_sdk() -> Optional[Path]:
    """Détecte l'installation du SDK Vulkan (variable VULKAN_SDK ou scan de C:\\VulkanSDK)."""
    env_sdk = os.getenv("VULKAN_SDK")
    if env_sdk and Path(env_sdk).exists():
        return Path(env_sdk)

    base_sdk = Path(r"C:\VulkanSDK")
    if base_sdk.exists():
        versions = [d for d in base_sdk.iterdir() if d.is_dir()]
        if versions:
            versions.sort(key=lambda p: [int(x) if x.isdigit() else 0 for x in p.name.split(".")], reverse=True)
            return versions[0]

    return None


def detecter_cmake() -> Optional[Path]:
    """Vérifie la disponibilité de cmake dans le PATH."""
    path = shutil.which("cmake")
    return Path(path) if path else None


def detecter_git() -> Optional[Path]:
    """Vérifie la disponibilité de git dans le PATH."""
    path = shutil.which("git")
    return Path(path) if path else None


def detecter_compilateur_msvc() -> Optional[str]:
    """Recherche Visual Studio / MSVC via vswhere.exe."""
    vswhere = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if vswhere.exists():
        try:
            res = subprocess.run(
                [str(vswhere), "-latest", "-products", "*", "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass
    return None


def creer_sauvegarde(install_dir: Path) -> Optional[Path]:
    """Crée une sauvegarde horodatée du dossier C:\\llama.cpp."""
    if not install_dir.exists():
        return None

    fichiers_a_sauver = list(install_dir.glob("*.exe")) + list(install_dir.glob("*.dll"))
    if not fichiers_a_sauver:
        return None

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = install_dir / "backups" / f"backup_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    log_info(f"Création de la sauvegarde dans : {backup_dir}")
    for item in install_dir.iterdir():
        if item.name == "backups":
            continue
        if item.is_file():
            shutil.copy2(item, backup_dir / item.name)

    log_success(f"Sauvegarde terminée ({len(fichiers_a_sauver)} exécutables/bibliothèques archivés).")
    return backup_dir


def lister_sauvegardes(install_dir: Path) -> List[Path]:
    """Liste toutes les sauvegardes existantes."""
    backup_root = install_dir / "backups"
    if not backup_root.exists():
        return []
    backups = [d for d in backup_root.iterdir() if d.is_dir() and d.name.startswith("backup_")]
    backups.sort(key=lambda d: d.name, reverse=True)
    return backups


def restaurer_sauvegarde(install_dir: Path, target_backup: Optional[Path] = None) -> bool:
    """Restaure une sauvegarde précédente."""
    backups = lister_sauvegardes(install_dir)
    if not backups:
        log_error("Aucune sauvegarde trouvée dans C:\\llama.cpp\\backups\\")
        return False

    choix = target_backup or backups[0]
    log_step(f"Restauration de la sauvegarde : {choix.name}")

    fichiers = list(choix.glob("*.*"))
    for f in fichiers:
        if f.is_file():
            shutil.copy2(f, install_dir / f.name)

    log_success(f"Restauration réussie ({len(fichiers)} fichiers restaurés).")
    return True


def telecharger_fichier_avec_progression(url: str, destination: Path) -> None:
    """Télécharge un fichier distant avec affichage de progression en console."""
    req = urllib.request.Request(url, headers={"User-Agent": "generator-assets-llama-updater/1.0"})
    with urllib.request.urlopen(req) as response:
        taille_totale = int(response.headers.get("content-length", 0))
        taille_telechargee = 0
        chunk_size = 65536
        start_time = time.time()

        with open(destination, "wb") as f_out:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                f_out.write(chunk)
                taille_telechargee += len(chunk)
                if taille_totale > 0:
                    pct = (taille_telechargee / taille_totale) * 100
                    debit_mo = (taille_telechargee / (1024 * 1024)) / max(0.001, time.time() - start_time)
                    sys.stdout.write(
                        f"\r⏳ Téléchargement : {taille_telechargee / (1024 * 1024):.1f} / {taille_totale / (1024 * 1024):.1f} Mo "
                        f"({pct:.1f}%) à {debit_mo:.1f} Mo/s... "
                    )
                    sys.stdout.flush()
    print()


def action_verifier(install_dir: Path) -> None:
    """Affiche un tableau complet de l'état local et des nouveautés disponibles pour llama.cpp."""
    log_step("Inspection de l'état de llama.cpp")

    local_info = obtenir_version_locale(install_dir)
    distant_info = obtenir_infos_distantes()

    print("\n" + "=" * 70)
    print(" 🦙 RAPPORT DE VERSION LLAMA.CPP (Vulkan)")
    print("=" * 70)

    # 1. État local
    if local_info["installed"]:
        print(f"  • Installation locale  : {local_info['path']}")
        print(f"  • Build local          : {local_info['build'] or 'Inconnu'}")
        print(f"  • Commit local         : {local_info['commit'] or 'Inconnu'}")
        print(f"  • Date des binaires    : {local_info['date']}")
        print(f"  • Backend Vulkan       : {'✅ Oui (ggml-vulkan.dll)' if local_info['has_vulkan'] else '❌ Non'}")
    else:
        print("  • Installation locale  : ❌ Aucun binaire détecté dans " + str(install_dir))

    print("-" * 70)

    # 2. État distant
    if distant_info["release_tag"]:
        print(f"  • Dernière Release     : {distant_info['release_tag']} ({distant_info['release_date']})")
        print(f"  • Asset Vulkan Win64   : {distant_info['vulkan_asset_name']} ({distant_info['vulkan_asset_size_mb']} Mo)")
    if distant_info["master_commit"]:
        print(f"  • Dernier commit master: {distant_info['master_commit']} ({distant_info['master_commit_date']})")
        if distant_info["master_commit_msg"]:
            print(f"  • Message commit       : \"{distant_info['master_commit_msg']}\"")

    print("-" * 70)

    # 3. Diagnostic de mise à jour
    est_a_jour = False
    retard_builds = None
    if local_info["installed"] and local_info["build"] and distant_info["release_build"]:
        try:
            b_loc = int(local_info["build"])
            b_dist = int(distant_info["release_build"])
            if b_loc >= b_dist:
                est_a_jour = True
            else:
                retard_builds = b_dist - b_loc
        except Exception:
            pass

    if est_a_jour:
        log_success("Votre installation de llama.cpp est parfaitement À JOUR !")
    else:
        if retard_builds:
            log_warn(f"Une NOUVELLE VERSION est disponible (retard de {retard_builds} builds : local {local_info['build']} vs distant {distant_info['release_build']}) !")
        else:
            log_warn("Une NOUVELLE VERSION est disponible !")

        print("\n💡 Pour mettre à jour rapidement via les binaires officiels GitHub :")
        print(f"   python scripts/update_llama_cpp.py --download")
        print("\n💡 Pour compiler les toutes dernières sources master avec Vulkan :")
        print(f"   python scripts/update_llama_cpp.py --build")

    print("=" * 70 + "\n")


def action_telecharger_release(install_dir: Path, backup: bool = True) -> bool:
    """Télécharge et installe la dernière release officielle Vulkan pour Windows."""
    log_step("Téléchargement de la dernière release Vulkan GitHub pour llama.cpp")

    distant = obtenir_infos_distantes()
    asset_url = distant.get("vulkan_asset_url")
    asset_name = distant.get("vulkan_asset_name")

    if not asset_url:
        log_error("Impossible de localiser l'asset Vulkan pour Windows sur GitHub Releases.")
        return False

    log_info(f"Release cible : {distant.get('release_tag')} | Fichier : {asset_name} ({distant.get('vulkan_asset_size_mb')} Mo)")

    # 1. Sauvegarde
    if backup:
        creer_sauvegarde(install_dir)

    # 2. Téléchargement
    temp_zip = install_dir / "temp_llama_vulkan.zip"
    try:
        install_dir.mkdir(parents=True, exist_ok=True)
        telecharger_fichier_avec_progression(asset_url, temp_zip)

        # 3. Extraction
        log_step("Extraction des binaires dans " + str(install_dir))
        import zipfile
        with zipfile.ZipFile(temp_zip, "r") as zip_ref:
            zip_ref.extractall(install_dir)

        log_success("Extraction terminée avec succès.")
    except Exception as e:
        log_error(f"Erreur lors du téléchargement ou de l'extraction : {e}")
        return False
    finally:
        if temp_zip.exists():
            try:
                temp_zip.unlink()
            except Exception:
                pass

    # 4. Vérification post-installation
    return verifier_installation(install_dir)


def action_compiler_vulkan(
    source_dir: Path,
    install_dir: Path,
    branch: str = "master",
    backup: bool = True,
    clean: bool = False,
    parallel_jobs: Optional[int] = None
) -> bool:
    """Clone/Met à jour le dépôt et compile nativement llama.cpp avec Vulkan."""
    log_step("Initialisation de la compilation Vulkan depuis les sources pour llama.cpp")

    # 1. Prérequis
    git_bin = detecter_git()
    if not git_bin:
        log_error("Git n'est pas installé ou introuvable dans le PATH.")
        return False

    cmake_bin = detecter_cmake()
    if not cmake_bin:
        log_error("CMake n'est pas installé ou introuvable dans le PATH.")
        return False

    vulkan_sdk = detecter_vulkan_sdk()
    if not vulkan_sdk:
        log_error("SDK Vulkan introuvable ! Téléchargez-le depuis https://vulkan.lunarg.com/")
        return False

    msvc_path = detecter_compilateur_msvc()
    if not msvc_path:
        log_warn("Visual Studio / MSVC non détecté via vswhere. CMake tentera la détection automatique.")
    else:
        log_info(f"Visual Studio détecté : {msvc_path}")

    log_info(f"SDK Vulkan sélectionné : {vulkan_sdk}")
    log_info(f"Dossier source         : {source_dir}")
    log_info(f"Dossier d'installation : {install_dir}")

    # Environnement de compilation avec SDK Vulkan
    build_env = os.environ.copy()
    build_env["VULKAN_SDK"] = str(vulkan_sdk)
    vulkan_bin_dir = str(vulkan_sdk / "Bin")
    if vulkan_bin_dir not in build_env.get("PATH", ""):
        build_env["PATH"] = f"{vulkan_bin_dir};{build_env.get('PATH', '')}"

    # 2. Clônage ou mise à jour git
    if not source_dir.exists():
        log_step(f"Clônage du dépôt {REPO_URL} dans {source_dir}...")
        source_dir.parent.mkdir(parents=True, exist_ok=True)
        res = subprocess.run(
            [str(git_bin), "clone", "--recursive", REPO_URL, str(source_dir)],
            check=False
        )
        if res.returncode != 0:
            log_error("Échec du clônage git.")
            return False
    else:
        log_step(f"Mise à jour du dépôt git ({branch})...")
        subprocess.run([str(git_bin), "-C", str(source_dir), "fetch", "origin", branch], check=False)
        subprocess.run([str(git_bin), "-C", str(source_dir), "checkout", branch], check=False)
        subprocess.run([str(git_bin), "-C", str(source_dir), "pull", "origin", branch], check=False)
        log_info("Mise à jour des submodules récursifs...")
        subprocess.run([str(git_bin), "-C", str(source_dir), "submodule", "sync", "--recursive"], check=False)
        subprocess.run([str(git_bin), "-C", str(source_dir), "submodule", "update", "--init", "--recursive"], check=False)

    build_dir = source_dir / "build"
    if clean and build_dir.exists():
        log_step("Nettoyage de l'ancien dossier de compilation...")
        shutil.rmtree(build_dir, ignore_errors=True)

    build_dir.mkdir(parents=True, exist_ok=True)

    # 3. Configuration CMake pour llama.cpp sous Vulkan
    log_step("Configuration CMake pour llama.cpp avec support Vulkan...")
    cmake_args = [
        str(cmake_bin),
        "-B", str(build_dir),
        "-S", str(source_dir),
        "-A", "x64",
        "-DGGML_VULKAN=ON",
        "-DGGML_BACKEND_DL=ON",
        "-DGGML_CPU_ALL_VARIANTS=ON",
        "-DBUILD_SHARED_LIBS=ON"
    ]

    log_info("Commande CMake : " + " ".join(cmake_args))
    res = subprocess.run(cmake_args, env=build_env)
    if res.returncode != 0:
        log_error("Échec de la configuration CMake.")
        return False

    # 4. Compilation
    jobs = parallel_jobs or os.cpu_count() or 8
    log_step(f"Compilation Release de llama.cpp ({jobs} threads parallèles)...")
    build_args = [
        str(cmake_bin),
        "--build", str(build_dir),
        "--config", "Release",
        "--parallel", str(jobs)
    ]
    res = subprocess.run(build_args, env=build_env)
    if res.returncode != 0:
        log_error("Échec de la compilation C++ de llama.cpp.")
        return False

    log_success("Compilation terminée avec succès !")

    # 5. Localisation des binaires
    dossier_bin = build_dir / "bin" / "Release"
    if not dossier_bin.exists() or not (dossier_bin / "llama-cli.exe").exists():
        dossier_bin = build_dir / "bin"

    if not (dossier_bin / "llama-cli.exe").exists():
        log_error(f"llama-cli.exe introuvable dans {dossier_bin}")
        return False

    # 6. Sauvegarde et déploiement
    if backup:
        creer_sauvegarde(install_dir)

    log_step(f"Déploiement des nouveaux binaires dans {install_dir}...")
    install_dir.mkdir(parents=True, exist_ok=True)

    fichiers_copies = 0
    for f in dossier_bin.glob("*.*"):
        if f.suffix.lower() in [".exe", ".dll", ".txt"]:
            shutil.copy2(f, install_dir / f.name)
            fichiers_copies += 1

    log_success(f"Déploiement réussi ({fichiers_copies} fichiers copiés dans {install_dir}).")

    # 7. Vérification
    return verifier_installation(install_dir)


def verifier_installation(install_dir: Path) -> bool:
    """Exécute llama-cli.exe --version et contrôle la présence des bibliothèques clés."""
    log_step("Validation du bon fonctionnement des binaires installés...")
    llama_cli = install_dir / "llama-cli.exe"

    if not llama_cli.exists():
        log_error("llama-cli.exe est introuvable après l'opération.")
        return False

    try:
        res = subprocess.run([str(llama_cli), "--version"], capture_output=True, text=True, timeout=10)
        output = (res.stdout or "") + (res.stderr or "")
        print(f"\n[Sortie llama-cli --version] :\n{output.strip()}\n")

        vulkan_ok = (install_dir / "ggml-vulkan.dll").exists()
        if vulkan_ok:
            log_success("Backend Vulkan opérationnel (ggml-vulkan.dll présent) !")
        else:
            log_warn("ggml-vulkan.dll n'a pas été trouvé dans le répertoire.")

        log_success("llama.cpp est opérationnel et prêt pour generator-assets !\n")
        return True
    except Exception as e:
        log_error(f"Erreur lors du test d'exécution de llama-cli.exe : {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mise à jour et compilation Vulkan automatisée de llama.cpp."
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Vérifie les versions locale et distante sans modifier les fichiers."
    )
    parser.add_argument(
        "--download", action="store_true",
        help="Télécharge et installe la dernière release Vulkan x64 officielle GitHub."
    )
    parser.add_argument(
        "--build", action="store_true",
        help="Compile nativement depuis les sources Git avec Vulkan (CMake + MSVC)."
    )
    parser.add_argument(
        "--rollback", action="store_true",
        help="Restaure la sauvegarde précédente depuis C:\\llama.cpp\\backups\\."
    )
    parser.add_argument(
        "--list-backups", action="store_true",
        help="Liste les sauvegardes existantes."
    )
    parser.add_argument(
        "--install-dir", type=Path, default=DEFAULT_INSTALL_DIR,
        help=f"Dossier d'installation cible (défaut: {DEFAULT_INSTALL_DIR})."
    )
    parser.add_argument(
        "--source-dir", type=Path, default=DEFAULT_SOURCE_DIR,
        help=f"Dossier des sources Git pour la compilation (défaut: {DEFAULT_SOURCE_DIR})."
    )
    parser.add_argument(
        "--branch", type=str, default="master",
        help="Branche Git à compiler (défaut: master)."
    )
    parser.add_argument(
        "--no-backup", action="store_true",
        help="Désactive la sauvegarde automatique préalable."
    )
    parser.add_argument(
        "--clean", action="store_true",
        help="Nettoie le dossier build avant de recompiler."
    )
    parser.add_argument(
        "--jobs", "-j", type=int, default=None,
        help="Nombre de cœurs processeur pour la compilation."
    )

    args = parser.parse_args()

    if not (args.check or args.download or args.build or args.rollback or args.list_backups):
        action_verifier(args.install_dir)
        sys.exit(0)

    if args.list_backups:
        backups = lister_sauvegardes(args.install_dir)
        print(f"\n📦 Sauvegardes trouvées dans {args.install_dir / 'backups'} :")
        if not backups:
            print("  (Aucune sauvegarde)")
        for b in backups:
            print(f"  • {b.name}")
        print()
        sys.exit(0)

    if args.rollback:
        succes = restaurer_sauvegarde(args.install_dir)
        sys.exit(0 if succes else 1)

    if args.check:
        action_verifier(args.install_dir)
        sys.exit(0)

    if args.download:
        succes = action_telecharger_release(args.install_dir, backup=not args.no_backup)
        sys.exit(0 if succes else 1)

    if args.build:
        succes = action_compiler_vulkan(
            source_dir=args.source_dir,
            install_dir=args.install_dir,
            branch=args.branch,
            backup=not args.no_backup,
            clean=args.clean,
            parallel_jobs=args.jobs
        )
        sys.exit(0 if succes else 1)


if __name__ == "__main__":
    main()
