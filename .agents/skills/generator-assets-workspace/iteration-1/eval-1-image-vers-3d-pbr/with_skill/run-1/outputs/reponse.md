# Casque PNG → objet 3D fermé + PBR pour Godot : le plan complet

Bonne nouvelle : c'est exactement le cas d'usage du workflow **`mesh_ia`** (TRELLIS.2-4B via
trellis.cpp, backend Vulkan) — et ton casque est même **le cas d'école qui a servi à valider
ce workflow le 2026-09-06** (« énorme ça marche », MEMORY_BANK §1.14). On a donc des durées
et des résultats mesurés précisément sur cette image.

Pourquoi pas autre chose :
- **`mesh3d`** (formes paramétriques Blender) ferait une extrusion 2,5D — du bas-relief, pas
  un volume fermé. C'est précisément ce que tu ne veux pas.
- **`voxel3d`** ferait du voxel pour GridMap, pas un mesh lisse.
- **`mesh_ia`** infère un **vrai volume fermé** (le casque existe « tout autour », on peut le
  tourner dans Godot) avec **textures PBR** (basecolor / metallic / roughness) embarquées
  dans le GLB, prêtes pour un `MeshInstance3D` Godot 4.

Le pipeline interne : DINOv3 (conditionnement image) → flow sparse-structure → flow shape
SLAT → décodage mesh FlexiDualGrid avec **rebouchage des trous** (d'où le volume fermé) →
flow texture SLAT + décodage PBR → décimation QEM + atlas UV xatlas → GLB.

⚠️ **Rien n'a été lancé maintenant** : le GPU est occupé par un autre travail. Règle du dépôt
(incident documenté, RTF mesuré 3,3× trop lent à cause d'une contention GPU) : on ne lance
jamais une génération lourde sur une machine chargée. Voici donc le plan à exécuter dès que
le GPU est libre — dans cet ordre.

---

## 1. Vérifications AVANT de lancer

```bash
# Depuis la racine du dépôt C:\GIT\generator-assets

# a) Contrôle de charge système — OBLIGATOIRE avant toute génération lourde
#    exit 1 = machine encore occupée → on attend un créneau libre, on ne lance pas
uv run python scripts/check_charge_systeme.py

# b) Vérification que les moteurs et modèles sont détectés
uv run python main.py --check
```

À savoir sur ces vérifications :
- `check_charge_systeme.py` échantillonne CPU/GPU/RAM/VRAM (seuils par défaut : CPU 60 %,
  GPU 40 %, RAM 90 %, VRAM 80 % ; ajustables via `--cpu-threshold` etc. si besoin).
- Le workflow `mesh_ia` revérifie lui-même au démarrage que `trellis-cli.exe`
  (`C:\trellis\`) et les **10 GGUF TRELLIS.2 f16** (~16,4 Go, `C:\Modeles_LLM\trellis2-gguf`)
  sont présents — il s'interrompt proprement si quelque chose manque.
- **Une seule génération lourde à la fois** (RX 6950 XT 16 Go) : vérifier qu'aucun
  `audiocpp_cli.exe` / `sd-cli.exe` / `trellis-cli.exe` / `ffmpeg.exe` ne tourne, et ne
  jamais en tuer un en cours.

Vérification de l'image source — **déjà faite, elle est idéale** :
`godot_assets/casque.png` = **512×512, RGBA, fond transparent**, objet unique centré.
C'est l'entrée parfaite pour TRELLIS : l'image étant pré-détourée, l'alpha est conservé tel
quel et le cutout BiRefNet interne de trellis n'a pas à deviner le fond.

---

## 2. Les commandes exactes, dans l'ordre

### Étape A — itération rapide à la résolution 512 (~12 min)

Pour juger la forme du volume avant d'investir le master :

```bash
uv run python main.py -w mesh_ia -i godot_assets/casque.png --res 512 -o casque --seed 42
```

Options :
- `-i godot_assets/casque.png` : ton image source (pas de prompt nécessaire, donc pas de
  génération d'image en amont — le chaînage `generate` ne se déclenche que sans `-i`) ;
- `--res 512` : résolution de génération 3D d'itération (~11 min ; défaut = 512) ;
- `-o casque` : nom de base des sorties → dossier `output/mesh_ia/casque/` ;
- `--seed 42` : graine fixée (convention du dépôt) pour reproduire/comparer en A/B.

Ensuite : **inspecter la planche de contrôle** `casque_512_planche.png` (image source, 4 vues
orbitales Blender, aperçu de l'atlas PBR). Si la forme ou la texture ne plaît pas, on relance
à 512 avec une autre graine — c'est la raison d'être de cette étape (itéérer à ~12 min et non
~1 h).

### Étape B — master haute définition à la résolution 1024, avec version jeu Godot

Une fois la forme validée à 512 :

```bash
uv run python main.py -w mesh_ia -i godot_assets/casque.png --res 1024 --faces-cible 30000 -o casque --seed 42
```

Options supplémentaires :
- `--res 1024` : master HD (cascade LR→HR interne) — atlas PBR 2048² au lieu de 1024²,
  micro-relief nettement supérieur ;
- `--faces-cible 30000` : décimation Blender headless optionnelle (collapse délimité
  UV/SHARP, **textures PBR conservées**) qui produit un GLB « jeu » supplémentaire — le
  master pleine qualité est toujours conservé à côté.

Choix de `--faces-cible` (dépend de la distance caméra et du nombre d'instances, pas de la
qualité visuelle puisque les textures sont intactes) :
- **`30000` = item héros vu de près** → c'est la bonne valeur pour un casque équipé sur un
  personnage ;
- `10000` = prop de décor vu à 2-10 m ; `2000-3000` = clutter répété ×50 ;
- garder ≥ 8000 si silhouette très courbée (cornes, drapés) — le casque est courbé, 30000
  est confortable.

Remarque : `--res 1536` existe mais n'est pas testé (non recommandé sans validation) ; les
variantes GGUF q4/q8 ne sont pas testées non plus — on reste en f16 validé.

---

## 3. Sorties attendues et emplacements

Tout atterrit dans **`output/mesh_ia/casque/`** (dossier créé par le workflow ; il n'existe
pas encore, aucun écrasement à craindre) :

| Fichier | Contenu | Ordre de grandeur (mesuré sur ce casque) |
| :--- | :--- | :--- |
| `casque_512.glb` puis `casque_1024.glb` | **Master** volume fermé, atlas PBR embarqué | 512 : ~5,3 Mo, ~144 200 faces, atlas 1024² • 1024 : ~12 Mo, ~293 356 faces, atlas 2048² |
| `casque_1024_jeu.glb` | GLB décimé « runtime Godot » (uniquement avec `--faces-cible`) | ~30 000 faces, ~1,5 Mo (mesuré : 144 200 → 29 999 en 512) |
| `casque_<res>_base.png` | Aperçu de l'**atlas** UV — ⚠️ pas l'image source | — |
| `casque_<res>_vue0.png` … `vue3.png` | 4 rendus orbitaux studio (Blender EEVEE headless) | — |
| `casque_<res>_planche.png` | Planche de contrôle 2×3 : source + 4 vues + atlas | c'est le fichier à inspecter pour valider |
| `casque_<res>.ply` | Maillage brut (bonus) | — |
| `casque_<res>_infos.json` | Durées par étape, comptages de faces, chemins, seed | — |

Côté Godot : glisser `casque_1024_jeu.glb` dans le projet → import GLTF → `MeshInstance3D`
directement utilisable (matériau PBR inclus dans le GLB). Le master `casque_1024.glb` reste
en archive si on veut re-décimer à une autre cible plus tard.

---

## 4. Durées estimées (RX 6950 XT, Vulkan, GGUF f16 — mesurées sur CE casque)

| Étape | res 512 (itération) | res 1024 (master) |
| :--- | :--- | :--- |
| Génération TRELLIS.2 | **10 min 44 s** | **55 min 10 s** |
| Décimation `--faces-cible` (si présente) | ~40 s | ~1-2 min |
| Rendus Blender + planche | ~1 min | ~1-2 min |
| **TOTAL** | **~11-12 min** | **~57-60 min** |

Plan complet (itération 512 + master 1024) : **environ 1 h 10 de GPU**, à lancer en deux
créneaux si besoin. Le workflow affiche la progression en direct (étapes 1/6 → 6/7) et
récapitule les durées par étape à la fin ; tout est consigné dans `_infos.json`.

Note perf : le RDNA2 n'a pas de « matrix cores » Vulkan, on est ~4-6× plus lent que les
benchmarks Strix Halo du projet — d'où la règle pratique : **itérer à 512, master à 1024**.

---

## 5. Récapitulatif opérationnel

1. Attendre la fin du travail GPU en cours (aucun lancement maintenant).
2. `uv run python scripts/check_charge_systeme.py` → exit 0 requis.
3. `uv run python main.py -w mesh_ia -i godot_assets/casque.png --res 512 -o casque --seed 42` (~12 min).
4. Inspecter `output/mesh_ia/casque/casque_512_planche.png` → valider la forme/le volume.
5. Si OK : `uv run python main.py -w mesh_ia -i godot_assets/casque.png --res 1024 --faces-cible 30000 -o casque --seed 42` (~1 h).
6. Intégrer `output/mesh_ia/casque/casque_1024_jeu.glb` dans Godot.

Licence : trellis.cpp MIT, TRELLIS.2-4B MIT, DINOv3 Apache-2.0, BiRefNet MIT — usage jeu +
chaîne sans aucune contrainte. Comme l'esthétique 3D est subjective, je te soumettrai la
planche de contrôle à chaque étape avant de passer à la suivante.
