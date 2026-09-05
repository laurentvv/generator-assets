import os
import subprocess
import shutil

TARGET_DIR = r'C:\Modeles_LLM'
curl = shutil.which('curl.exe') or 'curl'

MODELS = [
    ('Wan2.2-T2V-P14B-HighNoise-Q4_K_M.gguf', 'https://huggingface.co/QuantStack/Wan2.2-T2V-A14B-GGUF/resolve/main/HighNoise/Wan2.2-T2V-A14B-HighNoise-Q4_K_M.gguf'),
    ('Wan2.2-T2V-A14B-LowNoise-Q4_K_M.gguf', 'https://huggingface.co/QuantStack/Wan2.2-T2V-A14B-GGUF/resolve/main/LowNoise/Wan2.2-T2V-A14B-LowNoise-Q4_K_M.gguf')
]

for name, url in MODELS:
    dest = os.path.join(TARGET_DIR, name)
    if os.path.exists(dest) and os.path.getsize(dest) > 100 * 1024 * 1024:
        print(f'Deja present : {name}')
        continue
    print(f'\nTelechargement : {name}...')
    cmd = [curl, '-L', '-C', '-', '--fail', '--progress-bar', '-o', dest, url]
    subprocess.run(cmd, check=True)
    print(f'Termine : {name}')
print('\n[SUCCES] Wan 2.2 MoE telecharge !')
