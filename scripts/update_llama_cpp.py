#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automation tool for the update and Vulkan build
of llama.cpp (https://github.com/ggml-org/llama.cpp).

Supported modes:
  --check     : Checks the local and remote versions (builds, commits, releases).
  --download  : Quick download of the latest official GitHub Vulkan x64 release.
  --build     : Full native build with Vulkan hardware acceleration (Git + CMake + MSVC + Vulkan SDK).
  --rollback  : Restores the previous backup from C:\\llama.cpp\\backups\\.

Features:
  • Automatic detection of the Vulkan SDK (C:\\VulkanSDK\\* or $env:VULKAN_SDK).
  • Automatic detection of the MSVC / Visual Studio compiler.
  • Git clone or update with recursive submodules.
  • Optimized multi-threaded CMake Release build with a dynamic Vulkan backend.
  • Timestamped backup before update into C:\\llama.cpp\\backups\\.
  • Post-installation check (llama-cli.exe --version & presence of ggml-vulkan.dll).
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
from typing import Dict, List, Optional

# UTF-8 support on Windows consoles (avoids cp1252 UnicodeEncodeError)
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
    """Inspects the installed llama-cli.exe executable and its metadata."""
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

        # Detection of the build number (e.g. "build 10514")
        match_build = re.search(r"build\s+(\d+)", out, re.IGNORECASE)
        if match_build:
            info["build"] = match_build.group(1)

        # Detection of the commit (e.g. "commit 7221e24f5")
        match_commit = re.search(r"commit\s+([a-f0-9]{7,40})", out, re.IGNORECASE)
        if match_commit:
            info["commit"] = match_commit.group(1)[:7]
    except Exception as e:
        info["version_err"] = str(e)

    return info


def requete_github_api(url: str) -> Optional[any]:
    """Performs a GET request against the GitHub API with error handling."""
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
            log_warn("GitHub API rate limit reached (HTTP 403).")
        else:
            log_warn(f"GitHub API error ({e.code}) for {url}")
        return None
    except Exception as e:
        log_warn(f"Unable to reach the GitHub API: {e}")
        return None


def obtenir_commit_distant_via_git() -> Optional[str]:
    """Fallback: fetches the latest master commit via git ls-remote."""
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
    """Fetches the latest Vulkan release and latest master commit information."""
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
        # Look for the most recent release containing a Windows Vulkan asset
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
    """Detects the Vulkan SDK installation (VULKAN_SDK variable or scan of C:\\VulkanSDK)."""
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
    """Checks the availability of cmake in the PATH."""
    path = shutil.which("cmake")
    return Path(path) if path else None


def detecter_git() -> Optional[Path]:
    """Checks the availability of git in the PATH."""
    path = shutil.which("git")
    return Path(path) if path else None


def detecter_compilateur_msvc() -> Optional[str]:
    """Looks for Visual Studio / MSVC via vswhere.exe."""
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
    """Creates a timestamped backup of the C:\\llama.cpp folder."""
    if not install_dir.exists():
        return None

    fichiers_a_sauver = list(install_dir.glob("*.exe")) + list(install_dir.glob("*.dll"))
    if not fichiers_a_sauver:
        return None

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = install_dir / "backups" / f"backup_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    log_info(f"Creating the backup in: {backup_dir}")
    for item in install_dir.iterdir():
        if item.name == "backups":
            continue
        if item.is_file():
            shutil.copy2(item, backup_dir / item.name)

    log_success(f"Backup done ({len(fichiers_a_sauver)} executables/libraries archived).")
    return backup_dir


def lister_sauvegardes(install_dir: Path) -> List[Path]:
    """Lists all the existing backups."""
    backup_root = install_dir / "backups"
    if not backup_root.exists():
        return []
    backups = [d for d in backup_root.iterdir() if d.is_dir() and d.name.startswith("backup_")]
    backups.sort(key=lambda d: d.name, reverse=True)
    return backups


def restaurer_sauvegarde(install_dir: Path, target_backup: Optional[Path] = None) -> bool:
    """Restores a previous backup."""
    backups = lister_sauvegardes(install_dir)
    if not backups:
        log_error("No backup found in C:\\llama.cpp\\backups\\")
        return False

    choix = target_backup or backups[0]
    log_step(f"Restoring the backup: {choix.name}")

    fichiers = list(choix.glob("*.*"))
    for f in fichiers:
        if f.is_file():
            shutil.copy2(f, install_dir / f.name)

    log_success(f"Restoration successful ({len(fichiers)} files restored).")
    return True


def telecharger_fichier_avec_progression(url: str, destination: Path) -> None:
    """Downloads a remote file with a console progress display."""
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
                        f"\r⏳ Download: {taille_telechargee / (1024 * 1024):.1f} / {taille_totale / (1024 * 1024):.1f} MB "
                        f"({pct:.1f}%) at {debit_mo:.1f} MB/s... "
                    )
                    sys.stdout.flush()
    print()


def action_verifier(install_dir: Path) -> None:
    """Displays a complete table of the local state and the available updates for llama.cpp."""
    log_step("Inspecting the state of llama.cpp")

    local_info = obtenir_version_locale(install_dir)
    distant_info = obtenir_infos_distantes()

    print("\n" + "=" * 70)
    print(" 🦙 LLAMA.CPP VERSION REPORT (Vulkan)")
    print("=" * 70)

    # 1. Local state
    if local_info["installed"]:
        print(f"  • Local installation  : {local_info['path']}")
        print(f"  • Local build         : {local_info['build'] or 'Unknown'}")
        print(f"  • Local commit        : {local_info['commit'] or 'Unknown'}")
        print(f"  • Binary date         : {local_info['date']}")
        print(f"  • Vulkan backend      : {'✅ Yes (ggml-vulkan.dll)' if local_info['has_vulkan'] else '❌ No'}")
    else:
        print("  • Local installation  : ❌ No binary detected in " + str(install_dir))

    print("-" * 70)

    # 2. Remote state
    if distant_info["release_tag"]:
        print(f"  • Latest release      : {distant_info['release_tag']} ({distant_info['release_date']})")
        print(f"  • Vulkan Win64 asset  : {distant_info['vulkan_asset_name']} ({distant_info['vulkan_asset_size_mb']} MB)")
    if distant_info["master_commit"]:
        print(f"  • Latest master commit: {distant_info['master_commit']} ({distant_info['master_commit_date']})")
        if distant_info["master_commit_msg"]:
            print(f"  • Commit message      : \"{distant_info['master_commit_msg']}\"")

    print("-" * 70)

    # 3. Update diagnostic
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
        log_success("Your llama.cpp installation is perfectly UP TO DATE!")
    else:
        if retard_builds:
            log_warn(f"A NEW VERSION is available ({retard_builds} builds behind: local {local_info['build']} vs remote {distant_info['release_build']})!")
        else:
            log_warn("A NEW VERSION is available!")

        print("\n💡 To quickly update via the official GitHub binaries:")
        print("   python scripts/update_llama_cpp.py --download")
        print("\n💡 To build the very latest master sources with Vulkan:")
        print("   python scripts/update_llama_cpp.py --build")

    print("=" * 70 + "\n")


def action_telecharger_release(install_dir: Path, backup: bool = True) -> bool:
    """Downloads and installs the latest official Vulkan release for Windows."""
    log_step("Downloading the latest GitHub Vulkan release for llama.cpp")

    distant = obtenir_infos_distantes()
    asset_url = distant.get("vulkan_asset_url")
    asset_name = distant.get("vulkan_asset_name")

    if not asset_url:
        log_error("Unable to locate the Vulkan asset for Windows on GitHub Releases.")
        return False

    log_info(f"Target release: {distant.get('release_tag')} | File: {asset_name} ({distant.get('vulkan_asset_size_mb')} MB)")

    # 1. Backup
    if backup:
        creer_sauvegarde(install_dir)

    # 2. Download
    temp_zip = install_dir / "temp_llama_vulkan.zip"
    try:
        install_dir.mkdir(parents=True, exist_ok=True)
        telecharger_fichier_avec_progression(asset_url, temp_zip)

        # 3. Extraction
        log_step("Extracting the binaries into " + str(install_dir))
        import zipfile
        with zipfile.ZipFile(temp_zip, "r") as zip_ref:
            zip_ref.extractall(install_dir)

        log_success("Extraction completed successfully.")
    except Exception as e:
        log_error(f"Error during download or extraction: {e}")
        return False
    finally:
        if temp_zip.exists():
            try:
                temp_zip.unlink()
            except Exception:
                pass

    # 4. Post-installation check
    return verifier_installation(install_dir)


def action_compiler_vulkan(
    source_dir: Path,
    install_dir: Path,
    branch: str = "master",
    backup: bool = True,
    clean: bool = False,
    parallel_jobs: Optional[int] = None
) -> bool:
    """Clones/Updates the repo and natively builds llama.cpp with Vulkan."""
    log_step("Starting the Vulkan build from sources for llama.cpp")

    # 1. Prerequisites
    git_bin = detecter_git()
    if not git_bin:
        log_error("Git is not installed or not found in the PATH.")
        return False

    cmake_bin = detecter_cmake()
    if not cmake_bin:
        log_error("CMake is not installed or not found in the PATH.")
        return False

    vulkan_sdk = detecter_vulkan_sdk()
    if not vulkan_sdk:
        log_error("Vulkan SDK not found! Download it from https://vulkan.lunarg.com/")
        return False

    msvc_path = detecter_compilateur_msvc()
    if not msvc_path:
        log_warn("Visual Studio / MSVC not detected via vswhere. CMake will attempt automatic detection.")
    else:
        log_info(f"Visual Studio detected: {msvc_path}")

    log_info(f"Selected Vulkan SDK : {vulkan_sdk}")
    log_info(f"Source folder       : {source_dir}")
    log_info(f"Installation folder : {install_dir}")

    # Build environment with the Vulkan SDK
    build_env = os.environ.copy()
    build_env["VULKAN_SDK"] = str(vulkan_sdk)
    vulkan_bin_dir = str(vulkan_sdk / "Bin")
    if vulkan_bin_dir not in build_env.get("PATH", ""):
        build_env["PATH"] = f"{vulkan_bin_dir};{build_env.get('PATH', '')}"

    # 2. Git clone or update
    if not source_dir.exists():
        log_step(f"Cloning the repo {REPO_URL} into {source_dir}...")
        source_dir.parent.mkdir(parents=True, exist_ok=True)
        res = subprocess.run(
            [str(git_bin), "clone", "--recursive", REPO_URL, str(source_dir)],
            check=False
        )
        if res.returncode != 0:
            log_error("Git clone failed.")
            return False
    else:
        log_step(f"Updating the git repo ({branch})...")
        subprocess.run([str(git_bin), "-C", str(source_dir), "fetch", "origin", branch], check=False)
        subprocess.run([str(git_bin), "-C", str(source_dir), "checkout", branch], check=False)
        subprocess.run([str(git_bin), "-C", str(source_dir), "pull", "origin", branch], check=False)
        log_info("Updating the recursive submodules...")
        subprocess.run([str(git_bin), "-C", str(source_dir), "submodule", "sync", "--recursive"], check=False)
        subprocess.run([str(git_bin), "-C", str(source_dir), "submodule", "update", "--init", "--recursive"], check=False)

    build_dir = source_dir / "build"
    if clean and build_dir.exists():
        log_step("Cleaning the old build folder...")
        shutil.rmtree(build_dir, ignore_errors=True)

    build_dir.mkdir(parents=True, exist_ok=True)

    # 3. CMake configuration for llama.cpp under Vulkan
    log_step("CMake configuration for llama.cpp with Vulkan support...")
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

    log_info("CMake command: " + " ".join(cmake_args))
    res = subprocess.run(cmake_args, env=build_env)
    if res.returncode != 0:
        log_error("CMake configuration failed.")
        return False

    # 4. Build
    jobs = parallel_jobs or os.cpu_count() or 8
    log_step(f"llama.cpp Release build ({jobs} parallel threads)...")
    build_args = [
        str(cmake_bin),
        "--build", str(build_dir),
        "--config", "Release",
        "--parallel", str(jobs)
    ]
    res = subprocess.run(build_args, env=build_env)
    if res.returncode != 0:
        log_error("llama.cpp C++ build failed.")
        return False

    log_success("Build completed successfully!")

    # 5. Locating the binaries
    dossier_bin = build_dir / "bin" / "Release"
    if not dossier_bin.exists() or not (dossier_bin / "llama-cli.exe").exists():
        dossier_bin = build_dir / "bin"

    if not (dossier_bin / "llama-cli.exe").exists():
        log_error(f"llama-cli.exe not found in {dossier_bin}")
        return False

    # 6. Backup and deployment
    if backup:
        creer_sauvegarde(install_dir)

    log_step(f"Deploying the new binaries into {install_dir}...")
    install_dir.mkdir(parents=True, exist_ok=True)

    fichiers_copies = 0
    for f in dossier_bin.glob("*.*"):
        if f.suffix.lower() in [".exe", ".dll", ".txt"]:
            shutil.copy2(f, install_dir / f.name)
            fichiers_copies += 1

    log_success(f"Deployment successful ({fichiers_copies} files copied into {install_dir}).")

    # 7. Check
    return verifier_installation(install_dir)


def verifier_installation(install_dir: Path) -> bool:
    """Runs llama-cli.exe --version and checks the presence of the key libraries."""
    log_step("Validating that the installed binaries work...")
    llama_cli = install_dir / "llama-cli.exe"

    if not llama_cli.exists():
        log_error("llama-cli.exe could not be found after the operation.")
        return False

    try:
        res = subprocess.run([str(llama_cli), "--version"], capture_output=True, text=True, timeout=10)
        output = (res.stdout or "") + (res.stderr or "")
        print(f"\n[llama-cli --version output]:\n{output.strip()}\n")

        vulkan_ok = (install_dir / "ggml-vulkan.dll").exists()
        if vulkan_ok:
            log_success("Vulkan backend operational (ggml-vulkan.dll present)!")
        else:
            log_warn("ggml-vulkan.dll was not found in the directory.")

        log_success("llama.cpp is operational and ready for generator-assets!\n")
        return True
    except Exception as e:
        log_error(f"Error while running the llama-cli.exe test: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Automated update and Vulkan build of llama.cpp."
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Checks the local and remote versions without modifying files."
    )
    parser.add_argument(
        "--download", action="store_true",
        help="Downloads and installs the latest official GitHub Vulkan x64 release."
    )
    parser.add_argument(
        "--build", action="store_true",
        help="Builds natively from the Git sources with Vulkan (CMake + MSVC)."
    )
    parser.add_argument(
        "--rollback", action="store_true",
        help="Restores the previous backup from C:\\llama.cpp\\backups\\."
    )
    parser.add_argument(
        "--list-backups", action="store_true",
        help="Lists the existing backups."
    )
    parser.add_argument(
        "--install-dir", type=Path, default=DEFAULT_INSTALL_DIR,
        help=f"Target installation folder (default: {DEFAULT_INSTALL_DIR})."
    )
    parser.add_argument(
        "--source-dir", type=Path, default=DEFAULT_SOURCE_DIR,
        help=f"Git sources folder for the build (default: {DEFAULT_SOURCE_DIR})."
    )
    parser.add_argument(
        "--branch", type=str, default="master",
        help="Git branch to build (default: master)."
    )
    parser.add_argument(
        "--no-backup", action="store_true",
        help="Disables the automatic prior backup."
    )
    parser.add_argument(
        "--clean", action="store_true",
        help="Cleans the build folder before rebuilding."
    )
    parser.add_argument(
        "--jobs", "-j", type=int, default=None,
        help="Number of CPU cores for the build."
    )

    args = parser.parse_args()

    if not (args.check or args.download or args.build or args.rollback or args.list_backups):
        action_verifier(args.install_dir)
        sys.exit(0)

    if args.list_backups:
        backups = lister_sauvegardes(args.install_dir)
        print(f"\n📦 Backups found in {args.install_dir / 'backups'}:")
        if not backups:
            print("  (No backup)")
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
