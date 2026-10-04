# Factory preset corpus — 50 Line 6 Stadium factory guitar presets

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

**Known gaps.** Rows are BASE values — snapshot arrays are ignored here,
and `amp Drive` alone is snapshot-modulated on 20 of 45 amp instances
in the guitar set, so a single number can be one end of a designed range.
Infrastructure blocks (inputs, outputs, splits, joins, looper) are excluded.

**Amp model family:** Agoura 53 vs legacy 12 amp instances.

**Blocks per preset:** median 12 (min 7, max 21)

**Named snapshots per preset:** median 5 (min 4, max 8)

## amp

| param | n | at default | median (all) | median (moved) | moved p25-p75 | min..max |
|---|---|---|---|---|---|---|
| Drive | 45 | 6 | 0.5 | 0.53 | 0.46-0.64 | 0.2..1 |
| Master | 58 | 28 | 0.85 | 0.52 | 0.3625-0.6875 | 0.21..1 |
| MasterVol | 4 | 4 | 1 | - | - | 1..1 |
| Hype | 53 | 39 | 0 | 0.26 | 0.2075-0.3675 | 0..0.58 |
| ZPrePost | 50 | 49 | 0.3 | 0.35 | - | 0.3..1 |
| Bass | 61 | 8 | 0.5 | 0.5 | 0.35-0.6 | 0.19..1 |
| Mid | 37 | 5 | 0.53 | 0.54 | 0.445-0.6425 | 0.28..1 |
| Treble | 58 | 13 | 0.625 | 0.63 | 0.5-0.7 | 0.32..1 |
| Presence | 33 | 7 | 0.55 | 0.595 | 0.4775-0.76 | 0.02..1 |

Blocks that are ON at load (the rest are engaged by a snapshot or footswitch):

| param | n on | median (on) |
|---|---|---|
| Drive | 38 | 0.52 |
| Master | 51 | 0.79 |
| Hype | 51 | 0 |
| ZPrePost | 49 | 0.3 |
| Bass | 54 | 0.5 |
| Mid | 31 | 0.55 |
| Treble | 51 | 0.63 |
| Presence | 27 | 0.59 |

Suppressed in amp (unit mixture — see `by_model`): `Boost`, `Bright`, `Channel`, `Level`, `Ripple`, `Sag`

## cab

| param | n | at default | median (all) | median (moved) | moved p25-p75 | min..max |
|---|---|---|---|---|---|---|
| Distance | 81 | 42 | 1.25 | 3 | 1-3.5 | 1..7 |
| Angle | 81 | 71 | 0 | 0 | 0-0 | 0..45 |
| Position | 81 | 27 | 0.3 | 0.3 | 0.1925-0.31 | 0..0.77 |
| Mic | 81 | 20 | mode 0 | mode 5 | - | 0..11 |
| HighCut | 81 | 41 | 10000 | 9650 | 8275-10000 | 3600..20100 |
| LowCut | 81 | 47 | 31 | 50 | 36.75-71.75 | 19..99 |
| Level | 81 | 47 | 0 | 2.5 | -2.9-6 | -6.9..6 |
| Pan | 81 | 59 | 0.5 | 0.5 | 0-1 | 0..1 |

## drive

| param | n | at default | median (all) | median (moved) | moved p25-p75 | min..max |
|---|---|---|---|---|---|---|
| Gain | 50 | 3 | 0.33 | 0.32 | 0.119-0.46 | 0..0.76 |
| Tone | 48 | 6 | 0.5588 | 0.58 | 0.37-0.71 | 0.08..0.88 |

Blocks that are ON at load (the rest are engaged by a snapshot or footswitch):

| param | n on | median (on) |
|---|---|---|
| Gain | 20 | 0.25 |
| Tone | 19 | 0.52 |

Suppressed in drive (unit mixture — see `by_model`): `Bright`, `Clipping`, `Level`

## delay

| param | n | at default | median (all) | median (moved) | moved p25-p75 | min..max |
|---|---|---|---|---|---|---|
| Mix | 68 | 4 | 0.33 | 0.33 | 0.29-0.415725 | 0.13..1 |
| Feedback | 68 | 5 | 0.3775 | 0.39 | 0.295-0.5 | 0..0.77 |

Blocks that are ON at load (the rest are engaged by a snapshot or footswitch):

| param | n on | median (on) |
|---|---|---|
| Mix | 20 | 0.3605 |
| Feedback | 20 | 0.305 |

Suppressed in delay (unit mixture — see `by_model`): `Bass`, `LowCut`, `Mode`, `Pitch`, `Ramp`, `Speed`, `Time`, `Treble`

## reverb

| param | n | at default | median (all) | median (moved) | moved p25-p75 | min..max |
|---|---|---|---|---|---|---|
| Mix | 67 | 3 | 0.31 | 0.305 | 0.2375-0.37 | 0.13..0.59 |

Blocks that are ON at load (the rest are engaged by a snapshot or footswitch):

| param | n on | median (on) |
|---|---|---|
| Mix | 48 | 0.285 |

Suppressed in reverb (unit mixture — see `by_model`): `Decay`, `HighCut`, `LowCut`, `PreDelay`

## dynamics

| param | n | at default | median (all) | median (moved) | moved p25-p75 | min..max |
|---|---|---|---|---|---|---|
| Mix | 27 | 6 | 0.7 | 0.67 | 0.46-0.7 | 0.3205..1 |

Suppressed in dynamics (unit mixture — see `by_model`): `Attack`, `Decay`, `Level`, `Release`, `Threshold`

