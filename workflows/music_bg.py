#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Music BG Workflow: AI Background Music Loops (audio.cpp Vulkan).
Available engines: MiniMax-Music3 (default) or ACE-Step 1.5 Turbo (MIT,
BPM/key/measure constraints enforceable on the planner).
Produces:
- Seamless WAV 48 kHz PCM16 loop (BPM/measure-aligned or ambient crossfade)
- Normalized "bed" version (default -30 LUFS) ready behind a voice-over
- OGG previews (Godot loop/playback) and 192k MP3
- ffmpeg ducking recipe (sidechaincompress) to mix under a voice
- Optional QA by Music Flamingo (llama-cli, analysis only, non-commercial licence)
"""

import os
import shutil
from typing import Any, Dict, List

import soundfile

from core.config import ACESTEP15_VARIANTES, DEFAULT_OUTPUT_DIR, slugifier_texte
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
    generer_musique_acestep,
    generer_musique_music3,
    mesurer_lufs,
    normaliser_pic,
    post_traiter_lit_voix,
    resoudre_audiocpp,
    ressampler,
    verifier_boucle,
)
from workflows.base import BaseWorkflow, WorkflowRegistry

# Default prompt: discreet "tech" loop for a YouTube background behind a voice
PROMPT_TECH_DEFAUT = (
    "subtle minimal techno groove, soft pulsing analog synth bass, muffled kick, "
    "airy hi-hats, clean dark pads, instrumental only, steady understated momentum, no vocals"
)

MOTEURS = {
    "music3": "MiniMax-Music3 GGUF (audio.cpp)",
    "acestep": "ACE-Step 1.5 Turbo bf16 GGUF (audio.cpp)",
}


@WorkflowRegistry.register
class MusicBgWorkflow(BaseWorkflow):
    """Generation of AI music loops (MiniMax-Music3 or ACE-Step 1.5 GGUF, Vulkan) calibrated as background behind a voice-over."""

    name = "music_bg"
    description = "\"Tech\" AI music loops as YouTube background (MiniMax-Music3 / ACE-Step 1.5 GGUF Vulkan + -30 LUFS bed + ducking recipe)"

    emoji = "🎵"

    # CLI declarations (audit §2.2, migration from cli/parser.py's flat table:
    # help/defaults kept as-is, unchanged surface). Shared flags of the
    # audio family hosted here: --moteur (also voix_off), --variante (also
    # chanson/musique_adn), --music-backend (also musique_essence/retrait_voix/
    # voix_off), --tonalite and --lyrics (also musique_adn). ⚠️ --force-bpm exposes
    # dest=force_bpm but the run reads bpm_force: historical mismatch, to be fixed
    # only with user validation (the flag is currently inert).
    PARAMETRES = [
        dict(flags=("--lufs",), type=float, default=None,
             help="Target LUFS of the \"bed\" music bed for music_bg (workflow default: -30)."),
        dict(flags=("--loop-mode",), choices=["percussive", "ambient"], default="percussive",
             help="music_bg looping strategy (default: percussive, BPM-aligned)."),
        dict(flags=("--music-backend",), choices=["vulkan", "cpu", "auto", "sam"], default="vulkan",
             help="audio.cpp backend for music_bg (default: vulkan); retrait_voix also accepts 'sam' = SAM Audio text-prompted separation (CPU, scratch-master engine until the next audio.cpp release)."),
        dict(flags=("--moteur",), choices=["acestep", "music3", "qwen3", "voxcpm2", "fish"], default="acestep",
             help="Engine: music_bg → acestep (default, ACE-Step 1.5) | music3 ; voix_off → qwen3 (cloning+instruct, Apache-2.0) | voxcpm2 (cloning without transcript, Apache-2.0) | fish (expression tags, research licence)."),
        dict(flags=("--variante",), choices=["turbo", "xl-turbo", "xl-sft"], default=None,
             help="ACE-Step variant: default = turbo for music_bg, xl-turbo for chanson/musique_adn (vocal quality, validated recipes); turbo = distilled DiT 2B, xl-turbo = distilled DiT 4B (~1.8x slower), xl-sft = DiT 4B with CFG."),
        dict(flags=("--force-bpm",), type=int, default=None,
             help="Force the tempo (ACE-Step only) — e.g.: 124."),
        dict(flags=("--tonalite",), default=None,
             help="Force the key (ACE-Step only) — e.g.: A minor."),
        dict(flags=("--mesure",), default=None,
             help="Force the time signature (ACE-Step only) — e.g.: 4/4."),
        dict(flags=("--candidats",), type=int, default=3,
             help="Number of music_bg candidates to generate then rank (default: 3)."),
        dict(flags=("--lyrics",), default="[Instrumental]",
             help="Lyrics/structure for music_bg (default: [Instrumental])."),
        dict(flags=("--analyse",), action="store_true",
             help="Enables Music Flamingo QA on the selected bed (music_bg)."),
    ]

    def run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        prompt = params.get("prompt") or PROMPT_TECH_DEFAUT
        # The --duration CLI flag has a low default (2 s): any value < 4 s = not provided
        duree = float(params.get("duration") or 12.0)
        if duree < 4.0:
            duree = 12.0
        etapes = int(params.get("steps") or 0)
        # Default: ACE-Step 1.5 (validated as better quality by the user on
        # 2026-09-05, ~36x faster, MIT, native 48 kHz). Music3 remains
        # available via --moteur music3.
        moteur = params.get("moteur") or "acestep"
        if moteur not in MOTEURS:
            raise ValueError(f"Unknown engine: {moteur} (choices: {', '.join(MOTEURS)})")
        variante = params.get("variante") or "turbo"
        if variante not in ACESTEP15_VARIANTES:
            raise ValueError(f"Unknown ACE-Step variant: {variante} (choices: {', '.join(ACESTEP15_VARIANTES)})")
        if etapes <= 0:
            # Distilled variants (turbo): 8 steps; xl-sft (CFG) asks for
            # more; Music3: 30 steps
            if moteur == "music3":
                etapes = 30
            else:
                etapes = 8 if variante != "xl-sft" else 25
        # Musical constraints (ACE-Step only: enforced on the LM planner)
        bpm_force = params.get("bpm_force")
        tonalite = params.get("tonalite") or None
        mesure = params.get("mesure") or None
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
            script = "download_acestep15_gguf.py" if moteur == "acestep" else "download_music3_gguf.py"
            raise FileNotFoundError(
                f"audiocpp_cli.exe not found: {exe}\n"
                f"→ Run: uv run python scripts/{script}"
            )

        self.log(f"Engine: {MOTEURS[moteur]}{f' • variant {variante}' if moteur == 'acestep' and variante != 'turbo' else ''} • backend={backend} • {nb_candidats} candidate(s)")
        self.log(f"Prompt: \"{prompt}\"")
        contraintes = []
        if bpm_force:
            contraintes.append(f"{int(bpm_force)} BPM")
        if tonalite:
            contraintes.append(tonalite)
        if mesure:
            contraintes.append(mesure)
        if contraintes:
            if moteur != "acestep":
                self.log("⚠️ enforced bpm/key/measure: ignored by MiniMax-Music3 (ACE-Step only).")
            else:
                self.log(f"Constraints enforced on the planner: {' • '.join(contraintes)}")
        self.log(f"Target: {duree:.0f} s loop • mode={loop_mode} • bed {lufs_cible:.0f} LUFS")

        # ------------------------------------------------------------------
        # 1. Candidate generation (+3 s headroom for measure alignment)
        # ------------------------------------------------------------------
        dossier_bruts = os.path.join(output_dir, "candidats")
        os.makedirs(dossier_bruts, exist_ok=True)
        # Headroom for measure alignment: ACE-Step ends its pieces with a
        # long fade-out (~4-6 s) → large headroom (the engine is ~40x faster
        # than Music3, the cost is negligible).
        duree_generation = duree + (8.0 if moteur == "acestep" else 3.0)
        empreintes_vues = set()
        bruts: List[Dict[str, Any]] = []

        for i in range(1, nb_candidats + 1):
            chemin_brut = os.path.join(dossier_bruts, f"cand_{i}_brut.wav")
            self.log(f"Generating candidate {i}/{nb_candidats} ({duree_generation:.0f} s)...", emoji="🎵")
            graine_i = graine + i - 1 if graine >= 0 else -1
            if moteur == "acestep":
                chemin, backend_utilise = generer_musique_acestep(
                    description=prompt,
                    chemin_sortie=chemin_brut,
                    duree=duree_generation,
                    etapes=etapes,
                    backend=backend,
                    lyrics=lyrics,
                    graine=graine_i,
                    bpm=bpm_force,
                    tonalite=tonalite,
                    mesure=mesure,
                    variante=variante,
                    log=lambda m: self.log(m, emoji="   "),
                )
            else:
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
                self.log("Candidate identical to the previous one (unseeded) — stopping the generations.", emoji="♻️")
                os.remove(chemin)
                break
            empreintes_vues.add(empreinte)
            bruts.append({"index": i, "chemin": chemin, "backend": backend_utilise})

        if not bruts:
            raise RuntimeError("No candidate generated.")

        # ------------------------------------------------------------------
        # 2. Looping + post-processing + validation of each candidate
        # ------------------------------------------------------------------
        candidats: List[Dict[str, Any]] = []
        for brut in bruts:
            i = brut["index"]
            self.log(f"Looping & post-processing of candidate {i}...", emoji="🔊")
            audio, sr = charger_audio(brut["chemin"])
            boucle, infos_boucle = fabriquer_boucle(audio, sr, duree_cible=duree, mode=loop_mode)
            boucle = post_traiter_lit_voix(boucle, sr)
            boucle, sr = ressampler(boucle, sr, SR_CIBLE)
            boucle = normaliser_pic(boucle, -1.0)

            chemin_full = os.path.join(dossier_bruts, f"cand_{i}_loop_full.wav")
            soundfile.write(chemin_full, boucle, sr, subtype="PCM_16")

            verification = verifier_boucle(chemin_full)
            mesures = mesurer_lufs(chemin_full)
            bpm_txt = f"{infos_boucle['bpm']:.0f} BPM" if infos_boucle.get("bpm") else "ambient"
            self.log(
                f"Candidate {i}: {bpm_txt}, {infos_boucle['duree']:.1f} s, "
                f"seam Δ{verification['ecart_couture_db']} dB, "
                f"LUFS {mesures['I']:.1f}, peak {verification['pic_dbfs']} dBFS"
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
        # 3. Best-candidate selection (cleanliness first, then minimal seam)
        # ------------------------------------------------------------------
        candidats_valides = [c for c in candidats if c["verification"]["propre"]]
        pool = candidats_valides or candidats
        meilleur = min(pool, key=lambda c: c["verification"]["ecart_couture_db"])
        self.log(
            f"Best candidate: #{meilleur['index']} "
            f"(seam Δ{meilleur['verification']['ecart_couture_db']} dB)",
            emoji="🏆",
        )

        # ------------------------------------------------------------------
        # 4. Final exports: every candidate is finalized (LUFS bed + MP3),
        #    the best one is promoted to the root level
        # ------------------------------------------------------------------
        wav_full = os.path.join(output_dir, f"{nom_base}_full.wav")
        shutil.copyfile(meilleur["chemin"], wav_full)
        bed = os.path.join(output_dir, f"{nom_base}_bed.wav")
        mesures_bed = exporter_bed_lufs(wav_full, bed, lufs_cible)
        ogg = convertir_ogg(bed, os.path.join(output_dir, f"{nom_base}.ogg"))
        mp3 = convertir_mp3(bed, os.path.join(output_dir, f"{nom_base}_preview.mp3"))

        self.log(f"Normalized bed: {mesures_bed['I']:.1f} LUFS (target {lufs_cible:.0f}) • TP {mesures_bed['TP']:.1f} dBTP")

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
                f"Candidate {cand['index']} finalized: {os.path.basename(bed_c)} "
                f"({mesures_c['I']:.1f} LUFS)"
            )

        # ------------------------------------------------------------------
        # 5. Optional Music Flamingo QA
        # ------------------------------------------------------------------
        resultat_analyse = None
        if analyse:
            self.log("Music Flamingo (QA) analysis of the selected bed...", emoji="🧠")
            resultat_analyse = analyser_boucle_flamingo(bed, log=lambda m: self.log(m, emoji="   "))
            if resultat_analyse:
                self.log(f"Verdict: {resultat_analyse}")

        # ------------------------------------------------------------------
        # 6. Mixing recipe under a voice-over (automatic ducking)
        # ------------------------------------------------------------------
        recette = construire_recette_ducking("voix_off.wav", os.path.basename(bed), "mix_final.wav")
        chemin_recette = os.path.join(output_dir, "recette_mixage_voix.txt")
        with open(chemin_recette, "w", encoding="utf-8") as f:
            f.write(
                "RECIPE: mixing the loop under a voice-over (automatic ducking)\n"
                "==============================================================\n\n"
                "1) Put this file next to your voice-over: voix_off.wav\n"
                "2) Run the command:\n\n"
                f"    {recette}\n\n"
                "3) Result: mix_final.wav — the loop is repeated to the duration of the\n"
                "   voice and attenuated automatically as soon as the voice speaks.\n"
                "   Adjustments:\n"
                "   - music too present → lower volume=1.0 (e.g.: 0.7)\n"
                "   - stronger ducking → ratio=8 and/or threshold=0.03\n"
                "   - faster recovery after the voice → release=350\n"
            )

        self.log(f"Final exports in '{output_dir}/':", emoji="🎉")
        self.log(f"  • Full loop       : {wav_full}")
        self.log(f"  • Bed {mesures_bed['I']:.1f} LUFS   : {bed}")
        self.log(f"  • OGG loop        : {ogg}")
        self.log(f"  • MP3 preview     : {mp3}")
        self.log(f"  • {len(candidats)} finalized loops (bed + MP3) in 'candidats/'", emoji="🎵")
        self.log(f"  • Ducking recipe  : {chemin_recette}", emoji="💎")

        return {
            "wav_full": wav_full,
            "bed": bed,
            "ogg": ogg,
            "mp3": mp3,
            "recette_ducking": chemin_recette,
            "bpm": meilleur["boucle"].get("bpm"),
            "duree_boucle": meilleur["boucle"]["duree"],
            "strategie": meilleur["boucle"]["strategie"],
            "moteur": moteur,
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
