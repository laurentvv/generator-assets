# Boucle musicale sombre/ambient pour le menu principal Godot — plan de génération

Bonne nouvelle : ce besoin est exactement le terrain du workflow **`music_bg`** du dépôt, avec le moteur **ACE-Step 1.5 Turbo** (défaut, validé utilisateur le 2026-09-05, ~36× plus rapide que MiniMax-Music3, licence **MIT** donc aucune mention obligatoire dans le jeu). Pour un drone ambient, on utilisera le mode de bouclage `--loop-mode ambient` (crossfade equal-power ~1 s queue→tête, pas d'alignement BPM — un drone n'a pas de pulsation à caler).

**Le GPU étant actuellement occupé par un autre travail, je ne lance rien maintenant** : la règle du dépôt est formelle (jamais de génération lourde sur une machine chargée — cf. smoke test v0.7.3 du 2026-09-08 : RTF mesuré 3,3× trop lent à cause d'une contention GPU). Tout est prêt ci-dessous, il n'y aura qu'à relancer dès que la machine se libère.

---

## 1. Vérifications à faire AVANT de lancer (dans l'ordre)

Toutes les commandes se lancent **depuis la racine du dépôt** `C:\GIT\generator-assets` (Git Bash).

### 1.1 Charge système (obligatoire, doit passer)

```bash
uv run python scripts/check_charge_systeme.py
```

- **Exit 0** = machine libre → on peut lancer. **Exit 1** = machine occupée → on attend un créneau, on ne lance pas.
- Seuils par défaut : CPU 60 %, GPU 40 %, RAM 90 %, VRAM 80 %. Étant donné que le GPU est déjà pris par un autre travail, ce script sortira actuellement en échec (⛔ GPU) — c'est le comportement attendu ; je le relancerai dès la fin de l'autre job.

### 1.2 Aucune génération audio déjà en cours

```bash
tasklist | grep -i audiocpp || echo "aucun audiocpp_cli en cours"
```

(Évite toute contention/superposition de jobs Vulkan sur le même GPU.)

### 1.3 Moteur et modèle présents (déjà vérifiés à l'instant en lecture seule)

- `C:\audio-cpp\audiocpp_cli.exe` ✅ présent (audio.cpp v0.8.0 du 2026-09-16) ;
- `C:\Modeles_LLM\ACE-Step1.5-GGUF\turbo\ace-step-1.5-turbo-bf16.gguf` ✅ présent (9,4 Gio, paquet monolithique). Rien à télécharger.

Si un jour le modèle manquait : `uv run python scripts/download_acestep15_gguf.py turbo`.

---

## 2. Commandes exactes à exécuter, dans l'ordre

### Étape 1 — contrôle de charge (cf. §1.1, doit exit 0)

```bash
uv run python scripts/check_charge_systeme.py
```

### Étape 2 — génération : 3 candidats drone ambient de ~20 s, graines fixes

```bash
uv run python main.py -w music_bg "dark ambient drone, cold glacial synth pads, deep sustained low tones, bleak hollow atmosphere, distant metallic shimmer, very slow evolution, instrumental only, no vocals, no drums, no percussion" --duration 20 --candidats 3 --loop-mode ambient --seed 42 --lufs=-18 -o menu_drone_sombre
```

Détail des options :
- **prompt en anglais** (règle du dépôt), sobre et sans ancre artiste — le registre « nappes sombres / ambient » est bien maîtrisé par ACE-Step (le « plafond pop » documenté dans MEMORY_BANK §1.11 concerne le réalisme instrumental rock basse/batterie/guitares, pas les nappes) ;
- `--duration 20` : cible de boucle ≈ 20 s (le moteur génère 28 s pour garder une marge, ACE-Step terminant ses morceaux par un long fondu de sortie) ;
- `--candidats 3` : 3 propositions générées puis départagées automatiquement par la qualité de couture (Δ dB au raccord boucle) ; toutes sont finalisées, la meilleure est promue à la racine ;
- `--loop-mode ambient` : bouclage par crossfade equal-power ~1 s dans la zone d'énergie stable — la bonne stratégie pour un drone (le mode `percussive` par défaut sert aux musiques à tempo) ;
- `--seed 42` : graines déterministes 42/43/44 → reproductible pour A/B ou regénération (contrat du dépôt) ;
- `--lufs=-18` : le défaut −30 LUFS est calibré pour un lit derrière une voix off YouTube ; pour une musique de menu Godot autonome, −18 LUFS est un niveau plus approprié (le `.ogg` exporté pour Godot est dérivé du bed, donc de cette cible) ;
- `-o menu_drone_sombre` : base du nom des fichiers de sortie.

### Étape 3 — aperçus d'écoute (la boucle répétée 3× pour juger la couture)

```bash
uv run python scripts/ecoute_candidat_music_bg.py 1
uv run python scripts/ecoute_candidat_music_bg.py 2
uv run python scripts/ecoute_candidat_music_bg.py 3
```

Chaque script produit `ECOUTE_cand<N>_boucle_x3.mp3` (boucle ×3 à −16 LUFS, niveau d'écoute) : c'est le meilleur test « tourne sans couture pendant des minutes » avant intégration. (Le script coupe en mode percussive par défaut, mais bascule automatiquement en ambiante quand aucune pulsation n'est détectée — ce sera le cas du drone.)

### Variantes optionnelles (si les 3 premiers candidats ne conviennent pas)

```bash
# Tonalité froide imposée au planner (ACE-Step only) :
uv run python main.py -w music_bg "dark ambient drone, cold glacial synth pads, bleak hollow atmosphere, very slow evolution, instrumental only, no vocals" --duration 20 --candidats 3 --loop-mode ambient --seed 52 --lufs=-18 --tonalite "D minor" -o menu_drone_sombre_Dm

# Variante DiT 4B distillée (~2× plus lente, qualité parfois supérieure) :
uv run python main.py -w music_bg "dark ambient drone, cold glacial synth pads, bleak hollow atmosphere, very slow evolution, instrumental only, no vocals" --duration 20 --candidats 3 --loop-mode ambient --seed 42 --lufs=-18 --variante xl-turbo -o menu_drone_sombre_xl
```

---

## 3. Fichiers de sortie attendus

Tout arrive dans **`C:\GIT\generator-assets\output\music_bg\`** :

| Fichier | Contenu | Usage |
|---|---|---|
| `menu_drone_sombre.ogg` | Boucle OGG Vorbis (dérivée du bed −18 LUFS) | **Le fichier pour Godot** |
| `menu_drone_sombre_full.wav` | Boucle sans couture 48 kHz PCM16, normalisée en pic −1 dBFS | Master/source |
| `menu_drone_sombre_bed.wav` | Version normalisée −18 LUFS (loudnorm 2 passes ffmpeg) | Écoute de référence niveau jeu |
| `menu_drone_sombre_preview.mp3` | Aperçu MP3 192k | Écoute rapide |
| `recette_mixage_voix.txt` | Recette ffmpeg ducking (pour voix off) | Pas utile pour le jeu, inoffensif |
| `candidats/cand_N_brut.wav` | Génération brute (28 s) de chaque candidat | Re-post-traitement possible |
| `candidats/cand_N_loop_full.wav` | Boucle complète de chaque candidat | Comparaison |
| `candidats/cand_N_bed.wav` + `cand_N_preview.mp3` | Chaque candidat finalisé | Comparaison |
| `ECOUTE_cand<N>_boucle_x3.mp3` (après étape 3) | Boucle ×3 à −16 LUFS | **Test de couture à l'écoute** |

Intégration Godot : importer le `.ogg`, cocher **Loop** dans l'onglet Import, rejouer via un `AudioStreamPlayer` sur un bus « Music ». L'OGG boucle sans trou en 4.x.

---

## 4. Durée estimée (machine libérée)

- Génération : 3 candidats × 28 s de musique à RTF ~1,5 (mesuré sur RX 6950 XT, Vulkan) ≈ **~45 s par candidat**, soit **~2 min 15 s** de génération GPU ;
- Post-traitement (recherche de couture, vérification, loudnorm 2 passes, OGG/MP3) : ~15–30 s par candidat ;
- **Total : ~4 à 6 minutes** tout compris, hors écoute. (Pour comparaison, le moteur legacy MiniMax-Music3 prendrait ~25 min par candidat — d'où le choix d'ACE-Step.)

---

## 5. Notes et réserves honnêtes

1. **Durée finale légèrement variable** : en mode ambient, la boucle est découpée dans la zone d'énergie stable du brut de 28 s → la boucle fera typiquement ~17–21 s, pas exactement 20,0 s. C'est sans conséquence pour un menu.
2. **Post-traitement « lit de voix »** : le workflow applique un highpass 80 Hz + un léger creux à 2,8 kHz (conçu pour laisser la place à une voix off). Le drone garde tout son spectre au-dessus de 80 Hz ; si tu veux du infrabasse < 80 Hz, on le mentionnera et j'ajusterai après ton verdict.
3. **`--loop-mode ambient` figure encore « non testé » dans le statut README** (daté 2026-09-06). Les fichiers `ECOUTE_cand<N>_boucle_x3.mp3` sont précisément là pour valider la couture ; après ton écoute je consignerai le verdict dans `docs/MEMORY_BANK.md` / statut README (workflow déjà existant, rien à créer).
4. **Pas de voix garantie** : `lyrics=[Instrumental]` par défaut + « no vocals » dans le prompt ; ACE-Step sans paroles = instrumental natif.
5. **Licence MIT** : aucune mention d'attribution requise pour le jeu (contrairement à Music3 qui imposerait une mention).

**Prochaine étape dès que le GPU se libère** : je relance `check_charge_systeme.py`, et s'il passe j'exécute les étapes 1→3 d'un bloc, puis je te soumets les 3 `ECOUTE_*.mp3` à l'écoute — c'est toi qui choisiras le candidat qui part dans Godot.
