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
`uv tool install 'helixgen[device]==0.36.0'` puts a `helixgen` binary on
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
vars ride along the same way when they apply: device-network verbs normally
need **no address env at all** — since core 0.24.0 they resolve the record
persisted by `helixgen device discover` (step 1.5 below; `--ip` and
`$HELIXGEN_HELIX_IP` remain overrides, not the primary path). And if the
user has a custom IR
directory on record (step 2 / `$HELIXGEN_IRS`), prefix IR-touching verbs
(`register-irs`, `ir-scan`, `list-irs`, `generate` with IR blocks) with
`HELIXGEN_IRS="<dir>"` too — otherwise they default to `<library>/irs`, i.e.
**inside whatever `HELIXGEN_LIBRARY` points at**. Under the bundled-library
fallback that is the plugin's own `data/library/irs/`, which a `/plugin`
update can replace — so if the user is registering IRs they want to keep,
either put them on record under `$HELIXGEN_IRS` or move them somewhere
durable. (`~/.helixgen/irs/` is the pre-0.26 *legacy* location; core only
reads it to bridge an old `mapping.json` up on first use.)
It's harmless to carry all applicable prefixes uniformly.

One cache to know about: IR verbs also write the **IR-hash cache** at
`~/.helixgen/cache/irhash.json` — and they do so **regardless of
`HELIXGEN_IRS`** (the IR-directory env does not relocate it). Since core
0.29.0 a session that needs full isolation (tests, sandboxes) should just set
`$HELIXGEN_HOME` — the cache follows it, along with everything else (see the
next paragraph). `HELIXGEN_IRHASH_CACHE` (path to the single cache file) and
`HELIXGEN_CACHE` (the cache *directory*) remain available as finer-grained
overrides, as does `HELIXGEN_LOCKS` (the device-lock lease root; see the
`device` skill). Inspect/maintain the cache with
`helixgen ir-cache --stats|--clear|--prune`. Normal sessions can ignore it.

**The helixgen home (`$HELIXGEN_HOME`, 0.22.0).** `$HELIXGEN_HOME` (default
`~/.helixgen`) is the root of what the engine persists — the block library,
IRs, the setlists manifest (now at `setlists/manifest.json`), per-device
observed state (`devices/`), and device-lock leases (`locks/`) all derive
their default location from it, and the per-area env vars
(`HELIXGEN_LIBRARY`, `HELIXGEN_IRS`, `HELIXGEN_SETLISTS`, `HELIXGEN_LOCKS`)
win over the home-derived default when set. **Since core 0.29.0 it is a
one-knob isolation switch:** `preferences.json` and the IR-hash cache follow
`$HELIXGEN_HOME` too (they anchored to the real `~/.helixgen` in earlier
versions), so setting it alone relocates every area a tone/device session
touches. (One straggler: `helixgen bootstrap`'s upstream-repo clone cache is
still hard-coded to `~/.helixgen/.cache` — irrelevant to normal sessions.)
`HELIXGEN_PREFS` and
`HELIXGEN_IRHASH_CACHE` (or `HELIXGEN_CACHE`) remain available as
finer-grained overrides that win over the home. Two engine
behaviors to not be surprised by: on its first write
the engine **auto-initializes the home as a git repo** (whenever `git` is on
PATH; a missing git only warns — nothing fails) with `devices/`, `cache/`,
`locks/`, and IR audio gitignored, and it **auto-commits manifest saves**
there, gated by the `git_commit_tones` preference (`"false"` skips the
commits). That home repo is the engine's — don't hand-manage it; the
git-commit guidance later in this skill is about the *IR library* directory,
which is a different, user-owned location.

**Device-mutating verbs auto-lock (0.22.0).** Every verb that writes to the
Stadium auto-acquires a machine-local advisory lock so concurrent helixgen
processes don't collide on the device — the `device` skill's "Device locks"
section (and `docs/CLI.md` "Device locks") is the full model; nothing to do
here in setup.

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

- **Prints `helixgen, version 0.36.0`** (the version this plugin release is
  built against) → proceed.
- **Command not found** → install it (isolated env; needs network the first
  time):

  ```bash
  uv tool install 'helixgen[device]==0.36.0'
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
  `user_device.md` if that memory exists; otherwise leave `device.model: null`
  (step 1 will ask). `guard_paid_irs_in_git` and `reveal_in_finder` seed `true`
  (matching the existing feedback-memory defaults); `favor_irs` seeds `true`
  only if a "prefer IRs" feedback memory exists, else `false`. The user's
  guitars are **not** stored here — they live as guitar **profiles** under
  `library/guitars/` (see **Guitar profiles** below); scaffold those separately.
  Tell the user in one line: "Created `~/.helixgen/preferences.json` — edit it
  any time to change these defaults (device model, favor_irs, …)." If
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

#### Converge, don't interview

A setup pass that ends in a list of questions has done half its job. **Fix
what has one correct answer; ask only where the answer is genuinely the
user's.** The test is simple: *could I be wrong about this?* If not, do it and
say you did.

**Do it, don't ask:**

- **The engine is behind the pin this plugin declares.** That is not a
  preference — the pin IS the version these skills are written against, and a
  mismatch is the single most common source of "the skill told me to run a
  flag that doesn't exist". Run `uv tool install --force
  'helixgen[device]==<pin>'`, verify `helixgen --version`, report the upgrade
  in one line. (Do ask before a DOWNGRADE — an engine ahead of the pin may be
  deliberate.)
- **A missing `normalization` block on an existing profile.** Core scaffolds
  it for a brand-new profile, so a user whose `preferences.json` merely
  predates that release gets a worse default for no reason. Write the same
  thing core would: `mode: "play"`, `target_db: 17.5` with its
  `target_source` provenance. Nothing here is a guess (see below).
- **Any missing scaffold with a known-correct shape** — the `~/.helixgen`
  layout, a `preferences.json` that doesn't exist at all, the home git repo.

**Ask, because you cannot know:**

- **`default_guitar`** — which guitar they actually reach for. Only they know.
- **Anything destructive**: deleting stale device records, pruning IRs,
  running `library migrate` for real, overwriting a file that already has
  content.
- **A rig decision**: `normalization.mode` beyond the `play` default, because
  `sample` and `looper` mean cabling and a calibration the user has to
  physically do.
- **Subjective content**: `character_md` on a guitar profile, IR character
  tags. Offer to draft, never invent silently.

Report gaps you did NOT act on as a short list, not as a queue of questions to
work through one at a time.

Keys this skill owns: `device.model`, `favor_irs`, `reveal_in_finder`,
`guard_paid_irs_in_git`, `default_guitar`, and the `normalization` block
(below). (`author` is consumed by the `tone` skill.) The user's guitars are no longer a preferences key — they are guitar
**profiles** under `library/guitars/` (see **Guitar profiles** below).
`instruments` and `preset_output_dir` are **deprecated** (replaced by guitar
profiles and the `library/tones/` default write location); if a loaded
`preferences.json` still carries either non-empty key, the engine prints a
one-line stderr warning pointing at `helixgen library migrate`, which removes
them — offer to run it (see **Migrating a pre-library home** below). Both keys
are still parsed for back-compat until migrated. `ir_library_dir` is
deliberately **not** in this file — the IR directory stays env-only via
`$HELIXGEN_IRS`; see step 2.

#### Guitar profiles

The user's guitars are stored as **profiles** — one JSON file per guitar at
`library/guitars/<slug>.json` (schema 1; `slug = slugify(name)`), under the
helixgen home library, **not** in `preferences.json`. The profile file is the
on-disk source of truth for a guitar. Scaffolding and editing profiles
(**including the control inventory**) via structured questions is this skill's
job — it replaces the old `instruments`-array onboarding. Create new profiles
with `helixgen library add-guitar <name> [--short-name SHORT] [--type
guitar|bass]` (0.27.0) — it scaffolds the schema-1 skeleton at
`library/guitars/<slug>.json` (name, short_name, type; every other field
null/empty for this skill to enrich) and auto-commits the home repo like every
other library write; then fill in the remaining fields by editing that JSON
directly. A profile already at `slugify(name)` is refused (exit 1) — edit the
existing JSON instead (`library validate` checks it). Read/verify existing
profiles with `helixgen library show <guitar> --json` and
`helixgen library list --guitars [--json]`.

Profile shape:

```json
{
  "schema": 1,
  "name": "Gibson Les Paul Junior",
  "short_name": "Les Paul Jr",
  "type": "guitar",
  "active": false,
  "pickups": "one bridge P-90 (single-coil soapbar)",
  "construction": "mahogany body + neck, wraparound bridge",
  "character_md": "Breaks up early; raw, midrange-forward — vol + tone only.",
  "genres": ["punk", "garage", "raw rock", "blues"],
  "controls": [
    {"name": "Volume", "kind": "knob"},
    {"name": "Tone", "kind": "knob"}
  ]
}
```

Fields: `name`, `short_name` (what appears in preset display names / filename
slugs), `type` (`"guitar"`|`"bass"`), `active` (bool|null — active vs passive
pickups), `pickups`, `construction`, `character_md` (the tonal character — what
the guitar is *for*; the `tone` skill reads this to adapt params), `genres[]`
(style hints used to auto-pick a guitar when none is named), and `controls[]`
— the **control inventory**: each control is `{name, kind, positions?, notes?}`
where `kind` ∈ `knob`/`switch`/`push-pull`/`other` (a pickup selector is a
`switch` whose `positions` list its settings). A tone variant's
`guitar_settings` keys validate (as warnings) against these control names, so
capture the physical controls accurately.

**Scaffold a profile by asking structured questions**, one guitar at a time:
its name, a short name for display, type (guitar/bass), pickups, construction,
what it's tonally for (→ `character_md`), the genres it suits, and its physical
controls — every knob, switch, pickup selector (with its positions), and
push-pull. Run `library add-guitar` with the name/short-name/type answers,
then write the rest into `library/guitars/<slug>.json`. If a
`user_guitars.md` memory exists, seed one profile per guitar from it (the
user's confirmed guitars: **Les Paul Jr** — P-90 bridge, vol + tone only;
**ESP LTD EC-1000** — active EMG HH, 3-way selector; **Strandberg Boden
Essential 6** — HSS, 5-way; **Ibanez Prestige** — HSH, 5-way), still confirming
the control inventory with the user.

**Committing:** do **not** git-commit the profile yourself. Core owns the
home-repo commits — `library add-guitar` auto-commits the scaffold it writes,
and any later library-mutating verb runs `git add -A` on the helixgen home, so
the directly-edited enrichment is swept into core's next auto-commit. Just
note briefly that enrichment edits land on the next library write, rather than
committing them here.

`default_guitar` (in `preferences.json`) now names a guitar **profile** — its
slug, `name`, or `short_name` — to default to when a tone request doesn't name
a guitar (`HELIXGEN_DEFAULT_GUITAR` env override still works). It feeds
tone-naming (the preset title, `.hsp`/`.md` filename, and description are named
for the target guitar's `short_name`). If it's unset (`null`) and the `tone`
skill needs a guitar, the tone skill asks which guitar to use and offers to save
the choice here (confirm-first-then-silent, matching the other prefs).

There's no `helixgen prefs` CLI yet — `preferences.json` is plain JSON
(`json.load`/atomic tmp+rename write), so read or hand-edit it directly, per the
confirm-first-then-silent rule above. The one exception is the `normalization`
block, which **`helixgen device calibrate` writes for you** — don't hand-edit
the `calibration` sub-block, it is measured data.

#### The `normalization` block (0.35.0)

The loudness-normalization protocol: which stimulus, which target, and the
calibration that makes runs comparable between sessions. **Additive — an
absent block means every `device normalize` flag keeps its built-in default**,
so scaffolding it is a convenience, never a requirement.

```jsonc
"normalization": {
  "mode": "play",            // play | sample | looper — see the `device` skill
  "target_db": 17.5,         // the SHIPPED reference target — scaffolded, not invented
  "target_source": {...},    // where 17.5 came from; scaffolded alongside it
  "seconds": null,           // measurement window (CLI default 10)
  "tolerance_db": null,      // in-band dead zone (CLI default 1.0)
  "measure_via": null,       // meters | capture (CLI default meters)
  "capture_input": null,     // capture device NAME, for measure_via=capture
  "sample": {                // the recorded stimulus, `sample` mode only
    "path": null, "loop_seconds": null,
    "playback_cmd": "play -q {path} repeat 9999",
    "output_device": null, "volume": null
  },
  "calibration": {           // WRITTEN BY `device calibrate` — measured, don't invent
    "reference_input_db": null, "reference_guitar": null,
    "achieved_input_db": null, "calibrated_on": null
  }
}
```

Scaffold it with `mode: "play"` and everything else null on first run: `play`
mode needs no cabling and no calibration, so the user is immediately able to
normalize. Rules for the rest:

- **`target_db`**: **17.5 dB, written without asking.** Core 0.36.0 scaffolds
  it into a brand-new profile, so an older `preferences.json` missing the
  block should simply be brought up to the same state — the value is not a
  judgement call. Its provenance goes in `target_source`: the factory
  *Stadium Rock Rig* measured 17.51 dB total (2026-07-29, Stadium XL). It is
  a CONSTANT, not something each rig measures: the factory presets are identical across Stadiums, and
  separate runs only land on a common level when they all use the same
  number. Don't replace it with a per-preset guess, and don't leave it null —
  a null target makes `device normalize` anchor on its own first target,
  level-matching within one preset while leaving separate runs unmatched.
  One exception: it is a METERS target. A `--measure-via capture` run needs a
  LUFS target (≤ 0), and the engine refuses a positive one there.
- **`calibration`**: `helixgen device calibrate` owns it. Recording a
  reference you did not measure would make every later run confidently wrong.
- **`mode`**: changing it is a rig decision (does the user want to play, or to
  cable a computer into Inst 1?) — ask, don't infer. `device calibrate` sets it
  to `sample` when it succeeds.
- Scalars honor `HELIXGEN_NORMALIZE_*` env overrides
  (`HELIXGEN_NORMALIZE_TARGET_DB`, `_MODE`, `_SECONDS`, `_TOLERANCE_DB`,
  `_MEASURE_VIA`, `_CAPTURE_INPUT`); the nested blocks are file-only.

The `device` skill owns what the modes mean, what to cable, and how to run the
calibration — point the user there rather than re-explaining it here.

#### Migrating a pre-library home

An existing user whose `~/.helixgen` predates the library layout should be
offered `helixgen library migrate` — a one-shot, idempotent migration into the
new layout. The stderr warning about deprecated `instruments` /
`preset_output_dir` keys (above) is the usual trigger. It:

- moves each manifest tone's `.hsp` into `library/tones/<slug>.hsp` under the
  new naming schema, folds a sibling `.md` into `description_md`, writes
  per-tone metadata JSON, and re-keys the manifest;
- **copies** (never moves) each mapped IR WAV into `library/irs/<pack>/` with a
  scaffolded metadata sidecar, and rewrites `mapping.json`;
- seeds a guitar profile from each `preferences.instruments` entry;
- removes the deprecated `instruments` / `preset_output_dir` keys from
  `preferences.json` and reconciles `default_guitar`.

**Run `helixgen library migrate --dry-run` FIRST** — it prints an editable plan
(JSON) and mutates nothing; recommend the user review/correct it before
executing (`--plan <plan.json>` then runs a reviewed plan). EXPLAIN what migrate
does and get explicit user consent before running the real (non-dry-run)
migration.

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

### 1.5. Locate the device on the network — discover-first (0.24.0)

Only when the session will actually talk to the device over the LAN (the
`device` skill, or any `helixgen device` verb). Skip entirely for pure
generation/edit sessions.

**Run discovery once — don't hunt for the IP by hand:**

```bash
helixgen device discover          # or --json for the machine shape
```

It finds the Stadium via mDNS (the device advertises
`_stadiumserver._tcp.local.` and answers a one-shot multicast query), falls
back to a bounded TCP probe of this machine's own /24 only, confirms every
candidate with the read-only `/ProductInfoGet` handshake, and **persists**
ip/serial/model/firmware — plus `port` **only when nonstandard** (one above
the advertised stream port; the observed 2001→2002 offset — a standard device
stays portless, `None` = the default 2002) — into
`~/.helixgen/devices/<serial>.json`. It is read-only on the device (no lock).
After one successful discover, **every device verb resolves the address
automatically** — no env prefix, no flag.

**The resolution chain (0.24.0):** `--ip` > `$HELIXGEN_HELIX_IP` > the
persisted discover record. There is **no built-in default IP** any more, and
a missing address never stalls: with none of the three available, device
verbs **fail fast with an instructive error naming `device discover`** — the
fix is to run it, not to guess an address. An **empty/whitespace-only `--ip`**
(typically an unset shell variable) is **rejected** with a nonzero exit — no
longer silently treated as unset (behavior change, #77); omit the flag to fall
back down the chain. `--port` defaults to the record's persisted port (2002
unless a nonstandard advertised port was recorded); an explicit `--port` wins.
To drop a stale record, `helixgen device discover --forget SERIAL-OR-IP` (no
network; see the `device` skill / `docs/CLI.md`).

- **Discovery found the device** → done; the record is persisted. Nothing to
  export, nothing to remember.
- **Discovery found nothing** (multicast blocked *and* the probe missed) →
  only then ask the user for the device's IP, and pass it explicitly:
  `--ip <addr>` on the verb, or a `HELIXGEN_HELIX_IP=<addr>` prefix.
  `$HELIXGEN_HELIX_IP` stays documented as an **override** (multiple devices,
  unusual networks, CI) — not the primary path.
- **Re-run `device discover`** whenever the device changes networks or picks
  up a new DHCP lease — the persisted record goes stale with the old address.
  With several Stadiums found, all are persisted and the most recently
  discovered wins by default; pass `--ip` to target another.

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

**`register-irs` and `ir-scan` now COPY each WAV into the library by default.**
Each imported WAV is copied into `library/irs/<pack>/`, a metadata sidecar
`library/irs/<pack>/<name>.json` is scaffolded, and `mapping.json` (now at
`library/irs/mapping.json`, auto-bridged from the legacy location) points at the
copy. `--no-copy` opts out (registers the WAV in place, no sidecar). After a
copy-import, **enrich each sidecar** — see **Enriching IR metadata (sidecars)**
below. Paid IR audio stays gitignored (`library/irs/**/*.wav`), so the copies
are never committed.

### Registering a single IR mid-conversation

If the user names one specific WAV, run `helixgen register-irs <wav>` — it
copies the WAV into `library/irs/<pack>/`, scaffolds a metadata sidecar, points
`library/irs/mapping.json` at the copy, and prints the computed `<hash>  <wav>`
pair (`--no-copy` registers in place without a sidecar). Enrich the new sidecar
per **Enriching IR metadata (sidecars)** below. (To hash without registering
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
This keeps "which IR is beefiest/brightest/best-for-X" answerable by grep. Also
enrich each IR's per-IR sidecar (see **Enriching IR metadata (sidecars)**
below) — same manual mining, written as per-IR JSON in the helixgen home.

## Enriching IR metadata (sidecars)

Every copy-imported IR gets a scaffolded sidecar at
`library/irs/<pack>/<name>.json`. Core fills only `irhash`, `wav`,
`imported_from`, and guesses `mix` from a `Mix NN` filename token; **everything
else is yours to fill.** Enrich each sidecar after importing a pack (via
`register-irs`/`ir-scan`) or after `helixgen library ir-backfill`. Sidecar
(IrMeta) shape:

```json
{
  "schema": 1,
  "irhash": "…",
  "wav": "…",
  "imported_from": "…",
  "pack": null,
  "cab": null,
  "speaker": null,
  "mics": [],
  "mix": null,
  "tags": [],
  "measured": null,
  "notes_md": null
}
```

Procedure (the same `_catalog` mining used in helixgen-core's `irs/_catalog/`):

1. Read the pack's `*Manual*.pdf` for cab/speaker/amp, mic legend, per-mix mic
   combos, and artist/usage notes → fill `cab`, `speaker`, `mics[]`, `mix`,
   `pack`.
2. Fill `tags[]` using **only** the controlled vocabulary (34 tags):
   - tone: `bright dark warm neutral scooped mid-forward beefy tight boomy boxy
     fizzy smooth articulate aggressive airy full chime`
   - gain: `clean edge-of-breakup crunch high-gain`
   - era: `vintage modern`
   - use: `classic-rock blues metal thrash garage fuzz indie lead rhythm stereo
     room`

   (`helixgen library validate` flags off-vocabulary tags as WARNINGS.)
3. *Optionally* compute a 5-band FFT `measured` dict skill-side with stdlib
   `wave` + `numpy` in a **throwaway** script (numpy is allowed in skill-side
   throwaway analysis scripts ONLY — never in shipped code; core leaves
   `measured` null because core is stdlib-only). Bands (provisional): low
   60–200 Hz, low_mid 200–500, mid 500–1200, high_mid 1200–4000, high
   4000–10000.
4. Write the enriched sidecar back to `library/irs/<pack>/<name>.json`.
5. **Cross-check** the controlled-tag vocabulary against the LIVE
   `irs/_catalog/README.md` in the user's helixgen-core checkout as you enrich
   — that README is gitignored, so core can't verify it stayed in sync. If the
   two diverge, note the discrepancy to the user rather than silently picking
   one.

Do **not** commit IR sidecars from this skill — core auto-commits the home repo,
and paid-IR WAVs stay gitignored (`library/irs/**/*.wav`).

## Git-commit IR library changes

**`mapping.json` and IR sidecars now live inside the helixgen home**
(`library/irs/`), which core **auto-commits** — do not hand-commit them from
this skill (and paid IR `.wav`s stay gitignored via `library/irs/**/*.wav`).
The one thing left to hand-commit is the tonal **catalog** in the user's
helixgen-core checkout — `_catalog/<slug>.md` + its `_catalog/README.md` index,
a separate, user-owned repo. If that directory is git-managed, commit just
those files:

1. **Detect per-directory**: `git -C <catalog-dir> rev-parse
   --is-inside-work-tree`. If it errors or prints `false`, skip silently.
2. **Honor `git_commit_tones`** from `preferences.json` (default `"auto"`
   commits whenever step 1 says yes; `"true"` always tries; `"false"` never
   commits).
3. **Respect `guard_paid_irs_in_git`** (default `true`): never `git add` a
   gitignored paid IR `.wav` (see CLAUDE.md's "no paid IRs in repo" note) —
   commit only the `_catalog/*.md` files. If the user has explicitly turned
   `guard_paid_irs_in_git` off and wants a WAV tracked too, that's a deliberate
   `git add -f` they run themselves, not something this skill does for them.
4. **Stage exactly the changed tracked files** (`git -C <catalog-dir> add --
   _catalog/<slug>.md _catalog/README.md`), never `-A`/`.`. Check `git -C
   <catalog-dir> status` first: if the repo already has unrelated staged
   changes, warn the user and skip rather than folding them into the commit.
5. **Commit locally, never push** — `git -C <catalog-dir> commit -m
   "<message>"` with a short message, e.g. `ir: catalog Ownhammer OH V30 pack`.

Keep every git command scoped with `-C <catalog-dir>` (as in step 1) — your
shell's cwd is usually **not** the catalog repo, so an unscoped
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
