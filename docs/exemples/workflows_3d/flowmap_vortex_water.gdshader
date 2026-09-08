shader_type spatial;
// Shader de flux d'eau / lave animé avec Flowmap (Double sampling déphasé)
// Généré automatiquement par Generator Assets pour Godot 4

uniform sampler2D albedo_texture : source_color, filter_linear_mipmap, repeat_enable;
uniform sampler2D flowmap_texture : hint_default_black, filter_linear_mipmap, repeat_enable;
uniform vec4 tint_color : source_color = vec4(0.2, 0.5, 0.9, 0.9);
uniform float flow_speed : hint_range(0.0, 2.0) = 0.4;
uniform float flow_strength : hint_range(0.0, 1.0) = 0.15;

void fragment() {
    vec2 flow = texture(flowmap_texture, UV).rg * 2.0 - vec2(1.0);
    float time = TIME * flow_speed;

    // Deux échantillons déphasés de 0.5 cycle pour une boucle continue sans raccord visible
    float phase0 = fract(time);
    float phase1 = fract(time + 0.5);

    vec2 uv0 = UV + flow * phase0 * flow_strength;
    vec2 uv1 = UV + flow * phase1 * flow_strength;

    vec4 col0 = texture(albedo_texture, uv0);
    vec4 col1 = texture(albedo_texture, uv1);

    float blend_weight = abs(0.5 - phase0) / 0.5;
    vec4 final_color = mix(col0, col1, blend_weight) * tint_color;

    ALBEDO = final_color.rgb; ALPHA = final_color.a; ROUGHNESS = 0.05; METALLIC = 0.0;
}
