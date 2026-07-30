# Loudness normalization: calibration loop, trim validation, and the production run

**Beads:** he-77l (source questions), he-hp9 (skill edit), plus the implementation beads filed off this spec
**Date:** 2026-07-29
**Revision:** 2 — rewritten after adversarial review (three independent reviewers; findings folded in below)
**Status:** design approved, ready to implement

## Goal

Normalization is implemented, validated, merged, installed on this machine, and used to
level-match every tone in the local library — against a baseline taken from a factory
tone rather than an arbitrary anchor.

Getting there needs four things: a repeatable calibration signal, proof that the output
trim does what it claims, a baseline derived from factory tones, and a production run
with a restore point in front of it.

## What is already settled

From the shipped design (`device` SKILL.md Loudness section, `docs/CLI.md`,
`docs/helix-protocol.md`) — recorded so the hardware session does not re-litigate it:

- **`device normalize` already normalizes via the output block `level` only** — never amp
  channel volume, never in-chain block levels. "Normalize via the output slider only" is
  not a proposal to evaluate; it is what ships. Snapshot scope writes per-snapshot
  overrides, setlist scope writes a uniform whole-preset shift that preserves internal
  balance. **Scope note:** this is true of the *closed loop*. The `tone` skill deliberately
  says the opposite for *authoring* (`tone/SKILL.md:401-404`: normalize with the amp
  channel volume, because the meters tap upstream of `b13 gain`). Both are correct; they
  are different jobs.
- ~~**The trim is downstream of every meter tap.** `helix-protocol.md:499`: "Every tap sits
  upstream of the output block's `gain` (a landed −60 dB output-gain write moves no cell)."
  A confirming `device measure` cannot see a written trim. Verification must capture
  outside the Helix. That parenthetical is also proof the write *lands*.~~
  **RETRACTED 2026-07-30 (he-06i / core PR #51) — this premise was FALSE.** The taps sit
  **DOWNSTREAM** of the output gain: re-measured on Stadium XL fw 1.3.2, same preset and
  stimulus, only the output gain moved — `0 dB → gain_db +8.37`, `−20 dB → gain_db −11.11`
  (a −20 dB write moved the meter −20.04 dB). A confirming `device measure` **does** see a
  synced trim, and `device normalize` had been double-counting the output level (see
  hc-daz). The quoted claim was an inference presented as a measurement; it is corrected in
  `docs/helix-protocol.md` and in the `device`/`tone` skills.
- **Output `level` range is −120..+20 dB** (`recipe-reference.md:97`), so a `--target-db`
  above `chain gain + 20` is unreachable and the quietest chain sets a run's ceiling.
- **`output_db` above 0 dBFS is in-chain clipping**, upstream of the trim, unfixable by any
  level move. It is a gain-staging problem in the chain.

**Cut from this spec after review:** the planned "prove a negative trim cannot fix a clipped
chain" demo. It restates a settled claim and costs device time. The ceiling *behavior* test
survives, because "clamps vs errors vs distorts" is genuinely unknown.

## Answering he-77l's questions

**Which input works.** The 1/4" guitar jack, and the reason is structural, not preference:
`--source input` gates on the **instrument input** meter. Feed a return, aux or USB input
instead and that gate sees nothing — the same structural silence that forced `--source loop`
to exist in the first place. So the guitar jack is the only input where the default
measurement mode can work at all. **This also closes the "does input trim/pad differ per
input" sub-question: moot by construction, since no other input is a candidate.**

**Which signal.** A pre-recorded loop played from the Mac's headphone output into that jack,
with the guitar unplugged. Detailed below.

**Output-slider-only normalization.** Already shipped (above). What is genuinely open, and
what experiment B tests, is whether the trim moves the delivered level by exactly the dB it
claims across the usable range.

**Global EQ interaction** (he-77l's fourth drawback bullet, and hc-b19 item c). The Stadium
has **three independent Global EQs — 1/4" (`qtr`), XLR (`xlr`), Phones (`pho`), one per
output layer, each with its own level — and no USB layer** (`CLI.md:584`). They are
**write-only over the network**; there is no read-back. This matters less than it looks:
a Global EQ is a *constant per-output offset applied to every preset alike*, so it cancels
out of any **relative** level-matching, which is what normalization does. It shifts only
the absolute target. Therefore USB capture is a valid instrument for this work, and
per-output uniformity is **out of scope by argument, not by omission**. The one real
requirement is that Global EQ must not *change* mid-session — so it gets pinned in the rig.

## Calibration signal

`helix-cal-loop.wav` — 10 single notes, E2 through C5, 0.5 s each, concatenated to
**exactly 240000 samples = 5.00 s**. 48 kHz / 24-bit mono, peak −3.00 dBFS, RMS −15.2 dBFS,
crest 12.2 dB.

Assembled from the FreePats *FSBS Electric Guitar Direct* bank (CC0 1.0, raw unprocessed
guitar DI — no amp, no effects). The bank ships individual sampled notes, not riffs, so the
loop is built rather than found.

- **5.00 s exactly** so a 10 s or 20 s measurement window, and any capture window that is a
  multiple of 5 s, contains whole loop cycles. A window that cuts a cycle reports a
  misleading number, because the loop's own level contour lands differently every time.
- **Peak −3 dBFS** for intersample-peak margin through the OS resampler. Note the file's
  digital peak buys *no analog headroom* — the analog operating point is set entirely by the
  Mac volume notch and the input Pad, which are calibrated in experiment A.
- **Real guitar DI, not pink noise.** Amp, drive and compressor models respond to pick attack
  and decay in ways noise does not. Whether that actually changes the resulting trims is not
  tested here — explicitly deferred, not assumed.
- **CC0 and script-reproducible**, so it can be committed and regenerated.

### Build script

Source: `https://freepats.zenvoid.org/ElectricGuitar/FSBS-EGuitar/EGuitarFSBS-bridge-direct-SFZ+FLAC-20220911.7z`
(92 MB; macOS `tar -xf` reads 7z via libarchive — no p7zip needed). Verified: the source
notes are already 48 kHz / 24-bit / mono, but the flags are passed explicitly so the output
does not silently inherit a different source's format.

```bash
S=EGuitarFSBS-bridge-direct-SFZ+FLAC-20220911/samples
i=0
for n in E2_s1 A2_s2 C3_s2 D3_s3 E3_s3 G3_s4 B3_s5 E4_s6 G4_s6 C5_s6; do
  i=$((i+1))
  sox "$S/${n}_01.flac" -b 24 -r 48000 -c 1 "$(printf 'v2n%02d' $i).wav" \
      trim 0 0.5 fade 0.003 0.5 0.06
done
sox v2n01.wav v2n02.wav v2n03.wav v2n04.wav v2n05.wav \
    v2n06.wav v2n07.wav v2n08.wav v2n09.wav v2n10.wav \
    helix-cal-loop.wav gain -n -3

# assert the one property everything else depends on
[ "$(sox --i -s helix-cal-loop.wav)" = 240000 ] || { echo "NOT 5.00s — abort"; exit 1; }
```

`gain -n -3` normalizes the **concatenated** file to −3 dBFS peak. Per-note `gain` would
either fail to guarantee the peak (plain `gain -3` attenuates, it does not normalize) or
flatten the relative dynamics between notes (`gain -n` per note). Both were caught in review.

Playback, looped without gaps and without running out mid-session:

```bash
play -q helix-cal-loop.wav repeat 9999   # sox; ^C to stop
```

**Not `while :; do afplay …; done`.** Each `afplay` invocation costs ~0.8-0.9 s of
process startup — measured 5.28 s to play three 1.00 s files back to back. That turns
a 5.00 s loop into a ~5.9 s period jittering +/-0.3 s and destroys the exact-cycle
property the whole design rests on. sox's `repeat` runs inside one effects chain and is
genuinely gapless.

## Fixed rig

Recorded once per session, constant for every measurement in it. Changing any of these
invalidates comparison across runs.

| Item | Setting |
|---|---|
| Signal in | Mac headphone out → 1/4" guitar input. **Guitar unplugged.** USB is not an input path. |
| Mac output device | **Pinned to the headphone jack.** The Stadium is itself a USB audio interface and plugging it in often steals the system default output — the loop then leaves over USB, nothing reaches the jack, and `measure` reports "not enough playing" with no hint why. Volume pinned at the notch found in experiment A, no other audio on the machine |
| Mac input device | **Pinned to the Stadium.** `sox -d` grabs the system default input — on a laptop that is the built-in mic, which records plausible-looking garbage instead of erroring |
| Input block | `Pad` **engaged** and volume started low (a headphone out is ~1-2 Vrms into an input expecting ~100 mV; the `output_db > 0` check catches chain-out clipping, not a slammed input converter); `Trim` recorded; **impedance pinned to a fixed value, not Auto** — a real pickup is impedance-loaded, so `FirstBlock` auto-modes would make A3's by-hand reference itself preset-dependent |
| Global EQ | Flat/bypassed on all three layers, set explicitly via `device globaleq` (write-only — cannot be read back, so set it, never assume it) |
| Output block routing | Destination confirmed to include the USB pair being captured |
| Master volume knob | Position recorded, and the global setting for whether it controls USB out recorded |
| Capture | 48 kHz, 24-bit, from the Stadium over USB |
| Device lock | `helixgen device lock --scope all --label <bead-id>` held for the session |

**Why the input-device pin gets its own row:** it is the highest-probability silent-garbage
failure in the entire plan. Mitigation is one check, below.

## Experiments

Prerequisite: `helixgen device discover` has run and the device answers. Pick one explicit
test preset with a **clean** chain (saturation compresses level differences and would
confound linearity) and record which one.

### A — rig bring-up and source calibration

**A1. Pin the capture path and prove it.** Capture 10 s. Then stop `afplay` and capture 10 s
again. The second capture must drop to the noise floor. If it does not, you are recording the
built-in mic and every number after this is fiction.

**A2. Noise floor.** With playback stopped, capture 10 s and record its RMS. It must sit at
least 40 dB below the quietest test capture. The Mac is connected to the Helix twice (analog
out + USB), which forms a ground loop through the chassis; run on battery and record that you
did.

**A3. Source level calibration — hc-b27's rule, and the step this spec previously got wrong.**
Do **not** pick the source level to make a meter look nice. hc-b27 proved on hardware
(2026-07-27) that source level *determines the clean-to-saturated spread*: a clean snapshot
tracks source level ~1:1 while a saturated one is nearly input-independent (~0.05 dB/dB).
Four runs of one preset gave deltas from −11.56 to −20.91 dB purely from source level. An
arbitrary source level yields a perfectly repeatable rig that produces trims which are an
artifact of that arbitrary choice.

So: measure with the player **playing normally by hand**, note **`input_db`**, then adjust
the Mac volume until the loop reads within **1 dB** of it. One or two measure-adjust
iterations. Record the final notch. This is what anchors everything downstream to real
playing.

**Null against `input_db`, not `gain_db`.** `gain_db` is median(out - in), and this spec's
own premise is that a clean chain tracks source level ~1:1 — which is exactly the statement
that `gain_db` does *not* move with source level on a clean chain. Nulling against it would
"converge" instantly at any arbitrary level, the precise failure A3 exists to prevent.
`input_db` is the jack level itself: chain-independent, works on any preset, and drops the
clean-snapshot prerequisite entirely.

```bash
helixgen device measure --source input --seconds 10 --json    # live playing, note input_db
# ... start the loop, adjust Mac volume, repeat until input_db is within 1 dB
```

Fallback if the gate never credits the loop: `--source loop`, which gates on chain-out level
instead — `gain_db` then comes back null and `output_db` is the comparison number. Note that
loop mode's documented premise is a *silent* jack, which is not this rig; here it would be
triggered by the pitch gate failing on the plucked notes, and loop mode has its own chain-out
floor, so it is not an unconditional escape hatch.

**A4. Capture-path repeatability — on the instrument experiment B actually uses.** The
previous revision measured repeatability with `device measure` (device meters, ~10 Hz
network telemetry) and then applied a *tighter* tolerance to a completely different
instrument (USB capture + RMS). Incoherent, and caught by two reviewers independently.

Three captures, 60 s each, nothing changed between them. Record the spread. **This number
defines experiment B's tolerance** — see below.

**A5. Headroom.** Set the output-block level so the baseline capture peaks at **≤ −21 dBFS**,
leaving room for the full +20 dB sweep without the capture clipping. This is a separate knob
from A3's source level: A3 sets what drives the chain, A5 sets where the output sits.

### B — trim linearity and headroom

**Actuator: live edit-buffer writes, not preset installs.** The previous revision used
`helixgen device install <preset.hsp>`, which is wrong three ways — the real signature is
`install <hsp> <name> --pos N` with `--pos` required, it authors a **new** preset into an
**empty** slot rather than updating the loaded one, and it leaves the active tone untouched.
Six iterations would have created six pool presets while every capture recorded the
unchanged original: four deltas of 0.00 dB, reading exactly like a real engine bug. The
`.hsp` write path is already covered by documented behavior; B tests the *actuator*.

```bash
helixgen device params 0 13          # discover the output block's pid — never guess pids
helixgen device set-param 0 13 <pid> <dB>
```

(`CLI.md:556` carries the live-proven example `device set-param 0 13 2 3.0` — output block at
grid slot 13, `gain` pid 2.)

**Measurement:** `helixgen analyze-audio cap.wav --json`. It returns RMS dBFS, peak dBFS,
true peak, crest, LUFS and a **clipping flag** directly — no manual `20*log10`, no brittle
grep against sox's column spacing. Capture with sox (pinned to the Stadium input) because
`analyze-audio --record` is marked EXPERIMENTAL and untested against hardware; validating
`--record --input` during a session that is already capturing is nearly free, so it gets a
results row of its own.

```bash
sox -c 1 -b 24 -r 48000 -d cap.wav trim 0 60    # format flags BEFORE -d, or they apply to the output
helixgen analyze-audio cap.wav --json
```

Capture 60 s, analyze the middle 55 s (= exactly 11 whole 5.00 s cycles). Playback and
capture are independent clock domains; at a typical ±100 ppm relative drift the accumulated
misalignment over 55 s is 5.5 ms, or 1.1×10⁻⁴ of the window. Against a 12 dB crest signal
that is a worst-case **0.007 dB** of error — two orders of magnitude of margin. Recorded here
so anyone changing the window length can re-check it rather than trusting the number.

**Per-capture validity gate.** Discard any capture whose `clipped` flag is true or whose peak
exceeds −0.5 dBFS. Without this, a clipped +12 dB reading gets recorded as a linearity
failure and filed as an engine bug — which is exactly what the first draft would have done,
since a 12 dB crest signal driven +12 dB from a −6 dBFS baseline clips hard and reads roughly
+8 to +10 dB instead of +12.

**Procedure.** From the A5 baseline, step the output-block level in +6 dB increments while the
capture peak stays under −0.5 dBFS, then in −6 dB decrements, measuring RMS at each. Expect
each measured delta to match its nominal step.

**Tolerance:** **3× the A4 spread, with a floor of 0.2 dB** — derived from the rig's own
measured precision instead of the arbitrary ±0.3 dB the first draft asserted. State the
computed value in the results table before running the sweep.

**Drift guard:** re-capture the baseline **last**, and require it within ±0.1 dB of the first.
One extra capture that catches every knob bump, thermal drift and accidental state change in
the whole session. Highest value-per-effort item in the review.

**Ceiling:** push the level toward +20 dB and record what happens at and beyond it. Note
which layer answers — the local schema validator caps at +20 (`recipe-reference.md:97`), so it
may well reject the write before hardware ever sees it. That is a valid finding, but say
which one it was.

**Abort criteria.** If A1 fails, stop — wrong input device. If A4's spread exceeds 0.5 dB,
stop — the rig is not repeatable. If the −20 dB confirmation write does not move the capture
audibly, stop — the capture is tapping something other than the output block's downstream
signal, and every subsequent delta would read 0.00 dB for the wrong reason.

### C — factory baselines and tone categories

Normalization needs an absolute target, not the default anchor (the first target that
measures ok), which equalizes only within one run's scope and can drag a preset down to its
quietest snapshot.

**Reference: the factory tone "Stadium Rock Rig."** Measure it, and let its total loudness
define the house level.

Categories are derived from the factory set rather than invented: pull the factory list off
the device (`helixgen device list --setlist factory --json`), pick representatives for
**clean**, **rhythm/crunch** and **lead/high-gain**, and measure each. If the factory set
itself places leads above rhythms and rhythms above cleans, adopt those measured offsets as
per-category targets; if the factory tones all sit within the tolerance of each other, use a
single target and record that the per-category idea was tested and rejected. Either outcome is
a result.

Then classify the 31 library tones into those categories — the library metadata already
carries tags, so classification is a metadata pass, not a listening exercise.

| Category | Factory representative | Measured total (dB) | Target offset |
|---|---|---|---|
| Reference | Stadium Rock Rig | | 0 |
| Clean | | | |
| Rhythm / crunch | | | |
| Lead / high gain | | | |

### D — production run

1. **Restore point first.** Commit and tag `~/.helixgen` (it is already a git repo) *before*
   any trim is written. This is what makes the whole run reversible.
2. Dry run `device normalize` across the library with the chosen `--target-db`, and read the
   report. Every target's measured chain gain is in it — confirm the target sits at or below
   the quietest chain's ceiling (`chain gain + 20`) before committing.
3. Apply with `--yes`. This writes local `.hsp` files only.
4. `device sync <setlist>` to push. **Warn first:** sync is a whole-managed-pool mirror. It
   re-pushes every manifest-known tone whose content hash differs — not only the normalized
   ones — and overwrites device-side edits that were never pulled back.
5. Re-run the dry run. In-band zero trims across the board confirm convergence. Do **not**
   re-run `device measure` expecting to see the trims; the taps are upstream of them.

Skipped targets warn and exit 1 — re-run for stragglers. A snapshot-scope `--yes` run with any
skipped target records no library metadata even though the ok targets' trims *are* written.

## Results

| Experiment | Measurement | Expected | Observed | Verdict |
|---|---|---|---|---|
| A1 | capture drops when playback stops | yes | | |
| A2 | noise floor vs quietest capture | ≥ 40 dB below | | |
| A3 | loop vs live-played clean snapshot | within 1 dB | | |
| A4 | 3-capture spread | ≤ 0.5 dB (defines B's tolerance) | | |
| A5 | baseline capture peak | ≤ −21 dBFS | | |
| B | delta per +6 dB step | nominal ± (3× A4) | | |
| B | delta per −6 dB step | nominal ± (3× A4) | | |
| B | behavior at the +20 dB cap | documented, with layer named | | |
| B | end-of-session baseline drift | ≤ 0.1 dB | | |
| B | `analyze-audio --record --input` | works / fails | | |
| C | Stadium Rock Rig total loudness | recorded | | |
| C | per-category offsets | adopted or rejected | | |
| D | post-run dry run | all in-band | | |

## Skill edit (he-hp9)

he-hp9 is **documentation-only and is not blocked on any of the above** — the first draft
coupled it to experiment B passing, which would have stranded content that needs writing
either way. Split by dependency:

**Landable now, no hardware:**
- The whole-cycle measurement rule: why a window that does not cover whole loop cycles
  reports a misleading number.
- hc-b27's source-level lore: source level determines the clean-to-saturated spread; a
  saturated chain is nearly input-independent (~0.05 dB/dB); calibrate the loop's playback
  level against a live-played clean snapshot to within ~1 dB. Not loop-specific —
  `--source input` has the same physics.
- The calibration-loop recipe: stimulus, 5.00 s cycle, rig table.

**Already present in the skill — do not duplicate:** hc-b19's session lore is largely
written up already (10 s windows suffice at `SKILL.md:704`; absolute `--target-db` because the
anchor drags to the quietest snapshot at `:708-713`; the +20 dB cap at `:714-716`;
`output_db` over 0 dBFS as unfixable in-chain clipping at `:720-724`). Neither he-hp9 nor the
first draft of this spec noticed. Only hc-b27's half plus the new rig recipe is outstanding.

**Needs experiment B:** whatever B establishes about trim accuracy and ceiling behavior.

## Out of scope

- Per-output uniformity across 1/4", XLR and phones — argued out above, not dropped silently.
- Unattended/automated normalization passes. The rig makes them possible later.
- USB 3/4 or 5/6 as a reamp input path — structurally incompatible with the `--source input`
  gate.
- Whether the stimulus must be guitar-realistic (loop vs noise vs live playing).
- Any engine change in `helixgen_core`. If B fails, that becomes a core bead, not a doc note.

## Device contention

Every hardware bead holds `helixgen device lock --scope all --label <bead-id>` for its
duration and releases it at the end. The device is a single physical resource and several of
these beads mutate the active tone. The bead dependency graph serializes them; the lock is
the backstop for anything run out of order.
