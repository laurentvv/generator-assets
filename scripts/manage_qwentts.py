#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Management of the dedicated qwentts.cpp TTS engine (C:\\IA\\qwentts.cpp) for the
generator-assets repository.

Tool migrated from the ai-doc2video project on 2026-09-12 (evening) — same
behavior, new commands: git management (upstream commits
ServeurpersoCom/qwentts.cpp vs local HEAD), binary backups
(C:\\IA\\qwentts_backups, rotation 5), CMake Vulkan Release build,
audio smoke test and instant rollback. Also manages the GGUF model
catalog (C:\\IA\\qwentts.cpp\\models) with integrity checks
(GGUF header, size, SHA256 vs LFS OID) against the HuggingFace repo
Serveurperso/Qwen3-TTS-GGUF.

Management rule (user approval 2026-09-12, MEMORY_BANK §1.20): the
clone is NEVER modified by hand (no custom README inside, docs live in
this repo); updates go exclusively through this script.

Usage: uv run python scripts/manage_qwentts.py --check | --models |
       --backup | --update | --rollback | --test | --list-backups
"""

import os
import sys
import json
import time
import shutil
import logging
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("qwentts_manager")

QWEN_DIR = Path(r"C:\IA\qwentts.cpp")
BACKUP_ROOT = Path(r"C:\IA\qwentts_backups")
MODELS_DIR = QWEN_DIR / "models"
RELEASE_DIR = QWEN_DIR / "build" / "Release"
MAX_BACKUPS_TO_KEEP = 5
HEALTH_STATE_FILE = BACKUP_ROOT / "last_health_check.json"

def check_periodic_due(max_age_days: int = 5, auto_run: bool = True) -> bool:
    """
    Checks whether a routine check is required (last check > max_age_days).
    If auto_run=True and the delay is exceeded, automatically runs show_status().
    Returns True if a check was performed or was due, False otherwise.
    """
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    needs_check = True
    now = datetime.now()

    if HEALTH_STATE_FILE.is_file():
        try:
            with open(HEALTH_STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            last_check_str = data.get("last_check_timestamp")
            if last_check_str:
                last_dt = datetime.fromisoformat(last_check_str)
                age_days = (now - last_dt).total_seconds() / 86400.0
                if age_days < max_age_days:
                    needs_check = False
        except Exception:
            needs_check = True

    if needs_check:
        if auto_run:
            print("\n" + "=" * 80)
            print(f"⏰ [QWEN-TTS] Periodic health audit (> {max_age_days} days without a check)...")
            print("=" * 80)
            show_status()
        return True
    return False

def get_git_commit(repo_path: Path) -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            check=True
        )
        return res.stdout.strip()
    except Exception:
        return "unknown"

def get_git_commit_short(repo_path: Path) -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            check=True
        )
        return res.stdout.strip()
    except Exception:
        return "unknown"

def get_git_status(repo_path: Path) -> Dict[str, Any]:
    subprocess.run(["git", "fetch", "origin"], cwd=str(repo_path), capture_output=True, text=True)
    local_hash = get_git_commit(repo_path)

    behind_commits = []
    try:
        res = subprocess.run(
            ["git", "log", "HEAD..origin/master", "--oneline"],
            cwd=str(repo_path),
            capture_output=True,
            text=True
        )
        if res.stdout.strip():
            behind_commits = res.stdout.strip().splitlines()
    except Exception:
        pass

    submodule_status = "ok"
    try:
        res_sub = subprocess.run(
            ["git", "submodule", "status"],
            cwd=str(repo_path),
            capture_output=True,
            text=True
        )
        submodule_status = res_sub.stdout.strip()
    except Exception:
        pass

    return {
        "local_commit": local_hash,
        "is_up_to_date": len(behind_commits) == 0,
        "behind_count": len(behind_commits),
        "behind_commits": behind_commits,
        "submodules": submodule_status
    }

def check_binaries() -> Dict[str, Any]:
    target_exe = RELEASE_DIR / "qwen-tts.exe"
    vulkan_dll = RELEASE_DIR / "ggml-vulkan.dll"

    exists = target_exe.is_file() and vulkan_dll.is_file()
    size_mb = 0.0
    mod_time = "N/A"

    if exists:
        total_bytes = sum(f.stat().st_size for f in RELEASE_DIR.glob("*") if f.is_file())
        size_mb = total_bytes / (1024 * 1024)
        mtime = target_exe.stat().st_mtime
        mod_time = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")

    return {
        "healthy": exists,
        "exe_path": str(target_exe),
        "last_compiled": mod_time,
        "release_dir_size_mb": round(size_mb, 2)
    }

# ---------------------------------------------------------------------------
# GGUF model management and integrity checking
# ---------------------------------------------------------------------------

HF_API_TREE_URL = "https://huggingface.co/api/models/Serveurperso/Qwen3-TTS-GGUF/tree/main"
HF_DOWNLOAD_BASE_URL = "https://huggingface.co/Serveurperso/Qwen3-TTS-GGUF/resolve/main"

MODELS_CATALOG = {
    "qwen-talker-1.7b-customvoice-Q8_0.gguf": {
        "role": "Speaker Ryan (CustomVoice)",
        "required": True,
        "expected_bytes": 2042834304,
    },
    "qwen-tokenizer-12hz-Q8_0.gguf": {
        "role": "Audio Codec / 12Hz Vocoder",
        "required": True,
        "expected_bytes": 291150624,
    },
    "qwen-talker-1.7b-voicedesign-Q8_0.gguf": {
        "role": "VoiceDesign (custom voices)",
        "required": False,
        "expected_bytes": 2042833824,
    },
    "qwen-talker-1.7b-base-Q8_0.gguf": {
        "role": "1.7B Base Model",
        "required": False,
        "expected_bytes": 2079448256,
    },
}

def compute_file_sha256(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()

def check_gguf_magic(path: Path) -> Tuple[bool, int, str]:
    if not path.is_file():
        return False, 0, "File missing"
    try:
        with open(path, "rb") as f:
            magic = f.read(4)
            if magic != b"GGUF":
                return False, 0, f"Invalid magic bytes: {magic!r}"
            version = int.from_bytes(f.read(4), byteorder="little")
            return True, version, f"GGUF v{version}"
    except Exception as e:
        return False, 0, str(e)

def fetch_hf_model_metadata() -> Dict[str, Dict[str, Any]]:
    import urllib.request
    try:
        req = urllib.request.Request(
            HF_API_TREE_URL,
            headers={"User-Agent": "generator-assets/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            meta = {}
            for item in data:
                path_str = item.get("path", "")
                if path_str.endswith(".gguf"):
                    meta[path_str] = {
                        "size": item.get("size"),
                        "oid": item.get("lfs", {}).get("oid"),
                    }
            return meta
    except Exception as e:
        logger.warning(f"Unable to reach the HuggingFace API ({HF_API_TREE_URL}): {e}")
        return {}

def check_models(verify_remote: bool = True, verify_hash: bool = False) -> List[Dict[str, Any]]:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    remote_meta = fetch_hf_model_metadata() if verify_remote else {}

    results = []

    # 1. Analyze the catalog models
    for filename, info in MODELS_CATALOG.items():
        file_path = MODELS_DIR / filename
        exists = file_path.is_file()
        local_size = file_path.stat().st_size if exists else 0
        local_size_mb = round(local_size / (1024 * 1024), 1) if exists else 0.0

        magic_ok, gguf_ver, magic_desc = check_gguf_magic(file_path) if exists else (False, 0, "Not installed")

        rem_info = remote_meta.get(filename, {})
        remote_size = rem_info.get("size")
        remote_oid = rem_info.get("oid")

        status = "OK"
        hash_status = "N/A"

        if not exists:
            status = "MISSING_REQUIRED" if info["required"] else "MISSING_OPTIONAL"
        elif not magic_ok:
            status = "CORRUPTED_HEADER"
        elif remote_size and local_size != remote_size:
            status = "SIZE_MISMATCH"
        elif info["expected_bytes"] and local_size != info["expected_bytes"]:
            status = "SIZE_MISMATCH"

        if exists and verify_hash:
            logger.info(f"Computing SHA256 for {filename} ({local_size_mb} MB)...")
            local_sha = compute_file_sha256(file_path)
            if remote_oid:
                if local_sha.lower() == remote_oid.lower():
                    hash_status = "MATCH_HF_LFS"
                else:
                    hash_status = "HASH_MISMATCH"
                    status = "CORRUPTED_HASH"
            else:
                hash_status = f"SHA256:{local_sha[:12]}"

        results.append({
            "filename": filename,
            "role": info["role"],
            "required": info["required"],
            "exists": exists,
            "local_size_bytes": local_size,
            "local_size_mb": local_size_mb,
            "remote_size_bytes": remote_size,
            "gguf_valid": magic_ok,
            "gguf_desc": magic_desc,
            "status": status,
            "hash_status": hash_status,
            "remote_oid": remote_oid
        })

    # 2. Detect other local .gguf models not listed in the catalog
    for local_file in MODELS_DIR.glob("*.gguf"):
        if local_file.name not in MODELS_CATALOG:
            size_mb = round(local_file.stat().st_size / (1024 * 1024), 1)
            magic_ok, _, magic_desc = check_gguf_magic(local_file)
            results.append({
                "filename": local_file.name,
                "role": "Additional local model",
                "required": False,
                "exists": True,
                "local_size_bytes": local_file.stat().st_size,
                "local_size_mb": size_mb,
                "remote_size_bytes": None,
                "gguf_valid": magic_ok,
                "gguf_desc": magic_desc,
                "status": "CUSTOM_LOCAL",
                "hash_status": "N/A",
                "remote_oid": None
            })

    return results

def download_model_file(filename: str, force: bool = False) -> bool:
    import urllib.request
    dest_path = MODELS_DIR / filename
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    if dest_path.is_file() and not force:
        magic_ok, _, _ = check_gguf_magic(dest_path)
        if magic_ok:
            logger.info(f"The file {filename} already exists and is valid. Use --force to re-download it.")
            return True

    url = f"{HF_DOWNLOAD_BASE_URL}/{filename}"
    temp_path = dest_path.with_suffix(".download")
    logger.info(f"Downloading {filename} from HuggingFace...")
    logger.info(f"URL: {url}")

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "generator-assets/1.0"})
        with urllib.request.urlopen(req) as resp, open(temp_path, "wb") as out_f:
            total_bytes = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            start_t = time.perf_counter()
            last_print = 0

            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                out_f.write(chunk)
                downloaded += len(chunk)

                now = time.perf_counter()
                if now - last_print > 1.0 or downloaded == total_bytes:
                    speed = (downloaded / (1024 * 1024)) / max(0.001, (now - start_t))
                    pct = (downloaded / total_bytes * 100) if total_bytes > 0 else 0.0
                    mb_cur = downloaded / (1024 * 1024)
                    mb_tot = total_bytes / (1024 * 1024)
                    sys.stdout.write(f"\r   [{pct:5.1f}%] {mb_cur:.1f}/{mb_tot:.1f} MB @ {speed:.1f} MB/s...")
                    sys.stdout.flush()
                    last_print = now
            print()

        magic_ok, ver, desc = check_gguf_magic(temp_path)
        if not magic_ok:
            logger.error(f"Validation failed after download ({desc}). File deleted.")
            temp_path.unlink(missing_ok=True)
            return False

        if dest_path.is_file():
            dest_path.unlink(missing_ok=True)
        temp_path.rename(dest_path)
        logger.info(f"✅ {filename} downloaded and successfully validated ({desc})!")
        return True
    except Exception as e:
        logger.error(f"❌ Error while downloading {filename}: {e}")
        temp_path.unlink(missing_ok=True)
        return False

def show_models_table(verify_remote: bool = True, verify_hash: bool = False):
    print("=" * 80)
    print("🧠 GGUF MODEL CATALOG AND INTEGRITY (C:\\IA\\qwentts.cpp\\models)")
    print("=" * 80)
    print(f"📁 Local folder : {MODELS_DIR}")
    print("🌐 Remote repo : HuggingFace (Serveurperso/Qwen3-TTS-GGUF)")
    if verify_hash:
        print("🔍 Check mode: full SHA256 computation vs HuggingFace LFS OID")
    print("-" * 80)

    results = check_models(verify_remote=verify_remote, verify_hash=verify_hash)

    header = f"{'GGUF model':<38} | {'Role':<22} | {'Format':<10} | {'Size':<10} | {'Status'}"
    print(header)
    print("-" * 80)

    for r in results:
        fname = r["filename"]
        fname_display = (fname[:35] + "...") if len(fname) > 38 else fname

        role = r["role"]
        role_display = (role[:19] + "...") if len(role) > 22 else role

        if r["exists"]:
            etat = r["gguf_desc"]
            taille = f"{r['local_size_mb']} MB"
            if r["status"] == "OK":
                if verify_hash:
                    statut = f"✅ VALID ({r['hash_status']})"
                else:
                    statut = "✅ CONFORMING (Size & GGUF)"
            elif r["status"] == "CORRUPTED_HASH":
                statut = f"❌ WRONG SHA256 ({r['hash_status']})"
            elif r["status"] == "CORRUPTED_HEADER":
                statut = f"❌ INVALID HEADER ({r['gguf_desc']})"
            elif r["status"] == "SIZE_MISMATCH":
                statut = f"⚠️ WRONG SIZE ({r['local_size_bytes']} B)"
            else:
                statut = f"ℹ️ {r['status']}"
        else:
            etat = "ABSENT"
            rem_sz = round(r["remote_size_bytes"] / (1024 * 1024), 1) if r.get("remote_size_bytes") else "---"
            taille = f"({rem_sz} MB)" if rem_sz != "---" else "---"
            if r["required"]:
                statut = "❌ REQUIRED (Missing)"
            else:
                statut = "⚪ OPTIONAL (Not installed)"

        print(f"{fname_display:<38} | {role_display:<22} | {etat:<10} | {taille:<10} | {statut}")

    print("=" * 80)

    required_missing = [r["filename"] for r in results if r["required"] and not r["exists"]]
    corrupted = [r["filename"] for r in results if r["status"] in ("CORRUPTED_HEADER", "CORRUPTED_HASH", "SIZE_MISMATCH")]

    if not required_missing and not corrupted:
        print("🎉 All required production models (Ryan CustomVoice + 12Hz Codec) are intact!")
    else:
        if required_missing:
            print(f"⚠️ Missing required model(s): {', '.join(required_missing)}")
            print("💡 To download: uv run python scripts/manage_qwentts.py --download-model <file_name>")
        if corrupted:
            print(f"❌ Corrupted model(s) detected: {', '.join(corrupted)}")
            print("💡 To repair: uv run python scripts/manage_qwentts.py --download-model <file_name> --force")
    print("=" * 80)

def create_backup(reason: str = "manual_backup") -> Optional[Path]:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    commit_short = get_git_commit_short(QWEN_DIR)
    backup_name = f"backup_{timestamp}_{commit_short}"
    dest_dir = BACKUP_ROOT / backup_name

    logger.info(f"Creating the backup: {dest_dir}...")

    if not RELEASE_DIR.exists():
        logger.error(f"The Release folder ({RELEASE_DIR}) does not exist. Cannot back up the binaries.")
        return None

    try:
        dest_bin = dest_dir / "Release"
        dest_bin.mkdir(parents=True, exist_ok=True)

        # Copy all the compiled binaries and libraries
        copied_files = []
        for item in RELEASE_DIR.iterdir():
            if item.is_file():
                shutil.copy2(item, dest_bin / item.name)
                copied_files.append(item.name)

        # Save the backup metadata
        meta = {
            "timestamp": timestamp,
            "created_at": datetime.now().isoformat(),
            "reason": reason,
            "commit": get_git_commit(QWEN_DIR),
            "commit_short": commit_short,
            "submodule_ggml": get_git_commit(QWEN_DIR / "ggml"),
            "copied_files_count": len(copied_files),
            "copied_files": copied_files
        }
        with open(dest_dir / "backup_metadata.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        logger.info(f"✅ Backup successful ({len(copied_files)} files, ~{len(copied_files)} artifacts).")
        prune_old_backups()
        return dest_dir
    except Exception as e:
        logger.error(f"❌ Backup failed: {e}")
        if dest_dir.exists():
            shutil.rmtree(dest_dir, ignore_errors=True)
        return None

def prune_old_backups():
    if not BACKUP_ROOT.exists():
        return
    backups = sorted([d for d in BACKUP_ROOT.iterdir() if d.is_dir() and d.name.startswith("backup_")], key=lambda d: d.name)
    if len(backups) > MAX_BACKUPS_TO_KEEP:
        to_delete = backups[:-MAX_BACKUPS_TO_KEEP]
        for old in to_delete:
            logger.info(f"Backup rotation: deleting {old.name}")
            shutil.rmtree(old, ignore_errors=True)

def list_backups() -> List[Dict[str, Any]]:
    if not BACKUP_ROOT.exists():
        return []
    backups = sorted([d for d in BACKUP_ROOT.iterdir() if d.is_dir() and d.name.startswith("backup_")], key=lambda d: d.name, reverse=True)
    results = []
    for b in backups:
        meta_file = b / "backup_metadata.json"
        meta = {}
        if meta_file.is_file():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                pass
        results.append({
            "name": b.name,
            "path": str(b),
            "created_at": meta.get("created_at", "N/A"),
            "commit_short": meta.get("commit_short", "N/A"),
            "reason": meta.get("reason", "N/A"),
            "files_count": meta.get("copied_files_count", 0)
        })
    return results

def rollback(backup_name: Optional[str] = None) -> bool:
    backups = list_backups()
    if not backups:
        logger.error("No backup available in C:\\IA\\qwentts_backups.")
        return False

    target_backup = None
    if backup_name:
        for b in backups:
            if b["name"] == backup_name or backup_name in b["name"]:
                target_backup = Path(b["path"])
                break
        if not target_backup:
            logger.error(f"Backup not found: '{backup_name}'")
            return False
    else:
        target_backup = Path(backups[0]["path"])

    logger.warning(f"⚠️ Restoring the backup: {target_backup.name}...")
    source_bin = target_backup / "Release"
    if not source_bin.exists():
        logger.error("The Release folder is missing from the backup.")
        return False

    try:
        RELEASE_DIR.mkdir(parents=True, exist_ok=True)
        restored = 0
        for item in source_bin.iterdir():
            if item.is_file():
                shutil.copy2(item, RELEASE_DIR / item.name)
                restored += 1

        logger.info(f"✅ Rollback completed successfully! ({restored} files restored into {RELEASE_DIR}).")
        return True
    except Exception as e:
        logger.error(f"❌ Critical error during the rollback: {e}")
        return False

def smoke_test() -> bool:
    target_exe = RELEASE_DIR / "qwen-tts.exe"
    if not target_exe.is_file():
        logger.error("qwen-tts.exe not found for the smoke test.")
        return False

    talker = MODELS_DIR / "qwen-talker-1.7b-customvoice-Q8_0.gguf"
    codec = MODELS_DIR / "qwen-tokenizer-12hz-Q8_0.gguf"

    if not (talker.is_file() and codec.is_file()):
        logger.warning("Models not found for the full audio test. Running the --help test...")
        res = subprocess.run([str(target_exe), "--help"], capture_output=True, text=True)
        return res.returncode == 0

    test_wav = QWEN_DIR / "build" / "smoke_test.wav"
    cmd = [
        str(target_exe),
        "--model", str(talker),
        "--codec", str(codec),
        "--speaker", "ryan",
        "--lang", "English",
        "-o", str(test_wav)
    ]

    logger.info("🧪 Running the Vulkan audio Smoke Test (generation of a short sentence)...")
    try:
        start_t = time.perf_counter()
        proc = subprocess.run(
            cmd,
            input="Local text to speech engine smoke test.".encode("utf-8"),
            capture_output=True,
            check=False,
            timeout=45
        )
        elapsed = time.perf_counter() - start_t

        if proc.returncode == 0 and test_wav.is_file() and test_wav.stat().st_size > 1000:
            logger.info(f"✅ Smoke Test PASSED in {elapsed:.2f}s! WAV generated ({test_wav.stat().st_size} bytes).")
            test_wav.unlink(missing_ok=True)
            return True
        else:
            logger.error(f"❌ Smoke Test failure: returncode={proc.returncode}, stderr={proc.stderr.decode('utf-8', errors='replace')}")
            test_wav.unlink(missing_ok=True)
            return False
    except Exception as e:
        logger.error(f"❌ Exception during the Smoke Test: {e}")
        test_wav.unlink(missing_ok=True)
        return False

def build_vulkan() -> bool:
    logger.info("🔨 CMake Vulkan Release configuration and build...")

    cmake_env = os.environ.copy()
    build_dir = QWEN_DIR / "build"
    build_dir.mkdir(parents=True, exist_ok=True)

    # 1. CMake Configure
    cfg_cmd = [
        "cmake",
        "-S", str(QWEN_DIR),
        "-B", str(build_dir),
        "-DGGML_VULKAN=ON"
    ]
    logger.info(f"   Config: {' '.join(cfg_cmd)}")
    cfg_res = subprocess.run(cfg_cmd, cwd=str(QWEN_DIR), env=cmake_env, capture_output=True, text=True)
    if cfg_res.returncode != 0:
        logger.error(f"CMake configure failed:\n{cfg_res.stderr}\n{cfg_res.stdout}")
        return False

    # 2. CMake Build
    build_cmd = [
        "cmake",
        "--build", str(build_dir),
        "--config", "Release",
        "-j4"
    ]
    logger.info(f"   Build: {' '.join(build_cmd)}")
    build_res = subprocess.run(build_cmd, cwd=str(QWEN_DIR), env=cmake_env, capture_output=True, text=True)
    if build_res.returncode != 0:
        logger.error(f"CMake build failed:\n{build_res.stderr}\n{build_res.stdout}")
        return False

    logger.info("✅ Build completed successfully.")
    return True

def perform_update(force: bool = False) -> bool:
    print("=" * 80)
    print("🚀 SECURE QWENTTS.CPP UPDATE PROCEDURE")
    print("=" * 80)

    # 1. Check the git state
    status = get_git_status(QWEN_DIR)
    logger.info(f"Current commit: {get_git_commit_short(QWEN_DIR)}")

    if status["is_up_to_date"] and not force:
        logger.info("The local repo is already up to date with origin/master (no new commit).")
        return True
    elif status["is_up_to_date"] and force:
        logger.info("Forced rebuild and validation...")

    # 2. MANDATORY prior backup
    logger.info("Step 1/4: Safety backup of the current working binaries...")
    backup_path = create_backup(reason="pre_update_backup")
    if not backup_path:
        logger.error("Unable to create the backup. Cancelling the update for safety.")
        return False

    # 3. Git Pull & Submodules
    logger.info("Step 2/4: Downloading the Git updates...")
    try:
        pull_res = subprocess.run(["git", "pull", "--rebase"], cwd=str(QWEN_DIR), capture_output=True, text=True, check=True)
        logger.info(f"Git pull: {pull_res.stdout.strip()}")
        subprocess.run(["git", "submodule", "update", "--init", "--recursive"], cwd=str(QWEN_DIR), capture_output=True, text=True, check=True)
        logger.info("Git submodules updated.")
    except Exception as e:
        logger.error(f"Git pull failed: {e}")
        logger.warning("Restoring the backup...")
        rollback(backup_path.name)
        return False

    # 4. Vulkan build
    logger.info("Step 3/4: Vulkan Release C++ rebuild...")
    build_ok = build_vulkan()
    if not build_ok:
        logger.error("❌ The build failed! Automatically triggering the ROLLBACK...")
        rollback(backup_path.name)
        return False

    # 5. Smoke Test
    logger.info("Step 4/4: Functional validation (Smoke Test)...")
    smoke_ok = smoke_test()
    if not smoke_ok:
        logger.error("❌ The built binary failed the Smoke Test! Automatically triggering the ROLLBACK...")
        rollback(backup_path.name)
        return False

    new_commit = get_git_commit_short(QWEN_DIR)
    print("\n" + "=" * 80)
    print("🎉 UPDATE COMPLETED SUCCESSFULLY!")
    print(f"New Commit: {new_commit}")
    print(f"Fallback backup kept in: {backup_path.name}")
    print("=" * 80)
    return True

def show_status():
    print("=" * 80)
    print("📊 TTS ENGINE STATE AND HEALTH (C:\\IA\\qwentts.cpp)")
    print("=" * 80)

    status = get_git_status(QWEN_DIR)
    bins = check_binaries()
    backups = list_backups()

    print(f"📁 Repo path        : {QWEN_DIR}")
    print(f"🔗 Local commit     : {status['local_commit'][:12]} ({get_git_commit_short(QWEN_DIR)})")

    if status["is_up_to_date"]:
        print("⚡ Git status       : ✅ UP TO DATE with origin/master")
    else:
        print(f"⚡ Git status       : ⚠️ BEHIND by {status['behind_count']} commit(s):")
        for c in status["behind_commits"]:
            print(f"   - {c}")

    print("-" * 80)
    print(f"⚙️ Compiled binaries : {'✅ OPERATIONAL' if bins['healthy'] else '❌ MISSING OR INCOMPLETE'}")
    print(f"   Executable       : {bins['exe_path']}")
    print(f"   Last build       : {bins['last_compiled']}")
    print(f"   Artifact size    : {bins['release_dir_size_mb']} MB")

    print("-" * 80)
    models = check_models(verify_remote=False, verify_hash=False)
    req_ok = all(m["status"] == "OK" for m in models if m["required"])
    installed_cnt = sum(1 for m in models if m["exists"])
    total_sz_mb = sum(m["local_size_mb"] for m in models)
    print(f"🧠 GGUF TTS models   : {'✅ READY & CONFORMING' if req_ok else '❌ REQUIRED MODEL(S) MISSING'}")
    print(f"   Folder           : {MODELS_DIR}")
    print(f"   Installed models : {installed_cnt} file(s) (~{total_sz_mb:.1f} MB)")
    for m in models:
        if m["exists"]:
            icon = "✅" if m["status"] == "OK" else "⚠️"
            print(f"   • {m['filename']:<38} : {icon} {m['gguf_desc']} ({m['local_size_mb']} MB) [{m['role']}]")
        elif m["required"]:
            print(f"   • {m['filename']:<38} : ❌ MISSING (Required for Ryan)")

    print("-" * 80)
    print(f"📦 Available backups : {len(backups)} backup(s) archived in {BACKUP_ROOT}")
    for b in backups[:3]:
        print(f"   • {b['name']} [{b['created_at']}] (Commit: {b['commit_short']}) - {b['reason']}")
    print("=" * 80)

    try:
        BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
        with open(HEALTH_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "last_check_timestamp": datetime.now().isoformat(),
                "local_commit": status["local_commit"][:12],
                "is_up_to_date": status["is_up_to_date"],
                "binaries_healthy": bins["healthy"],
                "models_ok": req_ok
            }, f, indent=2)
    except Exception:
        pass

def main():
    parser = argparse.ArgumentParser(description="Update, backup and model manager for qwentts.cpp (generator-assets repo)")
    parser.add_argument("--check", action="store_true", help="Check the git state, the binaries and the available updates")
    parser.add_argument("--due-only", action="store_true", help="Only check if the last check is older than --days days")
    parser.add_argument("--days", type=int, default=5, help="Inactivity threshold in days before automatic trigger (default: 5)")
    parser.add_argument("--models", action="store_true", help="Check the GGUF model catalog and integrity")
    parser.add_argument("--verify-hash", action="store_true", help="Compute and verify the full SHA256s against HuggingFace LFS")
    parser.add_argument("--download-model", type=str, default=None, help="Download a specific model from HuggingFace")
    parser.add_argument("--download-all", action="store_true", help="Download all the missing required models")
    parser.add_argument("--no-remote", action="store_true", help="Disable HuggingFace network queries")
    parser.add_argument("--backup", action="store_true", help="Create an immediate backup of the current binaries")
    parser.add_argument("--update", action="store_true", help="Perform the secure update with backup, build and smoke test")
    parser.add_argument("--force", action="store_true", help="Force the re-download or the rebuild")
    parser.add_argument("--rollback", nargs="?", const="latest", default=None, help="Restore a backup (default: the most recent)")
    parser.add_argument("--list-backups", action="store_true", help="List all the available backups")
    parser.add_argument("--test", action="store_true", help="Run an audio validation smoke test on the current binaries")

    args = parser.parse_args()

    if args.check:
        if args.due_only:
            is_due = check_periodic_due(max_age_days=args.days, auto_run=True)
            if not is_due:
                print(f"✅ TTS engine checked recently (< {args.days} days). No check needed.")
        else:
            show_status()
    elif args.models:
        show_models_table(verify_remote=not args.no_remote, verify_hash=args.verify_hash)
    elif args.download_model:
        download_model_file(args.download_model, force=args.force)
    elif args.download_all:
        models = check_models(verify_remote=False)
        for m in models:
            if m["required"] and not m["exists"]:
                download_model_file(m["filename"], force=args.force)
    elif args.backup:
        create_backup("manual_cli_backup")
    elif args.update:
        perform_update(force=args.force)
    elif args.rollback:
        target = None if args.rollback == "latest" else args.rollback
        rollback(target)
    elif args.list_backups:
        backups = list_backups()
        print(f"\n📦 {len(backups)} recorded backup(s):")
        for b in backups:
            print(f"  • {b['name']} ({b['created_at']}) | Commit: {b['commit_short']} | {b['reason']}")
        print()
    elif args.test:
        smoke_test()
    else:
        show_status()

if __name__ == "__main__":
    main()
