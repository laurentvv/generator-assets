---
name: blender-rig
description: Rigging et animation IA locale dans Blender via MCP (port 9876) — construire un rig Rigify agentique sur un mesh nu (humain ou quadrupède), animer en procédural FK, générer du mocap IA texte→mouvement (Kimodo CPU), exporter en GLB game-ready Godot avec clips AN_*, et rendre des clips MP4 de contrôle (captures multi-vues). Utiliser ce skill quand l'utilisateur veut riguer, skinner, animer un personnage ou un animal, générer du mocap IA, exporter un asset animé vers Godot, ou dérouler le pipeline complet « mesh → rig → animation → GLB » — mais PAS pour un simple asset statique (generator-assets suffit).
---

# blender-rig — rigging & animation IA locale (Blender MCP)

Chaîne validée campagne 2026-09-18 (MEMORY_BANK §1.28) : **mesh → rig Rigify
agentique → animation (procédurale FK ou mocap natif/Kimodo) → GLB Godot vérifié**.
Règle d'or issue des verdicts utilisateur : **le mocap natif/naturel sur
personnage texturé = le standard** ; le procédural FK = boucles d'ambiance ;
le retarget inter-rigs et l'habillage mocap = PARKÉS (fonctionnels, non retenus
visuellement).

## 1. Setup — piloter Blender depuis l'agent

1. Blender GUI lancé avec autostart MCP :
   `blender.exe --python scripts/proto_rig/demarrer_blender_mcp.py`
   (addon BlenderMCP v1.5 déjà installé — socket localhost:9876).
2. Client direct (protocole : 1 JSON par connexion) :
   `uv run python scripts/proto_rig/blender_client.py --ping|--code <py>|--screenshot out.png`
3. Boucle de vérification = **captures multi-vues** :
   `uv run python scripts/proto_rig/capture_multivues.py <nom> [-t 1100]`
   (avant/¾/profil/dos, cadrage auto, offscreen GPU — marche fenêtre en
   arrière-plan). Toujours vérifier visuellement après chaque étape.

## 2. Rigging agentique (humain et quadrupède)

Recette éprouvée (humain 410 os, loup 823 os) :

1. **Mesurer le mesh** par tranches (hauteur, épaules, hanches, cou —
   positions en Z, largeurs X/Y) : le fit est géométrique, pas à l'œil.
2. **Méta-rig** : humain = `armature_human_metarig_add` ; quadrupèdes = Rigify
   embarque **wolf / cat / horse / shark / bird** + `basic_quadruped`
   (`armature_wolf_metarig_add` etc.).
3. **Fit** : échelle uniforme + repositionnement des os clés en EDIT mode
   (align_roll systématique), **léger pli coude/genou obligatoire** (membres
   rectilignes = crash Rigify `compute_pole_angle`).
4. **Rig facial** : soit conservé (loup, 823 os), soit supprimé + paramètres
   `use_head`/`neck_pos` sur l'os spine (sinon pas d'os déformeur tête —
   contournement : contrôles `use_deform` + vertex groups manuels, fragile).
5. `pose.rigify_generate` — **jamais depuis un méta-rig caché** (AssertionError
   `__duplicate_rig`) ; l'objet résultat ≠ metarig → à renommer.
6. **Poids** : `parent_set(type='ARMATURE_AUTO')` sur le mesh.
7. **Poses de test** + captures multi-vues avant de valider.

## 3. Animation

- **Procédurale FK** (validé : trot loup « OK ») : basculer les membres en FK
  (`['IK_FK'] = 1.0` sur les os `*_parent`, keyframé) — sinon les contrôles FK
  sont inertes ; **limiter la bascule aux membres** (torse basculé = blob
  d'épaules). Axes éprouvés : bras Z ∓1.35 = baisser (miroir L/R), cuisses X
  pour la foulée. Caméra **fixe profil** pour la locomotion (le 3/4 de face
  tue la lecture). Rendu : `rendre_clip.py --fixe [--profil] --boucle`.
- **Mocap natif de pack** (validé « parfait ») : rendre le rig du pack avec
  ses actions natives — ne pas retargeter sans besoin (tenté : sous la barre).
- **Mocap IA Kimodo** (`C:\IA\kimodo`, texte→BVH CPU 50 s) : moteur validé,
  BVH livré. Habillage sur mesh = PARKÉ (conflits de vertex groups) ;
  `TEXT_ENCODERS_DIR` + miroir NousResearch + DLL MinGW requis (détails §1.28).
- **Retarget inter-rigs** (`retarget_quaternius.py`) : deltas monde → basis
  locale, contraintes DEF muted, purge par différence — PARKÉ (amplitude sous
  le natif).

## 4. Export game-ready Godot

```bash
uv run python main.py -w animal_godot -i <animal_packe.blend> -o <sortie.glb> [--animal-prefixe AN_]
```

Purge parasites pack (Camera/Cube/Light), clips renommés `AN_*` (un par action
native), export `export_animation_mode='ACTIONS'`, **vérifié par ré-import**
(os + clips + meshes). Exemple livré : `output/test_rig/loup_quaternius_godot.glb`
(51 os, 12 clips, CC0).

## 5. Écueils critiques (historique complet en MEMORY_BANK §1.28)

- `libraries.load` n'instancie PAS dans la scène → **lier explicitement à
  `scene.collection`**, sinon ni animation ni contraintes évaluées.
- Actions legacy 2.79 sous Blender 5.2 : évaluer les fcurves à la main
  (`channelbag.fcurves[i].evaluate(f)`) — `frame_set` ne les joue pas.
- Import GLB : matrices locales ROTÉES (Y-up) → décalages géométriques en
  espace monde via inverse de `matrix_world` ; `bound_box` est un cache paresseux.
- Retarget : quaternions en basis locale (`rest⁻¹ @ frame`), jamais l'espace
  armature ; suppressions d'objets par DIFFÉRENCE avant/après import (jamais
  au nom près).
- `read_factory_settings` en MCP coupe la réponse socket ; exports/imports
  headless : `select_set` direct (`select_all` = contexte manquant) ;
  enum moteur = `BLENDER_EEVEE` ; `origin_set` sans argument `mode`.
