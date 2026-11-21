#version 330
// Preset 1 - domain-warped fbm nebula, deep blue -> cyan -> white, slow drift.
// Deterministic: color is a pure function of uTime and fragTexCoord.
in vec2 fragTexCoord;
uniform float uTime;
uniform vec2 uRes;
out vec4 finalColor;

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

float vnoise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 5; i++) {
        v += a * vnoise(p);
        p = p * 2.03 + vec2(17.3, 9.1);
        a *= 0.5;
    }
    return v;
}

void main() {
    vec2 uv = fragTexCoord;
    vec2 p = uv * vec2(uRes.x / uRes.y, 1.0) * 3.0;
    float t = uTime * 0.05;

    // two-level domain warp for filament structure
    vec2 q = vec2(fbm(p + t), fbm(p + vec2(5.2, 1.3) - t * 0.7));
    float n = fbm(p + 2.2 * q + vec2(t * 0.4, 0.0));

    vec3 deep = vec3(0.02, 0.02, 0.07);
    vec3 mid  = vec3(0.10, 0.17, 0.45);
    vec3 cyan = vec3(0.31, 0.85, 0.91);
    vec3 hot  = vec3(0.96, 0.98, 1.00);

    vec3 col = mix(deep, mid, smoothstep(0.25, 0.62, n));
    col = mix(col, cyan, smoothstep(0.58, 0.82, n));
    col = mix(col, hot, smoothstep(0.82, 0.97, n) * 0.85);

    // sparse stars (hash threshold, twinkle-free)
    vec2 sp = uv * uRes;
    float star = step(0.9985, hash(floor(sp / 2.0)));
    col += star * 0.8 * (1.0 - n);

    // gentle vignette
    vec2 d = uv - 0.5;
    col *= 1.0 - 0.55 * dot(d, d) * 2.2;

    finalColor = vec4(col, 1.0);
}
