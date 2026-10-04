# Factory preset corpus — 16 Line 6 Stadium factory bass presets

What Line 6's own preset designers actually do, measured from the
Stadium's factory setlist. Engine: `helixgen, version 0.52.1`.

## How to read a row — this matters more than the numbers

**`at_default` is half the answer.** Each row counts every instance of the
param, including the ones nobody touched. A median over that pool describes
no real preset: cab `HighCut` pools cabs left wide open at the model default
with cabs deliberately cut, so the pooled median can say nothing about
which choice a designer made. So each row also carries:

- **`at_default`** — how many of the `n` instances sit on the model's own
  default. High `at_default` means the factory answer is *leave it alone*.
- **`moved`** — the distribution over the instances a designer actually
  changed. **This is the design signal.** Use it when you have decided to
  set the param at all.
- **`enabled_only`** — for effect blocks, the distribution over instances
  that are ON in the preset's base state. Most factory drive and delay
  blocks are bypassed at load (engaged by snapshot or footswitch), and
  their values differ by ~20% from the bypassed ones.

Integer and switch params report **mode + frequencies**, never a median —
a median mic index is meaningless and a fractional one is unsettable.
Quartiles are omitted below n=8.

A category row appears only where every contributing model declares the
same type and range; the rest are listed as suppressed, because the same
param name carries different units in different models (reverb `Decay` is
a 0..1 knob on HD2 models and SECONDS on VIC ones). Per-model numbers for
those live in `data/factory-corpus.json` under `by_model`.

**Known gaps.** Rows are BASE values — snapshot
arrays are ignored here, and `amp Drive` alone is snapshot-modulated on 20 of
45 amp instances in the guitar set, so a single number can be one end of a designed range.
Infrastructure blocks (inputs, outputs, splits, joins, looper) are excluded.

**Amp model family:** Agoura 16 vs legacy 10 amp instances.

**Blocks per preset:** median 15 (min 8, max 18)

**Named snapshots per preset:** median 4.5 (min 4, max 8)

## amp

| param | n | at default | median (all) | median (moved) | moved p25-p75 | min..max |
|---|---|---|---|---|---|---|
| Drive | 15 | 1 | 0.45 | 0.445 | 0.4025-0.56 | 0.28..0.88 |
| Master | 25 | 13 | 1 | 0.85 | 0.8475-0.892375 | 0.55..1 |
| Level | 15 | 3 | -10 | -10.55 | -16.775--3.75 | -22..2.7 |
| Hype | 16 | 12 | 0 | 0.35 | - | 0..1 |
| Sag | 15 | 12 | 0 | -0.86 | - | -1..0 |
| ZPrePost | 12 | 9 | 0.5 | 0.328 | - | 0..1 |
| Bass | 17 | 12 | 0.55 | 0.577413 | - | 0.5..0.7 |
| Mid | 11 | 6 | 0.5 | 0.35 | - | 0.31..0.73 |
| Treble | 17 | 7 | 0.55 | 0.605 | 0.497875-0.65 | 0.3..0.764525 |
| Presence | 2 | 0 | 0.48 | 0.48 | - | 0.27..0.69 |

Suppressed in amp (unit mixture — see `by_model`): `Channel`

## cab

| param | n | at default | median (all) | median (moved) | moved p25-p75 | min..max |
|---|---|---|---|---|---|---|
| Distance | 27 | 14 | 2.75 | 2 | 1-4 | 1..9 |
| Angle | 27 | 16 | 45 | 0 | 0-0 | 0..45 |
| Position | 27 | 17 | 0.35 | 0.4 | 0.4-0.58 | 0..0.75 |
| Mic | 27 | 16 | mode 6 | mode 10 | - | 1..11 |
| HighCut | 27 | 20 | 13800 | 8000 | - | 3700..20100 |
| LowCut | 27 | 24 | 19.9 | 54 | - | 19.9..69 |
| Level | 27 | 21 | 0 | 1.25 | - | -3..6 |
| Pan | 27 | 27 | 0.5 | - | - | 0.5..0.5 |

## drive

| param | n | at default | median (all) | median (moved) | moved p25-p75 | min..max |
|---|---|---|---|---|---|---|
| Gain | 6 | 2 | 0.42 | 0.415 | - | 0.25..0.65 |
| Level | 20 | 1 | 0.7 | 0.7 | 0.615-0.74 | 0.45..1 |
| Tone | 2 | 1 | 0.455 | 0.38 | - | 0.38..0.53 |

Blocks that are ON at load (the rest are engaged by a snapshot or footswitch):

| param | n on | median (on) |
|---|---|---|
| Gain | 1 | 0.42 |
| Level | 6 | 0.7 |
| Tone | 1 | 0.53 |

Suppressed in drive (unit mixture — see `by_model`): `Bass`, `Treble`

## delay

| param | n | at default | median (all) | median (moved) | moved p25-p75 | min..max |
|---|---|---|---|---|---|---|
| Mix | 2 | 1 | 0.61 | 0.72 | - | 0.5..0.72 |
| Feedback | 2 | 1 | 0.3325 | 0.29 | - | 0.29..0.375 |

Suppressed in delay (unit mixture — see `by_model`): `LowCut`, `Time`

## reverb

| param | n | at default | median (all) | median (moved) | moved p25-p75 | min..max |
|---|---|---|---|---|---|---|
| Mix | 2 | 1 | 0.71 | 0.92 | - | 0.5..0.92 |
| Decay | 1 | 1 | 1.2 | - | - | 1.2..1.2 |

Suppressed in reverb (unit mixture — see `by_model`): `PreDelay`

## dynamics

| param | n | at default | median (all) | median (moved) | moved p25-p75 | min..max |
|---|---|---|---|---|---|---|
| Mix | 31 | 11 | 0.71 | 0.7 | 0.7-0.7025 | 0.61..1 |

Blocks that are ON at load (the rest are engaged by a snapshot or footswitch):

| param | n on | median (on) |
|---|---|---|
| Mix | 30 | 0.71 |

Suppressed in dynamics (unit mixture — see `by_model`): `Attack`, `Gain`, `Level`, `Ratio`, `Release`, `Threshold`

