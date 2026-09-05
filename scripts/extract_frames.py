import os
import sys
import subprocess

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

def extract_frames(video_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    ffmpeg_exe = r"C:\Program Files\Amuse\ffmpeg.exe"
    if not os.path.exists(ffmpeg_exe):
        ffmpeg_exe = "ffmpeg"
    
    cmd = [
        ffmpeg_exe, "-y",
        "-i", video_path,
        "-vf", "select=not(mod(n\\,8))",
        "-vsync", "vfr",
        "-q:v", "2",
        os.path.join(out_dir, "frame_%02d.png")
    ]
    subprocess.run(cmd, check=True)
    frames = sorted([os.path.join(out_dir, f) for f in os.listdir(out_dir) if f.endswith(".png")])
    print(f"Extracted {len(frames)} frames to {out_dir}")
    for f in frames:
        print(f"  {f}")
    return frames

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python extract_frames.py <video_path> <out_dir>")
        sys.exit(1)
    extract_frames(sys.argv[1], sys.argv[2])
