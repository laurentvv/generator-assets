import os
import shutil
import subprocess
import sys
import time
import zipfile

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

# audio.cpp (GGUF Vulkan inference engine, like sd-cli / llama-cli)
AUDIO_CPP_VERSION = "v0.7.2"
AUDIO_CPP_URL = (
    "https://github.com/0xShug0/audio.cpp/releases/download/"
    f"{AUDIO_CPP_VERSION}/audio-{AUDIO_CPP_VERSION}-bin-windows-x64-vulkan.zip"
)
AUDIO_CPP_DIR = os.getenv("AUDIO_CPP_DIR", r"C:\audio-cpp")

# MiniMax-Music3 GGUF — default mix recommended (Q4_0 / Q8_0, VRAM peak ~9.8 GiB)
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
    """Downloads via curl (resume -C -) with a .part file, skipped if already complete."""
    dest = os.path.join(dossier, nom)
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    if os.path.exists(dest):
        taille_mo = os.path.getsize(dest) / (1024 * 1024)
        # Large files: valid from 100 MB; small config files: from 1 byte
        seuil_mo = 0.0 if taille_attendue_mo < 1.0 else 100.0
        if taille_mo > seuil_mo:
            print(f"✅ Already present: {nom} ({taille_mo:.1f} MB)")
            return
        os.remove(dest)

    print(f"\n⬇️ Downloading: {nom} (~{taille_attendue_mo:.0f} MB)...")
    print(f"   Source: {url}")
    part = dest + ".part"
    t0 = time.time()
    cmd = [curl_path, "-L", "-C", "-", "--fail", "--retry", "5", "--retry-delay", "3",
           "--progress-bar", "-o", part, url]
    result = subprocess.run(cmd)
    if result.returncode != 0 or not os.path.exists(part):
        raise RuntimeError(f"Download of {nom} failed (code {result.returncode})")
    os.replace(part, dest)
    print(f"✅ Done: {nom} ({os.path.getsize(dest) / (1024 * 1024):.1f} MB) in {time.time() - t0:.1f}s")


def installer_audio_cpp():
    """Downloads and extracts the audio.cpp Vulkan release to AUDIO_CPP_DIR."""
    exe_attendu = os.path.join(AUDIO_CPP_DIR, "audiocpp_cli.exe")
    if os.path.exists(exe_attendu):
        print(f"✅ audio.cpp already installed: {exe_attendu}")
        return

    os.makedirs(AUDIO_CPP_DIR, exist_ok=True)
    archive = os.path.join(AUDIO_CPP_DIR, f"audio-{AUDIO_CPP_VERSION}-vulkan.zip")
    print(f"\n⬇️ Downloading: audio.cpp {AUDIO_CPP_VERSION} (Windows x64 Vulkan, ~53 MB)...")
    print(f"   Source: {AUDIO_CPP_URL}")
    cmd = [curl_path, "-L", "-C", "-", "--fail", "--progress-bar", "-o", archive, AUDIO_CPP_URL]
    result = subprocess.run(cmd)
    if result.returncode != 0 or not os.path.exists(archive):
        raise RuntimeError(f"audio.cpp download failed (code {result.returncode})")

    print("📦 Extracting the archive...")
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(AUDIO_CPP_DIR)

    # The archive may contain a subfolder: move audiocpp_cli.exe up to the root
    for racine, _, fichiers in os.walk(AUDIO_CPP_DIR):
        for f in fichiers:
            if f.lower() == "audiocpp_cli.exe" and os.path.join(racine, f) != exe_attendu:
                shutil.move(os.path.join(racine, f), exe_attendu)
                # Move any companion DLLs up as well
                for dll in [x for x in fichiers if x.lower().endswith(".dll")]:
                    shutil.move(os.path.join(racine, dll), os.path.join(AUDIO_CPP_DIR, dll))
                break

    if not os.path.exists(exe_attendu):
        raise RuntimeError(f"audiocpp_cli.exe not found after extracting {archive}")

    os.remove(archive)
    print(f"✅ audio.cpp installed: {exe_attendu}")


def main():
    print("=" * 80)
    print("📦 MINIMAX-MUSIC3 GGUF + AUDIO.CPP (VULKAN) DOWNLOAD")
    print(f"   Engine      : {AUDIO_CPP_DIR}")
    print(f"   Models      : {MUSIC3_DIR}")
    print("   Total       : ~8.5 GB (default Q4_0/Q8_0 mix)")
    print("=" * 80)

    installer_audio_cpp()

    for f_info in FILES:
        telecharger(
            f_info["name"],
            MUSIC3_BASE + f_info["name"],
            MUSIC3_DIR,
            f_info["size_gb"] * 1024,
        )

    print("\n🎉 SUCCESS: MiniMax-Music3 GGUF and audio.cpp (Vulkan) are ready!")
    print("   Quick test: audiocpp_cli --task gen --family minimax_music3 --model <folder> --backend vulkan")


if __name__ == "__main__":
    main()
