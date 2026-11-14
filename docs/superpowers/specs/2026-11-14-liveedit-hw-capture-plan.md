# Live chain editor — hardware capture/probe plan (2026-11-14)

Unblocks the two device-gated follow-ups left after the 0.61.0 / 5.11.0 ship:

- **hgc-5gh** — `device live` covers only each block's first model (`mdls[0]`). A dual cab's **second model** (`mdls[1]`, same pids as the first) and **harness params** (`hrns`: delay/reverb **Trails**, dynamics **ControlSource** — all flagged internal by paraminfo) have no known live-write address.
- **hgc-9qd (bypass half)** — the in-place snapshot path ships for params; a snapshot switch that flips a block **on/off** currently falls back to a full re-read because we don't know how recall signals per-snapshot bypass on the wire.

Owner-driven, on the Stadium **XL**. Model the capture format on the prior specs in this repo family: `helixgen-core docs/superpowers/specs/2026-07-14-parity-capture-plan.md` and `2026-07-14-parity-capture-findings.md`. Protocol references below cite `helixgen-core docs/helix-protocol.md`.

## 0. Setup (once)

1. **Back up the device first** — `helixgen device backup` (so any probe write is recoverable). Probes only touch the live edit buffer, never Save, but back up anyway.
2. Quiet the network: NordVPN kill switch OFF for Wi-Fi editing (see `env_nordvpn_blocks_usb_editing`).
3. **Capture tool = helixgen's own 2001 subscriber**, not frida, wherever the *device* broadcasts the answer. A ~15-line logger reusing `helixgen.device.subscribe.HelixSubscriber` that prints each decoded 2001 frame as `ts  seq  addr  args` is enough; run it in one terminal while you drive the hardware in the other. Frida on the Stadium app is the **fallback**, needed only for target B2 (outbound writes the device doesn't echo on 2001).
4. Ground truth that a write *landed* is a `/ParamValueGet` read-back or the meters — **never the echo alone** (`project_loudness_feedback_phase01`: echoes ≠ landing-proof).

---

## Target A — hgc-9qd: how a snapshot recall signals per-snapshot bypass (PASSIVE capture)

**Why it's safe/cheap:** we only need to see what the *device broadcasts* on 2001 when a snapshot recall toggles a block. helixgen already subscribes to 2001.

**Hypothesis.** Recall emits one of:
- `/setBlockEnable [cmd, dsp, grid_slot, enable]` per flipped block (the echo of `/BlockEnableSet`, `helix-protocol.md:443`) — if so, our existing `("bypass", …)` decode already sees it, and the ship-time conservative fix (re-read when a bypass action rides a snapshot poll) is already correct; the in-place upgrade is just "apply it instead of re-reading."
- `/assignSnapshotBypass` (seen cascading on model swap, `:430`) or `/setSnapshotBypassState [origin, seq, block, state]` (no `path` field) — then we need its exact block-addressing to apply in place.

**Procedure.**
1. Load a tone with ≥2 blocks and set snapshot 1 = block X ON, snapshot 2 = block X OFF (do this on the hardware or the Stadium app).
2. Start the 2001 logger.
3. Recall snapshot 1 → 2 → 1 on the hardware, pausing between.
4. In the log, isolate the frames that follow each `/activateSnapshot`. Record: the exact address that carries the bypass, its full arg layout, and **how the block is identified** (grid_slot + dsp like everything else, or an opaque `block` index with no path).

**Success criterion.** We can map the bypass message's block field to a `(path, grid_slot)` the page already addresses.

**Resulting code change (in `helixgen-core`, liveedit/session.py + events.py).**
- If it's `/setBlockEnable`: in the in-place snapshot path, apply the `("bypass", …)` action to the control instead of forcing the re-read — drop the conservative fallback for the bypass case.
- If it's `/setSnapshotBypassState`/`/assignSnapshotBypass`: add a decode for it to `events.py` keyed by the captured layout, then apply in place.
- Either way, keep the re-read fallback for anything still unrecognized.

---

## Target B — hgc-5gh: addressing `mdls[1]` and harness params

### B1 — second model of a dual cab (ACTIVE probe)

**Hypothesis (now well-grounded).** `/ParamValueSet` is `[reqid, path, grid_slot, 0, paramId, value, -1]` and that 4th `0` is "fixed in captures" (`:428`). `/ModelSet` already carries an explicit **`subpos`** field (`[cmd, dsp, grid_slot, subpos, modelId]`, `:430`). So the fixed `0` in `/ParamValueSet` is almost certainly **subpos** — model slot within the block. `mdls[1]` → `subpos = 1`.

**Procedure.**
1. Put a **dual-cab** block on the device (two mics/IRs, `mdls[0]` and `mdls[1]`, same pids).
2. Pick a param with an audible/readable effect on each model (e.g. each model's `Level` or a distinct cut).
3. Via helixgen's client, send `/ParamValueSet [reqid, path, grid_slot, **1**, paramId, value, -1]` (4th arg = **1**, everything else as for `mdls[0]`).
4. Read back with `/ParamValueGet` at `subpos` 0 and 1 (if `Get` takes the field) and confirm by ear/meters: did **`mdls[1]`** change while **`mdls[0]` stayed put**?
   - 4th=1 → mdls[1], 4th=0 → mdls[0]: **confirmed** — the address is `(path, grid_slot, subpos, paramId)`.
   - no effect / wrong model → the sub index lives elsewhere; capture a dual-cab param edit made in the Stadium app and read the field directly.

**Resulting code change.** Grow the liveedit state-model address from `(path, grid_slot, paramId)` to `(path, grid_slot, subpos, paramId)`; surface `mdls[1]`'s controls in the page (they already share pids with `mdls[0]`). Removes the ship-time `sub != 0` skip in the in-place path.

### B2 — harness params (Trails, ControlSource — internal)

**Hypothesis.** `hrns` params are flagged internal by paraminfo and may not be writable via `/ParamValueSet` at all; they may use a different verb.

**Procedure (passive first, frida fallback).**
1. Passive: start the 2001 logger, toggle delay/reverb **Trails** (and a dynamics **ControlSource**) in the Stadium app, and watch for any 2001 echo and its address/args.
2. If 2001 shows nothing usable, the write only exists on the app's outbound 2002 — **frida-hook the Stadium app's ZeroMQ send** (reuse the `2026-07-14-parity-capture` harness) and capture the exact verb + args for the Trails toggle.

**Success criterion.** A verb + arg layout that sets a named harness param, confirmed by read-back/ear.

**Resulting code change.** Add the harness-param write path to the client and expose those controls in the page; if they turn out to be truly non-live-writable, record that in `helix-protocol.md` and close B2 as device-limited.

---

## Order & effort

1. **A** (passive, ~15 min) — cheapest, and it tells us whether 9qd's bypass upgrade is trivial or needs a new decode.
2. **B1** (active probe, ~20 min) — one write + read-back confirms the sub index; high payoff (unlocks dual cabs).
3. **B2** (passive → frida) — do last; may end "device-limited."

Record findings in a dated `*-capture-findings.md` beside this plan and in `helix-protocol.md`; then the code changes land in `helixgen-core` (liveedit) as a normal worktree PR with adversarial review, and the plugin bumps its engine pin.
