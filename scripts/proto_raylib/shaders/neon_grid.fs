#version 330
// Preset 3 - dark-tech neon perspective grid scrolling toward the viewer,
// cyan lines on near-black, horizon glow, starfield above. ai-doc2video vibe.
// Deterministic: pure function of uTime and fragTexCoord.
in vec2 fragTexCoord;
uniform float uTime;
uniform vec2 uRes;
out vec4 finalColor;

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

void main() {
    // y-up convention: uv.y = 0 at image bottom, 1 at top -> floor below horizon
    vec2 uv = vec2(fragTexCoord.x, 1.0 - fragTexCoord.y);
    float t = uTime * 0.6;
    vec3 col = vec3(0.012, 0.014, 0.030);

    float horizon = 0.44;
    if (uv.y < horizon) {
        // perspective floor: depth from screen y, x spread grows with depth
        float d = 1.0 / (horizon - uv.y + 0.02);      // 0.02 avoids pole blowup
        float z = d * 0.55 + t;                        // scroll toward viewer
        float lane = uv.x - 0.5 + (uv.x - 0.5) * (d - 1.0) * 0.35;
        float gx = abs(fract(lane * 6.0) - 0.5);
        float gz = abs(fract(z) - 0.5);
        float lx = smoothstep(0.46, 0.50, 1.0 - gx * 2.0);   // near 1 at line center
        float lz = smoothstep(0.40, 0.50, 1.0 - gz * 2.0);

        float fog = exp(-(horizon - uv.y) * 9.0);      // fade lines near horizon
        float glow = 0.035 / (abs(gx) + 0.035) + 0.035 / (abs(gz) + 0.035);
        vec3 neon = vec3(0.0, 0.90, 1.0);
        col += neon * (lx * 0.55 + lz * 0.55 + glow * 0.10) * fog;
    } else {
        // above horizon: subtle stars + thin scan shimmer
        float star = step(0.9982, hash(floor(uv * uRes / 2.0)));
        col += star * 0.7;
    }

    // horizon line glow band
    float hb = exp(-abs(uv.y - horizon) * 55.0);
    col += vec3(0.0, 0.75, 0.9) * hb * 0.8;

    // vignette
    vec2 dd = uv - 0.5;
    col *= 1.0 - 0.5 * dot(dd, dd) * 2.0;

    finalColor = vec4(col, 1.0);
}
