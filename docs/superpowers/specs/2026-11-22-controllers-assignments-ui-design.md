# Controllers & assignments UI parity (`helixgen-81v.3`) — design

**Status:** design — awaiting approval.
**Date:** 2026-11-22.
**Scope:** the **Controllers & assignments** area of the `device live` workspace
(parity-doc P1): bypass + parameter assignment to footswitches, expression pedals,
and MIDI; the Bypass/Control panel; min/max range (incl. reverse); stomp
label/colour; swap stomps; clear assignments; the XY controller.
**Manual:** [bypass-and-controller-assign](https://manuals.line6.com/en/helix-stadium/live/bypass-and-controller-assign)
(Owner's Manual v1.4 Rev D).
**Relation to the signal-flow epic (`81v.1`):** this is the controller/footswitch
area that `81v.1` and
[`2026-11-21-signalflow-editor-parity-design.md`](2026-11-21-signalflow-editor-parity-design.md)
hold **explicitly out of scope** (both their §4 non-goals list "controllers /
Command Center assignment"). It is a **sibling P1 epic**, not a sub-epic of the
signal-flow editor. §11 below flags the surfaces the two epics share.
**Command Center** (sources → commands: PC/CC/MMC/Hotkey/Looper) is a **separate
P2 epic** and is out of scope here; this epic is bypass + parameter control only.

---

## 1. Intent / why

`device live` today **reads** every controller assignment and renders it, but
offers **no way to edit one**. The live bridge already lifts, per block, from the
edit buffer: footswitch bypass controllers (`fs_bypass` — source + latching/
momentary + curve/threshold), parameter controllers (`ctl_params` — EXP sweeps
*and* FS param-toggles, with source/behavior/min/max), and MIDI-CC bindings
(`midi_bypass`, `midi_params`) — see `src/helixgen/device/bridge.py` `_ctl_meta`
/ `_ctl_params` and the per-block spec builder. So the display half is **done**;
the gap is **assignment** — learn a controller, drag a range, pick a source,
label a stomp, swap or clear.

To assign a controller today a user drops to the offline `.hsp` CLI
(`set-footswitch` / `set-expression` / `remove-*`) or to the Stadium Edit app.
This epic brings the assignment workflow into `device live`, heard immediately,
matching the Stadium Edit app's Bypass/Control screen and Quick/Learn flows.

The target is parity with the manual's **Bypass and Controller Assignment** page
(app v1.4 / fw 1.4).

---

## 2. The model decision — RESOLVED by existing captures (no new spike needed)

`81v.1` had to spike an unknown ("can the device do structural edits live?").
**This epic does not** — controller assignment is a **per-block leaf edit, not
topology**, and the live opcodes were already decoded in the 2026-07-14 parity
capture and the 81v.1 add-block capture. The question "live-only / dual-mode /
hybrid" is therefore already answered by what the Stadium app does on the wire.

### What the wire shows
The app assigns a controller with **granular 2002 opcodes**, no whole-buffer push
(`docs/helix-protocol.md` §6 "Live device control" + §"Command Center, MIDI/XY
controllers"; the 81v.1 add-block cascade, model spec §2):

| Assignment op | Live opcode(s) | Status in helixgen-core |
|---|---|---|
| FS/EXP **bypass** → block | `/attachBlockBypassControllerWithBlob` (`lrtcpgsm` blob) + `/setControllerSource` + `/setSourceEnable` | decoded; **no client method yet** |
| FS/EXP **param** control | `/attachParamController` (+ source) | decoded; **no client method yet** |
| **MIDI** CC source | `/ControllerMIDISourceAdd` (CC# = BE uint16 @ blob off. 12; no channel) | decoded; **no client method yet** |
| **Stomp label / colour / source** | `preset.floorboard.stomp.*` / `preset.sources` property writes | decoded (read side synthesized in bridge); **no live write yet** |
| **Clear** block's snapshot-bypass target | `/removeSnapshotTarget` | decoded (seen in 81v.1 clear capture) |

These are **granular** — the same class as param/bypass, which `device live`
already writes live. There is **no** evidence the app pushes a whole buffer to
assign a controller.

### Decision: **granular-live, offline-`.hsp` as substrate + Save**
- **Assign / re-range / re-label / clear live** via the granular opcodes above —
  heard at once, no apply seam, exactly as the app does it.
- The engine's **mature offline controller path** (`mutate.wire_footswitch` /
  `wire_expression` / `wire_midi` / `wire_wah_toe`, `remove_*`) is **not thrown
  away**: it stays the authority for `.hsp` round-trip and for the **Save** that
  persists an assignment, and it is the **fallback writer** (§2 Plan B).
- **Plan B (fallback), decided:** two opcodes carry an opaque blob whose
  synthesis is not yet proven live — `/attachBlockBypassControllerWithBlob`'s
  `lrtcpgsm` blob and `/ControllerMIDISourceAdd`'s CC-offset blob. For any
  assignment whose live blob can't be synthesized byte-faithfully (pin-first,
  §9), fall back to the **81v.1 unified-live whole-buffer push**: mutate the live
  buffer's `.hsp` form with the existing `wire_*` op, encode `_sbepgsm`, live
  whole-buffer SET. This is the *same* fallback 81v.1 uses for topology and reuses
  the *same* mature offline path — so the worst case is a sub-second re-push, not a
  won't-do. Param-source assignment (`/attachParamController` + `/setControllerSource`)
  has no opaque blob and should land granular first.

This matches the app's own model and reuses the battle-tested offline mutate +
transcoder path that already round-trips controllers byte-faithfully in `.hsp`.

---

## 3. Engine-readiness — explicit

| Capability | Readiness | Notes |
|---|---|---|
| **Read** every FS/EXP/MIDI assignment from the live buffer | ✅ **shipped** | `bridge.py` already emits `fs_bypass`/`ctl_params`/`midi_bypass`/`midi_params` per block; the UI renders existing state with zero new engine work. |
| **Offline `.hsp` write** + byte-faithful round-trip | ✅ **shipped** (core 0.58) | `set-footswitch` (bypass / param-toggle, latching/momentary, label/colour/curve/threshold, merge = multi-target last-wins), `set-expression` (sweep, **reverse via min>max**, multi-target), `remove-footswitch`/`remove-expression`, `wire_wah_toe` (EXP1Toe auto-engage). Controllers live in the **decoded** `cg__.entt` maps (`docs/helix-protocol.md` §9). |
| **Live granular write** (assign/re-range/clear) | 🟡 **new core work, on DECODED ground** | Opcodes known (§2 table); needs client methods on `device/client.py` + the two opaque-blob syntheses pinned. Materially lighter than 81v.1's topology-synthesis — **no undecoded structure to reverse** for FS/EXP/MIDI-CC. `set_block_model` already notes the app "re-attaches controllers … (not replayed here)" — that replay is exactly this work. |
| **Whole-buffer-push fallback** | 🟡 **shared with 81v.1** | Depends on the same live whole-buffer SET keystone 81v.1 pins (§9, §11). |
| **MIDI CC binding** | 🟡 **partial** | `wire_midi` is CC-only and stored in a **helixgen-namespaced** `preset._helixgen_midi` sidecar, *not* the device-native wiring — reconcile with `/ControllerMIDISourceAdd` before claiming native MIDI parity (§9). |
| XY controller / external FS / triggers as sources | 🔴 **not modeled** | See §6 won't-do / deferred. |

**Bottom line:** read + offline-write + round-trip are done; the live-write
opcodes are decoded but unexposed. This is **heavy UI over mostly-existing engine
ground**, with one bounded pin-first capture (two blobs) rather than a new
engine epic.

---

## 4. Goals (what the UI delivers)

Mapped to the manual and the parity checklist:

- **Quick Bypass Assign** — select a block, pick a footswitch, choose **Replace/
  Merge** (default Merge) and **Momentary/Latching** (default Latching), set
  **Label/Color**. (Input/Output/Merge blocks refused; Split blocks allowed —
  manual.)
- **Learn** — a "learn" affordance on a block (bypass) or a parameter (control):
  arm it, then the next FS press / EXP move / MIDI CC captured becomes the source.
  A UI event ("I pressed this stomp") stands in for the hardware gesture, routed
  as a granular assign to that source.
- **Bypass/Control panel** per block/param, mirroring the app's Knob-1-selects
  Bypass-or-param model:
  - **Switch/Controller source** picker — the §6 source set.
  - **Type** (Stomp / ext FS): Latching | Momentary.
  - **Position** (EXP): 0–99% travel point where it switches.
  - **Wait** (EXP): delay before bypass (no numeric range published — surface the
    device's own range if the protocol exposes it, else a raw field).
  - **Behavior** (EXP bypass): Toggle | Toe Down | Heel Down.
  - **MIDI In**: None | Note | CC0–CC127 (CC 0–63 = off, 64–127 = on).
- **Min/Max range drag** on a parameter: white min/max nodes on the value slider,
  draggable; **reverse** by dragging min past max (engine already accepts min>max
  as an inverted sweep — `wire_expression`). Default min/max read from the
  block/param.
- **Stomp label + LED colour** — ≤12-char label (`set-footswitch --label`),
  colour swatch incl. **Auto** (block-type default) and **Off**
  (`set-footswitch --color`; vocabulary already in `controllers.py`).
- **Swap stomps** — pick two stomp-mode footswitches → swap, keeping labels,
  colours and multiple assignments.
- **Clear** — per-param **Clear Controllers**, per-block **Clear Assignments**,
  preset-wide **Clear All Assignments** (with the manual's confirm prompt).
- **XY Controller** — assign params to X/Y, drag the node (see §6 for the
  rubber-band / persistence caveat).
- Every assignment is **heard immediately** (granular live write), **persists via
  the existing Save / `device copy`**, and **round-trips `.hsp` ⇄ library** with
  no fidelity loss.
- Parity items the live protocol genuinely can't do are **won't-do with the
  reason** (§6), never silently missing.

## 5. Non-goals (other epics)
Command Center (sources → PC/CC/MMC/Note/Hotkey/Looper/Utility commands — P2);
Snapshots management incl. snapshot-controlled parameters and the per-snapshot
"white value" toggle (P1 snapshots epic — a *snapshot* is a controller source the
manual mentions but documents under Snapshots); Global settings (Switches/Pedals,
"Assign FX to Stomps" auto-assign policy — P2); the signal-flow structural editor
and Focus View (`81v.1`).

## 6. Won't-do / deferred — with the reason (same discipline as 81v.1 §9)

- **MIDI channel per assignment — WON'T-DO (protocol limit).** `/ControllerMIDISourceAdd`
  carries the CC# but **no channel** (`docs/helix-protocol.md` §"MIDI/XY
  controllers"); channel is global. The UI documents channel as a global setting,
  not a per-assignment field.
- **MIDI *Note* bypass/control — DEFERRED (engine gap, capture-gated).** The device
  supports Note sources; `wire_midi` is **CC-only** by explicit design ("MIDI Note
  sources are out of scope"). Needs an offline-model + live-opcode extension; low
  value vs CC. Surface MIDI In as None | CC only until then.
- **External footswitches / drum triggers / contact mics (CONTROL A/B, C/D on XL)
  — DEFERRED (not modeled, capture-gated).** `controllers.py` models only FS1–5,
  FS7–11, EXP1, EXP2, EXP1Toe — no source IDs for the external CONTROL jacks, and
  they need physical external hardware to validate. Capture their source IDs before
  exposing.
- **XY Controller rubber-band runtime + "Rubber Band Time" — PARTIAL / pin-first.**
  *Assigning* a param to an X/Y axis routes through the controller-source path like
  any source and is in scope. But the **live node position is a performance control,
  not persisted**, and **XY-zone storage in `_sbepgsm` is an open unknown shared with
  81v.1's amp-lens editor** (`/SetBatchedParamValues` activates a zone live but
  inactive zones do **not** appear in the saved buffer — `docs/helix-protocol.md`
  §9). So: ship XY param *assignment* + a live rubber-band node; **defer persisted
  XY state** until that storage is resolved, and document it. Rubber Band Time range
  is unpublished (capture).
- **"Assign FX to Stomps" auto-assign policy** is a **Global Setting**, not
  per-preset — belongs to the P2 global-settings epic; the UI honours whatever the
  device does on add (it already sees the auto-assigned stomp via the 2001 echo).

## 7. Anti-goals (a failure even if it technically works)
- A **visible "apply controllers" step** — assignment must be as seamless as a knob
  turn (the whole point of granular-live; the whole-buffer fallback is sub-second
  and only for un-pinnable blobs).
- **Fidelity loss on controller round-trip** — an assigned/re-ranged controller
  that doesn't come back byte-faithfully through `.hsp` ⇄ `_sbepgsm` (the `cg__.entt`
  controller leaves).
- **A second, divergent live-controller client** that duplicates the one 81v.1's
  add-block cascade already needs (§11) — the stomp-assign / bypass-controller-attach
  opcodes are shared; build one module.

## 8. The how — decided

### 8.1 Edit routing
- **Assign / re-range / re-label / clear** → granular live opcodes (§2 table) via a
  **new shared live-controller client** (`device/client.py`), with each op's 2001
  echo applied idempotently (never re-write on echo — the existing live-ops rule).
- **Blob-bearing ops** (`attachBlockBypassControllerWithBlob`, `ControllerMIDISourceAdd`)
  → granular once the blob synthesis is **pinned** (§9); until then, the **whole-
  buffer-push fallback** (mutate `.hsp` with `wire_*`, encode, live SET) — reusing
  81v.1's path. Param-source assignment (no blob) lands granular first.
- **Follow the device** — after any assignment the panel re-syncs from the 2001
  echo, the same path a hardware/HX-Edit assignment already takes; a block move or
  model-swap from 81v.1 re-indexes footswitches, and the controller panel must
  reflect that re-index from the echo, not a cached view.
- **Persist** via the existing **Save** (`/SavePresetWithCID`) / `device copy`;
  `device to-hsp` must round-trip the assignments (already true for `wire_*` output).

### 8.2 New engine + protocol surface (helixgen-core)
- Client methods wrapping the §2 opcodes: `attach_param_controller`,
  `attach_block_bypass_controller`, `set_controller_source` / `set_source_enable`,
  `add_midi_source`, `remove_snapshot_target`, and the `preset.floorboard.stomp.*`
  / `preset.sources` property writer for label/colour/source + swap.
- **Blob synthesis** for `lrtcpgsm` (bypass controller) and the CC-offset blob —
  the two pin-first unknowns (§9). The offline `.hsp` already encodes equivalent
  controller leaves byte-faithfully, so the field content is known; what's unproven
  is the **live blob framing**.
- **Agent-surface sync (CLAUDE.md "ship in sync"):** the new live-controller facts
  land in **helixgen-core** first (client + `docs/helix-protocol.md`), with a
  companion plugin PR updating `skills/*` + synced `docs/` once the live-assign CLI
  verbs exist (today's controller verbs are offline-only).

### 8.3 Reusing the read model
The UI's "show current assignments" is `bridge.py`'s existing per-block
`fs_bypass` / `ctl_params` / `midi_bypass` / `midi_params`. **No new read work** —
the editor already has the data; this epic adds the *edit* affordances over it.

## 9. What's left to the builder
- **Pin-first capture (before committing the blob-bearing live paths):** drive the
  Stadium app through (a) a **bypass assign** and capture the `lrtcpgsm` blob of
  `/attachBlockBypassControllerWithBlob`; (b) a **MIDI CC assign** and confirm the
  `/ControllerMIDISourceAdd` CC-offset framing. a,b → gate granular; if un-pinnable,
  both degrade to the whole-buffer-push fallback (tolerable — §2 Plan B).
- **Reconcile MIDI storage:** `wire_midi`'s helixgen-namespaced `_helixgen_midi`
  sidecar vs the device-native `cg__.entt`/`ControllerMIDISourceAdd` wiring — decide
  whether live MIDI assign writes native (and whether to migrate the sidecar) before
  claiming native MIDI parity.
- **Confirm controller-leaf round-trip** of a live-assigned buffer is byte-faithful
  (`cg__.entt` leaves) before trusting the whole-buffer fallback for real presets —
  shared with 81v.1's §8.6 round-trip proof.
- **Capture gaps the manual leaves open:** EXP **Wait** range/units, **Rubber Band
  Time** range, external-CONTROL source IDs, full colour-swatch list + label char
  limit (helixgen already caps label ≤12).
- **XY-zone storage** (shared with 81v.1 amp-lens) before persisting XY state.
- **Merge semantics:** confirm the device's merge-switch last-wins matches
  `wire_footswitch`'s multi-target model under live assign (one switch → several
  blocks), and the per-target `remove-footswitch --block`.

## 10. Acceptance
- A user assigns and edits bypass + parameter controllers (FS latching/momentary +
  merge/replace; EXP position/wait/behavior; MIDI CC; min/max incl. reverse; stomp
  label/colour; swap; clear per-param/block/preset) **entirely in `device live`**,
  heard immediately — no `.hsp` hand-edit, no Stadium app.
- Assignments persist via the existing Save / `device copy` and round-trip
  `.hsp` ⇄ library with no fidelity loss.
- Won't-do items (§6) are documented with their reason, not silently missing.

## 11. Collision surface with the signal-flow epic (`81v.1`) — flag for the owner
These two P1 epics **share live surfaces**; build the shared parts once.

- **Shared live-controller opcodes.** 81v.1's **add-block cascade** already emits
  `/attachBlockBypassControllerWithBlob`, `/setControllerSource` + `/setSourceEnable`,
  and **auto-assigns a stomp** for a new Effect/Looper/FX-Loop (model spec §2). That
  is the *same* opcode set this epic exposes for manual assignment. → **One shared
  live-controller client module**, consumed by both; do not fork it. Sequencing
  note: whichever epic lands first should land that module.
- **Shared whole-buffer SET keystone.** This epic's Plan-B fallback and 81v.1's
  entire topology path both ride the live whole-buffer SET (§2) and the
  `/EditBufferStateGet` re-read-before-push concurrency rule (81v.1 §8.1). Pin it
  once.
- **Footswitch re-index on topology edits.** 81v.1's move/split emits a batch of
  `preset.floorboard.stomp.*` re-index writes — the *same* property namespace this
  epic writes for label/colour/source. A topology edit can move the stomp a
  controller panel is showing; the panel must re-sync from the echo (§8.1). → Agree
  a single owner of the `preset.floorboard.stomp.*` surface.
- **Snapshot-bypass target** (`/assignSnapshotBypass` / `/removeSnapshotTarget`) is
  touched by this epic's clear, 81v.1's add/clear cascade, **and** the P1 snapshots
  epic. → Three-way shared; the snapshots epic should own snapshot-bypass semantics.
- **Shared open unknown:** XY-zone `_sbepgsm` storage blocks both this epic's
  persisted-XY and 81v.1's amp-lens editor. One capture resolves both.

## 12. Capture evidence / provenance
Grounded in: `docs/helix-protocol.md` (§6 Live device control, §"Command Center,
MIDI/XY controllers", §9 known-unknowns); the 2026-07-14 parity capture and the
81v.1 add-block/clear capture (model spec §2); and the shipped offline path in
`helixgen-core` `src/helixgen/mutate.py` (`wire_footswitch`/`wire_expression`/
`wire_midi`/`wire_wah_toe`, `remove_*`), `src/helixgen/controllers.py` (source
vocabulary FS1–5/FS7–11/EXP1/EXP2/EXP1Toe + colours), and `src/helixgen/device/
bridge.py` (the shipped read model). Manual: Owner's Manual v1.4 Rev D,
bypass-and-controller-assign. No new hardware capture was run for this design; the
two pin-first blobs (§9) are the only items requiring one before implementation.
