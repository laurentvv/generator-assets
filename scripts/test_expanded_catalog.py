# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.clothes_catalog import charger_catalogue, aiguiller_modele_vetement

cat = charger_catalogue()
print(f"Total modèles indexés : {len(cat)}")

test_prompts = [
    "medieval leather boots",
    "medieval tunic peasant",
    "knight armor plate",
    "viking beard",
    "wizard robe",
    "long skirt female",
    "vintage hat",
    "casual jeans and t-shirt",
    "cowboy boots",
    "short female hair"
]

print("\n=== TEST DE RECHERCHE SÉMANTIQUE SUR LES 177 ASSETS ===")
for p in test_prompts:
    res = aiguiller_modele_vetement(p)
    if res:
        print(f"🎯 '{p}' \n   ➔ ID: {res['id']} | Nom: {res['name']} | Catégorie: {res['category']}\n")
