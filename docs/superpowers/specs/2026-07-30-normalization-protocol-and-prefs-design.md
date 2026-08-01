# Normalization protocol: make the skill and CLI understand it end to end

**Date:** 2026-07-30
**Status:** IMPLEMENTED — core 0.35.0 (PR #53) + plugin 4.9.0 (PR #19), 2026-07-31.
Amendments from implementation are marked inline. The whole-library scope remains
deferred behind `he-5pm`.
**Prior art:** `2026-07-29-loudness-calibration-loop-design.md` (the hardware validation that produced these findings)

## Problem

`device normalize` works, but the *protocol* around it lives only in a human's head. A
user has to know: what signal to feed the chain, how loud to feed it, what to anchor the
target to, and which physical connections are needed for which part. None of that is
captured, so every run is re-derived from scratch and the results aren't comparable
between sessions.

This spec makes the protocol explicit, persists the user's choices, and gives the skill
enough structure to run it without a human re-deriving the setup each time.

## The three connections (and which are actually required)

This is the most commonly confused part, so it is stated first.

| Link | Carries | Required for normalization |
|---|---|---|
| **LAN — WiFi or Ethernet** | Every `device` verb. mDNS `_stadiumserver._tcp` discovery, control port 2002, ZMQ/msgpack transport. **The loudness meters arrive over this link.** | **Always.** There is no USB control transport in helixgen. |
| **Analog audio out → 1/4" Inst 1** | A pre-recorded stimulus played from the computer into the instrument jack. | Only in `sample` mode. |
| **USB audio** | Recording the Stadium's processed output back to the computer (ch 1/2 = processed, ch 7 = DI tap). | **No.** Validation/analysis only — `device measure` never needs it. |

Two consequences worth writing into the skill, because both are natural wrong guesses:

- **USB cannot replace the LAN.** Measurement is network telemetry, not audio analysis.
- **USB is a poor substitute for the analog cable.** Feeding a loop over USB means
  repointing every preset's input block away from Inst 1, which is invasive *and* defeats
  `--source input`, whose gate reads the instrument-input meter.

## Protocol modes

The measurement always works the same way (network meters, playing-gated). What varies is
the stimulus. Three modes, in the order a user is likely to want them:

### 1. `play` — the user plays guitar

The shipped, field-proven path. `--source input`, player plays through the whole run,
~10 s per target. No extra cabling, no calibration step.

- **Pro:** nothing to set up; the stimulus is by definition realistic.
- **Con:** ~10 s of steady playing per target — 31 tones is 10+ minutes of continuous
  playing, and consistency across that span is on the human.

### 2. `sample` — a pre-recorded loop from the computer

Computer plays a fixed stimulus into Inst 1. Repeatable, unattended, and the same every
session — which is what makes runs comparable over time.

- **Pro:** identical signal every measurement; the run needs no human once calibrated.
- **Con:** needs an analog cable, and needs the **source-level calibration** below, which
  is the step that makes or breaks the result.

### 3. `looper` — on-device looper block

Already supported via `--source loop`. The jack is structurally silent while the looper
replays, so the gate switches to chain-out level, `gain_db` comes back null, and
`output_db` is the comparison number.

- **Pro:** no computer audio path at all.
- **Con:** requires recording the loop first; same calibration problem as `sample`.

## The calibration step (why `sample` and `looper` need it)

Measured on live hardware 2026-07-29, and this is the crux of the whole protocol:

- A **clean** chain tracks source level ~**1:1**.
- A **saturated** chain is nearly source-independent — measured **0.16 dB/dB** on a real
  high-gain preset (input rose 36.6 dB, output moved 6 dB).

So the *balance between clean and saturated tones* is a function of how hard the source
drives the chain. Pick the playback level arbitrarily and every derived trim is an
artifact of that arbitrary choice — the run is perfectly repeatable and consistently
wrong. Error in the clean-vs-saturated balance is roughly **0.84 × (level error)**.

**Calibrate against `input_db`, never `gain_db`.** `input_db` is the jack level itself:
chain-independent, monotonic in playback volume, works on any preset. `gain_db` on a clean
chain is precisely the quantity that does *not* move with source level, so nulling against
it "converges" instantly at any level.

**Procedure:**

1. User plays by hand; record `input_db` (one 20 s window is enough).
2. Play the stimulus; adjust computer volume until `input_db` is within ~1 dB of that.
3. Persist the resulting volume setting *and* the reference reading.

Session result for reference: guitar (ESP LTD EC-1000, active EMG) read `input_db −31.0`;
macOS output volume **53** produced `−30.72` — 0.28 dB off, one iteration, no hunting.

**The reference guitar matters.** Output varies widely across instruments (active EMG vs
P-90 is easily 10+ dB), so the profile must record *which* guitar the calibration was
taken with. Re-calibrating with a different guitar is a legitimate reason to re-run.

## Target selection

`--target-db` should be absolute, never the default anchor (which equalizes within one run
only and can drag a preset down to its quietest snapshot).

Anchor it to a **factory preset**, so the library sits at a level the device's own
designers chose. Measured factory totals (all factory presets carry output level 0.0 dB,
so total == chain gain):

| Factory tone | Category | Total dB |
|---|---|---|
| **Stadium Rock Rig** | reference | **17.51** |
| German Lead | lead | 19.17 |
| Modern Metal | rhythm | 17.77 |
| Quiet Time | clean | 15.54 |
| Jazzy Jazz | clean | 9.21 |

**Per-category targets were tested and rejected.** Lead-over-rhythm is only 1.4 dB, and the
two clean representatives disagree by 6.3 dB — no defensible clean offset exists from that
sample. Use one absolute target. Corroboration that 17.5 is sane: one already-normalized
tone in the library measured 17.69 total against a +17.9 output level.

**Reachability is a hard constraint.** The trim is the last stage, so a tone can only reach
`chain gain + 20` (the output-level cap). Tones below that are a **gain-staging problem
inside the chain**, not something the trim can fix — see "Escalation" below.

## Preferences

`~/.helixgen/preferences.json` already exists, is owned by the `setup` skill, and documents
its precedence rules (env > file > memory seed > default). Add one block:

```jsonc
{
  "normalization": {
    "mode": "sample",                      // play | sample | looper
    "target_db": 17.5,
    "target_source": {                     // how target_db was derived, for provenance
      "kind": "factory_preset",
      "name": "Stadium Rock Rig",
      "measured_total_db": 17.51,
      "measured_on": "2026-07-29"
    },
    "seconds": 10,                         // measurement window
    "tolerance_db": 1.0,
    "sample": {
      "path": "<plugin>/docs/superpowers/specs/assets/helix-cal-loop.wav",
      "loop_seconds": 5.00,
      "playback_cmd": "play -q {path} repeat 9999",
      "output_device": "External Headphones",
      "volume": 53
    },
    "calibration": {
      "reference_input_db": -31.0,
      "reference_guitar": "esp-ltd-ec-1000",
      "achieved_input_db": -30.72,
      "calibrated_on": "2026-07-29"
    }
  }
}
```

Keys are additive; nothing here changes existing behavior when the block is absent.

**Staleness.** A calibration is only valid while the physical rig is unchanged. Warn (don't
block) when the block is older than some threshold, or when the reference guitar differs
from `default_guitar`. Re-calibration is two measurements — cheap enough to offer freely.

## What to build

### CLI (helixgen_core)

1. **`device calibrate`** — runs the procedure above: prompt for by-hand playing, capture
   `input_db`, then loop {play stimulus, measure, adjust} until within tolerance, and write
   the `calibration` block. Needs a way to set playback volume (platform-specific; macOS via
   `osascript`) or, failing that, to *report* the required change and re-check.
2. **`device normalize` reads the prefs block for its defaults** — `--target-db`,
   `--seconds`, `--tolerance-db`, `--source` all fall back to the profile. Explicit flags
   still win.
3. **Stimulus playback owned by the CLI**, not the agent: start/stop the loop around the
   run so the agent isn't orchestrating background processes.
4. **Reachability preflight** — before writing anything, report every target whose
   `chain gain + 20 < target_db`, and say plainly that those need chain gain staging.
5. **A whole-library scope that isn't setlist-shaped** — see the blocking issue below.

### Skill (`device`)

The skill already carries the calibration rules (merged 2026-07-29). Add:

- A short decision tree: which mode, and what each one requires physically.
- The three-connections table above — it is the most common misunderstanding.
- The first-run flow: no `normalization` block → offer calibration → persist.
- The escalation path when a tone can't reach the target.

### Skill (`setup`)

Add `normalization.*` to the keys it owns, and scaffold the block on first run the same way
it scaffolds the rest of `preferences.json`.

## Escalation: tones that cannot reach the target

Found on 3 of 31 tones in the real library. The fix is **in-chain gain staging**, typically
the amp's channel volume, and it is dramatic — `ChVol` is far from linear in dB:

| Tone | Change | Chain gain |
|---|---|---|
| Warm Jazz Clean | `ChVol` 0.55 → 1.0 | **−26.01 → −1.32** (+24.7 dB) |
| Tool - Schism - EC-1000 | both amps' `ChVol` raised | **−15.62 → +1.69** (+17.3 dB) |
| Tom Petty | `ChVol` 0.63 → 0.70 | **−2.56 → +13.25** (+15.8 dB) |

Do **not** fix these by raising the output-level cap. The hardware does ignore the
documented +20 limit (`he-b9i`: a write of 25 delivered a faithful +5.00 dB), but boosting
a quiet chain ~40 dB at the output amplifies its noise floor by the same amount. Raising
`ChVol` produces real signal instead.

On dual-amp presets, raise both amps together to preserve their blend.

## Gotchas that must survive into the implementation

Each of these cost real debugging time this session:

- **`afplay` in a shell loop is not gapless** — ~0.8-0.9 s of process startup per
  invocation (measured 5.28 s for three 1.00 s files), turning a 5.00 s loop into a ~5.9 s
  jittering period. Use `play -q <file> repeat N` (sox), which loops inside one effects chain.
- **Negative values need the `--` sentinel**: `device set-param 0 13 2 -- -14`. Without it
  the CLI errors with `No such option '-14'`. A sweep that suppressed stderr silently
  measured the *unchanged* preset three times.
- ~~**`device measure` cannot verify a trim.** Every meter tap sits upstream of the output
  block's gain.~~ **Corrected 2026-07-30 (hc-daz, core PR #51):** the taps sit
  DOWNSTREAM — [MEASURED] Stadium XL fw 1.3.2, a −20 dB output-gain write moved the
  meter −20.04 dB. A re-measure DOES confirm a trim, once that trim has been synced to
  the device. The old inference is what made `normalize` add the output level on top of
  a `gain_db` that already contained it, double-counting every trim.
- **Set the Mac's output device explicitly.** The Stadium is itself a USB audio interface
  and often steals the system default output, so the stimulus leaves over USB and never
  reaches the jack — `measure` then reports "not enough playing" with no hint why.
- **Don't touch Global EQ.** USB has no Global EQ layer, so it cannot affect a USB capture,
  and writing it flat would overwrite the user's real tone settings. It is also write-only
  (no read-back), so it can never be restored from the device.
- **Verify what's actually loaded before trusting a measurement.** A silently failed
  `device load` produced a plausible-looking reading for the wrong preset.

## The calibration stimulus

`helix-cal-loop.wav`, committed at `docs/superpowers/specs/assets/helix-cal-loop.wav`:

- 10 guitar-DI notes E2→C5, 0.5 s each, **exactly 240000 samples = 5.00 s** at 48 kHz,
  24-bit mono, peak −3.00 dBFS.
- Built from the FreePats *FSBS Electric Guitar Direct* bank — raw unprocessed DI, **CC0 1.0
  public domain**, so it ships freely.
- Rebuildable byte-identically via `build-helix-cal-loop.sh` beside it.
- The exact 5.00 s cycle exists so measurement windows contain whole loop cycles; a window
  that cuts a cycle reports a phase-dependent number.

Ship it as the default stimulus. A user-supplied file is fine, but the profile should record
its loop length so window advice stays correct.

## Blocking issue

`normalize --setlist` and `sync` both key off **local manifest setlist membership**, and a
real library had 31 of 52 placed tones outside any setlist. There is also no in-place content
update verb (`push`/`save` both demand an empty slot). Tracked as **he-5pm**, which needs its
own brainstorming session on the library-vs-device identity model. A whole-library
normalization scope depends on resolving it.

Workaround that worked here: `device setlist create-local` + `sync-off` to build a
measurement-only grouping. Note that `device sync --all` *does* reconcile the pool for every
manifest tone (30 updated), so content updates were broader than setlist membership implied —
the gap is specifically in what `normalize --setlist` can iterate.

## Measurement backend: network meters vs USB capture

Added 2026-07-30 after `hc-daz` showed the meter-based path is built on a false premise.

Two ways to answer "how loud is this tone":

| | **Network meters** (`device measure`) | **USB capture** (`analyze-audio`) |
|---|---|---|
| Data | ~10 Hz point samples of meter cells | the actual audio |
| Units | a dB proxy | integrated **LUFS** (ITU-R BS.1770), plus peak/true-peak/crest/clipping |
| Tap position | **settled: DOWNSTREAM** (`hc-daz`, measured twice on fw 1.3.2) | unambiguous: it is the real output |
| Needs | LAN only | LAN **plus** a USB cable, `helixgen[analyze]` (numpy), a pinned capture device |
| Verifies a trim? | broken today (see `hc-daz`) | yes, trivially |

**Recommendation: support both, default to USB where available.** LUFS is a better answer to
"make these equally loud" than a meter proxy, and the capture path cannot be wrong about
where the tap sits — which is exactly the failure that cost this project a full run.

The channel map is known: **USB ch 1/2 = processed output, ch 7 = DI tap, ch 3-6 silent.**
`analyze-audio --record --input` exists but is marked EXPERIMENTAL and untested against
hardware; capturing with sox and analyzing the file is the proven path.

Add `normalization.measure_via: "meters" | "usb"` to the prefs block, with the capture device
name alongside it.

> **Amended 2026-07-31 (as shipped, core 0.35.0).** The value is
> `"meters" | "capture"`, not `"usb"` — it matches the `--measure-via` flag that
> already existed. `load_preferences` REJECTS an unknown value, so a profile
> copied from the paragraph above would break every helixgen command that reads
> preferences, not just normalize. The capture device name is a sibling key,
> `normalization.capture_input`.

**USB never replaces the LAN.** Control — loading presets, recalling snapshots — is network
only. There is no USB control transport.

## TUI integration

The deterministic path needs **no LLM**: measure, subtract, write the output level, sync. The
TUI should call the CLI directly for that, with an optional target value.

Judgment is only required at the escalation — when a tone cannot reach the target, choosing
*which* amp parameter to raise and by how much is tone-design work (and `ChVol` is wildly
non-linear: 0.55 → 1.0 was +24.7 dB on one amp). So:

- TUI runs the programmatic normalize itself.
- It surfaces the reachability preflight: every tone where `chain gain + cap < target`.
- For those, it offers an **explicit** escalation to Claude — never an implicit LLM call for
  what is otherwise a subtraction.

This also keeps the TUI usable with no Claude installation at all, which is the right default
for a tool whose main job is arithmetic.

## Blocking

- **`hc-daz` (P0)** — normalize oscillates because `total_db` double-counts the output level.
  Nothing here is worth building until the measurement math is correct; the protocol would
  faithfully automate a loop that does not converge.
- **`he-5pm`** — library-vs-device identity, for the whole-library scope.
