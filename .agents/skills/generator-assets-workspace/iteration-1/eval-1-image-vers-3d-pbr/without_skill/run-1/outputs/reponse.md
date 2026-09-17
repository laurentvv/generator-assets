# Casque PNG → objet 3D volumique PBR pour Godot

**Réponse courte : c'est exactement le cas d'usage du workflow `mesh_ia`** (TRELLIS.2-4B via trellis.cpp, Vulkan) — validé par toi le 2026-09-06, et ironie du sort, **sur cette même image de casque** (c'est le cas d'école du README : « impossible via extrusion 2,5D »). Il produit un **vrai maillage fermé volumique inféré par IA** — pas une extrusion plate — avec **textures PBR intégrées** (basecolor / metallic / roughness) dans un `.glb` prêt pour Godot 4.

## Pourquoi `mesh_ia` et pas `mesh3d`

- `mesh3d --shape cutout` = extrusion 2,5D (bas-relief à partir d'un masque) — c'est ce que tu ne veux pas.
- `mesh_ia` = TRELLIS.2-4B (transformer de flow-matching, Microsoft, MIT) exécuté par **trellis.cpp** en C++/GGML Vulkan — même philosophie que sd-cli/audio.cpp, zéro PyTorch. Pipeline : conditionnement DINOv3 → structure sparse → shape SLAT (décodage FlexiDualGrid **avec rebouchage des trous** = volume fermé) → texture SLAT + **décodage PBR** → décimation QEM + atlas UV xatlas. Le GLB sortant a un matériau PBR complet, atlas embarqué.

## ⚠️ Situation actuelle : GPU occupé → on ne lance rien maintenant

Le GPU est pris par un autre travail. **Aucune commande n'est exécutée maintenant** — conformément à la règle du dépôt (jamais de génération lourde sur une machine chargée ; cf. l'incident smoke test v0.7.3 : RTF mesuré 3,3× trop lent à cause d'une contention GPU). Voici le plan complet à dérouler quand la machine sera libre.

---

## 1. Vérifications AVANT de lancer (obligatoires, dans l'ordre)

Toutes les commandes se lancent **depuis la racine du dépôt** `C:\GIT\generator-assets` (les sorties sont écrites en chemin relatif `output/...`).

### a) Charge système — LE garde-fou bloquant

```bash
cd /c/GIT/generator-assets && uv run python scripts/check_charge_systeme.py
```

- **exit 0** → on peut lancer. **exit 1** → machine occupée (CPU/GPU/RAM/VRAM au-dessus des seuils), on attend un créneau libre. Seuils ajustables au besoin (`--cpu-threshold`, `--gpu-threshold`, `--ram-threshold`, `--vram-threshold`, `--duration`).
- C'est ce check qui décide du moment du lancement — tant que le GPU est occupé par l'autre travail, il doit renvoyer 1.

### b) Image source — déjà vérifiée pour toi

`godot_assets/casque.png` : **512×512, RGBA, fond transparent** — c'est l'entrée idéale pour TRELLIS (l'alpha est conservé par trellis, donc pas de détourage BiRefNet déclenché ; `--bg-removal auto` par défaut le détecte tout seul). Objet unique, centré, non coupé : la checklist « bonne source » du README est déjà remplie. Rien à préparer.

### c) Chaîne TRELLIS — déjà vérifiée également

- `C:\trellis\trellis-cli.exe` : présent (v0.6.0).
- Les **10 GGUF requis** (16,4 Go, f16) dans `C:\Modeles_LLM\trellis2-gguf\` : tous présents (`ss_flow/ss_dec/shape_flow_512/shape_flow_1024/shape_dec/tex_flow_512/tex_flow_1024/tex_dec/dinov3/birefnet`).
- De toute façon le workflow auto-vérifie ça au démarrage (`verifier_trellis()`) et refuse de tourner si un fichier manque.
- Blender (headless) sert aux rendus de contrôle et à la décimation optionnelle — déjà utilisé par les autres workflows du dépôt, et son absence est non bloquante (rendus sautés, master GLB quand même produit).

### d) Divers

- Espace disque dérisoire : ~5-12 Mo par GLB + un .ply intermédiaire.
- Veille consultée : aucune maj trellis.cpp en attente (`maj_en_attente.json` vide au 2026-09-17), la stack est à jour.

---

## 2. Les commandes exactes, dans l'ordre

**Stratégie recommandée : itérer en 512 (~12 min) pour valider le volume sur la planche de contrôle, puis master en 1024 (~1 h) avec décimation « jeu ».** La graine est fixée pour la reproductibilité A/B.

### Étape 1 — itération rapide res 512 (~10-12 min au total)

```bash
cd /c/GIT/generator-assets && uv run python main.py -w mesh_ia -i godot_assets/casque.png --res 512 --seed 42 -o casque
```

Puis **inspecter la planche** `output/mesh_ia/casque/casque_512_planche.png` (source + 4 vues orbitales + texture PBR) : le volume est-il fermé et fidèle ? Le casque étant un objet symétrique assez classique, TRELLIS le gère très bien — c'est l'image de validation historique. Si la silhouette ou le rendu texturé décoit, c'est ici qu'on itère (12 min le cycle, pas 1 h).

### Étape 2 — master res 1024 + GLB « jeu » décimé (~57-60 min au total)

```bash
cd /c/GIT/generator-assets && uv run python main.py -w mesh_ia -i godot_assets/casque.png --res 1024 --faces-cible 30000 --seed 42 -o casque
```

Explication des options :
- `--res 1024` : cascade LR→HR, atlas PBR 2048², micro-relief (meillé d'armure, rayures) — mesuré à 55 min 10 s sur ce casque précis.
- `--faces-cible 30000` : décimation Blender headless (collapse, délimitée UV/SHARP, **textures PBR conservées**) → GLB « jeu » supplémentaire. **30000 = item héro vu de près** (casque équipé / arme tenue). Repères : 10000 = prop de décor vu à 2-10 m, 2000-3000 = clutter répété ×50, et garder ≥8000 pour les silhouettes très courbes. Le **master complet est toujours conservé** à côté.
- `--seed 42` : reproductibilité (relancer redonne le même résultat ; indispensable pour l'A/B 512 vs 1024).
- `-o casque` : nom de base des sorties (dossier + fichiers).

Variante : si la 512 te convainc immédiatement (elle avait été validée en 2026-09-06), tu peux sauter l'étape 1 et lancer directement la 1024 — mais 12 min de contrôle avant 1 h de calcul, c'est une assurance rentable.

---

## 3. Fichiers de sortie attendus

Tout atterrit dans **`C:\GIT\generator-assets\output\mesh_ia\casque\`** :

| Fichier | Contenu | Étape |
|---|---|---|
| `casque_512.glb` | **GLB master 512** — maillage fermé + PBR (atlas 1024² embarqué), ~5,3 Mo, ~144 k faces | 1 |
| `casque_512.ply` | Maillage brut intermédiaire | 1 |
| `casque_512_base.png` | Aperçu de l'**atlas** de textures (⚠️ pas l'image source) | 1 |
| `casque_512_vue0.png` … `vue3.png` | 4 rendus orbitaux studio (EEVEE, azimuts 25/115/205/295°) | 1 |
| `casque_512_planche.png` | Planche de contrôle 2×3 : source + 4 vues + atlas | 1 |
| `casque_512_infos.json` | Durées par étape, nb de faces, chemins, graine | 1 |
| `casque_1024.glb` | **GLB master 1024** — ~12 Mo, ~293 k faces, atlas 2048² | 2 |
| `casque_1024_jeu.glb` | **GLB jeu décimé** (~30 k faces, ~1,5 Mo) — celui qu'on met dans Godot | 2 |
| `casque_1024.ply`, `_base.png`, `_vue0-3.png`, `_planche.png`, `_infos.json` | Idem étape 1 en 1024 | 2 |

(À noter : les sorties de la validation historique existent toujours dans `output/trellis_smoke/` — `casque_512.glb`, `casque_1024.glb` et leurs planches — si tu veux comparer avant même de relancer.)

## 4. Durées estimées (RX 6950 XT, Vulkan, GGUF f16 — mesures réelles du 2026-09-06 sur CE casque)

| Étape | res 512 | res 1024 |
|---|---|---|
| Génération TRELLIS.2 | **8 min 53 s – 10 min 44 s** | **55 min 10 s** (cascade LR→HR) |
| Décimation `--faces-cible` | — (non utilisée) | ~1-2 min |
| Rendus Blender + planche | ~1 min | ~1-2 min |
| **Total** | **~10-12 min** | **~57-60 min** |

Pourquoi c'est lent : le RDNA2 n'a pas de « matrix cores » Vulkan → ~4-6× plus lent que les benchmarks Strix Halo du projet. D'où la règle pratique : **512 pour itérer, 1024 pour le master.** (`--res 1536` existe mais non mesuré.)

## 5. Intégration dans Godot

1. Copier **`casque_1024_jeu.glb`** dans le projet Godot (le master 144-293 k faces reste en réserve pour d'éventuels retraits/zbrusheries).
2. Glisser-déposer dans la scène : Godot l'importe en `PackedScene` avec `MeshInstance3D` et son matériau **PBR complet** (basecolor/metallic/roughness de l'atlas, embarqué dans le GLB — rien d'autre à brancher, pas de `.tres` à créer contrairement au workflow `material3d`).
3. Ajuster l'échelle/rotation selon la convention de ton projet (TRELLIS sort un objet à l'échelle unitaire environ, Y-up comme Godot).

## Points de vigilance connus (MEMORY_BANK §1.14)

- `_base.png` = aperçu de l'atlas, **pas** l'image source — ne pas s'en étonner.
- La décimation ne touche **pas** aux textures : choisir `--faces-cible` selon la distance caméra / nombre d'instances, pas selon la qualité visuelle.
- Chaque run log un récap par étape et écrit `<nom>_<res>_infos.json` — à consulter pour les durées réelles.

---

**Prochaine action concrète : dès que le GPU se libère, lancer `uv run python scripts/check_charge_systeme.py` ; s'il passe (exit 0), enchaîner étape 1 puis étape 2 ci-dessus.** Dis-moi quand la machine est libre et je déroule le plan.
