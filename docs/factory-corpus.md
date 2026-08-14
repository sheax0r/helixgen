# Factory preset corpus — 66 Line 6 Stadium factory presets

What Line 6's own preset designers actually do, measured from the
Stadium's factory setlist. Engine: `helixgen, version 0.45.0`.

## How to read a row — this matters more than the numbers

**`at_default` is half the answer.** Each row counts every instance of the
param, including the ones nobody touched. A median over that pool describes
no real preset: cab `HighCut` pools 29 cabs left wide open at 20100 with 13
deliberately cut to 8000, and the resulting median (11750) occurs **zero**
times in the corpus. So each row also carries:

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

**Known gaps.** `device to-hsp` drops the second model slot of every
two-slot cab block; 48 of those hold `NoCab` and lose nothing, but ~30 real
second cabs are missing (bead hgc-q38). Rows are BASE values — snapshot
arrays are ignored here, and `amp Drive` alone is snapshot-modulated on 21
of 60 amps, so a single number can be one end of a designed range.
Infrastructure blocks (inputs, outputs, splits, joins, looper) are excluded.

**Amp model family:** Agoura 69 vs legacy 22 amp instances.

**Blocks per preset:** median 11.5 (min 6, max 19)

**Named snapshots per preset:** median 5 (min 4, max 8)

## amp

| param | n | at default | median (all) | median (moved) | moved p25-p75 | min..max |
|---|---|---|---|---|---|---|
| Drive | 60 | 7 | 0.5 | 0.5 | 0.41-0.61 | 0.2..1 |
| Master | 83 | 41 | 0.9895 | 0.645 | 0.415-0.85 | 0.21..1 |
| MasterVol | 4 | 4 | 1 | - | - | 1..1 |
| Hype | 69 | 51 | 0 | 0.275 | 0.2075-0.385 | 0..1 |
| ZPrePost | 62 | 58 | 0.3 | 0.339 | - | 0..1 |
| Bass | 78 | 20 | 0.5 | 0.5 | 0.3525-0.6225 | 0.19..1 |
| Mid | 48 | 11 | 0.510528 | 0.53 | 0.43-0.63 | 0.28..1 |
| Treble | 75 | 20 | 0.6 | 0.62 | 0.495-0.69 | 0.3..1 |
| Presence | 35 | 7 | 0.55 | 0.595 | 0.465-0.72 | 0.02..1 |

Blocks that are ON at load (the rest are engaged by a snapshot or footswitch):

| param | n on | median (on) |
|---|---|---|
| Drive | 53 | 0.5 |
| Master | 76 | 0.92475 |
| Hype | 67 | 0 |
| ZPrePost | 61 | 0.3 |
| Bass | 71 | 0.5 |
| Mid | 42 | 0.510528 |
| Treble | 68 | 0.605 |
| Presence | 29 | 0.59 |

Suppressed in amp (unit mixture — see `by_model`): `Boost`, `Bright`, `Channel`, `Jack`, `Level`, `Ripple`, `Sag`

## cab

| param | n | at default | median (all) | median (moved) | moved p25-p75 | min..max |
|---|---|---|---|---|---|---|
| Distance | 78 | 43 | 1.75 | 3 | 1-3.875 | 1..9 |
| Angle | 78 | 60 | 0 | 0 | 0-0 | 0..45 |
| Position | 78 | 33 | 0.3 | 0.3 | 0.29-0.39 | 0..0.77 |
| Mic | 78 | 30 | mode 11 | mode 0 | - | 0..11 |
| HighCut | 78 | 51 | 11750 | 9100 | 8000-10000 | 3600..20100 |
| LowCut | 78 | 57 | 19.9 | 54 | 39-74 | 19..90 |
| Level | 78 | 58 | 0 | 6 | 1.75-6 | -5.2..6 |
| Pan | 78 | 67 | 0.5 | 0.35 | 0-1 | 0..1 |

## drive

| param | n | at default | median (all) | median (moved) | moved p25-p75 | min..max |
|---|---|---|---|---|---|---|
| Gain | 56 | 5 | 0.365 | 0.32 | 0.12-0.48 | 0..0.76 |
| Tone | 50 | 7 | 0.54 | 0.58 | 0.37-0.71 | 0.08..0.88 |

Blocks that are ON at load (the rest are engaged by a snapshot or footswitch):

| param | n on | median (on) |
|---|---|---|
| Gain | 21 | 0.3 |
| Tone | 20 | 0.525 |

Suppressed in drive (unit mixture — see `by_model`): `Attack`, `Bass`, `Bright`, `Clipping`, `Fuzz`, `Level`, `Treble`

## delay

| param | n | at default | median (all) | median (moved) | moved p25-p75 | min..max |
|---|---|---|---|---|---|---|
| Mix | 70 | 5 | 0.335 | 0.33 | 0.29-0.42 | 0.13..1 |
| Feedback | 70 | 6 | 0.375 | 0.39 | 0.29-0.5 | 0..0.77 |

Blocks that are ON at load (the rest are engaged by a snapshot or footswitch):

| param | n on | median (on) |
|---|---|---|
| Mix | 20 | 0.3605 |
| Feedback | 20 | 0.305 |

Suppressed in delay (unit mixture — see `by_model`): `Bass`, `LowCut`, `Mode`, `Pitch`, `Ramp`, `Speed`, `Time`, `Treble`

## reverb

| param | n | at default | median (all) | median (moved) | moved p25-p75 | min..max |
|---|---|---|---|---|---|---|
| Mix | 69 | 4 | 0.32 | 0.31 | 0.24-0.37 | 0.13..0.92 |

Blocks that are ON at load (the rest are engaged by a snapshot or footswitch):

| param | n on | median (on) |
|---|---|---|
| Mix | 48 | 0.285 |

Suppressed in reverb (unit mixture — see `by_model`): `Decay`, `HighCut`, `LowCut`, `PreDelay`

## dynamics

| param | n | at default | median (all) | median (moved) | moved p25-p75 | min..max |
|---|---|---|---|---|---|---|
| Mix | 58 | 17 | 0.7 | 0.7 | 0.61-0.7 | 0.3205..1 |

Blocks that are ON at load (the rest are engaged by a snapshot or footswitch):

| param | n on | median (on) |
|---|---|---|
| Mix | 57 | 0.7 |

Suppressed in dynamics (unit mixture — see `by_model`): `Attack`, `Decay`, `Gain`, `Level`, `Ratio`, `Release`, `Threshold`

