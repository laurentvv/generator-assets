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

# Dossiers et Modèles de base
DEFAULT_MODEL_DIR = os.getenv("MODEL_DIR", r"C:\Modeles_LLM")
DEFAULT_LLM_MODEL = os.getenv("LLM_MODEL_PATH", os.path.join(DEFAULT_MODEL_DIR, "LFM2.5-8B-A1B-Q6_K.gguf"))
DEFAULT_SD_MODEL = os.getenv("SD_MODEL_PATH", os.path.join(DEFAULT_MODEL_DIR, "flux1-dev-Q6_K.gguf"))
DEFAULT_CLIP_L = os.getenv("SD_CLIP_L_PATH", os.path.join(DEFAULT_MODEL_DIR, "clip_l.safetensors"))
DEFAULT_T5XXL = os.getenv("SD_T5XXL_PATH", os.path.join(DEFAULT_MODEL_DIR, "t5xxl_fp16.safetensors"))
DEFAULT_VAE = os.getenv("SD_VAE_PATH", os.path.join(DEFAULT_MODEL_DIR, "ae.safetensors"))

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

# Paramètres de rendu
DEFAULT_BACKEND = os.getenv("SD_BACKEND", "diffusion=vulkan0,te=cpu")
DEFAULT_THREADS = int(os.getenv("SD_THREADS", "16"))
DEFAULT_OUTPUT_DIR = os.getenv("OUTPUT_DIR", "godot_assets")
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
