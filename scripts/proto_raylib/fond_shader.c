// LEG 2 - GPU shader backgrounds rendered fully offscreen (hidden window).
// For each preset: 240 frames at 1920x1080/30fps exported as PNGs, plus one
// 3840x2160 hero still at t=4.0s. Time comes from the frame index (t = f/30),
// never from the wall clock -> bit-reproducible renders.
// Modes:
//   fond_shader.exe            full campaign (3 presets)
//   fond_shader.exe --repro    re-render preset 0 frames 0-2 into fonds_repro/
#include "raylib.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <direct.h>
#include <time.h>

// Portable recursive mkdir (single-level segments, forward or back slashes).
static void mkdirs(const char *path) {
    char buf[512];
    snprintf(buf, sizeof(buf), "%s", path);
    for (char *p = buf + (buf[1] == ':' ? 3 : 0); *p; p++) {
        if (*p == '/' || *p == '\\') {
            *p = '\0';
            _mkdir(buf);
            *p = '/';
        }
    }
    _mkdir(buf);
}

#define SHADER_DIR "scripts/proto_raylib/shaders"
#define OUT_ROOT "output/test_raylib/fonds"
#define FPS 30
#define FRAMES 240

static const char *PRESETS[] = { "nebula_fbm", "aurora_flow", "neon_grid" };
static const int N_PRESETS = 3;

// Render frames [f0, f1) of one preset at WxH into dir/<name>/f_%04d.png
static bool render_frames(const char *name, int W, int H, int f0, int f1,
                          const char *root, bool hero_still) {
    char fs_path[512], dir[512], path[512];
    snprintf(fs_path, sizeof(fs_path), "%s/%s.fs", SHADER_DIR, name);

    Shader sh = LoadShader(NULL, fs_path);
    if (sh.id == 0) { printf("FOND: %s shader compile FAILED\n", name); return false; }
    int locT = GetShaderLocation(sh, "uTime");
    int locR = GetShaderLocation(sh, "uRes");

    RenderTexture2D target = LoadRenderTexture(W, H);
    Texture2D white = LoadTextureFromImage(GenImageColor(1, 1, WHITE));

    snprintf(dir, sizeof(dir), "%s/%s", root, name);
    mkdirs(dir);

    clock_t t0 = clock();
    int exported = 0, total = f1 - f0 + (hero_still ? 1 : 0);

    for (int f = f0; f < f1; f++) {
        float t = (float)f / FPS;
        BeginTextureMode(target);
            BeginShaderMode(sh);
                SetShaderValue(sh, locT, &t, SHADER_UNIFORM_FLOAT);
                Vector2 res = { (float)W, (float)H };
                SetShaderValue(sh, locR, &res, SHADER_UNIFORM_VEC2);
                DrawTexturePro(white, (Rectangle){ 0, 0, 1, 1 },
                               (Rectangle){ 0, 0, (float)W, (float)H },
                               (Vector2){ 0, 0 }, 0.0f, WHITE);
            EndShaderMode();
        EndTextureMode();

        Image img = LoadImageFromTexture(target.texture);
        ImageFlipVertical(&img);
        snprintf(path, sizeof(path), "%s/f_%04d.png", dir, f);
        exported += ExportImage(img, path) ? 1 : 0;
        UnloadImage(img);
    }

    if (hero_still) {
        // 4K hero still on its own render target, t = 4.0s
        RenderTexture2D hero = LoadRenderTexture(3840, 2160);
        float t = 4.0f;
        BeginTextureMode(hero);
            BeginShaderMode(sh);
                SetShaderValue(sh, locT, &t, SHADER_UNIFORM_FLOAT);
                Vector2 res = { 3840.0f, 2160.0f };
                SetShaderValue(sh, locR, &res, SHADER_UNIFORM_VEC2);
                DrawTexturePro(white, (Rectangle){ 0, 0, 1, 1 },
                               (Rectangle){ 0, 0, 3840.0f, 2160.0f },
                               (Vector2){ 0, 0 }, 0.0f, WHITE);
            EndShaderMode();
        EndTextureMode();
        Image img = LoadImageFromTexture(hero.texture);
        ImageFlipVertical(&img);
        snprintf(path, sizeof(path), "%s/%s_hero_3840x2160.png", OUT_ROOT, name);
        exported += ExportImage(img, path) ? 1 : 0;
        UnloadImage(img);
        UnloadRenderTexture(hero);
    }

    double ms = (double)(clock() - t0) * 1000.0 / CLOCKS_PER_SEC;
    printf("FOND: %s %dx%d frames=%d %.0f ms total (%.1f ms/frame) exported=%d/%d\n",
           name, W, H, f1 - f0, ms, ms / (f1 - f0), exported, total);

    UnloadTexture(white);
    UnloadRenderTexture(target);
    UnloadShader(sh);
    return exported == total;
}

int main(int argc, char **argv) {
    bool repro = (argc > 1 && strcmp(argv[1], "--repro") == 0);
    SetConfigFlags(FLAG_WINDOW_HIDDEN | FLAG_MSAA_4X_HINT);
    InitWindow(64, 64, "raylib fond shader (hidden)");

    int ok = 0;
    if (repro) {
        if (render_frames(PRESETS[0], 1920, 1080, 0, 3, OUT_ROOT "/../fonds_repro", false)) ok = 1;
    } else {
        for (int i = 0; i < N_PRESETS; i++)
            ok += render_frames(PRESETS[i], 1920, 1080, 0, FRAMES, OUT_ROOT, true);
        printf("FOND DONE: %d/3 presets fully exported\n", ok);
    }

    CloseWindow();
    return (repro ? ok == 1 : ok == N_PRESETS) ? 0 : 1;
}
