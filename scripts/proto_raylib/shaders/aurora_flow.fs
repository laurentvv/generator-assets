#version 330
// Preset 2 - animated aurora curtains, teal -> emerald -> violet, flowing upward.
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
    for (int i = 0; i < 4; i++) {
        v += a * vnoise(p);
        p = p * 2.1 + vec2(11.7, 5.3);
        a *= 0.5;
    }
    return v;
}

void main() {
    // y-up convention: uv.y = 0 at image bottom, 1 at top
    vec2 uv = vec2(fragTexCoord.x, 1.0 - fragTexCoord.y);
    float t = uTime * 0.25;

    // night-sky backdrop
    vec3 col = mix(vec3(0.010, 0.040, 0.055), vec3(0.004, 0.010, 0.030), uv.y);

    // three curtains, each a wavy fbm band with soft vertical falloff
    for (int k = 0; k < 3; k++) {
        float fk = float(k);
        float x = uv.x * (2.5 + 0.7 * fk) + fbm(vec2(uv.x * 3.0 + fk * 7.0, t * 0.35 + fk)) * 1.4;
        float wave = 0.58 + 0.16 * sin(x * 3.1 + t * (0.6 + 0.23 * fk)) + 0.10 * sin(x * 7.7 - t * 0.9);
        float band = exp(-pow((uv.y - wave) * 5.5, 2.0));
        float streak = fbm(vec2(uv.x * 9.0, uv.y * 2.0 - t * (0.5 + 0.15 * fk)));
        float glow = band * (0.35 + 0.65 * streak);

        vec3 c1 = vec3(0.05, 0.85, 0.60);   // emerald
        vec3 c2 = vec3(0.15, 0.95, 0.85);   // teal
        vec3 c3 = vec3(0.55, 0.40, 0.95);   // violet
        vec3 curtain = mix(mix(c1, c2, streak), c3, smoothstep(0.35, 0.9, uv.y - wave + 0.15));
        col += curtain * glow * (0.55 - 0.12 * fk);
    }

    // stars, slightly stronger away from the glow near the horizon
    float star = step(0.9988, hash(floor(uv * uRes / 2.0)));
    col += star * 0.55;

    finalColor = vec4(col, 1.0);
}
