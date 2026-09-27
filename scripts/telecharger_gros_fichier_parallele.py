#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Parallel chunked download over HTTP Range for large files (HF,
ModelScope…). Works around the single-connection CDN throttling observed on
Hugging Face (drop from 18 MB/s to ~0.6 MB/s after a few GiB): 10 parallel
connections hold ~112 MB/s.

- Reuses any .part prefix left by curl/audiocpp (-C -)
- 128 MB segments written directly at their offset into the final file
- Resumable: JSON state per segment (can be re-run as-is)
- Checks the final size before promoting the file

Usage:
  uv run python scripts/telecharger_gros_fichier_parallele.py <url> <destination> [nb_travailleurs]
Example:
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
    # Some CDNs only give the size via Range
    r = requests.get(url, headers={"Range": "bytes=0-0"}, allow_redirects=True, timeout=30)
    r.raise_for_status()
    plage = r.headers.get("Content-Range", "")
    return int(plage.rsplit("/", 1)[-1])


def preparer_fichier(dest: str, total: int) -> int:
    """Preallocates the file and copies any .part prefix into it. Returns its size."""
    prefix = 0
    part = dest + ".part"
    if os.path.exists(part):
        prefix = os.path.getsize(part)
    if os.path.exists(dest + ".download") and os.path.getsize(dest + ".download") == total:
        return prefix  # already preallocated (resume)

    log(f"📂 Preallocating {total / 2**30:.2f} GiB (.part prefix: {prefix / 2**30:.2f} GiB)...")
    with open(dest + ".download", "wb") as f:
        f.truncate(total)
    if prefix:
        if prefix > total:
            raise RuntimeError(".part prefix larger than the expected file?!")
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
                        raise RuntimeError(f"segment {i_seg} incomplete ({handle.tell()} != {fin + 1})")
                    with verrou_etat:
                        etat["segments_finis"].append(i_seg)
                        tmp = dest + f".etat.{hashlib.md5(url.encode()).hexdigest()[:8]}.json.tmp"
                        with open(tmp, "w", encoding="utf-8") as f_etat:
                            json.dump(etat, f_etat)
                        os.replace(tmp, dest + f".etat.{hashlib.md5(url.encode()).hexdigest()[:8]}.json")
                        compteurs["octets"] += fin + 1 - debut
                        ecoule = max(1e-9, time.time() - compteurs["t0"])
                        fait = compteurs["octets"]
                        log(f"✅ segment {i_seg} ({(fin + 1 - debut) / 2**20:.0f} MB) — "
                            f"{fait / 2**30:.2f} GiB, {fait / ecoule / 2**20:.1f} MB/s avg.")
                    break
                except Exception as e:
                    if essai == 5:
                        log(f"❌ segment {i_seg} abandoned after 5 attempts: {e}")
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
    log(f"   Total size: {total} bytes ({total / 2**30:.2f} GiB)")
    prefix = preparer_fichier(dest, total)

    etat = {"segments_finis": []}
    if os.path.exists(chemin_etat):
        with open(chemin_etat, encoding="utf-8") as f:
            etat = json.load(f)
    finis = set(etat["segments_finis"])
    seg_depart = -(-prefix // TAILLE_SEG)  # ceil: segments overlapping the prefix are redone
    segments = [i for i in range(seg_depart, -(-total // TAILLE_SEG)) if i not in finis]
    log(f"🧩 {len(finis)} segment(s) already done, {len(segments)} to download "
        f"({len(segments) * TAILLE_SEG / 2**30:.2f} GiB max)")

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
            raise RuntimeError(f"{compteurs['echecs']} segment(s) failed — run again to resume.")

    if os.path.getsize(dest + ".download") != total:
        raise RuntimeError(f"Unexpected final size: {os.path.getsize(dest + '.download')} != {total}")
    os.replace(dest + ".download", dest)
    for residu in (dest + ".part", chemin_etat):
        if os.path.exists(residu):
            os.remove(residu)
    log(f"🎉 SUCCESS: {dest} ({os.path.getsize(dest) / 2**30:.2f} GiB)")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    nb = int(sys.argv[3]) if len(sys.argv) > 3 else NB_TRAVAILLEURS_DEFAUT
    telecharger(sys.argv[1], sys.argv[2], nb)


if __name__ == "__main__":
    main()
