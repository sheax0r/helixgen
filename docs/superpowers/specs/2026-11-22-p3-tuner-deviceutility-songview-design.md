# P3 tail — Tuner/tempo, Device/utility, Song View (`helixgen-81v.10/11/12`) — triage + design

**Status:** design / triage — awaiting owner ratification.
**Date:** 2026-11-22.
**Scope:** the three lowest-priority (P3) items of the `device live` editor-parity
epic (`helixgen-81v`). This is a **triage** doc: two small surfaces to build, one
won't-do to ratify. It is deliberately lighter than the P1/P2 specs — P3 is
nice-to-have, and the job here is to not over-invest.

**Verdict up front:**

| Item | Verdict | One-line reason |
|---|---|---|
| **81v.10 Tuner / tempo** | **BUILD** (small) | Engine already ships it — live pitch decoder + global settings. Pure UI over solved ground. |
| **81v.11 Device / utility** | **BUILD a thin strip, won't-do the rest** | `device info`/`discover` is the whole useful surface. Firmware/account/PIN/licenses are OS-level, unsafe, out of mission. |
| **81v.12 Song View / Showcase** | **WON'T-DO** (ratify) | microSD-gated device feature, device-level, zero overlap with tone authoring. 256-song library + playback engine for no tone-authoring gain. |

The common thread: **none of the three is a preset-editing surface.** They are
device/global state. That is why they are P3, and it shapes every decision below —
they live in a small **device/global strip** of `device live`, not in the signal
chain.

---

## 1. Intent / why

`device live` (the 81v epic — the browser editor, not yet in core) is a
**preset-centric** editor: its job is building and shaping a preset's signal
chain. The three P3 items are the things in the Stadium *Edit* app that are **not**
about a preset:

- a **tuner + tempo** readout (live device state, global settings),
- a **device/utility** menu (connect, firmware, account, rename, licenses),
- **Song View** (a backing-track/playback engine).

The question for each is not "can we clone the app screen" but "does a
preset-authoring tool earn its keep by showing this?" For the tuner, yes — cheaply,
and it is genuinely useful while dialing a tone. For device/utility, only the thin
identity/connect part. For Song View, no.

---

## 2. Engine-readiness (grounded in helixgen-core, read-only)

Checked `helixgen-core` @ `95f9197`. There is **no `device live` browser editor in
core yet** — it is the 81v.1 epic being built now; these P3 surfaces are designed to
live in that same editor once it exists. What *does* ship today:

### 81v.10 Tuner / tempo — **SHIPPED engine ground**
- **Live pitch:** `src/helixgen/device/tuner.py` decodes the Stadium's **always-on**
  pitch detector off the **2003 `/dspEvent`** stream (`eid_=10, mid_=796`, a
  fractional-MIDI-note float; `-1.0` = no signal). Hardware-verified. `helixgen
  device tuner` already renders a live needle in the terminal — **no Stadium app, no
  engaging the hardware tuner screen.** This is the hard part and it is done.
- **Tuner settings:** every tuner control is an existing global-settings key,
  readable/writable via `device settings get/set` (`device/_settings_pages.json`,
  page `tuner`):
  `global.tuner.type` (Needle/Strobe), `global.tuner.reference.pitch` (425–455),
  `global.tuner.offsets` + `global.tuner.offset.string.1..6`, `global.tuner.input`,
  `global.tuner.output`, `global.tuner.trails`, `global.tuner.indicator` (flat/sharp),
  `global.tuner.needle.sensitivity`.
- **Tempo:** existing global keys (page `tempo-click`): `global.tempo.bpm`,
  `global.bpm.whole` / `global.bpm.hundredths`, `global.tempo.select` (snapshot/
  preset/global scope), `global.tempo.follow`, `global.midi.clock.receive/send/synced`,
  `global.click*`, `global.sound.click`, `global.tap.tempo.pitch`.
- **Gap (pin-first, degrades gracefully):** sending a **tap gesture** on the wire to
  let the device derive BPM from taps. Not confirmed as an opcode. **Not needed** —
  the browser computes BPM from tap intervals client-side and writes
  `global.tempo.bpm`. If a tap opcode is later captured, swap it in. No blocker.

### 81v.11 Device / utility — **PARTIAL; the useful part ships**
- **Connect / identity:** `device discover` (mDNS discovery) + `device info`
  (`/ProductInfoGet`: model, device_id, serial, firmware + build + date, SD storage
  free/total). That **is** the "connect dialog" and the useful half of the main
  menu, already in the editor's own connect handshake.
- **Backup/restore:** covered by CLI (`maintenance.py`, backup/pull verbs) — already
  its own surface; not duplicated here.
- **No engine support, and correctly so:** firmware download/install, Line 6 account
  login, remote-access PIN, licenses. None is modeled; firmware flashing is
  destructive and OS-level. Rename-device is not exposed either (no device-name
  property in `bridge.py`/`client.py`).

### 81v.12 Song View — **NO engine ground, by design**
- Nothing in core touches songs, backing tracks, stems, or the microSD song library.
  `device info` reads SD *bytes* for storage display only. Building Song View means
  an entirely new protocol surface (song library CRUD up to 256 songs, 8-track audio
  transfer, stem-split, flags/markers, playback transport) — **all net-new RE and
  engine work**, for a feature orthogonal to tone authoring.

---

## 3. 81v.10 Tuner / tempo — **BUILD** (design)

A compact **Tuner/Tempo panel** in `device live`, opened from a persistent
tuner/tempo button in the editor chrome (the app enters the tuner by holding FS12;
here it is a panel toggle). It is **device/global**, not per-preset — it shows and
edits device state, independent of which preset is loaded.

### 3.1 Tuner (live read + settings)
- **Live needle/strobe** driven by the 2003 pitch stream (reuse `tuner.py`'s decoder
  verbatim — it already yields note + cents + Hz). Needle mode: ±50-cent meter, green
  at center. Strobe mode: motion stops in tune. Cents readout top-left. This is a
  **follow-only** display — subscribe, render, done.
- **Settings row** (write-through to `device settings set`):
  Needle/Strobe (`global.tuner.type`), Reference Pitch 425–455 with the app's
  non-440-turns-red cue (`global.tuner.reference.pitch`), String Offsets on/off +
  6 string offsets (`global.tuner.offsets`, `...offset.string.1..6`), Tuner Input /
  Output / Trails / flat-sharp indicator.
- **Mute behavior:** the real tuner can mute/route output (`global.tuner.output`).
  The panel **reads and exposes** that setting but does not force-mute on open —
  helixgen never silences the rig as a side effect of opening a readout.

### 3.2 Tempo (read + set)
- **BPM field** (whole + hundredths, 20.00–300 range per the manual) writing
  `global.tempo.bpm`.
- **Tap button** — the browser times taps and writes the derived BPM (see §2
  gap; tap-on-wire is not required). Taps < 40 BPM ignored (match the hardware).
- **Tempo scope** selector (`global.tempo.select`: per-snapshot / per-preset /
  global) and **Follow Song Tempo** (`global.tempo.follow`) exposed as-is.
- **MIDI clock** receive/send/synced indicators (`global.midi.clock.*`),
  read-mostly.
- **Out of scope (defer to Global Settings / Tempo-Click, a P2 surface):** the Click
  metronome sound config, count-in (manual says not yet functional), send-clock
  output enumeration. The tempo panel surfaces BPM + scope + follow; the full
  Tempo/Click page belongs to the Global Settings epic, not here. Don't rebuild it.

### 3.3 Live-write / follow mapping
| Control | Direction | Transport |
|---|---|---|
| Needle/strobe reading | follow | 2003 `/dspEvent` (shipped decoder) |
| Tuner settings (type/ref/offsets/in/out/trails/indicator) | write-through | `device settings set global.tuner.*` |
| BPM | write-through | `device settings set global.tempo.bpm` |
| Tap | write-through | compute BPM in browser → set `global.tempo.bpm` |
| Tempo scope / follow / MIDI clock | read + write-through | `global.tempo.*`, `global.midi.clock.*` |

No new protocol opcodes required (tap excepted, which degrades to client-side
compute). Settings reflect back via the normal settings-read path, so the panel
stays truthful if the hardware or another client changes a value.

### 3.4 Acceptance (81v.10)
- Opening the panel shows a live needle/strobe that tracks a played note with no
  Stadium app and without engaging the hardware tuner screen.
- Changing Reference Pitch, tuner type, or a string offset in the panel is reflected
  on the device and persists (read back equal).
- Setting BPM (typed or tapped) changes the device tempo; tempo scope and follow are
  shown and settable.
- The panel never mutes or alters the signal chain as a side effect of opening.

---

## 4. 81v.11 Device / utility — **BUILD a thin strip; won't-do the rest**

The Stadium main-menu is a grab-bag. Triaged by what belongs in a preset editor:

### 4.1 BUILD — device identity / connect strip
A small, mostly read-only **device strip** (header or a "Device" popover in
`device live`):
- **Connect / pick device:** the editor already needs to choose an IP; surface
  `device discover` results (model + name + IP) as the connect affordance. This is
  the only genuinely interactive device/utility need, and it is already the editor's
  own connect handshake.
- **Identity readout** from `device info` (`/ProductInfoGet`): model, serial,
  firmware version + build + date, SD storage free/total. Read-only.
- **Backup** is already a CLI surface (`maintenance.py` / backup verbs); link to it,
  don't rebuild. Restore stays ask-first / CLI-only (destructive to owner content).

### 4.2 WON'T-DO — the OS/account half of the main menu
With reasons, so they are documented-missing, not silently absent:
- **Firmware download/install** — destructive, OS-level flashing; a bricking risk
  helixgen must not own. Belongs to the official app / device. **Won't-do.**
- **Line 6 account login** — third-party auth for update notifications; no tone-
  authoring value, and credential handling helixgen shouldn't take on. **Won't-do.**
- **Remote-access PIN** — pairing/security for the official app's remote access; not
  helixgen's channel (helixgen talks the LAN protocol directly). **Won't-do.**
- **Licenses** — static legal text. **Won't-do** (zero value in the editor).
- **Rename device** — not exposed by the engine (no device-name property). **Deferred,
  not won't-do:** if a trivial device-property write is later confirmed, it's a
  one-field add to the device strip. Not worth a protocol spike on its own.

### 4.3 Acceptance (81v.11)
- The editor can discover and connect to a device and show its identity (model/
  serial/firmware/storage), read-only.
- The firmware/account/PIN/licenses items are **absent by design**, each listed as
  won't-do in this doc with its reason.

---

## 5. 81v.12 Song View / Showcase — **WON'T-DO** (recommendation to ratify)

**Recommendation: do not build Song View in `device live`.** This is the candidate
won't-do the parity map already flagged; here is the case to ratify it.

### 5.1 Why it does not belong in helixgen
1. **Hardware/purchase gate.** Every audio feature of Song View requires a **microSD
   card (sold separately)**, formatted by the Stadium, inserted before power-on.
   helixgen can't provision or require that, and a tone-authoring tool shouldn't make
   a microSD a dependency.
2. **Mission fit — none.** helixgen's mission is **authoring `.hsp` presets from
   natural-language tone requests** and driving tone/preset state over LAN. Song View
   is a **live-performance backing-track player**: audio tracks, stem split (5 stems),
   markers, flags that automate preset/snapshot recall, playlists, a transport. It
   consumes presets; it doesn't author them. The overlap is a single thin edge (a
   flag can *recall* a preset), not a shared surface.
3. **Surface cost vs value — badly lopsided.** Parity would mean a net-new protocol
   + engine track: song-library CRUD (up to **256 songs**), **8-track** audio
   transfer and format conversion (WAV/AIFF/FLAC/OGG → 48k/16/stereo, ≤13 min),
   **stem-split** orchestration, flags/markers model, and a playback transport UI.
   That rivals the *entire* signal-flow epic in size, for **zero tone-authoring
   gain**. It is the single worst effort-to-mission ratio in the whole parity map.
4. **It's device-level, not preset-level.** Like a librarian, it sits outside the
   preset the editor exists to shape — the P3 "not a preset surface" thread at its
   extreme.

### 5.2 Minimal alternative (only if the owner insists on *some* presence)
If, and only if, the owner wants a toehold rather than a full won't-do, the
**smallest defensible** surface is **read-only, no audio**:
- **Follow** the device's active-song / active-flag state on the 2001/2003 streams
  (if it broadcasts there — a capture, not assumed) and show "Song: X / Flag: Y" as a
  status line in the editor, so a tone author sees which song context is live.
- **Explicitly not:** song creation, audio transfer, stem split, playlist editing,
  transport. Those stay in the official app.

This alternative is a **status readout**, not Song View. Recommend it only as a
fallback; the default recommendation is a clean won't-do.

### 5.3 What ratification means
Owner says either:
- **"Won't-do"** → Song View is struck from the 81v epic; the parity map notes it as
  owner-ratified won't-do with this doc as the reason. **(Recommended.)**
- **"Toehold"** → open a tiny follow-up to capture whether song/flag state is
  broadcast, and add the read-only status line only if it is.

---

## 6. Cross-epic notes (shared surfaces)
- **Global settings overlap:** tuner and tempo controls are `global.*` settings. The
  **Global settings / I/O** P2 epic owns the full settings pages. The tuner/tempo
  panel here deliberately surfaces only the *tuner-relevant* subset (needle while
  dialing a tone, BPM for tempo-synced blocks) and **defers the full Tempo/Click +
  tuner-settings pages to that epic** — agree one owner for `global.tuner.*` /
  `global.tempo.*` write-through so the two surfaces don't fight. One settings client.
- **Device strip overlap:** `device info`/`discover` is also the editor's connect
  handshake (81v.1). The device strip is a *view* of that same connect state, not a
  second connection path.
- **No new engine work for 81v.10/11.** Both are UI over shipped CLI/decoder surfaces.
  81v.12 is struck (or a capture-first toehold). This P3 tail adds **no helixgen-core
  epic** — the only possible core touch is an optional tap-tempo opcode capture, which
  is a nice-to-have, not a blocker.

## 7. What's left to the builder
- **Tap-tempo:** confirm/deny a tap opcode on the wire during 81v.1 captures; if
  absent, ship client-side-computed BPM (the plan of record). No blocker either way.
- **Tempo range:** confirm the settable BPM range on the wire (manual says 20.00 via
  Tempo Panel, taps ignore < 40.00) — clamp the field to what the device accepts.
- **Tuner output/mute:** decide the panel's default for `global.tuner.output` on open
  (recommend: show current, change nothing).
- **Rename-device:** a 10-minute capture would confirm whether a device-name property
  exists; only then add the field. Not worth a dedicated spike.
- **Song/flag broadcast:** needed only if the owner picks the §5.2 toehold.
