# Boucle musicale sombre/ambient pour le menu principal Godot — plan de génération

Oui, je peux te la générer — c'est exactement le boulot du workflow `music_bg` de la fabrique : il est
faire pour produire des **boucles musicales sans couture** (moteur ACE-Step 1.5 en local, Vulkan, validé
utilisateur). Mais le GPU est actuellement occupé par un autre travail, et la règle du dépôt est stricte :
**jamais de génération lourde sur une machine chargée** (incident documenté : RTF mesuré 3,3× trop lent
à cause d'une contention GPU). Je ne lance donc rien maintenant — voici le plan exact, prêt à exécuter
dès que la machine est libre.

## 1. Choix du workflow

`music_bg` plutôt que `audio_ambience` : ce dernier génère des ambiances sonores procédurales (forêt,
donjon, tempête…), alors que tu veux une **boucle musicale** (drone composé). `music_bg` enchaîne :

1. génération de plusieurs candidats depuis une description en anglais (ACE-Step 1.5 Turbo, ~42 s par
   candidat de 28 s sur ta RX 6950 XT, natif 48 kHz, licence MIT) ;
2. construction d'une **boucle parfaite** par recherche du meilleur point de coupe ; en mode
   `ambient`, couture par **crossfade equal-power de 1 s** — exactement ce qu'il faut pour un drone
   (le mode `percussive` par défaut aligne sur les mesures/BPM, utile pour de la musique rythmée) ;
3. post-traitement « bed » (passe-haut 80 Hz + creux de présence), normalisation LUFS, export
   **WAV + OGG + MP3 d'écoute** (chaque candidat est fourni en version « boucle ×3 » pour juger la
   couture à l'oreille).

Le paramètre par défaut `--lyrics [Instrumental]` garantit l'absence de voix — c'est le réglage
validé du dépôt pour des lits instrumentaux, donc ton « sans voix » est couvert d'office.

## 2. Vérifications AVANT de lancer (dans l'ordre, depuis `C:\GIT\generator-assets`)

```bash
cd /c/GIT/generator-assets

# (a) Contrôle de charge système — OBLIGATOIRE avant toute génération lourde.
#     Exit 1 = machine occupée → on attend un créneau libre, on ne lance pas.
uv run python scripts/check_charge_systeme.py

# (b) Moteurs et modèles détectés (audio.cpp + GGUF ACE-Step 1.5).
uv run python main.py --check

# (c) Vérifier qu'aucun audiocpp_cli.exe / ffmpeg.exe / sd-cli.exe ne tourne
#     (une seule génération lourde à la fois — VRAM limitée à 16 Go).
```

Si `main.py --check` signale le modèle ACE-Step absent (package turbo ~9,4 Gio dans
`C:\Modeles_LLM\ACE-Step1.5-GGUF`), le télécharger d'abord :

```bash
uv run python scripts/download_acestep15_gguf.py turbo
# si bridage CDN HF : uv run python scripts/telecharger_gros_fichier_parallele.py <url> <dest>
```

C'est précisément le contrôle (a) qui bloquerait maintenant : GPU occupé → exit 1 → on attend. C'est
le comportement voulu.

## 3. La commande de génération (à lancer une fois la machine libre)

```bash
cd /c/GIT/generator-assets
uv run python main.py -w music_bg "dark ambient drone, cold sustained low tones, slowly evolving atmospheric pads, distant icy reverb, minimal, no percussion, no vocals" \
  --duration 20 --candidats 3 --loop-mode ambient --tonalite "D minor" \
  --seed 42 --lufs -16 -o menu_drone_froid
```

Détail des options :

- **prompt en anglais** (règle du dépôt) et volontairement sobre — le plafond de réalisme d'ACE-Step
  est documenté : descriptions simples, tonalité mineure imposée, on ne sur décrit pas ;
- `--duration 20` : boucle cible ~20 s (le workflow génère 28 s par candidat — marge de +8 s pour la
  recherche du meilleur point de bouclage) ;
- `--candidats 3` : 3 propositions à départager à l'écoute (graines 42, 43, 44 — dérivées de
  `--seed 42`, donc reproductibles pour A/B) ;
- `--loop-mode ambient` : couture par crossfade 1 s, le bon mode pour un drone (le défaut
  `percussive` est pensé pour de la musique battue alignée BPM) ;
- `--tonalite "D minor"` : tonalité mineure imposée au planificateur ACE-Step pour asseoir le côté
  sombre ;
- `--lufs -16` : le défaut −30 LUFS est la convention « lit derrière voix off » de la chaîne YouTube ;
  pour un menu de jeu sans voix par-dessus, −16 LUFS (niveau d'écoute) évite de devoir rajouter ~14 dB
  dans Godot. On peut aussi garder −30 et gérer le volume dans le bus audio Godot, au choix ;
- `-o menu_drone_froid` : nom de base des sorties ;
- pas besoin de `--moteur` (ACE-Step 1.5 turbo est le défaut validé, ~40× plus rapide que Music3).

## 4. Sorties attendues et emplacements

Tout atterrit dans `C:\GIT\generator-assets\output\music_bg\` :

| Fichier | Contenu |
| :--- | :--- |
| `menu_drone_froid.ogg` | **la boucle à utiliser dans Godot** (OGG Vorbis) |
| `menu_drone_froid_full.wav` | boucle sans couture 48 kHz PCM16 (~20 s), le « master » |
| `menu_drone_froid_bed.wav` | version normalisée −16 LUFS (base de l'OGG) |
| `menu_drone_froid_preview.mp3` | aperçu MP3 du candidat promu |
| `ECOUTE_cand1..3_boucle_x3.mp3` | **aperçus d'écoute : chaque boucle jouée 3× de suite à −16 LUFS** — c'est le test de la couture |
| `candidats/cand_N_brut.wav` | générations brutes (N = 1..3) |
| `candidats/cand_N_loop_full.wav`, `cand_N_bed.wav`, `cand_N_preview.mp3` | chaque candidat finalisé |
| `recette_mixage_voix.txt` | recette ffmpeg de ducking (sous-produit pour voix off — inutile pour le jeu) |

Le candidat à la meilleure couture est promu à la racine ; les 3 restent disponibles dans `candidats/`.

## 5. Durée estimée

- Génération : ~42 s par candidat de 28 s × 3 ≈ **~2 min** ;
- Post-traitement (recherche du point de bouclage, loudnorm 2 passes, exports OGG/MP3) : ~1-2 min ;
- **Total : environ 4 à 6 minutes** sur machine libre.

## 6. Après la génération

- Je te fais **écouter les `ECOUTE_cand*_boucle_x3.mp3`** — règle du dépôt : tout rendu subjectif est
  soumis à validation avant industrialisation. Tu choisis le candidat ; si le retenu n'est pas celui
  promu automatiquement, sa version finalisée est déjà dans `candidats/`.
- Intégration Godot : importer le `.ogg`, cocher **Loop** sur la ressource `AudioStreamOggVorbis`
  dans l'inspecteur, et le jouer via un `AudioStreamPlayer` dans ta scène de menu (volume fin dans le
  bus audio). La boucle est sans couture par construction.
- Deux réserves honnêtes, listées « pas encore testées » dans le README du workflow :
  `--loop-mode ambient` et `--tonalite`. C'est pour ça qu'on écoute les aperçus ×3 avec attention
  (la couture d'un drone s'entend surtout sur les tenues longues). Si le résultat sonne mal, on
  retombe sur le mode `percussive` validé et/ou on retire `--tonalite`.
- Si le candidat retenu mérite mieux : A/B avec la variante `--variante xl-turbo` (DiT 4B, ~2× plus
  lent, qualité accrue, validée elle aussi) en gardant la même graine pour comparer.

Dis-moi quand le GPU est libéré (ou veux-tu que je surveille avec `check_charge_systeme.py` ?) et je
lance la génération telle quelle.
