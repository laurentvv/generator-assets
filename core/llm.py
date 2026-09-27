#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sequential LLM inference module via llama.cpp.
Ensures isolated execution and full VRAM release after prompt generation.
"""

from typing import Optional

from core.config import (
    DEFAULT_LLAMA_CLI,
    DEFAULT_LLM_MODEL,
    DEFAULT_STYLE_ANCHOR,
    CADRAGE_INSTRUCTIONS
)
from core.process import run_engine


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
    Builds the final diffusion prompt.
    By default (sans_llm=True), the concept is passed through directly with its framing and style.
    If sans_llm=False, calls llama.cpp as a subprocess to enrich the prompt.
    """
    cadrage = custom_cadrage or CADRAGE_INSTRUCTIONS.get(type_asset, "centered 2D game asset")

    # Direct mode without LLM (default behavior)
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
        print(f"🧠 [LLM] Art direction via llama.cpp for '{concept}'...")
    except UnicodeEncodeError:
        print(f"[LLM] Art direction via llama.cpp for '{concept}'...")

    commande_llm = [
        llama_cli,
        "-m", llm_model,
        "-p", prompt_texte,
        "-st",                    # Single-turn
        "--simple-io",            # Plain output
        "-n", "500",              # Token budget
        "--temp", "0.4",          # Low temperature
        "-ngl", "99",             # GPU offload
        "--log-disable"           # Hides internal logs
    ]

    try:
        resultat = run_engine(
            commande_llm,
            check=True,
            timeout=600,
            etiquette="llama-cli enrichment",
        )

        sortie_brute = resultat.stdout
        if "[End thinking]" in sortie_brute:
            sortie_brute = sortie_brute.split("[End thinking]")[-1]
        elif "\n> " in sortie_brute:
            sortie_brute = sortie_brute.rsplit("\n> ", 1)[-1]
        else:
            sortie_brute = sortie_brute.replace(prompt_texte, "")

        lignes = [
            ligne for ligne in sortie_brute.splitlines()
            if ligne.strip()
            and not ligne.strip().startswith("[Start thinking]")
            and not (ligne.strip().startswith("[") and "t/s" in ligne)
        ]
        description_llm = lignes[0].strip() if lignes else concept

        prompt_final = f"{description_llm}, {cadrage}, {style_anchor}"
        try:
            print(f"✨ [Final LLM Prompt] (VRAM released):\n   {prompt_final}\n")
        except UnicodeEncodeError:
            print(f"[Final LLM Prompt] (VRAM released):\n   {prompt_final}\n")
        return prompt_final

    except Exception as e:
        try:
            print(f"❌ Error while running llama.cpp: {e}")
        except UnicodeEncodeError:
            print(f"Error while running llama.cpp: {e}")
        if hasattr(e, 'stderr') and e.stderr:
            print(f"Details: {e.stderr}")
        print("⚠️  Falling back to the raw concept prompt.")
        parties = [concept]
        if cadrage:
            parties.append(cadrage)
        if style_anchor:
            parties.append(style_anchor)
        return ", ".join([p.strip().rstrip(",") for p in parties if p and p.strip()])
