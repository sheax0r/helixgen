# helixgen (Claude Code plugin)

Claude Code plugin + single-plugin marketplace for helixgen: generate Line 6 Helix Stadium `.hsp` presets from natural-language tone requests, control Stadium over LAN. Repo carries **only plugin surfaces** — engine lives in [`helixgen-core`](https://github.com/sheax0r/helixgen-core).

**Repo family (all under `sheax0r`):** [`helixgen-core`](https://github.com/sheax0r/helixgen-core) = Python package `helixgen` — libs, CLI (**only** engine surface since core 0.20.0 — MCP server removed), tests, authoritative docs + backlog; **this repo** = plugin/marketplace (skills, bundled block-library data); [`helixgen-tui`](https://github.com/sheax0r/helixgen-tui) = terminal UI. Engine changes always land in helixgen-core — never patch engine behavior from here.

## How the plugin loads the engine (CLI-first, since 4.0.0)

No MCP server, no `.mcp.json`. Skills drive `helixgen` **CLI**, provisioned as isolated tool:

```bash
uv tool install 'helixgen[device]==0.98.0'
```

`setup` skill step 0 performs/verifies this (`helixgen --version`), handles stale-shadow failure mode (broken `helixgen` earlier on PATH — invoke `"$(NO_COLOR=1 uv tool dir --bin)/helixgen"` — `NO_COLOR=1` matters: with `FORCE_COLOR` set, uv emits ANSI codes inside substitution — or fall back to plain `~/.local/bin/helixgen` path, never touch ambient Python), upgrades with `uv tool install --force 'helixgen[device]==X.Y.Z'`.
CLI self-documenting: skills start capability discovery at `helixgen --help` / `helixgen device --help`; each verb's `--help` = its behavioral contract.

**Engine version pin lives in skills** (`setup` step 0; echoed in `tone`/`device` and README). Bump engine = update pinned version there + cut plugin release.

**Block library:** engine reads `$HELIXGEN_LIBRARY`. Skills resolve per session — already-set env var wins, then populated `~/.helixgen/library/`, else plugin's bundled library at `${CLAUDE_PLUGIN_ROOT}/data/library` — and prefix **every** `helixgen` invocation with it (shell exports don't persist across agent Bash calls). `${CLAUDE_PLUGIN_ROOT}` expanded by Claude Code anywhere in plugin skill content, so installed skills carry absolute path; skills also document dev-checkout fallback (walk up from skill directory to ancestor containing `.claude-plugin/plugin.json`) and sanity check (empty `list-blocks` result exits 0 — silent sign env didn't reach CLI).

## Project layout

- `skills/` — three skills (plugin ROOT, which is where the loader scans; `.claude/skills/` is NOT scanned inside an installed plugin): `setup` (CLI provisioning + device/prefs onboarding), `tone` (author `.hsp` from tone request), `device` (copy authored tones onto hardware; back up / restore the device)
- `.claude-plugin/` — `plugin.json` + `marketplace.json`; version bump here on `main` triggers release (see Releasing)
- `data/library/` — bundled block library (`HELIXGEN_LIBRARY`)
- `docs/` — runtime references skills consult: `CLI.md`, `recipe-reference.md`, `helix-protocol.md` (synced FROM helixgen-core — core authoritative), plus `demo.gif`
- `docs/superpowers/specs/` — **design specs** (`YYYY-MM-DD-<topic>-design.md`), written before implementation and kept as the record of *why*. Distinct from `docs/plans/`, which holds ralphex implementation plan files. Spec assets (calibration audio, fixtures) live under `docs/superpowers/specs/assets/`.
- `tests/` — skill-doc frontmatter + content checks (`python3 -m pytest`, needs only pytest)

**The plugin backlog is a flat beads export — there is no served beads DB in this repo.** `bd ready` / `bd create` / `bd where` do **not** resolve here (beads proper lives in **helixgen-core**, at `helixgen-core/.beads`; engine work is tracked there). Don't reach for `bd` in this repo. Read and append the plugin backlog at [`docs/parity/stadium-parity-beads.jsonl`](docs/parity/stadium-parity-beads.jsonl) (its human-readable map is [`docs/parity/stadium-app-parity.md`](docs/parity/stadium-app-parity.md)); track plugin-only work there, not in TodoWrite or markdown TODO lists. `BACKLOG.md` in the coordination workspace remains the historical cross-repo backlog (entries #57–#59 cover the repo split).

## Agent autonomy — do these WITHOUT asking

Standing owner authorization for agents developing in this repo. Asking permission for any of the below is the wrong move — do it, then report what you did. Applies to development sessions only; the shipped `skills/*` keep their own ask-first rules, which protect end users' devices.

- **Wait for CI, then merge.** Opening a PR is not the end of the task: stay on it until CI finishes (`gh pr checks <n> --watch`), fix and re-push if it fails, and never merge red or still-running CI. For a PR this session opened: CI passing + adversarial-review findings fixed + mergeable → merge, in the same session, without checking in — subject only to the release order under Development workflow (a pin-bump PR waits for the engine version to be on PyPI). In this repo a merge that carries a version bump *is* a release (the workflow ships it); that is intended and needs no extra sign-off.
- **Validate on hardware.** The owner's Stadium XL is on the LAN for this purpose: run `helixgen device …` verbs (copy, live, measure, snapshot, etc.) against it whenever validation is useful. Leave it as you found it — work in a scratch setlist/preset where possible, pull back or back up anything you will overwrite, and remove test content afterwards. If the device is unreachable or validation needs someone to play the guitar, don't block: ship and note it as owed.
- **Skip hardware validation when tests are sufficient.** If the change is covered by tests (unit, round-trip/corpus, published-wheel check) and does not introduce new on-the-wire or on-device behavior, ship without HW validation and say so in the PR. Don't ask whether to validate — decide. New protocol/transcoder/device-write behavior is what warrants a HW pass.
- **Drive the Helix Stadium app UI.** Use the Stadium desktop app (computer-use tools) freely to debug, investigate, discover protocol behavior, capture traffic, or cross-check what helixgen wrote — no need to ask first.

**CLAUDE.md is the source of truth — not agent memory.** Auto-memory has proven unreliable here (stale, contradictory, session-specific). Do not save durable guidance, preferences, or project rules to memory; put them in this file (or the relevant repo's CLAUDE.md) via PR. Where a recalled memory conflicts with CLAUDE.md, the code, or git/PR state, the memory is wrong — verify against the repo and `gh` instead of trusting it.

**Push release tags without asking.** The core `vX.Y.Z` tag that publishes to PyPI is yours to push — autonomously, no sign-off, as the last step of landing a release (see Development workflow + Releasing). Standing owner authorization; don't ask, and don't wait for the owner to push it.

Still ask: anything destructive to the owner's real content that can't be restored (device restore/factory reset, mirror-sync onto a setlist they use, deleting presets/IRs you did not create). Leave the plugin's `stable` branch and `helixgen--v*` tags to the release workflow — not a trust gate: CI creates them idempotently from a version bump, so a hand-pushed one just collides (see Releasing).

## Development workflow

- **Worktrees, branched from fresh `origin/main`.** All non-trivial work in git worktree whose branch starts from freshly-fetched `origin/main` — never commit directly on local `main`. Fetch again before picking release version number.
- **Adversarial review before shipping.** Before merging PR, dispatch at least one independent review subagent prompted to *break* change. Confirmed findings fixed or explicitly deferred to backlog.
- **Watch CI and merge green PRs — don't wait to be asked** (see Agent autonomy above). The default here is to get work landed: once a PR this session opened is green (CI passing, review findings fixed, mergeable), merge it. Respect the release order: core PR → merge → **push the `vX.Y.Z` tag** that publishes to PyPI (yours to push, no sign-off — just don't move plugin `stable` by hand, that ref is workflow-owned) → then the plugin PR (whose pin needs the PyPI release) merges. Re-fetch both repos' `origin/main` before merging: concurrent releases move `main` and take version numbers, so reconcile (merge, not rebase) and re-pick the next free version first.
- **Agent-facing surfaces ship in sync — across repos.** Skills describe CLI behavior implemented in helixgen-core. Core behavior change that skills describe needs companion PR here updating `skills/*` + synced `docs/` copies (`CLI.md`, `recipe-reference.md`, `helix-protocol.md`); land two PRs together, cross-reference.
- **Skills operate through CLI, not source.** Skills must let agent work purely via `helixgen` CLI; behavioral contracts live in CLI's per-verb `--help` (pinned by core's `tests/test_cli_parity.py`) + synced docs. Running engine = uv-tool-installed package — reading local checkout source can mislead about running version.
- **Never commit paid IR packs or personal device exports.**

## Releasing (automated — do NOT move `stable` or push `helixgen--v*` by hand)

Releases published by `.github/workflows/release.yml`, fires when `.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json` changes on `main`. Plugin installed from GitHub **`stable` branch** — merge to `main` does NOT ship release; only version bump + workflow does.

To cut release:

1. Bump version in **both** `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` (workflow fails build if they disagree).
2. Commit `release X.Y.Z — …`, open PR, merge to `main`.
3. Workflow auto-creates annotated tag `helixgen--vX.Y.Z`, fast-forwards `stable` to that commit. Idempotent; refuses force-push if `stable` diverged.

Do **not** manually `git branch -f stable …`, push `stable`, or push `helixgen--v*` tag — workflow owns those refs. Users get release via `/plugin` update. Plugin release needed for plugin-surface changes (skills, block-library data, docs) — and to bump engine version pin skills carry. Core releases first (PyPI `helixgen`, tag `vX.Y.Z`), then this repo bumps pin in skills + README, cuts own release.

## ralphex

Implementation tasks driven from helix coordination workspace run via [ralphex](https://github.com/umputun/ralphex) plan files in `docs/plans/` (scaffold: `docs/plans/TEMPLATE.md`); completed plans move to `docs/plans/completed/`. Launcher syncs local `main` from `origin/main` before run. Review = ralphex built-in pipeline (`external_review_tool = none`). `default_branch = main` pinned in `.ralphex/config`. `.ralphex/config` tracked; `.ralphex/worktrees/` + `.ralphex/progress/` runtime state, gitignored.
