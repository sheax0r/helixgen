# helixgen (Claude Code plugin)

Claude Code plugin + single-plugin marketplace for helixgen: generate Line 6 Helix Stadium `.hsp` presets from natural-language tone requests, control Stadium over LAN. Repo carries **only plugin surfaces** — engine lives in [`helixgen-core`](https://github.com/sheax0r/helixgen-core).

**Repo family (all under `sheax0r`):** [`helixgen-core`](https://github.com/sheax0r/helixgen-core) = Python package `helixgen` — libs, CLI (**only** engine surface since core 0.20.0 — MCP server removed), tests, authoritative docs + backlog; **this repo** = plugin/marketplace (skills, bundled block-library data); [`helixgen-tui`](https://github.com/sheax0r/helixgen-tui) = terminal UI. Engine changes always land in helixgen-core — never patch engine behavior from here.

## How the plugin loads the engine (CLI-first, since 4.0.0)

No MCP server, no `.mcp.json`. Skills drive `helixgen` **CLI**, provisioned as isolated tool:

```bash
uv tool install 'helixgen[device]==0.30.0'
```

`setup` skill step 0 performs/verifies this (`helixgen --version`), handles stale-shadow failure mode (broken `helixgen` earlier on PATH — invoke `"$(NO_COLOR=1 uv tool dir --bin)/helixgen"` — `NO_COLOR=1` matters: with `FORCE_COLOR` set, uv emits ANSI codes inside substitution — or fall back to plain `~/.local/bin/helixgen` path, never touch ambient Python), upgrades with `uv tool install --force 'helixgen[device]==X.Y.Z'`.
CLI self-documenting: skills start capability discovery at `helixgen --help` / `helixgen device --help`; each verb's `--help` = its behavioral contract.

**Engine version pin lives in skills** (`setup` step 0; echoed in `tone`/`device` and README). Bump engine = update pinned version there + cut plugin release.

**Block library:** engine reads `$HELIXGEN_LIBRARY`. Skills resolve per session — already-set env var wins, then populated `~/.helixgen/library/`, else plugin's bundled library at `${CLAUDE_PLUGIN_ROOT}/data/library` — and prefix **every** `helixgen` invocation with it (shell exports don't persist across agent Bash calls). `${CLAUDE_PLUGIN_ROOT}` expanded by Claude Code anywhere in plugin skill content, so installed skills carry absolute path; skills also document dev-checkout fallback (walk up from skill directory to ancestor containing `.claude-plugin/plugin.json`) and sanity check (empty `list-blocks` result exits 0 — silent sign env didn't reach CLI).

## Project layout

- `.claude/skills/` — three skills: `setup` (CLI provisioning + device/prefs onboarding), `tone` (author `.hsp` from tone request), `device` (push/sync authored tones onto hardware)
- `.claude-plugin/` — `plugin.json` + `marketplace.json`; version bump here on `main` triggers release (see Releasing)
- `data/library/` — bundled block library (`HELIXGEN_LIBRARY`)
- `docs/` — runtime references skills consult: `CLI.md`, `recipe-reference.md`, `helix-protocol.md` (synced FROM helixgen-core — core authoritative), plus `demo.gif`
- `tests/` — skill-doc frontmatter + content checks (`python3 -m pytest`, needs only pytest)

**Plugin backlog lives at `BACKLOG.md` in coordination workspace** (repos' shared backlog; entries #57–#59 cover repo split) — file plugin-only work there.

## Development workflow

- **Worktrees, branched from fresh `github/main`.** All non-trivial work in git worktree whose branch starts from freshly-fetched `github/main` (GitHub remote named **`github`**, not `origin`) — never commit directly on local `main`. Fetch again before picking release version number.
- **Adversarial review before shipping.** Before merging PR, dispatch at least one independent review subagent prompted to *break* change. Confirmed findings fixed or explicitly deferred to backlog.
- **Agent-facing surfaces ship in sync — across repos.** Skills describe CLI behavior implemented in helixgen-core. Core behavior change that skills describe needs companion PR here updating `.claude/skills/*` + synced `docs/` copies (`CLI.md`, `recipe-reference.md`, `helix-protocol.md`); land two PRs together, cross-reference.
- **Skills operate through CLI, not source.** Skills must let agent work purely via `helixgen` CLI; behavioral contracts live in CLI's per-verb `--help` (pinned by core's `tests/test_cli_parity.py`) + synced docs. Running engine = uv-tool-installed package — reading local checkout source can mislead about running version.
- **Never commit paid IR packs or personal device exports.**

## Releasing (automated — do NOT move `stable` or push tags by hand)

Releases published by `.github/workflows/release.yml`, fires when `.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json` changes on `main`. Plugin installed from GitHub **`stable` branch** — merge to `main` does NOT ship release; only version bump + workflow does.

To cut release:

1. Bump version in **both** `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` (workflow fails build if they disagree).
2. Commit `release X.Y.Z — …`, open PR, merge to `main`.
3. Workflow auto-creates annotated tag `helixgen--vX.Y.Z`, fast-forwards `stable` to that commit. Idempotent; refuses force-push if `stable` diverged.

Do **not** manually `git branch -f stable …`, push `stable`, or push `helixgen--v*` tag — workflow owns those refs. Users get release via `/plugin` update. Plugin release needed for plugin-surface changes (skills, block-library data, docs) — and to bump engine version pin skills carry. Core releases first (PyPI `helixgen`, tag `vX.Y.Z`), then this repo bumps pin in skills + README, cuts own release.

## ralphex

Implementation tasks driven from helix coordination workspace run via [ralphex](https://github.com/umputun/ralphex) plan files in `docs/plans/` (scaffold: `docs/plans/TEMPLATE.md`); completed plans move to `docs/plans/completed/`. Launcher syncs local `main` from `github/main` before run. Review = ralphex built-in pipeline (`external_review_tool = none`). `default_branch = main` pinned in `.ralphex/config` — remote named `github`, so no `origin/HEAD` auto-detect. `.ralphex/config` tracked; `.ralphex/worktrees/` + `.ralphex/progress/` runtime state, gitignored.
