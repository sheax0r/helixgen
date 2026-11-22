# Snapshots management UI parity (`helixgen-81v.2`) — design

**Status:** design — awaiting approval.
**Date:** 2026-11-22.
**Scope (parity doc "P1 — Snapshots management"):** bring the `device live`
workspace from *follows snapshot switches* up to the Stadium Edit app's full
**Snapshot panel** — select/configure 8 snapshots, per-snapshot capture of
bypass + snapshot-controlled params + tempo, the per-param "Snapshot Ctrl"
(white-value) toggle, the per-block "Snapshots Set Bypass" exclude, rename +
color, copy/paste + swap a whole snapshot, and Discard-Edits mode.
**Sibling, NOT parent:** this is a P1 sibling of the signal-flow editor epic
(`helixgen-81v.1`); snapshots were explicitly carved out of 81v.1's scope. It
rides 81v.1's **unified-live** architecture (same workspace, same follow +
409-guard write model) but ships independently of the topology engine track.
**Supersedes** the parity doc's one-paragraph "P1 — Snapshots management" blurb,
specifically its claim that this is *"UI over solved engine ground"* — see §2.

Manual: [snapshots](https://manuals.line6.com/en/helix-stadium/live/snapshots)
(app v1.4 / fw 1.4). Protocol facts:
[`docs/helix-protocol.md`](../../helix-protocol.md) → SNAPSHOT NAME, Recall
snapshot (live), `/setParamValue`+`/setSnapshotValue`, `/setSnapshotBypassState`,
`/assignSnapshotBypass`/`/removeSnapshotTarget`, `cg__.asnp`, the `snps`
8-element array.

---

## 1. Intent / why

`device live` today **follows** snapshots — a snapshot switch from the hardware,
HX Edit, or `device snapshot N` re-reads the buffer and the page updates — and,
because the live page already writes `/setParamValue` with the `snap` field, a
param edited while a snapshot is active is **captured into that snapshot** by the
device. What's missing is the entire **management** surface: you cannot see the 8
snapshots, select one from the page, rename or color it, choose which params a
snapshot controls (the "white value" toggle), exclude a block's bypass from
snapshot control, copy/paste or swap snapshots, or set Discard-Edits mode. To do
any of that today a user drops to the hardware, HX Edit, or offline `.hsp`
editing (`set-snapshot` / `patch`).

This closes that gap: a user builds and manages all 8 snapshots of a preset —
names, colors, which params/bypasses each snapshot owns, copy/paste/swap,
Discard-Edits — **entirely in `device live`**, heard immediately, no hardware
dance, no `.hsp` hand-edit.

Target: parity with the Line 6 **Helix Stadium Edit** Snapshot panel.

---

## 2. Engine-readiness — the honest matrix (corrects the backlog)

The backlog calls this *"UI over solved engine ground."* That is **half true and
the misleading half matters.** Two engine layers must be distinguished:

- The **snapshot data model + offline `.hsp` authoring** is genuinely **solved**:
  the transcoder round-trips per-scene bypass + param deltas byte-faithfully
  (`to-hsp` is a fixed point across all 66 factory presets — `helix-protocol.md`,
  `tests/test_untranscode.py`), and the `.hsp` layer can **create / name / color /
  activate / clone / remove** snapshots and write per-snapshot param/bypass/output
  overrides offline (`set_snapshot` / `remove_snapshot` / `set-param --snapshot` /
  `enable|disable --snapshot`, CLI.md). `bridge.py:hsp_snapshot_meta` already
  exposes each slot's `name` / `exsw` / `bpm` / `color` / `valid`, and
  `is_snapshot_assignment` / `_snapshot_arrays` decode the dense 8-slot arrays and
  the value-polarity invariant. **Nothing new is needed here.**

- The **live-ops client** (`client.py`), by contrast, ships **exactly one**
  snapshot verb: `activate_snapshot(index)` (`/activateSnapshot`). Every other
  management operation has **no method in the live client yet** — some are decoded
  in the protocol doc, some need a capture spike. The parity blurb glosses this.

> ⚠️ **NB for implementers:** `src/helixgen/device/snapshot.py` is the device
> **photograph/backup** module (git-trackable `.sbe` pool snapshot) — *not*
> preset scenes. The scene model lives in `transcode.py` / `untranscode.py` /
> `bridge.py` + the `.hsp` verbs. Don't start there.

### The matrix

| Capability | Live-ops today | What's needed |
|---|---|---|
| Recall snapshot 0–7 | ✅ `/activateSnapshot` (`device snapshot`) | — |
| Read active index | ✅ `/getActiveSnapshotIndex` (`cg__.asnp`) | — |
| **Follow** a snapshot switch | ✅ bridge re-reads buffer on `/activateSnapshot` echo | — |
| **Capture** a snapshot-ctrl **param** edit | ✅ live page writes `/setParamValue` w/ `snap`; device captures into active snapshot; echoed `/setSnapshotValue` | — (the "press-and-turn → white" *capture* is already live for assigned params) |
| **Capture** a **block bypass** edit | ✅ device auto-captures bypass per snapshot for assigned blocks | — |
| **Per-snapshot tempo** | ✅ `global.tempo.select=Snapshot` + `global.tempo.bpm` (via `device settings`); `bpm` in `snps` meta | surface + warn (see §8.5) |
| **Discard-Edits** mode | ✅ `global.snapshot.edits` (via `device settings`) | surface + warn; icon color |
| **Rename** | ⚠️ opcode **decoded**, not in client: `/SetSnapshotName [reqid, index, name]` | thin new live verb |
| **Color** | ❌ `color` in meta, **no live opcode decoded** | capture + new verb (pin-first) |
| **Snapshot-Ctrl toggle** (white value) per param | ❌ assign side undecoded; remove seen (`/removeSnapshotTarget`) | capture + new verb (pin-first) |
| **"Snapshots Set Bypass"** exclude per block | ❌ `/assignSnapshotBypass` + `/removeSnapshotTarget` seen in cascades; `/setSnapshotBypassState` **UNVERIFIED** layout | capture + new verb (pin-first) |
| **Copy / paste** whole snapshot | ❌ **no atomic opcode** (manual + doc: app batches writes) | orchestrate — see §8.3 |
| **Swap** two snapshots | ❌ no atomic opcode | orchestrate — see §8.3 |

**Verdict:** the *model* is solved; the *live surface* is mostly unbuilt. One
opcode is decoded (rename), three need a capture spike (color, param
Snapshot-Ctrl assign, block Snapshots-Set-Bypass), two are orchestrations (copy,
swap). **The clean out is to reuse 81v.1's unified-live model** — granular where
a live opcode exists (recall + per-snapshot capture already work), and the
**offline-`.hsp`-mutate + whole-buffer live push** for everything without a
granular opcode. Because the offline snapshot layer is a byte-faithful fixed
point, every remaining operation can land **through the whole-buffer push on day
one**, with granular opcodes substituted in as the capture spike pins them. See
§8.

---

## 3. The model decision — unified-live, inherited from 81v.1

81v.1's protocol spike (2026-11-21) established the **unified-live** model:
granular live opcodes where they exist, and a **live whole-edit-buffer push**
(mutate the current buffer's `.hsp` form offline, encode `_sbepgsm`, write it in
place — echoed `/setEditBuffer`, no reload, no CID change, no apply seam) for
everything else. Snapshot management fits that model **better** than topology
does, because:

- Snapshot edits **never change topology** — they touch the `snps` scene array,
  per-param/`per-block` snapshot arrays, and `cg__` meta. So the whole-buffer
  fallback here does **not** depend on the engine topology-synthesis track
  (81v.1's long pole). It only needs the `.hsp`→`_sbepgsm` encoder to round-trip a
  **scene-mutated** buffer — which it already does (fixed point).
- Two management operations already have **granular** live paths (recall; per-
  snapshot param/bypass capture), so the common editing loop needs no push at all.

**Decision:** snapshots ride unified-live:
- **Granular (shipped):** select (`/activateSnapshot`), capture param/bypass edits
  into the active snapshot (existing live-page writes).
- **Granular (thin new verb, opcode decoded):** rename (`/SetSnapshotName`).
- **Whole-buffer push (day one), swapped for granular when pinned:** color,
  per-param Snapshot-Ctrl toggle, per-block Snapshots-Set-Bypass, copy/paste,
  swap — all expressed as offline `.hsp` scene mutations (`set-snapshot`,
  `set-param --snapshot`, `enable|disable --snapshot`, `clone_from`) then pushed.
- **Global settings (shipped):** Discard-Edits (`global.snapshot.edits`),
  per-snapshot tempo (`global.tempo.select` + `global.tempo.bpm`).

This is the app's own model — the Stadium app itself has **no atomic
copy/swap opcode** and batches writes (`helix-protocol.md` §Recall snapshot).

---

## 4. Goals

- A **Snapshot panel** in the `device live` header: the 8 snapshots with their
  names + colors, the active one highlighted, Discard-Edits state shown on the
  snapshot icon (white outline off / red on — the manual's convention).
- **Select** any snapshot from the page (granular recall); the page follows a
  switch originating anywhere (hardware/HX Edit/CLI) as it does today.
- **Capture** stays automatic: editing a Snapshot-Ctrl param or a block bypass
  while a snapshot is active writes into that snapshot (already live) — the panel
  only makes the model **visible and configurable**.
- **Per-param Snapshot-Ctrl toggle** (the "white value") in the Parameter panel:
  turn snapshot control on/off for a param; the param's value renders white when
  on. Assign/remove the snapshot target.
- **Per-block "Snapshots Set Bypass"** toggle in the block Action panel: exclude a
  block's bypass from snapshot control (default on; Looper excluded by the device).
- **Rename + color** a snapshot.
- **Copy/paste** a whole snapshot's contents into another slot; **swap** two slots.
- **Discard-Edits** mode toggle, with the "press SAVE twice to keep edits" nuance
  surfaced.
- **Per-snapshot tempo** surfaced (and the `Tempo Select = Snapshot` global that
  gates it).
- **MIDI Recall** read-only display: the PC/CC to recall the current setlist /
  preset / snapshot.
- Everything **heard immediately**; persists via the existing **Save** /
  `device copy`; round-trips `.hsp` ⇄ library with no fidelity loss (`to-hsp`
  already covers scenes).
- Parity items the live protocol genuinely can't do → **won't-do with the
  reason** (§9), never silently missing.

## 5. Non-goals (other epics)
- **Command Center snapshot-controlled command params.** The manual lists these
  as a thing snapshots store, but Command Center is its own epic (parity doc
  "P2 — Command Center"). The snapshot panel **respects and displays** snapshot-
  controlled command values that already exist (they ride the same scene arrays),
  but the **assignment UI** for command params lives in that epic. Cross-ref.
- Controllers / footswitch assignment, the signal-flow editor itself, global
  settings pages beyond the three snapshot-relevant keys, Song View / Showcase
  snapshot automation, the tuner.

## 6. Anti-goals (a failure even if it technically works)
- A **visible "apply snapshot change" step.** A rename, color, copy, or toggle
  must feel as immediate as selecting a snapshot — the whole-buffer push must be
  as seamless as it is in 81v.1 (no save, no reload).
- **Capturing a param into the wrong snapshot.** Every per-snapshot write must be
  pinned to the active index the page is showing; a stale index silently rewrites
  another scene. (This is the snapshot analogue of 81v.1's 409 revision guard —
  see §8.6.)
- **Fidelity loss on scene round-trip** — a managed snapshot set that doesn't come
  back byte-faithfully through `.hsp` ⇄ `_sbepgsm`.
- **Two owners of the same snapshot-bypass target.** The per-block "Snapshots Set
  Bypass" toggle and 81v.1's model/add/clear cascade both write
  `/assignSnapshotBypass` / `/removeSnapshotTarget`; they must share one
  representation (see §10 collision #2).

## 7. Approaches considered
1. **Wait for granular opcodes for everything.** Capture `/SetSnapshotColor`, the
   param Snapshot-Ctrl assign, and the block Snapshots-Set-Bypass live commands
   before building any UI. **Ruled out:** serializes the whole feature behind a
   protocol-RE spike, when the offline scene layer already expresses every one of
   these operations and the whole-buffer push can carry them today.
2. **Pure offline `.hsp` + `device copy` reload.** Edit the on-disk `.hsp`, re-copy.
   **Ruled out:** adds a save + preset-reload seam the app doesn't have, and
   fights the "live edit buffer vs editing a file" reconciliation the parity doc
   flagged.
3. **Unified-live (CHOSEN).** Granular opcodes where they exist (recall, capture,
   rename); whole-buffer offline-mutate + live push for the rest; granular
   opcodes dropped in as the spike pins them. Matches the app, no seam, ships on
   the already-solved offline scene layer, and is **decoupled from the topology
   engine track** (snapshots don't touch routing).

## 8. The how — decided

### 8.1 Panel + follow
- Header **Snapshot icon**: number = active index (from `/getActiveSnapshotIndex`
  / `cg__.asnp`), outline color = Discard-Edits state. Tapping opens the panel:
  8 snapshots with name + color chips, active highlighted, plus sidebar actions
  (Rename/Color, Copy, Paste, Swap, Discard-Edits, MIDI Recall).
- **Configured vs blank:** a slot is configured iff it carries a non-placeholder
  name (`valid` / `name != "Snap N"` — `hsp_snapshot_meta` + CLI.md). An
  unconfigured slot shows as its placeholder; selecting it and editing promotes it
  (the device's own "becomes active on first edit" behavior — we don't force it).
- **Follow** is the existing bridge path: `/activateSnapshot` echo → one buffer
  re-read (the ~0.5 s snapshot switch already measured in `device live`), rebuild
  panel + chain state. The panel's **own** recall is recognized by request id and
  not double-applied, same as every live write today.

### 8.2 Select + capture (granular, shipped)
- **Select** → `client.activate_snapshot(index)`.
- **Capture** needs no new code: the live page already writes
  `/setParamValue [origin, seq, path, grid_slot, snap, pid, value]`, and a write
  to a snapshot-assigned param lands in the **active snapshot only**
  (`helix-protocol.md`, HW-verified 2026-11-13) with a `/setSnapshotValue` echo;
  block-bypass edits auto-capture per snapshot for assigned blocks. The panel
  makes this **legible** (white values, active-snapshot banner) rather than adding
  a capture command. The manual's "press-and-turn to white" *is* this write.

### 8.3 The management ops without a granular opcode
Each is expressed as an **offline `.hsp` scene mutation** on the re-read live
buffer, then whole-buffer pushed (§8.6). The `.hsp` verbs already exist:

- **Per-param Snapshot-Ctrl toggle** → assign: `set-param <buf> <block> <param>
  --snapshot <active>` seeds the per-snapshot array (promotes the param to
  snapshot-tracked — `is_snapshot_assignment` true once it varies / is targeted);
  remove: revert the array to base. The value renders **white** when the array is
  a real assignment.
- **Per-block "Snapshots Set Bypass"** → the block's `@enabled.snapshots` bypass
  array is an assignment or not (`_block_bypass_snapshots` / `is_snapshot_assignment`);
  toggle assigns/removes that block's snapshot-bypass target. Default on; Looper
  has none.
- **Rename** → granular `/SetSnapshotName [reqid, index, name]` (opcode decoded;
  thin new client verb — the one management op that skips the push).
- **Color** → `set-snapshot --index I --color C` offline + push (until the color
  opcode is pinned, §9).
- **Copy/paste** → `set-snapshot --index TARGET --clone-from SOURCE` (copies full
  per-snapshot state — bypasses + params + output — **state only, never the
  name**; CLI.md) offline + push.
- **Swap** → clone A→tmp semantics in `.hsp` (read both scenes, write each into the
  other's slot) offline + push. One push = one undo step.

### 8.4 New / confirmed engine + protocol surface (lands in helixgen-core first)
- **`/SetSnapshotName`** — decoded; add a `client.set_snapshot_name(index, name)`
  live verb. Low risk.
- **Pin-first capture spike** (same discipline as 81v.1 §9), on the real device,
  `helixgen device watch` on 2001 while driving the Stadium app:
  - (a) **Snapshot color** opcode (app: Snapshot panel → Rename/Color → color).
  - (b) **Param Snapshot-Ctrl assign** opcode (app: Parameter panel → Snapshot Ctrl
    ON) and its remove twin (`/removeSnapshotTarget` already seen).
  - (c) **Block Snapshots-Set-Bypass** opcode (app: block Action panel → toggle),
    and confirm `/setSnapshotBypassState`'s arg layout (currently **UNVERIFIED**).
  Each pinned opcode **replaces** its whole-buffer push with a granular write;
  until pinned, the push covers it. None **blocks** the feature (unlike 81v.1's
  topology keystone) — they are optimizations from push → granular.
- **`_sbepgsm` round-trip of a scene-mutated buffer** is already a fixed point
  (all 66 factory presets, `test_untranscode.py`); confirm on a couple of
  **device-re-saved** buffers before trusting the push for real user presets (the
  known canonicalization diffs — `snps` `si__` ordering, `cg__` numbering — are
  tone-neutral, but verify on a snapshot-heavy preset).

### 8.5 Tempo + Discard-Edits (global settings, shipped)
- **Per-snapshot tempo:** surface `global.tempo.select` (Per Preset / Snapshot);
  when Snapshot, each snapshot's `bpm` (in `snps` meta) is captured/recalled by
  the device. The panel shows the active snapshot's tempo and a one-line note that
  per-snapshot tempo is gated by the global. Writes go through `device settings`.
- **Discard-Edits:** `global.snapshot.edits` (OFF = remember edits across
  switches, default; ON = discard). The panel toggles it and renders the icon
  color accordingly, plus the manual's nuance: with Discard-Edits ON, **press SAVE
  twice** to keep edits before leaving a snapshot. (`global.snapshot.reselect` —
  "Snapshot Reselect" — is the adjacent global; surface read-only or defer.)

### 8.6 Write safety — the active-index guard
A per-snapshot write (capture, toggle-via-push, copy) is correct **only** against
the index the page believes is active. Reuse 81v.1's **409 structure-revision
guard**, extended to carry the **active snapshot index**: every per-snapshot write
names `(preset-rev, active-snapshot-index)`; if the device switched snapshots (or
the preset/model changed) since the page rendered, the write is **refused with the
current state** and the panel re-reads rather than writing into the wrong scene.
The whole-buffer push additionally **re-fetches `/EditBufferStateGet` immediately
before mutate+push** (81v.1 §8.1 concurrency rule) so a copy/swap never clobbers a
concurrent writer. **Undo:** one management push = one undo step; history clears on
snapshot/preset change exactly as today (and the snapshot panel is now a *cause* of
that clear — it must trigger the same reset the hardware switch does).

## 9. What's left to the builder
- **Pin-first spike** (§8.4): capture color / param-assign / block-bypass live
  opcodes. Non-blocking — each only upgrades a push to a granular write.
- **`exsw` meaning:** `hsp_snapshot_meta` returns an `exsw` field per slot
  (alongside name/bpm/color/valid) — confirm whether it's snapshot
  external-switch/edit-switch state and whether the panel must surface it, or
  whether it's device-internal (likely the latter; don't expose until confirmed).
- **Confirm scene round-trip** on a device-re-saved, snapshot-heavy preset (§8.4).
- **Copy/paste UX:** the app is select-source → Copy → select-target → confirm;
  decide the browser gesture (two-step vs drag) — capability parity, not gesture
  parity (the hardware "touch-hold two footswitches to swap" has no page analogue;
  a Swap action with two pickers is the parity).
- **"Save twice" affordance** for Discard-Edits ON — how the page communicates it
  (the device's double-SAVE is a hardware idiom; surface as a hint + a one-click
  "keep edits" that does the double-save, if the save path allows).
- **Blank-snapshot promotion:** match the device ("appears same as the one you came
  from until you edit it") — don't eagerly `valid:true` a slot the user only
  selected.

## 10. Collisions with the signal-flow editor epic (81v.1) — FLAGGED

1. **🔴 Amp-lens "store 8 lens positions as snapshots 1–8" (81v.1 §8.4 / parity
   Focus-View).** 81v.1 proposes storing amp XY-morph lens positions **as
   snapshots 1–8**. If taken literally that **commandeers the user's 8 snapshot
   slots** and is flatly incompatible with this epic (the user's Intro/Verse/Chorus
   scenes *are* those slots). This must be reconciled before either ships: either
   the amp lens uses a **separate** store (X/Y zone params, not scene slots — the
   manual's amp "Based On" morph is per-model, not the preset's 8 snapshots), or
   81v.1 drops the literal-snapshot storage. **My read:** 81v.1 mis-mapped the
   amp-lens model onto preset snapshots; lens zones are not the 8 scenes. Owner
   should resolve — this is the sharpest collision.

2. **🟠 Snapshot-bypass target ownership.** 81v.1's model/add/clear cascade emits
   `/assignSnapshotBypass` + `/removeSnapshotTarget` for a block; this epic's
   per-block "Snapshots Set Bypass" toggle writes the **same** target. They must
   share **one** representation of a block's snapshot-bypass assignment (the
   `@enabled.snapshots` array / `is_snapshot_assignment`), or adding a block and
   toggling its snapshot-bypass will fight. Single source of truth required.

3. **🟡 Whole-buffer push keystone (81v.1 §8.2, still pin-first/unproven).** Color /
   copy / swap fall back to the same whole-buffer SET command 81v.1 depends on.
   **But** snapshots don't need the topology-synthesis engine track, and their
   common ops (recall, capture, rename) are granular — so snapshot management is
   **far less exposed** to that keystone than topology is, and can ship its
   granular surface even if the push slips. Shared dependency, lower blast radius.

4. **🟡 Shared workspace plumbing.** Both panels live in `device live`, share the
   2001 follow subscription, the 409 guard (extended here with the active-snapshot
   index, §8.6), and the undo/history-clears-on-snapshot-change rule. The snapshot
   panel is now a **cause** of snapshot changes, so it must drive the same reset
   the hardware switch does. Coordinate the guard + undo contract across both
   epics (one implementation, not two).

## 11. Acceptance
- A user selects, renames, colors, copies/pastes, and swaps all 8 snapshots of a
  preset, toggles Snapshot-Ctrl per param (white value) and Snapshots-Set-Bypass
  per block, and sets Discard-Edits — entirely in `device live`, heard
  immediately, no hardware dance, no `.hsp` hand-edit.
- Per-snapshot writes land in the shown active snapshot and never another
  (active-index guard); concurrent hardware/HX Edit switches are followed.
- The managed snapshot set persists via Save / `device copy` and round-trips
  `.hsp` ⇄ library with no fidelity loss (`to-hsp`).
- Command Center snapshot-controlled command params are respected/displayed but
  their assignment UI is deferred to the Command Center epic (documented, not
  silently missing).
- Parity items the live protocol genuinely can't do are won't-do with the reason.

## 12. Won't-do / caveats (with reasons)
- **Hardware swap gesture** ("touch-hold two footswitches") → no page analogue;
  replaced by a Swap action with two pickers (capability parity).
- **Looper bypass per snapshot** → the device excludes the Looper from snapshot
  bypass; the panel respects it (not a helixgen limitation).
- **Command Center snapshot-controlled command param *assignment*** → Command
  Center epic (§5); values are respected here.
- **Song View / Showcase snapshot automation** → Song View epic (candidate
  won't-do overall).
- No hard "the protocol can't do this" item on the snapshot feature set itself —
  every operation maps to a granular live write or the whole-buffer push. The only
  genuinely non-granular ops (color/copy/swap) are handled by the push, exactly as
  the Stadium app batches them.

## 13. Capture evidence to sync into `helix-protocol.md`
After the §8.4 spike: the snapshot **color** opcode, the param **Snapshot-Ctrl
assign/remove** opcodes, the block **Snapshots-Set-Bypass** opcode +
`/setSnapshotBypassState` arg layout (today UNVERIFIED). Land in helixgen-core
(`docs/helix-protocol.md`) first, with the companion plugin PR updating `skills/*`
+ synced `docs/` — the two-PR cross-repo sync discipline (CLAUDE.md).
