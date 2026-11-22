# Command Center UI parity (`helixgen-81v.4`) — design

**Status:** design — awaiting approval.
**Date:** 2026-11-22.
**Scope:** the **Command Center** area of the `device live` unified-live workspace —
per-preset command assignments (sources → commands), the command inspector, snapshot
control of command params, copy/paste/clear, and Stomp label/colour. Sibling P2 epic
in the [`stadium-app-parity.md`](../../parity/stadium-app-parity.md) map; **explicitly
out of scope for 81v.1** (signal-flow editor), which lists it as a separate epic.
**Model:** inherits the **unified-live** model resolved by the 81v.1 protocol spike
(`2026-11-21-signalflow-editor-parity-design.md` §2). Command Center edits are
buffer-level and ride the **same whole-buffer live push keystone**; this doc does not
re-derive that mechanism, it depends on it.
**Manual:** <https://manuals.line6.com/en/helix-stadium/live/command-center>
(app v1.4 / fw 1.4), captured 2026-11-22.

---

## 0. TL;DR for the owner

- **Not a pure UI-add.** The param vocabularies and the forward (author → device)
  path exist; the **device → helixgen read path does not** — `untranscode` drops
  Command Center entirely (`cli_device.device_to_hsp` docstring: *"not reversed at
  all: Command Center commands and MIDI CC controller bindings"*). Until that reverse
  path lands in **helixgen-core**, the live editor is blind to any command already on
  the device. This is the long pole and it is engine work, not UI.
- **Key design decision:** command edits reach the device the **same way topology
  does** — mutate the live buffer's `.hsp` offline, encode `_sbepgsm`, whole-buffer
  push. There is **no granular command opcode**. So 81v.4 is sequenced **after** 81v.1
  pins the whole-buffer-SET verb; it is a consumer of that keystone, not an
  independent protocol problem.
- **Won't-do / caveats:** Hotkey and Ext Amp commands are *authorable* but
  helixgen cannot *exercise* them (USB-HID keystrokes; a physical amp jack) — ship as
  author-only with a "can't verify from helixgen" badge. Continuous/EXP MIDI command
  authoring is an engine gap (`#16` residual). Live MIDI-monitor / "learn incoming" is
  a won't-do (Command Center is outbound-only).

---

## 1. Intent / why

`device live` today edits the **signal chain** — blocks, params, bypass, snapshots it
follows. It has **no Command Center surface at all**: you cannot see, let alone author,
what a footswitch, expression pedal, or Instant slot *sends* when used — MIDI PC/CC/
Note/MMC to a rig, snapshot/preset recall, looper transport, Ext Amp channel switching,
Hotkeys to a DAW. To do any of that today a user drops to `helixgen`'s recipe/`.hsp`
authoring (which *can* write a subset of commands) or the Line 6 Stadium app.

This epic brings the Line 6 **Helix Stadium Edit** *Command Center* screen into the
unified-live workspace: a per-preset master-remote editor where every source
(footswitches, pedals, XY axes, Instants, external switches, triggers) shows its
assigned commands, each command is authored/edited live, and the panel **follows the
device** like every other control in `device live`.

Command Center is the device's outbound-control brain. It is distinct from (but shares
hardware sources with) the **Controllers & assignments** epic (P1, which maps a
source → a *block param or bypass*); Command Center maps a source → an *outbound
command or a Helix action*. See §12 for the overlap and the coordination it forces.

---

## 2. The model decision — how a command edit reaches the live device

81v.1's spike established that the Stadium live protocol has **granular opcodes** for a
handful of edit-buffer changes (`/setParamValue`, `/setBlockEnable`, `/ModelSet`) and
falls back to a **whole-edit-buffer live write** (echo `/setEditBuffer`, in place, no
reload, no apply seam) for everything structural. The open question for Command Center
is the same one 81v.1 asked for topology: **is there a granular live opcode for a
command, or is a command edit a buffer-level change?**

### Evidence from the engine (not a new spike — code + capture record)
- Commands are stored in the preset as **native `preset.commands`** records plus the
  relational `cg__` `srcs`→`cmnd`→`trgs` wiring that the `_sbepgsm` buffer carries
  (`transcode._synth_commands`, `_command_payload`, `_command_locl_ctxt_type`). A
  command is an **entity** (`enty 6`, `type 4`, `cmnd.cid_ == trg eID_`) — i.e. it
  lives in the same entity/source/target graph that topology and controllers do.
- The live-ops client (`device/client.py`) exposes **no command opcode** — its proven
  writes are `/BlockEnableSet`, `/ModelSet`, `/setParamValue`, bypass. There is no
  `/setCommand`, and no OSC **read** for commands either (the live editor reads blocks/
  params via `edit_buffer_blocks()` / `edit_buffer_params()`, which have no command
  analogue).
- The 81v.1 capture showed that **adding/removing an entity** (a block) is a
  whole-buffer `/setEditBuffer`, not a granular op. A command is an entity. By the same
  mechanism, **adding or removing a command, or changing its source/func, is a
  whole-buffer change.**

### Decision: **unified-live, whole-buffer push** (inherit 81v.1's keystone)
- **Add / remove / re-source / change-family a command** → mutate the live buffer's
  `.hsp` (`mutate.wire_command` + a new clear/remove), encode `_sbepgsm`, **whole-buffer
  live push** — the exact write-twin of a topology edit. One command edit = one
  whole-buffer push = one undo step. Re-sync the editor from the echoed `/setEditBuffer`.
- **Tweak a scalar param of an existing command** (CC `Value`, `Velocity`, MIDI
  `Channel`, `Wait`) → **candidate granular `/setParamValue`** on the command entity's
  param coordinate, *if* the command entity's params are addressable the same way a
  block's are. **Pin-first (§11):** confirm a command param echoes `/setParamValue`
  granularly. If it does, scalar command tweaks are as cheap as a knob turn; if not,
  they degrade to whole-buffer push (tolerable — a command edit is deliberate).
- **No independent protocol RE for 81v.4.** The whole-buffer-SET verb is 81v.1's
  pin-first keystone; 81v.4 consumes it. If 81v.1's keystone can't be pinned (its Plan
  B is offline→`/SetContentData`→reload with a visible apply step), Command Center
  inherits that degraded mode too.

This is the app's own model: the Stadium app's Command Center writes land in the live
buffer and are heard/active immediately, with no "apply commands" step.

---

## 3. Engine-readiness — explicit (what exists vs what's new engine work)

Grounded in the helixgen-core checkout (read-only), 2026-11-22. **This is the section
the owner should read to size the epic.**

| Capability | State | Where |
|---|---|---|
| Command param **vocabularies** (action, extamp select/state, looper, midi command/message, preset/snap, song, utility, midi_note C-1…G9, ext-amp-instant select) | ✅ **ready** | `device/_param_ui.json` `cc_*` + `midi_note` |
| **Author** a command into `.hsp` (`preset.commands` + `preset.sources`) | ⚠️ **partial** | `mutate.wire_command`, `recipe` `spec.commands` |
| **Forward transcode** `.hsp` → device `_sbepgsm` (synth `cg__` srcs/cmnd/trgs, byte-exact HW anchors) | ⚠️ **partial** | `transcode._synth_commands` / `_command_payload` |
| Flatten `preset.commands` → editor JSON | ✅ ready (but **unused** today) | `bridge.hsp_commands` (no caller yet) |
| **Reverse transcode** device `_sbepgsm` → `.hsp` commands | ❌ **DROPPED — new engine work** | `untranscode` (`"Command Center commands dropped — not yet reversed"`, line ~790) |
| **Live read** of device-resident commands (OSC) | ❌ none | no command read in `client.py` |
| **Live write** of a command (granular opcode) | ❌ none — rides 81v.1 whole-buffer push | `client.py` |

### Author/forward coverage (the ⚠️ rows), precisely
- **Sources resolvable today** (`controllers.resolve_command_source`): `FS1`–`FS5`,
  `FS7`–`FS11`, `Instant1`–`Instant6`. **Missing:** `Instant7`–`Instant16`, Expression
  pedals, Toe switch (XL), XY X/Y axes, External Stomp A/B, External C/D (XL), Triggers
  A/B and C/D (XL), External Controllers A–D.
- **Source → device mapping** (`transcode._command_locl_ctxt_type`): only FS bank A
  (`0x010101xx` → `locl 25+NN, ctxt 1, type 1`) and Instant 1–6 (`0x040401xx` →
  `locl NN, ctxt 0, type 4`). Everything else is **unmapped** → forward transcode
  can't place it.
- **Command families authorable today:** `snapshot`, `preset`, `midi_cc`, `midi_pc`,
  `midi_note`, `midi_mmc`. **Missing:** Song, Looper, Utility, Ext Amp, Hotkey, and
  Bank-only (no PC). Continuous/EXP MIDI payload is explicitly **"not authored (out of
  scope, #16 residual)"**.
- **Actions:** the `.hsp` record carries `behavior` (latching/momentary — **per
  footswitch**, matching the manual's Note-Off rule) + `toggle`, and an `Action` param
  whose vocab exists (`cc_action` = Press/Release/Hold/Toggle, `cc_drum_action` =
  Strike/Toggle). `wire_command` currently hardcodes `Action: 0` — the **Action 1 /
  Action 2** dual-action model the manual describes is **not yet authored**.

### The honest summary
helixgen can **author and install** the *anchored subset* of commands onto a device
today (via `.hsp` author → `device copy`/save → forward transcode). It **cannot read
back** any command from the device, and the live editor has **no command surface**.
81v.4 therefore needs, in helixgen-core, **(A) a reverse-transcode command decoder**
(the gating long pole — without it the panel can't follow the device or round-trip),
and **(B) coverage expansion** of sources/families/actions to match the manual. The UI
(C) is meaningful but is the *shorter* pole once A+B land. Sequence: **A → B → C**, and
C's live writes wait on **81v.1's whole-buffer-SET keystone**.

---

## 4. Goals

- A **Command Center panel** inside `device live`: a **source bar** (footswitches,
  pedals, XY, Instant 1–16, external switches, triggers — XL-aware) with a **turquoise
  "has-commands" marker** on any assigned source, and a **command inspector** for the
  selected source.
- **Author / edit / clear** commands live, heard-and-active immediately (whole-buffer
  push), across the full manual surface: all sources; all seven families (Preset/Snap,
  Song, Looper, Utility, Ext Amp, MIDI {Bank/Prog, CC, Note On, MMC}, Hotkey); **Action
  1 / Action 2** (Press/Release/Hold/Toggle; Strike/Toggle for triggers) with the
  toggle-locks-both rule; **Wait / Wait Time** on Instant commands; per-family param
  fields exactly as the manual enumerates.
- **Two commands per switch** (merged switch) where the source allows; the manual's
  per-source limits enforced (§8.1).
- **Snapshot control** of eligible command params (the "white value" toggle), excluding
  `Action` and MIDI `Command`, matching block-param snapshot control.
- **Copy / Paste** (one command, or All Commands) within and across presets, pasting
  only target-supported commands and overwriting; **Clear Command** / **Clear/Reset
  All**.
- **Label / Colour** on **Stomp A/B only** (scribble strip), with Auto/Off LED.
- **Follows the device:** a Command Center change made on the hardware, in HX Edit, or
  by another helixgen verb appears without reload (depends on reverse-transcode, §3 A).
- Commands **persist** via the existing Save / `device copy` model and **round-trip**
  `.hsp` ⇄ library (`device to-hsp`) with no loss (depends on §3 A).
- Parity items the live protocol genuinely can't do are **won't-do with the reason**
  (§10), never silently missing.

## 5. Non-goals (other epics)
- **Controllers & assignments** (P1): source → block param/bypass "learn", min/max
  range, EXP sweep, XY rubber-band controller. Command Center shares the *source bar*
  and *scribble strip* with that epic (§12) but owns only *commands*.
- Global Settings > Switches/Pedals (which jacks are EXP/Ext-Amp/trigger) and Global
  Settings > MIDI (output routing, base channel) — **P2 Global settings** epic. Command
  Center only *reflects* those globals (a source is unavailable if its jack isn't set).
- Snapshot **management** UI (capture/rename/copy snapshots) — P1 Snapshots epic.
  Command Center only *consumes* snapshot-control per param.
- Song View, Looper transport UI, tuner — separate epics. Command Center authors the
  *commands that drive* them, not those surfaces.

## 6. Anti-goals (a failure even if it technically works)
- A **visible "apply commands" step.** Inherits 81v.1's no-seam mandate — a command
  edit must feel like a knob turn, not a save.
- **Silent command loss on round-trip.** A preset authored/edited with commands that
  doesn't come back byte-faithfully through `.hsp` ⇄ `_sbepgsm` (the §3 A reverse path
  must be a fixed point, like `device to-hsp` is for blocks).
- A **helixgen-only command representation** diverging from the device's native
  `preset.commands` / `cg__` entity graph. Author natively (as `wire_command` already
  does), never a sidecar — the `#33` MIDI-CC sidecar is the anti-pattern to avoid
  repeating.
- **Showing a source as assignable when its global jack isn't configured** (external
  switches/pedals/triggers, Ext Amp) — mirrors the app, which gates them on Global
  Settings.

## 7. Constraints
- Device-bound, firmware **1.4+** (as `device live` today).
- **Skills drive the CLI, not source** — the command-authoring + new reverse-decode
  contracts live in `helixgen` per-verb `--help` (pinned by core's CLI-parity tests) +
  synced `docs/`. A companion plugin PR updates `skills/*` + `docs/CLI.md` /
  `docs/helix-protocol.md` when the engine surface lands.
- Offline command edits go through the existing `mutate` / `recipe` + `.hsp`→`_sbepgsm`
  transcoder; the encoder must round-trip a **command-mutated** buffer byte-faithfully
  (the `cg__` entity extension — `nxts`/`nxtt` bookkeeping in `_synth_commands`).
- **Agent-surface sync across repos:** the new reverse-transcode facts and any new
  source/family coverage land in **helixgen-core** first (engine + `docs/helix-
  protocol.md`), with the companion plugin PR here.
- XL-awareness: the source bar, Toe/External-C-D/Triggers-C-D, and Ext-Amp "C and D"
  option are XL-only; resolve chassis from `meta.device_id` (as `controllers.py` does).

## 8. The how — decided

### 8.1 Source bar (the left/top rail of the panel)
Render every command source for the chassis, grouped as the app does:
**Stomp A/B** (per assignable footswitch), **Expression pedals**, **Toe** (XL),
**XY X-Axis / Y-Axis**, **Instant 1–16**, **External Stomp A/B**, **External C/D**
(XL), **Triggers A/B**, **Triggers C/D** (XL), **External Controllers A–D**.
- A source shows a **turquoise triangle** when it holds ≥1 command (manual's marker).
- A source is **greyed/unavailable** when its backing global jack isn't configured
  (external switches/pedals/triggers via Global Settings > Switches/Pedals Control A–D;
  Ext Amp jack). helixgen already reads Global Settings (`device settings`), so the
  panel queries the live jack config to gate sources — it does **not** let the user set
  those jacks (that's the Global settings epic); it links out with a note.
- Per-source **command-type eligibility** enforced from the manual (§8.2 table): e.g.
  EXP and XY → MIDI CC only, one command; Instant → all families except Preset/Snap and
  Utility; triggers → Strike/Toggle actions only.

### 8.2 Command inspector (families + fields)
Selecting a source opens the inspector with **Action 1 / Action 2 tabs** (two commands
per switch where allowed) and a **family picker** (the manual's coloured boxes). Fields
per family, from the manual + the engine's existing `cc_*` vocab:

| Family | Fields (device param names) | Sources |
|---|---|---|
| **Preset/Snap** | `Action`, `Command` (`cc_presetsnapshot_command`: Next/Prev Bank/Preset/Snap, Preset, Snapshot), `Setlist`+`Preset` (when Preset), `Snapshot` (when Snapshot) | all except Instant, EXP, XY |
| **Song** | `Action`, `Command` (`cc_song_command`: Play/Pause, Prev/Next Song, Prev/Next Marker, Return to Zero, Cycle), `Wait` (Instant) | all except EXP, XY |
| **Looper** | `Action`, `Command` (`cc_looper_command`: Play/Stop, Record/Overdub, Play Once, Clear Loop, Reverse/Forward, Half/Full Speed, Undo/Redo), `Wait` (Instant) | all except EXP, XY |
| **Utility** | `Action`, `Command` (`cc_utility_command`: Save, Mute All, Stopwatch) | all except Instant, EXP, XY |
| **Ext Amp** | `Action`, `Select` (`cc_extamp_select`: A(Tip)/B(Ring)/A and B/C(Tip)/D(Ring)/C and D), `State` (`cc_extamp_state` Close/Open; Instant), `Wait` (Instant) | all except EXP, XY |
| **MIDI** | `Action`, `Command` (`cc_midi_command`: Bank/Program, CC, Note On, MMC), `MIDI Ch`, then per subtype: **Bank/Prog** `MSB(CC00)`/`LSB(CC32)`/`PC` each w/ Off; **CC** `CC#`/`Value` (EXP/XY: `Min`/`Max`); **Note On** `Note` (C-1…G9, `midi_note`), `Velocity`, `NoteOff` latching/momentary (per-FS, not Instant); **MMC** `Message` (`cc_midi_message`), `Wait Time` (Instant) | per-subtype (CC also EXP/XY) |
| **Hotkey** | `Action`, `Modifier 1/2/3`, `Keystroke`, `Wait Time` (Instant) | all except EXP, XY |

- **Action semantics:** Action 1/Action 2 each Press/Release/Hold/Toggle (triggers:
  Strike/Toggle). If Action 1 = Toggle, Action 2 locks to Toggle and greys out (the
  on/off pattern, e.g. one CC# with values 0 and 127). The inspector enforces this; the
  engine's `toggle` flag + two ordinals model it — but `wire_command`'s hardcoded
  `Action: 0` must become a real field (§3 engine B).
- **Note-Off latching/momentary is per-footswitch**, not per-command — the inspector
  surfaces it as a switch-level setting (matches `behavior` in the `.hsp` record) and
  refuses to mix opposing types on one switch.

### 8.3 Edit routing (the live mechanics)
- **Author/remove/re-family/re-source** → re-fetch `/EditBufferStateGet` (guard against
  a concurrent writer, as 81v.1 §8.1 decided for topology), mutate its `.hsp`
  (`wire_command` / new `clear_command`), encode `_sbepgsm`, **whole-buffer push**,
  re-sync from the echoed `/setEditBuffer`. One edit = one undo step.
- **Scalar param tweak of an existing command** → granular `/setParamValue` **iff** the
  §11 pin confirms command params echo granularly; else whole-buffer push.
- **Persist** with existing Save (`/SavePresetWithCID`) / `device copy`; `device to-hsp`
  round-trips (needs §3 A).

### 8.4 Snapshot control of command params
- Each eligible command param gets the **"white value" toggle** (press-and-turn, or a
  Snapshot-Ctrl toggle in the inspector sidebar), identical to block-param snapshot
  control (P1 Snapshots groundwork — dense `@enabled` arrays, value==active invariant).
- **Excluded:** `Action` and MIDI `Command` (manual). Instant commands change on
  snapshot recall when snapshot control is on.
- Reuses the engine's existing snapshot/controller `cg__` machinery
  (`untranscode`/`transcode` already model per-snapshot arrays + controller leaves) —
  the command entity joins the same per-snapshot array treatment.

### 8.5 Copy / Paste / Clear
- **Copy Command** (both, for a dual-command source) / **Copy All Commands** (whole
  preset) → helixgen-local clipboard of the native `preset.commands` records.
- **Paste Command / Paste All** → filter to the target's supported families (§8.2),
  overwrite the target, re-source the records' keys to the target's source id, then one
  whole-buffer push.
- **Clear Command** (per Action tab) / **Clear/Reset All** (whole preset) → drop the
  `preset.commands` key(s) + the orphaned `preset.sources` entry, whole-buffer push.

### 8.6 Label / Colour (Stomp A/B only)
- `wire_command` already writes `fs_label` / `fs_color` into `preset.sources` and warns
  on non-footswitch sources. The inspector exposes the keyboard label + colour swatch
  (Auto/Off) **only for Stomp A/B**; Preset/Snap, Looper, Utility commands and all
  non-footswitch sources show no label/colour control (manual).

### 8.7 Following the device
- The live editor follows block/param/snapshot changes today via the 2001 stream +
  `edit_buffer_*` reads. Commands have **no 2001 granularity and no OSC read** (§3), so
  "follow" for Command Center is: on any `/setEditBuffer` echo (a whole-buffer change
  from anywhere), **re-run the reverse-transcode command decode** (§3 A) and re-render
  the panel. This is the *only* way the panel can follow the device — which is exactly
  why §3 A is the gating prerequisite, not a nice-to-have.

## 9. Approaches considered
1. **Granular command opcodes** — author each command edit as a live op. **Ruled out:**
   no command opcode exists; a command is an entity and entity add/remove is
   whole-buffer (81v.1 spike). Even scalar tweaks are only *maybe* granular (§11 pin).
2. **helixgen sidecar for commands** (like `#33` MIDI-CC's `preset._helixgen_midi`).
   **Ruled out:** commands have a *native* `preset.commands` encoding the engine already
   authors into; a sidecar would re-introduce the exact divergence the `#33` approach
   was a workaround for, and break app/HX-Edit interop.
3. **Unified-live, native, whole-buffer push (CHOSEN)** — author natively, push the
   whole buffer, reverse-decode to follow. Matches the app; reuses 81v.1's keystone and
   the mature offline-mutate path; the only new *protocol* work is the reverse decoder
   (which is needed for round-trip regardless).

## 10. Won't-do / degraded, with the reason
- **Hotkey (QWERTY over USB-HID):** *authorable and storable* in the preset, and the
  device sends the keystrokes to a connected Mac/PC/iOS over USB. But helixgen drives
  the Stadium **over LAN** and is not the USB-HID host — it **cannot exercise or verify**
  the keystroke delivery. Ship as **author-only**, with a "fires from the device; can't
  be tested from helixgen" badge. (Needs engine family coverage, §3 B — not currently
  authored.) Not a hard won't-do, but an explicit capability ceiling.
- **Ext Amp switching:** authorable; requires a Control A–D jack set to "Ext Amp"
  (Global Settings) and a short-to-sleeve amp. helixgen can author it but can't
  validate without the physical rig. **Author + caveat**, gated on the live jack config
  (§8.1). Manual's damage warning surfaced in the UI.
- **Continuous / EXP-pedal MIDI command payload:** the forward transcoder explicitly
  does **not** author the EXP 5-slot continuous layout ("out of scope, #16 residual").
  Until engine coverage lands, EXP → MIDI CC commands are **won't-do-yet** (shown
  disabled with the reason), not silently absent.
- **Live MIDI monitor / "learn from incoming MIDI":** Command Center is **outbound
  only** (it *sends* commands). There is no inbound-command surface to mirror — **hard
  won't-do.**
- **Setting the Global jacks / MIDI base channel from this panel:** out of scope (P2
  Global settings epic). The panel **reads** them to gate sources and **links out**;
  it never writes them.

## 11. What's left to the builder (pin-first + open questions)
- **Pin-first (before committing the UI write path):**
  - **(a) 81v.1's whole-buffer-SET verb** — the shared keystone. 81v.4 is blocked on it;
    do not start the live-write UI until it's pinned (or its Plan B accepted).
  - **(b) Command-param granularity** — place a known command, change its `Value`/`Wait`
    via the app, watch 2001: does it echo `/setParamValue` (granular, cheap) or
    `/setEditBuffer` (whole-buffer)? Decides §8.3's scalar path.
  - **(c) Reverse-transcode anchors** — capture real multi-source, multi-family command
    presets (XY/EXP/trigger/external + Song/Looper/Hotkey) off the device so the §3 A
    decoder has byte anchors for the families/sources the forward path hasn't mapped.
- **Engine (helixgen-core), the long pole:**
  - **A. Reverse-transcode command decoder** — inverse of `_synth_commands`
    (`cg__` `cmnd`/`srcs`/`trgs` → `preset.commands` + `preset.sources`), making
    `device to-hsp` a fixed point for commands. **Gates** follow-the-device +
    round-trip; nothing in the UI can show a device-resident command without it.
  - **B. Coverage expansion** — add the missing sources to
    `controllers.resolve_command_source` + `_command_locl_ctxt_type` (Instant 7–16, EXP,
    toe, XY, external A/B + C/D, triggers A–D), the missing families to `wire_command` /
    `_command_payload` (Song, Looper, Utility, Ext Amp, Hotkey, Bank-only), and the real
    **Action 1/2** model (replace hardcoded `Action: 0`).
  - **C. Byte-faithful round-trip** of a command-mutated buffer (the `cg__` entity-space
    extension, `nxts`/`nxtt`) before trusting whole-buffer push for real presets.
- **Open questions:**
  - **Wait units/range** — manual gives ms and a 0 ms default but no max/step; capture
    from the device.
  - **Song / Looper command *value* enums beyond what `cc_*` lists** — the manual
    doesn't fully enumerate; the engine's `cc_song_command`/`cc_looper_command` are the
    current best list; verify against a capture.
  - **Per-preset total command limit** — not stated in the manual; per-source limits are
    known (§8.1). Find the ceiling (if any) from the entity-space bookkeeping or a
    capture, else document as best-effort.
  - **Instant source-id range** — `INSTANT_SOURCE_IDS` only anchors 1–6
    (`0x04040100+N-1`); confirm 7–16 follow the same stride before authoring them.

## 12. Collision check — sibling epics
- **81v.1 signal-flow editor:** **no feature overlap** (81v.1 explicitly excludes
  Command Center). But 81v.4 is a **hard dependency** on 81v.1's unified-live model and
  its whole-buffer-SET keystone (§2, §11a). Sequence 81v.4 *after* 81v.1's protocol
  foundation. The 81v.1 "no apply seam" anti-goal and whole-buffer re-sync/undo policy
  are inherited verbatim.
- **P1 Controllers & assignments (being designed concurrently):** **real overlap, needs
  coordination.** Command Center and Controllers both:
  - live in the same **source space** — a footswitch/EXP/XY/trigger id can carry *both*
    a controller assignment *and* a command (`transcode`: *"a footswitch can carry a
    controller AND a command, so the two never contend for one `srcs` entry"*). The
    **source bar is shared UI**; decide whether it's one rail with a Controller/Command
    mode toggle (like the app) or two panels reading the same source list.
  - share the **scribble strip** (`preset.sources` `fs_label`/`fs_color`) — a Stomp's
    label/colour is one record; both epics write it. One owner for that write path, or
    they clobber each other.
  - share the reverse-transcode need: `untranscode` drops **both** "Command Center
    commands **and** MIDI CC controller bindings." The §3 A decoder work should be
    scoped to cover both so the two epics don't each build half of it.
  **Recommendation:** land the reverse-transcode decoder (and the shared source-bar +
  scribble-strip ownership) as a **joint foundation** for 81v.4 + the Controllers epic,
  not twice. Flagged to the `design-controllers` session via the shared notes folder.

## 13. Acceptance
- In `device live`, a user sees every command source for their chassis, with assigned
  commands shown and the turquoise marker on assigned sources, and authors/edits/clears
  commands across all seven families — heard/active immediately, no app, no `.hsp`
  hand-edit.
- A Command Center change on the hardware / in HX Edit appears in the panel without
  reload (follows the device).
- Commands persist via Save / `device copy` and round-trip `.hsp` ⇄ library
  (`device to-hsp`) with no loss.
- Snapshot-controlled command params behave exactly like block-param snapshot control.
- Parity items the protocol genuinely can't do (live MIDI monitor; EXP continuous until
  engine coverage; Hotkey/Ext-Amp exercise-from-helixgen) are documented won't-do /
  caveat, not silently missing.

## 14. Evidence
helixgen-core checkout read 2026-11-22 (read-only): `device/_param_ui.json` (`cc_*` +
`midi_note` vocab), `mutate.wire_command` / `_command_native_record`,
`recipe` (`spec.commands` → `wire_command`), `device/transcode.py`
(`_synth_commands`, `_command_payload`, `_command_locl_ctxt_type`, HW anchors
2026-07-14/15), `device/untranscode.py` (`dropped_midi`, *"Command Center commands
dropped — not yet reversed"*), `device/bridge.py` (`hsp_commands`, no caller),
`cli_device.device_to_hsp` docstring (commands + MIDI-CC not reversed),
`controllers.py` (`INSTANT_SOURCE_IDS` 1–6, `resolve_command_source` FS1–5/FS7–11).
Manual: Line 6 Helix Stadium *Command Center* (app v1.4 / fw 1.4), fetched 2026-11-22 —
sources, seven families, Action 1/2 + toggle-lock, Wait, snapshot control, copy/paste/
clear, Stomp-only label/colour, per-source limits, XL-only sources.
