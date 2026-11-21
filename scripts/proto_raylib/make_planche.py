"""Build the comparative contact sheet for the raylib test campaign.

Tiles: leg 1 CPU textures (5), leg 2 shader posters (3), leg 3 turntable
posters (2) + hero stills row. Output: output/test_raylib/planche_raylib.png
"""
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "output", "test_raylib")
TILE_W, TILE_H, LABEL_H = 640, 360, 34

ROWS = [
    ("LEG 1 - CPU procedural textures (GenImage*, 1920x1080)", [
        ("tex01_deepspace_nebula", os.path.join(OUT, "textures", "tex01_deepspace_nebula_1920x1080.png")),
        ("tex02_neon_cellular", os.path.join(OUT, "textures", "tex02_neon_cellular_1920x1080.png")),
        ("tex03_aurora_wash", os.path.join(OUT, "textures", "tex03_aurora_wash_1920x1080.png")),
        ("tex04_ember_storm", os.path.join(OUT, "textures", "tex04_ember_storm_1920x1080.png")),
        ("tex05_orbital_composite", os.path.join(OUT, "textures", "tex05_orbital_composite_1920x1080.png")),
    ]),
    ("LEG 2 - GPU shader backgrounds (MP4 8s poster + 4K hero)", [
        ("nebula_fbm", os.path.join(OUT, "fonds", "nebula_fbm_poster.png")),
        ("aurora_flow", os.path.join(OUT, "fonds", "aurora_flow_poster.png")),
        ("neon_grid", os.path.join(OUT, "fonds", "neon_grid_poster.png")),
        ("nebula hero 4K", os.path.join(OUT, "fonds", "nebula_fbm_hero_3840x2160.png")),
        ("aurora hero 4K", os.path.join(OUT, "fonds", "aurora_flow_hero_3840x2160.png")),
    ]),
    ("LEG 3 - Blender/TRELLIS GLB -> raylib turntable (poster + 4K beauty)", [
        ("gem (Blender 5.3)", os.path.join(OUT, "turntable", "gem_poster.png")),
        ("crate (TRELLIS.2)", os.path.join(OUT, "turntable", "crate_trellis_poster.png")),
        ("gem beauty 4K", os.path.join(OUT, "turntable", "gem", "beauty01_3840x2160.png")),
        ("crate beauty 4K", os.path.join(OUT, "turntable", "crate_trellis", "beauty01_3840x2160.png")),
    ]),
]


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for cand in (r"C:\Windows\Fonts\consola.ttf", r"C:\Windows\Fonts\arial.ttf"):
        if os.path.exists(cand):
            return ImageFont.truetype(cand, size)
    return ImageFont.load_default()


def main() -> int:
    header_h = 56
    rows = [(title, [(label, p) for label, p in tiles if os.path.exists(p)]) for title, tiles in ROWS]
    max_cols = max(len(tiles) for _, tiles in rows)
    W = max_cols * TILE_W
    H = header_h + sum(LABEL_H + TILE_H for _, _ in rows)
    sheet = Image.new("RGB", (W, H), (12, 13, 20))
    draw = ImageDraw.Draw(sheet)
    font_t = load_font(26)
    font_l = load_font(20)

    draw.text((16, 14), "raylib 6.2 + Blender test campaign - generator-assets (ai-doc2video priority)",
              fill=(240, 244, 255), font=font_t)
    y = header_h
    for title, tiles in rows:
        draw.text((16, y + 6), title, fill=(120, 210, 255), font=font_t)
        y += LABEL_H
        for i, (label, path) in enumerate(tiles):
            x = i * TILE_W
            img = Image.open(path).convert("RGB").resize((TILE_W - 8, TILE_H - 8))
            sheet.paste(img, (x + 4, y + 4))
            draw.text((x + 10, y + TILE_H - 2), label, fill=(210, 215, 230), font=font_l)
        y += TILE_H
    dest = os.path.join(OUT, "planche_raylib_v2.png")
    sheet.save(dest)
    print(f"PLANCHE: {dest} ({os.path.getsize(dest)} bytes, {W}x{H})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
