# NOTICE — provenance and local modifications

- **Upstream**: [kajisho5/ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill)
- **Version vendored**: v4.2.2, commit `62f99aadcbc869b393fb1a631c18272b1f68bc1a` (2026-11-21)
- **License**: MIT, unchanged in `LICENSE`. Upstream remains the author of record for everything not listed below.
- **Vendored**: into `generator-assets/.agents/skills/ffmpeg-skill/` on 2026-10-09, at the user's request ("grab the skill and tweak it to your liking"), then promoted to the agents-kit fleet copy (see Fleet distribution below).
- **Re-synced**: v2.7.0 → v4.2.2 on 2026-11-21 (303 upstream commits, 300 files changed per the GitHub compare API `cb10cfbc...62f99aa`; all 45 scripts touched, +5 references, +`_smartcut.py`/`_review.py`/`_review.html`, +`_common/alpha.py`; upstream 3.0.0 requires FFmpeg ≥ 6.1 and Python ≥ 3.10 — machine runs ffmpeg 9.1 / Python 3.13, doctor re-measured 2026-11-21).

## Vendored subset

`SKILL.md`, `scripts/` (42 tools + `_common/` + `_contract.py` + `_platforms.py` + `_smartcut.py` (cut.py dependency) + `_review.py`/`_review.html` (standalone review page) + `_ass_overlay.py`), `references/` (10 files), `templates/` (10 files), `LICENSE`.

## Not vendored

`mcp/` (MCP stdio server), `bin/` + `package.json` (npx installer), `tests/`, `evals/`, `demos/`, `examples/`, `docs/` (12 MB rendered docs), `assets/`, `.github/`, `.claude*/`, upstream `AGENTS.md`/`README.md`/`CHANGELOG.md`/`CONTRIBUTING.md`/`SECURITY.md`/`CODE_OF_CONDUCT.md`, `.gitignore`/`.npmignore`.

## Local modifications (keep minimal; re-check on every upstream re-sync)

1. `SKILL.md` — added the "Fleet adaptation (agents-kit distribution) — read first" block: Windows 11/Git Bash (`python`, no `python3`), ffmpeg at `C:\ffmpeg` + `C:\ffmpeg\README.md` duty, measured machine gaps (re-measured by `doctor` on every re-sync; 2026-11-21: no vidstab filters, 'DejaVu Sans' missing + emoji monochrome, CJK/RTL/Indic render, no local parakeet, CPU x264/x265 only — `--hw` is Apple-only), a rule that repo-specific overrides (heavy-generation gates, per-project loudness specs, output locations) live in the HOST repo's AGENTS.md §7, knowledge-sync duty, not-vendored list. Reworded the `python3` invocations (quick start, review-page line) to `python`; Quick-start MCP sentence replaced by a not-vendored pointer. (Fleet-generalized 2026-10-09: replaced the original generator-assets-pinned adaptation block; its specifics remain recorded in generator-assets AGENTS.md §7.)
2. `references/workflow.md` — one `python3` → `python` (doctor invocation, workflow step 0).
3. `references/flags.md` — one `python3` → `python` (intro); the trailing MCP sentence replaced by a not-vendored pointer.
4. `references/gotchas.md` — one `python3` → `python` (doctor invocation, fonts section).
5. `references/scripts.md` — "MCP server" section replaced by a NOT-vendored note.
6. `package.json` — minimal manifest (`4.2.2+gas.1`): only feeds `scripts/_contract.py` `skill_version()` so `doctor` reports a truthful version for this copy instead of "unknown".
7. This `NOTICE.md` — new file.

No `.py` script was modified. Upstream is already Windows-hardened (fontconfig fallback via `C:\Windows\Fonts`, concat-demuxer instead of `-pattern_type glob`, crash exit-code handling — see its `references/ci-platform-pitfalls.md`).

## Fleet distribution (agents-kit)

- Promoted to the agents-kit fleet on 2026-10-09 (`skills author`, source "(authored)"): the kit copy in `skills/ffmpeg-skill/` is the single distribution source, deployed to the repositories' `.agents/skills/ffmpeg-skill/` as byte-identical copies under a fingerprint lock. "(authored)" means no upstream wiring: `skills update` never re-imports upstream over this fork — the re-sync recipe below stays a manual, reviewed step.
- Distributed fleet-wide via agents-kit 2026-10-09: installed in generator-assets, ai-doc2video, video-analys-ia.
- This NOTICE.md is the fork's provenance marker: the kit's repository guard exempts skill folders carrying it from the English-only scan, because the vendored upstream files are external content (their multilingual caption/filler data included) distributed byte-identical.

## Upstream re-sync recipe

```bash
git clone --depth 1 --branch v<version> https://github.com/kajisho5/ffmpeg-skill /tmp/ffmpeg-skill-upstream
# copy scripts/ references/ templates/ LICENSE SKILL.md over this directory,
# then re-apply the modifications listed above (this file lists them exhaustively);
# normalize every copied file to LF (fleet .gitattributes: skills/** text eol=lf)
```
