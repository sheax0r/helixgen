# One surface: the library hub as a drawer inside `device live`

**Date:** 2026-11-16
**Author:** Michael (with Claude)
**Status:** design — not yet implemented

## Intent and why

Today there are two separate localhost browser apps that both talk to the Stadium:

- **`device live`** (core `liveedit`) — the chain-knob editor: the active tone as a signal chain, every param a knob, live writes, undo/redo, device-native Save, plus the adjective-search knob highlight. Requires a connected device; holds the `editbuffer` lease.
- **`library ui`** (core `libraryui`) — the hub: browse/search the authored tone + IR library, diff it against the device, reconcile (copy to device, pull back, setlist CRUD, IR push/delete/rename). Offline-first; holds the `library`+`irs` leases. Its Phase 2 "Edit" button already launches `device live` in-process (`liveedit/embed.py`).

They are two commands, two windows, two leases — and the user experiences the library side as "a standalone thing." The goal is **one surface**: you open the chain editor, and the library is a drawer inside it. The thing you look at and work in most — the chain, the knobs, the adjective highlight — is the frame. The library is where you reach when you want a *different* tone, or to see what's drifted, or to push/pull/organize. Picking a tone in the drawer loads it straight into the live editor.

The abandoned `tweak-ui` prototype is dead (cleaned up 2026-11-16); its idea already lives on as the adjective highlight in `device live`. This work is unrelated to it.

## Goals

1. **One launcher, one window, one process.** `/helixgen:live` (→ `helixgen device live`) opens a single page: the chain editor with a slide-out library drawer. No second command, no second server, no second browser window.
2. **The library drawer carries the whole hub** — browse/search/filter, per-tone drift badges, copy-to-device, pull-back, setlist create/rename/delete/duplicate/add/remove/move, IR push/delete/rename.
3. **Pick a tone in the drawer → it loads live.** The drawer's "Edit this tone" loads the preset into the running live session; the chain re-renders; the drawer closes.
4. **Graceful with no device.** The app binds and serves with no Stadium present: the chain area shows a connect/empty state, the library drawer works offline (computer side), and a no-device launch opens the drawer by default (nothing to edit yet). This preserves offline library use under the one command.
5. **Net-delete, not net-add.** The merge removes the Phase 2 embed machinery and the duplicated server/guard code rather than piling a third thing on top.
6. **Device state stays current without work.** The drawer reflects changes made on the amp — saves, setlist edits, IR changes — without the user clicking refresh, and without re-scanning everything on each launch: PUB-subscriber events for freshness + a persistent diff cache reconciled in the background (Decision 4).

## Non-goals and anti-goals

- **Not an arbitrary structural editor.** Carry `device live`'s existing non-goals: no adding/removing/reordering blocks, no creating splits, no model swaps, from the chain view.
- **No latency regression.** `device live`'s live-write path (settle=0 + client-side coalescing, the anti-backlog design) must be untouched. A write must never queue without bound.
- **The page must not lie about the device.** The live edit buffer stays the only source the chain renders from; failed writes stay visible; a reconnect re-reads. The drawer's device-side presence/diff data must not claim a tone is on the device when it isn't. A **cached** diff verdict is provisional — shown as "verifying" until this session's background reconcile or a subscriber event confirms it, never presented as a verified in-sync state on its own.
- **Not multi-user, not remote.** Localhost only, single user at the amp.
- **Anti-goal — a page too big to maintain.** Approach 2 merges two large self-contained HTML files into one. If the merged `page.html` becomes unmaintainable, that is the signal the iframe approach (Approach 1, below) was the right call. This is a tripwire, not a goal.

## Constraints

- Core repo rules: TDD (failing test first), stdlib + `click` only (no web framework, no JS framework, no CDN — one self-contained HTML file), per-verb `--help` is the behavioral contract (pinned by `tests/test_cli_parity.py`), `docs/CLI.md` + `docs/helix-protocol.md` updated in the same change.
- Cross-repo: core lands and releases first (PyPI); the plugin PR (new skill + synced `docs/` + engine-pin bump + release) follows and cross-references it. Worktrees from freshly fetched `origin/main`; adversarial review before merge.
- **`HelixClient` is not thread-safe.** Each command client (the live editor's `editbuffer` client and the library's own client, Decision 4) is driven single-threaded / under its own lock; the two run concurrently. The 2001/2003 subscriber is a separate receive-only socket shared by both. The device network stack is flaky — connections drop and must re-establish without restarting the page.

## Approaches

All approaches share the same spine, which the architecture recon (origin/main) confirmed is a clean fit:

- liveedit's server is a plain `ThreadingHTTPServer` with a flat `_route` ladder over one `session` object (`liveedit/server.py:50`, GET dispatch `:116`) — adding the library endpoints is purely additive.
- liveedit already exposes **`LiveSession.load_preset(cid)`** (`liveedit/session.py:544`) — exactly the drawer's "edit this tone" hook. No new session API.
- libraryui's actions are already server-agnostic methods behind injectable `*_fn` seams (`libraryui/session.py`) — they mount onto liveedit's handler as-is; its read model is `public_state()` (`:315`).
- **`liveedit/embed.py` drops entirely.** It only exists because library is *currently* the frame and must stand liveedit up as a second server. Inverted, the live stack is already running and `load_preset` replaces the handoff.
- The duplicated Host/Origin/Content-Type guards and the `make_server`/`Handler`/`serve` skeleton (copy-pasted across the two `server.py` files) collapse to one copy.

**Approach 1 — iframe the existing library page into the drawer.** One merged server, but the drawer hosts libraryui's current `page.html` ~verbatim in an `<iframe>`, with one `postMessage` bridge for "Edit this cid" → parent `load_preset`. Reuses a whole shipped page; smallest diff. Cost: an iframe seam (two DOMs), and the full-screen hub shown inside a side panel.

**Approach 2 — merge the two pages into one DOM. (CHOSEN)** Port libraryui's browse/diff/reconcile/setlist/IR UI into liveedit's `page.html` as a hand-built slide-out drawer: one DOM, shared styling, one state tree, a drawer tailored for drawer context. Most cohesive, no iframe quirks. Cost: reconciling two big self-contained HTML files (styles, scripts, state) is the real work and risk.

**Chosen: Approach 2.** The user wants one seamless surface, not a hub bolted into a side panel. The spine (server merge, `load_preset` hook, embed deletion) is identical either way; Approach 2 spends its extra effort entirely on the page. Approach 1 is the fallback if the page merge proves unmaintainable (see the anti-goal tripwire).

## Decisions

1. **Chain editor is the frame; library is a drawer.** `[Michael]` A slide-out drawer toggled from the chain page (e.g. a `[≡ Library]` control). Open = browse/diff/reconcile/manage; "Edit this tone" loads it and closes the drawer.

2. **One server hosts both.** `[call]` liveedit's `ThreadingHTTPServer` gains the ~15 library POST routes (into the `_route` ladder, `server.py:50`) and the library GET routes (`do_GET`, `server.py:116`). The handler closes over both a `LiveSession` and a `LibrarySession`.

3. **`load_preset(cid)` is the Edit hook.** `[call]` The drawer's "Edit this tone" calls `LiveSession.load_preset(cid)` (`session.py:544`), guarded by the existing dirty flag (`session._dirty`; the equivalent guard today lives in `libraryui`'s `edit_handoff`, not in `embed.py`). No new API.

4. **Drawer freshness — subscribe, cache, reconcile in the background; never poll, no mandatory re-scan.** `[Michael]` Three mechanisms, ordered by how often they run:
   - **Subscribe (continuous, free).** One shared 2001/2003 PUB subscriber — a separate, receive-only socket, already run by the live editor, so no lock and no contention — feeds *both* the chain and the drawer. The drawer reacts to **stored-state** events: active-preset change (`loadContentRef`, known today) and, pending the capture spike, preset-save / setlist / IR events. A relevant event re-reads **only the affected item** (one RPC), never the whole library. Live knob/snapshot events are ignored by the drawer — they don't change stored content until a Save.
   - **Cache (persistent, server-side).** The expensive part — reading + diffing every device preset against the computer's `.hsp` — is cached so it is **not paid on every launch**. The cache is a small file under `~/.helixgen/`, keyed per-Stadium device id, storing per preset `cid`: the device-content fingerprint (the canonical hash `content_diff` already computes), the library `.hsp` hash, the verdict, and a timestamp — **not** full content, and **not** the browser (the server owns the device connection, the files, and the diff; browser storage is reserved for trivial UI prefs). Library-side staleness is detected cheaply and locally by `.hsp` hash; device-side staleness by the subscriber + the startup reconcile.
   - **Background reconcile (once per connect).** On device connect the drawer renders **instantly from cache** (entries shown provisional / "verifying"), and a **background job** reconciles the cache against the device, settling each badge as results land. This *is* the re-scan — automatic, no button required (a manual "re-check" may be kept as a cheap fallback — optional). How cheap the reconcile is hinges on the spike: if the device's preset listing exposes a per-preset version/hash/mtime, the job lists once and re-reads only changed presets; if not, it re-reads all (cold cost) or trusts cache+subscriber for presets unchanged since last session.
   - **Connections (this supersedes the earlier single-client sketch).** The background reconcile is a *sustained* read that runs every connect and must not stall the live editor, so the library gets **its own dedicated command client** for its reads (the sweep, targeted re-reads) and actions; the live editor keeps its `editbuffer` client; the subscriber is shared. Each command client is single-threaded / under its own lock; the two run concurrently — no knob stall for library reads. Phase 2 already ran concurrent clients against the Stadium (HW-validated), so two REQ connections are tolerated. libraryui's per-action `with client_factory() as h:` becomes one persistent non-closing library client (IR SFTP still against the same `ip`). **Writes** (copy/pull/setlist/IR vs. a live Save) are rare and user-initiated — coordinate them with a light app-level write-lock only if the spike shows the device dislikes concurrent *writes*.

5. **One process holds `editbuffer` + `library` + `irs`.** `[call]` Via the shared `helixgen.locks`. `library`+`irs` are taken once at startup, pid-bound (as the hub does today, `cli_library.py:2127`); `editbuffer` stays lazy/per-write with idle release (liveedit's model). liveedit's Save already escalates into `library` transiently, so the scopes already coexist in one process. Consequence: while the unified app is open, no other helixgen process can run library ops — acceptable for a single user at the amp.

6. **Graceful offline — new cold-start + discovery work.** `[Michael]` The app binds and serves with **no device**: the `HelixClient`, PUB subscriber, firmware check, and initial edit-buffer load are all **deferred**, not done at startup. (Today `device live` does them eagerly and aborts without a device; this is genuinely new work, distinct from the existing dropped-connection reconnect, which only recovers a session that *started* connected.) With no device: the library drawer runs offline (`lease=None`, `connected:false`) and opens by default; the chain area shows a connect/empty state. A **discovery loop** (the existing `device discover` mechanism, polled) detects an amp appearing and brings the chain online — construct the client + subscriber lazily on first connect, run the firmware-1.4 gate only then, load the edit buffer, render the chain. The `[device]` extra is always present in the plugin's install, so routing offline library use through `device live` doesn't gate it behind hardware.

7. **Delete the Phase 2 embed.** `[call]` Remove `liveedit/embed.py`, `EmbeddedEditor`, and `libraryui`'s `edit_handoff` launcher seam. Collapse the duplicated Host/Origin/Content-Type guards and the server skeleton to one copy. Bump the merged server's `MAX_BODY` to 256K (libraryui's cap; IR/copy bodies need it).

8. **Retire the standalone `library ui` command.** `[Michael]` Resolved: **remove it outright**, no alias. `/helixgen:live` is the single launcher; the drawer carries the full hub and (per Decision 6) works with no amp, so the offline use `library ui` served is fully covered. The `cli_library.py` `ui` verb and its lease/launcher plumbing are deleted; `library`'s other verbs (tag, list, etc.) stay.

9. **New `helixgen:live` launcher skill.** `[call]` A thin `skills/live/SKILL.md`: resolve `HELIXGEN_LIBRARY`, run `helixgen device live` backgrounded, hand the user the localhost URL, do not narrate knob moves. It leans on `setup` for CLI provisioning. This supersedes the live-chain-editor spec's Decision 10 ("no new skill"). The `device` skill's live section (if any) is trimmed to point at `/helixgen:live`.

10. **Host verb stays `helixgen device live`.** `[call]` It already exists and the skill abstracts the name; renaming to a top-level `helixgen live` is avoidable CLI-surface churn. The verb gains the drawer; its `--help` documents it.

## What's left to the builder

- **Drawer visual design** within the chain page: layout, width, how much of the hub shows at once, how the facet filters / setlist / IR sections fit a drawer rather than a full screen. (A layout mockup is worth a spike.)
- **Refresh choreography** when `load_preset` fires from the drawer: reuse liveedit's existing preset-switch rebuild-from-pushed-blob path (zero device I/O) rather than a fresh read; confirm the drawer's drift badges refresh after a copy/pull without a full re-render.
- **Test strategy:** libraryui's 67 fake-seam tests and liveedit's suite must both survive the mount; add a merged-handler test proving the library routes answer on the one server and that the single device lock serializes a library action against a live write. Keep the `*_fn` seams injectable.
- **Lease-ownership detail:** confirm the startup acquisition of `library`+`irs` coexists with liveedit's lazy `editbuffer` without a deadlock when Save escalates.
- **2001 capture + listing spike — do this first** (Decision 4): on the Stadium, capture the 2001 stream while (a) saving a preset, (b) editing a setlist, (c) pushing/deleting an IR, to learn which stored-state changes emit events and their layouts — this sets how much of the drawer is reactive vs. needs a targeted re-read. In the same pass, determine whether the preset / setlist / IR **listings carry a cheap per-item version/hash/mtime** (decides whether a warm-cache reconcile lists-and-re-diffs-only-changed, or must re-read all). And confirm two concurrent command connections coexist, including a **library write during a live Save** (Phase 2 ran concurrent clients; concurrent *writes* are the unverified part).
- **Cache format + invalidation** (Decision 4): the `~/.helixgen/` per-device cache schema (per-cid fingerprint / verdict / `.hsp` hash / timestamp), provisional-until-verified rendering, and local `.hsp`-hash invalidation on the library side.
- **Device-discovery mechanism** (Decision 6): how a never-connected app notices an amp appearing — poll `device discover` on an interval, the cold-start → connect → firmware-gate → edit-buffer-load → render sequence, and the connect/empty chain state. Also confirm a library mutation's own PUB echo (`loadContentRef` etc.) doesn't spuriously trigger a live-chain preset-switch/re-read.

## Reference

- Live chain editor design: `docs/superpowers/specs/2026-11-12-live-chain-editor-design.md` (this supersedes its Decision 10).
- Core packages: `src/helixgen/liveedit/` (host), `src/helixgen/libraryui/` (actions + read model, mounted), `helixgen.locks` (shared leases), `helixgen.liveedit.window` (browser launcher, already shared).
- Deleted by this work: `src/helixgen/liveedit/embed.py`.
