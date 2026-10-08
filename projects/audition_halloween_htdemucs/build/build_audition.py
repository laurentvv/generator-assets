#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build the local audition page for the audio verdicts still pending
(Halloween 2026 pack + HTDemucs 6-stems separation validation).

Run from the repository root:

    PYTHONPATH=. uv run python projects/audition_halloween_htdemucs/build/build_audition.py

Writes projects/audition_halloween_htdemucs/output/audition/ :
  index.html   self-contained page (dark theme, light fallback), nothing uploaded
  <id>.mp3     one re-encoded candidate per item, sitting next to the page
  ids.json     machine-readable manifest (id -> section/title/note/source)

Every candidate is re-encoded with ffmpeg (config.ffmpeg()) to MP3 128k
44.1 kHz stereo with loudnorm I=-23:TP=-2:LRA=11 so TONES are compared, not
levels — except master excerpts (norm=False), which keep the master loudness.
After the build, open the page in the DEFAULT browser (PowerShell:
Start-Process <path to index.html>).
"""

import html
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from core import config

PROJECT = "audition_halloween_htdemucs"
STATE_KEY = PROJECT  # localStorage key, unique to this project
OUT_DIR = Path("projects") / PROJECT / "output" / "audition"

# Read-only sources. Pack default overridable via env (no hardcoded machine
# paths outside config/env, AGENTS.md §1).
PACK = Path(
    os.getenv("AI_DOC2VIDEO_ASSETS_DIR", r"C:\GIT\ai-doc2video\assets_ia")
) / "halloween_2026"
HTDEMUCS = config.RACINE_DEPOT / "output" / "test_htdemucs6"

SECTIONS: dict = {}  # section heading -> [item, ...] (insertion-ordered)
ITEMS: list = []


def add(section, id, title, note, file, start=None, duration=None, norm=True):
    """Declare one audition item. start/duration in seconds (excerpt);
    norm=False keeps the source loudness (master excerpts)."""
    item = {
        "id": id,
        "section": section,
        "title": title,
        "note": note,
        "source": str(Path(file)),
        "start": start,
        "duration": duration,
        "norm": norm,
    }
    SECTIONS.setdefault(section, []).append(item)
    ITEMS.append(item)


# --------------------------------------------------------------- declarations
# A. Song delivered with the Halloween pack — pick ONE, it goes to the video.
add("A. Halloween song - pick ONE", "halloween_song",
    "halloween_night (EN, 60 s)",
    "ACE-Step 1.5 xl-turbo, EN lyrics, 12 lines (seed default). Verdict: "
    "Halloween register + intelligible lyrics -> pack + channel video.",
    PACK / "halloween_night.wav")

# B. The 8 SFX of the pack (SA3 small SFX, peak-normalized at generation).
for _sfx, _dur, _hint in [
    ("chains", "3 s", "chain rattle"),
    ("door_creak", "4 s", "creaking door"),
    ("evil_laugh", "3 s", "laugh"),
    ("ghost_whisper", "4 s", "whisper"),
    ("heartbeat", "3 s", "heartbeat"),
    ("knock", "3 s", "knocking"),
    ("thunder", "3 s", "thunder roll"),
    ("wolf_howl", "4 s", "distant howl"),
]:
    add("B. SFX pack (SA3 small SFX)", f"sfx_{_sfx}", _sfx,
        f"SA3 small SFX ({_dur}, {_hint}). Verdict: usable as-is in a video?",
        PACK / f"{_sfx}.wav")

# C. The 2 loopable ambiences of the pack.
add("C. Ambience loops (8 s, loopable)", "amb_haunted_mansion", "haunted_mansion",
    "wind + distant thunder + creaks + drone. Verdict: loop seam clean?",
    PACK / "haunted_mansion.wav")
add("C. Ambience loops (8 s, loopable)", "amb_graveyard_night", "graveyard_night",
    "crickets + owl + wind. Verdict: loop seam clean?",
    PACK / "graveyard_night.wav")

# D. HTDemucs 6-stems validation (10-05 test): source first (true level),
# then each stem loudnorm-ed — judge coloration/artifacts against the source.
add("D. HTDemucs 6-stems - separation vs source", "ref_source_30s",
    "Source excerpt (master level, 30 s)",
    "Input mix of the 10-05 test (the_ninth_son_en.wav 40-70 s). NOT "
    "normalized - reference level for the stems below.",
    HTDEMUCS / "input_30s.wav", start=0, duration=30, norm=False)
for _stem in ["bass", "drums", "guitar", "other", "piano", "vocals"]:
    add("D. HTDemucs 6-stems - separation vs source", f"stem_{_stem}", f"Stem: {_stem}",
        "HTDemucs 6-stems q8_0 Vulkan (RTF 0.08). Verdict: artifacts? "
        "coloration vs the source excerpt?",
        HTDEMUCS / "stems" / f"{_stem}.wav")


# --------------------------------------------------------------------- build
def encode(item: dict, dst: Path) -> None:
    """Re-encode one candidate: MP3 128k 44.1 kHz stereo, loudnorm by default
    (master excerpts keep their loudness with norm=False)."""
    cmd = [config.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error"]
    if item["start"] is not None:
        cmd += ["-ss", str(item["start"])]
    if item["duration"] is not None:
        cmd += ["-t", str(item["duration"])]
    cmd += ["-i", item["source"], "-ar", "44100", "-ac", "2",
            "-c:a", "libmp3lame", "-b:a", "128k"]
    if item["norm"]:
        cmd += ["-af", "loudnorm=I=-23:TP=-2:LRA=11"]
    cmd.append(str(dst))
    subprocess.run(cmd, check=True)


def _item_html(item: dict) -> str:
    """One .item block — structure copied from docs/examples/audition_example.html."""
    title = html.escape(item["title"])
    note = html.escape(item["note"])
    item_id = item["id"]
    return (
        f'<div class="item" data-id="{item_id}">'
        f'<div class="t"><b>{title}</b><br><small>{note}</small></div>'
        f'<audio controls preload="none" src="{item_id}.mp3"></audio>'
        f'<div class="b"><button data-v="keep">keep</button>'
        f'<button data-v="reject">reject</button>'
        f'<input placeholder="note" aria-label="note for {item_id}"></div></div>'
    )


# Structure and JavaScript copied from docs/examples/audition_example.html.
# Plain string + .replace() tokens: NEVER an f-string around JS (braces would
# need doubling and join('\n') would become a real newline — the buttons die).
PAGE_TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#0b0f19;--fg:#e6edf7;--mut:#8b97ad;--card:#131a2a;--ok:#2dd4bf;--ko:#ff5c7a}
@media (prefers-color-scheme: light){:root{--bg:#f5f7fb;--fg:#10182b;--mut:#55627a;--card:#fff}}
body{background:var(--bg);color:var(--fg);font:16px system-ui,sans-serif;margin:0;padding:16px;max-width:980px;margin:auto}
h1{font-size:22px}h2{font-size:17px;margin:28px 0 8px;color:var(--ok)}
.item{background:var(--card);border-radius:10px;padding:10px 12px;margin:8px 0;display:grid;grid-template-columns:1fr;gap:6px}
.item.keep{outline:2px solid var(--ok)}.item.reject{outline:2px solid var(--ko)}
audio{width:100%}small{color:var(--mut)}
button{margin-right:6px;padding:6px 14px;border-radius:8px;border:1px solid var(--mut);background:transparent;color:var(--fg);cursor:pointer}
input{background:transparent;border:1px solid var(--mut);border-radius:8px;color:var(--fg);padding:6px 8px;width:50%}
#out{width:100%;height:140px;background:var(--card);color:var(--fg);border:1px solid var(--mut);border-radius:8px;padding:8px}
</style></head><body>
<h1>__TITLE__</h1>
<p>Listen, press keep or reject, add a note, then press <b>Copy verdicts</b> and paste the text back in the chat. Nothing leaves this machine.</p>

__BODY__
<h2>Your verdicts</h2><textarea id="out" readonly placeholder="verdicts appear here"></textarea><p><button id="copy">Copy verdicts</button></p>
<script>
const KEY='__KEY__';            // one key per project
const st={};try{Object.assign(st,JSON.parse(localStorage.getItem(KEY)||'{}'))}catch(e){}
function render(){
  const lines=[];
  document.querySelectorAll('.item').forEach(el=>{
    const id=el.dataset.id,v=st[id]||{};
    el.classList.toggle('keep',v.v==='keep');el.classList.toggle('reject',v.v==='reject');
    el.querySelector('input').value=v.n||'';
    if(v.v||v.n)lines.push(id+': '+(v.v||'-')+(v.n?' | '+v.n:''));
  });
  document.getElementById('out').value=lines.join(String.fromCharCode(10));   // never '\\n' written through a Python f-string
  try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}
}
document.querySelectorAll('.item').forEach(el=>{
  const id=el.dataset.id;
  el.querySelectorAll('button').forEach(b=>b.onclick=()=>{st[id]=Object.assign(st[id]||{},{v:b.dataset.v});render()});
  el.querySelector('input').oninput=e=>{st[id]=Object.assign(st[id]||{},{n:e.target.value});render()};
});
document.getElementById('copy').onclick=()=>{
  const t=document.getElementById('out'),b=document.getElementById('copy');
  const done=()=>{b.textContent='Copied !';setTimeout(()=>{b.textContent='Copy verdicts'},1200)};
  const fallback=()=>{t.select();document.execCommand('copy');done()};
  if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(t.value).then(done).catch(fallback)}else{fallback()}
};
render();
</script></body></html>
"""


def page_html() -> str:
    body = []
    for section, items in SECTIONS.items():
        body.append(f"<h2>{html.escape(section)}</h2>")
        body.extend(_item_html(it) for it in items)
    return (PAGE_TEMPLATE
            .replace("__TITLE__", "Audition - Halloween pack + HTDemucs stems")
            .replace("__KEY__", STATE_KEY)
            .replace("__BODY__", "\n".join(body)))


def main() -> None:
    missing = [it["source"] for it in ITEMS if not Path(it["source"]).is_file()]
    if missing:
        sys.exit("Source file(s) missing: " + "; ".join(missing))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for item in ITEMS:
        dst = OUT_DIR / f"{item['id']}.mp3"
        encode(item, dst)
        print(f"  encoded {dst.name}")
    (OUT_DIR / "index.html").write_text(page_html(), encoding="utf-8")
    manifest = {
        "project": PROJECT,
        "state_key": STATE_KEY,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "ffmpeg": config.ffmpeg(),
        "verdict_line_format": "id: keep|reject | note",
        "items": ITEMS,
    }
    (OUT_DIR / "ids.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: {len(ITEMS)} items -> {OUT_DIR / 'index.html'}")


if __name__ == "__main__":
    main()
