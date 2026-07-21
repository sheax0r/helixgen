---
name: device
description: Use when the user wants to put helixgen presets ONTO their Helix Stadium over the network — install a tone, sync a whole setlist of tones to the device, or back up / restore. Drives the `helixgen device` CLI verbs (including the reference-based `device sync <setlist>` / `device sync --all`). Also covers finding the device on the LAN (`device discover`), level-matching loudness across snapshots or a setlist (`device normalize`), and on-device library housekeeping — create/rename/delete/duplicate setlists, delete/rename/prune IRs, preset color + notes. Runs after `tone` has authored the `.hsp` file(s) on disk. Triggers on "put this on my Helix", "sync my library to the device", "install these presets", "find my Helix's IP", "level-match my snapshots", "clean up my IRs", "delete/duplicate a setlist".
---

# device

## Overview

This is the bridge from `.hsp` files **on disk** to **playable presets in a
device setlist**, over the LAN (no editor app). The `setup` and `tone` skills
stop at writing `.hsp`/`.md` to disk; this skill drives the physical Stadium —
install one tone, **sync a whole setlist**, and back up / restore.

## Invoking the CLI

The engine is the `helixgen` CLI, installed as an isolated uv tool (the
`setup` skill's step 0 provisions it: `uv tool install
'helixgen[device]==0.30.0'`). If `helixgen` isn't found or errors with a
traceback, run the setup skill's step 0 — do not improvise an install; if a
stale `helixgen` shadows the uv tool on PATH, invoke
`"$(NO_COLOR=1 uv tool dir --bin)/helixgen"` by absolute path (`NO_COLOR=1`
keeps uv from emitting ANSI inside the substitution under `FORCE_COLOR`;
plain `~/.local/bin/helixgen` is the usual fallback).

Per-invocation environment (prefix each Bash call — exports don't persist):

- **Device address — usually nothing to set (0.24.0).** Every `device` verb
  resolves the Stadium's IP through one chain: `--ip` > `$HELIXGEN_HELIX_IP` >
  the record persisted by `helixgen device discover`
  (`~/.helixgen/devices/<serial>.json`). There is **no built-in default IP**
  any more: with none of the three available, the verb **fails fast with an
  instructive error naming `device discover`** — it never stalls on a wrong
  guessed address. An **empty or whitespace-only `--ip`** (typically an unset
  shell variable that expanded to nothing) is **rejected** at parse time with a
  clear message and a nonzero exit — it is no longer silently treated as unset
  (behavior change, #77); omit the flag to fall back to the record, or pass a
  real address. See **Finding the device** below; `HELIXGEN_HELIX_IP` is
  an override for special cases, not the primary path.
- `HELIXGEN_LIBRARY` — needed by verbs that touch the block library
  (`install`/`sync` transcode `.hsp` content). Same resolution as the other
  skills (see the `setup` skill's "Invoking helixgen"): honor a pre-set env
  var, else a populated `~/.helixgen/library/`, else the plugin's bundled
  `HELIXGEN_LIBRARY="${CLAUDE_PLUGIN_ROOT}/data/library"`. Carrying both
  prefixes on every call is harmless and keeps invocations uniform.
- `HELIXGEN_IRS="<dir>"` — only when the user has a custom IR directory on
  record and you're running an IR-registering fix (`register-irs`,
  `ir-scan`); otherwise the engine defaults to `<library>/irs` — inside
  whatever `HELIXGEN_LIBRARY` points at. Under the bundled-library fallback
  that is the plugin's own `data/library/irs/`, which a `/plugin` update can
  replace — so when registering IRs the user wants to keep, put them under
  `$HELIXGEN_IRS` or somewhere durable and say so (setup skill, step 0).
  (`~/.helixgen/irs/` is the legacy pre-0.26 location, read only to bridge an
  old `mapping.json` up.)
- IR verbs also write the **IR-hash cache** at `~/.helixgen/cache/irhash.json`
  — **regardless of `HELIXGEN_IRS`** (that env var doesn't relocate it). For
  a fully isolated session (tests/sandboxes), since core 0.29.0 setting
  `$HELIXGEN_HOME=<dir>` alone is enough — the cache, the locks and every
  other area follow it. `HELIXGEN_IRHASH_CACHE=<file>` (the single cache
  file), `HELIXGEN_CACHE=<dir>` (the cache directory) and `HELIXGEN_LOCKS=<dir>`
  (the device-lock lease root, see **Device locks** below) remain
  finer-grained overrides. Normal sessions can ignore this.
- `HELIXGEN_LOCK_TOKEN=<token>` — only while holding a **session lease**
  (see **Device locks** below): carry the token printed by `device lock` as
  a prefix on every covered verb, same prefix-per-call mechanism as
  `HELIXGEN_LIBRARY`.

### Where the answers live (consult these FIRST, never the source)

When you need to know *how a verb behaves*, *what a flag does*, or *what a
result means*, read it off the **contract surfaces**, in this order — never by
reading helixgen source (the engine is the uv-tool-installed package, not any
cwd checkout, so source can mislead about the live version):

1. **`helixgen device --help` and each verb's `--help`** — the authoritative
   behavioral contract (args, side effects, read-vs-write, result shape).
   `device --help` carries the device-wide mental models; per-verb `--help`
   carries everything verb-specific.
2. **`device setlist list` + the sync/op results (`--json`)** — live
   device/manifest state and the exact `{ok, pool, references, errors, …}` a
   run returns.
3. **`docs/CLI.md` "Device commands"** — the full per-verb reference (every
   flag, gotcha, and hardware-validation note).
4. **`docs/helix-protocol.md`** — only for wire-level protocol questions.

This is the *resolver pattern* (backlog #14): one authoritative surface per fact,
consulted first, so you never re-derive behavior from source.

## Finding the device: `device discover` (0.24.0)

```bash
helixgen device discover [--timeout N] [--json]
helixgen device discover --forget SERIAL-OR-IP [--json]
```

One-shot discovery: mDNS first (the Stadium advertises
`_stadiumserver._tcp.local.` and answers a one-shot multicast query itself),
then a bounded TCP connect-probe of this machine's **own /24 only** as a
fallback for multicast-blocked networks. Every candidate is confirmed with
the read-only `/ProductInfoGet` handshake before being trusted; confirmed
devices are **persisted** (ip, serial, model, firmware — plus the derived RPC
`port`, recorded **only when the device advertises a nonstandard** stream port,
observed 2001→2002 offset) into `~/.helixgen/devices/<serial>.json`. Read-only
on the device — no lock taken, nothing on the hardware changes.

- **Run it once, then work direct-to-IP.** After one successful discover,
  every device verb resolves the address from the record automatically. This
  is deliberate: the Stadium desktop app's *discovery* layer is known flaky
  while *direct-to-IP* sessions are stable, so helixgen discovers once,
  persists, and never re-discovers mid-session.
- **Re-run it when the device moves** — a new network or a fresh DHCP lease
  makes the persisted record stale (symptom: device verbs suddenly time out
  or can't connect at the recorded address). `device discover` again is the
  fix.
- **Multiple devices: most-recent-wins.** All found devices are listed and
  persisted; the resolver deterministically picks the **most recently
  discovered** (`ip_updated_at` desc, then serial desc) and warns when
  several records disagree. Pass `--ip` on any verb to target another
  device explicitly.
- **Found nothing?** Ask the user for the IP and pass `--ip <addr>` (or
  prefix `HELIXGEN_HELIX_IP=<addr>`) — the override slots above the record
  in the resolution chain.
- **Prune a stale record: `device discover --forget SERIAL-OR-IP`.** Removes
  the persisted `devices/<serial>.json` record whose serial or `ip` matches
  the argument, instead of discovering — use it when a device left the network
  for good. It **never touches the network**, and exits nonzero with a clear
  message (not a traceback) when nothing matches or no records exist yet;
  `--json` emits the removed record paths.
- **Nonstandard port is remembered.** When discovery sees the device advertise
  a nonstandard stream port, `--port` now defaults to the record's persisted
  RPC port (2002 unless nonstandard; the observed 2001→2002 offset) — so a
  nonstandard-port device is reached without re-passing `--port` every verb. An
  explicit `--port` always wins.

## The device model: a preset POOL + reference SETLISTS

The Stadium does not store a preset "inside" a setlist. It keeps a single
**preset pool** (container `-2`) plus named **setlists** (under `-5`) that hold
**references** into the pool. One authored tone lives once in the pool and can
be **referenced by many setlists** at once. Editing a pool preset changes it
everywhere it's referenced; removing a tone from one setlist just drops that
reference — the pool preset (and any other setlist that references it) is
untouched.

helixgen mirrors this with one local manifest, now at
`~/.helixgen/setlists/manifest.json` (override `$HELIXGEN_SETLISTS`; a legacy
v2 manifest at the old top-level location auto-migrates up on first load,
backup written first — nothing for you to do) — the **tone library**. Each
tone is a record (content `.hsp` + name + management **intent**): a desired
**user slot** (`null` = off device, `"auto"`, or `"1A".."128D"` — the slot
vocabulary runs to bank 128, not just bank 8, but it is **manifest-only**:
since core 0.30.0 `device add --slot` accepts only `auto` and **rejects** an
explicit label, because `device sync` never converted a recorded label into a
device address (it installs at the lowest empty slot regardless; backlog #30) —
place with `auto`, then move it with `device reorder`),
ordered **setlist memberships**, and provenance `source`. Manifest v3 is **intent-only** (desired slot + setlist memberships). A specific
Helix's **observed** placement (`cid`/`posi`) is deliberately NOT in the manifest
(manifest v3, 0.22.0) — it lives per device serial (the `serial` from `device
info`'s `/ProductInfoGet`) at `~/.helixgen/devices/<serial>.json`, **not
committed** (`devices/` is gitignored), and its placement observations are
rebuilt wholesale by every `device sync` (and the first sync after a v2→v3
migration harmlessly re-pushes placement for every managed tone). Since 0.24.0
the same `devices/<serial>.json` also carries the device's discovered **address**
record (`ip`, `ip_updated_at`, `model`, `firmware`, plus `port` — the derived RPC
port, present **only when nonstandard**; absent means the default 2002), written
by `device discover` and round-tripped through sync rebuilds — so losing the file costs only one
re-`discover` (placement rebuilds on the next sync). **"On the device" ⟺ the tone has a
slot.** There is
**no separate slot ledger** — this one manifest is the single management-intent
record for "which of my tones goes where." Every generated tone
**auto-registers** here (off-device by default); `device add`/`unsync` set the
slot; `device sync` is a **managed-set mirror** (installs/updates/reorders/
deletes only helixgen-managed tones, never touches untracked device presets).
**Never hand-edit it** — manage it through the `register` / `device add` /
`device unsync` / `device setlist` verbs, or the `tone` skill. (The engine
also auto-git-commits manifest saves inside `~/.helixgen` — its own home git
repo, gated by the `git_commit_tones` preference; that's engine behavior, not
something this skill drives.)

## Device locks (0.22.0) — auto-acquired, advisory, machine-local

Every device-**mutating** verb auto-acquires a machine-local advisory lease
for its duration (lease files at `~/.helixgen/locks/<device-ip>/<scope>.lock`;
root override `$HELIXGEN_LOCKS`), so concurrent helixgen processes on this
machine never collide on the device. **The guarantee assumes every client is
≥0.22.0** — locking arrived in that version, and an older `helixgen` on this
machine takes no lease and ignores existing ones, so it collides as if locks
didn't exist. If anything other than the pinned uv tool might be driving the
device, don't rely on locks for parallelism. Read-only verbs take nothing; you don't
lock anything by hand for a single verb — it's automatic. Scopes are granular
and non-conflicting with each other: `editbuffer` (live-ops on the ACTIVE
tone: `load`/`snapshot`/`bypass`/`model`/`set-param` — plus `normalize`,
which recalls snapshots / loads presets while measuring and so holds this
scope **even in its dry-run**), `library`
(pool/setlist/content writes, incl. `install` and `setlist import-hss`),
`irs` (device IR writes: `push-ir`/`delete-ir`/`rename-ir`/`ir-prune --yes`),
`globals` (`settings set`/`globaleq set`), `all` (exclusive). Two verbs take
`library`+`irs` together: `sync` (`--exclude-irs` drops `irs`) and
`install --auto-irs` (it uploads device IRs; plain `install` is `library`
only). Full verb → scope table: `docs/CLI.md` "Device locks".

**When a verb blocks, then fails naming a holder.** On contention a verb
waits up to `$HELIXGEN_LOCK_TIMEOUT` seconds (default **30**; `0` = fail
fast), then exits non-zero **naming the holder** (label, pid, host, age).
That error means another agent/process on this machine holds the scope. The
right response is to **wait and retry, or coordinate** with whatever the
label names — it is not a malfunction, and it is **not** a reason for
`--no-lock`. Stale leases (expired TTL / dead pid) self-reclaim on the next
acquire; a live lease is never broken implicitly.

**Session leases for long multi-verb flows.** A full setlist sync session,
bulk IR housekeeping, or any flow of several mutating verbs should hold its
scope(s) across calls instead of re-contending per verb:

```bash
helixgen device lock --scope library --scope irs --label "setlist sync: Gigs" --ttl 900
# prints HELIXGEN_LOCK_TOKEN=<token> — carry it on every covered verb:
HELIXGEN_LOCK_TOKEN=<token> helixgen device sync Gigs --json   # IP resolves from the discover record
# ... more verbs, same prefix ...
HELIXGEN_LOCK_TOKEN=<token> helixgen device unlock   # release at the end — token REQUIRED here too
```

- **Always pass a descriptive `--label`** — it's what other agents/users see
  when they hit your lease.
- **Carry the printed `HELIXGEN_LOCK_TOKEN` as an env prefix on every covered
  call — including the final `device unlock`.** Same-shell pid passthrough
  won't help you: each of an agent's Bash calls is a fresh shell/pid, so the
  exported token is the only reliable ownership proof (same prefix-per-call
  mechanism as `HELIXGEN_LIBRARY`). A bare `device unlock` from a later shell
  releases nothing (it reports your lease as foreign and keeps it).
- **Renewal — not `--ttl` — is what keeps the lease yours.** The
  lock-issuing shell's pid dies as soon as the call returns, and a dead-pid
  session lease is reclaimable by contenders after **120 s idle** (measured
  from its last acquisition/renewal) — `--ttl` caps the lease's lifetime, it
  does NOT extend that grace. Every token-carrying covered verb renews the
  lease, so a flow that keeps working stays covered; avoid idle gaps longer
  than ~2 minutes mid-flow, and after one, re-run the same `device lock`
  (idempotent renewal of your own scope) before the next mutating verb.
- **Token-prefixed `device unlock` when the flow ends — including failure
  paths.** Don't leave a lease to expire on its own when you can release it.
  Plain `device unlock` (with the token) releases all your leases; `--scope`
  narrows it.
- **Inspect with `helixgen device lock --status --json`** — every lease's
  scope, label, pid, host, age, TTL, live/stale, and whether it's yours.
  Read-only, always safe.

**Never pass `--no-lock` unless the user explicitly directs it.** It opts
that verb out of collision protection entirely. Likewise `device unlock
--force` breaks a live lease someone else is using — coordinate instead.

Limitations (by design): **advisory** — nothing stops a `--no-lock` caller —
and **machine-local** — direct-protocol clients on other hosts and the
Stadium desktop editor are NOT covered.

## How a tone becomes a device preset: the transcoder (no template)

helixgen installs a tone by **transcoding** its `.hsp` straight into the
device's native content format (`_sbepgsm`) and writing that into an empty pool
slot. The `.hsp` **is** a complete Line 6 preset; the transcoder just
re-serializes it — models, params, and IR references — into the on-device
encoding. **There is no template, no slot skeleton, and no coverage
precondition.** Any block chain installs at full fidelity; you never pick a
`--template` and never worry about whether some factory preset "has a
compressor slot."

The transcoder synthesizes the **full signal graph** onto the device's real
28-slot grid: serial chains, **dual-amp / dual-DSP**, **intra-flow parallel
splits**, **snapshots** (per-scene bypass + param deltas), and **footswitch/EXP
assignments** all transcode faithfully (hardware-validated byte-for-byte vs HX
Edit's own import). There is no serial-only limit any more.

## The default path: manage membership, then `device sync <setlist>`

For "get my tones onto the Helix":

1. **Make sure each tone is in a setlist** (in the manifest) — `device setlist
   add <setlist> <tone.hsp>` (the `tone` skill may have done this already).
2. **Make sure the setlist exists on the device.** If it doesn't, create it
   right there: `helixgen device setlist create <name>` — device-side creation
   shipped (#8); no Stadium app needed. The sync's missing-setlist error names
   this verb too.
3. **Sync:** `helixgen device sync <setlist> [--json]` for one setlist, or
   `device sync --all` for the whole manifest. The engine reconciles the
   **pool first** (install missing / update changed / skip unchanged —
   idempotent by content hash), then **rebuilds that setlist's references** to
   match manifest order. The result is the engine dict
   `{ok, setlists, pool, references, gc, irs, errors}`.

**Not a destructive mirror.** Unlike the retired directory-mirror sync, this
never wipes a setlist. It adds/updates only the pool presets the sync needs and
adds/removes/reorders only the references for the setlists being synced. It
**never orphans** a pool preset that another setlist still references. Pool
garbage-collection happens **only** on `device sync --all --gc`, and even then
only deletes pool presets that **no** manifest setlist references.

**The sync run IS your analysis.** You don't study the tones or the device to
predict what will fit — you run the sync and read `errors[]`, which names exactly
which tones failed and why. Fix that subset, re-run (re-syncing skips the tones
that already installed — it's idempotent), and waste zero work on tones that
install fine.

**Do NOT front-load analysis before the first sync.** Everything you'd "analyze"
is either done for you or reported by `errors[]`. Concretely:

- **Never read or parse `.hsp` bytes** (no `json.loads` on the file, no
  magic-stripping script). If you ever need a tone's contents, use
  `helixgen view` — but you do **not** need it before a sync.
- **Do not `view` every tone up front** to bucket them. Run the sync;
  `errors[]` is the only bucket that matters (the tones that didn't fit).

## When the device gets flaky — re-run, then reboot

The Helix Stadium's network stack drops connections intermittently — a sync may
fail partway or the device may stop responding mid-run. This is expected and the
sync is built for it: it **auto-reconnects (bounded)** on a dropped RPC and is
**idempotent**, so:

> **If a sync fails or the device stops responding, just re-run the exact same
> sync.** Tones already in the pool are skipped, so a re-run picks up where it
> left off and converges. **If it keeps dropping across several re-runs, tell
> the user to REBOOT the Helix** (power-cycle / restart it) — that reliably
> clears the wedged network stack. Then re-run the sync once more.

Don't treat a dropped connection as a tone failure or start diagnosing the
protocol — re-run first, reboot second.

## When to use

- User wants authored preset(s) **on the device** ("put White Limo on my Helix",
  "sync my tone library to the Stadium", "load these onto the device").
- User wants to **back up** or **restore** device slots.
- A generated preset "isn't loading on the device" and you need to (re)install it.

When NOT to use:
- Designing or editing a tone — that's `tone` / the surgical-edit verbs. Author
  the `.hsp` first, then come here to push it.
- Read-only device questions ("what's on my Helix?") — just run
  `helixgen device list` / `device setlists` directly.

## Red flags — STOP, you are going off the rails

If you catch yourself doing any of these **before running the sync**, stop and
just run it:

- Writing a script that reads/parses `.hsp` files (`open(...).read()`,
  `json.loads`, stripping the `rpshnosj` magic). **Never parse `.hsp` bytes.**
- Running `helixgen view` on many/all tones to classify them.
- Listing, reading, or loading factory presets "to find a template" or "to check
  coverage" — **there are no templates anymore** (the transcoder is
  template-free); this is pure wasted work.
- Building Simple/Rich/Quarantine buckets, or a per-tone install plan.
- Reading helixgen source to predict a verb's behavior instead of its `--help`.
- Diagnosing a dropped connection instead of just re-running (then rebooting).

All of these mean: **you are predicting failures you should be reading.** Run the
sync; its `errors[]` is the analysis, and it costs one call.

## Why a tone lands in `errors[]`

You don't need this to run the first sync — it's how you *read the results*.
Because install is a faithful, template-free transcode, most tones just install.
A tone lands in `errors[]` for one of a small, concrete set of reasons:

- **`could not resolve helixgen model 'X'`** — a block model has no device
  equivalent in the bridge. That tone isn't installable as-is; report it.
- **unregistered IR** (cab silent / "No Model" after install) — the referenced
  IR isn't on the device and isn't in your local `mapping.json`, so it can't be
  uploaded. `register-irs` the WAV (or import it in HX Edit), then re-sync.
- **dropped connection / device unresponsive** — not a tone failure at all; the
  flaky network stack. Re-run the sync; reboot the Helix if it persists.

(Dual-amp, parallel splits, snapshots, and footswitch/EXP assignments all
synthesize faithfully as of 2.18.0 — no quarantine needed.)

## The tools

### Manage setlist membership (local manifest)

```bash
helixgen device setlist list                       # setlists + their tones
helixgen device setlist add <setlist> <tone.hsp>   # append a tone (auto-creates the setlist locally)
helixgen device setlist add <setlist> <tone.hsp> --pos N   # insert at position N
helixgen device setlist remove <setlist> "<tone name>"     # drop membership (keeps the tone if other setlists use it)
helixgen device setlist create-local <setlist>     # empty setlist in the manifest only
```

- These touch only the local manifest (`~/.helixgen/setlists/manifest.json`)
  — no device, no lock. A tone's identity is
  its **display name** (`meta.name`). **The same tone can be in as many setlists
  as you want** — it's referenced once in the device pool and shared — so adding
  a tone that's already in another setlist is expected, and re-adding within one
  setlist is a harmless no-op. `add` only errors when a name is already
  registered to a *different* `.hsp` file (names must be unique). You never need
  to pre-check membership or read the manifest to add safely.
- `create-local` (and `add` auto-creating a setlist) only add it to the
  *manifest*. To also create it **on the device**, run `device setlist create
  <name>` (#8 shipped) — then `sync` can push to it.

### Device-side setlist management (create / rename / delete / duplicate)

```bash
helixgen device setlist create <name>          # new empty setlist ON the device
helixgen device setlist rename <old> <new>     # device + local manifest record
helixgen device setlist delete <name> --yes    # references die; pool presets NEVER deleted
helixgen device setlist duplicate <src> <dst>  # copies references; auto-creates <dst>
```

- **Delete never orphans:** removing a setlist kills only its references —
  every pool preset stays, still available to other setlists. Confirm with the
  user before a delete (no undo).
- **Duplicate shares, it doesn't copy:** both setlists reference the same pool
  presets, so editing a tone changes it in both.

### Importing / exporting a `.hss` setlist-bundle (EXPERIMENTAL)

```bash
helixgen device setlist import-hss export.hss --list          # offline: what's inside? (shows payload format)
helixgen device setlist import-hss export.hss --dry-run       # preview the device write
helixgen device setlist import-hss export.hss                 # install + reference into a setlist
helixgen device setlist import-hss export.hss --setlist Gigs  # override the destination setlist name
helixgen device setlist export-hss Gigs out.hss               # export a DEVICE setlist to a .hss bundle
```

- A `.hss` is the Stadium **app's** "export setlist" file — a different input
  than anything else this skill covers (not an authored `.hsp`, though a filled
  slot **embeds** one). `--list` is always safe to run first (fully offline);
  it now shows each filled slot's payload format (`hsp`/`sbepgsm`) and the
  preset name (read from the embedded `.hsp`'s `meta.name`). The write path
  **transcodes** each filled slot's `.hsp` to device content, installs it into
  the pool, and references it into a device setlist (created if absent) in
  bundle order. Imported presets **are recorded in the tone library** as
  *pathless* tones (source `import-hss`) with membership in the destination
  setlist — that record is what keeps a later `device sync <setlist>` from
  stripping the imported references. Having no local `.hsp`, they can't be
  restored by `device slots restore`. Flip side: if the destination setlist
  held references helixgen does NOT track, a later targeted `device sync
  <setlist>` will strip those untracked references — inherent managed-mirror
  semantics; prefer importing into a fresh setlist when the destination has
  untracked members you want to keep.
- **NOT idempotent on retry.** Re-running an import after a partial failure
  installs + references the already-succeeded slots AGAIN (duplicate pool
  presets + references). Before retrying, delete the setlist and the
  orphaned pool presets — or import into a fresh setlist. (Dedupe-on-retry
  is future work; backlog #31.)
- **`export-hss`** builds a `.hss` from a device setlist, embedding each
  referenced preset's **local `.hsp`** (resolved by preset name via the tone
  library) — mirroring how the app embeds a `.hsp` per preset. A referenced
  preset with **no local `.hsp`** (device-born / untracked) is **skipped**
  with a warning: helixgen has no device-content → `.hsp` converter (backlog
  #31 residual), so only tones the tone library backs export. The container
  framing (header, gzip header, ustar layout) is byte-faithful to a real app
  export; two benign envelope differences remain — the gzip DEFLATE stream
  (non-zlib app encoder) and compact vs pretty `.hsp` JSON (helixgen embeds
  compact; both re-import fine).

### IR maintenance (delete / rename / prune) + preset info

```bash
helixgen device list-irs [--json]                    # IRs ON the device; --json rows include `file`
helixgen device pull-ir <file-basename> <out.wav>    # download an IR by its on-device file basename
helixgen device delete-ir <name-or-hash> --yes       # registry entry + backing .wav
helixgen device rename-ir <name-or-hash> <new-name>  # display name only; hash keeps resolving
helixgen device ir-prune                             # DRY-RUN report: referenced / protected / orphans
helixgen device ir-prune --yes [--force] [--ignore-warnings] [--only <name-or-hash>]
helixgen device set-info <cid>... --color green --notes "..."   # batch color + notes
```

- **`pull-ir` takes the on-device `.wav` file basename, not the display
  name** — discover it via `device list-irs --json`, whose rows include
  `file` (0.21.0). `rename-ir` changes the *display* name only, so a renamed
  IR still downloads under its original upload basename (and its hash keeps
  resolving in presets).
- **`ir-prune` is dry-run by default.** Always run the dry-run first and show
  the user the `orphans` / `protected` lists — and any `warnings` (local
  tones whose recorded `.hsp` couldn't be read) — before executing.
  `protected` IRs are referenced by local off-device tones — they need
  `--force` and a deliberate user choice. Proceeding despite `warnings` is a
  **separate** consent, `--ignore-warnings` (don't reach for `--force` for
  that). A prune that aborts naming a **dangling** setlist reference means a
  setlist still points at a deleted preset — re-sync that setlist (or drop the
  entry) and retry.
- An IR referenced by any preset ON the device (or by the live edit buffer)
  is never a prune candidate. Execute mode re-verifies the plan right before
  deleting and aborts if the device listings changed — just re-run.
- **`delete-ir --force-wedge`** exists only for the wedged file-only state (a
  hash whose file still resolves but has no registry entry, after a delete →
  quick re-import). Never use it on an IR you just imported — the listing may
  merely be lagging. If a plain delete-ir errors suggesting the flag, wait a
  minute and retry without it first.
- `set-info` colors: `auto, white, red, dark orange, light orange, yellow,
  green, turquoise, blue, violet, pink, off` (or a raw index 0-11). Notes are
  written without activating the preset.

### Sync a setlist onto the device (pool + references)

```bash
helixgen device sync <setlist> [--exclude-irs] [--repush] [--no-progress] [--json]
helixgen device sync --all [--gc] [--exclude-irs] [--repush] [--no-progress] [--json]
```

- **Resolves the setlist by name** under `-5`. If the device doesn't have it,
  the run errors clearly, naming the fix: `helixgen device setlist create
  '<name>'`, then re-sync.
- **Pool-first, idempotent:** installs tones missing from the pool (transcoded,
  template-free), re-pushes ones whose `.hsp` content hash changed — the hash is
  **recomputed from the file at sync time**, so an in-place edit to an
  already-synced tone is detected — and skips unchanged ones.
- **Rebuilds references:** adds/removes/reorders the setlist's references to
  match manifest order — **never orphaning** a pool preset another setlist still
  references.
- **Uploads each tone's referenced IRs first** (instant `push_ir`) unless
  `--exclude-irs`, so cabs resolve immediately.
- **`--gc` (only with `--all`)** deletes pool presets that no manifest setlist
  references any more. A single-setlist sync never garbage-collects.
- **`--repush`** forces a content refresh of every in-scope tone already in the
  pool, even when its `.hsp` bytes are unchanged since the last sync (same
  non-activating existing-cid update path as a normal hash-triggered update).
  Because plain sync recomputes the file hash at sync time it **already**
  re-pushes genuinely edited `.hsp` files, so `--repush` is **only** for the
  unchanged-bytes case: **after a helixgen transcoder upgrade**,
  `device sync <setlist> --repush` refreshes device content that a plain sync
  would skip as unchanged — a byte-hash comparison can't see a
  transcoder-output difference for an unchanged `.hsp`.
- **Progress output goes to stderr, not stdout.** Sync shows a live display —
  a progress bar when stderr is a TTY, plain text otherwise, which is what an
  agent Bash call sees. **The plain form is one line per *item*, not per
  phase**: a `sync: <phase> (<n>)` header, then `  <phase> <i>/<n>: <label>`
  for every tone, plus `  uploading IR <i>/<n>: <label>` per IR. A 40-tone
  setlist is ~100 stderr lines — expect a wall of them, not a handful. It is
  **not** warnings or errors; don't read it as failure. `--no-progress` only
  forces the plain form — it does **not** silence the per-item lines, and it
  is a no-op for an agent Bash call, which is already non-TTY and therefore
  already plain. stdout (the summary) and `--json` are never affected, so
  parsing is unchanged either way.
- **Per-tone failures are collected and never abort the run.** Result:
  `{ok, setlists, pool:{installed,updated,skipped}, references:{added,removed},
  gc:{deleted}, irs:[…], errors:[…]}`. Read `errors`.

> **Heads-up after a manifest v2→v3 migration:** the migration splits per-device
> observed placement out into `devices/<serial>.json`, so the **first `device
> sync` after migrating re-pushes every managed tone once** — the device's real
> serial hasn't observed anything yet under its own file, so sync treats the
> whole managed set as needing a placement refresh. This is harmless and
> idempotent; don't be alarmed by the one-time full re-push.

> The old directory-mirror `device sync [dir]` is **gone**. Sync is now
> manifest- and setlist-driven; membership is managed with `device setlist`,
> not by globbing a directory.

### Single tone — `device install`

Use for one-off placement into a chosen pool slot:

```bash
helixgen device install <hsp> <name> --pos N --auto-irs
```

It records the tone library too. **Pass `--auto-irs`** (opt-in flag) so the
tone's referenced IRs are uploaded with it — without it, an IR the device
doesn't have leaves the cab silent ("No Model"). It shares the same per-tone
IR-upload core `device sync` uses, so behavior (resolve via `mapping.json`,
`push_ir`, verify the registered hash) is identical across paths. Note the
CLI aborts the install if an IR upload hard-fails (it never installs a preset
whose IR couldn't be pushed).

Reserve the other `device` verbs for reads / interactive single ops
(`device list`, `device read`, `device load`, and the live ops below).

### Targeting a setlist by name (`--setlist`, 0.21.0)

Every preset verb that takes `--setlist` — `device list` / `backup` /
`create` / `save` / `push` / `install` / `delete` / `slots restore` — accepts
`user` (the preset **pool**, the default), `factory` (read-only), or a **real
device setlist display name, case-insensitive** (e.g. `--setlist Gigs`) — the
same names `device reorder` / `device sync` already took. With a named
setlist, read verbs operate on that setlist's **references**, and write verbs
put the preset content in the pool and add a reference at `--pos`. (There is
no special `throwaway` token — target a real setlist by its name.)

### Live ops on the ACTIVE tone (blocks / params / bypass / model / set-param)

For interactive, immediately-audible tweaks to whatever tone is live on the
device. These edit the **live edit buffer** — audible at once, volatile (not
written to the preset until saved):

```bash
helixgen device blocks [--json]                  # edit buffer's blocks + their (path, block) coordinates
helixgen device params <path> <block> [--json]   # one block's params: pid, name, CURRENT raw value, type, range
helixgen device bypass <path> <block> <on|off>   # bypass/enable a block live
helixgen device model <path> <block> <model>     # swap a block's model live (same category only)
helixgen device set-param <path> <block> <pid> <value>   # set one param live (value in RAW units)
```

- **Block coordinates are the DSP grid slot exactly as `device blocks` prints
  them** — pass them to `bypass`/`model`/`set-param`/`params` **unchanged**.
  The grid is 0–27 and **not necessarily contiguous** (output blocks sit at
  slots 13/27), so never derive a coordinate from a block's list position —
  the pre-0.21.0 computed-index translation rule is dead (see the CLI.md
  live-ops erratum). An op at
  a slot holding no block is *silently* ineffective (a `set-param` write is
  dropped with no ack; a bypass toggle may still echo) — an echo is not
  proof an op landed; read back with `device params` or watch
  `device meters`.
- **Discover pids with `device params <path> <block>` — never guess.** It
  lists each param's numeric pid, name, current value, type, and range.
- **Param values are in RAW units** — dB, Hz, 0–1 knob positions, enum ints,
  exactly as `device params` reports them — **not** normalized 0–1.
- **Live ops hit whatever preset the player has ACTIVE.** Before mutating,
  read `helixgen device active [--json]` — the device's active preset (cid +
  name + pool slot; it tracks the player's own panel selection too). When
  the work is done (or if the session loads other presets via
  `device load`/install/sync), restore the player's selection with
  `device load <cid>` using the cid you noted.

### Loudness: `device measure` (0.22.0) + `device normalize` (0.23.0; library recording 0.26.0, loop source 0.27.0)

```bash
helixgen device measure [--seconds N] [--min-playing N] [--source input|loop] [--json]   # read-only
helixgen device normalize <preset.hsp> [--json]                      # snapshot scope, DRY-RUN
helixgen device normalize --setlist <name> [--json]                  # setlist scope, DRY-RUN
helixgen device normalize <preset.hsp> --yes                         # write trims to the LOCAL .hsp
```

`device measure` (read-only) reduces playing-gated telemetry to robust dB
stats while the player plays — the input-invariant **chain gain** is the
number to compare across snapshots/presets. `device normalize` is the closed
loop built on it: it recalls each target (each NAMED snapshot of a local
`.hsp`, or each tone of a manifest setlist), prompts the player to play per
target, and computes the dB trim that equalizes each target's **total
loudness** (measured chain gain + the output-block level already in force)
against the anchor — the first target that measured ok — or an absolute
`--target-db`. Trimming totals makes re-runs idempotent (in-band zero trims,
no compounding). The essentials:

- **DRY-RUN by default — always run and show the dry-run report first.**
  Measuring happens either way, but without `--yes` trims are only reported.
  Treat `--yes` as a separate, deliberate step after the user has seen the
  proposed trims.
- **`--yes` writes the LOCAL `.hsp` file(s) only — never the device copy.**
  Trims land as output-block `level` moves in the local source of truth:
  per-snapshot overrides in snapshot scope, a whole-preset uniform shift
  (base + any per-snapshot array, preserving the preset's internal balance)
  in setlist scope. **The device follows on the next `device sync <setlist>`
  / `device install`** — a normalize run without a follow-up sync changes
  nothing audible on the hardware.
- **Snapshot scope requires the ACTIVE device tone to BE that preset** —
  sync/install it and leave it active first. The active preset's name is
  verified before anything is measured; a mismatch aborts (an unverifiable
  name only warns). Setlist scope loads each tone by its observed CID and
  verifies the name — a mismatch means a stale observation and that tone is
  SKIPPED.
- **Skipped targets** (too little playing, no local `.hsp`, no observed
  placement, name mismatch) get a warning and the run **exits 1** to flag
  the partial result — re-run for the stragglers; already-written files
  re-measure in band.
- **`--source loop` (0.27.0) — measuring off a front-of-chain looper.** When
  a looper replays a recorded signal instead of live playing, the input-jack
  gate reads pure silence (no pitch, no input level — every sample would gate
  out), so loop mode gates on **chain-out level** instead. With no input
  reference, `gain_db` comes back `null` — the number to compare across
  targets is the raw **`output_db`** (the looped source is identical across
  targets by construction, so output-level differences ARE the chain
  differences). Works on both `measure` and `normalize`; keep the SAME loop
  replaying across every target of a run. Idempotency is unchanged (the
  meter taps sit upstream of the trims either way).
- **An unreachable device fails fast (0.27.0).** `measure` — like `device
  tuner`/`device meters` — preflights reachability with one cheap TCP probe
  of the `--port` control port before streaming (the `--port` flag is
  honored now): a powered-off/unreachable device errors immediately instead
  of streaming silence for the whole window and ending in "no meter data".
- **Don't re-measure to "confirm" a trim.** The meter taps sit UPSTREAM of
  the output-block gain, so a written trim is invisible to `device measure`
  by design — the loop trusts the dB math (the output `level` is dB-native,
  so each trim is exact). A confirmation re-measure would falsely report
  "no change".
- It holds the `editbuffer` lock even in dry-run (it recalls snapshots /
  loads presets while measuring), and it changes the device's ACTIVE tone
  selection during the run (restored best-effort afterwards).
- **`--yes` also records the run on the tone's library metadata (0.26.0).**
  When the written `.hsp` is a registered tone-library variant, the run is
  written onto that variant as a `normalized` record carrying the full
  per-target measurement telemetry (exactly what this verb's `--json`
  reports — `gain_db`, `output_db`, `total_db`, `trim_db`, `applied`, …;
  the verb's `--json` lists the recorded variants under `library_recorded`).
  Human summaries surface in `helixgen describe <tone>` and
  `helixgen library show <name>`; the full telemetry is under
  `helixgen library show <name> --json`. Latest run wins (records
  overwrite); in-band zero-trim runs still record (they confirm the tone
  measures level-matched); dry-runs and non-library `.hsp` files never
  touch metadata. Note: a snapshot-scope `--yes` run with ANY skipped
  target records NO library metadata even though the ok targets' trims
  ARE written to the `.hsp` — re-run cleanly to get the record.

#### Running normalize well — field-proven guidance (live hardware, 2026-07-16)

How to brief the player and pick the flags; all of this is validated on real
hardware:

- **One riff, played steadily, through the whole run.** The player plays the
  SAME riff at the same intensity for the entire run; each target is
  measured for roughly one window, the snapshot recalls / preset loads
  between windows happen automatically, and the preset's prior state is
  restored when the run ends. The player's only job is to keep playing.
- **`--seconds 10` suffices in practice** — the default 20 is conservative.
  The playing gate needs **pitched, steady playing** (roughly 4 s of
  credited playing per window minimum); muted scratching, noodling pauses,
  or silence don't credit the gate.
- **Cross-tone level matching: ALWAYS pass an explicit absolute
  `--target-db`.** The default anchor (the first target that measures ok)
  equalizes **within that scope only** — separate runs won't land on a
  common level — and on snapshot scope the anchor can drag the whole preset
  down to its quietest snapshot's level. Pick one absolute target and reuse
  it on every preset/setlist that should sit level with the others.
- **A clean chain caps the reachable target.** The output-block `level` maxes
  out at **+20 dB**, so a target above `chain gain + 20` is unreachable —
  e.g. a clean snapshot measuring −13 dB chain gain tops out at a total of
  ≈ +7. Pick the target at or below the **quietest chain's ceiling** (the
  dry-run report shows every target's measured gain — read it before
  choosing `--target-db`).
- **Chain-out `output_db` over 0 dBFS in the results = in-chain clipping
  that normalize CANNOT fix** — its trim is applied downstream of the meter
  taps. Don't chase it with level moves: flag it to the user as a
  **gain-staging problem inside the chain** (amp/drive levels — the `tone`
  skill's territory), then normalize again once the chain is clean.
- **Re-runs are idempotent** (total-loudness math + the tolerance dead-band):
  re-running with a different `--target-db` is safe — trims move to the new
  target and **nothing compounds**.

> **WARNING — the follow-up `device sync` is a whole-managed-pool mirror.**
> The sync that pushes your trims re-pushes **EVERY** manifest-known tone in
> its scope whose **content hash differs** — not just the ones you just
> normalized — and a re-push **overwrites hardware-side edits** that were
> **never pulled back** into the local `.hsp`. Before the post-normalize
> sync, ask/warn the user if they've been editing tones on the device
> itself.

**Manual per-snapshot counterpart.** Hand-balancing without the closed loop
is the local edit verb, not a device verb: `helixgen set-param <preset.hsp>
output level --snapshot <name-or-index> -- -3` (0.23.0; `--snapshot` also
works on library-block params and on `enable`/`disable`). Same rule applies:
it edits the local `.hsp`; the device follows on the next sync/install. Once
a param carries per-snapshot overrides, a later plain base edit of it is
inaudible on-device (`set-param` warns) — keep editing per-snapshot.

### Git-commit local artifact changes

Most of this skill only talks to the device, but two paths write **local**
files: registering an IR to fix an `errors[]`/`irs[]` unregistered-IR entry
(changes `mapping.json` in the IR library) and `device slots restore`
re-authoring a tone's `.hsp` in the preset output dir. When either happens,
commit the changed file(s) if the containing directory is git-managed:

1. **Detect per-directory** — `git -C <dir> rev-parse --is-inside-work-tree`
   on the specific directory that changed (IR library or preset output dir),
   not whatever repo you happen to be running in. Skip silently if it errors
   or prints `false`.
2. **Honor `git_commit_tones`** from `preferences.json` (`"auto"`/`"true"`/
   `"false"` — same vocabulary as the `tone`/`setup` skills; default `"auto"`
   commits whenever step 1 says yes).
3. **Respect `guard_paid_irs_in_git`** — never force-add a gitignored paid IR
   `.wav`; commit `mapping.json` only.
4. **Stage exactly the changed path(s)** — `git -C <dir> add -- <changed
   files>`, never `-A`/`.`. Check `git -C <dir> status` first: if the repo
   already has unrelated staged changes, warn the user and skip.
5. **Commit locally, never push** — `git -C <dir> commit -m "<message>"` with
   a short message, e.g. `ir: register missing IR for White Limo Lead sync`
   or `device: refresh restored tone <name>.hsp`.

Keep every git command scoped with `-C <dir>` (as in step 1) — your shell's
cwd is usually **not** the directory that changed, so an unscoped
`git add`/`commit` targets the wrong repo.

This is separate from `device sync` itself, which only ever touches the
device — it applies just to these two local-write side paths.

## Workflow

### 1. Get the tones into a setlist, confirm it exists on the device

1. **Membership:** for each tone the user wants, `device setlist add <setlist>
   <tone.hsp>` (skip any the `tone` skill already added). `device setlist list`
   shows the current membership.
2. **Device-side setlist:** if the target setlist isn't already on the Stadium,
   create it right from here: `helixgen device setlist create <name>` (#8
   shipped — no Stadium app needed). Syncing an existing setlist like a
   factory `user` setlist needs no creation step.

### 2. Sync

```bash
helixgen device sync <setlist> --json
```

A single sync locks itself (auto-acquired `library`+`irs` lease — see
**Device locks**). If this is a longer session — several setlists, sync plus
IR housekeeping, expected re-runs — take a session lease first (`device lock
--scope library --scope irs --label "<what>" --ttl 900`), carry the printed
`HELIXGEN_LOCK_TOKEN` on every verb, and release with a token-prefixed
`device unlock` when done.

The engine reconciles the pool (install/update/skip), rebuilds the setlist's
references in manifest order, and uploads each tone's IRs. **Order comes from the
manifest** — `device setlist add --pos` / the manifest order sets it; a later
sync will reorder the device right back to that recorded order. For a direct,
immediate device-side move that bypasses the manifest entirely — e.g. reordering
an *untracked* preset, or a quick one-off nudge you don't want `sync` to
remember — use `helixgen device reorder <setlist> <target> --to <N>` instead.

### 3. Read the result, fix `errors[]`, re-run

The result dict's `errors[]` is your analysis. Fix that subset and re-run
(re-syncing is idempotent — installed tones are skipped):

- **`could not resolve helixgen model 'X'`** — a block model doesn't bridge to
  the device; that tone isn't installable as-is. Report it.
- **unregistered IR** (cab silent / "No Model") — `register-irs` the WAV, re-sync (see **Git-commit local artifact changes** above).
- **dropped connection / device unresponsive** — not a tone failure; **re-run**
  the sync, and if it keeps dropping, **reboot the Helix** and re-run.
- **If you delegate the run to a subagent, keep it tight:** sync *this* setlist;
  report `pool`/`references`/`errors` verbatim; no improvising. Then check the
  device yourself.

### 4. IRs — usually automatic

`device sync` uploads each tone's referenced IRs first (instant registration
under the tone's exact hash), so **you normally do nothing**. Two caveats:

- An IR that isn't in your local `mapping.json` can't be resolved — it shows up
  as a per-IR note in the result (`irs[]`) and the cab will be silent. Register it
  first (`helixgen register-irs`) or import it in HX Edit, then re-sync.
- `--exclude-irs` skips IR upload entirely (use only if the IRs are already known
  to be on the device and you want a faster run).

### 5. Back up / restore

- **Back up the pool or a named setlist:** `helixgen device backup
  [--setlist <user|factory|NAME>]` pulls the pool (`user`, default) — or the
  presets a named device setlist references, in setlist order — to local
  `.sbe` files + `manifest.json` (then works offline via `device local-list`).
- **Put a recorded tone back:** `helixgen device slots restore <name-or-slot>` —
  re-authors an `.hsp`-sourced entry or re-pushes an `.sbe`-sourced one
  (`--setlist` takes `user`/`factory`/a device setlist name here too). Tones
  recorded from `save` (edit buffer) or `create` (on-device copy) have no local
  source and can't be restored this way — back them up first. `--force` pushes
  into an occupied **pool** slot (the occupant is not deleted), but an occupied
  **named-setlist** position is refused even with `--force` (0.27.0) — the
  error identifies the incumbent reference (by cid); proceeding would stack a
  second reference at one position. Remove the incumbent reference first (`device delete <cid>
  --setlist <name>`), then re-run. A re-authored
  `.hsp` is a local file change — see **Git-commit local artifact changes**
  above.

### 6. Report back

Tightly:
1. **What's on the device now** — the setlist and its tones in order (from the
   result's `references` / `device setlist list`).
2. **Pool changes** — installed / updated / skipped counts (and any `gc` deletions
   if you ran `--all --gc`).
3. **What errored and the fix** — each `errors[]` entry with its remedy
   (unresolvable model, register an IR, or
   re-run/reboot for a dropped connection).
4. **IRs** — uploaded vs any that couldn't be resolved (so the user registers
   them).

## Failure playbook — the exact errors

| Error / symptom | What it means | Do |
|---|---|---|
| a device verb fails fast with an error naming `device discover` (no `--ip`, no `$HELIXGEN_HELIX_IP`, no persisted record) | no device address is known — there is **no built-in default IP** (0.24.0); this is an immediate instructive failure, never a stall | run `helixgen device discover` once (persists the record); if it finds nothing, ask the user for the IP and pass `--ip` |
| device verbs time out / can't connect at the recorded address after working before | the persisted discover record went stale (new network or DHCP lease) | re-run `helixgen device discover`, then retry the verb |
| a verb exits non-zero rejecting an **empty/whitespace-only `--ip`** | `--ip ""` (usually an unset shell var that expanded to nothing) is a mistake, not a request to fall back (behavior change, #77) | omit `--ip` to fall back to the persisted record, or pass a real address |
| setlist not found on device (`create it with \`helixgen device setlist create ...\``) | the named setlist isn't on the device yet | run `device setlist create <name>`, then re-sync |
| `could not resolve helixgen model 'X'` | a block model doesn't bridge to the device | that tone isn't installable as-is; report it |
| cab silent / "No Model" after sync | referenced IR not in local `mapping.json` | `helixgen register-irs` the WAV, then re-sync (or import in HX Edit) |
| sync fails partway / device stops responding | the Stadium's flaky network stack dropped the connection | **re-run** the same sync (idempotent); if it persists, **reboot the Helix**, then re-run |
| `device setlist add` raises a name-collision error | the tone's `meta.name` is already registered to a **different** `.hsp` file (unique-name rule) — NOT triggered by adding the same tone to another setlist | rename one tone, or point at the already-registered file |
| `helixgen: command not found` / `ModuleNotFoundError` traceback | the CLI isn't provisioned, or a stale install shadows the uv tool on PATH | run the `setup` skill's step 0 (`uv tool install 'helixgen[device]==0.30.0'`), or invoke `"$(NO_COLOR=1 uv tool dir --bin)/helixgen"` (or `~/.local/bin/helixgen`) by absolute path |
| a mutating verb waits ~30 s then exits non-zero naming a lock **holder** (label / pid / host / age) | another helixgen process or agent on this machine holds that scope's advisory lease | wait and retry, or coordinate with whatever the label names — do **NOT** reach for `--no-lock` (see **Device locks** above) |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Parsing `.hsp` files (`json.loads`, magic-strip) to classify tones | Never parse `.hsp` bytes — just run the sync; `errors[]` is the classification |
| `view`-ing every tone / listing factory presets **before** the sync | The sync reports failures — run it, analyze `errors[]` after |
| Looking for a "template" or checking factory-preset "coverage" | There are no templates — install is a faithful, template-free transcode; just sync |
| Hand-rolling a per-preset install loop | Use `device sync <setlist>` — it reconciles the pool, rebuilds references, and uploads IRs in one call |
| Telling the user to create a setlist in the Stadium app | Not needed any more — `device setlist create <name>` creates it on the device (#8 shipped) |
| Hand-editing `~/.helixgen/setlists/manifest.json` | Manage it with `register` / `device add` / `device unsync` / `device setlist add/remove` (or the `tone` skill) |
| Passing `--no-lock` because a verb reported a lock holder | The holder message means another agent/process is mid-write on the device — wait/retry or coordinate; `--no-lock` is only ever used on the user's explicit direction |
| Running a long multi-verb device flow (full sync session, bulk IR housekeeping) without a session lease | `device lock --scope <s> --label "<what you're doing>" --ttl <covers the flow>`, carry the printed `HELIXGEN_LOCK_TOKEN` on every verb, `device unlock` at the end |
| Holding a session lease past the end of the flow (letting it expire on its own) | A token-prefixed `HELIXGEN_LOCK_TOKEN=<token> helixgen device unlock` releases it immediately — run it when the flow ends, including on failure paths (bare `device unlock` from a fresh shell can't prove ownership and keeps the lease) |
| Expecting `device sync` to touch presets helixgen didn't place | It won't — sync is a managed-set mirror keyed by tone name; untracked device presets are never moved, deleted, or overwritten |
| Pre-checking whether a tone is already in a setlist before adding it | Don't — a tone belongs in as many setlists as you want (shared, referenced once in the pool). `device setlist add` is idempotent within a setlist and only errors on a name/different-file collision. Just add it |
| Reading helixgen **source** (`SetlistManifest`, the manifest schema, engine internals) to confirm behavior or guard against "version drift" | Don't source-dive. The engine is the uv-tool-installed helixgen-core package, **not** any checkout in the working directory — so reading cwd source can *mislead* about the actual version/schema. Per-verb `--help`, `device setlist list`, the sync **result dict**, and `docs/CLI.md` are the authoritative contract (see "Where the answers live" above); operate through them |
| Expecting sync to wipe the setlist like the old mirror | It doesn't — it reconciles pool + references and never orphans; GC only on `--all --gc` |
| Diagnosing a dropped connection as a coverage failure | It's the flaky network stack — re-run the sync, reboot the Helix if it persists |
| Ignoring the `errors[]` in the sync result | That list *is* the remaining work — read it, fix each, re-sync |
| `device install` without `--auto-irs` when the tone references IRs | The CLI flag is opt-in (unlike the old MCP default) — pass `--auto-irs`, or the cab is silent until the IR reaches the device |
| Expecting `device install` to reconcile a whole setlist | It installs/records **one** tone but doesn't rebuild a setlist's full reference order the way `device sync <setlist>` does — use sync for batch/whole-setlist work |
| Hunting for the device's IP by hand (router UI, arp scans) or assuming a default address exists | Run `helixgen device discover` once — it persists the record and every verb resolves it; there is no built-in default IP (0.24.0), and a missing address fails fast pointing at discover |
| Treating `device normalize` as a device write, or skipping the sync after `--yes` | Normalize writes trims into the **local `.hsp` only** — the device copy is untouched until the next `device sync <setlist>` / `device install`; and it's dry-run by default — show the user the dry-run report before `--yes` |
| Re-running `device measure` to confirm a normalize trim landed | The meter taps sit upstream of the output-block gain, so the trim is invisible to `measure` by design — a confirmation re-measure falsely reads "no change"; trust the dB math |
| Level-matching across presets/setlists with the default anchor (no `--target-db`) | The anchor equalizes within one scope only, and on snapshot scope can drag a preset to its quietest snapshot's level — always pass one explicit absolute `--target-db` and reuse it across runs (see the field-proven guidance above) |
| Trying to fix a target whose chain-out `output_db` is over 0 dBFS with normalize | That's in-chain clipping upstream of the trim — normalize can't touch it; fix the chain's gain staging (amp/drive levels, `tone` skill), then re-run |
| Running the post-normalize `device sync` without checking for hardware-side edits | Sync re-pushes every managed tone whose content hash differs and overwrites device-side edits never pulled back — warn the user first (see the WARNING above) |
| Measuring a looper-replayed signal with the default input gate | The input jack is silent while a front-of-chain looper replays, so the default gate credits nothing and the window fails — pass `--source loop` (and compare raw `output_db`, not `gain_db`, across targets) |
| Reaching for `slots restore --force` to overwrite an occupied setlist position | `--force` only covers an occupied **pool** slot; an occupied named-setlist position is refused (the error identifies the incumbent by cid) — `device delete <cid> --setlist <name>` the incumbent reference first, then re-run |
