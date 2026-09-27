#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests of the generator-assets CLI consumer contract (ai-doc2video, video-analys-ia).

Freezes the guarantees the consumer repos depend on (check=True subprocess calls):
1. workflow-specific CLI options default to None — each workflow
   applies its own default (historical bug: --duration 2.0 overrode the
   180 s of chanson, the 24 fps of video, the 12 s of music_bg…);
2. `construire_params` only transmits actually provided keys;
3. the maintenance handlers (update_*) are outside the registry — the interactive
   menu must route them before WorkflowRegistry.get();
4. sd-cli rendering no longer writes temporary files at a relative path
   (ex-temp_render.png): unique file per call, cleaned up, insensitive to
   the parallel executions of the two consumers;
5. the batch workflow reports its failures: stop at the first error by default
   (exception → return code ≠ 0), --continue-on-error mode = full batch + failures
   in the result (return code ≠ 0 CLI-side).

The fake sd-cli are subprocess.run monkeypatches: no engine nor GPU required.
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
# 1 & 2. argparse / params contract
# ============================================================================

CHAMPS_SPECIFIQUES = ("duration", "frames", "fps", "pitch", "lufs", "factor")


def test_defauts_workflow_specifiques_absents_du_cli():
    """Without an explicit option, specific fields are None: the workflow keeps its default."""
    args = main.construire_parseur().parse_args(["-w", "video"])
    for champ in CHAMPS_SPECIFIQUES:
        assert getattr(args, champ) is None, (
            f"--{champ} must be None by default (otherwise it overrides the workflow's default)"
        )


def test_params_ne_transmet_que_les_cles_renseignees():
    """construire_params filters None keys and transmits the general defaults (seed…)."""
    args = main.construire_parseur().parse_args(
        ["-w", "video", "mystic cascade", "--frames", "25", "--fps", "24"]
    )
    params = main.construire_params(args, "mystic cascade")
    assert "duration" not in params
    assert "pitch" not in params
    assert params["frames"] == 25
    assert params["fps"] == 24.0
    assert params["seed"] == -1  # general default always transmitted
    assert params["prompt"] == "mystic cascade"


def test_param_explicite_reste_transmis():
    """An explicit value (e.g. --duration 45 for chanson) goes through the filter."""
    args = main.construire_parseur().parse_args(["-w", "chanson", "lyrics", "--duration", "45"])
    params = main.construire_params(args, "lyrics")
    assert params["duration"] == 45.0


# ============================================================================
# 3. Maintenance handlers outside the registry
# ============================================================================

def test_gestionnaires_maintenance_hors_registre():
    """update_* are not workflows: the interactive menu must route them
    to their dedicated branch BEFORE WorkflowRegistry.get (otherwise ValueError)."""
    for nom in ("update_sd", "update_llama", "update_vulkan"):
        with pytest.raises(ValueError):
            WorkflowRegistry.get(nom)


def test_menu_interactif_couvre_le_registre():
    """The interactive menu is generated from the registry: every registered workflow
    appears in it (anti-drift guard rail — 4 workflows had vanished from the menu)."""
    from cli.interactive import construire_menu

    menu = construire_menu()
    noms = {nom for nom, _ in menu.values()}
    maintenance = {"update_sd", "update_llama", "update_vulkan"}
    assert noms - maintenance == set(WorkflowRegistry.list_all())
    assert len(noms) == len(menu)  # no duplicate
    assert sorted(int(k) for k in menu) == list(range(1, len(menu) + 1))
    # every workflow carries a non-empty emoji and menu description
    for nom in WorkflowRegistry.list_all():
        cls = WorkflowRegistry.get(nom)
        assert getattr(cls, "emoji", ""), f"missing emoji on {nom}"


# ============================================================================
# 4. Temporary files of the sd-cli render
# ============================================================================

@pytest.fixture
def faux_sd_cli(monkeypatch):
    """Replaces subprocess.run with a fake sd-cli that writes a PNG at the -o path."""
    appels = []

    from subprocess import CompletedProcess

    def faux_run(commande, check=True, **kwargs):
        appels.append(list(commande))
        sortie = commande[commande.index("-o") + 1]
        Image.new("RGB", (4, 4), (200, 30, 30)).save(sortie, "PNG")
        return CompletedProcess(commande, 0, stdout="", stderr="")

    # All engines now go through core.process.run_engine:
    # a single monkeypatch covers diffusion, upscaler and blender_ops.
    monkeypatch.setattr(process.subprocess, "run", faux_run)
    return appels


def test_generer_image_temporaire_unique_et_nettoye(tmp_path, monkeypatch, faux_sd_cli):
    """Without output_path: render into a unique absolute temporary file, read back then deleted.
    No temp_render.png appears in the current directory (parallel executions)."""
    monkeypatch.chdir(tmp_path)
    img = diffusion.generer_image_vulkan(
        "unit test asset",
        sd_cli="fake-sd-cli",
        sd_model=diffusion.DEFAULT_SD_MODEL,
        width=64,
        height=64,
        steps=1,
    )
    assert isinstance(img, Image.Image)
    assert img.size == (4, 4)

    chemin_sortie = faux_sd_cli[0][faux_sd_cli[0].index("-o") + 1]
    assert Path(chemin_sortie).name != "temp_render.png"
    assert os.path.isabs(chemin_sortie)  # tempfile, not the current directory
    assert not Path(chemin_sortie).exists()  # cleaned up after reading
    assert not (tmp_path / "temp_render.png").exists()


def test_generer_image_chemin_explicite_conserve(tmp_path, faux_sd_cli):
    """With an explicit output_path: the final file is kept (historical behavior)."""
    sortie = tmp_path / "final.png"
    img = diffusion.generer_image_vulkan(
        "unit test asset",
        sd_cli="fake-sd-cli",
        sd_model=diffusion.DEFAULT_SD_MODEL,
        output_path=str(sortie),
    )
    assert sortie.exists()
    assert img.size == (4, 4)


def test_upscale_esrgan_sans_temporaire_dans_cwd(tmp_path, monkeypatch, faux_sd_cli):
    """upscale_esrgan goes through a TemporaryDirectory: no more temp_esrgan_*.png in cwd."""
    monkeypatch.chdir(tmp_path)
    modele = tmp_path / "4x-UltraSharp_faux.pth"
    modele.write_bytes(b"fake model")

    source = Image.new("RGBA", (8, 8), (10, 200, 30, 255))
    img = upscaler.upscale_esrgan(
        source, esrgan_model_path=str(modele), sd_cli="fake-sd-cli"
    )

    assert isinstance(img, Image.Image)
    assert img.mode == "RGBA"  # alpha re-injected
    assert img.size == (4, 4)
    assert sorted(p.name for p in tmp_path.iterdir()) == [modele.name]


def test_signature_generer_image_sans_defaut_relatif():
    """Guard rail: the output_path default must no longer be a relative path."""
    defaut = inspect.signature(diffusion.generer_image_vulkan).parameters["output_path"].default
    assert defaut is None


# ============================================================================
# 5. Batch workflow contract
# ============================================================================

@WorkflowRegistry.register
class _WorkflowSpectacle(BaseWorkflow):
    """Fake workflow: fails when the prompt contains "failure" (no engine required)."""

    name = "spectacle_contrat"
    description = "Fake workflow reserved for the batch contract tests"
    emoji = "🧪"

    def run(self, params):
        if "failure" in (params.get("prompt") or ""):
            raise RuntimeError("simulated engine failure")
        return {"ok": True, "prompt": params.get("prompt")}


@pytest.fixture
def recette_deux_assets(tmp_path):
    recette = tmp_path / "recette.json"
    recette.write_text(
        json.dumps([
            {"prompt": "asset ok 1", "workflow": "spectacle_contrat"},
            {"prompt": "asset failure", "workflow": "spectacle_contrat"},
            {"prompt": "asset never reached", "workflow": "spectacle_contrat"},
        ]),
        encoding="utf-8",
    )
    return recette


def test_batch_strict_arrete_a_la_premiere_erreur(tmp_path, recette_deux_assets):
    """Strict default: one asset's failure interrupts the batch with a clear exception."""
    batch = BatchWorkflow({})
    with pytest.raises(RuntimeError, match="asset failure"):
        batch.run({"file": str(recette_deux_assets), "output_dir": str(tmp_path)})


def test_batch_tolerant_termine_et_signale_les_echecs(tmp_path, recette_deux_assets):
    """--continue-on-error: the whole batch is walked, failures listed in the result."""
    batch = BatchWorkflow({})
    res = batch.run({
        "file": str(recette_deux_assets),
        "output_dir": str(tmp_path),
        "continue_on_error": True,
    })
    assert res["total_tasks"] == 3
    assert res["completed"] == 2
    assert len(res["echecs"]) == 1
    assert res["echecs"][0]["prompt"] == "asset failure"
    assert "simulated engine failure" in res["echecs"][0]["erreur"]


# ============================================================================
# 6. Options declared by the workflows (audit §2.2 keystone)
# ============================================================================

def test_aucun_doublon_de_flag_dans_le_parseur():
    """A flag must be declared only once (flat table OR workflow declaration):
    argparse silently accepts re-declarations (the last one wins) — the test
    protects the family-by-family migration."""
    parseur = main.construire_parseur()
    vus = []
    for action in parseur._actions:
        vus.extend(action.option_strings)
    doublons = {f for f in vus if vus.count(f) > 1}
    assert not doublons, f"flags declared several times: {sorted(doublons)}"


def test_flags_monoplan_migres_en_declaration_reste_identiques():
    """1st migrated family (monoplan_ia): same CLI surface, same dests/defaults.
    The ai-doc2video bridge calls these flags as a subprocess — frozen contract."""
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

    # --upscale-ia alias and untouched defaults
    args2 = parseur.parse_args(["-w", "monoplan_ia", "--upscale-ia"])
    assert args2.upscale_4k is True
    args3 = parseur.parse_args(["-w", "monoplan_ia"])
    assert args3.monoplan_frames == 65 and args3.upscale_4k is False

    # params transmitted to the workflow, with the contract's None filtering
    params = main.construire_params(args, "test prompt")
    assert params["monoplan_frames"] == 42
    assert params["upscale_4k"] is True
    assert params["carton_titre"] == "A|B"
    params3 = main.construire_params(args3, "test prompt")
    assert params3["monoplan_frames"] == 65
    assert "ambiance" not in params3  # None filtered


def test_monoplan_ia_porte_toutes_ses_declarations():
    """The class does expose its 10 parameters, and the registry aggregates them."""
    from workflows.monoplan_ia import MonoplanIaWorkflow
    assert len(MonoplanIaWorkflow.PARAMETRES) == 10
    toutes = WorkflowRegistry.parametres_declares()
    flags_agreges = {f for decl in toutes for f in decl["flags"]}
    assert {"--monoplan-frames", "--4k", "--carton-titre"} <= flags_agreges


def test_famille_audio_migree_en_declarations():
    """2nd migrated family (audit §2.2): the 10 audio workflows carry their
    30 flags; the family's shared flags live with their first user
    (--duration → sfx, --moteur/--variante/--music-backend… →
    music_bg). Surface frozen by test_surface_cli_gelee."""
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
    # chanson contract: the CLI's None defaults let the workflow apply
    # its own (xl-turbo, fr); an explicit value goes through the filter
    args = main.construire_parseur().parse_args(
        ["-w", "chanson", "lyrics", "--langue", "kr", "--variante", "xl-sft", "--duration", "120"]
    )
    assert args.langue == "kr" and args.variante == "xl-sft" and args.duration == 120.0


def test_famille_video_3d_migree_en_declarations():
    """3rd migrated family (audit §2.2): mesh_ia, video, h3_ref2va, animal_godot.
    --frames/--fps/--width/--height stay in the flat table (shared with the
    2D / character families). Surface frozen by test_surface_cli_gelee."""
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
    # h3_ref2va contract: --turbo (recommended default mode) and --max-vram go through
    args = main.construire_parseur().parse_args(
        ["-w", "h3_ref2va", "rest of the plan", "--turbo", "--max-vram", "12", "--dry-run"]
    )
    assert args.turbo is True and args.max_vram == 12 and args.dry_run is True


def test_famille_personnage_migree_en_declarations():
    """4th migrated family (audit §2.2): outfit, makehuman_clothes,
    character_makeup. --character (shared outfit/character_makeup) lives in
    outfit; --samples stays in the flat table (shared with asset_blendkit).
    Surface frozen by test_surface_cli_gelee."""
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
    # outfit contract: CLI defaults kept (marc_novice character), explicit goes through
    args = main.construire_parseur().parse_args(
        ["-w", "outfit", "runic fabric", "--character", "serena", "--age", "0.5"]
    )
    assert args.character == "serena" and args.age == 0.5


def test_declarations_heritees_emises_une_seule_fois():
    """character3d inherits from CharacterMakeupWorkflow: PARAMETRES is the same
    list object on both classes — the registry must aggregate it only once,
    otherwise argparse refuses the duplicate flag (--portrait conflict…)."""
    from workflows.character_makeup import Character3DWorkflow, CharacterMakeupWorkflow
    assert Character3DWorkflow.PARAMETRES is CharacterMakeupWorkflow.PARAMETRES
    toutes = WorkflowRegistry.parametres_declares()
    ids = [id(declaration) for declaration in toutes]
    assert len(ids) == len(set(ids)), "declaration aggregated several times"


def test_famille_2d_migree_en_declarations():
    """Last migrated family (audit §2.2): 15 2D workflows. The cross-family
    flags (--factor --frames --fps --columns --emotions --mode
    --samples --width --height) stay in the parser's flat table.
    Surface frozen by test_surface_cli_gelee."""
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
        # ui_9slice and anim_loop checked below (late imports)
    } <= flags_agreges
    from workflows import anim_loop, ui_9slice
    assert len(ui_9slice.UI9SliceWorkflow.PARAMETRES) == 2         # --margin --auto-margin
    assert len(anim_loop.AnimLoopWorkflow.PARAMETRES) == 1         # --mode-2d
    assert "--margin" in flags_agreges and "--mode-2d" in flags_agreges
    # batch contract: --recipe alias and strict default kept
    args = main.construire_parseur().parse_args(["-w", "batch", "--recipe", "r.json"])
    assert args.file == "r.json" and args.continue_on_error is False


def test_flags_cross_familles_restant_en_table_plate():
    """The 9 cross-family options stayed in the parser's shared group
    (no single owner): guard rail of the migration final."""
    parseur = main.construire_parseur()
    titres = [g.title for g in parseur._action_groups]
    assert "Options shared across workflow families" in titres
    groupe = next(g for g in parseur._action_groups
                  if g.title == "Options shared across workflow families")
    flags = {f for a in groupe._group_actions for f in a.option_strings}
    assert flags == {
        "--factor", "--mode", "--columns", "--frames", "--emotions", "--fps",
        "--samples", "--width", "--height",
    }


def test_tous_workflows_exclusifs_declares_chez_eux():
    """Every workflow with declarations exposes a consistent subset:
    the declaration lives in the class or its ancestor (never elsewhere)."""
    for nom in WorkflowRegistry.list_all():
        cls = WorkflowRegistry.get(nom)
        for declaration in getattr(cls, "PARAMETRES", []):
            assert "flags" in declaration, f"{nom}: declaration without 'flags'"


# ============================================================================
# 7. Freeze of the full CLI surface (audit §2.2 — migration safety net)
# ============================================================================

def test_surface_cli_gelee():
    """FREEZE of the entire argparse surface (consumer contract): flags,
    dests, action classes, defaults, choices, nargs, types — help stays
    excluded (cosmetic). Any difference = accidental drift (the
    anti-duplicate test sees neither a changed default nor a lost dest). If the
    change is INTENTIONAL, regenerate the snapshot and document it in
    the commit message:
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
            fromfile="frozen_surface", tofile="current_surface",
        )
        extrait = "".join(list(diff)[:40])
        pytest.fail("CLI surface drifted from the freeze (tests/surface_cli.json):\n" + extrait)
