# `device live` editor — Stadium layout parity design

**Status:** APPROVED (owner, 2026-11-25) — design + plan preapproved, build authorized.
Build = **Approach A (staged incremental)**. Lands in **helixgen-core**
(`src/helixgen/liveedit/page.html` + inlined CSS); companion plugin pin/doc bump.
**Date:** 2026-11-25
**Owner:** mike
**Plan:** [`plans/2026-11-25-stadium-layout-parity-plan.md`](../plans/2026-11-25-stadium-layout-parity-plan.md)
**Builds on:** [`2026-11-24-live-editor-canvas-ux-design.md`](2026-11-24-live-editor-canvas-ux-design.md)
(shipped the glyph-tile canvas + focus model this restructures). Reference: the Line 6
**Helix Stadium Edit** app, layout captured live against the owner's Stadium XL on 2026-11-25.

## Intent & why

The `device live` editor already mirrors Stadium's *two-level model* (glyph-tile canvas +
focus panel), but its **layout** diverges: vertical top-down flow, a tabbed shell, and a
slide-out library drawer. The owner wants the editor **layout-identical** to the Stadium
Edit app — the same panes in the same arrangement, with **horizontal** signal flow — so
moving between the real app and helixgen is seamless (muscle memory carries over).

"Identical" means **layout / structure parity, not pixel parity**: match the arrangement
and interactions, do **not** copy Line 6's artwork, icons, or exact colors.

## Current vs. Stadium (the gap)

| Zone | Stadium Edit | helixgen today |
|------|--------------|----------------|
| Signal flow | **Horizontal** L→R; parallel paths stacked; split/merge as branches; output arrows at right | **Vertical** top-down pill stack |
| Preset/setlist | Persistent **left column** (search, setlist selector, preset list) | Slide-out **Library drawer** + a `Load…` button |
| Model browser | Persistent **center-right pane** (category rail + model list) | On-demand **`+ Add block`** popup |
| Block editor | Persistent **right pane** | **Focus dock** below the canvas |
| Shell | **All panes at once** (wide) | Tabbed single pane + drawer |

## Goals

- Signal flow reads **horizontally, left→right** (input left, output arrows right); parallel
  paths stacked with split/merge drawn as branches; long chains scroll horizontally.
- **Four persistent panes at once** on a wide window, Stadium's arrangement:
  1. **Left** — preset/setlist browser (search, setlist selector, preset list).
  2. **Center** — horizontal signal-flow canvas.
  3. **Center-right** — categorized model browser (category rail + model list).
  4. **Right** — block editor for the selected block.
- Preserve everything that works today: live-write-on-change, follow-the-device, undo/redo,
  snapshots bar, device-native Save, adjective knob-search.

## Divergences from Stadium (owner's calls, 2026-11-25)

- **Knobs, not bars.** The block editor renders rotary **knobs** (helixgen's existing knob
  widget), not Stadium's horizontal slider bars — on amp and every block.
- **Library stays.** The helixgen tone/IR **library browser** is a helixgen-only feature
  Stadium has no concept of; keep it. Richer integration of the library into the new shell
  is a **later stage**, not this build.

## Non-goals / anti-goals

- Pixel / trade-dress parity; reproducing Line 6 artwork, icons, or exact colors.
- New deep Focus-View editors beyond what the block editor renders today.
- Re-homing peripheral panels (Mixer, Global EQ, Controllers, I/O, Tuner) behind
  Stadium-style top-nav icons **in this build** — they keep today's tabs; nav-chrome parity
  is later polish.
- A framework or build step. Stays one vanilla-JS file, full-re-render.
- A canvas that's "identical" but slower for common edits (anti-goal): the four-pane shell
  must not make a quick three-block tweak worse than today.

## Constraints

- **One file**, `src/helixgen/liveedit/page.html` (~3k lines), vanilla JS, no deps,
  **full-re-render** (`render()` with active-element/focus preservation). The new shell fits
  this model — re-render from state, restore selection + focus.
- **Reuse, don't rebuild.** Block tiles, the `blockEl` control body, the `MODELS[category]`
  catalog, knob widgets, and the drawer's preset list already exist — the shell relocates
  them. Structural ops unchanged (`add_block`/`swap_model`/`move_block`/`remove_block`/
  `add_split`); **no new engine behavior** — this is a front-end layout change, so it rides
  normal core releases with tests + a HW smoke pass, no protocol work.
- Live-write / follow-device / undo / snapshots / Save / adjective-search contracts
  unchanged.
- **Wide layout needs horizontal room.** Below a breakpoint, degrade gracefully to today's
  drawer/tab behavior rather than cramming four panes into a narrow window.

## Approaches

- **A — Incremental reshell, staged (CHOSEN).** Keep every renderer; restructure only the
  layout shell into the four-pane frame, **one stage per PR + core release**. Lowest risk,
  each stage validates on hardware, maximal reuse, fits the one-file constraint. Cost: not
  100% identical day one (peripheral panels stay tabbed for a while).
- **B — Full shell rewrite in one pass.** Rebuild the whole layout layer (four panes +
  top-nav parity) at once, porting renderers into new slots. Truest parity soonest, but one
  high-risk PR re-validating the entire device-write path at once, hard to bisect.
  **Rejected** for blast radius.
- **CSS-only flip — rejected:** horizontal flow needs real branch/connector geometry, not
  just `flex-direction`.

## Staging

- **S1 — Horizontal canvas.** Flip the signal-flow render vertical→horizontal: blocks L→R,
  parallel lanes stacked, split/merge + connectors redrawn in the new orientation, output
  arrows at right, horizontal scroll for long chains. Self-contained; biggest visible change.
  HW-validate that reorder/split still land on the device. → core release.
- **S2 — Persistent left preset/setlist browser.** Promote the slide-out drawer's preset +
  setlist list into a fixed left column (search, setlist selector, preset list, select-to-
  load). Keep drawer behavior under the narrow breakpoint. → core release.
- **S3 — Persistent model + knob editor panes → full four-pane shell.** Promote the `+ Add`
  model browser to a persistent center-right pane (category rail + list; add/swap over the
  existing endpoints) and the focus dock to a persistent right **knob** editor pane; assemble
  the four-column grid. → core release.
- **Later (not this build):** nav-chrome parity for peripheral panels; richer library
  integration into the shell.

## What's left to the builder

- Exact grid breakpoints and narrow-mode degradation.
- Horizontal branch-drawing geometry / connector routing; long-chain horizontal scroll.
- Where the snapshot bar + transport controls sit in the restructured top bar.
- Reusing vs. lightly refactoring the current per-block render fn into pane renderers.

## Acceptance

- Flow renders horizontally with correct branches; four panes visible at once on a wide
  window; block editor shows **knobs**; preset browser and model browser are persistent.
- Live-write, follow-device, undo/redo, snapshots, Save, and adjective-search all still work;
  the preset round-trips cleanly (this is a view change; the written preset is unaffected).
- Each stage ships as a core release, HW-smoke-validated on the owner's XL
  (fw 1.4, `192.168.4.84` / USB); the plugin pin + skill docs bump after each core release.
