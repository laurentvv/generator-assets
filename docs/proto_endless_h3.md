# 🧪 Prototype « endless » H3 Ref2VA — séquence vidéo longue par chunks

> **Statut : PRÉPARÉ, NON LANCÉ, NON VALIDÉ.** Ce document décrit le prototype de
> boucle multi-chunks MiniMax-H3 Ref2VA (pendant CLI du nœud ComfyUI
> [HR-Endless-Sampler](https://github.com/hradec/ComfyUI-HR-Endless-Sampler)).
> La brique unitaire (1 chunk) est **validée** → workflow `h3_ref2va`, lancé par ce
> prototype en mode `--turbo` (LoRA distillé 8 steps, validé le 2026-09-09 — ~38 min/chunk,
> raccord référence supérieur ; MEMORY_BANK §1.16). **La boucle elle-même n'a jamais été jugée** : les raccords
> chunk→chunk sont le point non validé. Ne deviendra un workflow qu'après
> validation utilisateur du résultat (règle AGENTS.md).

## 📏 Ce que ça produit (estimations mesurées, RX 6950 XT / 16 Go / 31,8 Go RAM, mode turbo)

| Fenêtre | Résultat attendu |
|---|---|
| **24 h** | ~34-36 chunks de 22 frames → **31-33 s de vidéo continue avec audio** (864×480, webm) |
| ~1 h 15 | 2 chunks → de quoi juger **le premier raccord** (recommandé comme 1re étape) |

Coût d'un chunk en turbo (~38 min, validé 2026-09-09) : encodage VAE de la référence
~14,5 min (CPU/swap) • Qwen3-VL ~1,5 min • sampling 8 steps ~18 min (134 s/step,
graph-cut) • décodage ~4,2 min. (Recette de base 20 steps : ~70 min/chunk — voir
MEMORY_BANK §1.16 pour l'A/B.)

**Bonus turbo pour CETTE boucle** : le raccord référence est **meilleur** qu'en recette
de base (frame 1 quasi identique à la dernière frame de la réf — le point critique
d'un chaînage chunk→chunk). Le risque n° 1 du proto en est réduit.

**Leviers restants** (non validés) : résolution ÷2 → ~45-60 s/24 h •
**RAM 64 Go = le vrai déblocage** (fin du swap VAE + DiT résident GPU
→ chunk ~10-15 min → **1,5-2,5 min/24 h**). Comparaison : Wan 2.2 sur 24 h ≈ 6-9 min
mais plans indépendants, sans continuité ni audio.

## 🚀 Lancement (quand décidé, machine LIBRE)

```bash
# 1. Vérifier la charge (règle AGENTS.md) — exit 1 = attendre
uv run python scripts/check_charge_systeme.py

# 2. Lancer la boucle détachée (survit à la fermeture de session)
mkdir -p output/endless_dragon_24h
nohup uv run python scripts/proto_endless_h3.py --output-dir output/endless_dragon_24h \
  > output/endless_dragon_24h/boucle.log 2>&1 & disown
```

Le script (`scripts/proto_endless_h3.py`) : storyboard de 18 prompts éditable en tête
de fichier (marche → feu → envol → lac → falaises → grotte → trésor → sommeil),
reprise automatique au premier chunk manquant, 3 essais/chunk espacés de 15 min
(absorbe un check_charge refusant), fenêtre 23 h (`--deadline-min`), concat finale
automatique (`endless_final.webm`, `-c copy`).

## 👀 Surveillance & arrêt

```bash
tail -f output/endless_dragon_24h/boucle.log      # journal en direct
ls output/endless_dragon_24h/chunk_*.webm         # avancement (1 chunk ≈ 38 min en turbo)
```

**Critère go/no-go (1er raccord, ~1 h 15)** : extraire la dernière frame du chunk_01 et
la première du chunk_02 — si le dragon mute ou saute franchement, arrêter (inutile de
brûler 11 h sur une dérive). Micro-sauts possibles : Ref2VA en CLI n'a pas de boundary
keyframe (incompatible `--init-img`), la référence seule porte la continuité.

**Arrêt d'urgence** (tout ce qui est généré est conservé) :
```bash
powershell -NoProfile -Command 'Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "proto_endless_h3|h3_ref2va" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }; Get-Process sd-cli -ErrorAction SilentlyContinue | Stop-Process -Force'
```

## ✅ Après un run conclu

1. Juger `endless_final.webm` (œil + oreille, continuité vidéo ET audio sur les raccords).
2. Consigner le verdict dans MEMORY_BANK §1.16 (nombre de chunks, dérive observée, timings).
3. Si validé → transformer la boucle en workflow `video_endless` (AGENTS.md : tout test
   validé devient un workflow) ; si non validé → noter les écueils et les leviers.
