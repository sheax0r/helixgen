# helixgen UI → Helix Stadium Edit app parity — backlog

**Goal:** bring the `helixgen device live` browser workspace to **feature parity
with the Line 6 Helix Stadium *Edit application*** (the Mac/Windows desktop
editor), **plus** the library-management surface the Stadium app has no
equivalent of (helixgen owns the authored on-disk `.hsp` + IR library).

This file is the **enumeration + epic map**. It exists because the plugin's
beads DB isn't currently serveable (see *Filing* at the bottom). The
**Signal-flow editor** section below is written to be **design-session-ready**:
it is the "editor bead" the owner asked to make ready first.

Source of truth for the official app: the Line 6 online manual, "live" rev
(app v1.4.0 / firmware v1.4). Page links are inline per area.

---

## Current state — what `helixgen device live` already does

The chain editor (the frame of `device live`) today:

- Renders the **loaded** tone as a signal chain — every block of every DSP path,
  inputs + outputs, **parallel sections as side-by-side lanes** between split and
  merge.
- Every parameter is a **knob / switch / list**; **bypass switch per block**.
- **Every control writes to the device immediately** (live edit buffer, heard at
  once; values sent in RAW range, device-clamped).
- **Save** = the hardware's own Save (overwrites the active tone's pool preset;
  factory presets refused).
- **Follows the device**: a knob/footswitch/snapshot/preset change from the
  hardware, HX Edit, or another helixgen verb shows up without reload.
- **Undo / redo** (Ctrl/Cmd+Z); a knob drag = one undo step; history clears on
  preset/snapshot change.
- **Adjective-search knob highlighting** (green ↑ / pink ↓ / blue by turn
  direction) — a helixgen-only feature, no Stadium-app equivalent.
- **Library drawer**: search the authored tone/IR library, per-tone drift badges
  vs the Stadium, copy a tone to the device, pull an edited preset back, manage
  setlists, push/rename/delete IRs, load any library tone into the editor.
- **Offline cold start**; needs device firmware **1.4+**.

**Explicit non-features today (the parity gap):**

- **No structural editing** — cannot add, remove, or move blocks, or swap a
  block's model.
- **Only each block's primary model** is shown — not a dual-cab's 2nd cab, nor
  harness settings such as Trails.
- No deep per-block editors (amp lens/XY morph, cab mic placement + IR plot,
  graphic EQ drag, comp gain-reduction meter).
- No Matrix Mixer; no snapshot-management UI; no controller/Command-Center
  assignment UI; no global settings / global EQ; no tuner; no Song View.

---

## The hard question the design session must answer first

The Stadium Edit app **edits a preset** — structural changes included — whether
or not a device is even producing sound. `device live` is **device-bound**:
every control is a live OSC write to the edit buffer, and structural editing was
left out partly because **it is unknown whether the Helix live protocol (2001/2002/2003)
supports add/remove/move-block live at all**. helixgen already has a *different*
path for structural edits: offline `.hsp` mutation (`mutate`, patch verbs) +
`device copy`.

So "editor parity" is not just "add more controls." It forces a model decision:

1. **Live-only** — implement structural ops as live protocol writes (if the
   device supports them). Keeps the one "everything is heard immediately" model.
   **Risk: protocol may not support it** → spike required.
2. **Dual-mode** — the same UI edits the on-disk `.hsp` via the engine
   (structural ops, deep editors) and *pushes* the result, while simple param
   tweaks stay live. Reuses the mature offline mutate path; reconciling "live
   edit buffer" vs "editing a file" is the design cost.
3. **Hybrid** — live for params/bypass (as today), offline-`.hsp`-then-reload for
   structure. Simplest to build on what exists; a visible "apply structure"
   step breaks the seamlessness.

**The editor epic below is blocked on this decision.** Everything downstream
(which structural features are even feasible live) depends on it. Design session
should start with a **protocol spike**: can the device add/remove/move a block
live and ack it? That answer picks the model.

---

## EPIC — Signal-flow editor parity  *(the "editor bead": make ready first)*

> **UPDATE 2026-11-24 — the editor UX reframe shipped (engine 0.92.0).** The
> Signal-flow pane is now a compact **glyph-tile canvas + focus panel**: type
> icons + category accents per block, **click a tile to edit it** in a focus
> panel (knobs, lenses, 2nd cab), **within-lane drag-reorder**, a **categorized
> model browser** for Add/Swap, and adjective-search that lights the matching
> **tiles** (↑/↓) and the **knobs** in the focus panel. This closes the UX gap
> this roadmap had enumerated functionally but never addressed. Design:
> `docs/superpowers/specs/2026-11-24-live-editor-canvas-ux-design.md`.
> **Remaining here is Stage 2:** moving a block *across* lanes / building new
> parallel topology by drag (gated on the topology-synthesis engine epic) and
> the deep Focus-View editors. Library/slot sidebar → bead **81v.14**; a
> canvas-UX pass for the IR / Command-Center / Global-EQ panes → bead **81v.15**.

**One-liner:** bring the `device live` chain editor from *read-the-structure,
turn-the-knobs* up to the Stadium Edit app's full **signal-flow editor** —
structural editing, the model browser, parallel routing, dual-amp/dual-cab,
input/output sourcing, and the per-block Focus View deep editors.

**Manual:** [signal-path-routing](https://manuals.line6.com/en/helix-stadium/live/signal-path-routing),
[display](https://manuals.line6.com/en/helix-stadium/live/display),
[the-focus-view](https://manuals.line6.com/en/helix-stadium/live/the-focus-view),
[matrix-mixer](https://manuals.line6.com/en/helix-stadium/live/matrix-mixer).

**Depends on:** the model decision above (protocol spike) — **RESOLVED 2026-11-21**:
unified-live model, design in
`docs/superpowers/specs/2026-11-21-signalflow-editor-parity-design.md`. The editor is
now **engine-first**: it is blocked on a helixgen-core **topology-synthesis** epic
(`docs/superpowers/specs/2026-11-21-topology-synthesis-engine-design.md`, handoff in
`docs/superpowers/plans/2026-11-21-topology-synthesis-core-handoff.md`), built first.

### Parity checklist — what the Stadium editor can do that we can't yet

**Blocks — add / remove / move**
- [ ] Add a block: pick an empty location → choose a model from the model browser.
- [ ] Delete / clear a block.
- [ ] Drag a block left/right to reorder within a path.
- [ ] Move a block to another path (drag onto it).
- [ ] Copy / paste / clear a block (block action panel).
- [ ] "Add to Favorites" from a block (see Favorites, librarian epic).

**Model browser (the picker)**
- [ ] Browse models by category (Input, Amp, Preamp, Cab, Effect, FX Loop,
      Send/Return, Split, Merge, Output, Looper, Clone, Poly).
- [ ] Mono / Stereo / Legacy subcategories; show each model's mono/stereo type.
- [ ] Amp list ordering (Agoura-type first, then HX-type).
- [ ] Swap a block's model in place.

**Parallel routing / structure**
- [ ] Add a Split block; choose **Split type** (types not enumerated in manual —
      needs capture) and **Balance**.
- [ ] Add a Merge/Return block; **Pan A / Pan B**.
- [ ] Drag a block down from the main path → auto-create Split+Merge parallel path.
- [ ] Multiple splits; merge two split paths.
- [ ] Clear Path B (double-tap its Input/Output → Clear).
- [ ] Up to **4 signal flows** (1A/1B/2A/2B); super-serial up to 24/48 locations
      "DSP permitting" (surface DSP headroom if the protocol exposes it).

**Dual-amp / dual-cab**
- [ ] Dual-amp (two amps parallel into shared cab).
- [ ] **Dual-cab: expose and edit the 2nd cab slot** (own model/IR, pan,
      settings) — today only the primary model is shown.

**Inputs / outputs**
- [ ] Input block: select source (Instrument, Mic, Return; Instrument 2 on XL).
- [ ] Output block: Level.
- [ ] Input/Output signal + clip metering (green/red).

**Mono/stereo conversion**
- [ ] Convert a block mono↔stereo in place, keeping settings (manual notes
      controller + snapshot assignments are *not* kept; excludes
      mono-only/stereo-only/Legacy).

**Focus View — per-block deep editors**
- [ ] Amp/Preamp: lens / XY cursor across 5 zones morphing multiple params;
      store up to 8 lens positions as snapshots 1–8; I/O meters; "Based On".
- [ ] Cab: mic position / distance / angle; IR frequency-response plot;
      Amp>Cab Link indicator + toggle.
- [ ] EQ: drag-band graphic/parametric editor (all except Acoustic Sim).
- [ ] Compressor/Gate: real-time gain-reduction meter.
- [ ] Clone: read-only metadata panel (Brand/Product/UUID/Notes/date).

**Harness / preset-level that the editor surfaces**
- [ ] Trails and other harness settings (currently hidden).

### Acceptance criteria (for the epic as a whole)
- A user can build a preset's signal chain from empty to multi-path, multi-block,
  dual-cab, with model selection, entirely in `device live` — no `.hsp` hand-edit,
  no HX Edit.
- Structural edits persist via the existing Save/copy model and round-trip
  cleanly (`device to-hsp` ⇄ library) with no fidelity loss.
- Parity items that the live protocol genuinely cannot do are documented as
  won't-do with the reason, not left silently missing.

### Out of scope for this epic (other epics)
Snapshots UI, controller/footswitch assignment, Command Center, global
settings/EQ, Matrix Mixer, IR import, tuner, Song View, librarian.

---

## Epic map — the other areas (stubs; decompose in their own design sessions)

Priority is a first guess for the owner to re-rank. P1 = closest to the editor's
core loop; P3 = nice-to-have / likely won't-do.

### P1 — Snapshots management
Manual: [snapshots](https://manuals.line6.com/en/helix-stadium/live/snapshots).
Today `device live` *follows* snapshot switches but has no snapshot **editing**
UI. Parity: 8 snapshots/preset; per-snapshot capture of block bypass +
snapshot-controlled params + tempo; enable/disable snapshot control per param
(the "white value" toggle); per-block "Snapshots Set Bypass" exclude; rename +
color; copy/paste a whole snapshot; swap; Discard-Edits mode. helixgen already
has deep snapshot-model knowledge (dense @enabled arrays, value==active
invariant, snapshot-bypass assignment) — this is UI over solved engine ground.

### P1 — Controllers & assignments
Manual: [bypass-and-controller-assign](https://manuals.line6.com/en/helix-stadium/live/bypass-and-controller-assign).
helixgen already edits footswitch/EXP assignments via CLI patch ops (core 0.58).
Parity UI: FS bypass assign (latching/momentary, merge/replace), EXP bypass
(position/wait/toe/heel), MIDI bypass, parameter→controller learn, min/max range
drag (incl. reverse), controller sources (stomp/ext FS/triggers/EXP/MIDI/XY),
stomp label + LED colour, swap stomps, clear controllers/assignments, XY
controller with rubber-band.

### P2 — Command Center
Manual: [command-center](https://manuals.line6.com/en/helix-stadium/live/command-center).
Per-preset command assignments: sources (stomp A/B, EXP, toe, XY, Instant 1–16,
external stomps, triggers), categories (Preset/Snap, Song, Looper, Utility, Ext
Amp, MIDI bank/prog/CC/note/MMC, Hotkey), actions (press/release/hold/toggle),
wait, snapshot-controlled command params, copy/paste/clear, label/colour.
helixgen engine already models MIDI CC / Command Center (plugin 2.26).

### P2 — Global settings / I/O / routing
Manual: [global-settings](https://manuals.line6.com/en/helix-stadium/live/global-settings).
8 categories (Ins/Outs, Switches/Pedals, Displays, Preferences, Songs,
Tempo/Click, MIDI, Date/Time). Many are hardware-global, not per-preset — decide
how much belongs in a preset-centric editor vs a separate "device settings" pane.

### P2 — Global EQ
Manual: global-settings (Global EQ view). Three global EQs (1/4", XLR, Phones),
independent of presets. Pairs naturally with the editor's EQ Focus View.

### P2 — IR management
Manual: [librarian-view](https://manuals.line6.com/en/helix-stadium/live/librarian-view).
helixgen's drawer already does push/rename/delete IRs on the device and owns the
on-disk IR library (more than the Stadium app, which can't touch an external
library). Parity gaps: import WAV (auto-convert 48k/32f/mono), up to 2048 slots,
folders, export, unresolved-on-delete handling, boot-reindex note.

### P2 — Matrix Mixer / outputs
Manual: [matrix-mixer](https://manuals.line6.com/en/helix-stadium/live/matrix-mixer).
Per-output matrix layer (1/4"/XLR/Phones), channels (paths, song tracks, click,
USB, Bluetooth, Aux), level/pan/mute/solo, per-output global EQ, reset. Larger,
newer surface; lower priority unless the owner uses multi-out routing.

**UPDATE 2026-11-23 — the mixer has a READ surface after all** (see
`docs/superpowers/specs/2026-11-23-undocumented-ops-discovery-findings.md`).
The per-strip Level/Pan/Mute/Solo plane is readable over the LAN as the single
structured property **`server.mixer.state`** (per channel `vol_`/`pan_`/`mute`/
`solo`/`src_`/`name`; AUX / Bluetooth / Click / Count / the four Home paths /
layer mixes). The prior "not a device property / won't-do" verdict rested on a
`dsp.matrix*` glob that missed it — the mixer is one `server.*` blob, not
per-strip dotted keys. **Write is still unproven** (candidate:
`/PropertyValueSet server.mixer.state` variant codec), so 81v.8 is re-scoped
from "won't-do" to "read-ready; one HW write-capture gates the write path".

### P2 — Preset / librarian management
Manual: [presets](https://manuals.line6.com/en/helix-stadium/live/presets),
librarian-view. Overlaps the existing library drawer. Parity gaps beyond today:
templates (+folders), favorites (import/export .hls/.hsf), clones/proxy-cloning
library (up to 2048, categories, folders), batch-color, full import/export
(.hsp/.hlx, setlists as one file), reorder-renumbers-MIDI-PC, preset
notes/clip/search. Decide helixgen-library-first vs device-librarian-mirror.

### P3 — Tuner / tap tempo / tempo panel
Manual: [tuner](https://manuals.line6.com/en/helix-stadium/live/tuner).
Needle/strobe tuner, reference pitch, string offsets, tuner in/out; tap tempo,
note-value, tempo panel. Mostly a live read/display surface.

### P3 — Device / utility
Manual: [main-menu](https://manuals.line6.com/en/helix-stadium/live/main-menu).
Connect dialog, firmware updates, remote-access PIN, rename device, licenses,
account. helixgen covers discovery/backup/restore via CLI. Low UI priority.

### P3 — Song View / Showcase  *(candidate won't-do)*
Manual: [song-view](https://manuals.line6.com/en/helix-stadium/live/song-view).
Backing-track / stem-split / playlist feature needing a purchased microSD and a
lot of surface for little overlap with helixgen's tone-authoring mission. Flag
for an explicit won't-do unless the owner wants it.

---

## Design-pass outcomes & implementation sequencing (2026-11-22)

A parallel design pass produced a full spec per area (merged to
`docs/superpowers/specs/2026-11-22-*-design.md`). It **supersedes the "first
guess" priorities above** with grounded engine-readiness, and surfaced two
hidden engine epics + one cross-epic conflict.

### Engine-readiness per area
| Area | Bead | Verdict |
|---|---|---|
| Global settings / I/O | 81v.5 | **Ready** — `device settings` reads/writes live. Pure UI-add. |
| Preset / librarian | 81v.9 | **Nearly ready** — pool/ref model already matches; needs templates + folders (disk metadata). |
| Controllers | 81v.3 | Offline ready; live needs 2 blob captures (light). |
| Snapshots | 81v.2 | Model ready; live ops via whole-buffer push day-one, granular later. |
| IR management | 81v.7 | One gap: WAV resampling; rest UI + disk-side IR folders. |
| Global EQ | 81v.6 | Half — write-only protocol; needs shadow-state + connect-time snapshot. |
| Command Center | 81v.4 | **Ready** — `device to-hsp` already round-trips commands + MIDI-CC (bead hgc-mid, since 0.67.0). Pure UI-add. |
| Matrix Mixer | 81v.8 | **Read-ready, write-gated** (updated 2026-11-23) — `server.mixer.state` reads the whole mix over the LAN; only the *write* path needs a HW capture (was mis-scoped "not engine-ready / no surface"). |

### One real engine epic hides inside "the UI" (helixgen-core, critical path)
1. **Matrix Mixer protocol-RE** — **partially solved 2026-11-23**: the mixer is
   **readable** as `server.mixer.state` (one structured property; no new opcode,
   no capture needed for reads). Only the **write** path still needs a HW capture
   + `device/client.py` method. Gates 81v.8's write half; serialized behind
   81v.1's `client.py` work and its exclusive HW use. See
   `docs/superpowers/specs/2026-11-23-undocumented-ops-discovery-findings.md`.

**Correction (2026-11-22):** an earlier reading of the Command Center spec
flagged an "untranscode reverse decoder" epic (claiming `device to-hsp` drops
commands + MIDI-CC bindings). That was a **false alarm** — verification found the
reverse decode already shipped on `main` under bead **hgc-mid** (since 0.67.0;
`_recover_commands`/`_recover_midi`, round-trip tests included). So 81v.4 is a
pure UI-add and 81v.3's round-trip concern is likewise moot. No reverse-decoder
epic is needed.

### Cross-epic conflict to reconcile
🔴 The 81v.1 spec (§8.4) stores amp-lens positions **as snapshots 1–8**, which
would commandeer the user's 8 scene slots — incompatible with 81v.2. Reconcile
before either ships (likely an 81v.1 mis-map: lens zones ≠ scenes).

### Serialization rule
The editor UI is one shared surface (`src/helixgen/liveedit/`, esp.
`page.html` + `server.py`) and every panel rides 81v.1's whole-buffer-SET
keystone. So **engine epics parallelize** (separate `device/` + new modules) but
**UI panels serialize** one-at-a-time through `liveedit/`, built on 81v.1's
foundation (shared reverse-transcode, source bar, snapshot-bypass built once,
not forked). Shipping order: engine long-poles → 81v.1 keystone → ready panels
(81v.5, 81v.9, 81v.3-offline) → capture-gated panels → Matrix Mixer.

---

## Explicitly out of scope (hardware-only, no app surface)
Physical footswitches/scribble strips, on-device Maintenance (microSD
backup/restore — the app itself doesn't do it either), capacitive-touch behavior.

---

## Manual gaps to capture during design (not assume absent)
- Split **types** are selectable but the manual doesn't enumerate them — capture
  from the device/protocol.
- DSP limits are "resources permitting" — no numeric block/DSP figures published.
- LFO/envelope controller types not mentioned (sources are FS/EXP/XY/MIDI/trigger).
- Native-plugin edit-panel manual page 404'd — re-pull for full parity detail if
  plugin parity matters.

## Source manuals
[Edit application](https://manuals.line6.com/en/helix-stadium/live/helix-stadium-edit-application) ·
[Signal path](https://manuals.line6.com/en/helix-stadium/live/signal-path-routing) ·
[Snapshots](https://manuals.line6.com/en/helix-stadium/live/snapshots) ·
[Presets](https://manuals.line6.com/en/helix-stadium/live/presets) ·
[Display](https://manuals.line6.com/en/helix-stadium/live/display) ·
[Focus View](https://manuals.line6.com/en/helix-stadium/live/the-focus-view) ·
[Matrix Mixer](https://manuals.line6.com/en/helix-stadium/live/matrix-mixer) ·
[Bypass/Controller](https://manuals.line6.com/en/helix-stadium/live/bypass-and-controller-assign) ·
[Command Center](https://manuals.line6.com/en/helix-stadium/live/command-center) ·
[Global Settings](https://manuals.line6.com/en/helix-stadium/live/global-settings) ·
[Librarian](https://manuals.line6.com/en/helix-stadium/live/librarian-view) ·
[Main menu](https://manuals.line6.com/en/helix-stadium/live/main-menu) ·
[Tuner](https://manuals.line6.com/en/helix-stadium/live/tuner) ·
[Song view](https://manuals.line6.com/en/helix-stadium/live/song-view)
