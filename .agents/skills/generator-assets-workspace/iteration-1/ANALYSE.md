# Analyse iteration-1 — skill `generator-assets`

## Chiffres

| Métrique | With skill | Without skill | Delta |
| :--- | :--- | :--- | :--- |
| Taux de réussite (18 assertions) | 100 % | 100 % | 0 |
| Temps moyen | 335,4 s | 308,7 s | +26,6 s |
| Tokens moyens | 655 537 | 769 902 | **−114 365 (−15 %)** |

## Observations de l'analyste

1. **Assertions non discriminantes** : les 18 assertions passent dans les deux configurations. Le
   routage et les garde-fous (check_charge_systeme, prompt anglais, seed) sont déjà bien portés par
   README + AGENTS.md — les agents baseline les retrouvent en explorant le dépôt. La valeur du skill
   ne se mesure donc pas en « réponses justes vs fausses » sur ces cas, mais ailleurs (voir 2-4).
2. **Efficience** : le skill réduit systématiquement les tokens (3 runs sur 3 : 288k<295k,
   331k<415k, 1,35M<1,60M) — l'agent va droit au but au lieu de fouiller README (2000 lignes) +
   MEMORY_BANK. Gain ~15 % en moyenne, davantage sur les cas complexes (eval 2 : −16 %).
3. **Écart de temps contre-intuitif** : avec skill plus lent en moyenne (+27 s), porté par l'eval 2
   (649 s vs 392 s) où l'agent with_skill a fait une vérification approfondie (38 tool calls,
   vérification des chemins de sortie dans le code). Les evals 0-1 étaient plus rapides avec le skill
   (139 s vs 260 s ; 218 s vs 275 s). Variance élevée → un seul run par eval, à ne pas sur-interpréter.
4. **Découverte précieuse du baseline** : le run *sans skill* de l'eval 2 a ressorti un écueil
   opérationnel critique absent du skill initial — LTX-2.5 **et** H3 cassés sur la sd-cli installée
   (master-864), production via la build parallèle `C:\SD-6b3edaa\` + préfixe `SD_CLI_PATH`
   (MEMORY_BANK §1.16-1.19). **Corrigé** : l'écueil est maintenant intégré au SKILL.md (§3 vidéo)
   et au catalogue de référence. Les futurs runs with_skill évitent l'OOM ~2 min garanti.
5. **Qualité perçue équivalente** : les 6 réponses sont complètes, structurées, honnêtes sur les
   réserves (features « non testées » signalées, licences citées, intégration Godot décrite).

## Conclusion iteration-1

Le skill atteint son objectif (routage fiable + garde-fous + recettes) avec un coût d'exploration
réduit. L'écart de pass-rate ne peut pas s'améliorer sur ces 3 cas (plafond atteint des deux côtés) ;
la prochaine itération gagnerait à : (a) des evals plus discriminants (questions auxquelles README
ne répond qu'en creux : choix entre workflows proches, gestion d'un échec/écueil réel), (b) vérifier
que l'écueil sd-cli maintenant dans le skill est bien restitué.
