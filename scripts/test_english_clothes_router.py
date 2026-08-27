# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.clothes_catalog import aiguiller_modele_vetement

prompts = [
    "rustic medieval peasant farmer overalls with linen fabric",
    "heavy combat leather boots",
    "elegant evening tuxedo and blazer for business",
    "casual streetwear hoodie and jeans",
    "adventurer brown fedora hat",
    "sporty gym athletic tracksuit",
    "woman chic casual everyday shirt and denim"
]

print("=== TEST AIGUILLAGE PROMPTS EN ANGLAIS ===")
for p in prompts:
    res = aiguiller_modele_vetement(p)
    print(f"🔹 '{p}' \n   ➔ ID: {res['id']} | Nom: {res['name']} | Catégorie: {res['category']}\n")
