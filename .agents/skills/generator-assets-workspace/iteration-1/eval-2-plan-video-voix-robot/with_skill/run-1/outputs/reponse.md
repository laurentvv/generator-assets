# Intro chaîne YouTube — plan cinématique 5 s + voix robot

Rien n'a été lancé : le GPU est actuellement occupé par un autre travail. Voici le plan
d'exécution complet, prêt à déclencher dès qu'un créneau libre se présente.

## 0. Ce que j'ai choisi (routage)

- **Vidéo** : workflow `monoplan_ia` — plan-séquence cinématique depuis une image fixe
  (LTX-2.5 I2V + ralenti motion-compensé + zoom pur conçu). C'est la recette validée
  utilisateur du 2026-09-10 (« c'est parfait, résultat magnifique » — intro Vent-Gris) ;
  c'est aussi le workflow utilisé par `ai-doc2video` pour les hooks cinématiques.
- **Voix** : workflow `voix_robot` — recette VALIDÉE et figée le 2026-09-17
  (Kokoro `af_heart`, pitch +30 %, ring modulation 120 Hz, tempo 0,65, gain −4 dB).
- Le travelling avant lent est obtenu par la combinaison validée : prompt de mouvement
  « dolly-in » pendant la génération + rampe de zoom conçue 1.10 → 1.32 par-dessus le
  ralenti — aucune mesure de tracking dans le warp, donc aucune vibration de caméra possible.

## 1. Vérifications AVANT de lancer (dans l'ordre)

1. **Créneau GPU libre (bloquant)** :
   ```bash
   uv run python scripts/check_charge_systeme.py
   ```
   Exit 0 obligatoire. Tant que le GPU est occupé par l'autre travail, on **attend** —
   exit 1 = on ne lance pas (incident documenté : RTF mesuré 3,3× trop lent à cause d'une
   contention GPU). Seuils ajustables (`--cpu-threshold`, `--gpu-threshold`, …) si besoin.
2. **Moteurs et modèles détectés** :
   ```bash
   uv run python main.py --check
   ```
   Vérifie sd-cli/LTX-2.5 et audio.cpp ; côté kokoro, le binaire avec eSpeak embarqué est
   résolu automatiquement par le workflow (MEMORY_BANK §1.21).
3. **⚠️ Image source absente** : `output/scene_intro.png` **n'existe pas actuellement dans
   le dépôt** (vérifié à l'instant). Deux options :
   - (a) tu y déposes ton image (n'importe quel format/ratio : le workflow recadre
     automatiquement en 16:9 832×480 par crop Lanczos) ;
   - (b) je la génère d'abord avec la commande 0 ci-dessous.
4. **Une seule génération lourde à la fois** : vidéo d'abord (~20 min), la voix ensuite —
   jamais en parallèle, les moteurs se battent pour les 16 Go de VRAM.
5. Vérifier qu'aucun `sd-cli.exe` / `audiocpp_cli.exe` / `ffmpeg.exe` ne tourne au démarrage
   (et ne jamais tuer celui de l'autre travail en cours).
6. `--seed 42` fixée partout (reproductibilité A/B, contrat des dépôts consommateurs).

## 2. Les commandes exactes, dans l'ordre

### Commande 0 — secours, uniquement si `output/scene_intro.png` n'existe pas encore

```bash
uv run python main.py -w generate "dark server room interior, long rows of black server racks with blinking status LEDs, cold blue light, thin haze, cinematic wide shot" -t prop --seed 42 -o scene_intro -d output
```

(~1-2 min, Flux 1024². À valider visuellement avant de lancer la vidéo : c'est elle qui
fixe le cadrage du plan. Prompt en anglais, règle du dépôt.)

### Commande 1 — le plan cinématique 5 s

```bash
uv run python main.py -w monoplan_ia "Slow cinematic dolly-in through a dark server room, long rows of black server racks with blinking status LEDs, thin haze drifting in cold blue light, moody sci-fi atmosphere" -i output/scene_intro.png --monoplan-duration 5 --ambiance "dark server room hum, low server fan drone, faint electrical buzz" --seed 42 -o intro_chaine -d output/monoplan_ia
```

Explication des choix :
- **prompt en anglais** (règle du dépôt) : il décrit le mouvement de caméra + la scène —
  c'est lui qui pilote le travelling avant pendant la génération LTX-2.5 ;
- `--monoplan-duration 5` : 65 trames générées (défaut = plafond GPU stable, max ~81) puis
  ralenties avec interpolation motion-compensée vers exactement 5 s — le ralenti divise la
  respiration caméra du modèle par le facteur d'étirement, d'où l'aspect « travelling lent » ;
- `--zoom-debut/--zoom-fin` **laissés aux défauts validés 1.10 → 1.32** : la rampe de zoom
  pur smootherstep par-dessus le ralenti, c'est elle qui « signe » l'avancée vers les baies ;
- `--ambiance` : lit sonore IA optionnel (SA3 Small SFX, audio.cpp) « salle serveur » —
  muxé automatiquement dans une version d'écoute `_avec_ambiance.mp4`. Pour une intro de
  chaîne c'est un vrai plus ; on peut le retirer si tu préfères poser la voix sur silence ;
- `--seed 42` : reproductibilité ;
- `-d output/monoplan_ia` : pour que tout atterrisse proprement dans `output/monoplan_ia/`
  (sinon le défaut du CLI écrit dans `godot_assets/`).

### Commande 2 — la voix robot

```bash
uv run python main.py -w voix_robot "Welcome to the system, human." --seed 42 -o welcome_robot
```

- **Aucune option `--robot-*`** : les défauts SONT la recette validée (17 essais, verdict
  utilisateur « c'est bien »). On ne modifie pas pitch/ringmod/tempo/gain sans accord explicite.
- À ce tempo (0,65), la réplique durera ~4-5 s : elle tient dans le plan de 5 s.

### Commande 3 — bonus (CPU seul, pas de GPU) : monter la voix sur l'ambiance

```bash
ffmpeg -i output/monoplan_ia/intro_chaine_5.0s_1080p_avec_ambiance.mp4 -i output/voix_robot/welcome_robot/welcome_robot.wav -filter_complex "[1:a]adelay=400:all=1[voix];[0:a][voix]amix=inputs=2:duration=first:weights='0.35 1.0'[aout]" -map 0:v -map "[aout]" -c:v copy -c:a aac -b:a 192k output/monoplan_ia/intro_chaine_5.0s_final_intro.mp4
```

- Voix en entrée à 400 ms, ambiance ramenée à 35 % pour que la voix robot passe devant ;
  `duration=first` coupe à 5 s pile. Le `adelay` est ajustable (300-800 ms selon le goût).
- Si tu préfères un ducking automatique de l'ambiance sous la voix (recette sidechaincompress
  validée du dépôt, comme pour les lits musicaux des voix off), dis-le-moi — je prépare la commande.

### Variante diffusion — master 4K UHD (recommandé pour YouTube)

Le piège YouTube : une source 1080p est écrasée par la compression AVC1 (~4-6 Mbps) ; un
master 4K force le profil haut débit VP09/AV01, même pour les spectateurs en 1080p. Donc :
d'abord on valide le 1080p (commande 1), puis on produit le master 4K **sans regénérer le
plan** en reprenant les trames brutes :

```bash
uv run python main.py -w monoplan_ia --monoplan-source output/monoplan_ia/intro_chaine_brut.webm --monoplan-duration 5 --4k --seed 42 -o intro_chaine_4k -d output/monoplan_ia
```

(Upscale IA 4x-UltraSharp des 65 trames brutes + ralenti/zoom en 3328×1920 + conform
3840×2160 @ 30 fps h264_amf ~45 Mbps. La voix se remonte dessus avec la commande 3 en
changeant simplement le nom du fichier d'entrée vidéo.)

## 3. Fichiers de sortie attendus

| Étape | Fichier | Emplacement |
| :--- | :--- | :--- |
| 0 (secours) | `scene_intro.png` | `output/` |
| 1 | `intro_chaine_amorce_832x480.png` (amorce recadrée 16:9) | `output/monoplan_ia/` |
| 1 | `intro_chaine_brut.webm` (65 trames LTX brutes — sert à la reprise 4K) | `output/monoplan_ia/` |
| 1 | `intro_chaine_5.0s_1080p_ralenti.mp4` (intermédiaire) | `output/monoplan_ia/` |
| 1 | `intro_chaine_5.0s_1080p.mp4` (**master muet**) | `output/monoplan_ia/` |
| 1 | `intro_chaine_ambiance.wav` (lit sonore SA3) | `output/monoplan_ia/` |
| 1 | `intro_chaine_5.0s_1080p_avec_ambiance.mp4` (master + ambiance) | `output/monoplan_ia/` |
| 2 | `welcome_robot.wav` (PCM 16-bit 24 kHz, l'effet appliqué) | `output/voix_robot/welcome_robot/` |
| 2 | `welcome_robot.mp3` (copie d'écoute) | `output/voix_robot/welcome_robot/` |
| 2 | `welcome_robot_brut.wav` (TTS brut — pour retoucher l'effet sans regénérer) | `output/voix_robot/welcome_robot/` |
| 3 (bonus) | `intro_chaine_5.0s_final_intro.mp4` (vidéo + ambiance + voix) | `output/monoplan_ia/` |
| Variante 4K | `intro_chaine_4k_5.0s_4k.mp4` (3840×2160 @ 30 fps) | `output/monoplan_ia/` |

## 4. Durées estimées (RX 6950 XT, machine sinon inoccupée)

| Étape | Durée |
| :--- | :--- |
| Commande 1 — génération LTX (65 trames, 8 steps) | ~15 min |
| Commande 1 — ralenti mci + zoom + ambiance + mux | ~4 min |
| Commande 2 — voix robot (TTS kokoro + chaîne FFmpeg) | ~1-2 min |
| Commande 3 — assemblage ffmpeg (CPU seul) | < 1 min |
| **Total GPU occupé (commandes 1 + 2)** | **~20-22 min** |
| Variante 4K ensuite (upscale IA + chaîne 4K, sans regénération LTX) | ~18 min de plus |

À relire au moment de lancer : ces estimations supposent la machine inoccupée — d'où le
gate `check_charge_systeme.py` en étape 1.

## 5. Après la génération (règles du dépôt)

- Je te livre les chemins des fichiers + la seed (42) ;
- rendu subjectif : je te fais **écouter la voix et regarder le plan avant toute
  industrialisation** (règle : jamais de workflow pour un test non validé) ;
- si la combinaison « plan + voix » est validée comme intro réutilisable de la chaîne, on
  en discutera la mise en workflow réutilisable ; sinon je consigne dans MEMORY_BANK ;
- écueil éventuel (device-lost Vulkan LTX au-delà de ~81 trames, etc.) → consigné dans
  MEMORY_BANK. On reste à 65 trames, sous le plafond.

**Prochaine action** : dès que le GPU est libre, je déroule les vérifications (section 1)
puis les commandes 0→3 dans l'ordre. Dis-moi aussi si tu veux le master 4K directement
(`--4k` à la commande 1, ~18 min au lieu de ~20 pour le 1080p, et dans ce cas pas besoin
de la variante de reprise).
