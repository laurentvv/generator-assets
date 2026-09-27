import os
import shutil
import subprocess
import sys
import time

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

# audio.cpp (already installed by download_music3_gguf.py — same v0.7.2 release that
# introduced the ace_step family): presence check only.
AUDIO_CPP_DIR = os.getenv("AUDIO_CPP_DIR", r"C:\audio-cpp")

# ACE-Step 1.5 GGUF — monolithic packages (DiT + 1.7B LM planner + text
# encoder + vocoder) published by audio-cpp.
# ⚠️ Clarifications: audio.cpp's guide docs/gguf.md flags q8_0 as "No" for
# ace_step (planner sampling failure: "found no valid token") and
# bf16 as "Pass (drift)" → bf16 mandatory.
# The turbo/base variants are on Hugging Face; the XL ONLY on the
# ModelScope mirror. Big files: the parallel downloader is ~10x
# faster than curl (single-connection CDN throttling).
ACESTEP15_DIR = os.getenv("ACESTEP15_MODEL_DIR", r"C:\Modeles_LLM\ACE-Step1.5-GGUF")
HF_BASE = "https://huggingface.co/audio-cpp/audio.cpp-gguf/resolve/main/ACE-Step1.5-GGUF/"
MS_BASE = "https://modelscope.cn/models/HereIsMark/audio.cpp-gguf/resolve/master/ACE-Step1.5-GGUF/"

VARIANTES = {
    "turbo":    {"fichier": "turbo/ace-step-1.5-turbo-bf16.gguf",          "source": HF_BASE, "gib": 9.40},
    "base":     {"fichier": "base/ace-step-1.5-base-bf16.gguf",           "source": HF_BASE, "gib": 9.40},
    "xl-turbo": {"fichier": "xl-turbo/ace-step-1.5-xl-turbo-bf16.gguf",    "source": MS_BASE, "gib": 14.23},
    "xl-sft":   {"fichier": "xl-sft/ace-step-1.5-xl-sft-bf16.gguf",        "source": MS_BASE, "gib": 14.23},
}

# Default: turbo alone (the XLs double the disk usage — ~14 GiB each)
VARIANTES_DEFAUT = ["turbo"]

curl_path = shutil.which("curl.exe") or "curl"


def telecharger(nom: str, url: str, dossier: str, taille_attendue_mo: float):
    """Downloads, with a .part file, skips if already complete.

    Big files (≥ 1 GiB): delegates to the parallel downloader by HTTP Range
    segments — single-connection CDN throttling bypassed, measured 166 MB/s on
    ModelScope on 2026-09-07 (vs ~2 MB/s in direct curl; xl-sft 14.23 GiB in
    ~3.5 min). ModelScope supports Range (HTTP 206 verified).
    """
    dest = os.path.join(dossier, nom)
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    if os.path.exists(dest):
        taille_mo = os.path.getsize(dest) / (1024 * 1024)
        # Big file: valid from 100 MB (resume handled by deletion otherwise)
        if taille_mo > 100.0:
            print(f"✅ Already present: {nom} ({taille_mo:.1f} MB)")
            return
        os.remove(dest)

    print(f"\n⬇️ Download: {nom} (~{taille_attendue_mo:.0f} MB)...")
    print(f"   Source: {url}")
    if taille_attendue_mo >= 1024:
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "telecharger_gros_fichier_parallele.py")
        resultat = subprocess.run([sys.executable, script, url, dest])
        if resultat.returncode != 0 or not os.path.exists(dest):
            raise RuntimeError(
                f"Parallel download of {nom} failed (code {resultat.returncode})")
        return
    part = dest + ".part"
    t0 = time.time()
    cmd = [curl_path, "-L", "-C", "-", "--fail", "--retry", "5", "--retry-delay", "3",
           "--progress-bar", "-o", part, url]
    result = subprocess.run(cmd)
    if result.returncode != 0 or not os.path.exists(part):
        raise RuntimeError(f"Download of {nom} failed (code {result.returncode})")
    os.replace(part, dest)
    print(f"✅ Done: {nom} ({os.path.getsize(dest) / (1024 * 1024):.1f} MB) in {time.time() - t0:.1f}s")


def verifier_audio_cpp():
    """Checks that audio.cpp ≥ 0.7.2 (ace_step family) is installed."""
    exe = os.path.join(AUDIO_CPP_DIR, "audiocpp_cli.exe")
    if os.path.exists(exe):
        spec = os.path.join(AUDIO_CPP_DIR, "model_specs", "ace_step.json")
        if os.path.exists(spec):
            print(f"✅ audio.cpp already installed with the ace_step family: {exe}")
            return
        raise RuntimeError(
            f"audio.cpp is present ({exe}) but without model_specs/ace_step.json:\n"
            "→ Version < 0.7.2. Run again: uv run python scripts/download_music3_gguf.py"
        )
    raise RuntimeError(
        f"audiocpp_cli.exe not found: {exe}\n"
        "→ Run first: uv run python scripts/download_music3_gguf.py"
    )


def main():
    # Arguments: variants to install, e.g. "xl-turbo" or "tout"/"all" (turbo + XLs)
    demande = sys.argv[1:] if len(sys.argv) > 1 else []
    if demande in (["tout"], ["all"]):
        demande = list(VARIANTES)
    for v in demande:
        if v not in VARIANTES:
            print(f"❌ Unknown variant: {v} (choices: {', '.join(VARIANTES)}, tout)")
            sys.exit(1)
    variantes = demande or VARIANTES_DEFAUT

    total_gib = sum(VARIANTES[v]["gib"] for v in variantes)
    print("=" * 80)
    print(f"📦 ACE-STEP 1.5 GGUF (BF16) DOWNLOAD — {', '.join(variantes)}")
    print(f"   Engine      : {AUDIO_CPP_DIR} (audio.cpp ≥ 0.7.2 required)")
    print(f"   Models      : {ACESTEP15_DIR}")
    print(f"   Total       : ~{total_gib:.1f} GiB")
    print("   License     : MIT (ACE-Step 1.5) — commercial use free")
    print("=" * 80)

    verifier_audio_cpp()

    for v in variantes:
        info = VARIANTES[v]
        print(f"\n▶️ Variant {v} ({info['gib']:.1f} GiB) — "
              f"{'ModelScope (mirror)' if info['source'] == MS_BASE else 'Hugging Face'}")
        telecharger(
            info["fichier"],
            info["source"] + info["fichier"],
            ACESTEP15_DIR,
            info["gib"] * 1024,
        )

    print("\n🎉 SUCCESS: ACE-Step 1.5 GGUF ready!")
    print("   Quick test: audiocpp_cli --task gen --family ace_step --model <folder> \\")
    print("               --backend vulkan --task-route text2music --text \"<desc>\" --duration-seconds 12")


if __name__ == "__main__":
    main()
