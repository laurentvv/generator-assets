#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Workflow Music BG : Boucles Musicales IA en Fond Sonore (MiniMax-Music3 via audio.cpp Vulkan).
Produit :
- Boucle sans couture WAV 48 kHz PCM16 (alignée BPM/mesures ou crossfade ambiante)
- Version « bed » normalisée (défaut -30 LUFS) prête derrière une voix off
- Aperçus OGG (boucle Godot/lecture) et MP3 192k
- Recette ffmpeg de ducking (sidechaincompress) pour mixer sous une voix
- QA optionnelle par Music Flamingo (llama-cli, analyse uniquement, licence non commerciale)
"""

import os
import shutil
from typing import Any, Dict, List

import numpy as np
import soundfile

from core.config import DEFAULT_OUTPUT_DIR, slugifier_texte
from core.music_ai import (
    SR_CIBLE,
    analyser_boucle_flamingo,
    charger_audio,
    construire_recette_ducking,
    convertir_mp3,
    convertir_ogg,
    empreinte_fichier,
    exporter_bed_lufs,
    fabriquer_boucle,
    generer_musique_music3,
    mesurer_lufs,
    normaliser_pic,
    post_traiter_lit_voix,
    resoudre_audiocpp,
    ressampler,
    verifier_boucle,
)
from workflows.base import BaseWorkflow, WorkflowRegistry

# Prompt par défaut : boucle « tech » discrète pour fond YouTube derrière une voix
PROMPT_TECH_DEFAUT = (
    "subtle minimal techno groove, soft pulsing analog synth bass, muffled kick, "
    "airy hi-hats, clean dark pads, instrumental only, steady understated momentum, no vocals"
)


@WorkflowRegistry.register
class MusicBgWorkflow(BaseWorkflow):
    """Génération de boucles musicales IA (MiniMax-Music3 GGUF, Vulkan) calibrées comme fond sonore derrière une voix off."""

    name = "music_bg"
    description = "Boucles musicales IA « tech » en fond sonore YouTube (MiniMax-Music3 GGUF Vulkan + bed -30 LUFS + recette ducking)"

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        prompt = params.get("prompt") or PROMPT_TECH_DEFAUT
        # Le flag CLI --duration a un défaut bas (2 s) : toute valeur < 4 s = non renseignée
        duree = float(params.get("duration") or 12.0)
        if duree < 4.0:
            duree = 12.0
        etapes = int(params.get("steps") or 30)
        backend = params.get("music_backend") or "vulkan"
        lufs_cible = float(params.get("lufs") or -30.0)
        loop_mode = params.get("loop_mode") or "percussive"
        analyse = bool(params.get("analyse"))
        nb_candidats = max(1, min(int(params.get("candidats") or 3), 12))
        lyrics = params.get("lyrics") or "[Instrumental]"
        graine = int(params.get("seed") if params.get("seed") is not None else -1)
        nom_base = params.get("output") or f"{slugifier_texte(prompt)}_loop"

        output_dir = params.get("output_dir") or ""
        if not output_dir or output_dir == DEFAULT_OUTPUT_DIR:
            output_dir = "output/music_bg"
        os.makedirs(output_dir, exist_ok=True)

        exe = resoudre_audiocpp()
        if not os.path.exists(exe):
            raise FileNotFoundError(
                f"audiocpp_cli.exe introuvable : {exe}\n"
                "→ Lancez : uv run python scripts/download_music3_gguf.py"
            )

        self.log(f"Moteur : audio.cpp ({os.path.basename(exe)}) • backend={backend} • {nb_candidats} candidat(s)")
        self.log(f"Prompt : « {prompt} »")
        self.log(f"Cible : boucle {duree:.0f} s • mode={loop_mode} • bed {lufs_cible:.0f} LUFS")

        # ------------------------------------------------------------------
        # 1. Génération des candidats (marge +3 s pour l'alignement mesures)
        # ------------------------------------------------------------------
        dossier_bruts = os.path.join(output_dir, "candidats")
        os.makedirs(dossier_bruts, exist_ok=True)
        duree_generation = duree + 3.0
        empreintes_vues = set()
        bruts: List[Dict[str, Any]] = []

        for i in range(1, nb_candidats + 1):
            chemin_brut = os.path.join(dossier_bruts, f"cand_{i}_brut.wav")
            self.log(f"Génération candidat {i}/{nb_candidats} ({duree_generation:.0f} s)...", emoji="🎵")
            graine_i = graine + i - 1 if graine >= 0 else -1
            chemin, backend_utilise = generer_musique_music3(
                description=prompt,
                chemin_sortie=chemin_brut,
                duree=duree_generation,
                etapes=etapes,
                backend=backend,
                lyrics=lyrics,
                graine=graine_i,
                log=lambda m: self.log(m, emoji="   "),
            )

            empreinte = empreinte_fichier(chemin)
            if empreinte in empreintes_vues and graine_i < 0:
                self.log("Candidat identique au précédent (graine non pilotée) — arrêt des générations.", emoji="♻️")
                os.remove(chemin)
                break
            empreintes_vues.add(empreinte)
            bruts.append({"index": i, "chemin": chemin, "backend": backend_utilise})

        if not bruts:
            raise RuntimeError("Aucun candidat généré.")

        # ------------------------------------------------------------------
        # 2. Bouclage + post-traitement + validation de chaque candidat
        # ------------------------------------------------------------------
        candidats: List[Dict[str, Any]] = []
        for brut in bruts:
            i = brut["index"]
            self.log(f"Bouclage & post-traitement du candidat {i}...", emoji="🔊")
            audio, sr = charger_audio(brut["chemin"])
            boucle, infos_boucle = fabriquer_boucle(audio, sr, duree_cible=duree, mode=loop_mode)
            boucle = post_traiter_lit_voix(boucle, sr)
            boucle, sr = ressampler(boucle, sr, SR_CIBLE)
            boucle = normaliser_pic(boucle, -1.0)

            chemin_full = os.path.join(dossier_bruts, f"cand_{i}_loop_full.wav")
            soundfile.write(chemin_full, boucle, sr, subtype="PCM_16")

            verification = verifier_boucle(chemin_full)
            mesures = mesurer_lufs(chemin_full)
            bpm_txt = f"{infos_boucle['bpm']:.0f} BPM" if infos_boucle.get("bpm") else "ambiante"
            self.log(
                f"Candidat {i} : {bpm_txt}, {infos_boucle['duree']:.1f} s, "
                f"couture Δ{verification['ecart_couture_db']} dB, "
                f"LUFS {mesures['I']:.1f}, pic {verification['pic_dbfs']} dBFS"
                f"{' ⚠️' if not verification['propre'] else ' ✅'}"
            )
            candidats.append({
                "index": i,
                "chemin": chemin_full,
                "brut": brut["chemin"],
                "backend": brut["backend"],
                "boucle": infos_boucle,
                "verification": verification,
                "lufs": mesures,
            })

        # ------------------------------------------------------------------
        # 3. Sélection du meilleur candidat (propreté puis couture minimale)
        # ------------------------------------------------------------------
        candidats_valides = [c for c in candidats if c["verification"]["propre"]]
        pool = candidats_valides or candidats
        meilleur = min(pool, key=lambda c: c["verification"]["ecart_couture_db"])
        self.log(
            f"Meilleur candidat : #{meilleur['index']} "
            f"(couture Δ{meilleur['verification']['ecart_couture_db']} dB)",
            emoji="🏆",
        )

        # ------------------------------------------------------------------
        # 4. Exports finaux : chaque candidat est finalisé (bed LUFS + MP3),
        #    le meilleur est promu au niveau racine
        # ------------------------------------------------------------------
        wav_full = os.path.join(output_dir, f"{nom_base}_full.wav")
        shutil.copyfile(meilleur["chemin"], wav_full)
        bed = os.path.join(output_dir, f"{nom_base}_bed.wav")
        mesures_bed = exporter_bed_lufs(wav_full, bed, lufs_cible)
        ogg = convertir_ogg(bed, os.path.join(output_dir, f"{nom_base}.ogg"))
        mp3 = convertir_mp3(bed, os.path.join(output_dir, f"{nom_base}_preview.mp3"))

        self.log(f"Bed normalisé : {mesures_bed['I']:.1f} LUFS (cible {lufs_cible:.0f}) • TP {mesures_bed['TP']:.1f} dBTP")

        fichiers_finale = [wav_full, bed, ogg, mp3]
        for cand in candidats:
            if cand["index"] == meilleur["index"]:
                cand["bed"] = bed
                cand["mp3"] = mp3
                continue
            bed_c = os.path.join(dossier_bruts, f"cand_{cand['index']}_bed.wav")
            mesures_c = exporter_bed_lufs(cand["chemin"], bed_c, lufs_cible)
            mp3_c = convertir_mp3(bed_c, os.path.join(dossier_bruts, f"cand_{cand['index']}_preview.mp3"))
            cand["bed"] = bed_c
            cand["mp3"] = mp3_c
            fichiers_finale += [bed_c, mp3_c]
            self.log(
                f"Candidat {cand['index']} finalisé : {os.path.basename(bed_c)} "
                f"({mesures_c['I']:.1f} LUFS)"
            )

        # ------------------------------------------------------------------
        # 5. QA optionnelle Music Flamingo
        # ------------------------------------------------------------------
        resultat_analyse = None
        if analyse:
            self.log("Analyse Music Flamingo (QA) du bed sélectionné...", emoji="🧠")
            resultat_analyse = analyser_boucle_flamingo(bed, log=lambda m: self.log(m, emoji="   "))
            if resultat_analyse:
                self.log(f"Verdict : {resultat_analyse}")

        # ------------------------------------------------------------------
        # 6. Recette de mixage sous voix off (ducking automatique)
        # ------------------------------------------------------------------
        recette = construire_recette_ducking("voix_off.wav", os.path.basename(bed), "mix_final.wav")
        chemin_recette = os.path.join(output_dir, "recette_mixage_voix.txt")
        with open(chemin_recette, "w", encoding="utf-8") as f:
            f.write(
                "RECETTE : mixage de la boucle sous une voix off (ducking automatique)\n"
                "=====================================================================\n\n"
                "1) Placez ce fichier à côté de votre voix off : voix_off.wav\n"
                "2) Lancez la commande :\n\n"
                f"    {recette}\n\n"
                "3) Résultat : mix_final.wav — la boucle est répétée à la durée de la\n"
                "   voix et atténuée automatiquement dès que la voix parle.\n"
                "   Ajustements :\n"
                "   - musique trop présente → abaisser volume=1.0 (ex: 0.7)\n"
                "   - ducking plus marqué → ratio=8 et/ou threshold=0.03\n"
                "   - retour plus rapide après la voix → release=350\n"
            )

        self.log(f"Exports finaux dans '{output_dir}/' :", emoji="🎉")
        self.log(f"  • Boucle complète : {wav_full}")
        self.log(f"  • Bed {mesures_bed['I']:.1f} LUFS   : {bed}")
        self.log(f"  • OGG boucle       : {ogg}")
        self.log(f"  • MP3 aperçu       : {mp3}")
        self.log(f"  • {len(candidats)} boucles finalisées (bed + MP3) dans 'candidats/'", emoji="🎵")
        self.log(f"  • Recette ducking  : {chemin_recette}", emoji="💎")

        return {
            "wav_full": wav_full,
            "bed": bed,
            "ogg": ogg,
            "mp3": mp3,
            "recette_ducking": chemin_recette,
            "bpm": meilleur["boucle"].get("bpm"),
            "duree_boucle": meilleur["boucle"]["duree"],
            "strategie": meilleur["boucle"]["strategie"],
            "backend": meilleur["backend"],
            "lufs_bed": mesures_bed["I"],
            "analyse_flamingo": resultat_analyse,
            "candidats": [
                {"index": c["index"], "couture_db": c["verification"]["ecart_couture_db"],
                 "bpm": c["boucle"].get("bpm"), "lufs": c["lufs"]["I"],
                 "bed": c["bed"], "mp3": c["mp3"]}
                for c in candidats
            ],
            "files": fichiers_finale + [chemin_recette],
        }
