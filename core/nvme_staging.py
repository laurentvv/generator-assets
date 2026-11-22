#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Temporary NVMe staging for cold-stored model files on slow external drives.

Per project process (AGENTS.md §7, 2026-11-14): D: is a slow USB 3.0 HDD
(2.8-30 MB/s on segmented tensor re-reads vs C: NVMe). Any model file residing
on a slow drive is copied into a unique subfolder under `nvme_root`, verified
by byte size, and always deleted in `finally` once execution completes or fails.
Files already on NVMe (or missing, e.g. mocked paths in tests) pass through
with zero overhead.
"""

from __future__ import annotations

from contextlib import contextmanager
import os
import shutil
import time
import uuid
from typing import Callable, Dict, Iterator, Tuple

from core.config import DEFAULT_MODEL_DIR


@contextmanager
def stager_vers_nvme_temporaire(
    paths: Dict[str, str],
    nvme_root: str = DEFAULT_MODEL_DIR,
    enabled: bool = True,
    slow_drives: Tuple[str, ...] = ("D:",),
    min_free_margin_bytes: int = 5 * 1024**3,
    prefix: str = "_tmp_nvme_",
    log_fn: Callable[[str], None] = print,
) -> Iterator[Dict[str, str]]:
    """Temporarily copies cold-stored model files from slow drives onto NVMe."""
    if not enabled:
        yield dict(paths)
        return

    nvme_abs = os.path.abspath(nvme_root)
    nvme_drive = os.path.splitdrive(nvme_abs)[0].upper()
    slow_norm = {d.upper() for d in slow_drives}

    to_stage: Dict[str, str] = {}
    for key, src_path in paths.items():
        if not src_path or not os.path.exists(src_path):
            continue
        src_abs = os.path.abspath(src_path)
        src_drive = os.path.splitdrive(src_abs)[0].upper()
        if src_drive in slow_norm and src_drive != nvme_drive:
            to_stage[key] = src_abs

    if not to_stage:
        yield dict(paths)
        return

    # Deduplicate shared source paths before disk-space budgeting and telemetry.
    unique_sources = list(dict.fromkeys(to_stage.values()))
    total_bytes = sum(os.path.getsize(p) for p in unique_sources)
    probe_dir = nvme_abs if os.path.exists(nvme_abs) else os.path.dirname(nvme_abs) or nvme_abs
    free_bytes = shutil.disk_usage(probe_dir).free
    if free_bytes < total_bytes + min_free_margin_bytes:
        raise OSError(
            f"Insufficient free space on '{nvme_root}' for temporary NVMe staging: "
            f"need {(total_bytes + min_free_margin_bytes) / (1024**3):.1f} GiB free, "
            f"have {free_bytes / (1024**3):.1f} GiB."
        )

    tmp_dir = os.path.join(nvme_abs, f"{prefix}{os.getpid()}_{uuid.uuid4().hex[:8]}")
    staged_map = dict(paths)
    try:
        os.makedirs(tmp_dir, exist_ok=True)
        t0 = time.monotonic()
        copied_by_src: Dict[str, str] = {}
        used_names: set[str] = set()
        for key, src_abs in to_stage.items():
            if src_abs in copied_by_src:
                staged_map[key] = copied_by_src[src_abs]
                continue
            base_name = os.path.basename(src_abs)
            dst_name = base_name if base_name not in used_names else f"{key}_{base_name}"
            idx = 1
            while dst_name in used_names:
                dst_name = f"{key}_{idx}_{base_name}"
                idx += 1
            used_names.add(dst_name)
            dst_abs = os.path.join(tmp_dir, dst_name)
            t_file = time.monotonic()
            shutil.copy2(src_abs, dst_abs)
            if os.path.getsize(dst_abs) != os.path.getsize(src_abs):
                raise RuntimeError(f"NVMe staging size mismatch for {base_name}")
            copied_by_src[src_abs] = dst_abs
            staged_map[key] = dst_abs
            size_gib = os.path.getsize(dst_abs) / (1024**3)
            log_fn(f"[NVMe stage] {base_name} ({size_gib:.2f} GiB in {time.monotonic() - t_file:.1f}s)")
        dt_total = time.monotonic() - t0
        mb_s = (total_bytes / (1024**2)) / max(dt_total, 1e-6)
        log_fn(f"[NVMe stage] Total {total_bytes / (1024**3):.2f} GiB staged in {dt_total:.1f}s ({mb_s:.1f} MB/s)")
        yield staged_map
    finally:
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
            if os.path.exists(tmp_dir):
                log_fn(f"⚠️ [NVMe stage] Partial cleanup (locked files remaining): {tmp_dir}")
            else:
                log_fn(f"[NVMe stage] Temporary copy cleaned: {tmp_dir}")
