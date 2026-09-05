import os
import subprocess
import sys

INPUT_VIDEO = sys.argv[1] if len(sys.argv) > 1 else r'C:\GIT\generator-assets\godot_assets\dragon_sequence_6s_hd.mp4'
if not os.path.exists(INPUT_VIDEO):
    INPUT_VIDEO = r'C:\GIT\generator-assets\godot_assets\dragon_sequence_6s_brute.mp4'

OUTPUT_1080P = sys.argv[2] if len(sys.argv) > 2 else r'C:\GIT\generator-assets\godot_assets\dragon_sequence_1080p_youtube_hd.mp4'
FFMPEG = r'C:\Program Files\Amuse\ffmpeg.exe'

if not os.path.exists(INPUT_VIDEO):
    print(f'Fichier source introuvable : {INPUT_VIDEO}')
    sys.exit(1)

cmd = [
    FFMPEG, '-y',
    '-i', INPUT_VIDEO,
    '-vf', 'scale=1920:1080:flags=lanczos,cas=0.75',
    '-c:v', 'h264_amf',
    '-quality', 'quality',
    '-rc', 'cbr',
    '-b:v', '22M',
    '-pix_fmt', 'yuv420p',
    OUTPUT_1080P
]

print(f'Export materiel YouTube HD 1080p vers : {OUTPUT_1080P}...')
subprocess.run(cmd, check=True)
print('SUCCES TOTAL : dragon_sequence_1080p_youtube_hd.mp4 genere !')
