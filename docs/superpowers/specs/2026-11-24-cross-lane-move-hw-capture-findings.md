# Cross-lane block move — HW capture findings (2026-11-24)

**Status:** investigation findings, feature NOT shipped (blocked — see below)
**Context:** last prominent `device live` editor-parity gap — dragging a block
between an existing lane A and lane B (as distinct from `add_split`/drag-to-split,
which *builds* a fresh split). Decoded by frida-capturing the Helix Stadium app
driving the owner's Stadium XL (fw 1.4.1), preset 25A "Avenged Sevenfold" (cid 1998).

## What was captured

Attached frida to the running Stadium app (`tools/hook_sockets.js`), drove the
editor via computer-use to drag lane-A blocks toward lane B, and decoded the
resulting `/doAgenda` msgpack. Three distinct drags produced:

| drag (drop column) | emitted op                         |
|--------------------|------------------------------------|
| col 4 → lane B     | `movb bl_s=4 bl_d=18 fl_s=0 fl_d=0` |
| col 2 → lane B     | `movb bl_s=4 bl_d=16 fl_s=0 fl_d=0` |
| col 6 → lane B     | `movb bl_s=6 bl_d=20 fl_s=0 fl_d=0` |

## Finding 1 — the op is a SINGLE bare `movb`, not an orchestration

A cross-lane move is **one** `movb col → (col + 14)` op in a `/doAgenda`
transaction — NOT the multi-op `split_out` orchestration (move + shift + split +
join). `bl_d = drop_col + LANE_B_OFFSET(14)` exactly; the app computes the lane-B
destination purely from the drop column. This **contradicts** the pre-capture
assumption (carried in the earlier session summary) that cross-lane move "needs an
orchestrated transaction like add_split." It does not. The op shape already exists
in `agenda.move()`.

## Finding 2 — the device REJECTED every such movb (no-op, no corruption)

All three ops left the live edit buffer **unchanged** (verified via
`HelixClient.edit_buffer_blocks()`: laneA `[0..8,11,13]`, laneB `[14,15,27]`,
`preset_edited=False` throughout). The device silently ignores a `movb` into an
existing "App DSP Split Y" lane B — both a gap target (slot 18, with 16/17 empty)
AND a contiguous target (slot 16, right after the existing slot-15 lane-B block).
No corruption occurred. Each attempt left only a transient empty selected lane-B
slot in the app UI, cleared by `device load 1998`.

**Implication:** incremental block-moves into an *existing* split's lane B may not
be a device-supported operation at all — lane B of a configured Split Y appears
fixed. Populating lane B is done by *building* the split (`split_out`), not by
moving blocks into one after the fact. This is the unresolved "A/B lane encoding"
decode item flagged in `2026-11-21-topology-synthesis-engine-design.md` §"still to
decode".

## Finding 3 — the earlier corruption was helixgen's path, not the device

The pre-compaction spike that corrupted the buffer used **helixgen's own**
`client.move_block` (a bare cross-lane `movb` via `agenda.move`). The Stadium app
emits the *same* op shape, yet the device safely no-ops it. So helixgen's
cross-lane `move_block` has a latent bug (it fires a `movb` the device won't honor
and then races the readback), while the device itself just ignores an invalid app
move. `client.move_block` should keep its current lane-A-only guard until a
confirmed-applying cross-lane op is captured.

## Why it's blocked (autonomous wall)

Never captured a **confirmed-applying** cross-lane move:
1. `app_drag` delivers the whole path in <1s with no press-and-hold, so the gesture
   registers as "create empty parallel slot" rather than "pick up block and move to
   lane B." Every drag created an empty lane-B slot; the source block stayed on lane A.
2. Even if the gesture landed, the existing Split Y rejected the movb (Finding 2).

## To finish (well-scoped)

- **Owner-assisted capture:** owner performs 3–4 real block→lane-B drags in the
  Stadium app (fresh simple split; move into it; move back; move within lane B)
  while the frida recorder (`scratchpad/agenda_recorder.py`, targets the MAIN
  'Helix Stadium' pid — helper subprocesses reject frida attach) runs. Decode the
  *applying* ops to learn the device-acceptance rule and the correct `bl_d`.
- **OR** accept that lane B is build-only: expose cross-lane *via rebuild*
  (remove+re-add split with new lane-B contents) rather than incremental move.
- Then wire into `client.move_block` (drop the lane-A-only guard for the proven
  case) + liveedit UI, unit-test the agenda builder, scratch-HW validate, ship
  core + plugin.

## Follow-up: code-driven test (partially confounded)

Tried to answer the crux ("does a movb into a *freshly-built, properly-wired*
split's lane B apply?") via helixgen directly (no fragile app drag), in a scratch
buffer (loaded "Dry" cid 2118):

- `set_block_model` ×4 + `add_split(0, 2)` built a **clean** fresh split: block 2
  → lane B slot 16, split node at 2, join at 3, later blocks shifted right.
  `add_split` is solid. ✓
- **BUT between script runs the edit buffer changed out from under me** — the
  device switched to an *edited* "Muse" preset (cid 1724, slot 11A), which I never
  loaded. Another actor (owner at the hardware, or a concurrent session sharing
  the LAN device) was using it. `move_block(0,4,17)` then ran against the Muse
  buffer and **no-op'd** (layout identical before/after) — consistent with every
  prior bare-movb-into-lane-B result, but NOT the clean fresh-split test I intended.
- **Halted all device interaction** at that point. Did not reload (would clobber
  the active edit). A7X (1998) was verified restored earlier; stored Dry (2118)
  never saved. The definitive fresh-split cross-lane test remains **unrun** — needs
  exclusive device access.

**Net:** bare `movb col→col+14` into lane B no-op'd on two different existing
splits (A7X, Muse) and via both the app and helixgen. The clean fresh-split case
(whether a wired 1-wide split can be *extended* by a movb, or needs the join
shifted like `split_out`) is the one remaining unknown, and needs the device to
itself.

## DEFINITIVE: a bare `movb` cannot extend lane B — not even a fresh split

Ran the clean fresh-split test successfully (rig was idle on 11B; scratch "Dry"
buffer; one connection; restored to 11B in a `finally`):

- `add_split(0, 2)` built a clean 1-wide split: laneA `[0,1,2(Split),3(Join),
  4,5,13]`, laneB `[14,16(amp),27]`.
- `move_block(0, 4, 17)` to extend lane B (add a 2nd lane-B block at col 3) →
  **NO-OP.** Buffer byte-identical before/after; no slot 17 appeared.

So the device rejects a bare `movb` into a lane-B slot outside the split's current
wired span — on a FRESH split just as on the A7X one. Combined with the app
captures (its `movb 4→16/18` also no-op'd), the conclusion is firm:

**Cross-lane move = extending lane B is NOT a bare `movb`. It needs an orchestrated
transaction like `split_out`** — shift the join (and later lane-A blocks) right to
open a lane-B column, move the block into the new slot, re-wire `spld`/`jono`. That
orchestration MUST be capture-pinned (project discipline), and the one capture I
could not get is the Stadium app SUCCESSFULLY extending a split's lane B — my
raw-input drags only ever created empty placeholders, never a committed extension.

**To finish 81v.16:** owner-assisted frida capture of a real, visibly-applied
lane-B extension in the Stadium app (owner drags a 2nd block into a split's lane B;
recorder running), then synthesize `extend_split`/`move_to_lane_b` from the capture,
unit-test the agenda, scratch-HW validate, ship. No bare-`movb` shortcut exists.

## SOLVED (2026-11-24) — bundled `/doAgenda` commits a lane-B move (HW-validated)

The bare `movb` orphans because the device commits a lane-B move only when the
`movb` rides in the SAME `/doAgenda` as the `spld`/`jono` wiring — exactly how
`split_out` builds a fresh split. **Moving a lane-A block into a split's lane B:**

```python
do_agenda([
    move(src, join_slot + 14, flow, flow),  # block -> the join's lane-B merge slot
    split(split_slot, first_lane_b, flow),  # re-assert the split's B entry
    merge(join_slot, join_slot + 14, flow), # join now merges from the new last block
])
```

HW-validated on a Stadium XL (scratch Dry buffer, restored to 11B): a fresh
1-wide split (split@2 `bblk=16`, amp@16, join@3 `bblk=17`) + this transaction
moving lane-A slot 4 → lane-B slot 17 produced a sound 2-wide series lane B:
laneB `[14,16(amp),17(dynplate),27]`, split@2↔16, join@3↔17, all `bblk` consistent,
no corruption. The new block lands at `join_slot + 14` (the join's merge slot,
previously empty); the join re-wires to merge from it; the split's entry is
re-asserted unchanged.

**Covers the common case** (append a block to a split's lane B — the 1-wide→2-wide
parallel move). A lane-B series already filling the join's merge slot (N-wide→N+1)
would additionally need the join + later lane-A blocks shifted right first (the
`split_out` shift step) before the bundled move — not yet HW-tested. Removing from
lane B / moving back to lane A is the inverse and also untested.

**81v.16 is now implementable** (no app capture needed): add a `move_into_lane_b`
agenda builder, a client method that reads the split's slots and issues the bundled
transaction, the liveedit drag handler, unit tests, HW-validate the general builder,
ship core + plugin.

## Recorder reuse

`scratchpad/agenda_recorder.py` — non-interactive; attaches to the main Stadium
process, streams all 2001–2003 OSC frames (base64) to JSONL, flags `/doAgenda`.
Decode: 2-byte len prefix, `/doAgenda\0` padded, `,ib` typetag, int reqid, int
bloblen, msgpack blob = list of op dicts (`cmnd` = big-endian 4CC).
