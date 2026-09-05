#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Téléchargement parallèle par segments HTTP Range pour gros fichiers (HF,
ModelScope…). Contourne le bridage CDN mono-connexion observé sur Hugging
Face (chute de 18 Mo/s à ~0,6 Mo/s après quelques Gio) : 10 connexions
parallèles tiennent ~112 Mo/s.

- Réutilise un éventuel préfixe .part laissé par curl/audiocpp (-C -)
- Segments de 128 Mo écrits directement à leur offset dans le fichier final
- Reprise : état JSON par segment (relançable tel quel)
- Vérifie la taille finale avant de promouvoir le fichier

Usage :
  uv run python scripts/telecharger_gros_fichier_parallele.py <url> <destination> [nb_travailleurs]
Exemple :
  uv run python scripts/telecharger_gros_fichier_parallele.py \
    "https://modelscope.cn/models/HereIsMark/audio.cpp-gguf/resolve/master/ACE-Step1.5-GGUF/xl-turbo/ace-step-1.5-xl-turbo-bf16.gguf" \
    "C:\\Modeles_LLM\\ACE-Step1.5-GGUF\\xl-turbo\\ace-step-1.5-xl-turbo-bf16.gguf"
"""

import hashlib
import json
import os
import queue
import sys
import threading
import time

import requests

for f in (sys.stdout, sys.stderr):
    if hasattr(f, "reconfigure"):
        f.reconfigure(encoding="utf-8", errors="replace")

TAILLE_SEG = 128 * 1024 * 1024
NB_TRAVAILLEURS_DEFAUT = 10

verrou_imp = threading.Lock()


def log(msg: str):
    with verrou_imp:
        print(msg, flush=True)


def taille_totale(url: str) -> int:
    r = requests.head(url, allow_redirects=True, timeout=30)
    r.raise_for_status()
    taille = r.headers.get("Content-Length")
    if taille:
        return int(taille)
    # Certains CDN ne donnent la taille que via Range
    r = requests.get(url, headers={"Range": "bytes=0-0"}, allow_redirects=True, timeout=30)
    r.raise_for_status()
    plage = r.headers.get("Content-Range", "")
    return int(plage.rsplit("/", 1)[-1])


def preparer_fichier(dest: str, total: int) -> int:
    """Préalloue le fichier et y copie l'éventuel préfixe .part. Retourne sa taille."""
    prefix = 0
    part = dest + ".part"
    if os.path.exists(part):
        prefix = os.path.getsize(part)
    if os.path.exists(dest + ".download") and os.path.getsize(dest + ".download") == total:
        return prefix  # déjà préalloué (reprise)

    log(f"📂 Préallocation de {total / 2**30:.2f} Gio (préfixe .part : {prefix / 2**30:.2f} Gio)...")
    with open(dest + ".download", "wb") as f:
        f.truncate(total)
    if prefix:
        if prefix > total:
            raise RuntimeError("Préfixe .part plus grand que le fichier attendu ?!")
        with open(part, "rb") as src, open(dest + ".download", "r+b") as dst:
            reste = prefix
            while reste > 0:
                bloc = src.read(min(8 * 1024 * 1024, reste))
                if not bloc:
                    break
                dst.write(bloc)
                reste -= len(bloc)
    return prefix


def travailleur(num: int, url: str, file_segments: "queue.Queue", total: int, etat: dict,
                verrou_etat: threading.Lock, compteurs: dict, dest: str):
    session = requests.Session()
    handle = open(dest + ".download", "r+b")
    try:
        while True:
            try:
                i_seg = file_segments.get_nowait()
            except queue.Empty:
                return
            debut = i_seg * TAILLE_SEG
            fin = min(debut + TAILLE_SEG, total) - 1
            for essai in range(1, 6):
                try:
                    rep = session.get(url, headers={"Range": f"bytes={debut}-{fin}"},
                                      stream=True, timeout=(15, 90))
                    if rep.status_code not in (200, 206):
                        raise RuntimeError(f"HTTP {rep.status_code}")
                    handle.seek(debut)
                    for bloc in rep.iter_content(chunk_size=1024 * 1024):
                        handle.write(bloc)
                    if handle.tell() != fin + 1:
                        raise RuntimeError(f"segment {i_seg} incomplet ({handle.tell()} != {fin + 1})")
                    with verrou_etat:
                        etat["segments_finis"].append(i_seg)
                        tmp = dest + f".etat.{hashlib.md5(url.encode()).hexdigest()[:8]}.json.tmp"
                        with open(tmp, "w", encoding="utf-8") as f_etat:
                            json.dump(etat, f_etat)
                        os.replace(tmp, dest + f".etat.{hashlib.md5(url.encode()).hexdigest()[:8]}.json")
                        compteurs["octets"] += fin + 1 - debut
                        ecoule = max(1e-9, time.time() - compteurs["t0"])
                        fait = compteurs["octets"]
                        log(f"✅ segment {i_seg} ({(fin + 1 - debut) / 2**20:.0f} Mo) — "
                            f"{fait / 2**30:.2f} Gio, {fait / ecoule / 2**20:.1f} Mo/s moy.")
                    break
                except Exception as e:
                    if essai == 5:
                        log(f"❌ segment {i_seg} abandonné après 5 essais : {e}")
                        with verrou_etat:
                            compteurs["echecs"] += 1
                    else:
                        time.sleep(2 * essai)
    finally:
        handle.close()


def telecharger(url: str, dest: str, nb_travailleurs: int = NB_TRAVAILLEURS_DEFAUT):
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    chemin_etat = dest + f".etat.{hashlib.md5(url.encode()).hexdigest()[:8]}.json"

    total = taille_totale(url)
    log(f"🌐 {url}")
    log(f"   Taille totale : {total} octets ({total / 2**30:.2f} Gio)")
    prefix = preparer_fichier(dest, total)

    etat = {"segments_finis": []}
    if os.path.exists(chemin_etat):
        with open(chemin_etat, encoding="utf-8") as f:
            etat = json.load(f)
    finis = set(etat["segments_finis"])
    seg_depart = -(-prefix // TAILLE_SEG)  # ceil : segments chevauchant le préfixe refaits
    segments = [i for i in range(seg_depart, -(-total // TAILLE_SEG)) if i not in finis]
    log(f"🧩 {len(finis)} segment(s) déjà fini(s), {len(segments)} à télécharger "
        f"({len(segments) * TAILLE_SEG / 2**30:.2f} Gio max)")

    if segments:
        file_segments: "queue.Queue" = queue.Queue()
        for s in segments:
            file_segments.put(s)
        compteurs = {"octets": 0, "echecs": 0, "t0": time.time()}
        verrou_etat = threading.Lock()
        fils = [threading.Thread(target=travailleur,
                                 args=(n, url, file_segments, total, etat, verrou_etat, compteurs, dest),
                                 daemon=True)
                for n in range(nb_travailleurs)]
        for fil in fils:
            fil.start()
        for fil in fils:
            fil.join()
        if compteurs["echecs"]:
            raise RuntimeError(f"{compteurs['echecs']} segment(s) en échec — relancez pour reprendre.")

    if os.path.getsize(dest + ".download") != total:
        raise RuntimeError(f"Taille finale inattendue : {os.path.getsize(dest + '.download')} != {total}")
    os.replace(dest + ".download", dest)
    for residu in (dest + ".part", chemin_etat):
        if os.path.exists(residu):
            os.remove(residu)
    log(f"🎉 SUCCÈS : {dest} ({os.path.getsize(dest) / 2**30:.2f} Gio)")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    nb = int(sys.argv[3]) if len(sys.argv) > 3 else NB_TRAVAILLEURS_DEFAUT
    telecharger(sys.argv[1], sys.argv[2], nb)


if __name__ == "__main__":
    main()
