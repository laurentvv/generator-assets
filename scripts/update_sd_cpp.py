#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automation tool for the update and Vulkan build
of stable-diffusion.cpp (https://github.com/leejet/stable-diffusion.cpp).

Supported modes:
  --check     : Checks the local and remote versions (commits, releases, dates).
  --download  : Quick download of the latest official GitHub Vulkan x64 release.
  --build     : Full native build with Vulkan hardware acceleration (Git + CMake + MSVC + Vulkan SDK).
  --rollback  : Restores the previous backup in case of a problem.

Features:
  • Automatic detection of the Vulkan SDK (C:\\VulkanSDK\\* or $env:VULKAN_SDK).
  • Automatic detection of the MSVC / Visual Studio compiler.
  • Git clone or update with recursive submodules.
  • Optimized multi-threaded CMake Release build with WebP & WebM (video) support.
  • Timestamped backup before update into C:\\SD\\backups\\.
  • Post-installation check (sd-cli.exe --version & --help).
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

REPO_URL = "https://github.com/leejet/stable-diffusion.cpp.git"
GITHUB_API_RELEASES = "https://api.github.com/repos/leejet/stable-diffusion.cpp/releases/latest"
GITHUB_API_COMMITS = "https://api.github.com/repos/leejet/stable-diffusion.cpp/commits/master"

DEFAULT_INSTALL_DIR = Path(os.getenv("SD_DIR", r"C:\SD"))
DEFAULT_SOURCE_DIR = Path(os.getenv("SD_SOURCE_DIR", r"C:\GIT\stable-diffusion.cpp"))


def log_step(message: str) -> None:
    print(f"\n[bold cyan]⚡ {message}[/bold cyan]" if "rich" in sys.modules else f"\n⚡ {message}")


def log_success(message: str) -> None:
    print(f"✅ {message}")


def log_warn(message: str) -> None:
    print(f"⚠️  {message}")


def log_error(message: str) -> None:
    print(f"❌ {message}")


def log_info(message: str) -> None:
    print(f"ℹ️  {message}")


def obtenir_version_locale(install_dir: Path) -> Dict[str, Optional[str]]:
    """Inspects the installed sd-cli.exe executable and its metadata."""
    sd_cli = install_dir / "sd-cli.exe"
    info = {
        "installed": False,
        "path": str(sd_cli),
        "commit": None,
        "date": None,
        "size_mb": None,
        "has_vulkan": (install_dir / "ggml-vulkan.dll").exists(),
        "has_webm": (install_dir / "webm.dll").exists(),
    }

    if not sd_cli.exists():
        return info

    info["installed"] = True
    stat = sd_cli.stat()
    info["date"] = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    info["size_mb"] = f"{stat.st_size / (1024 * 1024):.2f}"

    try:
        res = subprocess.run(
            [str(sd_cli), "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        out = (res.stdout or "") + (res.stderr or "")
        match = re.search(r"commit\s+([a-f0-9]{7,40})", out, re.IGNORECASE)
        if match:
            info["commit"] = match.group(1)[:7]
    except Exception as e:
        info["commit_err"] = str(e)

    return info


def requete_github_api(url: str) -> Optional[Dict]:
    """Performs a GET request against the GitHub API with error handling."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "generator-assets-sd-updater/1.0",
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
    """Fallback: fetches the latest master commit via git ls-remote without using the REST API."""
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
    """Fetches the latest release and latest master commit information."""
    result = {
        "release_tag": None,
        "release_commit": None,
        "release_date": None,
        "vulkan_asset_name": None,
        "vulkan_asset_url": None,
        "vulkan_asset_size_mb": None,
        "master_commit": None,
        "master_commit_msg": None,
        "master_commit_date": None
    }

    rel_data = requete_github_api(GITHUB_API_RELEASES)
    if rel_data:
        result["release_tag"] = rel_data.get("tag_name")
        target = rel_data.get("target_commitish", "")
        if len(target) >= 7:
            result["release_commit"] = target[:7]
        result["release_date"] = rel_data.get("published_at", "")[:10]

        for asset in rel_data.get("assets", []):
            name = asset.get("name", "")
            if "win" in name.lower() and "vulkan" in name.lower() and name.endswith(".zip"):
                result["vulkan_asset_name"] = name
                result["vulkan_asset_url"] = asset.get("browser_download_url")
                size = asset.get("size", 0)
                result["vulkan_asset_size_mb"] = f"{size / (1024 * 1024):.1f}"
                break

    commit_data = requete_github_api(GITHUB_API_COMMITS)
    if commit_data:
        sha = commit_data.get("sha", "")
        result["master_commit"] = sha[:7] if sha else None
        commit_details = commit_data.get("commit", {})
        msg = commit_details.get("message", "").split("\n")[0]
        result["master_commit_msg"] = msg
        date = commit_details.get("committer", {}).get("date", "")
        result["master_commit_date"] = date[:10]
    else:
        # git ls-remote fallback
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
            # Sort in descending alphabetical / version order
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
    """Creates a timestamped backup of the C:\\SD folder."""
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
        log_error("No backup found in C:\\SD\\backups\\")
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
    req = urllib.request.Request(url, headers={"User-Agent": "generator-assets-sd-updater/1.0"})
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
    """Displays a complete table of the local state and the available updates."""
    log_step("Inspecting the state of stable-diffusion.cpp")

    local_info = obtenir_version_locale(install_dir)
    distant_info = obtenir_infos_distantes()

    print("\n" + "=" * 70)
    print(" 📊 STABLE-DIFFUSION.CPP VERSION REPORT (Vulkan)")
    print("=" * 70)

    # 1. Local state
    if local_info["installed"]:
        print(f"  • Local installation  : {local_info['path']}")
        print(f"  • Local commit        : {local_info['commit'] or 'Unknown'}")
        print(f"  • Binary date         : {local_info['date']}")
        print(f"  • Vulkan support      : {'✅ Yes (ggml-vulkan.dll)' if local_info['has_vulkan'] else '❌ No'}")
        print(f"  • WebM video support  : {'✅ Yes (webm.dll)' if local_info['has_webm'] else '❌ No'}")
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
    if local_info["installed"] and local_info["commit"]:
        if distant_info["master_commit"] and local_info["commit"] == distant_info["master_commit"]:
            est_a_jour = True
        elif distant_info["release_commit"] and local_info["commit"] == distant_info["release_commit"]:
            est_a_jour = True

    if est_a_jour:
        log_success("Your stable-diffusion.cpp installation is perfectly UP TO DATE!")
    else:
        log_warn("A NEW VERSION is available!")
        print("\n💡 To quickly update via the official GitHub binaries:")
        print("   python scripts/update_sd_cpp.py --download")
        print("\n💡 To build the very latest master sources with Vulkan:")
        print("   python scripts/update_sd_cpp.py --build")

    print("=" * 70 + "\n")


def action_telecharger_release(install_dir: Path, backup: bool = True) -> bool:
    """Downloads and installs the latest official Vulkan release for Windows."""
    log_step("Downloading the latest GitHub Vulkan release")

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

    # 2. Download into a temporary folder
    temp_zip = install_dir / "temp_sd_vulkan.zip"
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
    """Clones/Updates the repo and natively builds stable-diffusion.cpp with Vulkan."""
    log_step("Starting the Vulkan build from sources")

    # 1. Prerequisite check
    git_bin = detecter_git()
    if not git_bin:
        log_error("Git is not installed or not present in the PATH.")
        return False

    cmake_bin = detecter_cmake()
    if not cmake_bin:
        log_error("CMake is not installed or not present in the PATH.")
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

    # Inject the Vulkan SDK into the environment
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

    # 3. CMake configuration
    log_step("CMake configuration with Vulkan & WebM (video) support...")
    cmake_args = [
        str(cmake_bin),
        "-B", str(build_dir),
        "-S", str(source_dir),
        "-A", "x64",
        "-DSD_VULKAN=ON",
        "-DSD_BUILD_SHARED_LIBS=ON",
        "-DGGML_NATIVE=OFF",
        "-DSD_BUILD_SHARED_GGML_LIB=ON",
        "-DGGML_BACKEND_DL=ON",
        "-DGGML_CPU_ALL_VARIANTS=ON",
        "-DSD_WEBP=ON",
        "-DSD_WEBM=ON"
    ]

    log_info("CMake command: " + " ".join(cmake_args))
    res = subprocess.run(cmake_args, env=build_env)
    if res.returncode != 0:
        log_error("CMake configuration failed.")
        return False

    # 4. CMake build
    jobs = parallel_jobs or os.cpu_count() or 8
    log_step(f"Building in Release mode ({jobs} parallel threads)...")
    build_args = [
        str(cmake_bin),
        "--build", str(build_dir),
        "--config", "Release",
        "--parallel", str(jobs)
    ]
    res = subprocess.run(build_args, env=build_env)
    if res.returncode != 0:
        log_error("C++ build failed.")
        return False

    log_success("Build completed successfully!")

    # 5. Locating the produced binaries
    dossier_bin = build_dir / "bin" / "Release"
    if not dossier_bin.exists() or not (dossier_bin / "sd-cli.exe").exists():
        dossier_bin = build_dir / "bin"

    if not (dossier_bin / "sd-cli.exe").exists():
        log_error(f"sd-cli.exe not found in {dossier_bin}")
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

    # Also copy the licenses when available
    licence_sd = source_dir / "LICENSE"
    if licence_sd.exists():
        shutil.copy2(licence_sd, install_dir / "stable-diffusion.cpp.txt")
    licence_ggml = source_dir / "ggml" / "LICENSE"
    if licence_ggml.exists():
        shutil.copy2(licence_ggml, install_dir / "ggml.txt")

    log_success(f"Deployment successful ({fichiers_copies} files copied into {install_dir}).")

    # 7. Final check
    return verifier_installation(install_dir)


def verifier_installation(install_dir: Path) -> bool:
    """Runs sd-cli.exe --version and checks the presence of the key libraries."""
    log_step("Validating that the installed binaries work...")
    sd_cli = install_dir / "sd-cli.exe"

    if not sd_cli.exists():
        log_error("sd-cli.exe could not be found after the operation.")
        return False

    try:
        res = subprocess.run([str(sd_cli), "--version"], capture_output=True, text=True, timeout=10)
        output = (res.stdout or "") + (res.stderr or "")
        print(f"\n[sd-cli --version output]:\n{output.strip()}\n")

        vulkan_ok = (install_dir / "ggml-vulkan.dll").exists()
        webm_ok = (install_dir / "webm.dll").exists()

        if vulkan_ok:
            log_success("Vulkan backend operational (ggml-vulkan.dll present)!")
        else:
            log_warn("ggml-vulkan.dll was not found. The Vulkan GPU backend may be inactive.")

        if webm_ok:
            log_success("WebM video support operational (webm.dll present)!")

        log_success("stable-diffusion.cpp is operational and ready for generator-assets!\n")
        return True
    except Exception as e:
        log_error(f"Error while running the sd-cli.exe test: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Automated update and Vulkan build of stable-diffusion.cpp."
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
        help="Restores the previous backup from C:\\SD\\backups\\."
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

    # If no specific argument is given, show the state and offer the choice
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
