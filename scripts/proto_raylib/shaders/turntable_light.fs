#version 330
// Turntable fragment shader - 3 point lights, blinn-phong + fresnel rim,
// albedo from texture0 * colDiffuse (both supplied by rlgl), soft tone map.
in vec3 fragPosition;
in vec3 fragNormal;
in vec2 fragTexCoord;

uniform sampler2D texture0;
uniform vec4 colDiffuse;

uniform vec3 viewPos;
uniform vec3 lightPos[3];
uniform vec3 lightColor[3];
uniform vec3 rimColor;

out vec4 finalColor;

void main() {
    vec4 texel = texture(texture0, fragTexCoord) * colDiffuse;
    vec3 N = normalize(fragNormal);
    vec3 V = normalize(viewPos - fragPosition);

    vec3 total = vec3(0.035, 0.040, 0.055);  // ambient
    for (int i = 0; i < 3; i++) {
        vec3 L = lightPos[i] - fragPosition;
        float dist = length(L);
        L /= dist;
        float atten = 1.0 / (1.0 + 0.05 * dist + 0.015 * dist * dist);
        float diff = max(dot(N, L), 0.0);
        vec3 H = normalize(L + V);
        float spec = pow(max(dot(N, H), 0.0), 48.0);
        total += lightColor[i] * atten * (diff + 0.65 * spec);
    }

    float rim = pow(1.0 - max(dot(N, V), 0.0), 3.0);
    vec3 col = texel.rgb * total + rimColor * rim * 0.55;

    // soft roll-off so key-light highlights do not clip to flat white
    col = col / (col + vec3(0.65)) * 1.55;

    finalColor = vec4(col, texel.a);
}
