# helixgen (Claude Code plugin)

The Claude Code plugin + single-plugin marketplace for helixgen: generate
Line 6 Helix Stadium `.hsp` presets from natural-language tone requests and
control a Stadium over the LAN. This repo carries **only the plugin
surfaces** — the engine lives in
[`helixgen-core`](https://github.com/sheax0r/helixgen-core).

**Repo family (all under `sheax0r`):**
[`helixgen-core`](https://github.com/sheax0r/helixgen-core) is the Python
package `helixgen` — libs, the CLI (the **only** engine surface since core
0.20.0 — the MCP server is removed), tests, and the authoritative docs +
backlog; **this repo** is the plugin/marketplace (skills, bundled
block-library data); [`helixgen-tui`](https://github.com/sheax0r/helixgen-tui)
is the terminal UI. Engine changes always land in helixgen-core — never patch
engine behavior from here.

## How the plugin loads the engine (CLI-first, since 4.0.0)

There is no MCP server and no `.mcp.json`. The skills drive the `helixgen`
**CLI**, provisioned as an isolated tool:

```bash
uv tool install 'helixgen[device]==0.24.0'
```

The `setup` skill's step 0 performs/verifies this (`helixgen --version`),
handles the stale-shadow failure mode (a broken `helixgen` earlier on PATH —
invoke `"$(NO_COLOR=1 uv tool dir --bin)/helixgen"` — the `NO_COLOR=1` matters:
with `FORCE_COLOR` set, uv emits ANSI codes inside the substitution — or fall
back to the plain `~/.local/bin/helixgen` path, instead of touching the
ambient Python), and upgrades with
`uv tool install --force 'helixgen[device]==X.Y.Z'`.
The CLI is self-documenting: skills start capability discovery at
`helixgen --help` / `helixgen device --help`, and each verb's `--help` is its
behavioral contract.

**The engine version pin lives in the skills** (`setup` step 0; echoed in
`tone`/`device` and README). Bumping the engine means updating the pinned
version there and cutting a plugin release.

**Block library:** the engine reads `$HELIXGEN_LIBRARY`. The skills resolve
it per session — an already-set env var wins, then a populated
`~/.helixgen/library/`, else the plugin's bundled library at
`${CLAUDE_PLUGIN_ROOT}/data/library` — and prefix **every** `helixgen`
invocation with it (shell exports don't persist across an agent's Bash
calls). `${CLAUDE_PLUGIN_ROOT}` is expanded by Claude Code anywhere in plugin
skill content, so installed skills carry the absolute path; the skills also
document the dev-checkout fallback (walk up from the skill's directory to the
ancestor containing `.claude-plugin/plugin.json`) and a sanity check (an
empty `list-blocks` result exits 0 — a silent sign the env didn't reach the
CLI).

## Project layout

- `.claude/skills/` — the three skills: `setup` (CLI provisioning +
  device/prefs onboarding), `tone` (author a `.hsp` from a tone request),
  `device` (push/sync authored tones onto the hardware)
- `.claude-plugin/` — `plugin.json` + `marketplace.json`; bumping the version
  here on `main` triggers a release (see Releasing)
- `data/library/` — the bundled block library (`HELIXGEN_LIBRARY`)
- `docs/` — the runtime references the skills consult: `CLI.md`,
  `recipe-reference.md`, `helix-protocol.md` (synced FROM helixgen-core —
  core is authoritative), plus `demo.gif`
- `tests/` — skill-doc frontmatter + content checks (`python3 -m pytest`,
  needs only pytest)

**The plugin backlog lives at `BACKLOG.md` in the coordination workspace**
(the repos' shared backlog; entries #57–#59 cover the repo split) — file
plugin-only work there.

## Development workflow

- **Worktrees, branched from fresh `github/main`.** All non-trivial work
  happens in a git worktree whose branch starts from freshly-fetched
  `github/main` (the GitHub remote is named **`github`**, not `origin`) —
  never commit directly on local `main`. Fetch again before picking a release
  version number.
- **Adversarial review before shipping.** Before merging a PR, dispatch at
  least one independent review subagent prompted to *break* the change.
  Confirmed findings are fixed or explicitly deferred to the backlog.
- **Agent-facing surfaces ship in sync — across repos.** Skills describe
  CLI behavior implemented in helixgen-core. A core behavior change that
  skills describe needs a companion PR here updating `.claude/skills/*` and
  the synced `docs/` copies (`CLI.md`, `recipe-reference.md`,
  `helix-protocol.md`); land the two PRs together and cross-reference them.
- **Skills operate through the CLI, not source.** Skills must let the agent
  work purely via the `helixgen` CLI; behavioral contracts live in the CLI's
  per-verb `--help` (pinned by core's `tests/test_cli_parity.py`) and the
  synced docs. The running engine is the uv-tool-installed package — reading
  any local checkout's source can mislead about the running version.
- **Never commit paid IR packs or personal device exports.**

## Releasing (automated — do NOT move `stable` or push tags by hand)

Releases are published by `.github/workflows/release.yml`, which fires when
`.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json` changes on
`main`. The plugin is installed from the GitHub **`stable` branch**, so
merging to `main` does NOT ship a release — only the version bump + workflow
does.

To cut a release:

1. Bump the version in **both** `.claude-plugin/plugin.json` and
   `.claude-plugin/marketplace.json` (the workflow fails the build if they
   disagree).
2. Commit `release X.Y.Z — …`, open a PR, merge to `main`.
3. The workflow auto-creates the annotated tag `helixgen--vX.Y.Z` and
   fast-forwards `stable` to that commit. Idempotent; refuses to force-push
   if `stable` diverged.

Do **not** manually `git branch -f stable …`, push `stable`, or push a
`helixgen--v*` tag — the workflow owns those refs. Users get the release via
`/plugin` update. A plugin release is needed for plugin-surface changes
(skills, block-library data, docs) — and to bump the engine version pin the
skills carry. Core releases first (PyPI `helixgen`, tag `vX.Y.Z`), then this
repo bumps the pin in the skills + README and cuts its own release.
