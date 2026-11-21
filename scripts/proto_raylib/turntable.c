// LEG 3 - orbit turntable renderer for GLB models (Blender- or TRELLIS-made).
// Custom 3-point-light shader + fresnel rim + soft tone map, SSAA 2x
// (3840x2160 FBO downscaled to 1080p per frame), deterministic camera
// (angle = frame index / total * 2*PI), beauty stills at 4K.
// Usage: turntable.exe <model.glb> <out_dir> [frames]
#include "raylib.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <direct.h>
#include <math.h>
#include <time.h>

#define SHADER_DIR "scripts/proto_raylib/shaders"
#define SS_W 3840
#define SS_H 2160
#define OUT_W 1920
#define OUT_H 1080
#define FPS 30

static void mkdirs(const char *path) {
    char buf[512];
    snprintf(buf, sizeof(buf), "%s", path);
    for (char *p = buf + (buf[1] == ':' ? 3 : 0); *p; p++) {
        if (*p == '/' || *p == '\\') { *p = '\0'; _mkdir(buf); *p = '/'; }
    }
    _mkdir(buf);
}

static void draw_scene(Model model, Model pool, Shader sh, Camera3D cam,
                       Vector3 center, float radius, Vector3 light_pos[3],
                       Vector3 light_col[3], Vector3 rim) {
    // uniforms must be set BEFORE the draws that use them
    Vector3 vp = cam.position;
    SetShaderValue(sh, GetShaderLocation(sh, "viewPos"), &vp, SHADER_UNIFORM_VEC3);
    SetShaderValueV(sh, GetShaderLocation(sh, "lightPos"), light_pos, SHADER_UNIFORM_VEC3, 3);
    SetShaderValueV(sh, GetShaderLocation(sh, "lightColor"), light_col, SHADER_UNIFORM_VEC3, 3);
    SetShaderValue(sh, GetShaderLocation(sh, "rimColor"), &rim, SHADER_UNIFORM_VEC3);

    BeginMode3D(cam);
        // soft glow pool under the model (unlit default-shader billboard)
        DrawModelEx(pool, (Vector3){ center.x, center.y - radius * 1.32f, center.z },
                    (Vector3){ 1, 0, 0 }, -90.0f,
                    (Vector3){ radius * 2.6f, radius * 2.6f, 1.0f }, WHITE);
        DrawModel(model, (Vector3){ 0, 0, 0 }, 1.0f, WHITE);
    EndMode3D();
}

int main(int argc, char **argv) {
    if (argc < 3) {
        printf("usage: turntable.exe <model.glb> <out_dir> [frames]\n");
        return 2;
    }
    const char *model_path = argv[1];
    const char *out_dir = argv[2];
    int frames = (argc > 3) ? atoi(argv[3]) : 240;

    SetConfigFlags(FLAG_WINDOW_HIDDEN | FLAG_MSAA_4X_HINT);
    InitWindow(64, 64, "raylib turntable (hidden)");

    Model model = LoadModel(model_path);
    if (model.meshCount == 0) { printf("TURNTABLE: model load FAILED %s\n", model_path); return 1; }
    BoundingBox bb = GetModelBoundingBox(model);
    Vector3 center = { (bb.min.x + bb.max.x) / 2, (bb.min.y + bb.max.y) / 2, (bb.min.z + bb.max.z) / 2 };
    float radius = fmaxf(fmaxf(bb.max.x - bb.min.x, bb.max.y - bb.min.y), bb.max.z - bb.min.z) * 0.5f;
    printf("TURNTABLE: %s meshes=%d materials=%d radius=%.3f\n",
           model_path, model.meshCount, model.materialCount, radius);

    // lighting shader on every material (albedo maps still bound by rlgl)
    char vs[512], fs[512];
    snprintf(vs, sizeof(vs), "%s/turntable_light.vs", SHADER_DIR);
    snprintf(fs, sizeof(fs), "%s/turntable_light.fs", SHADER_DIR);
    Shader sh = LoadShader(vs, fs);
    if (sh.id == 0) { printf("TURNTABLE: shader compile FAILED\n"); return 1; }
    for (int i = 0; i < model.materialCount; i++) model.materials[i].shader = sh;

    // materials with no albedo map (Blender color-only mats) would leave
    // texture0 sampling the previously bound texture -> bind a neutral one
    Image white_img = GenImageColor(8, 8, (Color){ 205, 208, 216, 255 });
    Texture2D white_tex = LoadTextureFromImage(white_img);
    UnloadImage(white_img);
    for (int i = 0; i < model.materialCount; i++)
        if (model.materials[i].maps[MATERIAL_MAP_ALBEDO].texture.id == 0)
            SetMaterialTexture(&model.materials[i], MATERIAL_MAP_ALBEDO, white_tex);

    // 3-point lighting, fixed in world space so surfaces light up as the
    // camera orbits (key warm / fill cool / rim cyan)
    Vector3 light_pos[3] = {
        { radius * 1.6f, radius * 2.0f, radius * 1.6f },
        { -radius * 2.2f, radius * 0.9f, -radius * 1.0f },
        { 0.0f, radius * 1.1f, -radius * 2.6f },
    };
    Vector3 light_col[3] = {
        { 1.15f, 1.05f, 0.92f },
        { 0.22f, 0.32f, 0.48f },
        { 0.35f, 0.85f, 1.10f },
    };
    Vector3 rim = { 0.30f, 0.80f, 1.00f };

    // unlit glow pool (radial alpha gradient on a ground-plane quad)
    Image glow_img = GenImageGradientRadial(256, 256, 0.45f,
        (Color){ 60, 190, 255, 150 }, (Color){ 8, 12, 24, 0 });
    Texture2D glow_tex = LoadTextureFromImage(glow_img);
    SetTextureFilter(glow_tex, TEXTURE_FILTER_BILINEAR);
    UnloadImage(glow_img);
    Mesh plane = GenMeshPlane(1.0f, 1.0f, 1, 1);
    Model pool = LoadModelFromMesh(plane);
    pool.materials[0].shader = LoadShader(NULL, NULL);  // rlgl default (unlit)
    SetMaterialTexture(&pool.materials[0], MATERIAL_MAP_ALBEDO, glow_tex);

    RenderTexture2D target = LoadRenderTexture(SS_W, SS_H);
    mkdirs(out_dir);

    clock_t t0 = clock();
    char path[512];
    int exported = 0;

    for (int f = 0; f < frames; f++) {
        float a = (float)f / frames * 2.0f * PI;
        float elev = 22.0f * DEG2RAD;
        float dist = radius * 3.3f;
        Camera3D cam = { 0 };
        cam.position = (Vector3){ center.x + dist * cosf(elev) * cosf(a),
                                  center.y + dist * sinf(elev),
                                  center.z + dist * cosf(elev) * sinf(a) };
        cam.target = center;
        cam.up = (Vector3){ 0.0f, 1.0f, 0.0f };
        cam.fovy = 38.0f;
        cam.projection = CAMERA_PERSPECTIVE;

        BeginTextureMode(target);
            ClearBackground(BLACK);
            DrawRectangleGradientV(0, 0, SS_W, SS_H,
                (Color){ 16, 18, 30, 255 }, (Color){ 5, 6, 10, 255 });
            draw_scene(model, pool, sh, cam, center, radius, light_pos, light_col, rim);
        EndTextureMode();

        Image img = LoadImageFromTexture(target.texture);
        ImageFlipVertical(&img);
        ImageResize(&img, OUT_W, OUT_H);  // SSAA 2x downscale
        snprintf(path, sizeof(path), "%s/f_%04d.png", out_dir, f);
        exported += ExportImage(img, path) ? 1 : 0;
        UnloadImage(img);

        // beauty stills at full 4K (no downscale), frames 0 and 90
        if (f == 0 || f == 90) {
            Image hero = LoadImageFromTexture(target.texture);
            ImageFlipVertical(&hero);
            snprintf(path, sizeof(path), "%s/beauty%02d_3840x2160.png", out_dir, f == 0 ? 1 : 2);
            exported += ExportImage(hero, path) ? 1 : 0;
            UnloadImage(hero);
        }
    }

    double ms = (double)(clock() - t0) * 1000.0 / CLOCKS_PER_SEC;
    int expected = frames + 2;
    printf("TURNTABLE: frames=%d %.0f ms total (%.1f ms/frame) exported=%d/%d\n",
           frames, ms, ms / frames, exported, expected);

    UnloadRenderTexture(target);
    UnloadModel(pool); UnloadTexture(glow_tex);
    UnloadModel(model); UnloadTexture(white_tex); UnloadShader(sh);
    CloseWindow();
    return exported == expected ? 0 : 1;
}
