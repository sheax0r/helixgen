# Tone change-migration registry — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give helixgen a consent-gated, content-detected way to find tones made stale by engine fixes and repair them in place — plus per-tone provenance so repair/regeneration stops re-deriving intent.

**Architecture:** A declarative registry of `ChangeEntry` objects (one per tone-affecting fix), each a content detector + idempotent in-place migration, lives in core. A `library upgrade` driver iterates the managed tone library once, runs every entry per variant, reports exact tones/variants/blocks counts, and applies only on `--apply` (ascending `landed_in` order, writes `apply_prefs=False`, gated auto-commit). A `changes` verb renders the same registry as a changelog. `generate` stamps per-variant provenance (recipe + summaries + versions).

**Tech Stack:** Python, click. Engine package `helixgen` (helixgen-core). Tests: pytest + click `CliRunner`.

**Spec:** `docs/superpowers/specs/2026-11-21-tone-change-migration-registry-design.md` (helixgen repo). Plan implements it in **helixgen-core**; a companion plugin PR (pin bump + `setup`/`tone` skill + synced `docs/CLI.md`) is tracked separately, not in this plan.

**Worktree:** `/Users/michael.shea/git/helixgen-core/.worktrees/migration-registry` (branch `feat/tone-change-migration-registry`, from fresh `origin/main` @ 0.85.0).

## Global Constraints

- Engine changes land in **helixgen-core** only.
- Detectors inspect **content** via `hsp.read_hsp(path) -> dict` and walking `body["preset"]["flow"][i]["bNN"]` — never a version stamp alone, never parsed CLI text output.
- Migration writes use `hsp.dumps_hsp(body, apply_prefs=False)` — a fix must never inject preference-driven blocks (usb taps).
- Never auto-apply. `upgrade` default = read-only report; mutation only under `--apply`.
- Apply is idempotent: **dry-run row set == apply row set** on a clean library; a migrated tone yields no change and no warning.
- Multi-entry apply on one variant: ascending `landed_in` order; one `.hsp` write per variant after all entries; on failure restore original bytes (mirror `venue-retrofit` cli_library.py:1512-1525).
- Side effects per changed variant: clear `variant.normalized`, bump tone `updated`, `gitops.auto_commit(home.helixgen_home(), ...)` (gated by `git_commit_tones` as existing verbs are).
- Standalone `venue-retrofit` / `info-backfill` verbs stay; entries reuse their underlying library functions, no rewrite of the verbs.
- Version: bump **both** `pyproject.toml:3` and `src/helixgen/__init__.py:1` at release (drift mis-stamps provenance).
- `.hsp` stays canonical for preset data; provenance lives on the **variant** record in the tone-library JSON.

## Review Focus

- **Missing `.hsp` on disk** (`_resolve_variant_hsp` returns a path that doesn't exist): upgrade skips with a `status:"missing"` row, exits 0, does not crash. → Task 4.
- **Tone with no provenance** (every existing tone): detection is content-based and must not assume a `provenance` key exists. → Tasks 3/4.
- **Already-migrated tone**: detect returns None, no "would-change", no spurious warning (report #7). → Tasks 3/4/6.
- **`--only unknown-id`**: errors naming the unknown id; does not silently run nothing. → Task 4.
- **Empty library** (zero tones): exits 0 with "nothing to do", no traceback. → Task 4.
- **Block path input rendered dict-or-string / odd block shapes** (report #5): the fs-bypass detector walks the raw `read_hsp` dict defensively (skip slots lacking `@enabled`), never the lossy extractor. → Task 3.

---

### Task 1: Per-variant provenance

**Files:**
- Modify: `src/helixgen/tone_meta.py` (Variant dataclass :139-147, `_VARIANT_KEYS` :285-287, `_variant_to_dict` :294, `_variant_from_dict` :312, `upsert_variant` :556)
- Modify: `src/helixgen/cli.py:188-513` (`generate` command — new options + provenance build at the :496 upsert call site)
- Test: `tests/test_tone_meta.py`, `tests/test_generate_provenance.py` (new)

**Interfaces:**
- Produces: `Variant.provenance: dict | None` with keys `prompt_summary`, `research_summary`, `recipe`, `engine_version`, `plugin_version`, `authored_at`. Written by `generate` default (no-`-o`) path. New `generate` options `--prompt-summary`, `--research-summary`, `--plugin-version` (all optional).

- [ ] **Step 1: Failing test — provenance round-trips through the Variant JSON.** In `tests/test_tone_meta.py`, build a `ToneMeta` with a variant carrying `provenance={"recipe": {...}, "engine_version": "0.86.0", ...}`, `save_tone_meta` then `load`, assert `.provenance` equals the input (first-class, not swept into `extra`).
- [ ] **Step 2: Run it, expect FAIL** (`provenance` not a known key / attribute).
  Run: `pytest tests/test_tone_meta.py -k provenance -v`
- [ ] **Step 3: Add `provenance` field** to `Variant` (default `None`), to `_VARIANT_KEYS`, and to `_variant_to_dict`/`_variant_from_dict`. Omit the key from the dict when `None` (keep existing tones byte-stable).
- [ ] **Step 4: Run it, expect PASS.**
- [ ] **Step 5: Failing test — `generate` stamps provenance.** In `tests/test_generate_provenance.py`, invoke `generate <spec.json> --prompt-summary "warm lead" --plugin-version 5.30.0` (no `-o`), load the written tone meta, assert the variant's `provenance.recipe` equals the spec's parsed recipe, `provenance.engine_version == helixgen.__version__`, `provenance.prompt_summary == "warm lead"`, `provenance.plugin_version == "5.30.0"`, and `authored_at` is an ISO string. Use a minimal spec fixture (reuse an existing generate test's spec).
- [ ] **Step 6: Run it, expect FAIL** (unknown option / no provenance written).
- [ ] **Step 7: Implement.** Add the three `@click.option`s to `generate`. In the no-`-o` branch build `provenance = {"prompt_summary": ..., "research_summary": ..., "recipe": <parsed spec dict>, "engine_version": __version__, "plugin_version": ..., "authored_at": _iso_now()}` dropping `None`-valued summary/plugin keys, and pass it to the variant — via `upsert_variant(..., provenance=...)` (add the kwarg) or `place_tone(variant_fields={"provenance": ...})`. Explicit `-o` path unchanged (no meta written).
- [ ] **Step 8: Run both test files, expect PASS.**
- [ ] **Step 9: Commit** (`feat: stamp per-variant provenance on generate`).

---

### Task 2: Registry module + `changes` verb

**Files:**
- Create: `src/helixgen/changes.py`
- Modify: `src/helixgen/cli_library.py` (register a top-level `changes` command, exported like `describe`) and `src/helixgen/cli.py:2088-2092` (import + `add_command`)
- Test: `tests/test_changes.py` (new)

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True)
  class Finding:         # a detect/apply result for one variant
      affected: bool
      blocks: list[str]          # affected block ids; [] when block-level N/A
      status: str                # "would-<verb>" | "<verbed>" | "skipped" | "missing"
      detail: str = ""
  @dataclass(frozen=True)
  class ChangeEntry:
      id: str
      landed_in: str             # engine version the fix shipped in
      kind: str                  # "bugfix" | "protocol" | "cosmetic"
      summary: str
      research: str
      detect: Callable[["UpgradeCtx"], Finding]
      apply: Callable[["UpgradeCtx"], Finding]
  REGISTRY: list[ChangeEntry]    # ordered by landed_in ascending
  def entries_since(version: str | None) -> list[ChangeEntry]
  ```
  (`UpgradeCtx` defined in Task 4; Task 2 may forward-declare / type as `Any` until Task 4, since no entries exist yet.)

- [ ] **Step 1: Failing test — `changes` lists registry entries.** In `tests/test_changes.py`, monkeypatch `changes.REGISTRY` to one fake entry, invoke the `changes` command, assert output contains its `id`, `landed_in`, `kind`, `summary`. Then `changes --since <landed_in>` excludes it and `--since <older>` includes it. `--json` emits a list of dicts with those keys + `research`.
- [ ] **Step 2: Run it, expect FAIL** (no `changes` command).
- [ ] **Step 3: Implement** `changes.py` with the dataclasses, an empty `REGISTRY = []`, `entries_since`, and a `@click.command(name="changes")` `@click.option("--since")/("--json")` that renders them. Wire it into cli.py like `describe`.
- [ ] **Step 4: Run it, expect PASS.**
- [ ] **Step 5: Commit** (`feat: change registry scaffold + changes verb`).

---

### Task 3: Registry entry — footswitch-bypass snapshot-assign

**Files:**
- Create: `src/helixgen/changes_entries.py` (entry defs + their detect/apply fns; appended to `REGISTRY`)
- Test: `tests/test_change_fs_bypass.py` (new)

**Interfaces:**
- Consumes: `Finding`, `ChangeEntry` (Task 2); `UpgradeCtx` (Task 4) — a variant-scoped context exposing `.body: dict` (loaded `.hsp`). Until Task 4 lands, the detect/apply fns take `ctx` and use `ctx.body` only.
- Produces: entry `id="fs-bypass-snapshot-assign"`, `landed_in="0.84.0"`, `kind="bugfix"`, appended to `REGISTRY`.

**Basis:** `mutate.py:1869-1881` — a bypass footswitch (no `param`) pins `bnn["@enabled"]["snapshots"] = [bool(value)] * HSP_SNAPSHOT_SLOTS`. Pre-fix tones have the bypass `controller` on `@enabled` but no dense 8-element `snapshots`. Read the exact controller shape from mutate.py (`wrapped["controller"]`, written :1868) to write the predicate.

- [ ] **Step 1: Failing test.** Hand-build a body dict with one flow slot `bNN["@enabled"]` carrying a footswitch-bypass `controller` (shape copied from mutate.py) and `value: false`, and **no** `snapshots`. Assert `detect(ctx)` → `affected=True, blocks=["bNN"]`. Assert `apply(ctx)` sets `@enabled.snapshots == [False]*8` and returns `status` past-tense. Add a second slot that already has a dense `snapshots` → not counted (idempotence boundary). Add a slot with no `@enabled` → skipped, no crash (Review Focus: odd shapes).
- [ ] **Step 2: Run it, expect FAIL** (module/fns absent).
- [ ] **Step 3: Implement** `detect`/`apply` walking `ctx.body["preset"]["flow"][*]` for `bNN` dicts, guarding on presence of `@enabled` with a bypass controller and absence of a length-8 `snapshots`. Use `from helixgen.hsp import HSP_SNAPSHOT_SLOTS`. `apply` mutates `ctx.body` in place and returns a `Finding`. Append the `ChangeEntry` to `REGISTRY`.
- [ ] **Step 4: Run it, expect PASS.**
- [ ] **Step 5: Commit** (`feat: fs-bypass snapshot-assign migration entry`).

---

### Task 4: `library upgrade` driver

**Files:**
- Modify: `src/helixgen/cli_library.py` (new `@library.command(name="upgrade")`; `UpgradeCtx` dataclass + `iter_variant_ctxs(...)` helper; may live in `changes.py` if cleaner)
- Test: `tests/test_library_upgrade.py` (new)

**Interfaces:**
- Consumes: `REGISTRY`, `entries_since` (Task 2); entries from Task 3.
- Produces:
  ```python
  @dataclass
  class UpgradeCtx:
      hsp_path: Path
      body: dict
      meta: ToneMeta
      variant_key: str
      variant: Variant
      library_dir: Path
      irs_dir: Path | None
      home: Path
  ```
  Command: `library upgrade [--apply] [--json] [--only ID ...] [--since VERSION] [--library DIR] [--irs-dir DIR]`.

**Driver loop** (per variant, mirror venue-retrofit's atomic/restore posture):
1. resolve `.hsp`; if missing → `status:"missing"` row, continue.
2. `body = read_hsp(hsp_path)`; for each applicable entry (filtered by `--only`/`--since`, ascending `landed_in`): `f = entry.detect(ctx)`; collect findings.
3. report mode: emit rows. apply mode: for each affected entry in order call `entry.apply(ctx)` (mutates `ctx.body`/`ctx.variant`); if any changed, `_atomic_write(hsp_path, dumps_hsp(ctx.body, apply_prefs=False))`, `ctx.variant.normalized=None`, `save_tone_meta(meta)`, `auto_commit`; restore original bytes on exception.
4. Aggregate roll-up: affected **tones / variants / blocks**, per-entry and total.

- [ ] **Step 1: Failing test — dry-run then apply + idempotence.** Seed a tmp library (conftest gives tmp `HELIXGEN_HOME`) with two tones: one pre-fix (bypass FS, no dense snapshots) and one clean. `library upgrade` (no flags) reports `1 tone / 1 variant / 1 block` affected and writes nothing (assert `.hsp` bytes unchanged). `library upgrade --apply` migrates it; re-reading the `.hsp` shows dense snapshots. A second `--apply` reports 0 affected (idempotent). `--json` shape asserted.
- [ ] **Step 2: Run it, expect FAIL.**
- [ ] **Step 3: Implement** `UpgradeCtx`, `iter_variant_ctxs`, and the command per the driver loop. Roll-up counts from findings.
- [ ] **Step 4: Run it, expect PASS.**
- [ ] **Step 5: Edge tests (Review Focus).** `--only bogus` → nonzero exit naming the id. Empty library → exit 0, "nothing to do". A variant whose `.hsp` is absent → `status:"missing"`, exit 0. Add these to `tests/test_library_upgrade.py`; implement the guards to pass.
- [ ] **Step 6: Run full file, expect PASS.**
- [ ] **Step 7: Commit** (`feat: library upgrade driver`).

---

### Task 5: Fold factory-info-clear into the registry

**Files:**
- Modify: `src/helixgen/changes_entries.py` (new entry reusing `cli_library._factory_donor_infos` + the clear logic)
- Test: `tests/test_change_factory_info.py` (new)

**Interfaces:**
- Produces: entry `id="factory-info-clear"`, `landed_in="0.65.0"` (core #117/#132), `kind="cosmetic"`. detect: `ctx.body["meta"]["info"]` non-empty and in the donor set; apply: set `""`. Donor set computed once per run from `ctx.library_dir/chassis.json` (cache on ctx-driver or compute in detect via `_factory_donor_infos(ctx.library_dir)`).

- [ ] **Step 1: Failing test.** Seed a tone whose `meta.info` matches a donor string in a seeded `chassis.json`, and one with a user info string. `library upgrade --apply` clears the donor one, leaves the user one; dry-run reports the donor one as `would-clear`. Idempotent re-run: 0.
- [ ] **Step 2: Run it, expect FAIL.**
- [ ] **Step 3: Implement** the entry, reusing `_factory_donor_infos`. Append to `REGISTRY`.
- [ ] **Step 4: Run it, expect PASS.**
- [ ] **Step 5: Commit** (`feat: factory-info-clear migration entry`).

---

### Task 6: Fold headphones-highcut into the registry

**Files:**
- Modify: `src/helixgen/changes_entries.py` (entry reusing `venue.retrofit_headphones`)
- Test: `tests/test_change_headphones_highcut.py` (new)

**Interfaces:**
- Produces: entry `id="headphones-highcut"`, `landed_in="0.65.0"` (core #116), `kind="bugfix"`. detect: variant `venue == "headphones"` and `venue.retrofit_headphones(ctx.body, ctx.variant.venue_detail, library, irs, close_highcut_hz=<pref>).changed` is True; apply: set `ctx.body = res.body` and `ctx.variant.venue_detail = res.venue_detail`. Needs `ctx.library_dir`, `ctx.irs_dir`, and the `headphones_highcut_hz` preference. Non-headphones variants → not affected (skip). Reuse the dry-run posture so detect never mutates.

- [ ] **Step 1: Failing test.** Reuse `tests/test_venue.py` `lib`/`irs`/`_chain` fixtures. Seed a headphones variant with a wide-open close IR. `library upgrade --irs-dir ... --apply` clamps it (assert via `read_hsp` the High Cut lands at the pref ceiling); a non-headphones variant is untouched; dry-run == apply; idempotent re-run reports 0 and emits no spurious warning (report #7).
- [ ] **Step 2: Run it, expect FAIL.**
- [ ] **Step 3: Implement** the entry; thread `irs_dir`/pref through `UpgradeCtx` (add if not already present from Task 4). Append to `REGISTRY`.
- [ ] **Step 4: Run it, expect PASS.**
- [ ] **Step 5: Commit** (`feat: headphones-highcut migration entry`).

---

### Task 7: Version, parity, docs

**Files:**
- Modify: `pyproject.toml:3`, `src/helixgen/__init__.py:1` (bump to the next free core version — re-fetch `origin/main` first)
- Modify: `tests/test_cli_parity.py` (`NEW_SURFACES` table ~:183 — add rows pinning `library upgrade` and `changes` key `--help` phrases)
- Modify: `docs/CLI.md` (document `library upgrade`, `changes`, provenance fields; this is the core copy — the plugin PR syncs it)
- Test: `tests/test_cli_parity.py`

- [ ] **Step 1: Failing test — parity rows.** Add `NEW_SURFACES` rows requiring `library upgrade --help` to contain e.g. `"--apply"`, `"in place"`, `"consent"`/`"only applies"`, and `changes --help` to contain `"--since"`. Run parity; expect FAIL until help text matches.
- [ ] **Step 2: Make help text + docs match**; write the `docs/CLI.md` sections.
- [ ] **Step 3: Bump version** in both files (same value).
- [ ] **Step 4: Full suite** `pytest -q`; expect PASS.
- [ ] **Step 5: Commit** (`feat: version bump + CLI docs + parity for upgrade/changes`).

---

## Deferred (noted, not built here)

- `library ir-backfill` folding — mapping-level, doesn't fit the per-variant driver; standalone verb remains.
- Report #9 dead `~/.helixgen/setlists/manifest.json` cleanup — a one-off, not a per-tone content fix.
- Per-`.hsp` `meta["helixgen"]` provenance stamp — the variant JSON is the record of truth; not needed for detection.
- `library regenerate <tone>` — unblocked by the stored recipe; a separate feature.
