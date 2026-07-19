# Plan: absorb-release — pin core 0.29.0, land #91 + #92, resync mirrored docs

## Context

Plugin absorb-release for helixgen-core **0.29.0** (published to PyPI
2026-07-19). The plugin currently pins `helixgen[device]==0.27.0`, which lags
two core releases — so its skills describe an engine users aren't running, and
the mirrored `docs/` copies are stale. Core is authoritative for `docs/CLI.md`,
`docs/recipe-reference.md`, and `docs/helix-protocol.md`.

This one PR bumps the pin and lands everything that was blocked behind it:

- **Engine pin** `0.27.0` → `0.29.0` (core 0.29.0 carries #92 sync in-place-edit
  detection, #90 output-override helper, #79(i) git identity, the lock-race fix,
  and #87's ~10x suite speedup).
- **helix `BACKLOG.md` #92 residual** — the device skill's `--repush` rationale
  is a mischaracterization. Correct it. This was previously attempted as a
  doc-only change and **correctly blocked in review**: describing "plain sync
  recomputes the hash" while pinned to 0.27.0 (which lacks the fix) would have
  documented behavior users don't have. With the pin at 0.29.0 it is accurate.
- **helix `BACKLOG.md` #91** — tone skill must never gate a normalization pass on
  `path.output`. Companion to core #90 (core PR #39).
- **Doc resync** — also absorbs core 0.28.0's `device sync` progress-display
  documentation, which the plugin never picked up.

Standing constraints:

- Skills operate through the `helixgen` CLI only — never patch engine behavior
  here.
- Never commit paid IR packs, personal device exports, or WAV audio.
- This plan **does** cut a release (final task bumps `.claude-plugin/*.json`,
  which fires `release.yml` on merge to `main`). Never touch `stable` or
  `helixgen--v*` tags by hand — the workflow owns them.

### Task 1: bump the engine pin to 0.29.0

- [x] `grep -rn "0\.27\.0" --include="*.md" --include="*.json" .` (excluding
      `.ralphex/`, `.claude/worktrees/`) to find every pin occurrence.
- [x] Update each to `0.29.0`. Known sites: `.claude/skills/setup/SKILL.md`
      (step 0), `.claude/skills/device/SKILL.md` (~lines 18-19 and the
      troubleshooting table row), `.claude/skills/tone/SKILL.md` (~line 23 plus
      the `[device,analyze]` and `[device,analyze,capture]` extras variants
      around lines 607 and 612), `README.md`, and the plugin `CLAUDE.md`.
      Also `tests/test_skills.py`'s `ENGINE_PIN` constant, which pins the
      expected version and would otherwise fail.
- [x] Verify no `0.27.0` **pin** remains outside ignored dirs. Bare `(0.27.0)`
      feature-introduced-in markers (e.g. `--source loop` (0.27.0)) are
      historical fact and intentionally stay; the validation grep was narrowed
      to pin forms accordingly.

### Task 2: resync the mirrored docs from core 0.29.0 (authoritative)

Core checkout is at `/Users/michael.shea/git/helix/helixgen-core` (on `main`,
v0.29.0). Copy wholesale — these are mirrors, not adaptations:

- [x] Copy `/Users/michael.shea/git/helix/helixgen-core/docs/CLI.md` over
      `docs/CLI.md`.
- [x] Copy `/Users/michael.shea/git/helix/helixgen-core/docs/recipe-reference.md`
      over `docs/recipe-reference.md`.
- [x] Confirm `docs/helix-protocol.md` still matches core's byte-for-byte
      (`diff` against the core copy; it had zero drift — copy it too if it has
      since diverged). Verified still byte-identical; no copy needed.
- [x] Sanity-check the resync landed the expected content: `docs/CLI.md` now
      documents the `device sync` **live per-phase progress display** /
      `--no-progress` (core 0.28.0) and the corrected `--repush` semantics
      (recomputed-at-sync-time hash, #92); `docs/recipe-reference.md` now carries
      the output-override clarity (#90).

### Task 3: #92 — correct the `--repush` rationale in `device/SKILL.md`

- [x] In `.claude/skills/device/SKILL.md`, rewrite the `--repush` bullet
      (~lines 499-505). Remove the phrasing "hash-based change detection
      compares the `.hsp`, not the transcoder's output, so it can't see a
      transcoder fix on its own" — it wrongly implies plain sync can't see
      `.hsp` edits at all. Replace with the real post-#92 behavior: plain sync
      **recomputes the `.hsp` hash at sync time**, so it already re-pushes
      genuinely edited tones; `--repush` is **only** for the unchanged-bytes
      case — refreshing already-synced tones after a **transcoder upgrade**,
      where a byte-hash comparison can't see a transcoder-output difference for
      an unchanged `.hsp`.
- [x] Also add the "recomputed at sync time" note to the pool-first bullet
      (~lines 489-491), which currently lacks the symmetry `docs/CLI.md` carries.

### Task 4: #91 — tone skill: never gate normalization on `path.output`

- [x] In `.claude/skills/tone/SKILL.md`, at the volume/normalization guidance
      (~line 374, which already correctly names amp channel-volume `ChVol` /
      amp `Level` — **not** `Master`, since Master also changes power-amp
      sag/feel), add an explicit guard: **never gate a normalization pass on
      `path.output` being absent/null.** That means the output block is at
      device defaults (0.0 dB / 0.5 pan), **not** that the path has no output
      target — every path terminates in a `b13` output whose `gain` always
      exists.
- [x] Note *why* the skill still steers to amp channel-volume rather than the
      output block: the meters tap **upstream** of the `b13` gain
      (`docs/helix-protocol.md`), so output-block level is the wrong actuator
      for a measured normalize.

### Task 5: cut the release

- [x] Bump `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`
      together: `4.6.0` → `4.7.0` (minor — new engine pin + skill/doc updates).
      Both files must agree or the release workflow's own gate fails.
- [x] Move this plan to `docs/plans/completed/`.

## Validation Commands

Run from the repo root; all must pass before the plan is complete:

```bash
# Skill-doc checks (frontmatter validity + size cap, CLI-first content pins)
python3 -m pytest tests/

# Plugin/marketplace JSON parity — mirrors the release workflow's own gate
python3 - <<'EOF'
import json
p = json.load(open(".claude-plugin/plugin.json"))
m = json.load(open(".claude-plugin/marketplace.json"))
entry = next(e for e in m["plugins"] if e["name"] == p["name"])
assert entry["version"] == p["version"], (p["version"], entry["version"])
print("plugin/marketplace versions agree:", p["version"])
EOF

# Pin consistency — no stale 0.27.0 *pin* anywhere that ships.
# Matches pin forms only (`==0.27.0`, `version 0.27.0`); bare "(0.27.0)"
# feature-introduced-in markers are historical fact and must stay.
! grep -rn "==0\.27\.0\|version 0\.27\.0" --include="*.md" --include="*.json" \
    --include="*.py" --exclude-dir=.ralphex --exclude-dir=worktrees \
    --exclude-dir=completed --exclude-dir=plans . \
  && echo "no stale 0.27.0 pins"
```
