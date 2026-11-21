# Engine topology-synthesis (helixgen-core) — design

**Status:** design — pre-approved by owner (standing approval for design docs this
session). Lands in **helixgen-core**.
**Date:** 2026-11-21.
**Why it exists:** it is the **engine prerequisite** the `device live` signal-flow
editor epic (`helixgen-81v.1`,
`docs/superpowers/specs/2026-11-21-signalflow-editor-parity-design.md` §8.6) is
gated on. Owner chose **engine-first**: build this, then 81v.1's topology UI on top.

---

## 1. Intent / why

helixgen can **preserve** an existing signal-chain topology through a round-trip
(`device to-hsp` is a fixed point, including cross-DSP taps via the `xbranch`
pointer) but cannot **synthesize** new topology: it can't create a split/merge,
add a parallel lane, populate a dual-cab 2nd model slot, or widen a block
mono→stereo. The device's routing lives in a per-block harness (`hrns`) + branch
pointers + a flow block-map that helixgen does not yet model or emit.

This epic decodes that representation and teaches the engine to **author
device-native routing from scratch**, proven byte-faithful by the existing export
round-trip net, and exposes it on the CLI. It also pins the **live whole-edit-buffer
SET** command so `device live` can push a synthesized topology **live** (no reload),
which is how `helixgen-81v.1` avoids an "apply" seam.

Beneficiaries beyond 81v.1: the bass parallel-dirt rule (needs a clean parallel
lane the engine currently "can't add split/join"), and any future authored preset
with parallel routing or dual cabs.

## 2. What the 2026-11-21 spike already established (don't re-derive)

**Op classes on the live wire** (captured driving the Helix Stadium app over USB,
watching network 2001; see the 81v.1 design §2 and
`[[project_live_whole_buffer_set_exists]]`):
- Granular live opcodes exist for param / bypass / **model-swap & add** (`/ModelSet`
  → `/setModelWithMID [_, _, path, grid_slot, subpos, modelId, -1]` + cascade) /
  **clear** (`/clearBlock [_, _, path, grid_slot]` + `/removeSnapshotTarget`).
- **Topology (move, split/parallel) has no granular opcode** — the app replaces the
  **whole edit buffer in place**: one `/setEditBuffer` (full `_sbepgsm`), **no
  `/loadContentRef`, no CID change, no reload**. A live whole-buffer SET path exists
  (the protocol doc assumed it didn't); its 2002 command verb is still unpinned.

**The topology representation** (decoded first-pass from a real parallel preset,
Stadium XL fw 1.4.1, `device pull <cid> x.sbe` + `device decode x.sbe`):
`sfg_.flow[dsp]` holds `bcnt`, `enbl`, `bmap`, `blks`. Per flow:
- **`bmap`** — list of length `bcnt`, maps logical block index → grid slot
  (identity `[0,1,…,27]` in a contiguous chain). **The move/reorder lever.**
- **`blks`** — `[grid_slot:int, block:dict, …]`. Each block dict carries:
  - **`mdls`** — list of model dicts (the specific model(s); `id__` = numeric model
    id, `parm` = its params). Length 1 today — a **dual-cab 2nd model would be
    `mdls[1]`** (or the `/ModelSet` `subpos` slot; unconfirmed — pin it).
  - **`hrns`** — an always-present, model-shaped **harness descriptor**: `id__` is a
    **harness-type id shared by blocks of the same category** (e.g. 778 for I/O, 479
    for cab-ish), with its own `parm` list = **harness-level settings** (this is where
    Trails / Amp>Cab Link / block-type defaults live). Distinct from `mdls[0].id__`.
    *Synthesis must populate `hrns` correctly for a new block — the add-block cascade
    (`/setModelWithMID` + property defaults) is the device doing exactly this.*
  - **`hasb` / `bflw` / `bblk`** — **the branch pointer**: has-branch,
    branch-target-flow, branch-target-block(slot). This is how splits / parallel
    lanes / cross-DSP taps are wired (observed in 11B: input→`bflw1 bblk11`
    cross-DSP; mid-chain `bflw0 bblk{15,20,25}` within-flow branches). The `.hsp`
    `xbranch` key already carries `{flow,bblk}` verbatim for round-trip; **synthesis
    must *generate* these**, which §9 of the protocol doc calls unmodeled.

## 3. Goals
- **Decode the harness fully**: `hrns` parm semantics (map to named settings incl.
  Trails, Amp>Cab Link); the **A/B lane encoding** within a flow (how split/merge
  blocks and their lanes are represented beyond the branch pointer); split **types**
  + balance, merge pan A/B.
- **Synthesize** device-native routing offline: add/remove a split & merge; add a
  parallel lane (incl. drag-down auto-split equivalent); dual-cab 2nd model slot;
  mono↔stereo widen (dropping controller/snapshot assignments per the manual);
  reorder (rewrite `bmap`).
- **Byte-faithful round-trip**: a synthesized topology survives `.hsp` ⇄ `_sbepgsm`
  ⇄ device with no fidelity loss, verified against the export round-trip net.
- **Live whole-buffer SET**: pin the 2002 command verb and add a device-client call
  that pushes a whole `_sbepgsm` into the live edit buffer (echo `/setEditBuffer`,
  no reload). Add `/ClearBlock` as a first-class verb.
- **CLI surface**: expose the new structural ops (behavioral contracts in per-verb
  `--help`, parity-pinned) so skills + `device live` drive them via CLI, not source.

## 4. Non-goals (other epics)
The `device live` **editor UI** and Focus View (that's `helixgen-81v.1`). Snapshots,
controllers/Command Center, global settings/EQ, Matrix Mixer, tuner, librarian.

## 5. Anti-goals
- A **helixgen-only routing representation** — the engine must emit the device's own
  `hrns`/`bmap`/`hasb`-`bflw`-`bblk` wiring, not a parallel abstraction.
- **Silent fidelity loss** — a synthesized or reordered chain that doesn't round-trip
  byte-faithfully. The export net must gate it.
- Shipping synthesis **un-validated on hardware** — routing that passes tests from
  source but was never loaded + played on a real Stadium.

## 6. Constraints
- Lands in **helixgen-core** (PyPI `helixgen`); the plugin bumps its pin + ships a
  companion PR (skills + synced `docs/helix-protocol.md`, `CLI.md`,
  `recipe-reference.md`) — agent-facing surfaces ship in sync across repos.
- Work in a git worktree branched from fresh `origin/main`; adversarial review before
  merge; HW-validate on the owner's Stadium XL.
- The export round-trip net (`tests/` 211-export fidelity) is the correctness gate;
  mutate guards stay permissive to match hardware.
- Skills/consumers drive the CLI; behavioral contracts live in per-verb `--help`
  (pinned by `tests/test_cli_parity.py`).

## 7. Approach
1. **Finish the decode** by controlled diff (recipe §9): capture a **series preset →
   add one split** (and → add dual-cab, → widen mono→stereo) via the app while
   watching 2001, `device pull`+`decode` before/after, diff the `sfg_` region. That
   isolates exactly which `bmap` / `hasb`/`bflw`/`bblk` / `hrns` / lane fields a split
   (etc.) sets.
2. **Model the harness** in the engine's content model (the `_sbepgsm` ↔ `.hsp`
   bridge, `defs.py` numeric↔name): represent `hrns` params + branch pointers + lane
   structure as first-class, round-trip-preserving fields (extend the existing
   `xbranch` carriage).
3. **Synthesis ops** in `mutate`/patch: `add_split`/`remove_split`,
   `add_parallel_lane`, `set_dual_cab`, `convert_mono_stereo`, `move_block`
   (bmap rewrite) — each emits device-native wiring and defaults `hrns` the way the
   add-block cascade does.
4. **Device client**: pin + add the **whole-buffer SET** RPC (probe the write-twin of
   `/EditBufferStateGet`, or MITM the app's 2002 socket once); add `/ClearBlock`.
5. **CLI verbs** + `--help` contracts; **sync docs**; **HW-validate**; plugin
   companion PR bumps the pin.

## 8. Acceptance
- The engine authors a preset from a flat series chain into multi-lane parallel,
  dual-cab, mono+stereo blocks — entirely offline — and it loads + plays correctly on
  a real Stadium XL and round-trips `.hsp` ⇄ device byte-faithfully.
- `device live` can push a synthesized topology **live** (whole-buffer SET, no reload)
  and `/ClearBlock` works as a first-class op.
- Routing the protocol genuinely can't synthesize is documented won't-do with the
  reason.

## 9. What's left to the builder (first tasks, ordered)
1. **Pin the whole-buffer-SET 2002 verb** (keystone). Recipe: MITM the app↔device
   2002 socket during a move/split, **or** probe candidate verbs from helixgen (try
   the write-twin of `/EditBufferStateGet`, send a known-good `_sbepgsm`, confirm the
   `/setEditBuffer` echo with no `/loadContentRef`). Also confirm **`/ClearBlock`** and
   **dual-cab `subpos`/`mdls[1]`** addressing the same way.
2. **Finish the lane/split decode** via the §7.1 before/after diff recipe — the one
   real unknown is how A/B lanes + the split/merge blocks themselves are encoded
   (vs. just the branch pointer).
3. **`hrns` parm semantics** — map harness params to named settings (Trails,
   Amp>Cab Link, …).
4. **Round-trip proof** of a *synthesized* buffer before trusting it on real presets.
5. Decide the **CLI verb shape** (extend `mutate`/patch vs new `device`/offline
   verbs) consistent with the existing surface.
6. **Mono↔stereo caveat** (manual): controller + snapshot assignments are not kept;
   mono-only/stereo-only/Legacy excluded.

## 10. Capture / decode recipe (reproducible on this machine)
- Watch: `helixgen device watch --seconds N` (2001/2003; `grep -v dspEvent` to cut
  telemetry). USB-originated app edits **do** echo on network 2001.
- Pull + decode a preset: `helixgen device pull <cid> out.sbe` (non-activating) then
  `helixgen device decode out.sbe` → JSON with `cg__`/`pm__`/`sfg_` (4CC keys).
- Diff method: do the structural edit in the app, `pull`+`decode` before/after, diff
  the `sfg_.flow[dsp]` region (`bmap`, each block's `hasb`/`bflw`/`bblk`/`hrns`).
- `HELIXGEN_LIBRARY` must be set (bundled `data/library` in the plugin, or the user's
  `~/.helixgen/library`) or `list-blocks` silently returns empty.

## 11. Protocol facts to upstream into `helixgen-core/docs/helix-protocol.md`
`/clearBlock` (+ `/removeSnapshotTarget`); the live whole-edit-buffer SET path (echo
`/setEditBuffer`, in place, no reload) once the verb is pinned; the `hrns` harness
characterization (harness-type id + params) and `bmap`/`hasb`/`bflw`/`bblk` as the
decoded routing representation; USB app edits broadcast on network 2001.
