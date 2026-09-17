# Plan de production — Intro chaîne YouTube : plan cinématique 5 s + voix de robot

**Demande** : plan cinématique de 5 secondes à partir de `output/scene_intro.png` (travelling avant lent, ambiance salle serveur sombre) + voix de robot qui dit « Welcome to the system, human. »

**Réponse courte** : les deux briques existent déjà comme workflows validés du dépôt —
`monoplan_ia` (plan-séquence cinématique depuis une image, recette validée le 2026-09-10,
MEMORY_BANK §1.17) et `voix_robot` (Kokoro-82M + ring modulation, recette validée
 **aujourd'hui même** le 2026-09-17, MEMORY_BANK §1.21). Rien à inventer, deux commandes suffisent.

⚠️ **Rien n'est lancé maintenant** : le GPU est occupé par un autre travail. Conformément à la
règle du dépôt, `scripts/check_charge_systeme.py` doit retourner exit 0 avant toute génération
lourde (l'incident du smoke test v0.7.3 du 2026-09-08 a mesuré un RTF 3,3× trop lent à cause
d'une contention GPU — on ne lance jamais sur une machine chargée, on attend le créneau).

---

## 1. Vérifications AVANT de lancer (dans l'ordre)

### 1.1 Créneau GPU libre (la porte d'entrée)

```bash
cd /c/GIT/generator-assets
uv run python scripts/check_charge_systeme.py
```

- **exit 0** → machine libre, on peut lancer. **exit 1** → machine occupée : on attend (aucun
  contournement, c'est la règle du dépôt). Seuils par défaut : CPU 60 %, GPU 40 %, RAM 90 %,
  VRAM 80 %.
- À repasser avant **chaque** lancement GPU (vidéo, puis audio) — pas seulement au début.

### 1.2 ⚠️ L'image source `output/scene_intro.png` N'EXISTE PAS actuellement

Je l'ai vérifié à l'instant en lecture seule : le fichier est absent du dossier `output/`
(aujourd'hui 2026-09-17). Deux possibilités :

- **Tu as l'image ailleurs** → la copier à cet emplacement (ou me donner son chemin, `-i`
  accepte n'importe quel chemin) :
  ```bash
  cp /chemin/vers/ton/image.png /c/GIT/generator-assets/output/scene_intro.png
  ```
- **Il faut la générer** → commande de secours (Flux.1 Vulkan, ~2-4 min, GPU requis) :
  ```bash
  uv run python scripts/check_charge_systeme.py   # encore la porte d'entrée
  uv run python main.py -w generate "Dark server room interior, long rows of server racks with blinking status LEDs, cold blue and teal glow, thin haze, deep shadows, cinematic composition" -s 1024 --seed 42 -o scene_intro -d output
  ```

Note : le workflow recadre automatiquement l'image au 16:9 exact (recadrage centré Lanczos
832×480, `conformer_amorce_16_9`). Toute proportion d'origine fonctionne ; si l'image est
carrée, haut et bas seront rognés — préparer une image proche du 16:9 si tu veux maîtriser
le cadrage.

### 1.3 ⚠️ CRITIQUE — LTX-2.5 est cassé sur la sd-cli installée : passer par le build parallèle

Piège connu du dépôt (MEMORY_BANK §1.17, confirmé le 2026-09-14) : la sd-cli **installée**
(`C:\SD\sd-cli.exe` = master-864) casse LTX-2.5 (`ltxav workspace capacity check` puis
`ErrorOutOfDeviceMemory` — régression mémoire introduite entre master-841 et 864). La dernière
build LTX validée est **6b3edaa (master-841)**, disponible en installation parallèle de
production : `C:\SD-6b3edaa\sd-cli.exe` (vérifiée présente à l'instant).

Le chemin du binaire se surcharge avec la variable d'environnement `SD_CLI_PATH` (lue par
`core/config.py`) — d'où le préfixe `SD_CLI_PATH=...` dans ma commande vidéo ci-dessous.
**Sans ce préfixe, la génération échouera en OOM vers ~2 min.**

(Précision pour la variante 4K : l'étape d'upscale IA appelle `C:\SD\sd-cli.exe` en dur dans
`scripts/upscale_video_ai.py` — c'est voulu et sans risque, l'upscale Flux/UltraSharp est
validé sur master-864 ; seule la génération LTX exige 6b3edaa.)

### 1.4 Modèles et binaires (déjà vérifiés pour toi, tous présents)

| Élément | Emplacement | Statut |
|---|---|---|
| DiT LTX-2.5 Distilled Q4_K_M | `C:\Modeles_LLM\LTX-2.5-Distilled-Q4_K_M.gguf` | ✅ présent |
| VAE vidéo LTX | `C:\Modeles_LLM\ltx-2.5-video-vae-conv-bf16.safetensors` | ✅ |
| LLM texte LTX (Gemma4) | `C:\Modeles_LLM\gemma4-12b-with-proj-ltx-2.5-Q5_K_M.gguf` | ✅ |
| Kokoro-82M q8_0 | `C:\Modeles_LLM\Kokoro-82M-GGUF\kokoro-82m-q8_0.gguf` | ✅ |
| Binaire Kokoro (eSpeak embarqué) | `C:\IA\audio_cpp_master_test\build-357\bin\Release\audiocpp_cli.exe` | ✅ (résolu automatiquement par le workflow) |
| SA3 Small SFX (lit d'ambiance) | `C:\Modeles_LLM\Stable-Audio-3-Small-SFX-GGUF` | ✅ |

Aucune mise à jour en attente côté veille (`output/veille/maj_en_attente.json` vide au
2026-09-17 09:42), rien à traiter avant de produire. Vérification générale optionnelle :
`uv run python main.py --check`.

### 1.5 Pas de génération en cours

Confirmer qu'aucun `sd-cli.exe` / `audiocpp_cli.exe` / `ffmpeg.exe` lourd ne tourne déjà
(`tasklist | grep -iE "sd-cli|audiocpp|ffmpeg"`) — règle « jamais deux moteurs GPU en
parallèle, jamais de maj en plein batch ».

---

## 2. Les commandes, dans l'ordre (à lancer quand le GPU est libre)

### Étape 1 — La voix de robot (courte : ~2-3 min, feedback rapide avant le long rendu)

```bash
cd /c/GIT/generator-assets
uv run python scripts/check_charge_systeme.py

uv run python main.py -w voix_robot "Welcome to the system, human." \
    --robot-voice af_heart --robot-pitch 1.30 --robot-ringmod 120 \
    --robot-tempo 0.65 --robot-gain -4 \
    -o intro_robot
```

- Toutes les valeurs ci-dessus sont les **défauts validés** (essai 17 du 2026-09-17, verdict
  utilisateur « c'est bien ») : Kokoro voix `af_heart`, pitch +30 %, ring modulation 120 Hz
  (le timbre métallique), débit 0.65 (« tranquille »), gain −4 dB. Je les écris explicitement
  pour que la recette reste lisible ; tu peux aussi ne rien passer.
- Le texte est en anglais, comme exigé par les conventions du dépôt (prompts modèles en EN).
- À l'écoute : le `--robot-tempo 0.65` étire la phrase (~3 s pour cette réplique) — parfait
  pour rentrer dans un plan de 5 s. Si tu veux une diction plus rapide : `--robot-tempo 0.85`.

### Étape 2 — Le plan cinématique 5 s (monoplan IA, ~18-20 min)

```bash
uv run python scripts/check_charge_systeme.py

SD_CLI_PATH="C:\SD-6b3edaa\sd-cli.exe" uv run python main.py -w monoplan_ia \
    "Slow cinematic dolly-in through a dark server room, long rows of server racks with blinking status LEDs, cold blue light, thin haze, deep shadows, moody high-tech atmosphere" \
    -i output/scene_intro.png \
    --monoplan-duration 5 \
    --monoplan-frames 65 \
    --zoom-debut 1.10 --zoom-fin 1.32 \
    --ambiance "dark server room ambience, low hum of cooling fans, air conditioning drone, faint electric buzz" \
    --seed 42 \
    -o intro_serveur -d output/intro_chaine
```

Ce que fait chaque option :

| Option | Rôle |
|---|---|
| prompt (anglais) | Le mouvement demandé au modèle : *travelling avant lent* = « slow cinematic dolly-in » — c'est lui qui pilote la caméra |
| `-i output/scene_intro.png` | Image d'amorce (conformée automatiquement en 16:9 832×480) |
| `--monoplan-duration 5` | Durée finale exacte : 5 s (le brut LTX 65 trames @ 24 fps ≈ 2,7 s est ralenti en motion-compensé — le ralenti divise la « respiration » caméra du modèle, c'est le cœur de la recette anti-tremblement) |
| `--monoplan-frames 65` | Défaut = plafond GPU stable (max ~81 au-delà = device lost, §1.17) — je l'écris pour mémoire |
| `--zoom-debut/--zoom-fin` | Rampe de zoom pur 1.10→1.32 par-dessus le ralenti (smootherstep, mathématiquement incapable de vibrer) — elle **renforce** le travelling avant demandé |
| `--ambiance "..."` | Optionnel : lit sonore IA (SA3 Small SFX) de salle serveur muxé à une copie d'écoute. Retire ce flag si tu veux un master muet (le mixage propre avec ducking sera fait côté ai-doc2video de toute façon) |
| `--seed 42` | Reproductibilité A/B (convention du dépôt) |
| `-o intro_serveur -d output/intro_chaine` | Nom + dossier des livrables |
| `SD_CLI_PATH=...` | **Indispensable** : route LTX vers le build 6b3edaa (cf. §1.3) |

**Variante 4K « broadcast YouTube »** (recommandée pour une intro de chaîne : un master
3840×2160 force YouTube à servir son profil premium VP09/AV01 25-45 Mbps, même aux spectateurs
en 1080p) — ajouter simplement `--4k` :

```bash
SD_CLI_PATH="C:\SD-6b3edaa\sd-cli.exe" uv run python main.py -w monoplan_ia \
    "Slow cinematic dolly-in through a dark server room, long rows of server racks with blinking status LEDs, cold blue light, thin haze, deep shadows, moody high-tech atmosphere" \
    -i output/scene_intro.png --monoplan-duration 5 \
    --ambiance "dark server room ambience, low hum of cooling fans, air conditioning drone, faint electric buzz" \
    --seed 42 --4k \
    -o intro_serveur -d output/intro_chaine
```

### Étape 3 (optionnelle) — Aperçu combiné vidéo + voix

Un simple mux d'écoute local (voix en retard de 0,8 s, lit d'ambiance à 30 %). Le mixage
définitif (lits −30 LUFS + ducking sidechain) est le travail d'`ai-doc2video`, pas de ce dépôt :

```bash
/c/ffmpeg/dist/bin/ffmpeg.exe -y \
    -i output/intro_chaine/intro_serveur_5.0s_1080p.mp4 \
    -i output/intro_chaine/intro_serveur_ambiance.wav \
    -i output/voix_robot/intro_robot/intro_robot.wav \
    -filter_complex "[2:a]adelay=800|800[voix];[1:a]volume=0.30[bed];[bed][voix]amix=inputs=2:duration=first:normalize=0[a]" \
    -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k \
    output/intro_chaine/apercu_intro_complete.mp4
```

---

## 3. Fichiers de sortie attendus

### Vidéo (`monoplan_ia`, chemin 1080p) — dans `output/intro_chaine/`

| Fichier | Contenu |
|---|---|
| `intro_serveur_amorce_832x480.png` | Image recadrée 16:9 servant de première trame |
| `intro_serveur_brut.webm` | Plan brut LTX-2.5 (65 trames @ 24 fps) — ⚠️ contient la piste audio brute LTX, à ne pas réutiliser |
| `intro_serveur_5.0s_1080p_ralenti.mp4` | Intermédiaire ralenti motion-compensé (minterpolate mci/aobmc/vsbmc) |
| **`intro_serveur_5.0s_1080p.mp4`** | **Master muet 1920×1080 @ 24 fps** (zoom pur 1.10→1.32 + FidelityFX CAS 0.75) |
| `intro_serveur_ambiance.wav` | Lit sonore SA3 (si `--ambiance` passé) |
| `intro_serveur_5.0s_1080p_avec_ambiance.mp4` | Copie d'écoute sonorisée |

Avec `--4k` en plus : `intro_serveur_brut_4k_ai.mp4` (master UltraSharp 3328×1920),
`intro_serveur_5.0s_4k_ralenti.mp4`, `intro_serveur_5.0s_4k_zoom.mp4` (intermédiaires) et
**`intro_serveur_5.0s_4k.mp4`** = master final 3840×2160 @ 30 fps, h264_amf ~45 Mbps.

*Astuce reprise* : chaque étape écrit un fichier → si une étape échoue, relancer la même
commande reprend là où elle s'était arrêtée ; on peut aussi repartir du brut avec
`--monoplan-source output/intro_chaine/intro_serveur_brut.webm` (saute la génération GPU).

### Voix (`voix_robot`) — dans `output/voix_robot/intro_robot/`

| Fichier | Contenu |
|---|---|
| **`intro_robot.wav`** | **Voix robot finale** — 24 kHz, PCM 16-bit mono, effet applisé |
| `intro_robot.mp3` | Copie d'écoute |
| `intro_robot_brut.wav` | TTS Kokoro sans effet (gardé pour retuner l'effet sans regénérer) |

---

## 4. Durées estimées (RX 6950 XT, machine seule, mesures réelles du dépôt)

| Étape | Durée |
|---|---|
| Voix robot (Kokoro 82M + effet FFmpeg) | **~2-3 min** |
| Génération LTX-2.5 65 trames (8 steps) | ~14-17 min (845 s mesurés sur `generate_video` + chargements ; 17,3 min/plan sur les runs chaînés validés) |
| Ralenti + interpolation 1080p | ~1-2 min |
| Zoom pur + CAS | <1 min |
| Lit d'ambiance SA3 + mux | ~1 min |
| **Total vidéo 1080p** | **~18-20 min** |
| Supplément chemin `--4k` (upscale UltraSharp 65 trames ~9 min + ralenti 3328×1920 ~3 min + zoom ~1,5 min + conform AMF <1 min) | **+~14 min → ~32-35 min** |
| **Total mission (1080p)** | **~20-25 min** ; en 4K : **~35-40 min** |

Si l'image `scene_intro.png` doit d'abord être générée (Flux) : +2-4 min.

---

## 5. Notes pour l'écoute et la suite

- **Ordre proposé** : voix d'abord (2 min, tu valides le ton robot immédiatement), puis le
  rendu vidéo de 18-20 min. Les deux sont séquentiels — jamais deux moteurs GPU en parallèle.
- **Si le rendu ne te plaît pas** : on itère sur la graine (`--seed`) et le prompt (traînée
  « drifting haze », « camera slowly pushing forward »…), pas sur la recette — elle est
  validée. Le défaut connu et accepté de LTX-2.5 : il impose toujours un léger push-in même
  avec un prompt caméra fixe (cfg 1.0) — ici c'est exactement ce qu'on veut (travelling avant).
- **Écueil device-lost** (§1.17) : si une série de crash Vulkan survient, redémarrer la
  machine **avant** d'incriminer la recette (le pilote AMD se dégrade après les device-lost
  en cascade). Et ne jamais monter `--monoplan-frames` au-delà de ~81.
- **Mixage final pour la chaîne** : la conformité broadcast (lits −30 LUFS, ducking
  automatique de l'ambiance sous la voix, master 4K YouTube) est le métier d'`ai-doc2video`
  via le bridge — mon mux d'écoute de l'étape 3 n'est qu'un aperçu.
- Ces deux workflows étant déjà validés et enregistrés, rien à ajouter au README/MEMORY_BANK
  pour cette production ; en revanche je consignerai le verdict d'écoute de l'intro si tu
  veux en faire la carte de visite réutilisée de la chaîne.

**En résumé** : dès que `check_charge_systeme.py` passe au vert et que `output/scene_intro.png`
est en place, ce sont exactement 2 commandes (voix ~2 min, vidéo ~18-20 min, +14 min en 4K),
avec le préfixe `SD_CLI_PATH` obligatoire sur la commande vidéo tant que master-864 casse LTX.
