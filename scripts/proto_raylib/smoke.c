// Smoke test for the raylib test campaign: hidden window, offscreen
// RenderTexture, deterministic gradient + circle, export to PNG.
// Exit 0 = PNG written; exit 1 = export failed.
#include "raylib.h"
#include <stdio.h>

int main(void) {
    SetConfigFlags(FLAG_WINDOW_HIDDEN | FLAG_MSAA_4X_HINT);
    InitWindow(64, 64, "raylib smoke (hidden)");

    RenderTexture2D target = LoadRenderTexture(640, 360);
    BeginTextureMode(target);
        ClearBackground(RAYWHITE);
        for (int i = 0; i < 640; i++) {
            Color c = { (unsigned char)(i * 255 / 639), 40,
                        (unsigned char)(255 - i * 255 / 639), 255 };
            DrawRectangle(i, 0, 1, 360, c);
        }
        DrawCircle(320, 180, 80, (Color){ 255, 200, 40, 255 });
        DrawText("raylib 6.2 smoke", 236, 168, 20, BLACK);
    EndTextureMode();

    Image img = LoadImageFromTexture(target.texture);
    ImageFlipVertical(&img);  // RenderTextures are vertically flipped (OpenGL)
    bool ok = ExportImage(img, "output/test_raylib/smoke.png");
    printf("SMOKE: version=%s export=%d\n", RAYLIB_VERSION, ok);

    UnloadImage(img);
    UnloadRenderTexture(target);
    CloseWindow();
    return ok ? 0 : 1;
}
