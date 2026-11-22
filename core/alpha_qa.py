#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Alpha QA gates for transparent assets (stickers, sprites, GIF sources).

Ported from miles990/video-gif-studio (MIT) — scripts/image_alpha.py,
detection gates only. The upstream LLM-assisted hole review
(`image_hole_judge`) is intentionally NOT ported: enclosed zero-alpha
regions are counted into the hole-ratio gate instead, so the verdict is
purely local and deterministic (PASS / FAIL — no pending review state).

Gates (all measured after `clear_haze`, NEAR_ZERO_ALPHA=10):
- fake_transparency: painted checkerboard detector (RGB-only periodic
  neutral pattern along >=3 frame edges);
- transparent_fraction: share of alpha<=10 pixels must stay in [0.15, 0.90];
- clipped_border: 2-px frame border must be >=99% transparent;
- isolated_specks: non-largest connected-component area ratio > 0.001;
- interior_holes: zero-alpha cores >4 px not touching the border (plus
  translucent pockets of depth >=2), ratio > 0.005;
- halo: semi-transparent pixels within 5 px of an opaque area must have
  CIELAB ΔE <= 20 vs the nearest opaque color (>=95%), and the outer ring
  luma must stay <= 8.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np
from PIL import Image, ImageDraw

NEAR_ZERO_ALPHA = 10
HALO_DELTA_E_MAX = 20


def _lab(rgb: np.ndarray) -> np.ndarray:
    """CIELAB conversion of an RGB uint8 array (float32, L in 0..100)."""
    return cv2.cvtColor(rgb.astype(np.float32) / 255, cv2.COLOR_RGB2LAB)


def _delta_e(lab_a: np.ndarray, lab_b: np.ndarray) -> np.ndarray:
    """CIEDE2000 color difference (Sharma et al. 2005), vectorized.

    Same metric as upstream (`shot_match.delta_e`) so the halo threshold of
    20 keeps its upstream semantics (plain CIELAB Euclidean distance would
    over-report chroma fringes and make the gate stricter than intended).
    """
    l1, a1, b1 = lab_a[..., 0], lab_a[..., 1], lab_a[..., 2]
    l2, a2, b2 = lab_b[..., 0], lab_b[..., 1], lab_b[..., 2]
    c1 = np.hypot(a1, b1)
    c2 = np.hypot(a2, b2)
    c_bar = (c1 + c2) / 2
    c_bar7 = c_bar ** 7
    g = 0.5 * (1 - np.sqrt(c_bar7 / (c_bar7 + 25.0 ** 7)))
    a1p = (1 + g) * a1
    a2p = (1 + g) * a2
    c1p = np.hypot(a1p, b1)
    c2p = np.hypot(a2p, b2)
    h1p = np.where((a1p == 0) & (b1 == 0), 0.0, np.degrees(np.arctan2(b1, a1p)) % 360)
    h2p = np.where((a2p == 0) & (b2 == 0), 0.0, np.degrees(np.arctan2(b2, a2p)) % 360)
    delta_lp = l2 - l1
    delta_cp = c2p - c1p
    dh = h2p - h1p
    dh = np.where(c1p * c2p == 0, 0.0, dh)
    dh = np.where((c1p * c2p != 0) & (np.abs(dh) > 180), dh - 360 * np.sign(dh), dh)
    delta_hp = 2 * np.sqrt(c1p * c2p) * np.sin(np.radians(dh) / 2)
    l_bar = (l1 + l2) / 2
    cp_bar = (c1p + c2p) / 2
    h_sum = h1p + h2p
    h_bar = np.where(c1p * c2p == 0, h_sum,
                     np.where(np.abs(h1p - h2p) <= 180, h_sum / 2,
                              np.where(h_sum < 360, (h_sum + 360) / 2, (h_sum - 360) / 2)))
    t = (1 - 0.17 * np.cos(np.radians(h_bar - 30))
         + 0.24 * np.cos(np.radians(2 * h_bar))
         + 0.32 * np.cos(np.radians(3 * h_bar + 6))
         - 0.20 * np.cos(np.radians(4 * h_bar - 63)))
    d_theta = 30 * np.exp(-(((h_bar - 275) / 25) ** 2))
    cp_bar7 = cp_bar ** 7
    rc = 2 * np.sqrt(cp_bar7 / (cp_bar7 + 25.0 ** 7))
    sl = 1 + 0.015 * (l_bar - 50) ** 2 / np.sqrt(20 + (l_bar - 50) ** 2)
    sc = 1 + 0.045 * cp_bar
    sh = 1 + 0.015 * cp_bar * t
    rt = -np.sin(np.radians(2 * d_theta)) * rc
    return np.sqrt((delta_lp / sl) ** 2 + (delta_cp / sc) ** 2
                   + (delta_hp / sh) ** 2 + rt * (delta_cp / sc) * (delta_hp / sh))


def clear_haze(arr: np.ndarray) -> Any:
    """Keeps 2 px of true edge coverage, discards remote near-zero haze."""
    arr = arr.copy()
    _, distance = nearest_opaque(arr)
    haze = (arr[..., 3] > 0) & (arr[..., 3] <= NEAR_ZERO_ALPHA)
    if distance is not None:
        haze &= distance > 2
    arr[haze] = 0
    return arr, int(haze.sum())


def nearest_opaque(arr: np.ndarray) -> Any:
    """Nearest opaque pixel color per pixel + its distance (cv2 labels)."""
    opaque = arr[..., 3] >= 250
    if not opaque.any():
        return None, None
    distance, labels = cv2.distanceTransformWithLabels(
        (~opaque).astype("uint8"), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    colors = np.zeros((int(labels.max()) + 1, 3), np.uint8)
    colors[labels[opaque]] = arr[..., :3][opaque]
    return colors[labels], distance


def checkerboard(arr: np.ndarray) -> bool:
    """Detects a painted (opaque) checkerboard masquerading as transparency.

    Requires a periodic neutral two-color pattern along >=3 frame edges with
    any alpha present at all excluded (a real RGBA source fails the test
    immediately — upstream behavior).
    """
    rgb = arr[..., :3].astype(float)
    height, width = rgb.shape[:2]
    if arr.shape[2] == 4 and np.any(arr[..., 3] < 255):
        return False
    lines = [rgb[min(2, height - 1)], rgb[max(0, height - 3)],
             rgb[:, min(2, width - 1)], rgb[:, max(0, width - 3)]]
    hits = 0
    for line in lines:
        if len(line) < 64 or np.mean(np.ptp(line, axis=1) < 5) < 0.95:
            continue
        y = line.mean(axis=1)
        lo, hi = np.percentile(y, [10, 90])
        difference = hi - lo
        if not 10 <= difference <= 60:
            continue
        if np.mean(np.minimum(abs(y - lo), abs(y - hi)) < 4) < 0.9:
            continue
        y = y - y.mean()
        for block in range(8, 33):
            if len(y) <= 2 * block + 2:
                continue

            def corr(shift: int, series: np.ndarray = y) -> float:
                return float(np.dot(series[:-shift], series[shift:]) /
                             max(np.sqrt(np.sum(series[:-shift] ** 2) * np.sum(series[shift:] ** 2)), 1e-9))

            if corr(2 * block) >= 0.5 and corr(block) <= -0.5:
                hits += 1
                break
    return hits >= 3


def enclosed_regions(alpha: np.ndarray) -> Any:
    """Enclosed zero-alpha cores + substantial translucent pockets.

    A zero-alpha core stays enclosed even beside a translucent channel.
    Only <=4-pixel cores are ignored as raster specks; no shape grants
    approval (upstream comment).
    """
    result = np.zeros(alpha.shape, np.int32)
    regions: List[Dict[str, Any]] = []
    for binary, translucent in ((alpha == 0, False), (alpha < 250, True)):
        count, labels, stats, _ = cv2.connectedComponentsWithStats(binary.astype("uint8"), 8)
        boundary = set(np.unique(np.r_[labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
        for label in range(1, count):
            if label in boundary:
                continue
            area = int(stats[label, cv2.CC_STAT_AREA])
            if area <= 4:
                continue
            component = labels == label
            values = alpha[component]
            if translucent and (np.any(values == 0) or not np.any(values <= 128)):
                continue
            depth = cv2.distanceTransform(component.astype("uint8"), cv2.DIST_L2, 5)
            if translucent and depth.max() < 2:
                continue
            cy, cx = np.unravel_index(depth.argmax(), depth.shape)
            index = len(regions) + 1
            result[component] = index
            regions.append(dict(
                id=index, label=index, area=area, center=[int(cx), int(cy)],
                radius_px=float(depth.max()), translucent=translucent, designed=False,
                bbox=[int(stats[label, cv2.CC_STAT_LEFT]), int(stats[label, cv2.CC_STAT_TOP]),
                      int(stats[label, cv2.CC_STAT_WIDTH]), int(stats[label, cv2.CC_STAT_HEIGHT])],
            ))
    return result, regions


def _holes_overlay(arr: np.ndarray, regions: List[Dict[str, Any]], target: Path) -> None:
    """Saves a red-box overlay marking every detected hole (visual review)."""
    image = Image.fromarray(arr).convert("RGBA")
    canvas = Image.new("RGBA", image.size, (255, 255, 255, 255))
    canvas.alpha_composite(image)
    draw = ImageDraw.Draw(canvas)
    for region in regions:
        left, top, width, height = region["bbox"]
        draw.rectangle((left, top, left + width, top + height), outline=(255, 0, 0, 255), width=2)
        draw.text((left + 3, top + 3), str(region["id"]), fill=(255, 0, 0, 255))
    canvas.convert("RGB").save(target)


def alpha_qa_report(image: Image.Image, overlay_path: Optional[Path] = None) -> Dict[str, Any]:
    """Runs every gate on a PIL image and returns the verdict record.

    Status is PASS (no issue) or FAIL (at least one issue); the upstream
    needs_review state only exists for the LLM hole judge, which is not
    ported. With `overlay_path`, enclosed regions are marked for review.
    """
    arr, _ = clear_haze(np.array(image.convert("RGBA")))
    alpha = arr[..., 3]
    visible = alpha > NEAR_ZERO_ALPHA
    frame = np.zeros(alpha.shape, bool)
    frame[:2] = True
    frame[-2:] = True
    frame[:, :2] = True
    frame[:, -2:] = True
    fake = checkerboard(arr)
    fraction = float(np.mean(alpha <= NEAR_ZERO_ALPHA))
    clear_border = float(np.mean(alpha[frame] <= NEAR_ZERO_ALPHA))
    count, _, stats, _ = cv2.connectedComponentsWithStats(visible.astype("uint8"), 8)
    areas = stats[1:, cv2.CC_STAT_AREA]
    largest = int(areas.max()) if len(areas) else 0
    specks = (int(areas.sum()) - largest) / max(largest, 1)
    nearest, distance = nearest_opaque(arr)
    semi = (alpha > 0) & (alpha < 250)
    halo_good = None
    if nearest is not None and semi.any():
        edge = semi & (distance <= 5)
        if edge.any():
            halo_good = float(np.mean(_delta_e(_lab(arr[..., :3]), _lab(nearest))[edge] <= HALO_DELTA_E_MAX))
    center = (alpha >= 128).astype("uint8")
    outer = cv2.dilate(center, np.ones((7, 7), np.uint8)).astype(bool) & ~center.astype(bool)
    luma = arr[..., :3] @ np.array([0.2126, 0.7152, 0.0722]) * (alpha / 255)
    black_outer = float(luma[outer].mean()) if outer.any() else 0.0
    _, regions = enclosed_regions(alpha)
    holes = sum(region["area"] for region in regions)
    hole_ratio = holes / max(largest, 1)
    issues = []
    if fake:
        issues.append("fake_transparency")
    if not 0.15 <= fraction <= 0.90:
        issues.append("transparent_fraction")
    if clear_border < 0.99:
        issues.append("clipped_border")
    if specks > 0.001:
        issues.append("isolated_specks")
    if hole_ratio > 0.005:
        issues.append("interior_holes")
    if (halo_good is not None and halo_good < 0.95) or black_outer > 8:
        issues.append("halo")
    if overlay_path is not None and regions:
        _holes_overlay(arr, regions, Path(overlay_path))
    return dict(
        status="PASS" if not issues else "FAIL",
        issues=issues,
        fake_transparency=fake,
        transparent_fraction=fraction,
        clear_border_fraction=clear_border,
        speck_ratio=specks,
        interior_hole_ratio=hole_ratio,
        hole_regions=regions,
        halo_good_fraction=halo_good,
        black_outer_luma=black_outer,
        fractional_alpha_pixels=int(np.sum((alpha > 0) & (alpha < 255))),
        near_zero_alpha=NEAR_ZERO_ALPHA,
    )
