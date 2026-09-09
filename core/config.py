#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration globale, chemins d'accès par défaut, gestion des LoRAs et des Upscalers.
"""

import os
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Chemins des exécutables
DEFAULT_LLAMA_CLI = os.getenv("LLAMA_CLI_PATH", r"C:\llama.cpp\llama-cli.exe")
DEFAULT_SD_CLI = os.getenv("SD_CLI_PATH", r"C:\SD\sd-cli.exe")
DEFAULT_SD_DIR = os.getenv("SD_DIR", r"C:\SD")
DEFAULT_SD_SOURCE_DIR = os.getenv("SD_SOURCE_DIR", r"C:\GIT\stable-diffusion.cpp")
DEFAULT_AUDIOCPP_CLI = os.getenv("AUDIOCPP_PATH", r"C:\audio-cpp\audiocpp_cli.exe")


def _detecter_ffmpeg() -> str:
    """ffmpeg 9 (C:\\ffmpeg\\dist) en priorité, puis ancien build Amuse, puis PATH."""
    candidats = [
        r"C:\ffmpeg\dist\bin\ffmpeg.exe",
        r"C:\Program Files\Amuse\ffmpeg.exe",
    ]
    for c in candidats:
        if os.path.exists(c):
            return c
    return "ffmpeg"


DEFAULT_FFMPEG = os.getenv("FFMPEG_PATH", _detecter_ffmpeg())

# Dossiers et Modèles de base
DEFAULT_MODEL_DIR = os.getenv("MODEL_DIR", r"C:\Modeles_LLM")
DEFAULT_LLM_MODEL = os.getenv("LLM_MODEL_PATH", os.path.join(DEFAULT_MODEL_DIR, "LFM2.5-8B-A1B-Q6_K.gguf"))
DEFAULT_SD_MODEL = os.getenv("SD_MODEL_PATH", os.path.join(DEFAULT_MODEL_DIR, "flux1-dev-Q6_K.gguf"))
DEFAULT_CLIP_L = os.getenv("SD_CLIP_L_PATH", os.path.join(DEFAULT_MODEL_DIR, "clip_l.safetensors"))
DEFAULT_T5XXL = os.getenv("SD_T5XXL_PATH", os.path.join(DEFAULT_MODEL_DIR, "t5xxl_fp16.safetensors"))
DEFAULT_VAE = os.getenv("SD_VAE_PATH", os.path.join(DEFAULT_MODEL_DIR, "ae.safetensors"))

# Modèles Vidéo (Wan 2.1 / Wan 2.2, LTX-2.3 / LTX-2.5, MiniMax-H3)
DEFAULT_WAN_MODEL = os.getenv("WAN_MODEL_PATH", os.path.join(DEFAULT_MODEL_DIR, "wan2.1-t2v-1.3b-q8_0.gguf"))
DEFAULT_WAN_VAE = os.getenv("WAN_VAE_PATH", os.path.join(DEFAULT_MODEL_DIR, "wan_2.1_vae.safetensors"))
DEFAULT_WAN_T5XXL = os.getenv("WAN_T5XXL_PATH", os.path.join(DEFAULT_MODEL_DIR, "umt5-xxl-encoder-Q8_0.gguf"))

# Modèles vidéo MiniMax-H3 Ref2VA (référence vidéo+audio → vidéo générée, sortie webm avec audio).
# ⚠️ Le DiT ref2va est DISTINCT du fl2va (T2VA/I2VA) — source : leejet/MiniMax-H3-GGUF
# (le repo MiniMax-AI/MiniMax-H3-GGUF est gated). Recette validée : MEMORY_BANK §1.16.
DEFAULT_H3_REF2VA_MODEL = os.getenv(
    "H3_REF2VA_MODEL_PATH",
    os.path.join(DEFAULT_MODEL_DIR, "minimax_h3_ref2va_pruned-Q4_K_M.gguf"),
)
DEFAULT_H3_VIDEO_VAE = os.getenv(
    "H3_VIDEO_VAE_PATH", os.path.join(DEFAULT_MODEL_DIR, "minimax_h3_video_vae_fp16.safetensors")
)
DEFAULT_H3_AUDIO_VAE = os.getenv(
    "H3_AUDIO_VAE_PATH", os.path.join(DEFAULT_MODEL_DIR, "minimax_h3_audio_vae_fp32.safetensors")
)
DEFAULT_H3_LLM = os.getenv(
    "H3_LLM_PATH", os.path.join(DEFAULT_MODEL_DIR, "qwen3vl_32b_minimax_h3-Q2_K_M.gguf")
)
# LoRA turbo Ref2VA (distillation 20→8 steps, HF lightx2v/Minimax-h3-Turbo — prendre la
# variante NON `_comfyui_`). Recette VALIDÉE utilisateur le 2026-09-09 : sampling −64 %,
# total −46 %, qualité et raccord référence ≥ baseline (nom sans extension .safetensors).
DEFAULT_H3_REF2VA_TURBO_LORA = os.getenv(
    "H3_REF2VA_TURBO_LORA", "minimax_h3_ref2v_turbo_8step_v1.0_768p_bf16"
)

# Modèles Musique (MiniMax-Music3 GGUF via audio.cpp + Music Flamingo via llama.cpp)
DEFAULT_MUSIC3_DIR = os.getenv("MUSIC3_MODEL_DIR", os.path.join(DEFAULT_MODEL_DIR, "MiniMax-Music3-GGUF"))
DEFAULT_MUSIC3_LM = os.getenv("MUSIC3_LM_PATH", os.path.join(DEFAULT_MUSIC3_DIR, "language_model_q4_0.gguf"))
# ACE-Step 1.5 Turbo GGUF (bf16) via audio.cpp — paquet monolithique, licence MIT.
# ⚠️ q8_0 non supporté pour cette famille (échec d'échantillonnage du planner).
DEFAULT_ACESTEP15_DIR = os.getenv("ACESTEP15_MODEL_DIR", os.path.join(DEFAULT_MODEL_DIR, "ACE-Step1.5-GGUF"))
DEFAULT_MUSIC_FLAMINGO_DIR = os.getenv("MUSIC_FLAMINGO_DIR", os.path.join(DEFAULT_MODEL_DIR, "music-flamingo"))
DEFAULT_MUSIC_FLAMINGO_LM = os.getenv(
    "MUSIC_FLAMINGO_LM_PATH", os.path.join(DEFAULT_MUSIC_FLAMINGO_DIR, "music-flamingo-hf.Q4_K_M.gguf")
)
DEFAULT_MUSIC_FLAMINGO_MMPROJ = os.getenv(
    "MUSIC_FLAMINGO_MMPROJ_PATH", os.path.join(DEFAULT_MUSIC_FLAMINGO_DIR, "music-flamingo-hf.mmproj-f16.gguf")
)

# Dossiers spécialisés pour LoRAs et Upscalers (Recherche dans C:\Modeles_LLM\... puis dans le projet local)
DEFAULT_LORA_DIRS = [
    os.getenv("LORA_DIR", os.path.join(DEFAULT_MODEL_DIR, "loras")),
    os.path.abspath("loras")
]

DEFAULT_UPSCALER_DIRS = [
    os.getenv("UPSCALER_DIR", os.path.join(DEFAULT_MODEL_DIR, "upscalers")),
    os.path.abspath("upscalers"),
    DEFAULT_MODEL_DIR
]

DEFAULT_ESRGAN_MODEL = os.getenv(
    "SD_ESRGAN_PATH",
    os.path.join(DEFAULT_MODEL_DIR, "upscalers", "RealESRGAN_x4plus_anime_6B.pth")
)

# Modèles ONNX spécialisés (Segmentation, PBR, Animation)
DEFAULT_ONNX_DIRS = [
    os.getenv("ONNX_DIR", os.path.join(DEFAULT_MODEL_DIR, "onnx")),
    os.path.abspath("models"),
    os.path.join(DEFAULT_MODEL_DIR, "segmentation"),
    os.path.join(DEFAULT_MODEL_DIR, "pbr"),
    os.path.join(DEFAULT_MODEL_DIR, "animation"),
    DEFAULT_MODEL_DIR
]

DEFAULT_RMBG_MODEL = os.getenv(
    "RMBG_MODEL_PATH",
    os.path.join(DEFAULT_MODEL_DIR, "onnx", "rmbg-1.4.onnx")
)

DEFAULT_DEEPBUMP_MODEL = os.getenv(
    "DEEPBUMP_MODEL_PATH",
    os.path.join(DEFAULT_MODEL_DIR, "onnx", "deepbump256.onnx")
)

DEFAULT_RIFE_MODEL = os.getenv(
    "RIFE_MODEL_PATH",
    os.path.join(DEFAULT_MODEL_DIR, "onnx", "rife_fp32.onnx")
)

DEFAULT_YUNET_MODEL = os.getenv(
    "YUNET_MODEL_PATH",
    os.path.join(DEFAULT_MODEL_DIR, "onnx", "face_detection_yunet_2023mar.onnx")
)

# Paramètres de rendu
DEFAULT_BACKEND = os.getenv("SD_BACKEND", "diffusion=vulkan0,te=cpu")
DEFAULT_THREADS = int(os.getenv("SD_THREADS", "16"))
DEFAULT_OUTPUT_DIR = os.getenv("OUTPUT_DIR", "godot_assets")
DEFAULT_MPFB_DATA_DIR = os.getenv(
    "MPFB_DATA_DIR",
    os.path.expandvars(r"%APPDATA%\Blender Foundation\Blender\5.2\mpfb\data\data")
)
DEFAULT_MPFB_INK_DIR = os.getenv(
    "MPFB_INK_DIR",
    os.path.join(DEFAULT_MPFB_DATA_DIR, "ink_layers")
)
DEFAULT_MPFB_EYES_DIR = os.getenv(
    "MPFB_EYES_DIR",
    os.path.join(DEFAULT_MPFB_DATA_DIR, "eyes", "materials")
)
TEMP_IMAGE = "temp_render.png"

# Charte Visuelle par Défaut (Style Anchor)
DEFAULT_STYLE_ANCHOR = (
    "2D game asset, dark fantasy aesthetic, isolated on solid plain white background, "
    "obsidian steel, deep violet glowing runes, dark void energy, "
    "sharp clean edges, digital painting style, centered composition, no shadows on background"
)

# Cadrages selon le type d'asset
CADRAGE_INSTRUCTIONS = {
    "item": "front view or isometric view, single isolated game icon",
    "character": "full body sprite, neutral standing pose, front view",
    "prop": "isometric view, environmental 2D game object",
    "tile": "top-down or front view, seamless texture pattern",
    "angle_front": "front view, centered character sprite",
    "angle_right": "side profile view facing right, centered character sprite",
    "angle_back": "back view, centered character sprite",
    "angle_left": "side profile view facing left, centered character sprite"
}


def slugifier_texte(texte: str, max_longueur: int = 50) -> str:
    """Transforme une chaîne en nom de fichier sécurisé (snake_case)."""
    texte = unicodedata.normalize('NFKD', str(texte)).encode('ascii', 'ignore').decode('utf-8')
    texte = re.sub(r'[^\w\s-]', '', texte).strip().lower()
    texte = re.sub(r'[-\s]+', '_', texte)
    return (texte[:max_longueur].rstrip('_')) or "asset_render"


def lister_loras(dirs: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """Scanne les répertoires de LoRAs et renvoie la liste des fichiers disponibles."""
    dossiers = dirs or DEFAULT_LORA_DIRS
    fichiers_loras = []
    extensions = (".safetensors", ".bin", ".gguf")
    vus = set()

    for dossier in dossiers:
        if os.path.exists(dossier):
            for racine, _, fichiers in os.walk(dossier):
                for f in fichiers:
                    if f.lower().endswith(extensions) and f not in vus:
                        vus.add(f)
                        chemin = os.path.join(racine, f)
                        taille_mo = os.path.getsize(chemin) / (1024 * 1024)
                        fichiers_loras.append({
                            "name": Path(f).stem,
                            "filename": f,
                            "path": chemin,
                            "size_mb": round(taille_mo, 1)
                        })
    return fichiers_loras


def lister_upscalers(dirs: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """Scanne les répertoires et renvoie la liste des modèles d'upscaling ESRGAN/SwinIR."""
    dossiers = dirs or DEFAULT_UPSCALER_DIRS
    fichiers_upscalers = []
    extensions = (".pth", ".bin", ".safetensors", ".onnx")
    vus = set()

    for dossier in dossiers:
        if os.path.exists(dossier):
            for racine, _, fichiers in os.walk(dossier):
                for f in fichiers:
                    if f.lower().endswith(extensions) and f not in vus:
                        # Filtrer les modèles non-upscalers si dans C:\Modeles_LLM direct
                        if dossier == DEFAULT_MODEL_DIR and not any(k in f.lower() for k in ["esrgan", "upscale", "sharp", "remacri"]):
                            continue
                        vus.add(f)
                        chemin = os.path.join(racine, f)
                        taille_mo = os.path.getsize(chemin) / (1024 * 1024)
                        fichiers_upscalers.append({
                            "name": Path(f).stem,
                            "filename": f,
                            "path": chemin,
                            "size_mb": round(taille_mo, 1)
                        })
    return fichiers_upscalers


def resoudre_upscaler(nom_ou_chemin: Optional[str] = None) -> Optional[str]:
    """Résout le chemin absolu d'un modèle d'upscale à partir de son nom partiel, alias ou auto-détection."""
    dispos = lister_upscalers()
    if not dispos:
        return DEFAULT_ESRGAN_MODEL if os.path.exists(DEFAULT_ESRGAN_MODEL) else None

    # Si aucun modèle n'est spécifié ou mode 'auto'
    if not nom_ou_chemin or nom_ou_chemin.lower() in ("auto", "default"):
        # Priorité de qualité : 4x-UltraSharp > RealESRGAN_x4plus > RealESRGAN_x4plus_anime_6B
        priorites = ["4x-ultrasharp", "realesrgan_x4plus", "realesrgan_x4plus_anime_6b"]
        for pref in priorites:
            for up in dispos:
                if pref in up["name"].lower() or pref in up["filename"].lower():
                    return up["path"]
        return dispos[0]["path"]

    # Si c'est déjà un chemin absolu ou relatif existant
    if os.path.exists(nom_ou_chemin):
        return os.path.abspath(nom_ou_chemin)

    cle = nom_ou_chemin.lower()
    
    # Raccourcis / Alias courants
    alias = {
        "anime": "realesrgan_x4plus_anime_6b",
        "photo": "realesrgan_x4plus",
        "general": "realesrgan_x4plus",
        "ultrasharp": "4x-ultrasharp",
        "sharp": "4x-ultrasharp",
        "4k": "4x-ultrasharp",
        "esrgan": "realesrgan_x4plus"
    }
    terme_recherche = alias.get(cle, cle).lower()

    for up in dispos:
        if terme_recherche in up["name"].lower() or terme_recherche in up["filename"].lower():
            return up["path"]

    return dispos[0]["path"]


def resoudre_sd_model(nom_ou_chemin: Optional[str] = None) -> str:
    """Résout le chemin absolu d'un modèle de diffusion (Flux.1 ou SDXL Juggernaut)."""
    if not nom_ou_chemin or nom_ou_chemin.lower() in ("default", "flux", "flux.1"):
        return DEFAULT_SD_MODEL

    if os.path.exists(nom_ou_chemin):
        return os.path.abspath(nom_ou_chemin)

    cle = nom_ou_chemin.lower()
    if os.path.exists(DEFAULT_MODEL_DIR):
        for f in os.listdir(DEFAULT_MODEL_DIR):
            f_lower = f.lower()
            if not f_lower.endswith((".safetensors", ".gguf", ".ckpt", ".bin")):
                continue
            if cle in f_lower:
                return os.path.join(DEFAULT_MODEL_DIR, f)
            if cle in ("juggernaut", "juggernautxl", "sdxl", "ragnarok") and "juggernaut" in f_lower:
                return os.path.join(DEFAULT_MODEL_DIR, f)

    return nom_ou_chemin


def lister_modeles_onnx(dirs: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """Scanne les répertoires pour trouver les modèles ONNX."""
    dossiers = dirs or DEFAULT_ONNX_DIRS
    fichiers_onnx = []
    vus = set()

    for dossier in dossiers:
        if os.path.exists(dossier):
            for racine, _, fichiers in os.walk(dossier):
                for f in fichiers:
                    if f.lower().endswith(".onnx") and f not in vus:
                        vus.add(f)
                        chemin = os.path.join(racine, f)
                        taille_mo = os.path.getsize(chemin) / (1024 * 1024)
                        fichiers_onnx.append({
                            "name": Path(f).stem,
                            "filename": f,
                            "path": chemin,
                            "size_mb": round(taille_mo, 1)
                        })
    return fichiers_onnx


def resoudre_modele_onnx(cle_ou_chemin: Optional[str], defaut_path: Optional[str] = None) -> Optional[str]:
    """Résout le chemin d'un modèle ONNX par son nom partiel ou chemin direct."""
    if not cle_ou_chemin:
        return defaut_path if defaut_path and os.path.exists(defaut_path) else None

    if os.path.exists(cle_ou_chemin):
        return os.path.abspath(cle_ou_chemin)

    dispos = lister_modeles_onnx()
    cle = cle_ou_chemin.lower()
    for m in dispos:
        if cle in m["name"].lower() or cle in m["filename"].lower():
            return m["path"]

    return defaut_path if defaut_path and os.path.exists(defaut_path) else None


def resoudre_modele_video(chemin: Optional[str] = None) -> str:
    """
    Résout le modèle vidéo DiT (Wan 2.1 / 2.2, LTX-2.3 / 2.5).
    Recherche automatiquement dans DEFAULT_MODEL_DIR si aucun chemin direct valide n'est fourni.
    """
    if chemin and os.path.exists(chemin):
        return os.path.abspath(chemin)

    # Candidats Wan 2.1 / 2.2 et LTX par ordre de priorité
    candidats = [
        "wan2.1-t2v-14b-Q4_K_M.gguf",
        "wan2.1-t2v-14b-q4_k_m.gguf",
        "LTX-2.5-Distilled-Q4_K_M.gguf",
        "wan2.1-i2v-14b-480p-Q4_K_M.gguf",
        "Wan2.2-T2V-P14B-HighNoise-Q4_K_M.gguf",
        "Wan2.2-T2V-A14B-LowNoise-Q4_K_M.gguf",
        "minimax_h3_fl2va_pruned-Q4_K_M.gguf",
        "ltx-video-2b-v0.9-Q8_0.gguf"
    ]
    for nom in candidats:
        p = os.path.join(DEFAULT_MODEL_DIR, nom)
        if os.path.exists(p):
            return p

    # Recherche floue dans DEFAULT_MODEL_DIR
    if os.path.exists(DEFAULT_MODEL_DIR):
        for f in os.listdir(DEFAULT_MODEL_DIR):
            f_lower = f.lower()
            if (f_lower.startswith("wan") or f_lower.startswith("ltx")) and f_lower.endswith((".gguf", ".safetensors")):
                if "vae" not in f_lower and "encoder" not in f_lower:
                    return os.path.join(DEFAULT_MODEL_DIR, f)

    return os.path.join(DEFAULT_MODEL_DIR, "wan2.1-t2v-14b-Q4_K_M.gguf")


def resoudre_t5xxl_video(chemin: Optional[str] = None) -> str:
    """
    Résout l'encodeur de texte UMT5-XXL pour Wan 2.1 (Q4_K_M, Q8_0 ou fp16).
    """
    if chemin and os.path.exists(chemin):
        return os.path.abspath(chemin)

    candidats = [
        "umt5-xxl-encoder-Q8_0.gguf",
        "umt5-xxl-encoder-Q4_K_M.gguf",
        "umt5-xxl-encoder-q4_k_m.gguf",
        "umt5-xxl-encoder-q8_0.gguf",
        "umt5_xxl_fp16.safetensors"
    ]
    for nom in candidats:
        p = os.path.join(DEFAULT_MODEL_DIR, nom)
        if os.path.exists(p):
            return p

    if os.path.exists(DEFAULT_MODEL_DIR):
        for f in os.listdir(DEFAULT_MODEL_DIR):
            f_lower = f.lower()
            if "umt5" in f_lower and f_lower.endswith((".gguf", ".safetensors")):
                return os.path.join(DEFAULT_MODEL_DIR, f)

    return os.path.join(DEFAULT_MODEL_DIR, "umt5-xxl-encoder-Q8_0.gguf")


def resoudre_vae_video(chemin: Optional[str] = None) -> str:
    """
    Résout le VAE vidéo Wan 2.1 / Wan 2.2.
    """
    if chemin and os.path.exists(chemin):
        return os.path.abspath(chemin)

    candidats = [
        "wan_2.1_vae.safetensors",
        "wan2.1_vae.safetensors",
        "wan2.2_vae.safetensors"
    ]
    for nom in candidats:
        p = os.path.join(DEFAULT_MODEL_DIR, nom)
        if os.path.exists(p):
            return p

    return os.path.join(DEFAULT_MODEL_DIR, "wan_2.1_vae.safetensors")


# Composants requis du paquet MiniMax-Music3 GGUF (mix par défaut Q4_0 / Q8_0)
MUSIC3_FICHIERS_REQUIS = [
    "language_model_q4_0.gguf",
    "rvq_depth_decoder_q8_0.gguf",
    "transformer_q4_0.gguf",
    "condition_encoder.gguf",
    "vocoder.gguf",
    "tokenizer/tokenizer.json",
]


def resoudre_modele_musique(chemin: Optional[str] = None) -> str:
    """
    Résout le dossier du paquet MiniMax-Music3 GGUF pour audio.cpp
    et vérifie la présence des composants requis.
    """
    candidats_dir = [chemin, DEFAULT_MUSIC3_DIR] if chemin else [DEFAULT_MUSIC3_DIR]

    # Recherche floue d'un dossier MiniMax-Music3* dans DEFAULT_MODEL_DIR
    if os.path.exists(DEFAULT_MODEL_DIR):
        for f in os.listdir(DEFAULT_MODEL_DIR):
            if "minimax-music3" in f.lower() and os.path.isdir(os.path.join(DEFAULT_MODEL_DIR, f)):
                candidats_dir.append(os.path.join(DEFAULT_MODEL_DIR, f))

    for dossier in candidats_dir:
        if dossier and os.path.isdir(dossier):
            if all(os.path.exists(os.path.join(dossier, c)) for c in MUSIC3_FICHIERS_REQUIS):
                return dossier

    return DEFAULT_MUSIC3_DIR


# Variantes ACE-Step 1.5 : (chemin relatif du GGUF, load-option dit_model_path
# ou None). Les paquets sont spécifiques à une variante — xl-* exigent leur
# load-option (docs audio.cpp). XL = DiT 4B (~14,2 Gio bf16, non testé HF :
# hébergé sur le miroir ModelScope de audio.cpp).
ACESTEP15_VARIANTES = {
    "turbo": (os.path.join("turbo", "ace-step-1.5-turbo-bf16.gguf"), None),
    "xl-turbo": (os.path.join("xl-turbo", "ace-step-1.5-xl-turbo-bf16.gguf"), "acestep-v15-xl-turbo"),
    "xl-sft": (os.path.join("xl-sft", "ace-step-1.5-xl-sft-bf16.gguf"), "acestep-v15-xl-sft"),
}


def resoudre_gguf_acestep15(variante: str = "turbo") -> str:
    """Retourne le chemin absolu du GGUF ACE-Step 1.5 pour la variante donnée."""
    if variante not in ACESTEP15_VARIANTES:
        raise ValueError(f"Variante ACE-Step inconnue : {variante} (choix : {', '.join(ACESTEP15_VARIANTES)})")
    chemin_relatif, _ = ACESTEP15_VARIANTES[variante]
    return os.path.join(DEFAULT_ACESTEP15_DIR, chemin_relatif)


def resoudre_yunet_model(chemin: Optional[str] = None) -> str:
    """Résout le chemin vers le modèle ONNX YuNet pour la détection faciale."""
    if chemin and os.path.exists(chemin):
        return os.path.abspath(chemin)
    if os.path.exists(DEFAULT_YUNET_MODEL):
        return DEFAULT_YUNET_MODEL
    for d in DEFAULT_ONNX_DIRS:
        candidat = os.path.join(d, "face_detection_yunet_2023mar.onnx")
        if os.path.exists(candidat):
            return candidat
    return DEFAULT_YUNET_MODEL


def verifier_prerequis(config: dict) -> bool:
    """Vérifie l'existence des exécutables et des modèles requis."""
    manquants = []
    
    # Exécutables
    if not os.path.exists(config.get("llama_cli", DEFAULT_LLAMA_CLI)):
        manquants.append(f"llama-cli introuvable : {config.get('llama_cli', DEFAULT_LLAMA_CLI)}")
    if not os.path.exists(config.get("sd_cli", DEFAULT_SD_CLI)):
        manquants.append(f"sd-cli introuvable : {config.get('sd_cli', DEFAULT_SD_CLI)}")
        
    # Modèles obligatoires
    fichiers_modeles = [
        ("Modèle LLM", config.get("llm_model", DEFAULT_LLM_MODEL)),
        ("Modèle Flux.1", config.get("sd_model", DEFAULT_SD_MODEL)),
        ("CLIP-L", config.get("clip_l", DEFAULT_CLIP_L)),
        ("T5XXL", config.get("t5xxl", DEFAULT_T5XXL)),
        ("VAE", config.get("vae", DEFAULT_VAE)),
    ]
    for nom, chemin in fichiers_modeles:
        if not os.path.exists(chemin):
            manquants.append(f"{nom} manquant : {chemin}")
            
    if manquants:
        print("⚠️  [Diagnostic] Fichiers manquants détectés :")
        for m in manquants:
            print(f"   - {m}")
        return False
    return True
