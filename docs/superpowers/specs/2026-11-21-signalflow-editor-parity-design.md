# Signal-flow editor parity (`helixgen-81v.1`) — design

> **CORRECTION 2026-11-22 — read before implementing.** A Frida capture of the
> Stadium app's own traffic disproved this document's "live whole-buffer SET"
> mechanism: that verb does not exist. **Live** topology edits are a
> **`/doAgenda` op-transaction** (`movb` / `swap` / `setm` / `spld` / `jono` /
> `clrb`); the whole-buffer `/setEditBuffer` the spike saw is the device's 2001
> *echo*. What changes here:
> - Do not pin or implement a whole-buffer SET RPC; the live push emits a
>   `/doAgenda` op-list. Reasoning built on "a push replaces the entire buffer"
>   (concurrency, undo) needs redoing for op-transactions, not word substitution.
> - Do not implement `/ClearBlock` — `/clearBlock` is an echo; clear is a `clrb` op.
> - Dual cab's second cab is confirmed: a plain `/ModelSet` with `subpos = 1`.
> - **Unchanged:** the byte-faithful `_sbepgsm` encoder and the `.hsp`
>   harness/branch modelling are still needed for Save and library round-trip.
>
> Facts: [`docs/helix-protocol.md`](../../helix-protocol.md) → "Structural edits —
> `/doAgenda` op-transactions".

**Status:** design — awaiting approval.
**Date:** 2026-11-21.
**Scope chosen by owner:** the **whole epic as written** — structural editor *and*
the per-block Focus View deep editors (not split into a sibling epic).
**Hard dependency (owner decision, 2026-11-21):** topology editing needs unbuilt
helixgen-core work (decode the `hrns` harness, synthesize device-native routing —
see §8.6). The owner chose **engine-synthesis epic FIRST**: a separate helixgen-core
epic lands that capability, **then** 81v.1 (this doc) builds the full editor UI —
topology included — on top of it. So 81v.1 is **blocked on** that prerequisite epic;
this doc assumes it complete.
**Supersedes the open question in** `docs/parity/stadium-app-parity.md` §"The hard
question" — the model decision is now resolved by a live protocol spike (below).

---

## 1. Intent / why

`device live` today **reads** a preset's signal chain and lets you turn every
knob, toggle every bypass, and follow the device — but it cannot **build or
reshape** a chain: no add/remove/move block, no model swap, no parallel routing,
only each block's primary model, and no per-block deep editors. To do any of
that today a user drops to `.hsp` hand-editing or HX Edit / the Stadium app.

This epic closes that gap: a user builds a preset's signal chain from empty to
multi-path, multi-block, dual-cab, with model selection and deep per-block
editing, **entirely in `device live`** — heard immediately, no `.hsp`
hand-edit, no Stadium app.

The target is feature parity with the Line 6 **Helix Stadium Edit application**
signal-path editor + Focus View (app v1.4 / fw 1.4), plus the dual-cab / IR
surface helixgen owns that the app approximates differently.

---

## 2. The model decision — RESOLVED by protocol spike (2026-11-21)

The brief said structural "editor parity" forces a model choice — **live-only**,
**dual-mode**, or **hybrid** — gated on an unknown: *can the device do
structural edits live at all?* A spike answered it.

### Method
Drove the real **Helix Stadium app** (over USB) through each structural op while
`helixgen device watch` captured the device's **network 2001** PUB stream.
Verified first that a USB-originated edit echoes on network 2001 (it does: a
bypass toggle emitted `/setBlockEnable [_, _, 0, 15, 0]`). The 2002 RPC *command*
is request/reply and not passively observable, but the **2001 echo of every
edit-buffer change** is — and whether an op echoes **granularly** vs as a
**wholesale buffer** is exactly what decides the model.

### Result — two op classes

| Structural op | 2001 echo | Mechanism |
|---|---|---|
| Param set | `/setParamValue` | granular (shipped) |
| Bypass | `/setBlockEnable` | granular (shipped) |
| **Add block** | `/setModelWithMID` + cascade | granular `/ModelSet` |
| **Clear block** | `/clearBlock` + `/removeSnapshotTarget` | granular — **new opcode** |
| **Swap model** | `/setModelWithMID` + cascade | granular `/ModelSet` |
| **Move / reorder** | one `/setEditBuffer` (+ FS re-index) | **wholesale buffer** |
| **Add split / parallel** | one `/setEditBuffer` (+ FS re-index) | **wholesale buffer** |

Captured args (Stadium XL fw 1.4.1):
- Add Minotaur → `/setModelWithMID [67849, 1214, 0, 10, 0, 304, -1]` (path 0, grid_slot
  10, subpos 0, modelId 304) then the cascade (`setBlockEnable`, `setBlockFavorite`,
  `assignSnapshotBypass`, `attachBlockBypassControllerWithBlob`, controller/stomp
  auto-assign) — exactly the `/ModelSet` cascade the protocol doc §6 predicts.
- Clear → `/removeSnapshotTarget [67849, 1215, 18]` + `/clearBlock [67849, 1215, 0, 10]`.
- Move / Add-split → a single `/setEditBuffer [_, _, <whole _sbepgsm>]` + a batch of
  `preset.floorboard.stomp.*` property writes (footswitch re-index).

### The finding that settles it
Topology edits replace the **entire live edit buffer in place** — `/setEditBuffer`
with **no `/loadContentRef` and no CID change**. The device accepts a **live
whole-buffer write** and applies it instantly, heard at once, **no save, no
reload, no visible "apply" step**. The protocol reference (`docs/helix-protocol.md`
§4 source/sink, §9) assumed this did not exist — it lists `/SetContentData`→reload
as the only whole-content sink. It exists, and the Stadium app itself relies on it
for every move/split.

### Decision: **unified-live**
- **Granular opcodes** for param / bypass / model-swap / add / clear.
- **Whole-buffer live push** for everything topological (move, split/merge,
  routing, dual-cab 2nd slot, mono↔stereo convert, I/O source): mutate the current
  edit buffer offline with the engine's mature `.hsp` mutate/patch path, encode
  `_sbepgsm`, push the whole buffer live (the write-twin of `/EditBufferStateGet`,
  echoed as `/setEditBuffer`).

This **is** the app's own model. It gives seamless live structural editing with
**no apply seam**, while reusing the battle-tested offline-mutate + transcoder
path for topology helixgen can't express as a granular opcode.

---

## 3. Goals

- Build / reshape a preset's whole signal chain in `device live`, live:
  add / remove / move / swap blocks; **model browser** (categories, mono/stereo/
  legacy, amp ordering, swap-in-place); **parallel routing** (add split — type +
  balance; add merge/return — pan A/B; drag-down auto-split; multiple splits; up
  to 4 flows, super-serial "DSP permitting"); **dual-cab 2nd slot** (own model/IR/
  pan/settings); **inputs/outputs** (source select incl. Instrument 2 on XL; output
  level; I/O + clip metering); **mono↔stereo convert** in place.
- **Focus View deep editors** per block: amp/preamp lens / XY morph (store 8 lens
  positions as snapshots 1–8; "Based On"; I/O meters); cab mic position/distance/
  angle + IR frequency-response plot + Amp>Cab Link; EQ drag-band graphic/parametric
  (all but Acoustic Sim); compressor/gate real-time gain-reduction meter; Clone
  read-only metadata panel; Trails + other harness settings the editor surfaces.
- Structural edits are **heard immediately** (live), persist via the existing
  **Save / `device copy`** model, and round-trip `.hsp` ⇄ library with **no fidelity
  loss** (`device to-hsp`).
- Parity items the live protocol **genuinely cannot do** are documented as
  **won't-do with the reason**, never left silently missing.

## 4. Non-goals (other epics — `stadium-app-parity.md` map)
Snapshots management UI, controllers / Command Center assignment, global settings /
global EQ, Matrix Mixer, IR import, tuner, Song View, librarian / preset management.

## 5. Anti-goals (a failure even if it technically works)
- A **visible "apply / push structure" step**. Avoiding it was the point of the
  spike; the live whole-buffer push must be as seamless as a knob turn.
- **Fidelity loss on structural round-trip** (`.hsp` ⇄ `_sbepgsm`) — a reshaped
  chain that doesn't come back byte-faithfully.
- A **helixgen-only routing representation** that diverges from the device's own
  grid/topology model (grid-slot addressing, `xbranch` cross-DSP pointers).

## 6. Constraints
- Device-bound, firmware **1.4+** (as `device live` today).
- Offline structural edits go through the engine's existing `mutate` / patch verbs
  + `.hsp`→`_sbepgsm` transcoder — **skills drive the CLI, not source**; behavioral
  contracts live in per-verb `--help` + synced docs.
- The `_sbepgsm` encoder must round-trip a **structurally mutated** buffer
  byte-faithfully, including the still-open `hrns` harness + controller leaves
  (helix-protocol.md §9 "main lift").
- **Agent-surface sync:** the new protocol facts (`/clearBlock`, the whole-buffer
  SET verb) land in **helixgen-core** first (engine + `docs/helix-protocol.md`),
  with a companion plugin PR updating `skills/*` + synced `docs/`.

## 7. Approaches considered
1. **Live-only granular** — implement every structural op as a granular live
   opcode. **Ruled out:** the spike shows no move / reorder / split opcode exists;
   the app itself falls back to whole-buffer for topology.
2. **Offline → `/SetContentData`(cid) → reload** — mutate `.hsp`, write to a stored
   cid, reload. **Ruled out:** strictly worse — adds a save + preset-reload seam
   the app does **not** have (it pushes the live buffer in place).
3. **Unified-live (CHOSEN)** — granular opcodes where they exist; live whole-buffer
   push for topology. Matches the app exactly; no seam; reuses the mature
   offline-mutate path.

## 8. The how — decided

### 8.1 Edit routing (the core of the epic)
- **Granular ops** (param, bypass, model swap, add, clear) → the existing live-ops
  client path (`set_param`, `set_block_enable`, `/ModelSet`, **new `/ClearBlock`**),
  with their cascades replayed/observed via the 2001 echo (apply idempotently —
  never re-write on echo).
- **Topology ops** (move, split/merge, routing, dual-cab 2nd slot, mono↔stereo,
  I/O source) → **re-read the live buffer** (`/EditBufferStateGet`), mutate its
  `.hsp` form offline, encode `_sbepgsm`, **live whole-buffer push**. After the push,
  re-sync the editor from the echoed `/setEditBuffer` — the same code path as a
  preset load — so UI state stays truthful and undo can treat one topology edit as
  **one step**.
  - **Concurrency — decided (my call):** a whole-buffer push replaces the *entire*
    buffer, so unlike a granular op it can silently clobber a concurrent writer
    (hardware knob, HX Edit, another helixgen verb). Therefore a topology op
    **re-fetches `/EditBufferStateGet` (~0.6 s) immediately before mutate+push**,
    rather than trusting the buffer the editor is holding. 0.6 s on a deliberate
    structural edit is acceptable; the "no apply seam" anti-goal is about avoiding a
    *save + preset reload*, not about shaving sub-second latency off a structural
    change. Granular ops keep trusting the live-followed buffer (no re-read).
- Persist with the existing **Save** (`/SavePresetWithCID` on the active cid) /
  `device copy`; `device to-hsp` must round-trip the reshaped buffer.

### 8.2 New engine + protocol surface
- **`/ClearBlock [reqid, path, grid_slot]`** → `/clearBlock` echo (+ emit/replay
  `/removeSnapshotTarget` for the block's snapshot-bypass target). New verb; add to
  `docs/helix-protocol.md` §6 (the doc currently has **no** block-delete op).
  ⚠️ **Inferred from the 2001 echo, not yet captured as a 2002 command** — on the
  **pin-first** list below. If it can't be pinned it degrades gracefully to the
  whole-buffer push (tolerable, since clear is a buffer-level change anyway).
- **Whole-edit-buffer SET command** — the keystone of topology editing. The 2001
  echo is `/setEditBuffer`; the 2002 command is passively invisible. **Bounded
  spike (see §9):** it is almost certainly the write-twin of `/EditBufferStateGet`
  (which reads `_sbepgsm`); pin the verb, then this unlocks all topology ops. Strong
  evidence it is a true live write and not a disguised reload: the move/split echoes
  carried **no `/loadContentRef` and no CID change**, whereas a `/SetContentData` +
  `/LoadPresetWithCID` reload *does* emit `/loadContentRef`.

### 8.3 Model browser
- Source the catalog from the bundled defs helixgen already parses
  (`P35ModelCatalog.json` / `modeldefs/p35md-*.bin`, helix-protocol.md §8):
  categories (Input, Amp, Preamp, Cab, Effect, FX Loop, Send/Return, Split, Merge,
  Output, Looper, Clone, Poly), mono/stereo/legacy subcategories + each model's
  mono/stereo type, amp ordering (Agoura-type first, then HX-type), numeric
  `modelId` for `/ModelSet`.

### 8.4 Focus View deep editors
- **Params / EQ drag-band** → `/setParamValue` (granular; snapshot-aware per the
  live-write rules). EQ = band params mapped to drag; exclude Acoustic Sim.
- **Amp / preamp lens / XY morph** → multi-param morph across 5 zones; store up to
  8 lens positions as snapshots 1–8; "Based On" + I/O meters. ⚠️ **XY-zone storage
  is an open protocol unknown** (helix-protocol.md §9: inactive zones do **not**
  appear in the saved `_sbepgsm`). Resolve before building this editor (capture the
  app's lens-store sequence).
- **Cab** → mic position / distance / angle params; **IR frequency-response plot
  computed client-side** from the IR WAV (helixgen owns the IR library); Amp>Cab
  Link indicator + toggle (a harness setting).
- **Compressor / gate gain-reduction meter** → from the **2003 `/dspEvent`**
  telemetry grids (the per-node audio envelopes the loudness-feedback work decoded,
  ~10 Hz), mapped to the comp block.
- **Clone** → read-only metadata panel from the block's model/clone fields
  (Brand/Product/UUID/Notes/date).
- **Dual-cab 2nd slot** → the `/ModelSet` **`subpos`** arg is *assumed* to address
  the 2nd model; expose + edit it (own model/IR, pan, settings). Today only the
  primary model shows. ⚠️ **Unconfirmed:** every capture had `subpos = 0` and the
  block's `mdls` list was length 1, so a 2-model slot is not yet observed. On the
  **pin-first** list; if `subpos` is *not* the 2nd-model addressing, dual-cab 2nd
  slot becomes a topology-synthesis problem (see §8.6) rather than a simple write.

### 8.5 Inputs / outputs / metering
- Input block source select (Instrument, Mic, Return; Instrument 2 on XL); output
  Level; I/O signal + clip meters from the 2003 telemetry (green/red).

### 8.6 Engine prerequisite — topology SYNTHESIS (the long pole)
The unified-live model routes topology through "mutate the `.hsp` offline, encode,
push." That conflates two things the engine does **not** do equally well:
- **Topology preservation** (round-trip an existing chain, including cross-DSP taps
  via the `xbranch` pointer) — **solved** (`device to-hsp` is a fixed point).
- **Topology *synthesis*** (create a *new* split/merge, a 2nd cab slot, widen
  mono→stereo) — **NOT built.** Project record is explicit: parity doc "cannot add,
  remove, or move blocks"; memory "engine can't add split/join"; `helix-protocol.md`
  §9 "synthesizing a cross-DSP tap from scratch … unmodeled," the `hrns` harness
  dict per block still undecoded, and the bidirectional converter "the main lift."

Whether the new routing is expressed via `.hsp` mutate **or** by building the
`_sbepgsm` buffer directly, the engine must emit **device-native harness wiring**
(`hrns` / block-map / `bcnt` / `xbranch`) for brand-new routing — and the anti-goal
forbids a helixgen-only representation. **This engine work lands in helixgen-core
and is the long pole of the epic**: it must precede all topology UI, and its
feasibility gates the topology features (parallel routing, dual-cab 2nd cab,
mono↔stereo). Move/reorder of *existing* blocks is lighter (it rewrites slot
assignments, not harness wiring) and may land first.

**Decomposition + ordering (owner decision):** the work is two tracks — (A) **engine
topology-synthesis** in helixgen-core (decode `hrns`, model harness wiring, synthesize
split/merge + dual-cab + stereo-widen, prove byte-faithful round-trip); (B) the
**`device live` editor UI** (model browser, structural gestures, Focus View) that
consumes A for topology and the granular opcodes for everything else. **The owner
chose to do Track A first as its own helixgen-core epic**, then build 81v.1 (= Track
B, full UI incl. topology) on the finished engine. Track A needs its **own design
session** — it is a distinct project (protocol RE + engine, not UI) and should be
brainstormed on its own before implementation. 81v.1 is sequenced after it; the
pin-first capture spike (§9) feeds Track A's design.

## 9. What's left to the builder
- **Pin-first spike (do before committing topology UI):** on the live device,
  capture/confirm the three inferred 2002 commands — (a) the **whole-buffer-SET
  verb** (keystone; MITM the 2002 socket once, or probe the write-twin of
  `/EditBufferStateGet`), (b) **`/ClearBlock`**, (c) **dual-cab `subpos`** (place a
  real 2-model cab and confirm `subpos` addresses the 2nd). a→gates all topology;
  b→degrades to whole-buffer if absent; c→if wrong, dual-cab 2nd slot moves to the
  §8.6 synthesis track.
- **Contingency (Plan B) — decided (my call):** evidence is strong the live
  whole-buffer SET exists (§8.2). If it nonetheless can't be pinned or isn't safe
  live, topology falls back to Approach 2 (offline → `/SetContentData` → reload) as a
  **documented degraded mode with a visible apply step** — this deliberately relaxes
  the "no apply seam" anti-goal *only* in the fallback, rather than making topology a
  won't-do. Owner can override to "won't-do if not live."
- **Confirm `_sbepgsm` round-trip** of a structurally mutated buffer is
  byte-faithful (hrns / controller leaves) before trusting whole-buffer push for
  real presets — part of the §8.6 engine track.
- **Resolve XY-zone storage** (helix-protocol.md §9) before the amp-lens editor.
- **Split types** — the manual doesn't enumerate them; capture from the device.
- **Undo/coalesce policy** for a whole-buffer push (one topology edit = one undo
  step; history clears on preset/snapshot change as today).
- **DSP-headroom surfacing** for "DSP permitting" limits (up to 4 flows / 24–48
  locations) — only if the protocol exposes a headroom read; otherwise document as
  best-effort.
- **Mono↔stereo convert** caveat from the manual: controller + snapshot assignments
  are *not* kept; mono-only/stereo-only/Legacy excluded.

## 10. Acceptance
- A user builds a preset's signal chain from empty to multi-path, multi-block,
  dual-cab, with model selection and deep per-block editing, entirely in
  `device live` — no `.hsp` hand-edit, no Stadium app.
- Structural edits persist via the existing Save / `device copy` model and
  round-trip cleanly (`device to-hsp` ⇄ library) with no fidelity loss.
- Parity items the live protocol genuinely cannot do are documented won't-do with
  the reason, not left silently missing.

## 11. Capture evidence
Spike run 2026-11-21, Stadium XL (serial …381, fw 1.4.1 build 1343), Helix Stadium
app over USB, `helixgen device watch` over LAN 2001. Raw per-op captures were
session-scratch; the decoded opcodes + example args are recorded in §2 above and
are the authoritative record. Protocol facts to sync into
`helixgen-core/docs/helix-protocol.md`: `/clearBlock` (+ `/removeSnapshotTarget`);
the live whole-edit-buffer SET path (echo `/setEditBuffer`, in place, no reload);
confirmation that USB-originated app edits broadcast on network 2001.
