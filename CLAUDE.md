# helixgen (Claude Code plugin)

The Claude Code plugin + single-plugin marketplace for helixgen: generate
Line 6 Helix Stadium `.hsp` presets from natural-language tone requests and
control a Stadium over the LAN. This repo carries **only the plugin
surfaces** — the engine lives in
[`helixgen-core`](https://github.com/sheax0r/helixgen-core).

**Repo family (all under `sheax0r`):**
[`helixgen-core`](https://github.com/sheax0r/helixgen-core) is the Python
package `helixgen` — libs, CLI, MCP server, tests, and the authoritative
docs + backlog; **this repo** is the plugin/marketplace (skills, `.mcp.json`,
bundled block-library data);
[`helixgen-tui`](https://github.com/sheax0r/helixgen-tui) is the terminal
UI. Engine changes always land in helixgen-core — never patch engine
behavior from here.

## How the plugin loads the engine

`.mcp.json` launches the MCP server with
`uv run --with 'helixgen[mcp,device]==X.Y.Z' -m mcp_server`
— `uv` installs the core package (and its `mcp`/`device` extras) from PyPI
into an ephemeral env at server start. The pin is an exact PyPI version
(core is on PyPI as of v0.19.1 — core backlog #57/#58); bump it here, with a
plugin release, per engine release.
`HELIXGEN_LIBRARY` points at this repo's `data/library` — the bundled block
library that makes the plugin work out of the box.

## Project layout

- `.claude/skills/` — the three skills: `setup` (device/prefs onboarding),
  `tone` (author a `.hsp` from a tone request), `device` (push/sync authored
  tones onto the hardware)
- `.claude-plugin/` — `plugin.json` + `marketplace.json`; bumping the version
  here on `main` triggers a release (see Releasing)
- `.mcp.json` — spawns the MCP server (see above)
- `data/library/` — the bundled block library (`HELIXGEN_LIBRARY`)
- `docs/` — the runtime references the skills consult: `CLI.md`,
  `recipe-reference.md`, `helix-protocol.md` (synced FROM helixgen-core —
  core is authoritative), plus `demo.gif`
- `tests/` — skill-doc frontmatter checks (`python3 -m pytest`, needs only
  pytest)

**The plugin backlog lives at `docs/BACKLOG.md` in helixgen-core** (entries
#57–#59 cover the repo split); this repo has no separate backlog file yet —
file plugin-only work there until one exists.

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
  CLI/MCP behavior implemented in helixgen-core. A core behavior change that
  skills describe needs a companion PR here updating `.claude/skills/*` and
  the synced `docs/` copies (`CLI.md`, `recipe-reference.md`,
  `helix-protocol.md`); land the two PRs together and cross-reference them.
- **Skills operate through tools, not source.** Skills must let the agent
  work purely via CLI/MCP; behavioral contracts live in MCP tool
  descriptions (in helixgen-core's `mcp_server/`) and the synced docs.
  The running MCP server is resolved by `uv` from helixgen-core — reading
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
`/plugin` update. Since the engine is a `uv` dependency, a plugin release is
only needed for plugin-surface changes (skills, `.mcp.json`, block-library
data, docs) — and to bump the engine version pin. Because the pin is an
exact PyPI version, shipping an engine fix to plugin users means bumping the
pin in `.mcp.json` and cutting a plugin release; no `uv cache clean` on the
user's machine is involved.
