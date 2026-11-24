# `device live` editor — canvas + focus UX design

**Status:** design **approved** (owner, 2026-11-24). Implementation plan:
[`plans/2026-11-24-live-editor-canvas-stage1.md`](../plans/2026-11-24-live-editor-canvas-stage1.md).
**Stage 1 build is ON HOLD** until the `liveedit/` UI-panel wave drains (owner,
2026-11-24) — ~8 branches are concurrently editing `page.html` and the parity doc
requires UI panels to serialize through `liveedit/`, so the reframe waits for a settled
file rather than forcing rebases or merging into churn.
**Date:** 2026-11-24
**Owner:** mike
**Lands in:** `helixgen-core` (`src/helixgen/liveedit/page.html` + server), companion
skill/doc bump in the plugin repo.
**Related:** [`stadium-app-parity.md`](../../parity/stadium-app-parity.md) (functional
backlog — this is the UX reframe that was *missing* from it),
[`2026-11-21-signalflow-editor-parity-design.md`](2026-11-21-signalflow-editor-parity-design.md)
(functional/structural editor epic, engine-first).

---

## Intent & why

The `device live` chain editor works but the **editing experience** is wrong. Today
it renders the active tone as a **vertical scroll of fully-expanded block cards** —
every block shows *all* its knobs, all the time; parallel paths are side-by-side
columns of the same big cards; split/merge are just more cards. You never see the
tone as a *shape*, finding a model means scanning a flat A–Z list, and nothing tells
you at a glance what each block *is*.

The Line 6 **Helix Stadium Edit app** solves this with a **two-level model**:

1. A compact **signal-flow canvas** — each block a small glyph tile, color + icon
   coded by category, parallel paths drawn as branches. You read the whole tone at a
   glance and move blocks around directly.
2. A **focus panel** — click one tile and *that block's* controls appear; the rest of
   the chain stays compact.

Plus a **categorized model browser** (Amp / Preamp / Cab / Distortion / Delay / …) and
a **slot sidebar** of presets.

The existing parity backlog is a thorough *functional* enumeration (add/remove/move,
model browser, dual-cab, Focus-View deep editors) but says nothing about **how editing
should feel**. This spec is that missing piece: adopt the two-level canvas+focus model.
It is **mostly a front-end change** and — unlike the functional panels — is **not
blocked on the engine epics** (topology-synthesis etc.).

The owner picked the **full canvas direction** (over a lighter collapse-in-place
reskin) on 2026-11-24.

## Goals

- The Signal-flow pane becomes a **horizontal canvas of glyph tiles**, category
  color+icon coded, parallel paths drawn as branches, inputs/outputs at the ends —
  readable as one picture.
- **Selecting a tile** opens a **focus panel** rendering only that block's controls
  (reusing today's knob/switch/list/lens widgets).
- **Direct manipulation:** drag a tile to **reorder within a path** (ships now — the
  engine op exists) and to **move it between paths/lanes** (owner-chosen in scope,
  2026-11-24 — this pulls the topology-synthesis engine epic in as a Stage 2 dependency;
  see Constraints + Staging).
- **Categorized model browser** for add-block and swap-model, replacing the flat A–Z
  list.
- Every block carries a **type icon**.
- No loss of what works today: live-write-on-change, follow-the-device, undo/redo,
  snapshots bar, device-native Save, and the **adjective knob-search** (reworked, see
  Decisions) all survive.

## Non-goals (explicitly out — tracked elsewhere)

- The **Focus-View deep editors** (amp lens/XY morph zones, cab mic-placement + IR
  plot, EQ drag-band, comp gain-reduction meter). The focus panel shows the block's
  normal controls; deep editors are the functional backlog
  ([signalflow-editor-parity](2026-11-21-signalflow-editor-parity-design.md)).
- IR management, Command Center, Global EQ, Matrix Mixer, snapshots-management UI,
  controllers UI — unchanged by this work. (Investigate-beads to be logged for IRs /
  Command Center / Global EQ so they're tracked.)
- The **library/slot sidebar** rework (slot grid, drag slot-to-slot, on-disk library →
  slots) is a **separate follow-on pass**, designed after this lands. Noted here so the
  canvas leaves room for it; not built here.

## Anti-goals (failure even if it "works")

- A canvas that's pretty but makes common edits *slower* than today (e.g. tweaking three
  blocks now takes three click-to-focus round trips with no way to see them together).
  The focus model must not punish quick multi-block tweaks.
- Breaking the "every control is heard immediately / the page follows the hardware"
  contract. The reframe is visual; the live-write semantics stay identical.
- A bespoke drag/canvas framework. Stay vanilla, in `page.html`, no build step, no deps.

## Constraints

- **Front-end is one file, no framework:** `liveedit/page.html` (~2500 lines), vanilla
  JS, **full-re-render** pattern (`render()`) with active-element/focus preservation.
  The canvas must fit this model — re-render from state `S`, restore selection + focus.
- **Category accent colors already exist** as CSS vars (`.c-delay{--acc:#5fd38d}`,
  `.c-reverb`, `.c-modulation`, …). Reuse them for tiles, icons, and the browser rail.
- **Structural ops already exist in 0.89.0 (verified in source).** `session.py` ships
  `add_block`, `swap_model`, `move_block`, `remove_block`, all wired to `server.py`
  routes (`/add-block`, `/swap`, `/move-block`, `/remove-block`, `/add-split`) and used
  by today's `page.html`. So the categorized browser and **within-path drag-reorder are
  pure front-end** over endpoints that already work — no core release needed.
  - **`move_block`** is literally "the app's drag-to-reorder" via `/doAgenda [{movb}]`,
    but **restricted to lane-A processing slots 1..12, same path** (DSP 0 HW-validated;
    a `ponytail:` note flags DSP 1 as not yet HW-validated). Within-lane reorder: yes.
    Cross-lane / move-between-paths: **no**.
  - **`add_block` appends** (after the last block / lowest gap) — there is **no
    insert-at-arbitrary-slot**. Row-0 adds are refused (grid/routing corruption).
- **Cross-lane moves + new topology are the genuinely-gated piece — and are IN scope**
  (owner, 2026-11-24). Moving a block to another lane, and building split/merge topology
  by drag, require the sibling spec's **topology-synthesis engine epic**
  ([topology-synthesis-engine](2026-11-21-topology-synthesis-engine-design.md), already
  designed; handoff in
  [plans/](2026-11-21-topology-synthesis-core-handoff.md)). That epic (helixgen-core) is
  therefore a **Stage 2 dependency of this effort**, executed before the cross-lane
  front-end drag. Stage 1 (the whole visual reframe + within-lane drag) does **not**
  depend on it and ships first.
- **Shared surface:** `page.html` is the frame every functional panel hangs on. Doing
  this reframe **first** means those panels inherit the canvas; doing it later means
  reworking them. This argues for sequencing the UX reframe ahead of more functional
  panels.
- The owner's Stadium XL (fw 1.4, `192.168.4.84`) is available for HW validation.

## Approaches considered

**A — Collapse & accordion (reskin in place).** Keep the vertical list; collapse each
block to a one-line tile (icon + name + bypass), expand knobs inline on click; drag
tiles to reorder; add category icons/colors; category rail on the picker.
*Smallest change, nearly all reuse, pure front-end — but routing stays non-spatial
(parallel lanes still stack vertically). Delivers icons + a picker + collapse, but not
the "signal chain you can see and move around." A strict subset of B's first stage.*

**B — Signal-flow canvas + focus panel (chosen).** Horizontal glyph-tile chain with
parallel branches; selecting a tile opens a focus panel that renders that block's
controls (reusing existing widgets); drag tiles to reorder / move between lanes;
categorized model browser.
*The faithful Stadium model and what the owner asked for. Mostly front-end; the
live-write plumbing and control widgets are reused. Bigger build than A (a routing-canvas
renderer + selection/layout + a focus-panel home for the existing controls) and it
reshapes the shared `page.html` frame — which is why it goes first.*

**C — B + Focus-View deep editors.** Rejected for *this* spec: those deep editors are
the functional backlog, several are engine-gated, and they don't block the UX reframe.

**Chosen: B, staged** (see Staging).

## How it gets built — decided

Calls made for the builder. The two owner decisions (adjective-search, cross-lane
scope) are resolved inline below (owner, 2026-11-24).

- **Layout.** Signal-flow pane = **canvas on top** (full width, horizontally scrollable
  when long), **focus panel docked below** it. The **model browser** opens in that same
  lower region (replacing the focus panel) when adding or swapping a block, mirroring
  Stadium's bottom-of-window browser+focus. The snapshots bar, adjective search, and
  Undo/Redo/Library/Save chrome stay in the top bar as today. The **other tabs**
  (Device, Controllers, Mixer, Global EQ, Command Center, Tuner) are untouched — this
  reframes only the Signal-flow pane.
- **Tiles.** One tile per block: category **icon** + short name under/beside it,
  category **`--acc` border/tint**, a **bypass** affordance, selected state = bright
  border + glow (as Stadium). Inputs and outputs render as end-cap tiles. Splits/merges
  render as branch junctions, not cards.
- **Parallel paths — render against the real state model, not just 2-lane.** The
  renderer consumes `S.paths` as it actually is: `parallel` segments with `a`/`b`/`join`
  lanes, the `extra` second-row column, `split`/`join` STRUCT nodes, cross-DSP `xlink`
  taps, and (per the sibling spec) up to 4 flows / multiple splits. Draw each case the
  way Stadium draws it; capture the exact shapes against a real multi-path preset during
  implementation. A renderer built only for "split → two lanes → merge" would have to be
  rebuilt — so the core canvas is written general from the start. *(My call — resolves
  builder-check Q2; exact geometry still the builder's, per "What's left".)*
- **Focus panel.** Renders the selected block's existing controls verbatim (the current
  per-block knob/switch/list/lens rendering, relocated). Bypass + delete + "swap model"
  live in its header. Nothing is a new *control* — only a new *home* for them.
- **Selection identity across re-render + device-follow.** Key the selected tile on its
  **path+slot position** (there is no block-level stable id today, and adding one is
  engine/serialization work — out of scope). Extend `render()`'s active-element
  preservation to also restore selection. When the device changes topology underneath a
  following editor: an **in-place model-swap keeps** selection (same slot); a **reorder
  follows** the block to its new slot where derivable; a **removed/vanished** block
  **clears** the focus panel (deselect) with a subtle "block gone" note rather than
  freezing on stale controls. *(My call — resolves builder-check Q3; no engine work.)*
- **Drag.** Pointer-drag a tile to a new slot **within its path** → commit via the
  existing `move_block` (lane-A 1..12) — Stage 1. Dragging **onto another lane**
  (Stage 2-ui) commits via the new topology ops; until 2-engine lands it shows a
  disabled drop target with a reason, never silently missing (parity won't-do-with-reason
  rule).
- **Model browser.** Left rail of **categories** (reuse `--acc` colors + icons), right
  list of models in the selected category, search box filters within. Used for **swap**
  (block header → browser, in place) and **add**. Add is **append to the chosen path**
  (the engine is append-only; there is no insert-at-arbitrary-slot, so the browser picks
  *which path* to append to, not a free grid slot). Mono/stereo shown per model.
  *(My call — resolves builder-check Q4.)*
- **Focus-panel scope.** The panel relocates **every control the current per-block card
  renders today, verbatim** — knobs, switches, lists, and the existing pads the card
  already hosts (amp lens/XY, EQ curve, cab mic pad, 2nd-cab picker, snapshot-aware
  controls, any in-card assign UI). It is a new *home*, not new *editors*; build **no
  new** deep editor (those stay the functional backlog). *(My call — resolves
  builder-check Q5; bounds the Stage 1 refactor to relocating existing render code.)*
- **Icon key maps to the engine's own categories.** Glyphs key off the actual
  `b.category` strings the state model emits (e.g. `cab_ir_interp`, `ir`, `dynamics`,
  `split`/`join`), not Stadium's label list verbatim — matching Stadium's taxonomy where
  it lines up. *(My call — resolves builder-check's self-settled item.)*
- **Icons.** One glyph set keyed by category, as CSS/SVG in `page.html`. Reuse Stadium's
  taxonomy (Amp, Preamp, Cab, Distortion, Delay, Reverb, Modulation, Dynamics, EQ,
  Pitch/Synth, Wah/Filter, Volume/Pan, Looper, Send/Return, Split, Merge, Input,
  Output).
- **Adjective knob-search — decided (owner, 2026-11-24): highlight tiles, then knobs.**
  Today it highlights matching knobs across the whole expanded chain. In the two-level
  model it **highlights the matching tiles** on the canvas (glow/badge in the
  up/down/turn colors); focusing a highlighted tile then highlights the specific knob(s)
  in the focus panel. Keeps the helixgen-unique feature spatial. Part of Stage 1.

## Staging (re-cut after verifying the engine — the whole reframe is front-end)

Because `add` / `swap` / `move_block` (within-lane) / `remove` already ship, the entire
UX reframe the owner asked for is **front-end-only and unblocked**. Only cross-lane
moves wait on the separate engine epic.

- **Stage 1 — the canvas reframe (pure front-end, no core release).** Tiles + branches,
  selection → focus panel, type icons, **categorized model browser** (add-append + swap,
  over existing endpoints), **within-path drag-reorder** (over the existing `move_block`
  1..12 op), and adjective-search tile highlighting. This is the deliverable. Ships as a
  plugin release only if it touches skill docs; the editor code is core but adds no new
  engine behavior, so it rides a normal core release with tests + a HW smoke pass (still
  writes/follows, reorder lands on hardware). **Highest payoff, lowest risk.**
  - *Optional sub-split if Stage 1 is too big for one PR:* (1a) canvas + focus + icons;
    (1b) categorized browser; (1c) within-path drag. All front-end, any order.
- **Stage 2 — cross-lane moves (owner pulled this in; two sub-parts).**
  - **2-engine (helixgen-core long-pole):** execute the already-designed
    **topology-synthesis engine epic**
    ([design](2026-11-21-topology-synthesis-engine-design.md) +
    [handoff](2026-11-21-topology-synthesis-core-handoff.md)) — the ops to move a block
    across lanes and synthesize split/merge topology live. This is the real work and
    lands first in core.
  - **2-ui (front-end, on top of 2-engine):** the cross-lane drop targets + parallel-by-
    drag affordances, wired to the new ops. Until 2-engine lands, Stage 1 keeps these
    drop targets **disabled-with-reason** (never silently missing), so Stage 1 can ship
    independently without waiting.

Previous 2a/2b/2c split is superseded: within-lane reorder + the categorized browser
fold into Stage 1 (they already work); cross-lane is Stage 2, which now carries the
topology engine epic as its long-pole.

## Risks / open feasibility

- **Cross-lane moves** (Stage 2) — the real long-pole: the topology-synthesis engine
  epic in helixgen-core (already designed, not yet built). Owner pulled this into scope.
  Stage 1 (the whole reframe) does not depend on it and ships first, so the engine epic's
  size doesn't hold up the UX win.
- **Within-lane reorder on DSP 1** — `move_block` is HW-validated on DSP 0 only
  (`ponytail:` note). Validate path-2 reorder on the owner's XL during Stage 1; if it
  misbehaves, disable reorder on DSP 1 with a reason until core validates it.
- **Canvas density on long chains** — super-serial tones can be long; the canvas must
  scroll horizontally and stay legible. Validate with a real multi-path preset.
- **Focus model vs. quick multi-block tweaks** (anti-goal) — confirm during Stage 1 that
  moving between blocks is fast; if click-to-focus feels heavy, consider a "pin a second
  block open" affordance (note, not committed).

## What's left to the builder

- Exact tile dimensions, branch-drawing geometry, and the horizontal-scroll behavior.
- The glyph SVGs per category (match Stadium's taxonomy; exact art is the builder's).
- Whether the focus panel is a fixed-height dock or resizable (builder's call; default
  fixed).
- Drag hit-testing / drop-target geometry on the canvas (within-lane in Stage 1;
  cross-lane drop targets in Stage 2-ui).
- Reusing vs. lightly refactoring the current per-block render fn into a focus-panel
  renderer.

## Acceptance

- The Signal-flow pane shows the active tone as a readable glyph-tile canvas with
  branches; clicking a tile edits it in a focus panel; blocks carry type icons; the
  model browser is categorized.
- Live-write, follow-the-device, undo/redo, snapshots, Save, and adjective-search all
  still work.
- Round-trips cleanly (`device to-hsp` ⇄ library) with no fidelity change (this is a
  view change; the written preset is unaffected).
- Any move the live protocol can't do is disabled-with-reason, not missing.
