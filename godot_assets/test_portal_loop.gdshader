shader_type spatial;
render_mode blend_mix, unshaded, cull_disabled;

uniform sampler2D albedo_texture : source_color, repeat_enable, filter_linear_mipmap;
uniform vec2 scroll_speed = vec2(0.0, 0.25);
uniform float loop_frequency = 1.0;
uniform vec4 tint_color : source_color = vec4(1.0, 1.0, 1.0, 1.0);

void fragment() {
	float t1 = fract(TIME * loop_frequency);
	float t2 = fract(TIME * loop_frequency + 0.5);

	vec2 uv1 = UV + scroll_speed * t1;
	vec2 uv2 = UV + scroll_speed * t2;

	vec4 tex1 = texture(albedo_texture, uv1);
	vec4 tex2 = texture(albedo_texture, uv2);

	// Fondu croisé triangulaire entre les 2 échantillons déphasés
	float weight = abs((t1 - 0.5) * 2.0);
	vec4 final_color = mix(tex2, tex1, weight) * tint_color;

	ALBEDO = final_color.rgb; ALPHA = final_color.a;
}
