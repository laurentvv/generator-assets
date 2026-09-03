#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Module d'inférence LLM séquentiel via llama.cpp.
Assure l'exécution isolée et la libération totale de la VRAM après génération du prompt.
"""

import subprocess
from typing import Optional
from core.config import (
    DEFAULT_LLAMA_CLI,
    DEFAULT_LLM_MODEL,
    DEFAULT_STYLE_ANCHOR,
    CADRAGE_INSTRUCTIONS
)


def construire_prompt_coherant(
    concept: str,
    type_asset: str = "item",
    llama_cli: str = DEFAULT_LLAMA_CLI,
    llm_model: str = DEFAULT_LLM_MODEL,
    style_anchor: str = DEFAULT_STYLE_ANCHOR,
    custom_cadrage: Optional[str] = None,
    sans_llm: bool = True
) -> str:
    """
    Construit le prompt de diffusion final.
    Par défaut (sans_llm=True), le concept est transmis directement avec son cadrage et style.
    Si sans_llm=False, appelle llama.cpp en sous-processus pour enrichir le prompt.
    """
    cadrage = custom_cadrage or CADRAGE_INSTRUCTIONS.get(type_asset, "centered 2D game asset")

    # Mode direct sans LLM (comportement par défaut)
    if sans_llm:
        parties = [concept]
        if cadrage:
            parties.append(cadrage)
        if style_anchor:
            parties.append(style_anchor)
        prompt_final = ", ".join([p.strip().rstrip(",") for p in parties if p and p.strip()])
        try:
            print(f"✨ [Prompt Direct (Sans LLM)] :\n   {prompt_final}\n")
        except UnicodeEncodeError:
            print(f"[Prompt Direct (Sans LLM)] :\n   {prompt_final}\n")
        return prompt_final

    prompt_texte = (
        f"You are a professional art director and visual prompt engineer for video game assets. "
        f"Describe this asset in English concisely (max 30 words), focusing strictly on the visual appearance, material, and texture of: {concept}.\n"
        f"Description:"
    )

    try:
        print(f"🧠 [LLM] Direction artistique via llama.cpp pour '{concept}'...")
    except UnicodeEncodeError:
        print(f"[LLM] Direction artistique via llama.cpp pour '{concept}'...")

    commande_llm = [
        llama_cli,
        "-m", llm_model,
        "-p", prompt_texte,
        "-st",                    # Single-turn
        "--simple-io",            # Sortie sans fioritures
        "-n", "500",              # Budget tokens
        "--temp", "0.4",          # Faible température
        "-ngl", "99",             # Décharge GPU
        "--log-disable"           # Masque les logs internes
    ]

    try:
        resultat = subprocess.run(
            commande_llm,
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8'
        )

        sortie_brute = resultat.stdout
        if "[End thinking]" in sortie_brute:
            sortie_brute = sortie_brute.split("[End thinking]")[-1]
        elif "\n> " in sortie_brute:
            sortie_brute = sortie_brute.rsplit("\n> ", 1)[-1]
        else:
            sortie_brute = sortie_brute.replace(prompt_texte, "")

        lignes = [
            l for l in sortie_brute.splitlines()
            if l.strip()
            and not l.strip().startswith("[Start thinking]")
            and not (l.strip().startswith("[") and "t/s" in l)
        ]
        description_llm = lignes[0].strip() if lignes else concept

        prompt_final = f"{description_llm}, {cadrage}, {style_anchor}"
        try:
            print(f"✨ [Prompt Final LLM] (VRAM libérée) :\n   {prompt_final}\n")
        except UnicodeEncodeError:
            print(f"[Prompt Final LLM] (VRAM libérée) :\n   {prompt_final}\n")
        return prompt_final

    except Exception as e:
        try:
            print(f"❌ Erreur lors de l'exécution de llama.cpp : {e}")
        except UnicodeEncodeError:
            print(f"Erreur lors de l'exécution de llama.cpp : {e}")
        if hasattr(e, 'stderr') and e.stderr:
            print(f"Détails : {e.stderr}")
        print("⚠️  Repli sur le prompt conceptuel brut.")
        parties = [concept]
        if cadrage:
            parties.append(cadrage)
        if style_anchor:
            parties.append(style_anchor)
        return ", ".join([p.strip().rstrip(",") for p in parties if p and p.strip()])
