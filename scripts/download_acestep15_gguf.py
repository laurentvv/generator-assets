import os
import shutil
import subprocess
import sys
import time

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

# audio.cpp (déjà installé par download_music3_gguf.py — même release v0.7.2 qui
# a introduit la famille ace_step) : vérification de présence uniquement.
AUDIO_CPP_DIR = os.getenv("AUDIO_CPP_DIR", r"C:\audio-cpp")

# ACE-Step 1.5 GGUF — paquets monolithiques (DiT + LM planner 1.7B + text
# encoder + vocoder) publiés par audio-cpp.
# ⚠️ Précisions : le guide docs/gguf.md d'audio.cpp signale q8_0 « No » pour
# ace_step (échec d'échantillonnage du planner : « found no valid token ») et
# bf16 « Pass (drift) » → bf16 obligatoire.
# Les variantes turbo/base sont sur Hugging Face ; les XL UNIQUEMENT sur le
# miroir ModelScope. Gros fichiers : le téléchargeur parallèle est ~10x plus
# rapide que curl (bridage CDN mono-connexion).
ACESTEP15_DIR = os.getenv("ACESTEP15_MODEL_DIR", r"C:\Modeles_LLM\ACE-Step1.5-GGUF")
HF_BASE = "https://huggingface.co/audio-cpp/audio.cpp-gguf/resolve/main/ACE-Step1.5-GGUF/"
MS_BASE = "https://modelscope.cn/models/HereIsMark/audio.cpp-gguf/resolve/master/ACE-Step1.5-GGUF/"

VARIANTES = {
    "turbo":    {"fichier": "turbo/ace-step-1.5-turbo-bf16.gguf",          "source": HF_BASE, "gib": 9.40},
    "xl-turbo": {"fichier": "xl-turbo/ace-step-1.5-xl-turbo-bf16.gguf",    "source": MS_BASE, "gib": 14.23},
    "xl-sft":   {"fichier": "xl-sft/ace-step-1.5-xl-sft-bf16.gguf",        "source": MS_BASE, "gib": 14.23},
}

# Défaut : turbo seul (les XL doublent le volume disque — ~14 Gio chacun)
VARIANTES_DEFAUT = ["turbo"]

curl_path = shutil.which("curl.exe") or "curl"


def telecharger(nom: str, url: str, dossier: str, taille_attendue_mo: float):
    """Télécharge via curl (reprise -C -) avec fichier .part, skip si déjà complet."""
    dest = os.path.join(dossier, nom)
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    if os.path.exists(dest):
        taille_mo = os.path.getsize(dest) / (1024 * 1024)
        # Gros fichier : valide dès 100 Mo (reprise gérée par suppression sinon)
        if taille_mo > 100.0:
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


def verifier_audio_cpp():
    """Vérifie qu'audio.cpp ≥ 0.7.2 (famille ace_step) est installé."""
    exe = os.path.join(AUDIO_CPP_DIR, "audiocpp_cli.exe")
    if os.path.exists(exe):
        spec = os.path.join(AUDIO_CPP_DIR, "model_specs", "ace_step.json")
        if os.path.exists(spec):
            print(f"✅ audio.cpp déjà installé avec la famille ace_step : {exe}")
            return
        raise RuntimeError(
            f"audio.cpp est présent ({exe}) mais sans model_specs/ace_step.json :\n"
            "→ Version < 0.7.2. Relancez : uv run python scripts/download_music3_gguf.py"
        )
    raise RuntimeError(
        f"audiocpp_cli.exe introuvable : {exe}\n"
        "→ Lancez d'abord : uv run python scripts/download_music3_gguf.py"
    )


def main():
    # Arguments : variantes à installer, ex. « xl-turbo » ou « tout » (turbo + XL)
    demande = sys.argv[1:] if len(sys.argv) > 1 else []
    if demande in (["tout"], ["all"]):
        demande = list(VARIANTES)
    for v in demande:
        if v not in VARIANTES:
            print(f"❌ Variante inconnue : {v} (choix : {', '.join(VARIANTES)}, tout)")
            sys.exit(1)
    variantes = demande or VARIANTES_DEFAUT

    total_gib = sum(VARIANTES[v]["gib"] for v in variantes)
    print("=" * 80)
    print(f"📦 TÉLÉCHARGEMENT ACE-STEP 1.5 GGUF (BF16) — {', '.join(variantes)}")
    print(f"   Moteur      : {AUDIO_CPP_DIR} (audio.cpp ≥ 0.7.2 requis)")
    print(f"   Modèles     : {ACESTEP15_DIR}")
    print(f"   Total       : ~{total_gib:.1f} Gio")
    print("   Licence     : MIT (ACE-Step 1.5) — usage commercial libre")
    print("=" * 80)

    verifier_audio_cpp()

    for v in variantes:
        info = VARIANTES[v]
        print(f"\n▶️ Variante {v} ({info['gib']:.1f} Gio) — "
              f"{'ModelScope (miroir)' if info['source'] == MS_BASE else 'Hugging Face'}")
        telecharger(
            info["fichier"],
            info["source"] + info["fichier"],
            ACESTEP15_DIR,
            info["gib"] * 1024,
        )

    print("\n🎉 SUCCÈS : ACE-Step 1.5 GGUF prêt !")
    print("   Test rapide : audiocpp_cli --task gen --family ace_step --model <dossier> \\")
    print("                 --backend vulkan --task-route text2music --text \"<desc>\" --duration-seconds 12")


if __name__ == "__main__":
    main()
