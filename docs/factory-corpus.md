# Factory preset corpus — 66 Line 6 Stadium factory presets

What Line 6's own preset designers actually do. These distributions are
the reference the tone skill's defaults should sit inside.

**Method.** Parsed from the `.hsp` directly, NOT from `helixgen view`.
Every param the model declares is counted, defaulted when the designer
left it alone — `view` omits any param equal to the model default, so a
projection-based corpus silently drops every knob the designer was happy
to leave alone (about half of all values) and reports only deliberate moves.
Aggregated by **model id**: display names collide (`Mono` and `Stereo` each
name six different models).

**A category row is published only where every contributing model declares
the same type and range.** The same param name carries different units in
different models — reverb `Decay` is a 0..1 knob on HD2 models and SECONDS
on VIC ones; amp `Level` is dB on Agoura amps and a 0..1 knob elsewhere.
Pooling those would produce a median no amp can take. Suppressed rows are
listed per category; use `data/factory-corpus.json` `by_model` for those.

**Quartiles are omitted below n=8** — at n=2 or 3 an IQR is just the data
points wearing a disguise.

**Amp model family:** {'Agoura': 69, 'legacy': 22} — Agoura is what the factory
presets are built on; the legacy HX models exist for preset compatibility.

**Blocks per preset:** median 11.5 (min 6, max 19, p25-p75 9-14, n=66)

**Named snapshots per preset:** median 5 (min 4, max 8, p25-p75 4-7.75, n=66)

**Known gaps.** `device to-hsp` drops the B-cab of every dual-cab block (78 occurrences here), so the cab rows are the A-mic half of the truth (bead
hgc-q38). Per-snapshot values are also partly dropped, so these are BASE
values. Infrastructure blocks (inputs, outputs, splits, joins, looper) are
excluded by design.

## amp

| param | n | min | p25 | median | p75 | max |
|---|---|---|---|---|---|---|
| Drive | 60 | 0.2 | 0.395 | 0.5 | 0.6 | 1 |
| Master | 83 | 0.21 | 0.575 | 0.9895 | 1 | 1 |
| Hype | 69 | 0 | 0 | 0 | 0.07 | 1 |
| ZPrePost | 62 | 0 | 0.3 | 0.3 | 0.77 | 1 |
| Bass | 78 | 0.19 | 0.375 | 0.5 | 0.595 | 1 |
| Mid | 48 | 0.28 | 0.43 | 0.510528 | 0.63 | 1 |
| Treble | 75 | 0.3 | 0.495 | 0.6 | 0.7 | 1 |
| Presence | 35 | 0.02 | 0.41 | 0.55 | 0.685 | 1 |

Suppressed in amp (unit mixture — see `by_model`): `AmpCabZUpdate`, `Boost`, `Bright`, `Channel`, `Level`, `Ripple`, `Sag`

## cab

| param | n | min | p25 | median | p75 | max |
|---|---|---|---|---|---|---|
| Distance | 78 | 1 | 1 | 1.75 | 3.5 | 9 |
| Position | 78 | 0 | 0.24 | 0.3 | 0.4 | 0.77 |
| HighCut | 78 | 3600 | 8000 | 11750 | 20100 | 20100 |
| LowCut | 78 | 19 | 19.9 | 19.9 | 60 | 90 |
| Level | 78 | -5.2 | 0 | 0 | 0 | 6 |
| Pan | 78 | 0 | 0.5 | 0.5 | 0.5 | 1 |

Categorical (an index or a switch — mode, not median):

| param | n | min | max | mode | most common |
|---|---|---|---|---|---|
| Angle | 78 | 0 | 45 | mode 0 | 0x57, 45x21 |
| Mic | 78 | 0 | 11 | mode 11 | 11x17, 0x14, 10x13 |

## drive

| param | n | min | p25 | median | p75 | max |
|---|---|---|---|---|---|---|
| Gain | 56 | 0 | 0.124725 | 0.365 | 0.46 | 0.76 |
| Tone | 50 | 0.08 | 0.3725 | 0.54 | 0.7 | 0.88 |

Suppressed in drive (unit mixture — see `by_model`): `Attack`, `Bass`, `Level`, `Treble`

## delay

| param | n | min | p25 | median | p75 | max |
|---|---|---|---|---|---|---|
| Mix | 70 | 0.13 | 0.29 | 0.335 | 0.42 | 1 |
| Feedback | 70 | 0 | 0.2925 | 0.375 | 0.486 | 0.77 |

Suppressed in delay (unit mixture — see `by_model`): `Bass`, `LowCut`, `Pitch`, `Ramp`, `Speed`, `Time`, `Treble`

## reverb

| param | n | min | p25 | median | p75 | max |
|---|---|---|---|---|---|---|
| Mix | 69 | 0.13 | 0.24 | 0.32 | 0.39 | 0.92 |

Suppressed in reverb (unit mixture — see `by_model`): `Decay`, `HighCut`, `LowCut`, `PreDelay`

## dynamics

| param | n | min | p25 | median | p75 | max |
|---|---|---|---|---|---|---|
| Mix | 58 | 0.3205 | 0.6775 | 0.7 | 1 | 1 |

Suppressed in dynamics (unit mixture — see `by_model`): `Attack`, `Decay`, `Gain`, `Level`, `Ratio`, `Release`, `Threshold`

