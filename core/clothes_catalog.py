# -*- coding: utf-8 -*-
"""
clothes_catalog.py
Indexateur & Moteur d'aiguillage IA bilingue (FR / EN) pour les vêtements MakeHuman / MPFB.
1. Scanne et parse les répertoires de vêtements MakeHuman (.mhclo, .mhmat, .thumb, .obj).
2. Construit une base de connaissances structurée (JSON) avec tags, catégories, genre et métadonnées en français et en anglais.
3. Permet au LLM ou au moteur sémantique d'aiguiller automatiquement
   n'importe quel prompt utilisateur (FR/EN) vers le meilleur modèle 3D existant.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import DEFAULT_MPFB_DATA_DIR

DEFAULT_CATALOG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "clothes_catalog.json")

STOP_WORDS = {
    "the", "a", "an", "and", "or", "with", "in", "on", "of", "for", "by", "to",
    "le", "la", "les", "un", "une", "des", "et", "ou", "avec", "dans", "sur", "de", "pour", "par"
}

def parser_fichier_mhclo(mhclo_path: str) -> Dict[str, Any]:
    """Extrait les métadonnées clés d'un fichier .mhclo."""
    metadata = {
        "name": "",
        "tags": [],
        "category": "clothes",
        "gender": "unisex",
        "obj_file": "",
        "material": "",
        "z_depth": 50
    }
    if not os.path.exists(mhclo_path):
        return metadata

    with open(mhclo_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("name "):
                metadata["name"] = line.split("name ", 1)[1].strip()
            elif line.startswith("tag "):
                tag_val = line.split("tag ", 1)[1].strip()
                if tag_val not in ["MakeHuman™", "MakeHuman(TM)", "MakeHuman"]:
                    metadata["tags"].append(tag_val)
                    tag_lower = tag_val.lower()
                    if tag_lower in ["male", "homme", "man", "men"]:
                        metadata["gender"] = "male"
                    elif tag_lower in ["female", "femme", "woman", "women"]:
                        metadata["gender"] = "female"
                    elif tag_lower in ["shoes", "chaussures", "boots", "bottes", "footwear"]:
                        metadata["category"] = "shoes"
                    elif tag_lower in ["hat", "hats", "chapeau", "casquette", "headwear"]:
                        metadata["category"] = "hat"
            elif line.startswith("obj_file "):
                metadata["obj_file"] = line.split("obj_file ", 1)[1].strip()
            elif line.startswith("material "):
                metadata["material"] = line.split("material ", 1)[1].strip()
            elif line.startswith("z_depth "):
                try:
                    metadata["z_depth"] = int(line.split("z_depth ", 1)[1].strip())
                except ValueError:
                    pass
            elif line.startswith("verts "):
                break
    return metadata

def construire_catalogue_vetements(mpfb_data_dir: str = DEFAULT_MPFB_DATA_DIR, output_json: str = DEFAULT_CATALOG_PATH) -> Dict[str, Any]:
    """Scanne tous les dossiers de vêtements et génère le catalogue JSON indexé bilingue (FR/EN)."""
    dossiers_a_scanner = [
        os.path.join(mpfb_data_dir, "data", "clothes"),
        os.path.join(mpfb_data_dir, "clothes")
    ]
    catalog = {}

    for dossier_base in dossiers_a_scanner:
        if not os.path.exists(dossier_base):
            continue
        for item_name in os.listdir(dossier_base):
            item_path = os.path.join(dossier_base, item_name)
            if not os.path.isdir(item_path):
                continue
            
            # Recherche du .mhclo
            mhclo_file = os.path.join(item_path, f"{item_name}.mhclo")
            if not os.path.exists(mhclo_file):
                mhclos = list(Path(item_path).glob("*.mhclo"))
                if mhclos:
                    mhclo_file = str(mhclos[0])
                else:
                    continue

            meta = parser_fichier_mhclo(mhclo_file)
            
            # Détection de la catégorie par le nom si absent des tags
            nom_lower = item_name.lower()
            if "shoe" in nom_lower or "boot" in nom_lower:
                meta["category"] = "shoes"
            elif "hat" in nom_lower or "fedora" in nom_lower or "cap" in nom_lower:
                meta["category"] = "hat"
            elif "suit" in nom_lower or "worksuit" in nom_lower or "casual" in nom_lower:
                meta["category"] = "suit"
            elif "torso" in nom_lower or "top" in nom_lower or "shirt" in nom_lower or "tunic" in nom_lower:
                meta["category"] = "torso"
            elif "pant" in nom_lower or "trousers" in nom_lower:
                meta["category"] = "pants"

            if "male_" in nom_lower:
                meta["gender"] = "male"
            elif "female_" in nom_lower:
                meta["gender"] = "female"

            # Fichiers associés
            diffuse_files = list(Path(item_path).glob("*diffuse*.png")) + list(Path(item_path).glob("*_diffuse.png"))
            thumb_files = list(Path(item_path).glob("*.thumb")) + list(Path(item_path).glob("*.png"))
            obj_files = list(Path(item_path).glob("*.obj"))

            diffuse_path = str(diffuse_files[0]) if diffuse_files else ""
            thumb_path = str(thumb_files[0]) if thumb_files else ""
            obj_path = str(obj_files[0]) if obj_files else ""

            # Enrichissement bilingue exhaustif des mots-clés (FR + EN)
            keywords = [item_name, meta["category"], meta["gender"]] + meta["tags"]
            
            # Mots-clés de genre
            if meta["gender"] == "male":
                keywords.extend(["male", "man", "men", "boy", "homme", "garcon", "masculin"])
            elif meta["gender"] == "female":
                keywords.extend(["female", "woman", "women", "girl", "femme", "fille", "feminin"])

            # Mots-clés par type de vêtement (Bilingue EN / FR)
            if "worksuit" in nom_lower:
                keywords.extend([
                    "worksuit", "overalls", "dungarees", "dungaree", "jumpsuit", "apron", "boiler suit",
                    "peasant", "farmer", "worker", "laborer", "craftsman", "artisan", "rustic", "medieval", "tunic",
                    "salopette", "paysan", "artisan", "ouvrier", "fermier", "rural", "tunique", "chanvre", "burlap", "linen"
                ])
            elif "casualsuit" in nom_lower:
                keywords.extend([
                    "casual", "everyday", "streetwear", "modern", "tshirt", "t-shirt", "tee", "shirt", "jeans", "denim",
                    "pants", "trousers", "jacket", "hoodie", "chemise", "pantalon", "coton", "tenue"
                ])
            elif "elegantsuit" in nom_lower:
                keywords.extend([
                    "elegant", "formal", "suit", "tuxedo", "blazer", "jacket", "coat", "noble", "aristocrat", "business",
                    "dress", "costume", "veste", "chic", "gilet", "cravate", "soiree"
                ])
            elif "sportsuit" in nom_lower:
                keywords.extend([
                    "sport", "sportswear", "tracksuit", "jogging", "athletic", "gym", "sweatpants", "training",
                    "survetement", "fitness"
                ])
            elif "shoes" in nom_lower:
                keywords.extend([
                    "shoes", "shoe", "boots", "boot", "leather", "footwear", "sneakers", "combat boots", "work boots",
                    "moccasins", "loafers", "sandals", "heels", "bottes", "botte", "chaussures", "chaussure", "cuir", "souliers"
                ])
            elif "fedora" in nom_lower:
                keywords.extend([
                    "hat", "fedora", "cap", "headwear", "headpiece", "adventurer", "cowboy", "bowler", "vintage hat",
                    "chapeau", "casquette", "couvre-chef"
                ])

            catalog[item_name] = {
                "id": item_name,
                "name": meta["name"] or item_name,
                "category": meta["category"],
                "gender": meta["gender"],
                "tags": list(set(meta["tags"])),
                "keywords": list(set(keywords)),
                "z_depth": meta["z_depth"],
                "mhclo_path": mhclo_file,
                "obj_path": obj_path,
                "diffuse_path": diffuse_path,
                "thumb_path": thumb_path,
                "directory": item_path
            }

    os.makedirs(os.path.dirname(output_json), exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=4, ensure_ascii=False)

    print(f"✅ Catalogue de {len(catalog)} vêtements MakeHuman indexé dans : {output_json}")
    return catalog

def charger_catalogue(catalog_path: str = DEFAULT_CATALOG_PATH) -> Dict[str, Any]:
    """Charge le catalogue depuis le JSON, ou le reconstruit s'il n'existe pas."""
    if not os.path.exists(catalog_path):
        return construire_catalogue_vetements(output_json=catalog_path)
    try:
        with open(catalog_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return construire_catalogue_vetements(output_json=catalog_path)

def aiguiller_modele_vetement(
    concept: str,
    category: Optional[str] = None,
    gender: Optional[str] = None,
    catalog_path: str = DEFAULT_CATALOG_PATH
) -> Optional[Dict[str, Any]]:
    """
    Trouve le meilleur modèle 3D de vêtement correspondant au concept demandé (supporte les prompts en EN et en FR).
    Effectue un scoring sémantique et pondéré sur les mots-clés bilingues.
    """
    catalog = charger_catalogue(catalog_path)
    if not catalog:
        return None

    # Extraction des tokens en ignorant la ponctuation et les mots vides
    raw_tokens = re.findall(r"[a-zA-Z0-9_\-]+", concept.lower())
    concept_tokens = [t for t in raw_tokens if t not in STOP_WORDS and len(t) > 1]

    # Détection automatique du genre depuis le prompt si non fourni explicitement
    if not gender:
        if any(t in ["woman", "women", "female", "girl", "femme", "fille", "dame"] for t in concept_tokens):
            gender = "female"
        elif any(t in ["man", "men", "male", "boy", "homme", "garcon", "gars"] for t in concept_tokens):
            gender = "male"

    # Détection automatique de la catégorie depuis le prompt si non fournie
    if not category:
        if any(t in ["shoe", "shoes", "boot", "boots", "footwear", "sneakers", "bottes", "chaussures", "souliers"] for t in concept_tokens):
            category = "shoes"
        elif any(t in ["hat", "hats", "cap", "caps", "fedora", "headwear", "chapeau", "casquette"] for t in concept_tokens):
            category = "hat"

    meilleur_score = -1
    meilleur_item = None

    for item_id, item in catalog.items():
        score = 0
        
        # Filtre de genre strict si déterminé
        if gender and item["gender"] != "unisex" and item["gender"] != gender.lower():
            continue
            
        # Filtre de catégorie strict si déterminé
        if category and item["category"] != category.lower():
            continue

        item_keywords = [k.lower() for k in item["keywords"]]
        for token in concept_tokens:
            for kw in item_keywords:
                if token == kw:
                    score += 6
                elif token in kw or kw in token:
                    score += 2

        if score > meilleur_score:
            meilleur_score = score
            meilleur_item = item

    # Fallback si score nul
    if not meilleur_item or meilleur_score <= 0:
        if category == "shoes":
            return catalog.get("shoes01")
        elif category == "hat":
            return catalog.get("fedora01")
        elif gender == "female":
            return catalog.get("female_casualsuit01")
        else:
            return catalog.get("male_worksuit01") or catalog.get("male_casualsuit01")

    return meilleur_item

if __name__ == "__main__":
    construire_catalogue_vetements()
