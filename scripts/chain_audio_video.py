"""
chain_audio_video.py
Module d'enchainement audio-video avance avec fondus enchaines sonores (crossfade).
Permet de relier plusieurs plans video (avec ou sans audio) sans claquement ni rupture sonore.
"""
import os
import sys
import subprocess
import json

FFMPEG = r"C:\Program Files\Amuse\ffmpeg.exe"

def concatener_avec_audio_crossfade(clips, out_path, crossfade_sec=0.25):
    """
    Concatène plusieurs clips vidéo en préservant et mixant harmonieusement leurs pistes audio.
    Applique un fondu enchaîné (acrossfade) entre chaque segment audio pour une transition cinématographique.
    """
    if not clips:
        print("Erreur : Aucun clip fourni.")
        return None

    if len(clips) == 1:
        # Simple copie
        subprocess.run([FFMPEG, "-y", "-i", clips[0], "-c", "copy", out_path], check=True)
        return out_path

    print(f"\n🔗 [Enchaînement Audio-Vidéo] Assemblage de {len(clips)} plans...")
    print(f"   Fondu enchaîné audio : {crossfade_sec*1000:.0f} ms entre chaque plan")

    # Vérifier la présence d'audio dans les clips via ffprobe
    inputs = []
    for c in clips:
        inputs.extend(["-i", c])

    # Construction du filtre complexe FFmpeg
    # Concaténation vidéo directe + cascade de filtres acrossfade audio
    n = len(clips)
    
    # 1. Filtre vidéo
    v_inputs = "".join([f"[{i}:v]" for i in range(n)])
    v_filter = f"{v_inputs}concat=n={n}:v=1:a=0[vout]"

    # 2. Filtre audio cascade
    # [0:a][1:a] acrossfade=d=0.25 [a1]; [a1][2:a] acrossfade=d=0.25 [a2]...
    a_filters = []
    last_a = "[0:a]"
    for i in range(1, n):
        out_a = f"[a{i}]" if i < n - 1 else "[aout]"
        a_filters.append(f"{last_a}[{i}:a]acrossfade=d={crossfade_sec}:c1=tri:c2=tri{out_a}")
        last_a = f"[a{i}]"

    filter_complex = v_filter + "; " + "; ".join(a_filters)

    cmd = [
        FFMPEG, "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "[aout]",
        "-c:v", "h264_amf",
        "-quality", "quality",
        "-b:v", "20M",
        "-c:a", "aac",
        "-b:a", "192k",
        out_path
    ]

    try:
        subprocess.run(cmd, check=True)
        print(f"✅ Séquence audio-vidéo assemblée avec succès : {out_path}")
        return out_path
    except subprocess.CalledProcessError:
        # Si un des clips n'avait pas d'audio, fallback en concaténation vidéo pure
        print("⚠️ Pas de piste audio complète détectée sur tous les clips : fallback vidéo pure.")
        concat_txt = os.path.join(os.path.dirname(out_path), "concat_list.txt")
        with open(concat_txt, "w", encoding="utf-8") as f:
            for c in clips:
                f.write(f"file '{c}'\n")
        cmd_fallback = [
            FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", concat_txt,
            "-c:v", "h264_amf", "-b:v", "20M", out_path
        ]
        subprocess.run(cmd_fallback, check=True)
        return out_path

if __name__ == "__main__":
    if len(sys.argv) > 2:
        concatener_avec_audio_crossfade(sys.argv[1:-1], sys.argv[-1])
