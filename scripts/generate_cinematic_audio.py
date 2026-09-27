"""
generate_cinematic_audio.py
High-fidelity procedural cinematic sound design generator (48 kHz Stereo).
Produces a rich orchestral/cinematic ambience: sub-bass drone, wind gust, harmonic shimmer and impact.
"""
import os
import sys
import numpy as np
from scipy.io import wavfile

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

def create_cinematic_soundtrack(out_wav_path, duration_sec=10.0, sample_rate=48000):
    total_samples = int(duration_sec * sample_rate)
    t = np.linspace(0, duration_sec, total_samples, endpoint=False)

    # 1. Sub-Bass Drone (deep and imposing foundation 48 Hz - 55 Hz)
    f0 = 48.0
    f1 = 54.0
    freq_sweep = np.linspace(f0, f1, total_samples)
    drone = np.sin(2 * np.pi * freq_sweep * t) * 0.35
    # Warm harmonic (octave 96 Hz)
    drone += np.sin(2 * np.pi * freq_sweep * 2 * t) * 0.15
    # Third harmonic (144 Hz)
    drone += np.sin(2 * np.pi * freq_sweep * 3 * t) * 0.05

    # 2. Atmospheric wind gust (modulated pink noise)
    white_noise = np.random.normal(0, 1, total_samples)
    # Simple recursive low-pass filter to simulate the wind
    wind = np.zeros(total_samples)
    alpha = 0.04
    for i in range(1, total_samples):
        wind[i] = alpha * white_noise[i] + (1 - alpha) * wind[i-1]
    # Slow wind modulation (breathing)
    wind_mod = 0.5 + 0.5 * np.sin(2 * np.pi * 0.2 * t)
    wind = wind * wind_mod * 0.40

    # 3. Ether / Celestial shimmer (golden-scales harmonics at 528 Hz and 660 Hz)
    shimmer_l = np.sin(2 * np.pi * 528.0 * t + np.sin(2 * np.pi * 3.0 * t)) * 0.04
    shimmer_r = np.sin(2 * np.pi * 532.0 * t + np.sin(2 * np.pi * 2.5 * t)) * 0.04
    # Envelope modulation
    shimmer_env = np.clip((t - 2.0) / 4.0, 0, 1) * np.clip((duration_sec - t) / 2.0, 0, 1)
    shimmer_l *= shimmer_env
    shimmer_r *= shimmer_env

    # 4. Swell / Climax (cinematic intensity rise towards t=6s)
    swell_t = np.clip((t - 3.0) / 4.0, 0, 1)
    swell = np.sin(2 * np.pi * 110.0 * t) * (swell_t ** 2) * 0.12

    # Stereo mix with dynamic panning
    # Left
    pan_l = 0.5 + 0.3 * np.cos(2 * np.pi * 0.15 * t)
    # Right
    pan_r = 0.5 - 0.3 * np.cos(2 * np.pi * 0.15 * t)

    mix_l = (drone * 0.5 + wind * pan_l + swell * 0.4 + shimmer_l)
    mix_r = (drone * 0.5 + wind * pan_r + swell * 0.4 + shimmer_r)

    # 5. Global envelope (1.5s fade-in, 2.0s fade-out)
    fade_in_len = int(1.5 * sample_rate)
    fade_out_len = int(2.0 * sample_rate)

    env = np.ones(total_samples)
    env[:fade_in_len] = np.sin(np.linspace(0, np.pi / 2, fade_in_len)) ** 2
    env[-fade_out_len:] = np.cos(np.linspace(0, np.pi / 2, fade_out_len)) ** 2

    mix_l *= env
    mix_r *= env

    # Normalization and soft limiting (-1.0 dBFS)
    peak = max(np.max(np.abs(mix_l)), np.max(np.abs(mix_r)), 1e-6)
    target_peak = 0.89  # ~ -1 dBFS
    scale = target_peak / peak
    mix_l = np.clip(mix_l * scale, -1.0, 1.0)
    mix_r = np.clip(mix_r * scale, -1.0, 1.0)

    # Conversion to standard 16-bit PCM WAV
    stereo_int16 = np.column_stack((
        (mix_l * 32767).astype(np.int16),
        (mix_r * 32767).astype(np.int16)
    ))

    os.makedirs(os.path.dirname(os.path.abspath(out_wav_path)), exist_ok=True)
    wavfile.write(out_wav_path, sample_rate, stereo_int16)
    print(f"🎵 Cinematic soundtrack generated successfully: {out_wav_path} ({duration_sec}s, 48kHz Stereo)")
    return out_wav_path

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else r"C:\GIT\generator-assets\output\soundtrack_10s.wav"
    dur = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
    create_cinematic_soundtrack(out, dur)
