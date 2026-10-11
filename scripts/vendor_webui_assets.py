#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Downloads and vendors the pinned static assets of the web UI.

The web UI is full-Python (FastAPI + Jinja2 + HTMX): it must run offline,
from the local filesystem, with zero Node/npm toolchain. The few browser
libraries it uses are therefore downloaded ONCE by this script, pinned to
exact versions, and committed under server/static/vendor/. The Tailwind
standalone CLI (single binary, no Node) is only needed to REBUILD
server/static/app.css when the theme changes — the compiled CSS is
committed too, so running the web UI never requires any download.

Usage:
    uv run python scripts/vendor_webui_assets.py            # vendor JS libs
    uv run python scripts/vendor_webui_assets.py --tailwind # also fetch the Tailwind CLI
"""

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_DIR = REPO_ROOT / "server" / "static" / "vendor"
TOOLS_BIN = REPO_ROOT / "tools" / "bin"

# Pinned versions (checked 2026-10-11 against the npm registry and GitHub releases).
# JS libs are fetched as npm tarballs from registry.npmjs.org (host reachable in
# every environment observed so far, unlike unpkg.com/jsdelivr) and the single
# dist file is extracted from the package.
PINNED = {
    "htmx": {
        "url": "https://registry.npmjs.org/htmx.org/-/htmx.org-2.0.11.tgz",
        "member": "package/dist/htmx.min.js",
        "dest": VENDOR_DIR / "htmx.min.js",
        # Integrity pins computed from the first verified download (2026-10-11).
        "sha256": "d6fdc75f204e6bdefa99b69bf1e6d4ac69b8a364f77929f45c13476b4000f717",
    },
    "htmx-sse-ext": {
        "url": "https://registry.npmjs.org/htmx-ext-sse/-/htmx-ext-sse-2.2.4.tgz",
        "member": "package/dist/sse.js",
        "dest": VENDOR_DIR / "sse.js",
        "sha256": "3b5992a541619babefc4c169505af474df5c3039da51e59b96ccf9241ecd61d2",
    },
    "alpine": {
        "url": "https://registry.npmjs.org/alpinejs/-/alpinejs-3.17.4.tgz",
        "member": "package/dist/cdn.min.js",
        "dest": VENDOR_DIR / "alpine.min.js",
        "sha256": "232519394c6c8fdba6f362b1d9da16106db513cdbf899011f00daab4051df31c",
    },
    "tailwind": {
        "url": "https://github.com/tailwindlabs/tailwindcss/releases/download/v4.3.3/tailwindcss-windows-x64.exe",
        "dest": TOOLS_BIN / "tailwindcss.exe",
        "sha256": None,  # large binary: integrity checked by size only
    },
}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(name: str, spec: dict) -> int:
    import tarfile
    import tempfile

    dest: Path = spec["dest"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    already_ok = dest.exists() and (
        (spec["sha256"] and sha256_of(dest) == spec["sha256"])
        # Binaries without an integrity pin (tailwind): presence + sane size.
        or (spec["sha256"] is None and not spec.get("member") and dest.stat().st_size > (1 << 20))
    )
    if already_ok:
        print(f"[vendor] {name}: already vendored -> {dest.relative_to(REPO_ROOT)}")
        return 0
    print(f"[vendor] {name}: downloading {spec['url']} ...")
    # curl as the download engine: it honors the host network setup where a
    # plain urllib socket sometimes cannot resolve DNS (observed 2026-10-11).
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "download.bin"
        result = subprocess.run(
            ["curl", "-fsSL", "--retry", "3", "-o", str(raw), spec["url"]],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            print(f"[vendor] {name}: curl failed: {result.stderr.strip()}", file=sys.stderr)
            return 1
        if spec.get("member"):
            # npm tarball: extract exactly one dist member, no traversal.
            with tarfile.open(raw, "r:gz") as archive:
                member = archive.getmember(spec["member"])
                extracted = archive.extractfile(member)
                if extracted is None:
                    print(f"[vendor] {name}: member {spec['member']} is not a file", file=sys.stderr)
                    return 1
                dest.write_bytes(extracted.read())
        else:
            dest.write_bytes(raw.read_bytes())
    size = dest.stat().st_size
    if size < 1024:
        dest.unlink(missing_ok=True)
        print(f"[vendor] {name}: FAILED (only {size} bytes)", file=sys.stderr)
        return 1
    got = sha256_of(dest)
    if spec["sha256"] and got != spec["sha256"]:
        print(f"[vendor] {name}: sha256 MISMATCH got={got}", file=sys.stderr)
        return 1
    if spec["sha256"] is None:
        print(f"[vendor] {name}: downloaded {size} bytes, sha256={got} (update the pin if you keep it)")
    else:
        print(f"[vendor] {name}: vendored {size} bytes -> {dest.relative_to(REPO_ROOT)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tailwind", action="store_true", help="Also fetch the Tailwind standalone CLI (tools/bin, git-ignored).")
    args = parser.parse_args()

    targets = {k: v for k, v in PINNED.items() if k != "tailwind" or args.tailwind}
    codes = [download(name, spec) for name, spec in targets.items()]
    if any(codes):
        return 1
    print("[vendor] done. JS assets are committed; tools/bin stays git-ignored.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
