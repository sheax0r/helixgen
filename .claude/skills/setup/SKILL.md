---
name: setup
description: Use when the user wants to design, generate, or modify a Helix Stadium preset (.hsp) via helixgen, or when they want to register IRs. Verifies the helixgen CLI is installed (isolated uv tool), confirms device model (Stadium / Stadium XL only), locates the IR library, and recalls IR-related preferences. Runs before the `tone` skill picks blocks or params.
---

# helixgen setup

## Overview

This skill is the *setup* pass for any helixgen session. It makes sure the
agent has the right device-model, working helixgen CLI install, IR library,
and IR-preference context before the `tone` skill starts picking blocks (or
before the agent runs any `helixgen` command).

The engine is the `helixgen` **CLI** — there is no MCP server (removed in
core 0.20.0). The CLI is self-documenting: `helixgen --help` orients you
(verb groups + mental models), and each verb's `--help` is its full
behavioral contract.

## When to use

- User asks to design, generate, or modify a Helix preset
- User mentions an IR (impulse response) by name
- User wants to register IRs
- A previously generated preset isn't loading on the device

When NOT to use:
- Read-only questions ("what blocks do I have?") — just run
  `helixgen list-blocks` directly (with the library env — see
  **Invoking helixgen** below).
- Installing/syncing an already-authored preset onto the physical Helix over
  the LAN — that's the `device` skill (install / sync / backup), not a
  generation pass. A quick device-model check (step 1) is still worth it if
  this is the session's first exchange.

## Invoking helixgen (binary + library env) — read this once, apply to EVERY call

**Binary.** The engine is provisioned as an isolated CLI tool:
`uv tool install 'helixgen[device]==0.21.0'` puts a `helixgen` binary on
PATH (in uv's tool bin, usually `~/.local/bin`), in its own isolated env —
deliberately robust against polluted base Pythons. Verification and failure
modes are step 0 below.

**Block library.** helixgen reads blocks from `$HELIXGEN_LIBRARY` (default
`~/.helixgen/library/`). The plugin bundles a full block library so tone
work is possible out of the box. Resolve the library once per session, in
this order:

1. `$HELIXGEN_LIBRARY` is already set in the environment → leave it alone.
2. `~/.helixgen/library/` exists and is non-empty (the user built their own
   via `ingest`/`bootstrap`) → use the engine default; no env var needed.
3. Otherwise use the plugin's bundled library by prefixing the env var:

   ```bash
   HELIXGEN_LIBRARY="${CLAUDE_PLUGIN_ROOT}/data/library" helixgen list-blocks
   ```

   Claude Code expands `${CLAUDE_PLUGIN_ROOT}` to the plugin's install
   directory when this skill loads. If you see the *literal unexpanded*
   token (e.g. this skill was loaded from a repo checkout instead of an
   installed plugin), resolve the plugin root yourself: it is the ancestor
   directory containing `.claude-plugin/plugin.json` — walk up from this
   skill's own directory (the skill lives at
   `<plugin-root>/.claude/skills/setup/`).

**Sanity-check the resolution once:** run `helixgen list-blocks` with your
resolved env. If it prints an empty/`no blocks` result, the library env did
**not** reach the CLI (the exit code is still 0 — this failure is silent) —
stop and re-resolve the path rather than proceeding to tone work.

**The prefix must be on every invocation** that touches the library
(`generate`, `list-blocks`, `show-block`, `patch`, the single-op edit verbs,
`view`, `ingest`) — exported shell state does not persist between Bash
calls, so use the `ENV=value command` prefix form each time. Two more env
vars ride along the same way when they apply: device-network verbs need
`HELIXGEN_HELIX_IP=<device-ip>` (or `--ip`), and if the user has a custom IR
directory on record (step 2 / `$HELIXGEN_IRS`), prefix IR-touching verbs
(`register-irs`, `ir-scan`, `list-irs`, `generate` with IR blocks) with
`HELIXGEN_IRS="<dir>"` too — otherwise they default to `~/.helixgen/irs/`.
It's harmless to carry all applicable prefixes uniformly.

One cache to know about: IR verbs also write the **IR-hash cache** at
`~/.helixgen/cache/irhash.json` — and they do so **regardless of
`HELIXGEN_IRS`** (the IR-directory env does not relocate it). If a session
needs full isolation (tests, sandboxes), also set `HELIXGEN_IRHASH_CACHE`
(path to the single cache file) or `HELIXGEN_CACHE` (the cache *directory*)
alongside the other env prefixes. Inspect/maintain it with
`helixgen ir-cache --stats|--clear|--prune`. Normal sessions can ignore it.

## Editing an existing preset (direct edits)

Not every "modify" request is a full tone-design pass. If the user wants a
*targeted* change to a preset that already exists — change one param, disable
a block, swap a model, add/remove a block — that's the surgical-edit path, not
the `tone` skill: `helixgen patch <preset.hsp> <ops.json|->` for an atomic
batch, or the single-op verbs `set-param`/`enable`/`disable`/`add-block`/
`remove-block`/`swap-model`, plus read-only `view`. Run `helixgen patch
--help` for the ops schema; see the **"Commands"** section of `docs/CLI.md`
for the full verb list and the disambiguation flags (`--path`/`--lane`/
`--pos`, `--snapshot`). Still worth a quick device-model check (step 1
below) if this is the first exchange of the session; skip the rest of setup
(IR library location, IR preferences) unless the edit itself touches an IR
block.

## Before generating or modifying any preset

In order, every session:

### -1. Verify `uv` is on PATH

The helixgen CLI is installed and upgraded with `uv tool install`, so `uv`
itself must be present. Run `which uv` (or `command -v uv`) via Bash. If it
resolves, proceed — no need to mention it to the user. If missing, tell them
in one line:

> "helixgen is installed via `uv`. Install it with `brew install uv` (macOS)
> or `curl -LsSf https://astral.sh/uv/install.sh | sh`, then re-run this."

### 0. Verify the helixgen CLI — provision it if needed

Run:

```bash
helixgen --version
```

- **Prints `helixgen, version 0.21.0`** (the version this plugin release is
  built against) → proceed.
- **Command not found** → install it (isolated env; needs network the first
  time):

  ```bash
  uv tool install 'helixgen[device]==0.21.0'
  ```

  If the shell still can't find `helixgen` afterwards, uv's tool bin isn't
  on PATH — invoke it by absolute path (`"$(NO_COLOR=1 uv tool dir
  --bin)/helixgen"`, usually `~/.local/bin/helixgen`) and suggest the user
  run `uv tool update-shell` once.
- **Traceback (`ModuleNotFoundError: No module named 'helixgen'`) or a
  version other than the pin** → a **stale `helixgen` elsewhere on PATH is
  shadowing the uv tool** (e.g. a broken editable install in a base
  interpreter). Do NOT try to fix that ambient Python environment — it is
  not the engine. Invoke the uv-installed binary by absolute path instead:
  `"$(NO_COLOR=1 uv tool dir --bin)/helixgen"` — and use that path for the
  rest of the session. The `NO_COLOR=1` is load-bearing: when the session
  has `FORCE_COLOR` set (Claude Code often does), `uv tool dir --bin` emits
  ANSI escape codes *inside* the command substitution and the resulting path
  is garbage. If the substitution misbehaves anyway, fall back to the plain
  default path `~/.local/bin/helixgen`.
- **Upgrading** (when a newer plugin release pins a newer core):
  `uv tool install --force 'helixgen[device]==X.Y.Z'`.

Never `pip install` helixgen into the ambient Python for plugin use — the
uv tool env is the supported, isolated install.

### 0.25. Discover the CLI's capabilities from its own help

The **first** capability-discovery step is always:

```bash
helixgen --help          # verb groups + the mental models
helixgen device --help   # device read-vs-write split, tone-library model
helixgen <verb> --help   # the full behavioral contract for any verb
```

Help is the contract — per-verb `--help` carries everything you need to use
a verb correctly (arg shapes, gotchas, consent flags, JSON output). The
synced `docs/CLI.md`, `docs/recipe-reference.md`, and `docs/helix-protocol.md`
in this plugin remain the deep references; reach for them when help points
there (SEE ALSO) or for full recipe-field detail.

### 0.5. Load user preferences

Before checking device/IR details, load `~/.helixgen/preferences.json`
(override the whole-file location with `$HELIXGEN_PREFS`; override a single
key with `HELIXGEN_<KEY>` env, e.g. `HELIXGEN_FAVOR_IRS=1`). Precedence per
key: env var > file value > Claude-memory seed > built-in default.

- **File absent (first run):** scaffold it. Seed `device.model` from
  `user_device.md` and `instruments` from `user_guitars.md` if those memories
  exist; otherwise leave `device.model: null` and `instruments: []` (step 1
  will ask). `guard_paid_irs_in_git` and `reveal_in_finder` seed `true`
  (matching the existing feedback-memory defaults); `favor_irs` seeds `true`
  only if a "prefer IRs" feedback memory exists, else `false`. Tell the user
  in one line: "Created `~/.helixgen/preferences.json` — edit it any time to
  change these defaults (device model, favor_irs, instruments, …)." If
  `reveal_in_finder` resolves true and this is macOS, `open -R` the new file.
- **File present:** read it and apply each setting for the rest of the
  session. The file is now the authority — memory (`user_device.md`,
  `user_guitars.md`, the feedback memories) becomes a fallback/seed only;
  don't re-derive a setting from memory once the file carries an explicit
  value for it.
- **Learning a new value** (the user states their device model for the first
  time, or says "prefer IRs" / "favor cabs"): confirm before writing it back
  the *first* time a given key is set this way — e.g. "I'll set `favor_irs:
  true` in preferences.json — ok?" Once the user has confirmed that key once,
  later updates to it can be written silently.

Keys this skill owns: `device.model`, `favor_irs`, `reveal_in_finder`,
`guard_paid_irs_in_git`, `instruments`, `default_guitar`. (`preset_output_dir`
and `author` are consumed by the `tone` skill.) `ir_library_dir` is
deliberately **not** in this file — the IR directory stays env-only via
`$HELIXGEN_IRS`; see step 2.

#### Instruments

`instruments` is an array recording the user's confirmed guitars/basses,
seeded on first scaffold from `user_guitars.md` if present. Record shape:

```json
{
  "name": "Gibson Les Paul Junior",
  "type": "guitar",
  "pickups": "one bridge P-90 (single-coil soapbar)",
  "selector": "none",
  "genres": ["punk", "garage", "raw rock", "blues"],
  "notes": "breaks up early; vol + tone only"
}
```

Fields: `name`, `type` (`"guitar"`|`"bass"`) required; `pickups` (free text),
`selector` (`"none"`|`"3-way"`|`"5-way"`|string), `active` (bool — active vs
passive pickups), `genres` (array of style hints used to auto-pick an
instrument when the user doesn't name one), `notes` (one-liner) all optional.
This feeds the `tone` skill's instrument recommendations — picking a guitar by
`genres` when none is named, and phrasing pickup/selector guidance from
`selector`/`pickups`.

Seed the user's four confirmed instruments on first scaffold:

- **LP Jr** — P-90 (single bridge pickup), no selector (`"none"`).
- **ESP LTD EC-1000** — active EMG HH, 3-way selector.
- **Strandberg Boden Essential 6** — HSS, 5-way selector.
- **Ibanez Prestige** — HSH, 5-way selector.

`default_guitar` is a string naming which of the user's `instruments` to
default to when a tone request doesn't name a guitar — it feeds tone-naming
(the preset title, `.hsp`/`.md` filename, and description are named for the
target guitar). If it's unset (`null`) and the `tone` skill needs a guitar, the
tone skill asks the user which guitar to use and offers to save their choice
here (confirm-first-then-silent, matching the other prefs).

There's no `helixgen prefs` CLI yet — the file is plain JSON
(`json.load`/atomic tmp+rename write), so read or hand-edit it directly. Edit
it by hand or let this skill write it back per the confirm-first-then-silent
rule above.

### 1. Confirm the device model

Read `device.model` from `preferences.json` (loaded in step 0.5):

- **Set:** trust it — a file doesn't go stale, so there's no memory-age check
  to do here (unlike the old `user_device.md`-only flow).
- **Unset (`null`):** ask: "Which Helix do you have? Stadium, Stadium XL, or
  something else?" Write the answer back to `device.model` in the
  preferences file (confirm-first-then-silent, per 0.5); it's fine to also
  note it in memory as a convenience, but the file is the control now.

If the answer is *not* Stadium or Stadium XL, tell the user helixgen
supports the Stadium family only for now and stop — don't generate
something that won't load on their device.

This confirmation matters: the CLI no longer takes a per-call `model`
argument (the old MCP soft-gate is gone) — this step is the real
device-confirmation gate.

### 2. Locate IR library if applicable

If the user mentions IRs or `With Pan`/IR cab blocks:

- Check memory for `user_ir_directory.md`.
- **If absent**, ask: "Where do your impulse responses live? (Provide a
  directory path.)" Record. If the directory has many IRs (>50),
  bulk-cache hashes in one run: `helixgen ir-scan <dir> --json` (recursive;
  the `--json` summary reports `{registered, already_registered, conflicts,
  failed}`).
- **If present**, proceed; don't re-ask. The user can edit the memory if
  they reorganize.

### Registering a single IR mid-conversation

If the user names one specific WAV, run `helixgen register-irs <wav>` — it
prints the computed `<hash>  <wav>` pair. This changes `mapping.json` — see
**Git-commit IR library changes** below. (To hash without registering
anything, `helixgen irhash <wav-or-dir>... [--json]` is stateless.)

### 3. Recall IR preferences

`favor_irs` in `preferences.json` (loaded in step 0.5) is now the authority
for "prefer a matching user IR block over a stock cab" — true only once the
user has set it or confirmed it via the step-0.5 write-back. Older "prefer
IRs" feedback-memory notes were the prior mechanism; they only matter now as
the one-time seed value used the first time the file was scaffolded.

**First, check for a local cab-pack catalog** at `<ir-library>/_catalog/`
(e.g. `~/git/helixgen/irs/_catalog/`). If present it's the authoritative tonal
reference — grep it to pick an IR by character. It has an index `README.md`
(controlled tag vocabulary + mic legend) and one file per pack with per-mix mic
combos and tags. Examples:

```bash
grep -rin 'high-gain' ~/git/helixgen/irs/_catalog/*.md | grep tight  # tight modern-metal
grep -n beefy ~/git/helixgen/irs/_catalog/kw.md                       # beefiest Greenback
grep -rin vintage ~/git/helixgen/irs/_catalog/*.md | grep clean       # vintage clean
```

Then check memory for `project_ir_notes.md` (if present) for any user-specific
one-line preferences layered on top. Examples:

- `- YA DXVB 112 Mix 03 — vintage Marshall-leaning, bright top; user reaches
  for it on clean tones`
- `- OH SLO V30 Cap 02 — modern high-gain; sits well in thrash rhythm`

## When the user mentions an IR you haven't seen before

### 1. Try web research — only for known commercial-pack prefixes

If the basename matches a known commercial pack prefix:

| Prefix | Pack |
|--------|------|
| `YA `  | York Audio |
| `OH `  | Ownhammer |
| `3SP ` | 3 Sigma |
| `CTC ` | Celestion |
| `MJ `  | Mikko Jaakkola |

…web-search `<pack name> <basename> tonal description` to find what
amp/cab/mic combination it models and its character.

### 2. NEVER invent tonal descriptions from basename pattern-matching

`DXVB` does not "suggest a Diezel VH4" just because it starts with D. If
web research returns nothing high-confidence, **do not describe the IR
from the filename alone**. Ask the user: "What's `<basename>` meant for?
Any specific tones you reach for it for?"

### 3. Record findings

Add a one-line entry to `project_ir_notes.md` keyed by basename. Keep each
entry to one sentence; the file should stay scannable.

**If a whole new commercial cab pack was added to the IR library** (not just one
stray WAV), catalog it in `<ir-library>/_catalog/`: read the pack's
`*Manual*.pdf`, `ls` its `Mixes/` folder for exact basenames, optionally
FFT-measure each mix's band energy for bright/dark/beefy/tight tags, and write
`_catalog/<slug>.md` from the template + controlled vocabulary in
`_catalog/README.md` (its "Adding a new pack" section is the full procedure).
This keeps "which IR is beefiest/brightest/best-for-X" answerable by grep.

## Git-commit IR library changes

Registering an IR (`mapping.json`) or cataloging a new pack (`_catalog/<slug>.md`
+ the `_catalog/README.md` index) changes files under the IR library directory.
If that directory is git-managed, commit just those files:

1. **Detect per-directory**: `git -C <ir-library-dir> rev-parse
   --is-inside-work-tree`. If it errors or prints `false`, skip silently.
2. **Honor `git_commit_tones`** from `preferences.json` (default `"auto"`
   commits whenever step 1 says yes; `"true"` always tries; `"false"` never
   commits).
3. **Respect `guard_paid_irs_in_git`** (default `true`): never `git add` a
   gitignored paid IR `.wav` (see CLAUDE.md's "no paid IRs in repo" note) —
   commit only `mapping.json` and `_catalog/*.md`. If the user has explicitly
   turned `guard_paid_irs_in_git` off and wants a WAV tracked too, that's a
   deliberate `git add -f` they run themselves, not something this skill does
   for them.
4. **Stage exactly the changed tracked files** (`git -C <ir-library-dir> add
   -- mapping.json`, or `git -C <ir-library-dir> add -- _catalog/<slug>.md
   _catalog/README.md`), never `-A`/`.`. Check `git -C <ir-library-dir>
   status` first: if the repo already has unrelated staged changes, warn the
   user and skip rather than folding them into the commit.
5. **Commit locally, never push** — `git -C <ir-library-dir> commit -m
   "<message>"` with a short message, e.g. `ir: register YA VX30 212 BLU Mix
   01.wav` or `ir: catalog Ownhammer OH V30 pack`.

Keep every git command scoped with `-C <ir-library-dir>` (as in step 1) —
your shell's cwd is usually **not** the IR library, so an unscoped
`git add`/`commit` targets the wrong repo.

## After generating a preset that uses user IRs

Tell the user, in one sentence:

> "Make sure these IRs are loaded on your Stadium via the Librarian → Cab
> IRs → Import before you load this preset, or the IR block will show
> 'No Model'."

…then list the IR basenames the preset references so the user can verify.
(This applies to the HX Edit/USB loading path — if the preset instead goes
onto the device over the LAN via the `device` skill, `device sync` /
`device install --auto-irs` upload the referenced IRs automatically.)
Use `open -R "<path-to-hsp>"` to reveal the generated preset in Finder
(per the `feedback_reveal_file_in_finder.md` rule).
