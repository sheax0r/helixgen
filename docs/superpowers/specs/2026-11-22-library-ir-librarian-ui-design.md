# Library-management parity — IR (`81v.7`) + Preset/librarian (`81v.9`) — design

**Status:** design — awaiting approval.
**Date:** 2026-11-22.
**Scope:** two parity beads, one spec, because they are **one surface**: the
`device live` **library drawer**. This document designs the *gaps* between the
drawer as it ships today and the Line 6 **Helix Stadium Edit** Librarian view —
not a redesign of the drawer, which already carries the hub (browse/search/drift/
copy/pull/setlist CRUD/IR push·rename·delete·usage).
**Extends, does not duplicate:**
[`2026-11-16-live-library-drawer-design.md`](2026-11-16-live-library-drawer-design.md)
(the drawer-as-frame, one server, cache/reconcile model) and
[`2026-11-18-library-drawer-tabs-and-ir-usage-design.md`](2026-11-18-library-drawer-tabs-and-ir-usage-design.md)
(the three-tab split + `ir_usage` + fail-closed `delete_ir` guard). Read both
first — this spec assumes their decisions as the baseline.
**Quality bar / sibling epic:**
[`2026-11-21-signalflow-editor-parity-design.md`](2026-11-21-signalflow-editor-parity-design.md)
(`81v.1`). Collisions with it are called out in §0 and §C.

---

## 0. The one decision that shapes both beads — library-first vs device-mirror

The brief's key question: helixgen owns an **external on-disk library**
(`$HELIXGEN_HOME/library/` — a flat directory of `.hsp` files + an IR registry)
that the Stadium app **cannot see or touch**. The Stadium device *also* stores
organizational libraries (IRs, Templates, Favorites, Clones — up to 2,048 of
some), and the app mirrors those. So every gap below forces a per-feature choice:
does helixgen store the new state **on disk (library-first)** or **mirror the
device's own librarian (device-mirror)**?

The existing project model already answers most of it, and we keep faith with it
rather than inventing a second source of truth:

- **CLAUDE.md / the `device` verb are explicit:** *"THE DEVICE IS THE TRUTH about
  what is loaded and in what order … There is no local intent file."* Ordering,
  setlist membership, MIDI PC — **device-mirror**. helixgen already reorders on
  the device (`device reorder` / `move`); we never shadow order on disk.
- **The drawer's own charter** ([drawer spec](2026-11-16-live-library-drawer-design.md)
  Goal 2, Non-goal "page must not lie about the device") makes the on-disk `.hsp`
  library *the* truth for **authored content**, the device a copy target. So any
  gap that is really *"how do I organize my authored assets"* — folders,
  templates — is **library-first**. This is also the only coherent choice,
  because the whole point of the external library is that it outlives and
  out-scales the device's 512/2,048 slots and survives a factory reset.

### The split (justified per feature in §A/§B)

| Gap | Where state lives | Why |
|---|---|---|
| IR **folders** | **library-first** (disk) | device IR store is flat, hash-addressed; folders are app-side organization the device never needed |
| IR **import / convert / export / 2048-cap** | **device-mirror** (the acts) over library-first assets | the IR *lives* on disk; push/pull are device I/O helixgen already does |
| IR **unresolved-on-delete** | **device-mirror** | it is the *device's* own behaviour; helixgen only chooses to allow or guard it |
| Preset/template/favorite **folders** | **library-first** (disk) | organization of authored `.hsp`; device has no folder concept for presets |
| **Templates** (as library assets) | **library-first** | a template is just a starting-point `.hsp`; `New-from-template` *instantiation* is the editor epic, not this one (§C) |
| Preset **order / MIDI PC / setlist membership** | **device-mirror** | device is the truth for order; PC = position is hardware behaviour |
| Preset **color / notes** | **device-mirror** (write-through) | already a content attr the device round-trips (`device set-info`) |
| Whole-**setlist** export/import as one file | **device-mirror** source, disk artifact | `.hss` already exports a device setlist with full preset copies |
| **Favorites** (model favorites), **Clones** (proxy captures), preset **clips** | see §B won't-do | out of mission and/or collide with `81v.1`; reasoned-out |

**Net:** *organization* is library-first (disk owns folders + templates);
*ordering and device state* is device-mirror (the device stays the truth). This
is not a new model — it is the drawer's existing model carried to the gaps. No
feature below introduces a second authority over the same fact.

---

# BEAD 81v.7 — IR management parity

## A.1 Intent / why

The drawer already does the hard device-side IR work: `push-ir` (instant
watched-dir import with the `HASH` chunk so presets resolve), `rename-ir`,
`delete-ir` (fail-closed guard, §A.5), `ir_usage` (which on-device tones
reference an IR), `ir-prune`. What it does **not** yet have, measured against the
Stadium Librarian's Cab-IR view:

1. **Import a WAV of any sample rate** — the app accepts *"mono or stereo IR .wav
   files of any sample rate and bit depth"* and auto-converts. helixgen's
   canonicalizer **refuses anything but 48 kHz** (see §A.3).
2. **Folders** — the app groups IRs into folders ("folders always appear at the
   top"); helixgen's library + device listing are flat.
3. **Export** — multi-select IRs → a folder on disk. helixgen has single-file
   `pull-ir` only.
4. **A clear picture of the 2,048 cap** — the engine enforces it; the drawer
   doesn't show headroom.
5. **Unresolved-on-delete** done the *app's* way (let the delete happen, preset
   Cab tab goes "UNRESOLVED") vs helixgen's current *fail-closed* guard.
6. **Boot-reindex** heads-up after a bulk import.

## A.2 Goals

- Import a WAV of **any sample rate / bit depth / mono-or-stereo** from the IR
  tab; it lands on the device *and* in the on-disk IR library, converted to the
  device's 48 kHz / mono canonical form, resolving in presets immediately.
- **Folders** in the IR tab: create, rename, delete, move IRs in/out — a
  library-first organization layer; the device IR store stays flat.
- **Export** one or many IRs to a chosen folder on disk (the `.wav`).
- The IR tab shows **slot headroom** (`N / 2048`) and refuses/annotates an import
  that would overflow (the engine already refuses; surface it).
- **Delete** keeps the drawer's **fail-closed guard** as the default, but adds an
  explicit **"delete anyway → tones go UNRESOLVED"** affordance that matches the
  app's behaviour, surfaced with the consequence named.
- After a **large** import batch, a one-line note that the *next* device boot may
  take longer to index (then not again).

## A.3 Engine readiness — IR (what exists vs new)

| Capability | Engine today | Verdict |
|---|---|---|
| Instant device import w/ hash resolution | `device push-ir` (watched-dir + `HASH` chunk + cache nudge) | **READY** |
| Stereo→mono downmix + canonical quantize | `ir.py` canonicalizer (float round-trip → mono PCM_24) | **READY** |
| **Resample to 48 kHz** | **`ir.py:359` REFUSES non-48 kHz** — raises `ValueError` with a `sox -r 48000` hint | **NEW ENGINE WORK** |
| 2,048-slot cap enforcement | `push-ir` refuses a full device before upload; `copy --auto-irs` refuses an overflowing batch naming headroom | **READY** (needs a *read* of the count for the UI) |
| Single-IR export | `device pull-ir FILENAME OUTFILE` (by on-device basename from `list-irs --json`) | **READY** (multi-select is UI fan-out) |
| Rename / delete / prune | `rename-ir`, `delete-ir` (+`--force`/`--force-wedge`), `ir-prune` | **READY** |
| Usage lookup + fail-closed delete guard | `ir_usage` + guarded `delete_ir` ([tabs+usage spec](2026-11-18-library-drawer-tabs-and-ir-usage-design.md)) | **READY (designed; verify shipped)** |
| **IR folders** | none — library is a flat `tones/`+IR registry; device container -11 is flat | **NEW — library-first, disk-only** |

**The single real engine gap is resampling.** Everything else is UI over shipped
verbs or a disk-side metadata layer.

- **Resampling (the gap).** The app accepts any rate and converts to 48 kHz;
  helixgen stops at the door. Fix lands in **helixgen-core**: teach the
  `ir.py` canonicalizer to resample to 48 kHz inside its existing float
  round-trip (it already reads floats via libsndfile and rewrites — add a
  resample stage before the mono/quantize phase), behind the same hash
  computation so the resampled IR hashes deterministically. **Open question for
  the builder:** which resampler, and whether it must match the device/app's own
  resampling *bit-for-bit* (the device computes the `irhash` on *its* converted
  form — if helixgen's resample diverges from the app's, the same source WAV
  imported two ways gets two hashes and two slots). Needs an HW capture: import
  one non-48 kHz WAV via the Stadium app, read its on-device hash, and match
  helixgen's resampler to it. Until matched, resampling is **best-effort** and the
  UI says "converted to 48 kHz (hash may differ from a Stadium-app import of the
  same file)".
- **Bit depth is NOT a gap.** The app's *"32-bit float"* is its internal DSP
  representation; helixgen's PCM_24 canonical IRs already register and resolve on
  the device today (shipped). We do not chase 32f — the `irhash` is what presets
  key on, and helixgen's hash path is proven. (Flag only: confirm no device
  firmware rejects PCM_24 on import — it doesn't today.)

## A.4 The how — IR tab extensions

Built on the **existing IR tab** (tab #3 from the
[tabs spec](2026-11-18-library-drawer-tabs-and-ir-usage-design.md)); all new
pieces are additive routes on the one merged server + `LibrarySession`, the same
pattern the drawer is built on.

- **Import control** (new): a file-pick / drag-drop on the IR tab → POST the WAV
  to a new `/library/import_ir` route → `LibrarySession.import_ir(path, folder=…)`
  which (1) canonicalizes+resamples via `ir.py` into the on-disk IR library, (2)
  `push-ir`s it to the device, (3) records folder membership (§A.6). Pre-flight:
  read the device IR count; if `≥2048`, block with the engine's own
  "free space first" message before converting. Show a per-file progress/row
  (convert → upload → registered), reusing the drawer's existing action-row
  pattern.
- **Folders** (new, library-first — §A.6).
- **Export** (new): multi-select → `/library/export_ir` → fan out `pull-ir` to a
  chosen disk folder. Reuses `list-irs --json`'s `file` basename (the download
  key). Export is **read-only** on the device (no lease).
- **Headroom** (new): the IR tab header shows `N / 2048`, N from the cheap
  `list-irs` count (already carries hashes; no content sweep).
- **Delete** (change): keep the fail-closed guard as default (it already lists
  referencing tones + a remove-tones path). Add a secondary **"Delete anyway"**
  that calls `delete-ir --force` and names the outcome *in the app's own words* —
  *"the Cab block tab in N preset(s) will show UNRESOLVED"* — so helixgen's
  stricter default and the app's permissive behaviour are both reachable, the
  permissive one only behind an explicit, consequence-labelled click.
- **Boot-reindex note** (new, informational): after an import batch above a
  threshold (propose ~200, the manual's "several hundred"), a dismissible
  one-liner: *"Large IR import — your next Helix power-on may take a few extra
  minutes to index. Later boots won't."* No engine work; pure copy.

## A.5 Unresolved-on-delete — reconciling two philosophies

The app lets you delete an in-use IR and **degrades the preset** (Cab tab →
"UNRESOLVED", preset kept). helixgen today **refuses** (fail-closed guard, treats
even unreadable presets as possible referencers). These are not in conflict —
helixgen's guard is the *safer default*, and we keep it. The design adds the
app's permissive path as an **explicit escape hatch** (§A.4 "Delete anyway"), not
as the default. Rationale, carried from the
[tabs+usage spec](2026-11-18-library-drawer-tabs-and-ir-usage-design.md) Decision
3: "when unsure, don't delete" is the right default for an *external* library
owner that the user may be curating offline; the app can afford to be cavalier
because it only ever sees the device. We surface both; we default to safe.

## A.6 IR folders — library-first, disk-only (decision + mechanism)

The device IR store (container -11) is **flat and hash-addressed** — there is no
device-side folder to mirror. The app's folders are an organizational layer *the
app* maintains. So helixgen owns IR folders **on disk**, as the library's own
structure, and the device never learns about them.

- **Mechanism (builder's choice, propose the lighter):** either (a) real
  subdirectories under the IR library dir, or (b) a small sidecar
  `~/.helixgen/library/ir-folders.json` mapping IR hash → folder path. Propose
  **(b) sidecar** — it survives `rename-ir` (which changes only the display name,
  not the hash the folder keys on), doesn't fight the registry's hash-addressing,
  and a missing/empty sidecar degrades to today's flat view (no migration). Real
  subdirs (a) are more visible in a `git` checkout but re-sort on every rename and
  double as content; the sidecar keeps folders as *pure metadata*.
- **Device-side is untouched:** copy/push/pull ignore folders entirely; an IR in
  a folder uploads exactly as one at root. Folders are a *view*, never a device
  write. This is the cleanest expression of library-first: the organization is
  helixgen's, the resolution is the device's hash.
- **This is genuinely new state helixgen has never kept.** It is the one piece of
  81v.7 that is neither "UI over a shipped verb" nor "surface an engine behaviour"
  — flag it as the sub-bead that needs its own small engine PR
  (`LibrarySession` folder CRUD + the sidecar).

---

# BEAD 81v.9 — Preset / librarian management parity

## B.1 Intent / why

The drawer already browses/searches the authored tone library, badges drift,
copies to device, pulls back, and does full setlist CRUD (create/rename/delete/
duplicate/membership/reorder). Measured against the Stadium Librarian's Presets +
Templates view, the gaps are: **templates** as a managed asset class, **folders**
for presets/templates, **batch color**, **preset notes** surfaced, **richer
search**, **`.hsp`/`.hlx` import into the library**, **whole-setlist file
export/import**, and making the **reorder → MIDI PC renumber** consequence legible.

The device's own model is a near-exact match for helixgen's existing one — *"512
user preset locations … up to 122 setlists … each 1–128 presets … setlist
entries are aliases (pointers) to USER PRESETS"* is precisely helixgen's
pool(-2)+setlist-reference model. So most of this bead is **UI + organization**,
with little new device protocol.

## B.2 Goals

- **Templates as a library asset class:** a Templates view in the drawer (store /
  rename / delete / organize into folders / copy-to-device) over `.hsp` files the
  user has marked as starting points. *(Live "New Preset from template" that
  synthesizes routing is explicitly deferred to the editor epic — §C.)*
- **Folders** for presets and templates (library-first, disk).
- **Batch color** across multi-selected presets (device write-through).
- **Preset notes** visible + editable in the drawer (device write-through).
- **Search** that also matches **notes** and **model/amp name**, not just preset
  name/tags.
- **Import** `.hsp` / `.hlx` into the library from the drawer (→ `ingest`).
- **Export a whole setlist** as one `.hss` file, and **import** one.
- The reorder UI **states that it renumbers MIDI PC** (device behaviour) so a
  reorder isn't a silent MIDI change.

## B.3 Engine readiness — Preset/librarian (what exists vs new)

| Capability | Engine today | Verdict |
|---|---|---|
| Browse/search/drift/copy/pull/setlist CRUD | drawer + `libraryui` + `device copy/create/rm/move/reorder/setlist *` | **READY (shipped drawer)** |
| **Batch color + notes** write-through | `device set-info CIDS… --color --notes` (batch-capable, non-activating round-trip) | **READY** — pure UI |
| Reorder → MIDI PC renumber | `device reorder` / `move`; PC = position is **device-native** | **READY** — surface the consequence only |
| Import `.hsp`/`.hlx`/`.json` into library | `helixgen ingest PATH` (also recurses dirs) | **READY** — add a drawer route |
| Preset export to `.hsp` | `device to-hsp` / `device pull` / library `.hsp` is the file | **READY** |
| **Whole-setlist one file** | `device setlist export-hss` / `import-hss` → **`.hss`**, full preset copies (EXPERIMENTAL) | **READY (experimental)** — matches the app's own `.hss` exactly |
| Search over **notes / model name** | library search is name/tag-oriented today | **NEW (small)** — widen the index |
| **Templates** as managed assets | none — `chassis.py` is an internal generation shell, not a user template library | **NEW — library-first** |
| **Folders** (preset/template) | none — flat `tones/` dir | **NEW — library-first (shared w/ §A.6 sidecar)** |
| Favorites / Clones / Clips | none | **WON'T-DO / defer — §B.6** |

**Engine readiness verdict for 81v.9: nearly all READY.** The device model
already matches; the two genuinely new disk-side pieces are *templates* and
*folders* (and they share the library-first metadata layer of §A.6). The one
small engine touch is widening library search to notes/model text.

## B.4 The how — drawer extensions

All additive on the shipped drawer (Tones / Setlists / IRs tabs). Proposed tab
set after this work: **Tones / Templates / Setlists / IRs** (Templates is a new
sibling tab; it is the same row machinery as Tones, filtered to template-marked
`.hsp`).

- **Batch color + notes** (READY engine): the Tones tab gains multi-select → a
  "Set color…" action → `device set-info <cids> --color`; a per-row notes field
  (expand) → `--notes`. One route `/library/set_info`. The existing SSE
  `updateContent` delta already refreshes the row.
- **Notes display/edit** (READY): notes come back on the content read the drawer
  already does for drift; show them in the row's expand, edit writes through
  `set-info`.
- **Search widening** (NEW small): extend the library search index to include
  notes text and each tone's amp/effect model display names, matching the app's
  *"name, amp or effect name … and Preset Info text"*. Disk-side; no device I/O.
- **Import `.hsp`/`.hlx`** (READY): a drawer "Import to library" → POST file →
  `ingest`. Lands in the on-disk library (then copy-to-device is the existing
  drawer action). Note the chassis rule: the first-ever ingest sets the library
  chassis (`.hsp` vs `.hlx`) — surface, don't fight.
- **Setlist one-file export/import** (READY experimental): Setlists tab gains
  **Export** (→ `export-hss` → one `.hss` on disk) and **Import** (→ `import-hss`;
  the one *non-idempotent* retry — warn, and don't auto-retry on timeout). This is
  the closest-matching gap: the app's own whole-setlist format *is* `.hss`.
- **Reorder consequence** (READY): the existing reorder UI gets a one-line label —
  *"Reordering renumbers presets and the MIDI Program Change they respond to"* —
  so a drag isn't a silent MIDI remap. The device does the renumber; we only make
  it legible (the manual confirms the behaviour).
- **Templates** (NEW — §B.5).
- **Folders** (NEW — shared library-first layer, §A.6 sidecar generalized to
  preset/template folders).

## B.5 Templates — the library-first decision, and the boundary with 81v.1

A Stadium "template" holds *models, routing, and Command Center mapping* — i.e. a
preset used as a starting point. Two very different operations hide under
"templates," and the split is the whole design:

1. **Template *management*** — store an `.hsp` as a template, name/rename/delete
   it, organize templates into folders, copy one to the device. This is **just
   preset management over a tagged subset of the library** → **library-first, in
   this bead.** Mechanism: a `template: true` marker in tone metadata (or a
   `templates/` sub-area of the library) + the same folder sidecar as §A.6. Zero
   new device protocol — a template copied to the device is an ordinary preset.
2. **"New Preset from template"** — instantiate a *live* edit buffer from a
   template, i.e. load a routing/model layout into the chain. This **reshapes the
   signal chain** and therefore belongs to **`81v.1`** (the signal-flow editor),
   which owns live topology synthesis. It is **out of scope here** and flagged as
   a collision (§C): this bead must not grow a second structural-edit path.

So: **template library management ships here; template *instantiation* ships with
the editor.** Drawing the line here keeps 81v.9 free of the topology-synthesis
dependency that gates 81v.1, and lets template CRUD land now on the shipped copy
path.

## B.6 Won't-do (with reasons) — same discipline as 81v.1 §4/§5

- **Favorites (model favorites).** *Reason: wrong layer + collides with 81v.1.*
  Favorites are **model**-selection favorites (a shortlist in the model browser),
  not preset management — the app even keeps them in a separate `.hls`/`.hsf`/
  `.fav` world. The model browser is designed in **`81v.1 §8.3`**; a favorites
  layer belongs *on that browser*, not in the preset drawer. Building it here
  would fork the model catalog. **Deferred to the editor epic**, to be designed
  with the model browser. (If the owner wants favorites sooner, they attach to
  81v.1, not 81v.9.)
- **Clones / proxy-cloning library.** *Reason: out of mission.* Clones are
  **amp/cab captures** (NAM-style), up to 2,048 in four auto-sorted categories
  (Amp+Cab / Amp / Preamp / Distortion), with a `.clone` file type and a capture
  workflow helixgen has **no** path to produce. helixgen's mission is *authoring
  tones from language*, not managing hardware captures. A clone referenced by a
  preset already round-trips as block metadata (the editor's read-only Clone panel,
  81v.1 §8.4); *managing a clone library* is a distinct product with no overlap
  with tone authoring. **Won't-do** unless the owner specifically wants capture
  management — then it is its own epic, not a drawer tab.
- **Preset clips.** *Reason: out of mission, niche.* A "preset clip" is an audio
  clip the preset plays (a performer/Song-view convenience). It needs clip import/
  storage/playback the engine has nothing for, and serves the *player*, not the
  *author*. **Won't-do** (same bucket as Song View in the parity map's P3
  candidate won't-do).
- **Full Helix/HX *backup* file import.** *Reason: the app itself refuses it* —
  *"It cannot load an entire Helix/HX backup file."* We match the app: individual
  `.hsp`/`.hlx` and `.hss` setlists import; whole-backup blobs don't. Not a gap.

## B.7 Format landscape (so the builder doesn't invent extensions)

Ground truth from the manuals, to wire the right file-pickers:

- **Preset:** `.hsp` (Stadium + Native), `.hlx` (Helix/HX/Native). Both ingest.
- **Setlist (one file):** `.hss` — **helixgen already reads/writes this** via
  `export-hss`/`import-hss`. Full preset copies inside; import appends, collisions
  get `(1)`.
- **Favorites:** `.hls` (Stadium import), `.hsf` (Stadium export for Native),
  `.fav` (Helix). *Only relevant if favorites are ever built — and then on the
  model browser, §B.6.*
- **Clone:** `.clone`. *Won't-do, §B.6.*
- **IR:** `.wav` (any rate/depth in; 48 kHz/mono canonical).
- ⚠️ The librarian manual is **internally inconsistent** about `.hsf` vs `.hss`
  for setlists (it uses `.hsf` in one spot, `.hss` in another). helixgen's own
  `export-hss` is authoritative for *our* format; treat the manual's `.hsf`
  setlist mention as a doc bug, not a second format to support.

---

## C. Collisions with the signal-flow editor epic (`81v.1`) — flagged

1. **Templates — instantiation vs management (§B.5).** *Management* (CRUD/folders/
   copy) is this bead; *"New Preset from template"* (live routing synthesis) is
   81v.1's topology engine. **Boundary drawn at §B.5; do not build template
   instantiation here.** If 81v.1 lands a "load layout into buffer" primitive,
   this drawer's Templates tab can call it — a clean seam, not a conflict.
2. **Favorites — model-browser overlap (§B.6).** Favorites are model favorites;
   the model browser is 81v.1 §8.3. **Deferred to 81v.1.** Building here would
   duplicate the model catalog.
3. **IR usage / Cab-block IR addressing.** 81v.1 §8.4 exposes a Cab block's **two
   IR tabs / dual-cab 2nd slot** in the editor. This bead's `ir_usage` +
   unresolved-on-delete must stay consistent with however 81v.1 addresses the 2nd
   IR tab — they read the *same* on-device IR references. **No conflict today**
   (usage already reads both from the preset body), but the two should share the
   IR-hash-extraction path, not fork it.
4. **No shared *structural* state.** This bead touches only library organization +
   device librarian ops; it never edits a signal chain. The drawer-as-frame and
   the editor coexist in one page/server already (shipped). No concurrency seam
   beyond the one the drawer spec already handles (library client vs editbuffer
   client under separate locks).

**Nothing here blocks or is blocked by 81v.1** except the two deliberately-ceded
features (template instantiation, favorites). Both beads can be built on the
shipped drawer **now**, in parallel with the editor epic.

---

## D. Constraints (inherited)

- **Core-first, cross-repo.** The engine pieces (resample in `ir.py`; the
  library-first folder/template metadata layer in `LibrarySession`; widened
  search; the new drawer routes) land + release in **helixgen-core** (PyPI)
  first; the plugin PR (synced `docs/CLI.md`, engine-pin bump, skills, release)
  follows and cross-references it. Worktrees off freshly-fetched `origin/main`;
  adversarial review before merge.
- **Core repo rules:** TDD (failing test first), stdlib + `click` only (one
  self-contained `page.html`, no JS framework/CDN), per-verb/route `--help` is the
  contract (`tests/test_cli_parity.py`), docs updated in the same change.
- **`HelixClient` not thread-safe.** New device I/O (import/export/set-info/hss)
  runs on the drawer's **existing dedicated library command client** under its own
  lock — no new client, no contention with the editbuffer client. Folders/search/
  templates are disk-only (no device I/O, no lock).
- **Leases unchanged:** this work adds no new lease scope. IR writes take `irs`;
  preset writes take `library`; both already held by the drawer process.

## E. What's left to the builder

- **Resampler choice + hash-match (§A.3)** — the one real spike. Capture a
  non-48 kHz WAV's on-device hash after a Stadium-app import; match helixgen's
  resampler so the same source yields the same hash (or document best-effort +
  the UI caveat if it can't be matched). **Do this before shipping import-any-rate.**
- **Folder metadata mechanism (§A.6)** — sidecar vs subdirs; propose sidecar.
  Design the schema (hash→folder for IRs, `.hsp` path→folder for presets/
  templates), the empty-degrades-to-flat default, and how a `rename-ir`/preset
  rename preserves membership. Shared by §A.6 and §B.5.
- **Template marker** — metadata flag vs `templates/` sub-area; how a template
  differs from a tone in the browse list; whether copy-to-device of a template is
  any different from a preset (it isn't — confirm).
- **Search index widening (§B.4)** — include notes + model display names; confirm
  the drawer's existing search path can read notes without a device sweep (notes
  are a content attr — may need the same content read drift already does).
- **`import-hss` non-idempotency (§B.4)** — surface the warning; never auto-retry
  on timeout (it appends duplicates). Confirm the drawer's error path shows this.
- **Export fan-out (§A.4)** — multi-IR export as N× `pull-ir`; a folder picker in
  a localhost page (propose: server writes to a chosen `$HELIXGEN_HOME`-relative
  dir, since a browser can't pick an arbitrary FS path).
- **Headroom read (§A.4)** — `list-irs` count for `N/2048`; confirm it's the cheap
  listing (no content sweep).
- **Unresolved-on-delete wording (§A.5)** — the exact "delete anyway" consequence
  copy; keep the fail-closed default.
- **Tab layout** — Templates as a 4th tab vs a filter on Tones; where folders
  render in the narrow drawer (the tabs spec already flagged drawer-width layout
  as open).
- **HW validation (non-blocking, per CLAUDE.md):** import a 44.1 kHz WAV and
  confirm it resolves in a Cab block; delete an in-use IR with "delete anyway" and
  confirm the Cab tab shows UNRESOLVED; export/re-import a setlist `.hss` round-trip.
  Ship with tests if HW is busy; note HW owed.

## F. Acceptance

- From the drawer, a user imports a WAV of **any** sample rate into a **folder**,
  sees it resolve in a Cab block, exports it back out, and sees `N/2048` headroom
  — without dropping to the CLI or the Stadium app.
- A user organizes authored presets and **templates** into folders, batch-sets
  color, edits notes, searches by name/model/notes, imports a `.hsp`/`.hlx`, and
  exports/imports a whole setlist as one `.hss` — all in the drawer, with the
  **device staying the truth** for order and MIDI PC.
- Deleting an in-use IR is **safe by default** (guarded) with an explicit,
  consequence-labelled escape hatch matching the app.
- Favorites, clones, and clips are **documented won't-do with reasons**, not
  silently missing; template *instantiation* and favorites are **ceded to 81v.1**
  with the seam named.

## G. Reference

- Drawer this extends: [`2026-11-16-live-library-drawer-design.md`](2026-11-16-live-library-drawer-design.md),
  [`2026-11-18-library-drawer-tabs-and-ir-usage-design.md`](2026-11-18-library-drawer-tabs-and-ir-usage-design.md).
- Sibling epic / collisions: [`2026-11-21-signalflow-editor-parity-design.md`](2026-11-21-signalflow-editor-parity-design.md).
- Parity map: [`docs/parity/stadium-app-parity.md`](../../parity/stadium-app-parity.md)
  (P2 — IR management; P2 — Preset / librarian management).
- Manuals: [librarian-view](https://manuals.line6.com/en/helix-stadium/live/librarian-view),
  [presets](https://manuals.line6.com/en/helix-stadium/live/presets) (v1.4 Rev D).
- Core surfaces: `src/helixgen/ir.py` (canonicalizer — resample gap at `:359`),
  `src/helixgen/device/ir_upload.py`, `src/helixgen/device/sftp.py`,
  `src/helixgen/cli_library.py`, `src/helixgen/liveedit/` (drawer host + `page.html`),
  `src/helixgen/libraryui/session.py` (`LibrarySession`, mounted actions).
- Engine verbs leaned on: `device push-ir`/`pull-ir`/`rename-ir`/`delete-ir`/
  `ir-prune`/`list-irs`, `device set-info`, `device reorder`/`move`,
  `device setlist export-hss`/`import-hss`, `helixgen ingest`.
