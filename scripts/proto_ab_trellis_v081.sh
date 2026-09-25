#!/usr/bin/env bash
# proto_ab_trellis_v081.sh — A/B perf trellis v0.6.0 (production C:\trellis) vs v0.8.1 prébuilt (C:\trellis-081)
#
# Contexte : régression +51 % de v0.8.0 confirmée par A/B propre nuit 24→25/09 → rollback v0.6.0.
# v0.8.1 (publiée le 25/09) = packaging rétopologie, prebuilt annoncé sans changement fonctionnel
# → A/B de contrôle demandé par l'utilisateur le 25/09 (« prépare le test et je reboot avant de le lancé »).
#
# LANCER APRÈS REBOOT (machine propre) :
#   cd /c/GIT/generator-assets && bash scripts/proto_ab_trellis_v081.sh
#
# Idempotent : chaque jambe déjà terminée (GLB + duree.txt présents) est skippée — relançable tel quel.
# Jambes STRICTEMENT séquentielles (règle : jamais 2 jobs GPU en parallèle), seed 42 des deux côtés.
set -u

REPO=/c/GIT/generator-assets
IMG="$REPO/godot_assets/casque.png"
MODELES="C:/Modeles_LLM/trellis2-gguf"
OUTROOT="$REPO/output/trellis_ab_v081"
RES=512
SEED=42
BASELINE_S=644   # v0.6.0, matrice propre du 24/09 (même image, même résolution)

leg() {
  local label="$1" bindir="$2"
  local outdir="$OUTROOT/$label"
  local glb="$outdir/casque_${label}.glb"
  echo ""
  echo "================ JAMBE $label ($bindir) ================"
  if [ -f "$glb" ] && [ -f "$outdir/duree.txt" ]; then
    echo "[$label] déjà fait ($(cat "$outdir/duree.txt")s) — skip"
    return 0
  fi
  mkdir -p "$outdir"
  cd "$REPO" || return 1
  echo "[$label] check_charge_systeme…"
  if ! uv run python scripts/check_charge_systeme.py; then
    echo "[$label] machine chargée — ABANDON. Relancer le script plus tard (jambes faites conservées)."
    return 1
  fi
  local t0 t1 rc
  t0=$(date +%s)
  (cd "$bindir" && ./trellis-cli.exe -i "$IMG" -o "$glb" -m "$MODELES" --res "$RES" --seed "$SEED") \
    > "$outdir/run.log" 2>&1
  rc=$?
  t1=$(date +%s)
  echo "$((t1-t0))" > "$outdir/duree.txt"
  echo "[$label] rc=$rc durée=$((t1-t0))s (référence v0.6.0 du 24/09 : ${BASELINE_S}s)"
  if [ "$rc" -ne 0 ]; then
    echo "[$label] ÉCHEC — $outdir/run.log (10 dernières lignes) :"
    tail -10 "$outdir/run.log"
    return 1
  fi
  ls -la "$outdir" | grep -E "glb|ply|png"
  return 0
}

echo "A/B trellis $RES px — image $(basename "$IMG") — seed $SEED"
echo "Sorties : $OUTROOT"

leg v060 /c/trellis      ; r1=$?
leg v081 /c/trellis-081  ; r2=$?

echo ""
echo "================ RÉSUMÉ ================"
for label in v060 v081; do
  glb="$OUTROOT/$label/casque_${label}.glb"
  if [ -f "$glb" ] && [ -f "$OUTROOT/$label/duree.txt" ]; then
    echo "$label : $(cat "$OUTROOT/$label/duree.txt")s — GLB $(du -h "$glb" | cut -f1) — $glb"
  else
    echo "$label : incomplet"
  fi
done
echo ""
echo "Verdict : v081 ≈ v060 (±15 %) → upgrade production v0.8.1 (backup + version.json + README)."
echo "          v081 ~ +50 % (comme v0.8.0) → conserver v0.6.0, purger l'entrée de veille (attendre un vrai fix perf)."
echo "          Dans les deux cas : comparer AUSSI le rendu des 2 GLB (géométrie/textures) avant verdict."
[ "$r1" -eq 0 ] && [ "$r2" -eq 0 ] || exit 1
