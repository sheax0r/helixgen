# Library drawer: tabs + IR-usage guard

**Date:** 2026-11-18
**Author:** Michael (with Claude)
**Status:** design — not yet implemented

## Intent and why

The library drawer inside `device live` ([shipped core 0.77.0](2026-11-16-live-library-drawer-design.md)) renders the whole hub as one scrolling panel: a Tones browse list, a Setlists section, an IRs section, stacked under three `<h3>`s (`liveedit/page.html` `renderLib`). Two gaps:

1. **The panel is one long scroll.** Tones, setlists, and IRs are three different jobs sharing one column. Splitting them into tabs makes each a place you go, not a thing you scroll past.
2. **IRs delete blind.** The IR row's Delete button calls `delete_ir` with no idea whether any on-device tone still references that IR — you can orphan a preset's cab/IR block by deleting an IR out from under it, and there's no way to see "what uses this" before you do. The user wants to (a) see which **on-device** tones reference an IR and remove them from the amp, and (b) be stopped from deleting an IR while on-device tones still reference it.

This is two small, independent pieces. Full structural preset editing (the third original ask) is explicitly out — see Non-goals.

## Goals

1. **Drawer is three tabs: Tones / Setlists / IRs.** One tab bar at the top of the drawer; one panel visible at a time. The browse list becomes its own tab alongside the other two.
2. **IR tab shows on-device usage on demand.** Expanding/clicking an IR runs a usage lookup and lists the on-device tones that reference it (name + which setlist/pool), with a button to **remove those tones from the device**.
3. **Remove is device-only.** Removing a referencing tone pulls it off the amp (pool + any setlist membership); the local authored `.hsp` library is untouched — it stays the source of truth.
4. **Delete-IR is guarded.** `delete_ir` refuses while any **on-device** tone references that IR. The remove-tones button is how you clear the blockers; once nothing on the amp uses it, delete succeeds. A local `.hsp` that references the IR does not block a device IR delete.
5. **Net-small.** The usage query, the guard, and the remove button all share one engine lookup; the tabs are page-only. No new leases, no new clients, no protocol work.

## Non-goals and anti-goals

- **No full/structural preset editing.** Dropped from this work. The live editor's existing non-goals stand (no add/remove/reorder blocks, no model swaps, no splits).
- **No eager full-device sweep.** The usage lookup reads every device preset's content (same cost as the drift reconcile). It runs **only when the user asks for a specific IR's usage**, never for every IR on every render, and never on drawer open. The delete guard runs the same sweep once, at delete time.
- **No new destructive one-click purge.** The button removes *tones*; it never deletes the IR as a side effect. Deleting the IR stays its own action, now gated by the guard.
- **Not multi-user, not remote.** Unchanged — localhost, single user at the amp.

## Constraints

- Core-first, cross-repo: the engine change (new `LibrarySession` method + `delete_ir` guard + drawer route) + page UI land and release in **helixgen-core** (PyPI) first; the plugin PR (synced `docs/`, engine-pin bump, release) follows and cross-references it. Worktrees from freshly fetched `origin/main`; adversarial review before merge.
- Core repo rules: TDD (failing test first), stdlib + `click` only (one self-contained `page.html`, no JS framework/CDN), per-verb/route behavior is the contract, `docs/CLI.md` updated in the same change if the CLI surface moves.
- `HelixClient` is not thread-safe. The usage sweep runs on the drawer's **existing dedicated library command client** (the one the reconcile already uses) under its own lock — no new client, no contention with the live editor's `editbuffer` client.

## Approaches

There is genuinely one sensible build: **additive**. Both pieces extend the existing merged drawer (server route ladder + `LibrarySession` + `page.html` `renderLib`) in place — the same pattern the drawer itself was built on. The alternatives were considered and dropped:

- *Guard in the page only* (JS checks usage before calling delete) — rejected: a guard that lives only in the browser leaves the CLI `delete-ir` and any other caller unguarded. The guard belongs in `LibrarySession.delete_ir` so every caller is protected (root-cause, not per-caller).
- *Precompute an IR→tones index in the diff cache* — rejected as speculative: the cache keys per-preset fingerprints, not IR hashes, and usage is a rare user-initiated action. A lazy on-demand sweep is cheaper to build and correct by construction. Add an index only if the on-demand sweep measurably drags.

## Decisions

1. **Tabs are page-only.** `[call]` `renderLib` splits its one `body` into a tab bar + three panels (Tones / Setlists / IRs), one visible at a time; the per-section builders move into their panels unchanged. The SSE delta handlers (`onDrawerDelta`) address nodes by id/`LIBV`/`LIBSL` map, so they keep working while a panel is hidden — no change to the event path. Remember the active tab across re-renders (trivial module var; browser storage reserved for nothing here).

2. **One engine lookup: `ir_usage(name_or_hash)`.** `[call]` New `LibrarySession` method. Resolves the IR to a hash, then over the dedicated library client sweeps device presets (`list_presets()` → each preset's content). Each device blob is the stored `…pgsm` form, so — exactly as `_default_diff` does — it must be untranscoded to an `.hsp` body (`untranscode.sbe_bytes_to_hsp`) before `extract_ir_hashes(body)` (`ir.py:531`) can read its IR hashes. Returns, for each on-device tone referencing the hash, `{name, cid, setlist}`; **plus a separate `indeterminate` list** of cids that would not untranscode (see Decision 3). Mounted as the `/library/ir_usage` route.

3. **`delete_ir` gains the guard, in the engine — and it fails *closed*.** `[call]` `LibrarySession.delete_ir` runs the same sweep first; if any on-device tone references the IR, it raises `LibraryError` listing them (status 409-ish) instead of deleting. This guards the drawer **and** the CLI `device delete-ir` uniformly. **Indeterminate presets** (those that won't untranscode, so the sweep can't prove they don't use the IR) are treated as **possible referencers and block the delete** — fail-closed matches the user's stated intent ("don't let the IR get removed if tones are referencing it"): when unsure, don't delete. Consequence: an indeterminate preset can't be surfaced as a removable tone in the usage list (we don't know it references the IR), so it can't be cleared through the normal remove button. Therefore **`force=True` is required, not optional, and is surfaced in the UI** (a "delete anyway" affordance on the blocked state) as well as the CLI (`delete-ir --force`) — it is the only remediation for an indeterminate block. The guard's block message distinguishes "N tones reference this (removable)" from "M presets couldn't be read (use force to override)".

4. **Remove-tones must fully clear the tone from the device.** `[call]` The outcome is non-negotiable: after the button runs, the removed tone references the IR nowhere on the amp, so the guard (Decision 3) can then let the IR be deleted. The naive "one `setlist_remove(also_pool=True)` per tone" does **not** achieve this — `copy.remove_tone(also_pool=True)` (`device/copy.py:292`) *refuses* to drop the pool copy while any **other** setlist still references the tone (returns `ok=False`, leaves the pool copy and thus the IR reference in place), and `setlist_remove` takes exactly one required setlist. So removal must handle:
   - **Multi-setlist tones:** remove every (tone, setlist) membership, then the pool copy. Either iterate `setlist_remove(also_pool=True)` across all of the tone's setlist memberships — tolerating the intermediate `ok=False`/"still referenced by…" results as *progress*, not failure, since only the last call actually deletes the pool copy — or add a thin engine helper (`remove_tone_everywhere(cid)`) that drops all refs then the pool copy in one shot. Builder's choice; the *complete-removal outcome* is the requirement.
   - **Pool-only tones** (no setlist membership — device-only rows, or `copy_to_device` with no `to`): remove the pool copy directly. Don't rely on passing an arbitrary setlist name; use the pool scope explicitly.

   No tone is "removed" until its IR reference is gone device-wide; a partial removal that leaves the IR un-deletable is a bug, not a tolerated state. After removal the usage list refreshes (re-query, or drop the row); the removed tones also disappear from the Tones tab via the existing `remove` SSE delta.

5. **Removal is confirmed, with the list.** `[call]` Removing tones is destructive, so the IR tab shows the referencing tones and a confirm step ("Remove these N tones from the device?") before calling removal — reuse the existing modal/overlay in `page.html`. No silent bulk delete.

6. **Usage lookup is lazy + shows a pending state.** `[call]` Per-IR usage is fetched when the user expands/clicks that IR (not on render), with a "checking…" state while the sweep runs. The IRs listing itself stays cheap (it already carries `hash`).

## What's left to the builder

- **Tab visual design**: the tab bar's placement/affordance within the narrow drawer, which tab opens by default (propose: Tones, matching today), and how the IR row expands to show its usage list.
- **`ir_usage` return shape + the setlist attribution**: a tone can sit in the pool and/or multiple setlists; decide how to present "where it lives" (pool vs setlist name) from the `pool`/`setlists` read model (`libraryui/session.py:280`+). Dedupe a tone that appears in several setlists.
- **Guard error contract**: the exact `LibraryError` shape/status `delete_ir` raises when blocked, how the page renders it (toast vs. inline list in the IR row), and whether `force` is surfaced in the UI or CLI-only. Add/adjust the CLI `delete-ir --help` and `docs/CLI.md` if `force` lands there.
- **Test strategy**: `LibrarySession`'s fake-seam tests cover `ir_usage` (hash present in some preset bodies, absent, device offline) and the `delete_ir` guard (blocked vs. clear vs. `force`) without hardware. Add a merged-handler test that the `/library/ir_usage` route answers and that the guard fires through the route. Page/tab behavior: a lightweight check that the tab bar renders three panels and SSE deltas still land in a hidden panel.
- **HW check (non-blocking)**: on the Stadium, confirm (a) the sweep reads enough preset content to see IR hashes for the IR types in play (cab IR, IR block, dual-cab); (b) removing a **multi-setlist** tone and a **pool-only** tone each clears the device reference the guard keys on (Decision 4's complete-removal path, not just the single-setlist case); and (c) **completeness** — that scanning the USER pool (`list_presets()` default container) catches every on-device IR reference, i.e. that the "never-orphan" invariant holds for presets placed via the Stadium app (not just helixgen) and that factory presets can't reference a user IR. If completeness fails, the sweep must widen beyond the default `list_presets()` container.

## Reference

- Drawer this extends: `docs/superpowers/specs/2026-11-16-live-library-drawer-design.md`; code `src/helixgen/liveedit/drawer.py`, `src/helixgen/liveedit/page.html` (`renderLib`), `src/helixgen/libraryui/session.py` (`delete_ir`, `setlist_remove`, read model).
- IR-hash extraction: `extract_ir_hashes` (`helixgen.cli` import surface); IR listing carries `hash`.
- Guard precedent: `library venue --force` drop-guard (`docs/superpowers/specs/2026-11-11-venue-variants-design.md`).
