# Device file-copy model — design

**Date:** 2026-09-09
**Status:** approved, implementation pre-authorised
**Repos:** engine → `helixgen-core`; skill + synced docs → `helixgen` (this repo)

## Problem

Getting one tone onto the Helix costs three commands and a manifest the user
cannot see:

```
helixgen device setlist add Gigs tone.hsp     # local manifest membership
helixgen device add "Tone Name"               # local manifest slot intent
helixgen device sync Gigs                     # reconcile whole managed set
```

The reconcile walks the entire setlist, emits ~100 stderr lines, and re-checks
tones the user never touched. Its only purpose is to make the device agree with
`~/.helixgen/setlists/manifest.json`.

That manifest is the wrong model. The user wants the **device** to be the truth
about what is loaded and in what order, a **local library** of tones and IRs they
own, and a **git-tracked backup** of the device supporting diff and restore.

Three complaints, confirmed with the user: the manifest is the wrong model; the
sync is slow and noisy; the ceremony is too heavy for "put this tone on my amp".
Notably *not* a complaint: destructiveness. Sync's deletes were never the fear.

## What the manifest is today

`~/.helixgen/setlists/manifest.json`, schema v3, is two things fused:

```json
{ "version": 3,
  "tones":    { "Dream On": { "path": "...hsp", "content_hash": "sha256:…",
                              "source": "authored", "slot": null } },
  "setlists": { "Gigs": { "tones": ["name", "name"], "synced": false } } }
```

- **(a) a tone registry** — name → `.hsp` path, content hash, provenance.
- **(b) setlist intent** — desired membership, desired order, `slot`
  (`null` = off device, `"auto"` = wants on device), and a `synced` flag.

`device sync` exists solely to make the device match (b). Observed placement
(`cid`/`posi`) already lives outside the manifest, per device serial, in
`~/.helixgen/devices/<serial>.json` (gitignored, rebuilt wholesale by every sync).

Both halves go away. (b) moves to the device, which is where it belongs. (a)
becomes the directory listing of `library/tones/`.

## Model

Three stores, three jobs, no reconcile between them.

| Store | Job | Authoritative for |
|---|---|---|
| `~/.helixgen/library/tones/*.hsp` + `library/irs/` | content the user authors and owns | source files |
| the device | what is loaded, and in what order | setlists, membership, order |
| `~/.helixgen/backup/<serial>/` | photograph of the device, git-tracked | what the device held at time T |

```
~/.helixgen/
  library/
    tones/*.hsp                # name = meta.name; glob to list, no registry
    irs/ + mapping.json        # unchanged
  backup/<serial>/
    pool/<Name>.sbe            # device content bytes, faithful
    setlists/<Name>.json       # ["Dream On", "Back In Black"]   <- order
    irs/<irhash>.wav           # device-processed IR, ~32KB mono
    irs/index.json             # irhash -> display name, file basename, channels
    device.json                # model, firmware, serial, globals
```

### The snapshot is a photograph, not a working document

Deliberate and load-bearing. The user changes the device **only** through the
copy/remove/move verbs. `device backup` re-photographs. `git diff` reads the
drift. `device restore` replays a snapshot for disaster recovery.

Hand-editing `setlists/Gigs.json` does nothing. That is the line that stops this
design from quietly becoming `sync` again under a new name: today's `setlists{}`
and this snapshot are nearly the same data structure, and the only thing keeping
them distinct is the direction truth flows.

**Accepted cost:** reordering a 40-preset setlist is 40 `device move` calls. A
bulk form can come later if it bites; it is not in this design.

### Why `.sbe` and not `.hsp`

`.hsp` is a lossy *view* of device content, and only in the backwards direction.

Forward (`.hsp` → device) is not lossy: hardware-validated byte-for-byte against
HX Edit's own import (2.18.0), including models, params, snapshots,
footswitch/EXP, dual-amp, parallel splits and IR references.

Backwards (`device to-hsp`) has a **decoder** gap, not a format gap:

- **Dropped outright**, warning naming the count: Command Center commands (#16)
  and MIDI CC controller bindings (#33). `.hsp` holds both fine — the `tone`
  skill authors them — but the backwards transcoder cannot yet read them out of
  device bytes. Both are EXPERIMENTAL forward, neither is in the validation corpus.
- **Reported, one stderr line per loss:** a snapshot or controller assignment on
  a dual-cab's B model slot (models and params *are* carried; only the `cg__`
  target has no forward spelling), a disabled DSP path, a row-1 input that would
  revert to `InputNone`, a non-contiguous grid run a reinstall would compact, a
  controller source with no `.hsp` id, a snapshot target missing from some
  snapshots' `tamv`.
- **Not loss:** float32 widening (`0.15` → `0.15000000596046448`) re-encodes
  identically; per-block `harness` is not carried because the forward path
  synthesizes a canonical `hrns` regardless; "re-transcode differs" is expected
  whenever the *device* re-saved a preset (serialization convention and internal
  id numbering, not tone).

For anything helixgen authored and installed, `to-hsp` is byte-exact and
`--verify` says so. The loss only bites presets made on the amp or in HX Edit —
but "reported" is not "recovered". A backup built from `.hsp` would silently ship
a preset whose Command Center assignments were gone, and restore would put that
damaged version back.

So the snapshot stores the device's own bytes. No transcoder in the restore path.

### Diffing binary content

`.sbe` is `\xff\xff\xff\xffpgsm` + msgpack — binary, and `.hsp` is one
200KB line, so neither diffs in git unaided.

A new `helixgen device decode <file.sbe|-> [--indent N]` prints the **native**
content structure as pretty JSON (via `content.decode_any`, 4CC string keys).
Wired as a git textconv it makes `git diff` show exactly what changed in device
terms — lossless, no transcoder, better than an `.hsp` rendering would be.

```
# ~/.helixgen/.gitattributes
*.sbe diff=helixgen-sbe
# git config (set by `device backup` on first run, idempotent)
git config diff.helixgen-sbe.textconv "helixgen device decode"
git config diff.helixgen-sbe.binary false
```

## CLI surface

### New: the one real capability gap

```bash
helixgen device copy <file.hsp> --to <setlist> [--pos N] [--no-irs] [--json]
```

Preset name comes from the file's `meta.name`. **Upsert semantics:** if a preset
of that name is already in the target setlist, update its content in place (the
same non-activating existing-cid content update `sync` uses internally); else
pool it and add a reference at `--pos`, appending when `--pos` is omitted.

IRs referenced by the tone upload **by default**; `--no-irs` opts out. The
current `install --auto-irs` opt-in is backwards for a copy verb — a copy that
silently leaves a cab reading "No Model" is a broken copy.

This upsert is the entire reason every path routes through `sync` today:
`install` can only create, so an occupied name/slot leaves the user stuck and
only sync's update path can refresh edited content. Close this gap and sync has
no remaining job.

Omitting `--to` targets the pool (`user`) with no setlist reference.

### Renamed: same machinery, name-addressed

```bash
helixgen device rm <name> --from <setlist> [--also-pool] [--yes] [--json]
helixgen device move <name> --in <setlist> --to <N> [--json]
```

`rm` drops the setlist reference; the pool preset survives unless `--also-pool`.
Replaces `device delete <cid> --setlist <name>`. `move` replaces `device reorder`
for the name-addressed case.

### New: backup / diff / restore

```bash
helixgen device backup [--dry-run] [--json]
helixgen device restore [--from <git-ref>] [--setlist <name>] [--prune]
                        [--dry-run] [--yes] [--json]
helixgen device decode <file.sbe|-> [--indent N]
```

`backup` walks pool + setlists + IRs and writes `backup/<serial>/`. `--dry-run`
prints what *would* change without writing — that is the diff-against-live, so no
separate diff verb is needed. Diff-against-history is `git -C ~/.helixgen diff`.

`restore` replays a snapshot: pool content first, then setlist order. It prints
the diff and confirms before touching anything. Additive-and-update by default;
`--prune` deletes device presets absent from the snapshot. This *is* a
reconcile — but explicit, confirmed, rare, and against an artifact the user can
read. `--prune` is the one genuinely destructive path in the new surface.

**IR collection cross-check.** Collect every hash in `device list-irs` **plus**
every `irhash` referenced by a pulled preset, then verify each pulled file's MD5
equals its hash. The `-11` listing cache is known to go stale (#38 — an IR
imported by another client can stay unlisted for 11+ minutes), so listing alone
would silently under-collect. `device pull-ir` is EXPERIMENTAL and this design
makes it load-bearing for restore; the cross-check plus MD5 verification is what
makes that acceptable.

### Deleted

`device sync`, `device add`, `device unsync`, `device setlist add`,
`device setlist remove`, `device setlist create-local`, `device setlist sync-on`,
`device setlist sync-off`, `device library`, `device slots list`,
`device slots reorder`, `device slots restore`, `helixgen register`,
`manifest.json` and its whole v1→v2→v3 migration chain
(`device/manifest.py`, `device/setlist_sync.py`).

`device install` and `device delete` fold into `copy` and `rm`.

### Untouched

`discover`, `setlist create`/`rename`/`delete`/`duplicate`, `to-hsp`, `list`,
`read`, `load`, `active`, live ops (`blocks`/`params`/`bypass`/`model`/
`set-param`/`meters`), `measure`/`normalize`/`calibrate`, `push-ir`/`pull-ir`/
`list-irs`/`delete-ir`/`rename-ir`/`ir-prune`/`register-irs`, `settings`,
`globaleq`, `tuner`, `watch`, device locks.

## Rules that need stating

**Identity is the display name.** Device preset names are not guaranteed unique.
`copy` matches within the target setlist first; genuine ambiguity is an **error**
that prints the competing cids, with `--cid` as the escape hatch. Never guess.

**Order is device state.** Set it with `--pos` on `copy` and with `device move`.
The snapshot's setlist arrays *record* order; they do not drive it.

**Locks are unchanged.** `copy`/`rm`/`move`/`restore` take the `library` scope
(plus `irs` when uploading IRs); `backup` and `decode` are read-only —
`decode` is wholly offline.

## Migration

The device is the truth, so there is nothing to migrate:

1. `helixgen device backup` — photograph the live device into the new tree.
2. Commit it.
3. Delete `~/.helixgen/setlists/manifest.json`.

`~/.helixgen/device-backups/` (the old flat `NN-slot-Name.sbe` files) is left
alone as history. The engine emits a one-time notice when it finds a legacy
manifest, naming these three steps; it does not read or convert it.

## Delivery

Engine changes land in `helixgen-core`; skills and the synced `docs/CLI.md` land
here. Two PRs, cross-referenced, landed together — core releases to PyPI first,
then this repo bumps the pin in `skills/*` + `README.md` + `CLAUDE.md` and cuts
its own release. Per repo policy, engine behavior is never patched from the
plugin repo.

Skill sections that exist only to manage sync are deleted with it: "The default
path", "The sync run IS your analysis", "Do NOT front-load analysis", the sync
red-flags list, and "Why a tone lands in `errors[]`". The skill's spine becomes
copy / rm / move / backup / restore.

## Manifest couplings discovered during implementation

The manifest is load-bearing in more places than "sync" — found by grepping core
for `manifest` after the design was approved. Each must be re-pointed at the
library directory or at the device, not merely deleted:

| Site | Coupling today | Becomes |
|---|---|---|
| `tone_meta.py` | a metadata variant's `preset_name` must be registered in `manifest.tones` | the variant's `.hsp` must exist in `library/tones/` |
| `cli_library.py` | loads `SetlistManifest`, re-keys it when tones are renamed | globs `library/tones/`; rename is a file rename |
| `device/maintenance.py` | `local_referenced_ir_hashes(manifest)` walks `manifest.tones` to decide which IRs `ir-prune` must keep | walks `library/tones/*.hsp` |
| `device/hss.py` | import records pathless tones into the manifest so a later sync won't strip their references | records nothing; without a reconcile there is nothing to strip |
| `device/normalize.py` (setlist scope) | loads each tone by its **observed CID** from the per-device observations the sync rebuilt | resolves each tone **by name against the live device setlist** |
| `device/observations.py` | per-device `cid`/`posi` observations, rebuilt wholesale by every sync | no longer rebuilt; the address record in `devices/<serial>.json` stays, placement observations go |
| `device/reorder.py` | doc comments contrasting itself with the manifest-based reorder | doc-only fix; `reorder` already never touched the manifest |

`normalize`'s setlist scope is the one with real behavior risk: resolving by name
can fail where a stale CID silently "worked", so it must report a clear
not-found rather than normalizing the wrong preset.

## Risks

- **`pull-ir` is EXPERIMENTAL** and restore now depends on it. Mitigated by the
  hash cross-check and per-file MD5 verification, but it is a real dependency on
  a lightly-exercised path.
- **`--prune` on restore** is destructive and irreversible on the device. It is
  opt-in, dry-runnable, and confirmed.
- **Reordering cost** — 40 presets means 40 `move` calls (accepted; see above).
- **Name collisions** on a device the user organised by hand will surface as
  errors rather than silent wrong-target writes. Correct, but it will be a
  visible behavior change for anyone with duplicate preset names.
