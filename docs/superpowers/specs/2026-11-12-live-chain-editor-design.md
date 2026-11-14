# Design — Live chain editor (signal-chain knob UI for the Helix Stadium)

**Date:** 2026-11-12
**Status:** approved 2026-11-12 (Michael: "Design is preapproved, plan is preapproved. Implement it, test it, ship it.") — implemented in helixgen-core as `hgc-58a`. See *Revision 2026-11-12* at the end for what changed during the build.
**Scope:** cross-repo — the feature lives in `helixgen-core` (new verb + local server + page); this plugin repo adds launcher guidance to the `device` skill, synced docs, and an engine pin bump.

Markers used below: **[Michael]** = decided by Michael in brainstorming. **[call]** = a choice the author made that Michael has not explicitly agreed to; the builder may treat it as the default, Michael may overrule it.

## Intent / why

Michael builds presets at the desk with the guitar on. Today, changing a parameter means either reaching for the hardware/HX Edit, or asking an agent and waiting ~30 s per round trip. He wants to **play a chord, twist a knob on screen, and hear it move immediately** — with the *whole* rig laid out as a signal chain so nothing is hidden behind a menu.

The origin question was "can the helixgen skill, invoked in Claude, put up a UI with knobs that control the Helix?" The answer is a local web page served by a long-lived helixgen process that holds the device connection; Claude launches it and gets out of the way. Claude is never in the knob→device path.

A throwaway spike proved the loop on the Stadium XL on 2026-11-12 (see *Evidence from the spike*). Michael's verdict: "It's working great now, for a spike." This document is the design for the real thing.

## Goals

1. **Show the whole live rig as a signal chain** **[Michael]** — every block on the device's active tone, in signal order, across all DSP paths, including parallel lanes (splits/merges) and the **input and output blocks**.
2. **Every parameter is a native control** **[Michael]** — continuous params are knobs, on/off params are toggles, list params are dropdowns. Each block has a bypass toggle.
3. **Twist-and-hear** **[Michael]** — dragging a knob changes the sound while the drag is in progress, with no perceptible lag and no backlog.
4. **Undo / redo** **[Michael]** — Ctrl/Cmd+Z undoes, Ctrl/Cmd+Shift+Z redoes (Ctrl+Y also redoes **[call]**). A knob drag is **one** undo step, recorded when the knob is released, even though the device is updated continuously during the drag.
5. **The page tracks the device** — a change made on the hardware, by a footswitch, by HX Edit, or by another helixgen process shows up on the page without a manual refresh; a preset or snapshot switch re-renders the page.
6. **Launchable from Claude** — the plugin's `device` skill tells the agent how to start it and hand the user the URL.
7. **Keep what you dialed** — a Save control persists the tweaked tone (semantics: see *Decisions* 6 and *Questions for Michael* 1).

## Non-goals (v1)

- **No structural editing** **[Michael]** — no adding, removing, reordering blocks, no creating splits, no model swaps. *"I don't want to build an arbitrary editor yet. But I don't want to close the door to that."* See *Decisions* 9 for what "not closing the door" requires.
- **No optimistic load from the library** **[Michael]** — the page renders from the device, not from a guessed library file.
- **No device-vs-library drift report** in this work — wanted later, tracked as `hgc-wv1` in the core beads tracker.
- **No intent dials.** The adjective-dial tweaker on core's unmerged `tweak-ui` branch is a different UI and is not part of this (see *Decisions* 1).
- **No adjective search yet** **[Michael]** — wanted later, tracked as `hgc-nci`: a search box over known tone adjectives that *highlights* the knobs (in non-bypassed blocks) affecting that quality and dims the rest. This is how adjectives return — as a highlight layer over the real knobs, not as dials. The only thing it asks of this build: every control on the page is addressable by (DSP path, grid slot, param id) so a highlight can be applied without re-rendering.
- Not remote, not multi-user, no phone/tablet access: localhost only.
- No snapshot editing tools (clone, rename) and no controller/footswitch assignment UI.

## Anti-goals (failure even if it "works")

- **Backlog.** The spike's first cut queued every drag sample as a blocking write and fell *seconds* behind. Any design where write requests can queue without bound is wrong, however fast each write is.
- **The page lying about the device.** A control showing a value the device does not have — because a write failed silently, an event was missed, or the page rendered something other than the live edit buffer — is worse than a slow page. Failed writes must be visible on the control; a reconnect must re-read.
- **Showing a different rig than the one loaded.** The live edit buffer is the only source the page renders from. During the spike the loaded preset changed between sessions (19 blocks → 22, different amp); anything keyed on "what we expect is loaded" would have shown the wrong amp.
- **Writing values the hardware would not accept from its own knob.** The device clamps nothing: an out-of-range write lands and is applied. Every write is clamped to the advertised range server-side. The existing +20 dB output-level ceiling is honored.

## Constraints

- Stadium / Stadium XL only; device powered on and discovered (`helixgen device discover`). The device's network stack is flaky — connections drop and must be re-established without restarting the page.
- Core repo rules apply: TDD (failing test first), stdlib + `click` only (no web framework, no JS framework, no CDN — the page is one self-contained HTML file), per-verb `--help` is the behavioral contract (pinned by `tests/test_cli_parity.py`), `docs/CLI.md` and `docs/helix-protocol.md` updated in the same change.
- Cross-repo rule: core lands and releases first; the plugin PR (skill text + synced `docs/` + pin bump) follows and cross-references it. Worktrees branched from freshly fetched `origin/main` in both repos; adversarial review before merge.
- The device client is not thread-safe; all device I/O is serialized.

## Evidence from the spike (measured on the Stadium XL, 2026-11-12)

The spike is preserved at `docs/superpowers/specs/assets/live-chain-editor/chain_spike.py` — **reference only, not a starting codebase** (no tests, reaches into client privates, no event tracking).

| Finding | Number | Consequence |
|---|---|---|
| `HelixClient._rpc` default `settle=0.4` keeps polling for 0.4 s *after* the reply has arrived | one `/ParamValueSet` = **614 ms** median | unusable for live control |
| Same write with `settle=0`, short ack wait | **10 ms** median (device acks in ~10 ms) | the live write path must not use the default settle |
| Socket is `zmq.DEALER` | fire-and-forget is possible (~0 ms) but leaves acks unread | prefer consuming the ack (`settle=0`), keeps the receive buffer clean |
| One `read_edit_buffer()` returns the entire rig | **0.65 s** for 22 blocks, vs **~21 s** reading params per block | load = exactly one device read |
| Client-side coalescing (one write in flight, pending map keyed by block+param holding only the latest value) | a fast drag produced 2 writes instead of dozens | this is the anti-backlog mechanism |
| Param types come from the vendored model defs: `f` float, `i` int, `b` bool | — | control type is derivable without guessing |
| Input, output, split and join blocks are ordinary modeled blocks in the edit buffer with real params (e.g. input `Pad`, `Trim`, `noiseGate`, `threshold`, `decay`) | — | goal 1's "input and output params" needs no new protocol work |

## What already exists in core (verified against `origin/main` @ 0.59.1)

- `HelixClient`: `read_edit_buffer()`, `get_edit_buffer()` (raw blob), `edit_buffer_blocks()`, `edit_buffer_params()`, `set_param(path, block, pid, value, force=)` → `/ParamValueSet [path, grid_slot, 0, pid, value, -1]`, `set_block_enable()` → `/BlockEnableSet`, `activate_snapshot()`, `active_preset()`, `save_preset_with_cid(cid)` → `/SavePresetWithCID` (persist the edit buffer into an existing preset).
- `helixgen.device.subscribe.HelixSubscriber` — subscription to the device's 2001 change stream.
- `helixgen.device.defs` (`model_params_for`, `model_name_for`, `category_for`) and `helixgen.device.paraminfo.param_info(model_id, param_name)` → `{min, max, default, unit, scale, display_min, display_max, display_name, enum_labels, internal}`.
- `helixgen.device.untranscode` — already derives lane structure (split↔join pairing, which row-1 blocks a split brackets) when converting device content to `.hsp`; `view.branch_span` and `transcode._split_branch_gps` are the matching readers.
- Advisory device locks (`_locked("editbuffer", …)` in `cli_device.py`).

**On the unmerged `tweak-ui` branch** (core, local only, 31 commits ahead of main, no PR) — generic pieces worth lifting, independent of its intent-dial logic:

- `tweak/server.py`: the localhost-only `ThreadingHTTPServer` with Host/Origin/Content-Type guards (anti DNS-rebind / cross-origin), the **two-lock split** (`devlock` serializes device I/O, `cond` guards in-memory state + SSE — commit `4583a1a`), the SSE push loop, and the **coalescing subscriber loop** (commit `bff9684`: param events apply inline from the event payload, at most one rebuild per poll batch, a preset switch rebuilds from the pushed `/setEditBuffer` blob with zero device I/O).
- `tweak/events.py`: decoders for `/setParamValue [origin, seq, path, block, snap, pid, value]`, `/activateSnapshot`, `/setEditBuffer` (pushed live blob), `/loadContentRef`.
- `device/client.py`: `blocks_meta_from_edit_buffer()` / `blocks_meta_from_blob()` (pure parsers).
- `tests/test_tweak_server.py`: the fake-client / fake-subscriber test pattern.

## Decisions

1. **Independent of the intent-dial tweaker; built from fresh `origin/main`.** **[call]** A new package in core (working name `helixgen/liveedit/`) lifts the generic server/event/parser pieces listed above out of `tweak-ui` (copy with attribution in the commit message; do not merge the branch). `tweak-ui` stays parked and untouched; its intent library (`tweak/_intents.json`) is the starting material for the later adjective-highlight feature (`hgc-nci`). Rationale: the editor needs none of `tweak-ui`'s intent, resolve, or `.hsp` dual-write code, and that code carries its own unresolved hardware questions.

2. **The device is the truth; the server holds no `.hsp`.** **[call]** `tweak-ui` kept an in-memory `.hsp` and dual-wrote every change, mapping device blocks to `.hsp` blocks by ordinal — a mapping its own docstring flags as unvalidated, and one that cannot represent input/output/split/merge params at all. The editor instead keeps one in-memory structure parsed from the live edit buffer (all blocks, all params, raw units) and writes only to the device. This removes the mapping problem entirely and is what makes goal 1's input/output params free.

3. **One process, one device connection, in-process client.** The verb starts a server bound to `127.0.0.1`, opens one `HelixClient` and one `HelixSubscriber`, and serves a single page. Working verb name: **`helixgen device live`** **[call]** (options `--port-http`, `--no-open`, plus the standard `--ip/--port`). It holds the `editbuffer` advisory lock for its lifetime **[call]**, so other helixgen processes on the machine that mutate the edit buffer wait rather than fight the page.

4. **Load = one read.** On start, on reconnect, and on the page's explicit "re-read" control: one `read_edit_buffer()`, parsed into the chain structure. Never a per-block read. A preset switch rebuilds from the pushed `/setEditBuffer` blob (no device I/O), as `tweak-ui` does.

5. **Live write path.**
   - *Server:* a write is `/ParamValueSet` / `/BlockEnableSet` sent with no settle-drain and a short ack wait. This becomes a **supported option on the public client methods** (e.g. a keyword on `set_param` / `set_block_enable`) — not a call into `_rpc` from outside the client. Default behavior of every existing caller is unchanged. The server clamps to the advertised range from its own cached state (no per-write device read) before sending.
   - *Page:* coalescing as in the spike — at most one write in flight; newer values for the same (block, param) overwrite the pending entry; the request body is built at send time. No time-based throttle.
   - *Echo handling:* the device echoes edit-buffer changes on the 2001 stream. While a control is being dragged, incoming values for that control must not move it under the user's hand. **[call]** How (ignore-while-dragging, or filter by the event's `origin` field once hardware shows what it contains) is left to the builder, subject to hardware validation item 4.

6. **Save = the device's own save.** **[call]** The page's Save control calls `save_preset_with_cid(<active preset cid>)` — the same thing as pressing Save on the hardware; it persists everything, including input/output/split params. The page shows an unsaved-changes indicator once any write has been made since load/save. Whether Save *also* writes the result back into the library is **Question 1** below; until answered, the builder implements device save only and leaves a clearly separated seam for a library write-back step (`device to-hsp` of the saved cid).

7. **Undo / redo is page-side and write-based.** Each committed change is an entry `{block, param or bypass, before, after}`; undo writes `before` to the device through the normal write path, redo writes `after`. Toggles, dropdowns and bypass are one entry each; a knob drag is one entry at release (goal 4). **[call]** History is cleared when the preset changes **and when the active snapshot changes** — a param write lands on the active snapshot (see validation item 1), so replaying an entry recorded under another snapshot would write the wrong one. Save does not clear history. A change that arrives from the device (not made on the page) is not an undo entry.

8. **Controls show what the hardware shows.** Control type: `b` → toggle; a param with `enum_labels` → dropdown of those labels; `i` without labels → stepped knob; `f` → knob. Labels, units and display scaling come from `paraminfo.param_info` (e.g. `scale` 10 so a stored 0.74 reads 7.4, `display_name` instead of the raw param name), so numbers on the page match the Helix screen wherever metadata exists; where it does not, show the raw value. **[call]** Params flagged `internal` are hidden behind a per-block "show all" expander rather than shown by default (the spike showed the amp's ~12 internal cab-EQ params as a wall of meaningless knobs).

9. **Not closing the door on structural editing.** **[call]** Concretely: (a) the chain structure keeps each block's full device address (DSP path, grid slot, model id) and its row/lane position, not just a display order; (b) the page renders purely from that structure (a re-render after any structural change must just work — it already has to, for preset switches); (c) server operations are one endpoint per operation, so add/remove/move/model-swap can be added beside them later. Nothing else is built for it now.

10. **Plugin surface.** **[call]** No new skill: the `device` skill gains a short section (when the user wants to tweak the loaded tone by hand → run the verb in the background, give the user the URL, do not narrate knob moves) and its trigger description gains phrases like "tweak knobs", "live editor", "dial it in by hand". `docs/CLI.md` and `docs/helix-protocol.md` are re-synced from core; the pinned engine version is bumped in the skills + README; plugin version bumped in both manifest files.

## Layout (what Michael approved)

Reference mockup: `docs/superpowers/specs/assets/live-chain-editor/layout-mockup-splits.html` (open in a browser; knobs drag, bypass pills click).

- **Vertical flow** **[Michael]**, one block per row, top to bottom in signal order, each block a card: role label, model name, bypass toggle top-right, then its controls. A bypassed block is visibly dimmed.
- **A split opens side-by-side lanes** **[Michael]** — lane A and lane B as two columns, each its own vertical stack that may hold different numbers of blocks — and a **merge** closes them back to one column. The split and merge are shown as distinct structural nodes carrying their own params (split type/balance, merge levels/pans). Michael: *"It's obvious."*
- **All routing shapes must render** **[Michael]** ("I think we should support all the options here"; he does use two parallel lanes, one for a microphone). The device model, per DSP path (the edit buffer's `sfg_.flow[i]`, up to two): a two-row grid — row 0 is grid slots 0–13 (input at 0, output at 13), row 1 is slots 14–27 (input at 14, output at 27). Shapes that occur:
  - row 0 only (serial chain);
  - a split in row 0 feeding row-1 blocks that a join brings back (parallel section) — possibly more than one split/join pair in a path, paired in grid order;
  - a split with **no** join: the B lane runs on to row 1's own output (this is how USB recording taps appear);
  - row 1 with its **own real input** (not the "None" input): an independent second chain inside the same DSP path;
  - a second DSP path, rendered as its own section after the first.
  Use the engine's existing lane derivation (the pairing logic in `untranscode`, the split's `bblk` pointer) rather than re-deriving topology from slot arithmetic in the page. "None" input/output endpoints carry nothing to tweak and are not rendered **[call]**.
- **Visual polish is part of the build, not an afterthought** **[Michael]**: *"in the real UI I might want longer lines, more obvious indicators, and things to generally look a bit ... cooler."* Connectors between blocks should read as signal flow (longer, clearer lines than the mockup's small arrows; unmistakable branch/merge lines), state indicators (bypassed, unsaved, disconnected, write failed) should be obvious at a glance, and the overall look should feel like gear rather than a form. The mockup fixes the *layout*, not the styling; exact styling is the builder's, to be shown to Michael on the real rig before merge.
- Header: preset name, active snapshot name, connection state, unsaved indicator, Save, re-read.

## Architecture sketch

```
browser page (one self-contained HTML file)
   │  GET  /state            full chain structure (also sent on SSE when structure changes)
   │  GET  /events           SSE: structure pushes + small value/bypass/snapshot/connection deltas
   │  POST /param            {path, block, pid, value}      (coalesced client-side)
   │  POST /bypass           {path, block, enable}
   │  POST /save
   │  POST /reread
   ▼
helixgen device live   (127.0.0.1 only; Host/Origin guards; holds `editbuffer` lock)
   ├─ state: chain structure parsed from the live edit buffer (devlock / cond split)
   ├─ HelixClient        → fast-ack writes, one-read loads, save
   └─ HelixSubscriber    → 2001 events: param, bypass, snapshot, pushed edit buffer, preset ref
```

Endpoint names and payload shapes are illustrative; the builder owns them. Requirements that are not illustrative:

- **Deltas, not full-state pushes, for value changes.** A param event from the device updates one control on the page; it must not re-render the chain (that would kill an in-progress drag elsewhere and thrash at event rates).
- **`/setBlockEnable` must be decoded** from the 2001 stream (it is documented in `docs/helix-protocol.md` but `tweak-ui`'s decoder does not handle it) so hardware/footswitch bypass changes reach the page.
- **Snapshot switch** (from the device): the page must show the new snapshot's values. One coalesced `read_edit_buffer()` is acceptable; rebuilding from cached per-snapshot data with no I/O (as `tweak-ui` does for effect blocks) is an optimization the builder may take if it covers all block types.
- **Connection loss** is a visible state on the page; controls are disabled or clearly marked while disconnected; on reconnect the server re-reads and pushes fresh structure.
- **Write failure** is reported to the page and shown on the affected control; the control reverts to the device's last known value.

## Acceptance criteria

- Open → chain rendered: ≤ 2 s on the LAN.
- Server-side param write: median ≤ 25 ms; no code path where writes queue unboundedly.
- During a continuous 3-second drag the sound follows the drag; ≤ 100 ms after release the device holds the final value.
- A hardware knob turn or footswitch bypass shows on the page ≤ 250 ms; a preset switch re-renders ≤ 1 s.
- Every block the device reports (except "None" endpoints) appears, in the right lane, for: a serial preset, a split/join preset, a preset with an unjoined split (USB tap), a two-DSP-path preset with a mic path.
- Undo/redo behaves as in *Decisions* 7, verified by test: one entry per drag; undo writes the pre-drag value to the device.
- Unit tests run with no device (fake client + fake subscriber). `tests/test_cli_parity.py` covers the new verb's `--help`.

## Hardware validation (needs Michael and the Stadium XL — do these early, they can change the design)

1. **Where does a write land with respect to snapshots?** `/ParamValueSet` carries a trailing `-1`. For (a) a param that varies per snapshot and (b) one that does not: tweak it in snapshot 2, switch to 1, switch back — what does each snapshot hold? Same question for `/BlockEnableSet`. The expectation is "exactly what turning the knob on the hardware does"; if the device behaves otherwise, *Decisions* 7's history rule and the unsaved indicator need revisiting.
2. **Does `/SavePresetWithCID` persist everything written live** — float, int, bool params; input/output/split/merge params; bypass states — verified by reloading the preset. What is the right `block_count` argument (existing callers pass the default)?
3. **Int and bool params written as floats** land correctly (protocol doc says yes; confirm on a toggle and a list param), and a dropdown index equals the raw value for `enum_labels`.
4. **Echo behavior:** do our own writes come back on the 2001 stream, how fast, and does the `origin` field distinguish them from hardware-originated changes?
5. **Feel:** Michael drags knobs while playing — amp drive, a delay mix, a filter sweep — and confirms it tracks. (The spike passed this informally.)
6. **Split/merge params** audibly do what their controls say (balance/pan/level), since these have had no live-write exercise before.

## What is left to the builder

- Package layout and names inside core; the public shape of the fast-write option on `HelixClient`; endpoint/payload design; the SSE delta format; echo-suppression mechanism.
- How lanes are computed from the edit buffer, reusing `untranscode`'s logic (extract a shared helper if that is cleaner than importing from it).
- The page: rendering, the knob control (pointer + touch + keyboard-accessible stepping), connectors, visual design within the approved layout.
- Undo stack limits; exact shortcut handling across macOS/Windows/Linux browsers.
- Test design within core's conventions; which hardware checks become permanent `tests/live` cases (following that suite's `HGTEST` safety model).
- The `device` skill wording.
- Release mechanics: fetch before choosing version numbers (expected core 0.60.0, plugin 5.10.0 if nothing else lands first).

## Questions for Michael

1. **Should Save also update the library?** Device-only save leaves the library's `.hsp` stale — and `device copy` upserts by name, so a later copy of that tone from the library would overwrite the tweaks on the device. Options: (a) Save = device save, then pull the saved preset back into the library file of the same name via the existing `to-hsp` path (one button; relies on round-trip fidelity; the library is git-tracked so it is recoverable); (b) device-only Save plus a separate "update library" button; (c) device-only in v1, library sync stays a manual `device to-hsp`, with the future drift report (`hgc-wv1`) as the safety net.
2. **Intent dials stay parked** on `tweak-ui`, untouched by this work — agreed?
3. **Snapshot buttons on the page** (switch snapshot from the browser, not only from the footswitch) — in v1 or later? It is cheap (`activate_snapshot` exists) but is the first step past "tweak and bypass only".

## Revision 2026-11-12 — after the builder check and the first hardware probes

An independent "builder" read of this document, checked against the code and
then against the hardware, changed the following. Where this section disagrees
with the text above, this section is what was built.

**Questions for Michael — settled by the preapproval, as the stated defaults:**
Save is device-only with a seam for a later library write-back (Q1); intent
dials stay parked (Q2); no snapshot buttons on the page in v1 (Q3).

**Decision 3 (locking) is replaced.** Holding `editbuffer` for the server's
lifetime would lock the agent that launched the page out of `device load`,
`normalize` and every other live-ops verb (they wait 30 s, then fail). The
server now takes the lease **on demand**: at the first write, released ~2 s
after the last one, re-taken as needed, and it **fails fast** (no waiting) when
another process holds the device — the page shows who. Save takes
`editbuffer` + `library` for the moment it runs. `--no-lock` opts out. The verb
stops on Ctrl-C / SIGTERM.

**"Every parameter" means every param of each block's first model.** A dual
cab's second model (`mdls[1]`) and harness params (Trails, some dynamics
routing) have no known live-write address — `/ParamValueSet` carries a fixed
`0` in the position that might select them, unproven. They are not shown.
Follow-up: `hgc-5gh`.

**Layout: `bblk` is an instance id, resolved through the flow's `bmap`** (it
only equals the grid slot when `bmap` is the identity, as it was in the
spike). Lane B of a split is the row-1 blocks from the split's resolved
pointer to the join's. A block whose pointer names the **other** DSP path
(`bflw`) — the cross-DSP tap seen on White Limo — does not open a lane: each
path stays its own section and the block carries a "⇄ path N" tag. The
engine's existing lane code works on `.hsp` shapes and drops blocks with no
helixgen model, so the derivation was written fresh in `liveedit/chain.py`
rather than imported.

**The split "type" is not a control.** Y / A-B / Crossover / Dynamic are four
different *models*; changing one is a model swap (a non-goal). The split node
shows its model name and its own params (balance etc.).

**Save needs a guard the original text did not have.** It re-reads the active
preset at save time and refuses unless that preset is in the user pool
(`ccid == -2`); a factory preset or an unresolvable id gets an error pointing
at `device save`. A public `HelixClient.save_edit_buffer(cid)` was added
(the raw op was private).

**Echo handling (Decision 5) is by request id, not by time.** Hardware probe:
an echo's `seq` equals the request id of the write that caused it. The client
now exposes `last_request_id`; the session remembers its recent writes and
drops their echoes, so a late echo of an older value cannot drag a control
backwards. The page additionally tags its writes with a per-tab id so it can
ignore the server's rebroadcast of its own change.

**`/BlockEnableSet` does ack.** The code comment saying live-ops commands
reply only on 2001 predates fw 1.4; the hardware answers with `/status` in
~13 ms, so the fast-ack path applies to bypass too. Its 2001 echo layout
(`/setBlockEnable [origin, seq, path, grid_slot, enable]`) was captured and is
now written down in `docs/helix-protocol.md` — it was previously documented
only in a memory note.

**Validation item 3 was wrong as worded:** a list's label index is
`value − min`, not the raw value (many enums start at 1). Built accordingly.

**Events the page does not model** (`/setModelWithMID`,
`/setSnapshotBypassState`, `/setBatchedParamVals`) trigger one coalesced
re-read instead.

## Revision 2026-11-13 — hardware validation and adversarial review

Run on the Stadium XL (fw 1.4.1) against a throwaway copy of a real two-path
preset, deleted afterwards. Results against *Hardware validation* above:

1. **Snapshots — as hoped.** A write to a snapshot-assigned param lands in the
   active snapshot only; the other snapshots keep their values and the edit is
   still there after switching away and back. A param that is not
   snapshot-assigned changes everywhere. Same for bypass. Exactly what the
   hardware knob does, so Decision 7's history rule stands.
2. **Save in place works** (`/SavePresetWithCID` on the active preset's cid),
   verified by loading another preset and returning. `block_count` 0 is fine.
3. **Int and bool params were broken — in the engine, not just here.** The
   device silently drops an int/enum param sent as a float, and a bool sent as
   anything but the OSC `T`/`F` tags. `set_param` had always sent floats, so
   `device set-param` could never set a list or a switch either. Fixed in the
   client (typed encoding from the model defs), the OSC codec (`T`/`F`) and the
   2001 subscriber (bool events decoded as bools, not `None`).
4. **Echoes:** confirmed, `seq` == our request id; own echoes are dropped.
5. **Feel:** median 9 ms per write through the session; a foreign param change
   reaches the session in ~15–120 ms, a bypass in ~10–30 ms, a preset load in
   under a second with no re-read. A full re-read of this (large) tone takes
   ~1.5 s, so a snapshot switch refreshes the page in ~1.5 s — over the 1 s
   hoped for; decoding `/setBatchedParamVals` in place would remove that read
   (filed as a follow-up). Michael's own ear test of the shipped page is still
   to come.
6. Split/merge params: written and read back; not ear-checked.

Also learned: a re-read **does** reflect live bypass and param state on fw 1.4
(the older "saved state until you save" note is fw ≤1.3); the unsaved flag is
the `volatile.preset.edited` property — the buffer's `hist` field stays set
after a save — and that is what the page's indicator now follows.

**From the adversarial review of the page** (all reproduced with a fake-DOM
harness, now kept as a regression test): a write overlapping a re-render could
leave the page showing a value the device did not have — every write now
carries the structure revision and the server refuses a stale one; a
"disconnected" page was still writable by keyboard; drags were not bound to
their pointer; a plain click wrote to the device and left a phantom undo
step; Shift pressed mid-drag made the value jump; history survived a model
swap. All fixed.

**From the adversarial review of the Python side** (nothing above medium at
the reviewed head; each reproduced by script, each fixed with a test): value
events that preceded a re-read in the same batch were replayed on top of it;
echo and ack could be processed in an order that left the session disagreeing
with the device (echo handling now follows the stream's own order, and events
for a control are held while a write to it is on the wire); a preset pushed
while a write was in flight got that write's value committed into the new
tone; a read overtaken by a pushed buffer could put the old preset back; the
write lease ignored the lock-token session check and could be dropped under a
slow write; request bodies were read before the origin guards. Twelve
surviving mutants each got a test, plus a multi-threaded stress test. The
same review found that a "re-read" was four round-trips each paying a 0.4 s
settle — a snapshot switch now costs one fast buffer read (~0.5 s measured on
the XL, down from ~2 s).

**Still open after this build:** an ear test by Michael; the dual cab's second
model and harness params (`hgc-5gh`); applying a snapshot recall's value batch
in place instead of re-reading (`hgc-9qd`); a stream gap shorter than the
6-second silence threshold is not detected (the 2001 frame header carries a
sequence number that could be used).

**Found by the review of the plugin skill, and fixed in the engine before
release:** a tone loaded *from a setlist* is active under its setlist
reference, not its pool preset (checked on the XL), so the pool-only Save
guard would have refused nearly everything Michael loads. Save now resolves
the reference to the pool preset behind it — verified on throwaway objects
that this is what persists. The same review showed an agent had no way to
tell whether the edit buffer held unsaved work, or which preset to pull back:
`device active` now reports `edited` and `pool_cid`, and the skill is written
around them (heard is not saved; load discards; `to-hsp` reads the stored
preset; pull the device's version back into the library as soon as the user
has saved).

**Release note — 0.60.0 was published broken for this feature.** The wheel
did not contain `liveedit/page.html` (package-data was never updated for the
new package; the suite was green because tests import from the source tree).
Caught by installing the published package into a throwaway environment
before the plugin was released; fixed in 0.60.1 with a packaging test that
fails if any non-Python file under the package is not declared, and verified
by running the *built wheel* against the hardware. The plugin pins 0.60.1.

## Reference

- Spike: `docs/superpowers/specs/assets/live-chain-editor/chain_spike.py`
- Layout mockup: `docs/superpowers/specs/assets/live-chain-editor/layout-mockup-splits.html`
- Prior design this departs from: `docs/superpowers/specs/2026-10-27-tone-tweaker-ui-design.md`
- Core: branch `tweak-ui` (worktree `~/git/helixgen-core/.worktrees/tweak-ui`), commits `4583a1a`, `bff9684`, `113ddff`, `d8e504d`
- Deferred: `hgc-wv1` (device-vs-library drift report), `hgc-nci` (adjective search → knob highlight)
