import os
import shutil
import subprocess
import sys
import time
import zipfile

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

# audio.cpp (moteur d'inférence GGUF Vulkan, comme sd-cli / llama-cli)
AUDIO_CPP_VERSION = "v0.7.2"
AUDIO_CPP_URL = (
    "https://github.com/0xShug0/audio.cpp/releases/download/"
    f"{AUDIO_CPP_VERSION}/audio-{AUDIO_CPP_VERSION}-bin-windows-x64-vulkan.zip"
)
AUDIO_CPP_DIR = os.getenv("AUDIO_CPP_DIR", r"C:\audio-cpp")

# MiniMax-Music3 GGUF — mix par défaut recommandé (Q4_0 / Q8_0, pic VRAM ~9.8 Gio)
MUSIC3_DIR = os.getenv("MUSIC3_MODEL_DIR", r"C:\Modeles_LLM\MiniMax-Music3-GGUF")
MUSIC3_BASE = "https://huggingface.co/audio-cpp/MiniMax-Music3-GGUF/resolve/main/"

FILES = [
    {"name": "language_model_q4_0.gguf", "size_gb": 6.01},
    {"name": "rvq_depth_decoder_q8_0.gguf", "size_gb": 0.70},
    {"name": "transformer_q4_0.gguf", "size_gb": 1.40},
    {"name": "condition_encoder.gguf", "size_gb": 0.10},
    {"name": "vocoder.gguf", "size_gb": 0.22},
    {"name": "config.json", "size_gb": 0.00},
    {"name": "config/condition_encoder.json", "size_gb": 0.00},
    {"name": "config/language_model.json", "size_gb": 0.00},
    {"name": "config/rvq_depth_decoder.json", "size_gb": 0.00},
    {"name": "config/transformer.json", "size_gb": 0.00},
    {"name": "config/vocoder.json", "size_gb": 0.00},
    {"name": "tokenizer/tokenizer.json", "size_gb": 0.01},
    {"name": "tokenizer/tokenizer_config.json", "size_gb": 0.00},
]

curl_path = shutil.which("curl.exe") or "curl"


def telecharger(nom: str, url: str, dossier: str, taille_attendue_mo: float):
    """Télécharge via curl (reprise -C -) avec fichier .part, skip si déjà complet."""
    dest = os.path.join(dossier, nom)
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    if os.path.exists(dest):
        taille_mo = os.path.getsize(dest) / (1024 * 1024)
        # Gros fichiers : valides dès 100 Mo ; petits fichiers de config : dès 1 octet
        seuil_mo = 0.0 if taille_attendue_mo < 1.0 else 100.0
        if taille_mo > seuil_mo:
            print(f"✅ Déjà présent : {nom} ({taille_mo:.1f} Mo)")
            return
        os.remove(dest)

    print(f"\n⬇️ Téléchargement : {nom} (~{taille_attendue_mo:.0f} Mo)...")
    print(f"   Source : {url}")
    part = dest + ".part"
    t0 = time.time()
    cmd = [curl_path, "-L", "-C", "-", "--fail", "--retry", "5", "--retry-delay", "3",
           "--progress-bar", "-o", part, url]
    result = subprocess.run(cmd)
    if result.returncode != 0 or not os.path.exists(part):
        raise RuntimeError(f"Échec du téléchargement de {nom} (code {result.returncode})")
    os.replace(part, dest)
    print(f"✅ Terminé : {nom} ({os.path.getsize(dest) / (1024 * 1024):.1f} Mo) en {time.time() - t0:.1f}s")


def installer_audio_cpp():
    """Télécharge et extrait la release audio.cpp Vulkan vers AUDIO_CPP_DIR."""
    exe_attendu = os.path.join(AUDIO_CPP_DIR, "audiocpp_cli.exe")
    if os.path.exists(exe_attendu):
        print(f"✅ audio.cpp déjà installé : {exe_attendu}")
        return

    os.makedirs(AUDIO_CPP_DIR, exist_ok=True)
    archive = os.path.join(AUDIO_CPP_DIR, f"audio-{AUDIO_CPP_VERSION}-vulkan.zip")
    print(f"\n⬇️ Téléchargement : audio.cpp {AUDIO_CPP_VERSION} (Windows x64 Vulkan, ~53 Mo)...")
    print(f"   Source : {AUDIO_CPP_URL}")
    cmd = [curl_path, "-L", "-C", "-", "--fail", "--progress-bar", "-o", archive, AUDIO_CPP_URL]
    result = subprocess.run(cmd)
    if result.returncode != 0 or not os.path.exists(archive):
        raise RuntimeError(f"Échec du téléchargement audio.cpp (code {result.returncode})")

    print("📦 Extraction de l'archive...")
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(AUDIO_CPP_DIR)

    # L'archive peut contenir un sous-dossier : on remonte audiocpp_cli.exe à la racine
    for racine, _, fichiers in os.walk(AUDIO_CPP_DIR):
        for f in fichiers:
            if f.lower() == "audiocpp_cli.exe" and os.path.join(racine, f) != exe_attendu:
                shutil.move(os.path.join(racine, f), exe_attendu)
                # Remonter les DLL compagnons éventuelles
                for dll in [x for x in fichiers if x.lower().endswith(".dll")]:
                    shutil.move(os.path.join(racine, dll), os.path.join(AUDIO_CPP_DIR, dll))
                break

    if not os.path.exists(exe_attendu):
        raise RuntimeError(f"audiocpp_cli.exe introuvable après extraction de {archive}")

    os.remove(archive)
    print(f"✅ audio.cpp installé : {exe_attendu}")


def main():
    print("=" * 80)
    print("📦 TÉLÉCHARGEMENT MINIMAX-MUSIC3 GGUF + AUDIO.CPP (VULKAN)")
    print(f"   Moteur      : {AUDIO_CPP_DIR}")
    print(f"   Modèles     : {MUSIC3_DIR}")
    print(f"   Total       : ~8.5 Go (mix Q4_0/Q8_0 par défaut)")
    print("=" * 80)

    installer_audio_cpp()

    for f_info in FILES:
        telecharger(
            f_info["name"],
            MUSIC3_BASE + f_info["name"],
            MUSIC3_DIR,
            f_info["size_gb"] * 1024,
        )

    print("\n🎉 SUCCÈS : MiniMax-Music3 GGUF et audio.cpp (Vulkan) sont prêts !")
    print("   Test rapide : audiocpp_cli --task gen --family minimax_music3 --model <dossier> --backend vulkan")


if __name__ == "__main__":
    main()
