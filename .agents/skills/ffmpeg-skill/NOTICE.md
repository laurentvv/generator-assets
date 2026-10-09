# NOTICE — provenance and local modifications

- **Upstream**: [kajisho5/ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill)
- **Version vendored**: v2.7.0, commit `cb10cfbc5373a89feef0fda8c4d1c92e035bbe36` (2026-10-09)
- **License**: MIT, unchanged in `LICENSE`. Upstream remains the author of record for everything not listed below.
- **Vendored into**: `generator-assets/.agents/skills/ffmpeg-skill/` on 2026-10-09 (user instruction: "récupère le skill dans un coin et modifie le à ta sauce").

## Vendored subset

`SKILL.md`, `scripts/` (42 tools + `_common/` + `_contract.py` + `_platforms.py`), `references/` (5 files), `templates/`, `LICENSE`.

## Not vendored

`mcp/` (MCP stdio server), `bin/` + `package.json` (npx installer), `tests/`, `evals/`, `demos/`, `examples/`, `docs/` (12 MB rendered docs), `assets/`, `.github/`, `.claude*/`, upstream `AGENTS.md`/`README.md`/`CHANGELOG.md`/`CONTRIBUTING.md`/`SECURITY.md`/`CODE_OF_CONDUCT.md`, `.gitignore`/`.npmignore`.

## Local modifications (keep minimal; re-check on every upstream re-sync)

1. `SKILL.md` — added the "generator-assets local adaptation (read first)" block: Windows 11/Git Bash (`python`, no `python3`), ffmpeg at `C:\ffmpeg` + `C:\ffmpeg\README.md` duty, house GPU gate `scripts/check_charge_systeme.py` before heavy encodes, Apple-only `--hw` flagged dead on the AMD box, −30 LUFS music-bed caution for ai-doc2video, output-location and knowledge-sync house rules, not-vendored list. Reworded the two `python3`/`npx` invocations (workflow step 0, intro paragraph) to `python`; MCP sentence replaced by a not-vendored pointer.
2. `references/gotchas.md` — one `python3` → `python` (doctor invocation).
3. `references/scripts.md` — "MCP server" section replaced by a NOT-vendored note.
4. `package.json` — new minimal manifest (`2.7.0+gas.1`): only feeds `scripts/_contract.py` `skill_version()` so `doctor` reports a truthful version for this copy instead of "unknown".
5. This `NOTICE.md` — new file.

No `.py` script was modified. Upstream is already Windows-hardened (fontconfig fallback via `C:\Windows\Fonts`, concat-demuxer instead of `-pattern_type glob`, crash exit-code handling — see its `references/ci-platform-pitfalls.md`).

## Upstream re-sync recipe

```bash
git clone --depth 1 https://github.com/kajisho5/ffmpeg-skill /tmp/ffmpeg-skill-upstream
# copy scripts/ references/ templates/ LICENSE SKILL.md over this directory,
# then re-apply the 4 modifications above (this file lists them exhaustively)
```
