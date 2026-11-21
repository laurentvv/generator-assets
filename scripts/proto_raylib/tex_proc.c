// LEG 1 - CPU procedural textures via raylib GenImage* + ImageDraw* (no GPU).
// Deterministic: fixed offsets/scales, no clock or RNG input from the caller.
// Outputs PNGs into output/test_raylib/textures/ and prints per-recipe timings.
#include "raylib.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>

#define OUT_DIR "output/test_raylib/textures"

typedef struct {
    int count;
    Color stops[6];
} Palette;

// ---------- palette LUT ----------
static void palette_lut(const Palette *p, Color lut[256]) {
    int segs = p->count - 1;
    for (int i = 0; i < 256; i++) {
        float t = i / 255.0f * segs;
        int s = (int)t;
        if (s >= segs) s = segs - 1;
        float f = t - s;
        Color a = p->stops[s], b = p->stops[s + 1];
        lut[i].r = (unsigned char)(a.r + (b.r - a.r) * f);
        lut[i].g = (unsigned char)(a.g + (b.g - a.g) * f);
        lut[i].b = (unsigned char)(a.b + (b.b - a.b) * f);
        lut[i].a = 255;
    }
}

// Remap grayscale source through palette LUT into a fresh image.
static Image remap_gray(Image gray, const Color lut[256]) {
    int w = gray.width, h = gray.height;
    Color *src = LoadImageColors(gray);
    Image out = GenImageColor(w, h, BLACK);
    for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++) {
            Color c = src[y * w + x];
            int lum = (c.r * 299 + c.g * 587 + c.b * 114) / 1000;
            ImageDrawPixel(&out, x, y, lut[lum]);
        }
    UnloadImageColors(src);
    return out;
}

// Multiply img by a radial white->black falloff (vignette).
static void apply_vignette(Image *img, float strength) {
    int w = img->width, h = img->height;
    Color *px = LoadImageColors(*img);
    float cx = w * 0.5f, cy = h * 0.5f, maxd = cx;
    for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++) {
            float dx = (x - cx) / maxd, dy = (y - cy) / maxd;
            float d = sqrtf(dx * dx + dy * dy);
            float v = 1.0f - strength * d * d;
            if (v < 0) v = 0;
            Color c = px[y * w + x];
            ImageDrawPixel(img, x, y,
                (Color){ (unsigned char)(c.r * v), (unsigned char)(c.g * v),
                         (unsigned char)(c.b * v), 255 });
        }
    UnloadImageColors(px);
}

// Sparse starfield: threshold white noise, keep point-ish, tint slightly.
static void draw_stars(Image *img, float factor, Color tint, unsigned char min_lum) {
    Image noise = GenImageWhiteNoise(img->width, img->height, factor);
    Color *n = LoadImageColors(noise);
    for (int y = 0; y < img->height; y++)
        for (int x = 0; x < img->width; x++) {
            Color c = n[y * img->width + x];
            int lum = (c.r + c.g + c.b) / 3;
            if (lum >= min_lum) {
                ImageDrawPixel(img, x, y,
                    (Color){ (unsigned char)(tint.r), (unsigned char)(tint.g),
                             (unsigned char)(tint.b), 255 });
            }
        }
    UnloadImageColors(n);
    UnloadImage(noise);
}

// 3x3 gaussian via raylib kernel convolution (smooths perlin blockiness).
static void smooth(Image *img) {
    float kernel[9] = { 1, 2, 1, 2, 4, 2, 1, 2, 1 };
    for (int i = 0; i < 9; i++) kernel[i] /= 16.0f;
    ImageKernelConvolution(img, kernel, 3);
}

// ---------- palettes (ai-doc2video tech aesthetic) ----------
static const Palette PAL_DEEPSPACE = { 4, { { 5, 5, 16, 255 }, { 26, 43, 109, 255 },
                                            { 79, 216, 232, 255 }, { 245, 250, 255, 255 } } };
static const Palette PAL_NEON      = { 4, { { 10, 10, 18, 255 }, { 45, 27, 78, 255 },
                                            { 0, 229, 255, 255 }, { 210, 255, 255, 255 } } };
static const Palette PAL_AURORA    = { 5, { { 4, 16, 20, 255 }, { 9, 96, 84, 255 },
                                            { 56, 224, 168, 255 }, { 170, 140, 255, 255 },
                                            { 240, 255, 250, 255 } } };
static const Palette PAL_EMBER     = { 4, { { 12, 10, 14, 255 }, { 70, 30, 24, 255 },
                                            { 232, 104, 32, 255 }, { 255, 224, 180, 255 } } };

// ---------- recipes (sf = resolution scale factor, 1.0 at 1920 wide) ----------

static Image recipe_deepspace_nebula(int w, int h, float sf) {
    Color lut[256]; palette_lut(&PAL_DEEPSPACE, lut);
    Image perlin = GenImagePerlinNoise(w, h, 0, 0, 9.0f * sf);
    smooth(&perlin);
    Image out = remap_gray(perlin, lut);
    draw_stars(&out, 0.0009f, (Color){ 255, 255, 255, 255 }, 250);
    draw_stars(&out, 0.0003f, (Color){ 180, 220, 255, 255 }, 250);
    apply_vignette(&out, 0.55f);
    UnloadImage(perlin);
    return out;
}

static Image recipe_neon_cellular(int w, int h, float sf) {
    Color lut[256]; palette_lut(&PAL_NEON, lut);
    Image cells = GenImageCellular(w, h, (int)(130 * sf));
    Image out = remap_gray(cells, lut);
    // subtle horizontal scanlines for a CRT-tech feel (deterministic stride)
    for (int y = 0; y < h; y += 4)
        for (int x = 0; x < w; x++)
            ImageDrawPixel(&out, x, y, (Color){ 8, 8, 14, 255 });
    apply_vignette(&out, 0.7f);
    UnloadImage(cells);
    return out;
}

static Image recipe_aurora_wash(int w, int h, float sf) {
    Color lut[256]; palette_lut(&PAL_AURORA, lut);
    Image a = GenImagePerlinNoise(w, h, 0, 0, 22.0f * sf);
    Image b = GenImagePerlinNoise(w, h, 40, 40, 6.0f * sf);
    // average the two octaves manually through the LUT
    Color *ca = LoadImageColors(a);
    Color *cb = LoadImageColors(b);
    Image out = GenImageColor(w, h, BLACK);
    for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++) {
            Color pa = ca[y * w + x], pb = cb[y * w + x];
            int lum = (int)(((pa.r + pa.g + pa.b) / 3 + (pb.r + pb.g + pb.b) / 6) * 0.62f);
            if (lum > 255) lum = 255;
            ImageDrawPixel(&out, x, y, lut[lum]);
        }
    UnloadImageColors(ca); UnloadImageColors(cb);
    UnloadImage(a); UnloadImage(b);
    apply_vignette(&out, 0.45f);
    return out;
}

static Image recipe_ember_storm(int w, int h, float sf) {
    Color lut[256]; palette_lut(&PAL_EMBER, lut);
    Image perlin = GenImagePerlinNoise(w, h, 64, 96, 4.5f * sf);
    Image out = remap_gray(perlin, lut);
    apply_vignette(&out, 0.6f);
    UnloadImage(perlin);
    return out;
}

// Composite showcase: gradient sky + planet (ImageDrawCircleGradient) + rim
// glow + stars + faint nebula band -- exercises the v6.2 ImageDraw API.
static Image recipe_orbital_composite(int w, int h, float sf) {
    Image out = GenImageGradientRadial(w, h, 0.35f, (Color){ 10, 14, 42, 255 },
                                                  (Color){ 2, 2, 8, 255 });
    // faint nebula band
    Image neb = GenImagePerlinNoise(w, h, 7, 13, 14.0f * sf);
    smooth(&neb);
    Color *cn = LoadImageColors(neb);
    for (int y = 0; y < h; y++)
        for (int x = 0; x < w; x++) {
            Color n = cn[y * w + x];
            int lum = (n.r + n.g + n.b) / 3;
            int band = 255 - abs(y - (int)(h * 0.42f)) * 255 / (int)(h * 0.35f);
            if (band < 0) band = 0;
            int k = lum * band / 255 / 4;  // keep it subtle
            if (k > 4) ImageDrawPixel(&out, x, y, (Color){ 14 + k / 3, 20 + 2 * k / 3, 44 + k, 255 });
        }
    UnloadImageColors(cn); UnloadImage(neb);

    draw_stars(&out, 0.0012f, (Color){ 230, 240, 255, 255 }, 250);
    draw_stars(&out, 0.0004f, (Color){ 150, 200, 255, 255 }, 250);

    // planet: single radial gradient (lit upper-left -> deep shade lower-right)
    // reads as a shaded sphere; atmospheric rim halo behind it
    Vector2 center = { w * 0.68f, h * 0.40f };
    float radius = h * 0.24f;
    ImageDrawCircle(&out, (int)center.x, (int)center.y, (int)(radius * 1.16f), (Color){ 60, 140, 220, 60 });
    ImageDrawCircle(&out, (int)center.x, (int)center.y, (int)(radius * 1.07f), (Color){ 90, 180, 255, 90 });
    ImageDrawCircleGradient(&out, center, radius, (Color){ 200, 225, 255, 255 },
                                           (Color){ 10, 18, 52, 255 });
    return out;
}

// ---------- runner ----------
typedef struct {
    const char *name;
    Image (*fn)(int, int, float);
} Recipe;

int main(void) {
    Recipe recipes[] = {
        { "tex01_deepspace_nebula", recipe_deepspace_nebula },
        { "tex02_neon_cellular",    recipe_neon_cellular },
        { "tex03_aurora_wash",      recipe_aurora_wash },
        { "tex04_ember_storm",      recipe_ember_storm },
        { "tex05_orbital_composite", recipe_orbital_composite },
    };
    int n = (int)(sizeof(recipes) / sizeof(recipes[0]));
    char path[512];
    int ok = 0;

    struct { int w, h; } sizes[] = { { 1920, 1080 }, { 1920, 1080 }, { 1920, 1080 },
                                     { 1920, 1080 }, { 1920, 1080 } };
    for (int i = 0; i < n; i++) {
        float sf = sizes[i].w / 1920.0f;
        clock_t t0 = clock();
        Image img = recipes[i].fn(sizes[i].w, sizes[i].h, sf);
        double ms = (double)(clock() - t0) * 1000.0 / CLOCKS_PER_SEC;
        snprintf(path, sizeof(path), "%s/%s_%dx%d.png", OUT_DIR,
                 recipes[i].name, sizes[i].w, sizes[i].h);
        bool exported = ExportImage(img, path);
        printf("TEX: %s %dx%d %.0f ms export=%d\n", recipes[i].name,
               sizes[i].w, sizes[i].h, ms, exported);
        if (exported) ok++;
        UnloadImage(img);
    }

    // heroes at 4K (feature sizes scale with sf)
    struct { const char *name; Image (*fn)(int, int, float); } heroes[] = {
        { "texH1_deepspace_nebula", recipe_deepspace_nebula },
        { "texH2_orbital_composite", recipe_orbital_composite },
    };
    for (int i = 0; i < 2; i++) {
        clock_t t0 = clock();
        Image img = heroes[i].fn(3840, 2160, 2.0f);
        double ms = (double)(clock() - t0) * 1000.0 / CLOCKS_PER_SEC;
        snprintf(path, sizeof(path), "%s/%s_3840x2160.png", OUT_DIR, heroes[i].name);
        bool exported = ExportImage(img, path);
        printf("TEX: %s 3840x2160 %.0f ms export=%d\n", heroes[i].name, ms, exported);
        if (exported) ok++;
        UnloadImage(img);
    }

    printf("TEX DONE: %d/7 exported\n", ok);
    return ok == 7 ? 0 : 1;
}
