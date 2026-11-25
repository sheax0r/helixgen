# Live editor canvas + focus UX — Stage 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reframe the `device live` Signal-flow pane from a vertical stack of always-expanded block cards into a compact horizontal **glyph-tile canvas + focus panel**, with type icons, a categorized model browser, within-lane drag-reorder, and tile-level adjective-search highlighting.

**Architecture:** Pure front-end change to one file — `helixgen-core` `src/helixgen/liveedit/page.html` (vanilla JS, full-re-render). No new engine behavior: `add_block`/`swap_model`/`move_block`/`remove_block` and the per-block control rendering (`blockEl`) + category-keyed `MODELS` catalog already exist and are reused. The chain's existing segment model (`seg.kind`, `seg.a/b/join`, `p.extra`) stays; we render it compactly and move the controls into a selection-driven focus panel.

**Tech Stack:** Vanilla JS + CSS inlined in `page.html` (no framework, no build step, no new deps). Python server `server.py` unchanged. Plugin repo: Markdown skill/doc updates.

**Spec:** [`docs/superpowers/specs/2026-11-24-live-editor-canvas-ux-design.md`](../specs/2026-11-24-live-editor-canvas-ux-design.md) (plugin repo). Stage 2 (cross-lane moves) = the existing [topology-synthesis handoff](2026-11-21-topology-synthesis-core-handoff.md); **out of scope here**.

> **Status (2026-11-25): SHIPPED — complete.** The panel wave drained and this reframe
> landed in helixgen-core **0.92.0** (device live canvas + focus editor, #198). Stage 2
> (cross-lane / topology synthesis, out of scope here) also shipped: drag-to-split (0.94.0),
> cross-lane `move_into_split` (0.95.0), serial multi-split (0.100.0). Plugin skills/docs
> current through 5.49.0. Retained as the implementation record; nothing left to start.

## Global Constraints

- **One file, vanilla, no deps.** All editor changes land in `src/helixgen/liveedit/page.html`. No framework, no build step, no external JS/CSS files (it is served as one document).
- **Reuse, don't rebuild.** Controls come from the existing `blockEl(b)` body; models from the existing `MODELS[category]`; structural ops from the existing endpoints (`/add-block`, `/swap`, `/move-block`, `/remove-block`). No new engine code in Stage 1.
- **Live-write contract unchanged.** Every control still writes to the device on change; the page still follows the hardware (the `render()` full-re-render + focus-preservation loop stays).
- **Within-lane reorder only.** `move_block` is restricted to lane-A processing slots 1..12, same path (DSP 0 HW-validated). Cross-lane drop targets render **disabled-with-reason**, never silently missing.
- **No new deep editors.** The focus panel relocates exactly what `blockEl` renders today (knobs, switches, lists, EQ pad, cab mic pad, 2nd-cab, assign). Building new Focus-View editors is out of scope (functional backlog).
- **Testing reality:** `page.html` has no JS unit harness in-repo; validation is visual + on the owner's Stadium XL (fw 1.4, `192.168.4.84`) + "existing `pytest` and core round-trip suites still green" (this is a view change; the written preset is unaffected). Where a pure helper is extracted, add a `ponytail:`-style inline `assert` self-check runnable with `node`, not a framework.
- **Repo flow:** core worktree from fresh `origin/main`; adversarial review before merge; core release (version bump → workflow) ships first; plugin pin/doc bump second.

## Review Focus

Inputs the spec implies but no single task centers — pin each in the named task:

- **Multi-path / exotic topology** (multiple splits, `p.extra` second row, cross-DSP `b.xlink` taps): the canvas must draw these, not just split→2-lane→merge. → Task 2 validates against a real multi-path preset (the loaded A7X tone has a split + IR lanes + a `path 2`).
- **Selected block vanishes under device-follow** (HX Edit / hardware deletes or reorders it live): focus panel must clear gracefully, not freeze on stale controls. → Task 3.
- **Empty / cold-start / no-device**: canvas must render the "no tone loaded" hint and the drawer still opens offline (today's behavior preserved). → Task 2.
- **Long super-serial chain**: canvas scrolls horizontally and stays legible. → Task 2.
- **Reorder on DSP 1 (path 2)**: `move_block` HW-validated on DSP 0 only; verify path-2 drag on HW, disable-with-reason if it misbehaves. → Task 5.

---

## Task 1: Category taxonomy — icons + accents

**Files:**
- Modify: `src/helixgen/liveedit/page.html` (CSS `/* ---------- category accents ---------- */` block ~L345; add a `CAT_ICON` JS map near the render helpers).

**Interfaces:**
- Produces: `CAT_ICON[category] -> inlineSVGString` and a complete `.c-<category>{--acc:…}` set covering every `b.category` the state emits (`input`, `output`, `split`, `join`, `amp`, `preamp`, `cab_ir_interp`, `ir`, `distortion`, `delay`, `reverb`, `modulation`, `dynamics`, `eq`, `pitch`, `wah`/`filter`, `volume`, `looper`, `send`/`return`, …). Later tasks read both.

- [ ] **Step 1: Enumerate the live category set.** From a connected device, dump the distinct `b.category` values across a few presets (via the `/state` endpoint the page already polls) and reconcile with the CSS `--acc` set already present. List any category with no accent/icon.
- [ ] **Step 2: Add missing `--acc` accents** for every category in the set (reuse Stadium's hues where they map: amp/preamp red, cab magenta, distortion amber, delay green, reverb cyan/orange, modulation blue, dynamics lime, eq yellow, pitch/wah purple, volume teal).
- [ ] **Step 3: Add `CAT_ICON`** — one small inline-SVG glyph per category (stroke uses `currentColor`/`--acc`). Keep each glyph ~16–20px, single-path where possible.
- [ ] **Step 4: Validate** — temporarily tag each existing block card header with its icon; screenshot the editor; confirm every block shows a correct, legible, category-colored glyph. Remove the temporary tag (Task 2 places icons for real).
- [ ] **Step 5: Commit** (`feat(live): category icon + accent taxonomy`).

*Parallelizable: this is self-contained asset work; a subagent can produce the glyph set from the category list.*

## Task 2: Signal-flow tile canvas

**Files:**
- Modify: `src/helixgen/liveedit/page.html` — add `tileEl(b)`; change `seg()`/`lane()`/`render()` (~L1149, L1846) to build a compact horizontal canvas of tiles instead of stacked `blockEl` cards.

**Interfaces:**
- Consumes: `CAT_ICON`/accents (Task 1); existing `S.paths` segment model (`seg.kind`, `seg.a/b/join`, `seg.split`, `p.extra`, `b.xlink`), `STRUCT` set, `SPLIT_PATHS`.
- Produces: `tileEl(b) -> element` (a `.tile.c-<cat>` with icon + short name + bypass dot + `data-sel` selection key = `"<pathIdx>:<slot>"`), and a `renderCanvas()` that lays the chain horizontally with branch connectors. `blockEl` is **no longer called by `render()`** (it moves to the focus panel in Task 3; keep the function for now).

- [ ] **Step 1: Write `tileEl(b)`** — icon (Task 1) + name + bypass indicator + selected ring; `STRUCT` categories (`split`/`join`) render as small junction nodes, `input`/`output` as end-caps.
- [ ] **Step 2: Rewrite `seg()`/`lane()` to emit tiles**, drawing parallel segments as branches (split node → lane A / lane B stacked between split and join connectors), the `p.extra` row as a second flow line, and an `xlink` tap as a cross-line marker (match Stadium's drawing; exact geometry builder's choice).
- [ ] **Step 3: Make the canvas horizontally scrollable** and keep the "No tone is loaded" hint and offline cold-start path.
- [ ] **Step 4: Validate on the loaded multi-path preset** (A7X: split + dual IR lanes + path 2) — screenshot; confirm the whole tone reads as one branched picture, scrolls, and matches the device's routing. Confirm empty-state + a device-disconnect still render.
- [ ] **Step 5: Commit** (`feat(live): render the chain as a signal-flow tile canvas`).

## Task 3: Focus panel (selection → controls)

**Files:**
- Modify: `src/helixgen/liveedit/page.html` — add a focus-panel container below the canvas; wire tile selection; relocate the `blockEl(b)` body into it.

**Interfaces:**
- Consumes: `tileEl` selection key (Task 2); the existing `blockEl(b)` control body (knobs/switches/lists/EQ pad/cab pad/2nd-cab/assign).
- Produces: selection state `SEL` (the `"<pathIdx>:<slot>"` key) and `renderFocus()` that renders the selected block's controls; `render()` preserves `SEL` across re-render and clears it when the block is gone.

- [ ] **Step 1: Add `SEL` + click handler** — clicking a tile sets `SEL` and re-renders; selected tile shows the ring.
- [ ] **Step 2: `renderFocus()`** — resolve `SEL` to the block in `S.paths`; render its controls using the existing `blockEl` body (refactor `blockEl` so the body is reusable in the panel rather than a full card). Header carries name + bypass + swap + delete.
- [ ] **Step 3: Preserve + clear selection in `render()`** — restore `SEL` after re-render (extend the existing `data-k` focus-preservation); if the block at `SEL` no longer exists (deleted/reordered away under device-follow), clear the panel with a subtle "block gone" note; an in-place model-swap keeps `SEL`.
- [ ] **Step 4: Validate** — click several blocks incl. a split lane IR; confirm controls render and a knob change still writes live (watch the device). Delete the selected block on the hardware/HX Edit; confirm the panel clears, not freezes.
- [ ] **Step 5: Commit** (`feat(live): focus panel edits the selected block`).

## Task 4: Categorized model browser

**Files:**
- Modify: `src/helixgen/liveedit/page.html` — replace the inline same-category swap list (~L2425) and the add-block picker with a two-column browser.

**Interfaces:**
- Consumes: existing `MODELS` (category-keyed), `/swap` and `/add-block` endpoints, `CAT_ICON`/accents.
- Produces: `openBrowser({mode:"add"|"swap", path, block?})` rendering a left **category rail** (icon+accent) + right **model list** (name + mono/stereo) + a filter box; commits via `/add-block` (append to `path`) or `/swap`.

- [ ] **Step 1: Build the browser UI** — category rail from `Object.keys(MODELS)` ordered like Stadium (Amp, Preamp, Cab, Distortion, Delay, Reverb, Modulation, Dynamics, EQ, Pitch/Synth, Wah/Filter, Volume/Pan, …); right list from `MODELS[selectedCat]`; search filters within.
- [ ] **Step 2: Wire swap** — from the focus-panel header → `openBrowser({mode:"swap"})` → `/swap`. Wire add — the per-path `+` → `openBrowser({mode:"add", path})` → `/add-block` (append; note it cannot insert at an arbitrary slot).
- [ ] **Step 3: Validate on HW** — swap a distortion model and add a block; confirm both land on the device and the canvas updates. Confirm mono/stereo shows.
- [ ] **Step 4: Commit** (`feat(live): categorized model browser for add + swap`).

## Task 5: Within-lane drag-reorder

**Files:**
- Modify: `src/helixgen/liveedit/page.html` — pointer-drag on tiles → `/move-block`; replace the current neighbour-swap reorder affordance.

**Interfaces:**
- Consumes: `tileEl` tiles, `/move-block` (`path, src, dst`, lane-A 1..12).
- Produces: drag handlers that commit a within-lane reorder; cross-lane drop zones rendered disabled with a reason tooltip.

- [ ] **Step 1: Implement pointer drag** — drag a processing tile to a new slot within its lane; on drop, call `/move-block(path, src, dst)`; show a drop indicator between tiles.
- [ ] **Step 2: Disable cross-lane / out-of-range drops** — dropping onto another lane or a routing node shows "cross-lane moves need the topology engine (Stage 2)"; no write.
- [ ] **Step 3: Validate on HW** — reorder two blocks on path 1 (DSP 0) and confirm audibly/structurally on the device; attempt the same on path 2 (DSP 1) and, if it misbehaves, gate DSP-1 reorder with a reason.
- [ ] **Step 4: Commit** (`feat(live): drag to reorder within a lane`).

## Task 6: Adjective-search tile highlighting

**Files:**
- Modify: `src/helixgen/liveedit/page.html` — extend the adjective-search highlight (`.hl-*`, `CAT_ROLE`, `roleOf`) to mark tiles.

**Interfaces:**
- Consumes: existing adjective-intent matching (`#adjsearch`, `intents`, `roleOf(b)`, `.hl-up/.hl-down`); `tileEl`.
- Produces: tile-level highlight — tiles whose block contains a matching knob glow in the up/down color; the focus panel keeps the existing per-knob `.hl-*`.

- [ ] **Step 1: Compute matching blocks** — reuse the existing match to produce the set of blocks with ≥1 matching knob and the dominant direction.
- [ ] **Step 2: Highlight tiles** — add `hl-up`/`hl-down` glow to matching tiles on the canvas; dim non-matches (as today's `.hl-off`); keep per-knob highlight inside the focus panel when a matching tile is open.
- [ ] **Step 3: Validate** — type "crunchier"/"brighter"; confirm the right tiles glow and opening one highlights the knob. Confirm clearing the box restores all tiles.
- [ ] **Step 4: Commit** (`feat(live): adjective search highlights tiles then knobs`).

## Task 7: Plugin sync + docs + deferred beads

**Files:**
- Modify (plugin repo): `skills/live/SKILL.md`, `README.md`, `docs/parity/stadium-app-parity.md`; append to `docs/parity/stadium-parity-beads.jsonl`.

**Interfaces:**
- Consumes: the shipped Stage 1 behavior.
- Produces: skill/doc copy describing the canvas+focus UX; parity doc marks the editor-UX reframe landed; investigate-beads logged for IR / Command Center / Global EQ UX follow-ups and for the library/slot sidebar pass.

- [ ] **Step 1: Update `skills/live/SKILL.md` + `README.md`** — describe the canvas + focus panel + categorized browser + drag + tile search (replace the "signal chain of knobs" framing).
- [ ] **Step 2: Update `docs/parity/stadium-app-parity.md`** — record the UX reframe (icons, tile canvas, focus view, categorized browser, within-lane drag) as landed; note Stage 2 (cross-lane) pending the topology engine.
- [ ] **Step 3: Append investigate-beads** to `stadium-parity-beads.jsonl` — IR / Command Center / Global EQ UX follow-ups, library/slot-sidebar pass, each referencing this spec.
- [ ] **Step 4: Run plugin tests** — `python3 -m pytest` (skill-doc frontmatter/content checks) green.
- [ ] **Step 5: Commit** (`docs(live): skills + parity reflect the canvas UX`).

## Task 8: Validate, review, release

**Files:**
- Modify (core): version bump in the core package per its release flow.
- Modify (plugin): `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` (matching versions), engine pin in `skills/*` + README if the engine version moved.

- [ ] **Step 1: Full HW validation pass** — load a real multi-path preset; exercise select/edit/swap/add/reorder/search end to end on the Stadium XL; confirm live-write + follow still hold and the written preset round-trips (`device to-hsp` unchanged diff).
- [ ] **Step 2: Adversarial review** — dispatch ≥1 independent review subagent prompted to break the reframe (selection-key edge cases, re-render focus loss, drag race vs. device-follow, exotic topology rendering). Fix confirmed findings or defer to backlog with reason.
- [ ] **Step 3: Core release** — bump core version, PR, watch CI (`gh pr checks --watch`), merge green, push the `vX.Y.Z` tag that publishes to PyPI.
- [ ] **Step 4: Plugin release** — bump the engine pin to the new core version in `skills/*` + README, bump `plugin.json` + `marketplace.json`, PR, CI, merge (the version bump ships the release via the workflow).

---

## Notes on parallelism (per owner's "parallelize with subagents")

Stage 1 is **one shared file** (`page.html`) plus a serialization rule from the parity doc (UI panels serialize through `liveedit/`). Genuinely parallel: **Task 1** (icon/asset set), the **adversarial review** (Task 8.2), and the **plugin docs** (Task 7, different repo). Tasks 2→3→5 are a dependent chain on the canvas/selection and must serialize; Tasks 4 and 6 can be built against Task 2/3's interfaces but integrate into the same file, so land them one at a time. Recommendation: build the canvas chain (2→3) natively/serially, fan out Task 1, Task 7, and reviews to subagents, and merge the file-touching tasks in sequence.
