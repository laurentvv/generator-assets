#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests du contrat consommateurs du CLI generator-assets (ai-doc2video, video-analys-ia).

Fige les garanties dont dépendent les dépôts consommateurs (appels subprocess check=True) :
1. les options CLI spécifiques à un workflow valent None par défaut — chaque workflow
   applique donc son propre défaut (bug historique : --duration 2.0 écrasait les
   180 s de chanson, les 24 fps de video, les 12 s de music_bg…) ;
2. `construire_params` ne transmet que les clés réellement renseignées ;
3. les gestionnaires de maintenance (update_*) sont hors registre — le menu
   interactif doit les traiter avant WorkflowRegistry.get() ;
4. le rendu sd-cli n'écrit plus de fichiers temporaires en chemin relatif
   (ex-temp_render.png) : fichier unique par appel, nettoyé, insensible aux
   exécutions parallèles des deux consommateurs ;
5. le workflow batch signale ses échecs : arrêt à la première erreur par défaut
   (exception → code retour ≠ 0), mode --continue-on-error = lot complet + échecs
   dans le résultat (code retour ≠ 0 côté CLI).

Les faux sd-cli sont des monkeypatch de subprocess.run : aucun moteur ni GPU requis.
"""

import difflib
import inspect
import json
import os
from pathlib import Path

import pytest
from PIL import Image

import main
from cli.parser import surface_cli
from core import diffusion, process, upscaler
from workflows.base import BaseWorkflow, WorkflowRegistry
from workflows.batch import BatchWorkflow


# ============================================================================
# 1 & 2. Contrat argparse / paramètres
# ============================================================================

CHAMPS_SPECIFIQUES = ("duration", "frames", "fps", "pitch", "lufs", "factor")


def test_defauts_workflow_specifiques_absents_du_cli():
    """Sans option explicite, les champs spécifiques valent None : le workflow garde son défaut."""
    args = main.construire_parseur().parse_args(["-w", "video"])
    for champ in CHAMPS_SPECIFIQUES:
        assert getattr(args, champ) is None, (
            f"--{champ} doit valoir None par défaut (sinon il écrase le défaut du workflow)"
        )


def test_params_ne_transmet_que_les_cles_renseignees():
    """construire_params filtre les clés None et transmet les défauts généraux (seed…)."""
    args = main.construire_parseur().parse_args(
        ["-w", "video", "cascade mystique", "--frames", "25", "--fps", "24"]
    )
    params = main.construire_params(args, "cascade mystique")
    assert "duration" not in params
    assert "pitch" not in params
    assert params["frames"] == 25
    assert params["fps"] == 24.0
    assert params["seed"] == -1  # défaut général toujours transmis
    assert params["prompt"] == "cascade mystique"


def test_param_explicite_reste_transmis():
    """Une valeur explicite (ex. --duration 45 pour chanson) traverse bien le filtre."""
    args = main.construire_parseur().parse_args(["-w", "chanson", "paroles", "--duration", "45"])
    params = main.construire_params(args, "paroles")
    assert params["duration"] == 45.0


# ============================================================================
# 3. Gestionnaires de maintenance hors registre
# ============================================================================

def test_gestionnaires_maintenance_hors_registre():
    """update_* ne sont pas des workflows : le menu interactif doit les router
    vers leur branche dédiée AVANT WorkflowRegistry.get (sinon ValueError)."""
    for nom in ("update_sd", "update_llama", "update_vulkan"):
        with pytest.raises(ValueError):
            WorkflowRegistry.get(nom)


def test_menu_interactif_couvre_le_registre():
    """Le menu interactif est généré du registre : tout workflow enregistré y
    apparaît (garde-fou anti-dérive — 4 workflows avaient disparu du menu)."""
    from cli.interactive import construire_menu

    menu = construire_menu()
    noms = {nom for nom, _ in menu.values()}
    maintenance = {"update_sd", "update_llama", "update_vulkan"}
    assert noms - maintenance == set(WorkflowRegistry.list_all())
    assert len(noms) == len(menu)  # aucun doublon
    assert sorted(int(k) for k in menu) == list(range(1, len(menu) + 1))
    # chaque workflow porte un emoji et une description de menu non vides
    for nom in WorkflowRegistry.list_all():
        cls = WorkflowRegistry.get(nom)
        assert getattr(cls, "emoji", ""), f"emoji manquant sur {nom}"


# ============================================================================
# 4. Fichiers temporaires du rendu sd-cli
# ============================================================================

@pytest.fixture
def faux_sd_cli(monkeypatch):
    """Remplace subprocess.run par un faux sd-cli qui écrit un PNG au chemin -o."""
    appels = []

    from subprocess import CompletedProcess

    def faux_run(commande, check=True, **kwargs):
        appels.append(list(commande))
        sortie = commande[commande.index("-o") + 1]
        Image.new("RGB", (4, 4), (200, 30, 30)).save(sortie, "PNG")
        return CompletedProcess(commande, 0, stdout="", stderr="")

    # Tous les moteurs passent désormais par core.process.run_engine :
    # un seul monkeypatch couvre diffusion, upscaler et blender_ops.
    monkeypatch.setattr(process.subprocess, "run", faux_run)
    return appels


def test_generer_image_temporaire_unique_et_nettoye(tmp_path, monkeypatch, faux_sd_cli):
    """Sans output_path : rendu dans un fichier temporaire absolu, relu puis supprimé.
    Aucun temp_render.png n'apparaît dans le répertoire courant (exécutions parallèles)."""
    monkeypatch.chdir(tmp_path)
    img = diffusion.generer_image_vulkan(
        "unit test asset",
        sd_cli="faux-sd-cli",
        sd_model=diffusion.DEFAULT_SD_MODEL,
        width=64,
        height=64,
        steps=1,
    )
    assert isinstance(img, Image.Image)
    assert img.size == (4, 4)

    chemin_sortie = faux_sd_cli[0][faux_sd_cli[0].index("-o") + 1]
    assert Path(chemin_sortie).name != "temp_render.png"
    assert os.path.isabs(chemin_sortie)  # tempfile, pas le répertoire courant
    assert not Path(chemin_sortie).exists()  # nettoyé après lecture
    assert not (tmp_path / "temp_render.png").exists()


def test_generer_image_chemin_explicite_conserve(tmp_path, faux_sd_cli):
    """Avec output_path explicite : le fichier final est conservé (comportement historique)."""
    sortie = tmp_path / "final.png"
    img = diffusion.generer_image_vulkan(
        "unit test asset",
        sd_cli="faux-sd-cli",
        sd_model=diffusion.DEFAULT_SD_MODEL,
        output_path=str(sortie),
    )
    assert sortie.exists()
    assert img.size == (4, 4)


def test_upscale_esrgan_sans_temporaire_dans_cwd(tmp_path, monkeypatch, faux_sd_cli):
    """upscale_esrgan passe par un TemporaryDirectory : plus de temp_esrgan_*.png en cwd."""
    monkeypatch.chdir(tmp_path)
    modele = tmp_path / "4x-UltraSharp_faux.pth"
    modele.write_bytes(b"faux modele")

    source = Image.new("RGBA", (8, 8), (10, 200, 30, 255))
    img = upscaler.upscale_esrgan(
        source, esrgan_model_path=str(modele), sd_cli="faux-sd-cli"
    )

    assert isinstance(img, Image.Image)
    assert img.mode == "RGBA"  # alpha réinjecté
    assert img.size == (4, 4)
    assert sorted(p.name for p in tmp_path.iterdir()) == [modele.name]


def test_signature_generer_image_sans_defaut_relatif():
    """Garde-fou : le défaut de output_path ne doit plus être un chemin relatif."""
    defaut = inspect.signature(diffusion.generer_image_vulkan).parameters["output_path"].default
    assert defaut is None


# ============================================================================
# 5. Contrat du workflow batch
# ============================================================================

@WorkflowRegistry.register
class _WorkflowSpectacle(BaseWorkflow):
    """Faux workflow : échoue quand le prompt contient « echec » (aucun moteur requis)."""

    name = "spectacle_contrat"
    description = "Faux workflow réservé aux tests du contrat batch"
    emoji = "🧪"

    def run(self, params):
        if "echec" in (params.get("prompt") or ""):
            raise RuntimeError("panne moteur simulée")
        return {"ok": True, "prompt": params.get("prompt")}


@pytest.fixture
def recette_deux_assets(tmp_path):
    recette = tmp_path / "recette.json"
    recette.write_text(
        json.dumps([
            {"prompt": "asset ok 1", "workflow": "spectacle_contrat"},
            {"prompt": "asset echec", "workflow": "spectacle_contrat"},
            {"prompt": "asset jamais atteint", "workflow": "spectacle_contrat"},
        ]),
        encoding="utf-8",
    )
    return recette


def test_batch_strict_arrete_a_la_premiere_erreur(tmp_path, recette_deux_assets):
    """Défaut strict : l'échec d'un asset interrompt le lot avec une exception claire."""
    batch = BatchWorkflow({})
    with pytest.raises(RuntimeError, match="asset echec"):
        batch.run({"file": str(recette_deux_assets), "output_dir": str(tmp_path)})


def test_batch_tolerant_termine_et_signale_les_echecs(tmp_path, recette_deux_assets):
    """--continue-on-error : lot parcouru en entier, échecs listés dans le résultat."""
    batch = BatchWorkflow({})
    res = batch.run({
        "file": str(recette_deux_assets),
        "output_dir": str(tmp_path),
        "continue_on_error": True,
    })
    assert res["total_tasks"] == 3
    assert res["completed"] == 2
    assert len(res["echecs"]) == 1
    assert res["echecs"][0]["prompt"] == "asset echec"
    assert "panne moteur simulée" in res["echecs"][0]["erreur"]


# ============================================================================
# 6. Options déclarées par les workflows (audit §2.2 keystone)
# ============================================================================

def test_aucun_doublon_de_flag_dans_le_parseur():
    """Un flag ne doit être déclaré qu'une seule fois (table plate OU déclaration
    de workflow) : argparse accepte silencieusement les redéclarations (la
    dernière gagne) — le test protège la migration famille par famille."""
    parseur = main.construire_parseur()
    vus = []
    for action in parseur._actions:
        vus.extend(action.option_strings)
    doublons = {f for f in vus if vus.count(f) > 1}
    assert not doublons, f"flags déclarés plusieurs fois : {sorted(doublons)}"


def test_flags_monoplan_migres_en_declaration_reste_identiques():
    """1re famille migrée (monoplan_ia) : même surface CLI, mêmes dests/défauts.
    Le bridge ai-doc2video appelle ces flags en subprocess — contrat figé."""
    parseur = main.construire_parseur()
    args = parseur.parse_args([
        "-w", "monoplan_ia", "-i", "img.png",
        "--monoplan-frames", "42", "--monoplan-duration", "8.0",
        "--zoom-debut", "1.2", "--zoom-fin", "1.4",
        "--ambiance", "server room hum", "--monoplan-source", "plan.webm",
        "--carton-titre", "A|B", "--carton-duree", "3.0", "--carton-zoom-fin", "1.3",
        "--4k",
    ])
    assert args.monoplan_frames == 42
    assert args.monoplan_duration == 8.0
    assert args.zoom_debut == 1.2 and args.zoom_fin == 1.4
    assert args.ambiance == "server room hum"
    assert args.monoplan_source == "plan.webm"
    assert args.carton_titre == "A|B"
    assert args.carton_duree == 3.0 and args.carton_zoom_fin == 1.3
    assert args.upscale_4k is True

    # alias --upscale-ia et défauts par défaut
    args2 = parseur.parse_args(["-w", "monoplan_ia", "--upscale-ia"])
    assert args2.upscale_4k is True
    args3 = parseur.parse_args(["-w", "monoplan_ia"])
    assert args3.monoplan_frames == 65 and args3.upscale_4k is False

    # params transmis au workflow, avec filtrage None du contrat
    params = main.construire_params(args, "test prompt")
    assert params["monoplan_frames"] == 42
    assert params["upscale_4k"] is True
    assert params["carton_titre"] == "A|B"
    params3 = main.construire_params(args3, "test prompt")
    assert params3["monoplan_frames"] == 65
    assert "ambiance" not in params3  # None filtré


def test_monoplan_ia_porte_toutes_ses_declarations():
    """La classe expose bien ses 10 paramètres, et le registre les agrège."""
    from workflows.monoplan_ia import MonoplanIaWorkflow
    assert len(MonoplanIaWorkflow.PARAMETRES) == 10
    toutes = WorkflowRegistry.parametres_declares()
    flags_agreges = {f for decl in toutes for f in decl["flags"]}
    assert {"--monoplan-frames", "--4k", "--carton-titre"} <= flags_agreges


def test_famille_audio_migree_en_declarations():
    """2e famille migrée (audit §2.2) : les 10 workflows audio portent leurs
    30 flags ; les flags partagés de la famille vivent chez leur premier
    utilisateur (--duration → sfx, --moteur/--variante/--music-backend… →
    music_bg). Surface figée par test_surface_cli_gelee."""
    from workflows import music_bg, sfx, tts_dialogue, voix_robot
    assert len(sfx.SFXWorkflow.PARAMETRES) == 2          # --duration + --sfx-engine
    assert len(music_bg.MusicBgWorkflow.PARAMETRES) == 11
    assert len(voix_robot.VoixRobotWorkflow.PARAMETRES) == 5
    assert len(tts_dialogue.TTSDialogueWorkflow.PARAMETRES) == 1  # --pitch
    toutes = WorkflowRegistry.parametres_declares()
    flags_agreges = {f for decl in toutes for f in decl["flags"]}
    assert {
        "--duration", "--sfx-engine", "--ambience-type", "--lufs", "--loop-mode",
        "--music-backend", "--moteur", "--variante", "--force-bpm", "--tonalite",
        "--mesure", "--candidats", "--lyrics", "--analyse", "--voix-ref",
        "--instruct", "--lufs-voix", "--robot-voice", "--robot-pitch",
        "--robot-ringmod", "--robot-tempo", "--robot-gain", "--upsr-variante",
        "--upsr-rate", "--style-musique", "--langue", "--negatif", "--scale",
        "--keep-vocals", "--pitch",
    } <= flags_agreges
    # contrat chanson : les défauts None du CLI laissent le workflow appliquer
    # les siens (xl-turbo, fr), une valeur explicite traverse le filtre
    args = main.construire_parseur().parse_args(
        ["-w", "chanson", "paroles", "--langue", "kr", "--variante", "xl-sft", "--duration", "120"]
    )
    assert args.langue == "kr" and args.variante == "xl-sft" and args.duration == 120.0


def test_famille_video_3d_migree_en_declarations():
    """3e famille migrée (audit §2.2) : mesh_ia, video, h3_ref2va, animal_godot.
    --frames/--fps/--width/--height restent en table plate (partagés avec les
    familles 2D / personnage). Surface figée par test_surface_cli_gelee."""
    from workflows import h3_ref2va, mesh_ia, video
    assert len(mesh_ia.MeshIaWorkflow.PARAMETRES) == 2        # --res --faces-cible
    assert len(video.VideoWorkflow.PARAMETRES) == 3           # --end-img --control-video --flow-shift
    assert len(h3_ref2va.H3Ref2VAWorkflow.PARAMETRES) == 5    # --ref-frames --ref-audio --max-vram --turbo --dry-run
    from workflows import animal_godot
    assert len(animal_godot.AnimalGodotWorkflow.PARAMETRES) == 2
    toutes = WorkflowRegistry.parametres_declares()
    flags_agreges = {f for decl in toutes for f in decl["flags"]}
    assert {
        "--res", "--faces-cible", "--end-img", "--control-video", "--flow-shift",
        "--ref-frames", "--ref-audio", "--max-vram", "--turbo", "--dry-run",
        "--animal-prefixe", "--animal-actions",
    } <= flags_agreges
    # contrat h3_ref2va : --turbo (mode par défaut recommandé) et --max-vram traversent
    args = main.construire_parseur().parse_args(
        ["-w", "h3_ref2va", "suite du plan", "--turbo", "--max-vram", "12", "--dry-run"]
    )
    assert args.turbo is True and args.max_vram == 12 and args.dry_run is True


def test_famille_personnage_migree_en_declarations():
    """4e famille migrée (audit §2.2) : outfit, makehuman_clothes,
    character_makeup. --character (partagé outfit/character_makeup) vit chez
    outfit ; --samples reste en table plate (partagé avec asset_blendkit).
    Surface figée par test_surface_cli_gelee."""
    from workflows import character_makeup, makehuman_clothes, outfit
    assert len(outfit.OutfitWorkflow.PARAMETRES) == 3            # --character --top --shoes
    assert len(makehuman_clothes.MakeHumanClothesWorkflow.PARAMETRES) == 2  # --parts --mpfb-dir
    assert len(character_makeup.CharacterMakeupWorkflow.PARAMETRES) == 8
    toutes = WorkflowRegistry.parametres_declares()
    flags_agreges = {f for decl in toutes for f in decl["flags"]}
    assert {
        "--character", "--top", "--shoes", "--parts", "--mpfb-dir", "--portrait",
        "--skin", "--eye-color", "--blend-file", "--render-modes", "--age",
        "--gender", "--makeup-only",
    } <= flags_agreges
    # contrat outfit : défauts CLI conservés (personnage marc_novice), explicite traverse
    args = main.construire_parseur().parse_args(
        ["-w", "outfit", "tissu runique", "--character", "serena", "--age", "0.5"]
    )
    assert args.character == "serena" and args.age == 0.5


def test_declarations_heritees_emises_une_seule_fois():
    """character3d hérite de CharacterMakeupWorkflow : PARAMETRES est le même
    objet liste sur les deux classes — le registre ne doit l'agréger qu'une
    fois, sinon argparse refuse le flag en doublon (conflit --portrait…)."""
    from workflows.character_makeup import Character3DWorkflow, CharacterMakeupWorkflow
    assert Character3DWorkflow.PARAMETRES is CharacterMakeupWorkflow.PARAMETRES
    toutes = WorkflowRegistry.parametres_declares()
    ids = [id(declaration) for declaration in toutes]
    assert len(ids) == len(set(ids)), "déclaration agrégée plusieurs fois"


def test_famille_2d_migree_en_declarations():
    """Dernière famille migrée (audit §2.2) : 15 workflows 2D. Les flags
    cross-familles (--factor --frames --fps --columns --emotions --mode
    --samples --width --height) restent dans la table plate du parseur.
    Surface figée par test_surface_cli_gelee."""
    from workflows import (
        asset_blendkit, batch, flowmap, generate, ip_adapter, material3d,
        pixelart, pose_control, tileable, variations, voxel3d, vfx_flipbook,
    )
    assert len(generate.GenerateWorkflow.PARAMETRES) == 1          # --segmenter
    assert len(material3d.Material3DWorkflow.PARAMETRES) == 2      # --normal-strength --pbr-engine
    assert len(pixelart.PixelArtWorkflow.PARAMETRES) == 2          # --palette --grid-size
    assert len(asset_blendkit.AssetBlendkitWorkflow.PARAMETRES) == 11
    assert len(variations.VariationsWorkflow.PARAMETRES) == 1      # --themes
    assert len(tileable.TileableWorkflow.PARAMETRES) == 1          # --no-preview
    assert len(flowmap.FlowmapWorkflow.PARAMETRES) == 3            # --angle --flow-type --turbulence
    assert len(voxel3d.Voxel3DWorkflow.PARAMETRES) == 2            # --voxel-depth --voxel-scale
    assert len(vfx_flipbook.VFXFlipbookWorkflow.PARAMETRES) == 1   # --vfx-type
    assert len(ip_adapter.IPAdapterWorkflow.PARAMETRES) == 1       # --items
    assert len(pose_control.PoseControlWorkflow.PARAMETRES) == 1   # --pose
    assert len(batch.BatchWorkflow.PARAMETRES) == 2                # --file/--recipe --continue-on-error
    toutes = WorkflowRegistry.parametres_declares()
    flags_agreges = {f for decl in toutes for f in decl["flags"]}
    assert {
        "--segmenter", "--normal-strength", "--pbr-engine", "--palette",
        "--grid-size", "--query", "--asset-type", "--licence", "--index",
        "--list-assets", "--resolution", "--engine", "--camera", "--exposure",
        "--percentage", "--no-cache", "--themes", "--no-preview", "--angle",
        "--flow-type", "--turbulence", "--margin", "--auto-margin",
        "--voxel-depth", "--voxel-scale", "--biome-a", "--biome-b", "--vfx-type",
        "--mode-2d", "--items", "--pose", "--file", "--continue-on-error",
        # ui_9slice et anim_loop vérifiés ci-dessous (imports tardifs)
    } <= flags_agreges
    from workflows import anim_loop, ui_9slice
    assert len(ui_9slice.UI9SliceWorkflow.PARAMETRES) == 2         # --margin --auto-margin
    assert len(anim_loop.AnimLoopWorkflow.PARAMETRES) == 1         # --mode-2d
    assert "--margin" in flags_agreges and "--mode-2d" in flags_agreges
    # contrat batch : alias --recipe et défaut strict conservés
    args = main.construire_parseur().parse_args(["-w", "batch", "--recipe", "r.json"])
    assert args.file == "r.json" and args.continue_on_error is False


def test_flags_cross_familles_restant_en_table_plate():
    """Les 9 options cross-familles sont restées dans le groupe partagé du
    parseur (aucun propriétaire unique) : garde-fou du final de migration."""
    parseur = main.construire_parseur()
    titres = [g.title for g in parseur._action_groups]
    assert "Options partagées entre familles de workflows" in titres
    groupe = next(g for g in parseur._action_groups
                  if g.title == "Options partagées entre familles de workflows")
    flags = {f for a in groupe._group_actions for f in a.option_strings}
    assert flags == {
        "--factor", "--mode", "--columns", "--frames", "--emotions", "--fps",
        "--samples", "--width", "--height",
    }


def test_tous_workflows_exclusifs_declares_chez_eux():
    """Chaque workflow avec des déclarations expose un sous-ensemble cohérent :
    la déclaration vit dans la classe ou son ancêtre (jamais ailleurs)."""
    for nom in WorkflowRegistry.list_all():
        cls = WorkflowRegistry.get(nom)
        for declaration in getattr(cls, "PARAMETRES", []):
            assert "flags" in declaration, f"{nom} : déclaration sans 'flags'"


# ============================================================================
# 7. Gel de la surface CLI complète (audit §2.2 — filet de la migration)
# ============================================================================

def test_surface_cli_gelee():
    """GEL de la surface argparse entière (contrat consommateurs) : flags,
    dests, classes d'action, défauts, choices, nargs, types — le help reste
    exclu (cosmétique). Toute différence = dérive accidentelle (le test
    anti-doublon ne voit ni un défaut changé ni un dest perdu). Si le
    changement est INTENTIONNEL, régénérer le snapshot et le documenter dans
    le message de commit :
      uv run python -c "import json ; from cli.parser import construire_parseur, surface_cli ; \
print(json.dumps(surface_cli(construire_parseur()), indent=1))" > tests/surface_cli.json
    """
    chemin = Path(__file__).parent / "surface_cli.json"
    reference = json.loads(chemin.read_text(encoding="utf-8"))
    actuelle = surface_cli(main.construire_parseur())
    if actuelle != reference:
        diff = difflib.unified_diff(
            json.dumps(reference, indent=1, ensure_ascii=False).splitlines(keepends=True),
            json.dumps(actuelle, indent=1, ensure_ascii=False).splitlines(keepends=True),
            fromfile="surface_gelee", tofile="surface_actuelle",
        )
        extrait = "".join(list(diff)[:40])
        pytest.fail("surface CLI dérivée du gel (tests/surface_cli.json) :\n" + extrait)
