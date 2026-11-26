# Stadium Layout Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **This lands in helixgen-core, not the plugin repo.** Run in a **helixgen-core**
> worktree branched from freshly-fetched `origin/main` (local `main` there is stale). The
> design doc and this plan are readable in the plugin checkout at the paths cited.

**Goal:** Restructure the `device live` editor from a vertical/tabbed/drawer shell into the
Helix Stadium Edit app's **four-pane horizontal** layout — preset browser | horizontal
signal flow | model browser | block editor — without changing any engine behavior.

**Architecture:** Pure front-end reshell of one file, `src/helixgen/liveedit/page.html`
(vanilla JS, full-re-render). Keep every existing renderer (block tiles, `blockEl` controls,
`MODELS[category]`, knob widgets, the drawer's preset list); the work is relocating them into
a new CSS-grid shell and flipping the canvas to horizontal. Ships in **three stages, one core
release each** (Approach A). No new endpoints; structural ops (`add_block`/`swap_model`/
`move_block`/`remove_block`/`add_split`) are reused as-is.

**Tech Stack:** Vanilla JS + CSS inlined in `page.html`. No framework, no build step, no new
deps. Python `server.py` unchanged.

**Spec:** [`docs/superpowers/specs/2026-11-25-stadium-layout-parity-design.md`](../specs/2026-11-25-stadium-layout-parity-design.md)
(plugin repo). Reference capture: the live Stadium Edit app, 2026-11-25.

## Global Constraints

- **One file, vanilla, no deps.** All editor changes land in `src/helixgen/liveedit/page.html`.
- **Full-re-render preserved.** `render()` rebuilds from state with active-element/focus
  restoration; the new shell must survive a re-render (restore selection + focus + scroll).
- **No new engine behavior.** Reuse `add_block`/`swap_model`/`move_block`/`remove_block`/
  `add_split` and their existing `server.py` routes. This is a view change only.
- **Live contracts unchanged:** live-write-on-change, follow-the-device, undo/redo, snapshots
  bar, device-native Save, adjective knob-search all keep working across every stage.
- **Block editor renders KNOBS**, not Stadium's horizontal bars (owner's call) — reuse the
  existing knob widget; do not add a bar style.
- **Library stays**, integration deferred — do not delete the drawer; S2 promotes its preset
  list to a persistent pane but keeps drawer fallback under the narrow breakpoint.
- **Layout parity, not pixel parity** — match arrangement + interaction; do not copy Line 6
  artwork/icons/colors.
- **Testing reality:** no in-repo JS unit harness. Each task's acceptance = (a) the existing
  `pytest` + round-trip/corpus suites still green, and (b) a visual + on-hardware smoke pass
  on the owner's Stadium XL (fw 1.4, `192.168.4.84` / USB). Any **pure helper** extracted
  (e.g. branch-geometry math) gets a `ponytail:`-style inline `assert` self-check runnable
  with `node`.
- **Repo flow:** core worktree from fresh `origin/main`; adversarial review before merge;
  **one core release per stage** (version bump → workflow → tag → PyPI); after each core
  release, the plugin repo bumps the engine pin in skills + README and bumps any skill-doc
  wording, then cuts its own release.

## Review Focus

Inputs the spec implies but no single task centers — pin each in the named task:

- **Exotic topology** (multiple splits, serial parallel sections, `p.extra` second row,
  cross-DSP `b.xlink` taps): the horizontal canvas must draw these as branches, not just
  one split→2-lane→merge. → Task 1 validates against a real multi-path preset (the loaded
  Motor Spirit tone has a split + IR lanes + a second path).
- **Selected block vanishes under device-follow** (hardware/HX Edit deletes or reorders it
  live): the right block-editor pane must clear gracefully, not freeze on stale controls.
  → Task 4.
- **Narrow window**: below the breakpoint the four panes must collapse to today's
  drawer/tab/focus-dock behavior, not overlap or clip. → Task 5.
- **Long super-serial chain**: the horizontal canvas scrolls horizontally and stays legible;
  the other three panes keep their own scroll. → Task 1 / Task 5.
- **Reorder on DSP 1 (path 2)** after the flip: `move_block` is HW-validated on DSP 0 only;
  verify path-2 drag in the horizontal canvas on hardware, disable-with-reason if it
  misbehaves. → Task 1.

---

## Stage 1 — Horizontal canvas (core release)

### Task 1: Flip the signal-flow render to horizontal

**Files:**
- Modify: `src/helixgen/liveedit/page.html` — the signal-flow render path (`render()` and the
  canvas/segment drawing fns `blockEl`/`seg`; re-confirm exact anchors on fresh `origin/main`,
  line numbers have moved since the canvas shipped in 0.92.0).

**Interfaces:**
- Consumes: existing chain state (`seg.kind`, `seg.a`/`seg.b`/`seg.join`, `p.extra`),
  category accent CSS vars (`.c-delay{--acc}` etc.), and the existing tile renderer.
- Produces: a horizontal canvas — same DOM contract (one element per block tagged for
  selection + drag) so Tasks 2–5 and today's focus/drag code keep their hooks.

- [ ] **Step 1:** Extract the branch/connector geometry into a pure helper
  `laneLayout(segments) -> {blocks:[{id,x,y}], links:[{from,to,path}]}` and add a `node`
  `assert` self-check at the bottom of a small sibling script (or an inline `<!--node-check-->`
  block) covering: a serial chain, one split→2-lane→merge, and a serial second split.
- [ ] **Step 2:** Run the self-check: `node tools/laneLayout.check.js` → all asserts pass.
- [ ] **Step 3:** Rewrite the canvas container + segment drawing to lay blocks **left→right**,
  stack parallel lanes vertically, draw split/merge + connectors in the new orientation, put
  output arrows at the right end, and scroll horizontally when the chain overflows. Reuse the
  existing tile element and `--acc` colors; change layout, not the tile.
- [ ] **Step 4:** Launch `helixgen device live` against the XL; visually confirm the Motor
  Spirit preset (split + IR lanes + path 2) renders horizontally with correct branches; click
  a tile → focus still opens; drag-reorder within a lane still lands on the device; reorder on
  path 2 (DSP 1) — if it misbehaves, render its drop target disabled-with-reason.
- [ ] **Step 5:** Run the Python suites: `pytest` + the round-trip/corpus suite → green
  (this is a view change; the written preset is unaffected).
- [ ] **Step 6:** Commit (`feat(liveedit): horizontal signal-flow canvas`).

### Task 2: Ship Stage 1 as a core release

- [ ] **Step 1:** Adversarial review (independent subagent prompted to break the horizontal
  canvas: exotic topology, long chains, re-render focus loss, device-follow). Fix confirmed
  findings or defer to backlog.
- [ ] **Step 2:** Bump the core version; commit `release X.Y.0 — horizontal signal-flow
  canvas`; open PR; watch CI; merge green; **push the `vX.Y.0` tag** (publishes to PyPI).
- [ ] **Step 3:** (plugin repo) bump the engine pin in `skills/*` + README to the new version;
  one-line skill-doc note that the flow is horizontal; cut a plugin release.

---

## Stage 2 — Persistent left preset/setlist browser (core release)

### Task 3: Promote the drawer's preset list to a fixed left column

**Files:**
- Modify: `src/helixgen/liveedit/page.html` — the layout shell + the library-drawer preset/
  setlist list renderer.

**Interfaces:**
- Consumes: the existing drawer preset-list + setlist-selector renderers and their load action.
- Produces: a persistent left pane in the shell grid; the drawer code stays for narrow mode.

- [ ] **Step 1:** Add a left grid column to the shell; render search + setlist selector +
  preset list there by calling the **existing** drawer list renderer (relocate, don't
  rewrite). Selecting a preset uses the existing load-into-editor action.
- [ ] **Step 2:** Keep the slide-out drawer as the **narrow-breakpoint** fallback (same
  renderer, two mount points); above the breakpoint the left column is always visible.
- [ ] **Step 3:** HW smoke: load a library tone into the editor from the left column; confirm
  it writes/opens; confirm the drawer still works when the window is narrowed.
- [ ] **Step 4:** `pytest` + round-trip suite green. Commit
  (`feat(liveedit): persistent preset/setlist browser pane`).

### Task 4: Ship Stage 2 as a core release

- [ ] Adversarial review (focus: device-follow clearing the selected block; narrow/wide
  toggle; library drift badges still render). → bump core version, PR, CI, merge, tag/PyPI →
  plugin pin/doc bump + release. (Same shape as Task 2.)

---

## Stage 3 — Persistent model + knob editor panes → full four-pane shell (core release)

### Task 5: Promote model browser + focus dock to persistent panes; assemble the grid

**Files:**
- Modify: `src/helixgen/liveedit/page.html` — shell grid, the `+ Add` model-browser renderer,
  the focus-panel renderer.

**Interfaces:**
- Consumes: existing `MODELS[category]` browser renderer (category rail + list) and the
  `blockEl` knob renderer.
- Produces: the final four-column grid (browser | canvas | model | knob-editor), all panes
  persistent, degrading to today's drawer/tab/dock behavior below the breakpoint.

- [ ] **Step 1:** Mount the categorized model browser as a persistent center-right pane
  (category rail + model list), wired to the existing add-append + swap endpoints; `+ Add`
  selection targets the current insertion point as today.
- [ ] **Step 2:** Mount the block editor as a persistent **right** pane rendering the selected
  block's **knobs** via the existing `blockEl` body; when no block is selected or the selected
  block vanishes under device-follow, show an empty-state, not stale controls.
- [ ] **Step 3:** Assemble the four-column CSS grid; define the narrow breakpoint where panes
  collapse to today's drawer/tab/focus-dock behavior; restore selection + focus + each pane's
  scroll across `render()`.
- [ ] **Step 4:** HW smoke on the XL: all four panes visible on a wide window; add a block
  from the model pane; edit knobs in the right pane (writes land live); delete the selected
  block on the hardware and confirm the right pane clears; narrow the window and confirm
  graceful collapse.
- [ ] **Step 5:** `pytest` + round-trip suite green. Commit
  (`feat(liveedit): four-pane Stadium-style shell`).

### Task 6: Ship Stage 3 as a core release

- [ ] Adversarial review (focus: the full-shell re-render preserving focus/scroll; narrow-mode
  collapse; knob writes; model add/swap). → bump core version, PR, CI, merge, tag/PyPI →
  plugin pin/doc bump + release. Close the loop: `device live` is layout-identical to Stadium
  (four panes, horizontal flow, knobs); update the spec status to SHIPPED.
