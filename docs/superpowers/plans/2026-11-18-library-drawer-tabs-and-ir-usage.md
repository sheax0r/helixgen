# Library drawer: tabs + IR-usage guard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the `device live` library drawer into Tones/Setlists/IRs tabs, and make IRs show their on-device usage, remove the referencing tones device-wide, and refuse deletion of an IR that on-device tones still reference.

**Architecture:** All engine/UI work lands in **helixgen-core** (page-only tabs + one new device sweep reused by a `delete_ir` guard + a complete-removal primitive). The plugin repo follows with synced docs + engine-pin bump. Additive: no new leases, no new device client, no protocol work — the drawer's existing dedicated library client runs the sweep under its mutate lock.

**Tech Stack:** Python 3 (stdlib + `click`), one self-contained `src/helixgen/liveedit/page.html` (no JS framework/CDN), `pytest` + `testify`-style asserts, fake `*_fn` seams for device-free tests.

**Spec:** `docs/superpowers/specs/2026-11-18-library-drawer-tabs-and-ir-usage-design.md` (in this plugin repo).

## Global Constraints

- All code changes land in **helixgen-core** first; paths below are relative to that repo root. Worktree from freshly-fetched `origin/main`.
- TDD: failing test first, device-free via the injectable `*_fn` seams on `LibrarySession`.
- stdlib + `click` only; `page.html` stays one self-contained file, no CDN/framework.
- Keep the `*_fn` seams injectable; don't break the 67 existing libraryui fake-seam tests or the liveedit suite.
- Removal is **device-only**: the local authored `.hsp` library is never touched.
- The guard **fails closed**: a device preset that won't untranscode counts as a possible referencer and blocks the delete; `force=True` is the only override and is surfaced in the UI and the CLI.
- Core release is owner-gated (owner pushes the PyPI tag); plugin pin bump + release follows that.

## Review Focus

- **IR used by a multi-setlist tone** — remove must clear every setlist membership *and* the pool copy, or the IR stays un-deletable. Covered by Task 2.
- **IR used by a pool-only tone** (device-only row, no setlist) — remove must delete the pool copy directly, not demand a setlist. Covered by Task 2.
- **Device preset that won't untranscode during the sweep** — must be reported `indeterminate` and block delete (not silently skipped). Covered by Task 1 + Task 3.
- **IR referenced by nothing** — delete proceeds unguarded, exactly as today. Covered by Task 3.
- **No device connected** — `ir_usage` and the guard raise the existing "no Stadium connected" 409, never crash the page. Covered by Task 1.

---

### Task 1: `ir_usage` sweep on `LibrarySession`

**Files:**
- Modify: `src/helixgen/libraryui/session.py`
- Test: `tests/test_libraryui_session.py` (existing fake-seam suite)

**Interfaces:**
- Consumes: `self._device_model()` → `{"pool_rows": [{"cid_", "name"}], ...}`; a client's `get_content(cid) -> bytes`; `helixgen.device.untranscode.sbe_bytes_to_hsp(blob, name=, library=, author=None)`; `helixgen.ir.extract_ir_hashes(body: dict) -> list[str]`; `helixgen.library.Library` / `default_library_path`.
- Produces: `LibrarySession.ir_usage(name_or_hash) -> {"hash": str, "tones": [{"cid": int, "name": str, "setlists": [str]}], "indeterminate": [int]}`. `tones` = on-device presets that reference the hash; `indeterminate` = pool cids whose content would not untranscode.
- Produces (seam): a `usage_fn` default `_default_ir_usage(client, target_hash, device_model) -> {"tones", "indeterminate"}` injected like the other `*_fn`s, so tests drive it without a device.

- [ ] **Step 1: Write the failing test** `test_ir_usage_lists_referencing_tones`

```python
def test_ir_usage_lists_referencing_tones():
    # device model: pool_rows with cids; fake usage_fn maps the target hash
    # to two tones (one in setlists ["Rock"], one pool-only) and one indeterminate cid.
    s = make_session(usage_fn=lambda c, h, dm: {
        "tones": [{"cid": 11, "name": "A", "setlists": ["Rock"]},
                  {"cid": 12, "name": "B", "setlists": []}],
        "indeterminate": [99]})
    out = s.ir_usage("MyCab")      # resolves name -> hash via _ir_view
    assert out["hash"]             # resolved
    assert [t["cid"] for t in out["tones"]] == [11, 12]
    assert out["indeterminate"] == [99]
```

- [ ] **Step 2: Run to verify it fails** — `pytest tests/test_libraryui_session.py::test_ir_usage_lists_referencing_tones -v` → FAIL (`ir_usage` undefined).

- [ ] **Step 3: Implement `ir_usage(self, name_or_hash) -> dict`** in `session.py`. Resolve `name_or_hash` to a hash against `self._ir_view(self._device_model())` (accept an exact hash too). Then `self._run(lambda h: self._usage_fn(h, target_hash, self._device_model()))` wrapped with the resolved `hash`. Implement `_default_ir_usage(client, target_hash, device_model)`: for each `pool_rows` row, `blob = client.get_content(cid)`; try `body = untranscode.sbe_bytes_to_hsp(blob, name="x", library=lib, author=None)` then `target_hash in extract_ir_hashes(body)` → append `{cid, name, setlists}` (setlists from the device_model's setlist membership for that cid); on untranscode/exception → append cid to `indeterminate`. Add `usage_fn=_default_ir_usage` to `__init__` and store `self._usage_fn`.

- [ ] **Step 4: Run to verify it passes.**

- [ ] **Step 5: Add `test_ir_usage_offline_raises`** — `make_session(client_factory=None)`; `ir_usage(...)` raises `LibraryError` status 409. Run; it passes (via `_run`'s existing guard) or implement the early resolve to defer to `_run`.

- [ ] **Step 6: Commit** — `feat(libraryui): ir_usage sweep — which on-device tones reference an IR`.

---

### Task 2: complete device-wide tone removal

**Files:**
- Modify: `src/helixgen/device/copy.py` (new `remove_tone_everywhere`)
- Modify: `src/helixgen/libraryui/session.py` (new `remove_tone_device` + `remove_everywhere_fn` seam)
- Test: `tests/test_device_copy.py`, `tests/test_libraryui_session.py`

**Interfaces:**
- Consumes: `copy._other_setlists_referencing(client, pool_cid, exclude_setlist=None)`; `client.list_setlists()`; `client.remove_reference(setlist_cid, cid)`; `client._raw.delete(Container.POOL, [cid])`; `resolve_setlist_cid`.
- Produces: `copy.remove_tone_everywhere(client, cid: int) -> {"ok": bool, "removed_refs": [int], "removed_pool": Optional[int], "errors": [str]}` — drops the pool preset `cid`'s reference from **every** setlist that holds it, then deletes the pool copy. Idempotent-ish: a cid already gone is `ok` with empty removals.
- Produces: `LibrarySession.remove_tone_device(cid) -> dict` calling `remove_everywhere_fn` (default `lambda c, cid: copy.remove_tone_everywhere(c, cid)`) under `_run`.

- [ ] **Step 1: Write failing test** `test_remove_tone_everywhere_multi_setlist` (fake client: cid 11 referenced by setlists "Rock" and "Jazz" + pool). Assert both refs removed then pool deleted, `ok is True`.

- [ ] **Step 2: Add `test_remove_tone_everywhere_pool_only`** — cid 12 in no setlist; assert pool deleted directly, no setlist error, `ok is True`.

- [ ] **Step 3: Run both → FAIL** (`remove_tone_everywhere` undefined).

- [ ] **Step 4: Implement `remove_tone_everywhere`** in `copy.py`: under `client.mutating()`, find all setlists referencing `cid` (iterate `list_setlists()` → `list_container` refs, or reuse `_other_setlists_referencing(client, cid, exclude_setlist=None)`); `remove_reference` each (collect `removed_refs`, append error on refusal); then `_raw.delete(Container.POOL, [cid])` → `removed_pool`; `ok = not errors`.

- [ ] **Step 5: Run → PASS.**

- [ ] **Step 6: Add `test_remove_tone_device_wraps` in the session suite** — `make_session(remove_everywhere_fn=fake)`; `remove_tone_device(11)` returns the fake's dict; offline → 409. Implement `remove_tone_device` + seam. Run → PASS.

- [ ] **Step 7: Commit** — `feat(device): remove_tone_everywhere — clear a tone from all setlists + pool`.

---

### Task 3: `delete_ir` fail-closed guard + `force`

**Files:**
- Modify: `src/helixgen/libraryui/session.py` (`delete_ir`)
- Test: `tests/test_libraryui_session.py`

**Interfaces:**
- Consumes: `self.ir_usage(name_or_hash)` (Task 1); existing `self._delete_ir_fn`.
- Produces: `LibrarySession.delete_ir(name_or_hash, force: bool = False) -> dict`. Blocked → `LibraryError(status=409)` whose message lists referencing tone names and the indeterminate count; `force=True` skips the check and deletes.

- [ ] **Step 1: Write failing tests:**
  - `test_delete_ir_blocked_by_referencing_tone` — `usage_fn` returns one tone → `delete_ir("MyCab")` raises `LibraryError` status 409; `_delete_ir_fn` NOT called.
  - `test_delete_ir_blocked_by_indeterminate` — `usage_fn` returns `tones: [], indeterminate: [99]` → still raises 409.
  - `test_delete_ir_force_overrides` — same, `force=True` → `_delete_ir_fn` called, returns ok.
  - `test_delete_ir_unreferenced_proceeds` — empty usage → deletes as today.

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement the guard** in `delete_ir`: if not `force`, `u = self.ir_usage(name_or_hash)`; if `u["tones"] or u["indeterminate"]` raise `LibraryError(<message>, status=409)` before calling `_delete_ir_fn`. Message distinguishes "N tones reference this (remove them first)" from "M presets couldn't be read — use force".

- [ ] **Step 4: Run → PASS.**

- [ ] **Step 5: Commit** — `feat(libraryui): delete_ir refuses while on-device tones reference the IR (fail-closed, --force override)`.

---

### Task 4: drawer routes + CLI `--force`

**Files:**
- Modify: `src/helixgen/liveedit/drawer.py` (`_ACTIONS`)
- Modify: `src/helixgen/cli.py` (`device delete-ir --force`) + `docs/CLI.md` if the verb exists there
- Test: `tests/` liveedit drawer/handler test; `tests/test_cli_parity.py` if `--help` changes

**Interfaces:**
- Consumes: `LibrarySession.ir_usage`, `remove_tone_device`, `delete_ir(force=)`.
- Produces routes: `ir_usage` → `s.ir_usage(p["name_or_hash"])`; `remove_tone_device` → `s.remove_tone_device(p["cid"])`; `delete_ir` → `s.delete_ir(p["name_or_hash"], force=bool(p.get("force")))`.

- [ ] **Step 1: Write failing test** that the merged handler answers `POST /library/ir_usage` and `/library/remove_tone_device`, and that `delete_ir` passes `force` through.

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Add the three `_ACTIONS` entries** in `drawer.py` (mirror existing lambdas). Add `--force` to the CLI `delete-ir` command (locate it; wire to `delete_ir(force=...)`); update its `--help`/`docs/CLI.md`.

- [ ] **Step 4: Run → PASS** (incl. `tests/test_cli_parity.py` if touched).

- [ ] **Step 5: Commit** — `feat(liveedit,cli): wire ir_usage / remove_tone_device / delete_ir --force`.

---

### Task 5: drawer tabs + IR-usage UI (page.html)

**Files:**
- Modify: `src/helixgen/liveedit/page.html` (`renderLib`, drawer CSS, `onDrawerDelta`)
- Test: a lightweight DOM/string check in the liveedit page test if one exists; otherwise manual + the HW check.

**Interfaces:**
- Consumes: `/library/state` (unchanged shape), `/library/ir_usage`, `/library/remove_tone_device`, `/library/delete_ir` (now takes `force`).

- [ ] **Step 1: Tabs.** Split `renderLib`'s single `body` into a tab bar (`Tones` / `Setlists` / `IRs`) + three panels, one visible at a time; move each existing section builder into its panel unchanged. Keep a module-level `activeTab` so re-render restores it. Verify `onDrawerDelta` still finds `#ltones` / `LIBV` / `LIBSL` nodes while a panel is hidden (don't gate panel content on visibility — hide with CSS, keep nodes in DOM).

- [ ] **Step 2: IR usage.** Per IR row, add a "Used by…" control that `POST`s `/library/ir_usage` and renders the returned tones (name + setlist) inline, each with a per-tone implicit part of a single **"Remove N tones from device"** confirm action that calls `/library/remove_tone_device` per `cid`, then re-queries usage. Show a "checking…" state while the sweep runs.

- [ ] **Step 3: Delete guard UX.** On a `delete_ir` 409, render the blocked message inline in the IR row (referencing tones + indeterminate count) with a **"Delete anyway"** affordance that re-calls `delete_ir` with `force:true` (confirm first). Non-blocked delete behaves as today.

- [ ] **Step 4: Verify in the running app** (see Finishing): launch `helixgen device live`, open the drawer, exercise the three tabs, an IR with/without usage, remove, and a blocked delete + force. Read page via the browser tools; don't trust an un-run claim.

- [ ] **Step 5: Commit** — `feat(liveedit): drawer tabs + IR usage/remove/guarded-delete UI`.

---

### Task 6: full suite + docs sync

- [ ] **Step 1:** Run the whole core suite: `pytest -q`. All green.
- [ ] **Step 2:** Update `docs/CLI.md` / any `device --help` text the changes touched; confirm `tests/test_cli_parity.py` passes.
- [ ] **Step 3: Commit** any doc deltas — `docs: sync CLI/help for ir_usage + delete-ir --force`.

## Self-Review notes

- Spec coverage: tabs (Task 5) · ir_usage sweep + indeterminate (Task 1) · fail-closed guard + force (Task 3) · complete device-only removal incl. multi-setlist & pool-only (Task 2) · routes/CLI (Task 4) · docs (Task 6). All spec decisions map to a task.
- Type consistency: `ir_usage` returns `{hash, tones:[{cid,name,setlists}], indeterminate:[cid]}` — consumed identically in Tasks 3/4/5. `remove_tone_everywhere` → `remove_tone_device` → `/library/remove_tone_device(cid)` consistent.
- Review Focus: each line has an owning task above.
