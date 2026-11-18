#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Animated-icon rasterization: useAnimations Lottie JSON → transparent RGBA frames.

Pipeline (CPU-only, zero PyTorch):
1. the `react-useanimations` npm package (MIT) ships each icon as a CommonJS
   module embedding a Lottie `animationData` object — fetched once as an npm
   tarball and cached under `output/lottie_cache/`;
2. Node.js (native `require`) extracts the `animationData` object per icon —
   the modules are JavaScript object literals with unquoted keys, so the
   authoring runtime is the safe parser (no regex hacks);
3. `python-lottie` (PyPI `lottie`, pure Python) loads the dict into an
   `Animation` and exports each frame as SVG (dependency-free);
4. `resvg` (static Rust binary, MIT, C:\\resvg or RESVG_PATH) rasterizes each
   SVG to RGBA PNG with transparency;
5. the RGBA frames feed `core.gif_export` (encode/verify/contact) and
   `core.alpha_qa` — the same delivery machinery as `gif_export`.

Icons are 32×32 stroke icons animated at 30 fps (40-50 frames ≈ 1.3-1.7 s
loops), painted in a single color (black) — `recolor_animation` tints them
at the Lottie level (exact, no pixel heuristics).
"""

import json
import os
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from lottie.exporters.svg import export_svg
from lottie.objects import Animation

from core.process import run_engine

USEANIMATIONS_VERSION = "3.1.1"
USEANIMATIONS_TARBALL = (
    f"https://registry.npmjs.org/react-useanimations/-/react-useanimations-{USEANIMATIONS_VERSION}.tgz"
)
DEFAULT_CACHE_DIR = Path("output") / "lottie_cache"


def resolve_resvg() -> str:
    """resvg binary resolution: RESVG_PATH env → C:\\resvg\\resvg.exe → PATH."""
    env = os.getenv("RESVG_PATH")
    if env and Path(env).exists():
        return env
    default = Path(r"C:\resvg\resvg.exe")
    if default.exists():
        return str(default)
    return "resvg"  # PATH fallback


def fetch_useanimations(cache_dir: Path, version: str = USEANIMATIONS_VERSION,
                         timeout: float = 120.0) -> Path:
    """Downloads + extracts the npm tarball once; returns the lib/ icon dir.

    Cache layout: `<cache>/rua-<version>.tgz` + `<cache>/pkg-<version>/lib/*.js`.
    A cached version is reused as-is (re-run with a different version or an
    emptied cache to upgrade).
    """
    cache_dir = Path(cache_dir)
    lib_dir = cache_dir / f"pkg-{version}" / "lib"
    if lib_dir.exists() and any(lib_dir.glob("*.js")):
        return lib_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    tgz_path = cache_dir / f"rua-{version}.tgz"
    if not tgz_path.exists():
        url = (f"https://registry.npmjs.org/react-useanimations/-/"
               f"react-useanimations-{version}.tgz")
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = response.read()
        tgz_path.write_bytes(payload)
    pkg_dir = cache_dir / f"pkg-{version}"
    with tarfile.open(tgz_path, "r:gz") as archive:
        for member in archive.getmembers():
            if member.name.startswith("package/lib/") and member.name.endswith(".js"):
                # extractfile + rewrite: we flatten package/lib/<icon>.js to
                # pkg-<version>/lib/<icon>.js (tarfile.extract() would keep
                # the package/ prefix)
                relative = member.name[len("package/"):]
                target = pkg_dir / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, open(target, "wb") as out:
                    out.write(source.read())
    if not any(lib_dir.glob("*.js")):
        raise ValueError(f"No icon modules extracted from the tarball into {lib_dir}")
    return lib_dir


def export_icon_data(js_path: Path, node: str = "node") -> Dict[str, Any]:
    """Extracts the embedded `animationData` Lottie object via Node.js.

    The npm modules are CommonJS with unquoted JavaScript object keys — the
    authoring runtime is the safe parser; hand-rolled JSON hacks are not.
    """
    js_path = Path(js_path).resolve().as_posix()
    script = "const m = require(process.argv[1]);" \
             "process.stdout.write(JSON.stringify(m.default.animationData));"
    result = run_engine([node, "-e", script, js_path], timeout=30, etiquette="node")
    return json.loads(result.stdout)


def load_animation(data: Dict[str, Any]) -> Animation:
    """Lottie dict → python-lottie `Animation` (no temp file)."""
    return Animation.load(data)


def recolor_animation(data: Dict[str, Any], rgb: Tuple[int, int, int]) -> Dict[str, Any]:
    """Tints every Lottie color to `rgb` at the JSON level (exact, keeps alpha).

    useAnimations icons paint a single color (black, 0-1 float RGBA `c.k`
    arrays); this rewrites all color keys, preserving per-stop alpha.
    """
    import copy

    recolored = copy.deepcopy(data)
    target = [c / 255 for c in rgb]

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            color = node.get("c")
            if isinstance(color, dict) and isinstance(color.get("k"), list):
                k = color["k"]
                if k and isinstance(k[0], (int, float)):
                    alpha = k[3] if len(k) > 3 else 1
                    color["k"] = target + [alpha]
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(recolored)
    return recolored


def list_icons(lib_dir: Path) -> List[str]:
    """Icon names available in a cached tarball (sorted, .js stems)."""
    return sorted(p.stem for p in Path(lib_dir).glob("*.js"))


def render_frames(animation: Animation, size: int = 128,
                  resvg_path: Optional[str] = None,
                  timeout: float = 120.0) -> Tuple[List[Any], float, int]:
    """Renders every Lottie frame to an RGBA PIL image at `size` via resvg.

    python-lottie exports each frame as SVG (dependency-free); resvg
    rasterizes it with transparency at `size / animation.width` zoom.
    Returns (frames, fps, frame_count).
    """
    resvg = resvg_path or resolve_resvg()
    fps = float(animation.frame_rate)
    start = int(animation.in_point)
    end = int(animation.out_point)
    if end <= start:
        raise ValueError("Lottie animation has no frames")
    zoom = float(size) / float(animation.width)
    frames: List[Any] = []
    with tempfile.TemporaryDirectory(prefix="lottie_render_") as work_dir:
        svg_path = Path(work_dir) / "frame.svg"
        png_path = Path(work_dir) / "frame.png"
        for frame in range(start, end + 1):
            with open(svg_path, "wb") as svg_file:
                export_svg(animation, svg_file, frame=frame, pretty=False)
            run_engine([resvg, "--zoom", str(zoom), str(svg_path), str(png_path)],
                       timeout=timeout, etiquette="resvg")
            frames.append(Image.open(png_path).convert("RGBA"))
    return frames, fps, end - start + 1
