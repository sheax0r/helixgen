# Library-Drawer-in-`device live` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge the library hub (`library ui`) into the `device live` chain editor as one surface — chain editor as the frame, library as a slide-out drawer — with event-driven freshness, a persistent diff cache, offline cold-start, and a `helixgen:live` launcher skill.

**Architecture:** `liveedit` becomes the single host: its `ThreadingHTTPServer` mounts the library's actions + read model (a `LibraryDrawer` wrapping `libraryui.session.LibrarySession` on its own dedicated command client); the page gains a drawer in one DOM; `load_preset(cid)` is the Edit hook; `embed.py` is deleted. Freshness is driven by the 2001 content-store events (spike-decoded) plus a server-side diff cache reconciled in the background on connect. `device live` cold-starts with no device and discovers one.

**Tech Stack:** Python 3.12, stdlib `http.server` (ThreadingHTTPServer) + `click`, pyzmq/msgpack transport (the `[device]` extra), one self-contained `page.html` (no JS framework/CDN). Tests: pytest + the existing fake-seam patterns.

**Spec:** `docs/superpowers/specs/2026-11-16-live-library-drawer-design.md` (read it; this plan argues from it). The **Spike findings** table there is the authoritative 2001 event vocabulary.

**Repos:** core work lands in `helixgen-core` (a worktree off fresh `origin/main`); the plugin skill + doc sync land in this repo (`helixgen`). Core releases first (owner pushes the PyPI tag); the plugin pin-bump PR follows.

## Global Constraints

- Core repo rules: TDD (failing test first), **stdlib + `click` only** (no web framework, no JS framework, no CDN); **one self-contained `page.html`**; each verb's `--help` is the behavioral contract (pinned by `tests/test_cli_parity.py`); `docs/CLI.md` + `docs/helix-protocol.md` updated in the same change.
- `HelixClient` is **not thread-safe**: each command client is driven single-threaded / under its own lock. The live editor keeps its `editbuffer` client; the library gets its **own dedicated** command client. The 2001/2003 subscriber is one shared receive-only socket.
- Device I/O serializes per client; a library **write** coordinates with a live Save via a light app-level write-lock only if HW shows concurrent writes misbehave (residual check — single-lock fallback otherwise).
- Leases via `helixgen.locks`: one process holds `editbuffer` (lazy/per-write) + `library` + `irs` (taken once at startup, pid-bound). liveedit Save already escalates into `library`.
- The page must **not lie about the device**: failed writes stay visible; a cached diff verdict is provisional ("verifying") until this session's reconcile or a subscriber event confirms it.
- No live-write latency regression: the steady `set_param` path (settle=0 + coalescing) is untouched; library reads run on the library client, never stalling the chain.
- `NOISE_ADDRS` is only `{/heartbeat,/trigger}` — **filter `/dspEvent` explicitly**.
- Localhost only; `127.0.0.1` bind; Host/Origin/Content-Type guards retained (deduped to one copy).

## Review Focus

- **Stale cache presented as truth.** A preset changed on the amp while the app was closed → cold reconcile must re-read+diff it (no `cid_` change to key on); until reconciled its badge reads "verifying", never "in sync". Test in Task 7.
- **Lease deadlock on Save.** liveedit Save escalates `editbuffer`→`+library`; the drawer holds `library` at startup → Save must not deadlock against the drawer's own `library` hold (same pid, re-entrant/compatible). Test in Task 3.
- **Event echo loops.** A drawer-initiated write (copy/save) emits `/addContent`/`/saveContentRef` that the shared subscriber sees → applying it must be idempotent and must not re-trigger the action or a spurious full re-read. Test in Task 6.
- **Drawer refresh stalling the chain.** The background reconcile / drawer reads must run on the library client; a concurrent live `set_param` must not block behind them. Test in Task 5.
- **Offline cold-start.** `device live` with no amp must bind, serve, open the drawer, and not crash on absent device; discovery then connects. Test in Task 9.

---

## Phase A — Server unification (liveedit hosts the library)

### Task 1: `LibraryDrawer` — mount library actions + read model on a dedicated client

**Files:**
- Create: `src/helixgen/liveedit/drawer.py`
- Test: `tests/test_liveedit_drawer.py`

**Interfaces:**
- Consumes: `libraryui.session.LibrarySession` (actions behind `*_fn` seams; `public_state()`), `HelixClient`.
- Produces:
  - `class LibraryDrawer` constructed `LibraryDrawer(library_root, irs_root, *, client_factory, cache)` where `client_factory` returns the **dedicated, non-closing** library client.
  - `.public_state() -> dict` (delegates to the inner `LibrarySession`, merges cache-backed diff badges).
  - `.action(name: str, payload: dict) -> dict` dispatch for the library verbs (`copy, pull, update_local, content_diff, setlist_*, push_ir, delete_ir, rename_ir`).
  - `.apply_event(ev) -> Optional[dict]` (Task 6 fills this in; stub returns None here).

- [ ] **Step 1: Write failing test** `test_drawer_public_state_offline` — construct a `LibraryDrawer` with `client_factory=None` (offline) over a temp library dir with one `.hsp`; assert `public_state()["connected"] is False` and the tone appears with `presence == "computer"`.
- [ ] **Step 2: Write failing test** `test_drawer_action_dispatch` — a fake client records calls; `drawer.action("copy", {...})` routes to the inner session's `copy_to_device` via the injected `copy_fn`.
- [ ] **Step 3: Run tests, verify fail** (`ImportError`/`AttributeError`).
- [ ] **Step 4: Implement `LibraryDrawer`** wrapping `LibrarySession`, passing a **non-closing client adapter** as `client_factory` (an object whose `__enter__` returns the persistent client and whose `__exit__` does nothing). Keep the inner session's `*_fn` seams untouched.
- [ ] **Step 5: Run tests, verify pass.**
- [ ] **Step 6: Commit** `feat(liveedit): LibraryDrawer mounts library actions on a dedicated client`.

### Task 2: Mount library routes on the liveedit server

**Files:**
- Modify: `src/helixgen/liveedit/server.py` (`_route` at ~:50, `do_GET` at ~:116, `MAX_BODY` ~:35, guards ~:160-186, `make_server`)
- Test: `tests/test_liveedit_server_library_routes.py`

**Interfaces:**
- Consumes: Task 1 `LibraryDrawer`.
- Produces: `make_server(session, *, drawer=None, ...)` — the handler closes over both. New routes: GET `/library/state`; POST `/library/<action>` for each action name.

- [ ] **Step 1: Write failing test** `test_library_state_route` — build the server with a fake `LiveSession` + a `LibraryDrawer` over a temp lib; GET `/library/state` returns the drawer's `public_state()` JSON; an existing liveedit GET (`/state`) still works.
- [ ] **Step 2: Write failing test** `test_library_action_route` — POST `/library/copy` with a JSON body dispatches to `drawer.action("copy", body)`; a non-JSON body returns 415; an unknown action returns 404.
- [ ] **Step 3: Run, verify fail.**
- [ ] **Step 4: Implement** — add the GET/POST branches; raise `MAX_BODY` to `256*1024`; extract the duplicated Host/Origin/Content-Type guard into one module-level helper used by both liveedit and (via import) the former libraryui paths. Handler gets `drawer` from the `make_server` closure.
- [ ] **Step 5: Run, verify pass.**
- [ ] **Step 6: Commit** `feat(liveedit): serve library state + actions on the live server`.

## Phase B — Diff cache + background reconcile

### Task 3: `DiffCache` — persistent per-device diff cache

**Files:**
- Create: `src/helixgen/liveedit/diffcache.py`
- Test: `tests/test_liveedit_diffcache.py`

**Interfaces:**
- Produces: `class DiffCache(path)`; entry per `cid`: `{device_fp, hsp_hash, verdict, ts}`.
  - `.get(cid) -> Optional[entry]`, `.put(cid, entry)`, `.invalidate(cid)`, `.load()`, `.save()`.
  - `.verdict(cid, hsp_hash) -> Optional[str]` — returns the cached verdict only if the stored `hsp_hash` matches the current one (library-side staleness), else `None` (needs reconcile).
  - Path default: `~/.helixgen/diffcache/<device_serial>.json`.

- [ ] **Step 1: Write failing test** `test_cache_roundtrip_and_hsp_invalidation` — put a verdict; `verdict(cid, same_hash)` returns it; `verdict(cid, different_hash)` returns `None`.
- [ ] **Step 2: Write failing test** `test_cache_survives_reload` — save to a temp file, construct a new `DiffCache` on it, assert the entry is present.
- [ ] **Step 3: Run, verify fail.**
- [ ] **Step 4: Implement** — plain JSON file, atomic write (`os.replace`), tolerant of a missing/corrupt file (start empty). `# ponytail: whole-file JSON cache, fine for ~100 presets`.
- [ ] **Step 5: Run, verify pass.**
- [ ] **Step 6: Commit** `feat(liveedit): persistent per-device diff cache`.

### Task 4: Diff-badge resolution through the cache (provisional-until-verified)

**Files:**
- Modify: `src/helixgen/liveedit/drawer.py`
- Test: `tests/test_liveedit_drawer.py`

**Interfaces:**
- Produces: `LibraryDrawer.public_state()` now stamps each on-both tone with `diff: "same"|"changed"|"verifying"|"indeterminate"` using the cache (`"verifying"` when no fresh cached verdict). `.resolve_diff(cid) -> str` computes one tone's verdict via the inner session's `content_diff` and writes it to the cache.

- [ ] **Step 1: Write failing test** `test_public_state_badges_provisional` — with an empty cache, on-both tones come back `diff == "verifying"`.
- [ ] **Step 2: Write failing test** `test_resolve_diff_caches` — `resolve_diff(cid)` returns a verdict and a subsequent `public_state()` shows it settled (not "verifying").
- [ ] **Step 3: Run, verify fail.**
- [ ] **Step 4: Implement** — read the cache in `public_state()`; `resolve_diff` calls `content_diff` (the `diff_fn` seam) and `cache.put`.
- [ ] **Step 5: Run, verify pass.**
- [ ] **Step 6: Commit** `feat(liveedit): provisional diff badges resolved through the cache`.

### Task 5: Background reconcile on the library client

**Files:**
- Create: `src/helixgen/liveedit/reconcile.py`
- Test: `tests/test_liveedit_reconcile.py`

**Interfaces:**
- Produces: `run_reconcile(drawer, *, on_update: Callable[[str, str], None], should_stop: Callable[[], bool]) -> None` — iterates on-both tones whose cached verdict is stale/missing, calls `drawer.resolve_diff(cid)` on the **library client**, invokes `on_update(cid, verdict)` per result, and bails cooperatively when `should_stop()` (page closed / reconnect). IRs resolved by `hash` set-diff (no content read).

- [ ] **Step 1: Write failing test** `test_reconcile_settles_only_stale` — seed the cache with one fresh verdict and one missing; a fake `resolve_diff` counter proves only the missing one is read; `on_update` is called once.
- [ ] **Step 2: Write failing test** `test_reconcile_stops_cooperatively` — `should_stop` flips true after the first tone; assert it halts.
- [ ] **Step 3: Run, verify fail.**
- [ ] **Step 4: Implement** — plain loop; no threading inside (the caller runs it on a daemon thread with the library client). IR diff via `device_ir_hashes` vs library hashes.
- [ ] **Step 5: Run, verify pass.**
- [ ] **Step 6: Commit** `feat(liveedit): background diff reconcile on the library client`.

## Phase C — Reactive freshness (2001 content events → drawer)

### Task 6: Decode content-store events and apply to the drawer

**Files:**
- Modify: `src/helixgen/liveedit/events.py`, `src/helixgen/liveedit/drawer.py`
- Test: `tests/test_liveedit_content_events.py`

**Interfaces:**
- Produces: `events.decode_content_event(ev) -> Optional[ContentEvent]` for `/addContent, /updateContent, /removeContent, /updateContainerContent, /loadContentRef, /saveContentRef` (layouts: see the spec's Spike findings table). `LibraryDrawer.apply_event(ce) -> Optional[dict]` mutates drawer state: `/saveContentRef cid` → `cache.invalidate(cid)` + mark that tone `"verifying"` and schedule a `resolve_diff`; `/addContent|/removeContent` → add/drop the row; `/updateContainerContent` → replace that setlist's membership; `/loadContentRef` → set the active cid. Returns a drawer-state delta to push to the page, or `None` for irrelevant events.

- [ ] **Step 1: Write failing test** `test_saveContentRef_invalidates_and_reverifies` — feed a decoded `/saveContentRef [.., 2088]`; assert `cache.get(2088)` is cleared and that tone reads `"verifying"`.
- [ ] **Step 2: Write failing test** `test_updateContainerContent_replaces_membership` — feed a setlist membership event; assert the drawer's setlist members match the broadcast list.
- [ ] **Step 3: Write failing test** `test_self_initiated_event_is_idempotent` — applying the same `/addContent` twice yields one row, no exception (echo-loop guard).
- [ ] **Step 4: Run, verify fail.**
- [ ] **Step 5: Implement** the decoders (exact arg positions from the spec table) + `apply_event`. Filter `/dspEvent` and `NOISE_ADDRS`. A `resolve_diff` triggered here runs on the library client via the caller's scheduler.
- [ ] **Step 6: Run, verify pass.**
- [ ] **Step 7: Commit** `feat(liveedit): react to 2001 content-store events in the drawer`.

## Phase D — The drawer UI (page merge)

### Task 7: Merge the library drawer into `page.html`

**Files:**
- Modify: `src/helixgen/liveedit/page.html`
- Test: `tests/js/liveedit_page_scenarios.js` (+ a Python smoke test that the page serves and references the library endpoints)

**Interfaces:**
- Consumes: GET `/library/state`, POST `/library/<action>`, the SSE `/events` channel (extended to carry drawer deltas).
- Produces: a slide-out drawer toggled by a `[≡ Library]` control: browse/search/filter tones, per-tone diff badge (`same`/`changed — pull ←`/`verifying`), copy/pull, setlist + IR management, and an **Edit/Load** control that POSTs `/preset` (`load_preset`) then closes the drawer. Badges render provisional and settle from SSE deltas. No framework; vanilla JS in the one file.

- [ ] **Step 1: Write failing JS scenario** `drawer opens and renders tones from /library/state`; `a "verifying" badge settles to "changed" on an SSE delta`; `"Edit" posts /preset and collapses the drawer`.
- [ ] **Step 2: Run the JS scenario harness, verify fail.**
- [ ] **Step 3: Implement** the drawer markup + JS: fetch `/library/state` on open, render; subscribe to SSE deltas for badge/membership updates; wire the action buttons. Keep open cards / scroll on in-place badge updates (no full re-render), per Phase 2's pattern.
- [ ] **Step 4: Run JS scenarios, verify pass.**
- [ ] **Step 5: Add a Python smoke test** the served page contains the drawer markers and the library endpoint paths; run, verify pass.
- [ ] **Step 6: Commit** `feat(liveedit): library drawer in the live page (merged DOM)`.

## Phase E — Offline cold-start + device discovery

### Task 8: Defer device bring-up; serve with no amp

**Files:**
- Modify: `src/helixgen/cli_device.py` (`device live`), `src/helixgen/liveedit/session.py`
- Test: `tests/test_liveedit_offline_start.py`

**Interfaces:**
- Produces: `LiveSession` constructs with `client=None` allowed; `.connected -> bool`; bring-up (`HelixClient` connect, firmware-1.4 gate, edit-buffer load, subscriber) moves into `.connect_device(ip)` called lazily. `device live` binds + serves immediately; the drawer opens by default when `not connected`.

- [ ] **Step 1: Write failing test** `test_server_serves_without_device` — build the server with `client=None`; GET `/state` returns `{connected: false, ...}` without raising; GET `/library/state` works offline.
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** — guard every device call in `LiveSession` behind `connected`; `connect_device` does the eager sequence that `device live` does today; the firmware gate runs only on connect.
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** `feat(liveedit): cold-start without a device`.

### Task 9: Device-discovery loop → connect → populate

**Files:**
- Modify: `src/helixgen/cli_device.py` (`device live`), `src/helixgen/liveedit/session.py`
- Test: `tests/test_liveedit_discovery.py`

**Interfaces:**
- Produces: a daemon discovery loop (polls the existing `device discover` mechanism on an interval) that, on first sighting, calls `LiveSession.connect_device(ip)`, starts the subscriber, kicks off `run_reconcile` on the library client, and pushes a `connected` SSE delta. A later drop resumes discovery.

- [ ] **Step 1: Write failing test** `test_discovery_connects_and_reconciles` — a fake discovery returns an ip after N polls; assert `connect_device` is called once and a reconcile is scheduled.
- [ ] **Step 2: Run, verify fail.**
- [ ] **Step 3: Implement** — the loop with a stop flag; idempotent connect (ignore if already connected); confirm a library mutation's own PUB echo doesn't trigger a spurious chain preset-switch (reuse liveedit's existing foreign-change handling).
- [ ] **Step 4: Run, verify pass.**
- [ ] **Step 5: Commit** `feat(liveedit): discover and connect a device at runtime`.

## Phase F — Retire `library ui`; delete the embed

### Task 10: Hold library+irs leases at startup; delete `embed.py`; remove `library ui`

**Files:**
- Modify: `src/helixgen/cli_device.py` (`device live` lease acquisition), `src/helixgen/cli_library.py` (remove `ui`), `src/helixgen/libraryui/session.py` (drop `edit_handoff` launcher seam)
- Delete: `src/helixgen/liveedit/embed.py`
- Test: `tests/test_cli_parity.py` (update), `tests/test_liveedit_leases.py`

**Interfaces:**
- Produces: `device live` acquires `library`+`irs` (pid-bound, best-effort/offline-tolerant) at startup alongside its lazy `editbuffer`; `library ui` verb removed; `embed.py` and `EmbeddedEditor` gone.

- [ ] **Step 1: Write failing test** `test_live_holds_library_irs` — the startup path acquires `library`+`irs` via `helixgen.locks` (fake lock records scopes); `test_save_escalation_no_deadlock` — Save's `editbuffer+library` escalation succeeds while the drawer holds `library` (same pid).
- [ ] **Step 2: Update `test_cli_parity.py`** to expect `library ui` absent and `device live --help` to mention the drawer.
- [ ] **Step 3: Run, verify fail.**
- [ ] **Step 4: Implement** — move the hub's startup lease into `device live`; delete `embed.py` + the `ui` verb + `edit_handoff` launcher; keep `libraryui.session` (now consumed by `LibraryDrawer`) and `library`'s non-ui verbs.
- [ ] **Step 5: Run full core suite + parity, verify pass.**
- [ ] **Step 6: Commit** `feat: retire library ui, fold the hub into device live; drop embed.py`.

### Task 11: Update `device live --help` + `docs/CLI.md` + `docs/helix-protocol.md`

**Files:** Modify `src/helixgen/cli_device.py` (help text), `docs/CLI.md`, `docs/helix-protocol.md`
- [ ] **Step 1:** Update `device live --help` to document the drawer, offline start, and that it supersedes `library ui`. Add the content-store events to `docs/helix-protocol.md` (from the spec table).
- [ ] **Step 2:** Update `docs/CLI.md`: remove the `library ui` section, expand `device live`.
- [ ] **Step 3:** Run `test_cli_parity.py`, verify pass.
- [ ] **Step 4: Commit** `docs: device live drawer + content-store events; remove library ui`.

## Phase G — Core release + plugin surface

### Task 12: Core version bump + PR (release owner-gated)

- [ ] **Step 1:** Bump core version in `pyproject.toml` (next free minor; re-fetch `origin/main` first).
- [ ] **Step 2:** Run the full suite + build the wheel; verify `liveedit/page.html` ships in the wheel ([[feedback_verify_published_wheel]]).
- [ ] **Step 3:** Open the core PR; dispatch an adversarial review subagent; fix confirmed findings.
- [ ] **Step 4:** Merge to `main`. **STOP — the owner pushes the `vX.Y.Z` tag** (PyPI publish). Do not push core release tags.

### Task 13 (this repo): `helixgen:live` skill + device-skill trim + pin bump + plugin release

**Files:** Create `skills/live/SKILL.md`; modify `skills/device/SKILL.md`, `README.md`, `docs/CLI.md`, `tests/test_skills.py` (ENGINE_PIN), `.claude-plugin/plugin.json` + `marketplace.json`.
- [ ] **Step 1:** Write `skills/live/SKILL.md` — thin launcher: resolve `HELIXGEN_LIBRARY`, run `helixgen device live` backgrounded, hand over the localhost URL, don't narrate knob moves; leans on `setup` for provisioning.
- [ ] **Step 2:** Trim the `device` skill's live section to point at `/helixgen:live`; sync `docs/CLI.md`.
- [ ] **Step 3:** Bump `ENGINE_PIN` + README + skill pins to the new engine version; bump plugin version in both manifests.
- [ ] **Step 4:** Run `python3 -m pytest tests/` (skill checks), verify pass.
- [ ] **Step 5:** Open the plugin PR **after** PyPI has the new engine release; adversarial review; merge (workflow auto-tags + moves `stable`).

---

## Self-review notes

- **Spec coverage:** Goals 1–6 map to Tasks 2/13 (one launcher), 1–2/7 (drawer carries the hub), 7+Task6 (pick→load), 8–9 (offline), 10 (net-delete embed), 3–6 (freshness). Decisions 1–10 + Spike findings each have an owning task.
- **Review Focus** items are pinned to Tasks 7, 3, 6, 5, 9 respectively.
- **Type consistency:** `LibraryDrawer.resolve_diff/apply_event/action/public_state`, `DiffCache.verdict`, `run_reconcile(on_update, should_stop)`, `LiveSession.connect_device/connected` are used consistently across tasks.
- **Residual HW checks** (non-blocking, from the spec): IR event shape; two concurrent REQ clients under a library-write-during-Save. Verify opportunistically during Task 9/10 bring-up on the Stadium; single-lock fallback covers the latter.
