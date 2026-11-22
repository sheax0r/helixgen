# Device-global surface — Global Settings, Global EQ, Matrix Mixer (`helixgen-81v.5 / .6 / .8`) — design

**Status:** design — awaiting approval.
**Date:** 2026-11-22.
**Covers three beads, one surface:** they share the device's I/O / output plane and
all live *outside* the preset, so they are designed together as one **Device pane**:
- **81v.5 — Global Settings / I/O / routing** ([global-settings](https://manuals.line6.com/en/helix-stadium/live/global-settings))
- **81v.6 — Global EQ** (three per-output EQs; [global-eq](https://manuals.line6.com/en/helix-stadium/live/global-eq))
- **81v.8 — Matrix Mixer / outputs** ([matrix-mixer](https://manuals.line6.com/en/helix-stadium/live/matrix-mixer))

**Model this spec matches:** `2026-11-21-signalflow-editor-parity-design.md` (the
signal-flow editor, 81v.1) — same depth, the same engine-readiness honesty, the
same "won't-do with the reason" discipline. **Read §Collisions last** — this
surface borders 81v.1 at the input block, the output block, and the EQ widget.

**One-line decision (expanded in §2):** Global Settings, Global EQ, and the Matrix
Mixer are **hardware-global, not per-preset**. They do **not** belong in the
preset-centric signal-flow editor; they get a **sibling "Device" pane** in the
same one `device live` web app — same unified-live write model, separate scope
that does **not** reload on preset change.

---

## 1. Intent / why

`device live` today edits **one preset's** chain, live. It has **no surface at all**
for the device's own globals: you cannot see or change input/output levels,
footswitch behaviour, the three Global EQs, or the Matrix Mixer from the editor —
those are CLI-only (`device settings`, `device globaleq`) or Stadium-app-only
(Matrix Mixer). A user tuning a rig for a room — setting XLR out to Line, lifting
a ground loop, dialling a Phones Global EQ for IEMs, building a monitor mix —
drops to the Stadium app or a terminal.

This surface closes that gap: **browse and set every device global, the three
Global EQs, and (engine permitting) the Matrix Mixer from `device live`**, live,
with the Stadium app closed — while keeping them visibly *global*, never
masquerading as part of the preset you happen to have loaded.

The target is parity with the Stadium Edit app's **Global Settings menu**, its
**Global EQ view**, and its **Matrix Mixer** (app v1.4 / fw 1.4).

---

## 2. The key decision — per-preset vs global: RESOLVED

The brief flags it: "much of Global Settings is hardware-global, not per-preset."
That is true of **all three** beads, and the manuals confirm it:

- Global Settings: *"additional parameters that apply to all presets and songs"*
  (global-settings intro).
- Global EQ: three EQs *"for the 1/4", XLR, and Phones outputs"*, set per physical
  output, independent of any preset (global-eq).
- Matrix Mixer: organised around the **physical outputs** (1/4"/XLR/Phones), and it
  mixes **non-preset sources** — song tracks, click, USB, Bluetooth, Aux — that no
  preset owns (matrix-mixer).

### Decision: a separate **Device pane**, not a preset tab

All three live in a **sibling top-level pane** of the one `device live` web app
(call it **Device** / **Globals**), a peer of the preset signal-flow editor — **not**
a section inside it. Rationale:

1. **Persistence truth.** These settings are stored **device-wide**. Putting them in
   the per-preset editor implies they save with the preset and round-trip through
   `.hsp` (they don't). That would be a lie to the user and would corrupt the
   `device to-hsp` mental model. (Anti-goal §5.)
2. **Lifecycle.** The preset editor **reloads on every preset/snapshot change**
   (it follows the device). Globals must **survive** that — a Phones Global EQ or an
   XLR-out-level change is not undone by loading the next preset. A separate pane
   has its own lifecycle: it does not reload when the active preset changes.
3. **The app agrees.** The Stadium app reaches these through the **Global Settings
   menu**, the **Global EQ view**, and the **Matrix Mixer** (output buttons) — all
   *outside* the per-preset signal-path editor. Parity means matching that
   separation, not collapsing it.

### Still one app, one write model (unified-live)

The Device pane is **not** a second application or a modal. It is a sibling view in
the same bridge-served web app, with the **same unified-live discipline** as the
editor: every control is an immediate live write to the device, heard/applied at
once, no "apply" button. What differs is only the **write channel and the scope**
(device properties, not the edit buffer), and that the pane **does not follow
preset changes**. This keeps the project's "one editor, everything live" model
intact (`CLAUDE.md`: unified-live) while telling the truth about scope.

### The per-preset-linked exceptions (surfaced as global governors)

A few Global Settings **govern** per-preset behaviour without being per-preset
themselves. They stay in the Device pane, shown as the global toggles they are,
with a one-line note pointing at where the per-preset value lives (the editor's
input block — see §Collisions):

| Setting (key) | What it governs | Per-preset value lives in |
|---|---|---|
| `global.offset.input.inst*.pad` + Inst Pad mode (*No Offset / Off-Inst / On-Line*) | whether the pad is per-preset or forced global | Input block (81v.1) |
| `global.exp.pedal.position` (*Per Preset / Global*) | whether EXP pedal position recalls per preset | controller state |
| `global.tempo.select` (snapshot / preset / global) | where system tempo is stored | tempo panel (P3) |

These are **governors**, not duplicates. The pane never writes a per-preset value;
it writes the global rule, and the editor writes the per-preset one.

---

## 3. Engine readiness — stated per bead (the honest part)

Grounded in the **helixgen-core** checkout (read-only, head `95f9197`; installed
CLI `0.85.0`, pin `0.86.0`). What exists vs what is new engine work:

| Bead | Engine today | Verdict |
|---|---|---|
| **81v.5 Global Settings** | `device settings list/get/set` **shipped** — full property codec (`settings.py`), curated 9-page catalog (`_settings_pages.json`: ins-outs, switches-pedals, displays, preferences, songs, tempo-click, midi, date-time, tuner), **live read + write** over 2002 (`/PropertyValueGet`, `/PropertyValueSet`), `DANGEROUS_KEYS` guard. | **Engine-ready — pure UI-add.** The pane is a web front end over verbs that already read and write live. |
| **81v.6 Global EQ** | `device globaleq list/set` **shipped** — byte-exact write codec (`globaleq.py`), 3 outputs × 7 bands + level, HW-validated. **BUT write-only**: `dsp.globaleq.*` keys **do not answer `/PropertyValueGet`** (device returns an empty blob). Per-output **enable** *is* readable (it is a plain `global.eq.{qtr,xlr,phones}.enable` + `global.eq.sync` property). | **Half-ready.** Write path done; **no network read-back of band values** is the live constraint (see §5, §7). Engine ask: a connect-time `globals.eq` snapshot read. |
| **81v.8 Matrix Mixer** | **Nothing.** No module; the per-channel level/pan/mute/solo matrix is **not** in the property defs (`_defs_data.json`: zero `matrix` audio props). Adjacent bits *are* properties — `global.out.level.{qtr,xlr,spdif}`, USB/SPDIF routing (`global.out.usb.12`, `global.out.spdif`, with options *Direct Out / Matrix 1/4" / Matrix XLR / Matrix Phones*), and the MIDI matrix channels (`global.midi.matrix.ch.*`). The **mixer itself** is unmodeled. | **Not engine-ready — the long pole.** Needs protocol RE + a new engine codec in helixgen-core (parallel to `globaleq.py`). Lower priority (parity doc: "Larger, newer surface… lower priority unless the owner uses multi-out routing"). |

**Ordering follows readiness.** 81v.5 ships first (UI over ready verbs); 81v.6
ships its write UI next with the read-back caveat handled; 81v.8 is **gated on a
helixgen-core Matrix-Mixer protocol epic** and its UI lands after — same
engine-first shape as 81v.1's topology-synthesis dependency.

---

## 4. Non-goals (other epics / other beads)
Signal-flow editing, the model browser, per-block Focus View incl. the **per-block
EQ** (all 81v.1 — the per-block EQ is *not* the Global EQ, see §Collisions); snapshots
UI (P1); controllers / Command Center (P2); IR management (P2); preset / librarian
management (P2); tuner / tap-tempo panels (P3); Song View (P3 candidate won't-do);
firmware / device-utility dialogs (P3).

## 5. Anti-goals (a failure even if it technically works)
- **Globals that look per-preset.** Any affordance that implies a Global Setting /
  Global EQ / Matrix value saves with the preset or rides `.hsp`.
- **A pane that reloads on preset change.** Globals must not blink or reset when the
  active preset changes under the live-follow.
- **A write-only EQ that lies about current state.** Showing fabricated band
  positions the device never confirmed (the read-back gap, §3) as if they were read
  truth. Better an explicit "shadow / unconfirmed" state than a confident lie.
- **A visible "apply" step** on any control that *can* be live (same as 81v.1).
- **A bricked channel.** A UI that lets a user flip `global.wifi.enable` /
  `global.remote.access` (the `DANGEROUS_KEYS`) and sever its own transport.

## 6. Constraints
- Device-bound, firmware **1.4+**, same as `device live`.
- **Skills drive the CLI, not source** — the pane's behaviour is the behaviour of
  `device settings` / `device globaleq` (and a future `device matrix`); contracts
  live in each verb's `--help`, pinned by core's `test_cli_parity.py` + synced docs.
- The `DANGEROUS_KEYS` guard is **engine-side and authoritative**; the UI mirrors it
  (renders those keys read-only with "change on the device") but does not rely on UI
  discipline alone.
- **Agent-surface sync:** any new engine surface (Global EQ read-back, the Matrix
  codec) lands in **helixgen-core** first (engine + `docs/helix-protocol.md`), with
  a companion plugin PR updating `skills/*` + synced `docs/` — two PRs, cross-linked.

## 7. The how — per bead

### 7.1 Global Settings (81v.5) — pure UI over ready verbs

**Layout.** One **Device → Global Settings** view, tabbed by the catalog's pages —
in the manual's order: **Ins/Outs, Switches/Pedals, Displays, Preferences, Songs,
Tempo/Click, MIDI, Date/Time** (plus the engine's extra **Tuner** page; Wireless
folded in or omitted). Each page renders its keys as the right control from the
**device-supplied definition** (`get_property_def`): enum → dropdown, int/float with
`vmin/vmax` → slider/number, bool → toggle. Labels, ranges, and enum option text
come from the **device**, not hard-coded — so a firmware that adds an option Just
Works.

**Read.** On opening the pane (and on a manual refresh), `get_property` each visible
key for its live value — the pane reflects the device's truth. This is the
**device-follow** for globals: it is a **read on demand**, not a push subscription
(global settings do not broadcast on 2001 the way edit-buffer changes do), so a
change made on the device's own screen shows up on refresh / re-open, not instantly.
*(Builder spike: confirm whether any `global.*` change echoes on 2001; if some do,
live-follow those. Otherwise refresh-on-focus is the documented behaviour.)*

**Write.** A control change → `set_property(key, typ, value)` live. Values validated
client-side against the def (`coerce_value`) before the write, so the device sees
only in-range values.

**Guard.** `DANGEROUS_KEYS` (`global.wifi.enable`, `global.remote.access`) render
**read-only** with an inline "change this on the device's screen — doing it here can
lock out this connection." (Mirrors `guard_key`.)

**Per-preset governors** (§2 table) get a small "per preset" tag + link to the input
block / tempo panel.

### 7.2 Global EQ (81v.6) — write-live, shadow-read

**Layout.** A **Device → Global EQ** view, an **output switcher** (1/4" / XLR /
Phones; the manual's per-output independence, *"independent per output, regardless
of whether any outputs are linked"*). Per output: a **drag-node EQ graph** (gain =
vertical, frequency = horizontal — the app's exact gesture), the 7 bands
(lowcut/lowshelf/low/mid/high/highshelf/highcut) with their valid params from the
codec (`BANDS`), a per-band enable, and an output **Level**.

**Enable / bypass.** Per-output enable is a **readable** property
(`global.eq.{qtr,xlr,phones}.enable`) — read it live, toggle it live. This is the
one part of Global EQ with true read-back.

**Band writes.** A drag / knob → `set_globaleq(output, band, param, value)` live
(the variant blob). Immediate, heard at once.

**The read-back gap — decided.** Band **values** cannot be read from the device
(§3). So:
- **State source:** seed the graph from the device's **connect-time `globals.eq`
  snapshot** *if* the engine can expose it (the band defaults + current values the
  app itself uses — the codec already knows the factory `DEFAULT_FREQ`). **This is
  the one engine ask for 81v.6:** a `device globaleq get`/snapshot that reads the
  bulk `globals.eq` blob at connect, not per key. Until it exists:
- **Fallback (ship-now):** the graph opens from **factory defaults + a UI-local
  shadow** of every write this session made, each node tagged **"set"** (we wrote it)
  vs **"default/unconfirmed"** (we have not read it). Honest, not fabricated
  (anti-goal §5). A change made on the device's own screen is **not** reflected
  until the snapshot read lands — documented as a known limitation.
- **Copy / Paste / Reset EQ** (app features): Copy = read the shadow for output A,
  Paste = replay the writes to output B; Reset = write each band to default **but
  keep Low Cut / High Cut active** (the manual's exact Reset semantics). All
  expressible on the existing write verb; no new engine surface.

### 7.3 Matrix Mixer (81v.8) — gated on an engine epic

**What it is (manual).** A per-physical-output **monitor/cue mixer**: each of 1/4",
XLR, Phones has its **own Matrix layer**. Channels, in order:

| Channel | Notes |
|---|---|
| **Home** | sum of the 4 Home/Edit stereo paths; expands to **1A / 1B / 2A / 2B** |
| **Song** | sum of the 8 song tracks; expands to **Song Track 1–8** (names saved with the song) |
| **Click** | metronome click |
| **Count In** | **reserved for future firmware** → nothing to control (won't-do, §8) |
| **USB In 1/2** | DAW monitor return |
| **Bluetooth** | greyed unless a BT device is paired |
| **Aux** | rear Aux L/R; greyed unless `Return Type = Aux` (ties to `global.return.type.*`) |

Per channel: **Level** fader (press-to-reset = 0.0 dB), **pre-fader meter**, **Pan**
(reset = Center), **Mute**, **Solo** (multi-select bus; tap-hold clears all). Plus
**Main Volume** per output pair, output **linking**, a per-output **Global EQ
shortcut** (→ 7.2), and **Matrix Reset** (tap-hold the title → Level 0.0 / Pan
Center / Mute+Solo off, optional "reset output volume").

**Engine reality.** None of this is modeled (§3). So the honest plan:

1. **helixgen-core Matrix epic first** (this spec's long-pole dependency, its own
   design/RE session like 81v.1's topology engine): capture the app's Matrix writes
   over 2002, decode the per-(output×channel) level/pan/mute/solo property or RPC,
   build a `matrix.py` codec + `device matrix` verb (`list` / `get` / `set` / `reset`)
   parallel to `globaleq.py`. Resolve read-back the same way EQ does (snapshot vs
   write-only). Capture whether linking/solo are device state or per-layer.
2. **Then the UI**: the per-output layer, the channel strips, faders/pan/mute/solo,
   pre-fader meters from the **2003 telemetry** (`meters.py` already decodes the
   grid-level arrays — the meter source is ready even though the mixer controls are
   not), the Global EQ shortcut, and Reset. Unified-live writes, same pane.

Until the engine epic lands, the Matrix tab is **"requires engine support — not yet
available"** (or omitted), not a fake surface. **Flag for the owner:** confirm the
Matrix Mixer is worth the RE cost before starting the engine epic (parity doc marks
it lowest priority of the three).

**Persistence (decided):** treat the Matrix Mixer as **device-global** — the manual
never says it saves with a preset, it is organised around physical outputs, and it
mixes non-preset sources. The engine epic must **confirm** this against a capture
(does switching presets change the mixer? does it survive reboot?) before the UI
commits to the global model. Documented assumption, to be verified, not guessed-final.

## 8. Won't-do (with the reason — never silently missing)
- **Global EQ live band read-back / on-device-change follow** — protocol is
  write-only for `dsp.globaleq.*` (§3). Won't-do until a connect-time snapshot read
  lands in core; shadow-state in the meantime (§7.2).
- **Matrix Mixer edit** — no engine surface; gated on the core Matrix epic (§7.3).
  Shipped as "needs engine support," not faked.
- **Count In channel** — reserved for future firmware; nothing to control.
- **`global.wifi.enable` / `global.remote.access` toggles** — would sever the control
  channel; read-only with "change on device" (`DANGEROUS_KEYS`).
- **Allow Geolocation / Date-Time clock entry** — low tone-authoring value + a
  privacy toggle; surface read-only (and the WiFi-sync toggle), no full clock editor
  unless the owner asks.
- **Capacitive Touch, scribble-strip brightness, physical FS/combo mode config** —
  these are settable properties but only affect the **hardware's own** controls; the
  pane exposes them (they're in the catalog) with a "takes effect on the device"
  note, and does not pretend they change anything on the `device live` screen.
- **Song-related settings + Matrix Song channels** — only meaningful with Song View,
  itself a P3 won't-do candidate; surfaced read-through but not a feature focus.
- **Re-amp Src / S/PDIF sample-rate** niche routing — exposed as plain settings
  (they're properties) with no special UI; no custom routing diagram.

## 9. Collisions with the signal-flow editor epic (81v.1) — READ THIS
This surface touches 81v.1 at three seams. None is a blocker; all need a shared
contract so the two epics don't double-own a control.

1. **Input block (pad / trim / impedance / source).** 81v.1 owns the **per-preset**
   Input block. Global Settings owns the **global** Inst-Pad mode (*No Offset /
   Off-Inst / On-Line*) + input offset properties (`global.offset.input.inst*`). The
   per-preset pad lives in the editor; the global rule lives here. **Contract:** the
   editor's Input block shows the *effective* pad and links to this pane's Inst-Pad
   governor; this pane never writes the per-preset value.
2. **Output block vs Matrix Mixer — the sharp one.** 81v.1's output block edits the
   **per-preset** output gain/pan (the `P35_OutputMatrix` endpoint, model 783, in
   `transcode.py`) — the signal *leaving the chain*. The **Matrix Mixer** (81v.8) is a
   **different, device-global** per-output mix of *all* sources into each physical
   out. Same word "output," two unrelated surfaces. **They must not be conflated in
   UI or in the user's head** — label them distinctly (preset "Output block" vs
   device "Matrix Mixer"), and do not cross-wire their writes.
3. **EQ widget — shared component, different write path.** 81v.1.1's per-block **EQ
   Focus View** and this spec's **Global EQ** are both drag-node EQ graphs. **Reuse
   the same graph widget** (gain-vertical / freq-horizontal, band nodes) — but the
   per-block EQ writes `/setParamValue` (edit buffer, snapshot-aware) and the Global
   EQ writes `/PropertyValueSet` variant blobs (device property, no snapshots).
   **Contract:** factor the graph as a presentational component that takes a
   value-source + a write-callback; the two epics supply different ones. Also avoid
   the naming collision — "EQ" must read as per-block vs global everywhere.
4. **Global EQ enable** is a Global Setting (`global.eq.*.enable`) on the Ins/Outs
   page **and** the Global EQ view's bypass. **Own it once** (the Global EQ view is
   authoritative), cross-reference from Ins/Outs — don't ship two toggles for one bit.

## 10. What's left to the builder
- **81v.5:** confirm whether any `global.*` change echoes on 2001 (live-follow if so;
  else refresh-on-focus). Decide the Wireless page's fate. Pin the catalog page
  order to the manual.
- **81v.6:** the **connect-time `globals.eq` snapshot read** in core (the single
  engine ask) — scope it, or commit to the shadow-state fallback and document it.
  Confirm Copy/Paste/Reset semantics against the device.
- **81v.8:** the **core Matrix-Mixer RE + codec epic** (own design session) — capture
  the per-(output×channel) writes, decode level/pan/mute/solo + linking/solo scope,
  confirm global-vs-preset persistence by capture, build `device matrix`. Then map
  the 2003 meters (`meters.py`) to the right channel strips. **Owner gate:** is the
  Matrix worth the RE cost (lowest-priority of the three)?
- **All three:** the Device pane's place in the one web app (sibling tab vs drawer),
  and the rule that it does **not** reload on preset change.

## 11. Acceptance
- A user opens **Device** in `device live` and sets any Global Setting (input/output
  levels, footswitch behaviour, displays, MIDI, …) live, with the Stadium app closed;
  values and ranges come from the device, dangerous keys are read-only.
- A user dials each of the three **Global EQs** live per output, with current state
  shown honestly (read where the protocol allows, clearly-labelled shadow where it
  does not).
- The **Matrix Mixer** is either live (once the core epic lands) or shown as
  explicitly engine-gated — never a faked surface.
- Nothing in the pane implies these globals save with the preset; the pane survives
  preset changes; and it never collides with the editor's input/output blocks or EQ.
- Every parity item the protocol genuinely cannot do is documented won't-do with its
  reason (§8).
