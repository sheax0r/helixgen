# Factory preset corpus — 66 Line 6 Stadium factory presets

Measured from the device's own factory setlist. These are the
distributions the tone skill's defaults should sit inside.

**Provenance.** Harvested from a Helix Stadium XL (fw 1.3.2) with
`helixgen device backup --setlist factory` → `device to-hsp` → `view`, then
aggregated by `tools/harvest-factory-corpus.py`. Only *statistics* are stored
here — no factory preset content is redistributed. Regenerate with:

```bash
helixgen device backup --setlist factory --dir /tmp/factory
python3 tools/harvest-factory-corpus.py /tmp/factory /tmp/corpus
```

Machine-readable form, including per-model distributions, is
`data/factory-corpus.json`.

**How to read this.** A value outside a param's p25–p75 band is not wrong, but
it should be a deliberate choice the tone's write-up explains. A value outside
min–max is almost certainly a mistake — Line 6's own preset designers never went
there on 66 presets.

**These distributions are CONDITIONAL — read `n` carefully.** A preset only
stores a param that differs from the model's default, so a param appears here
only on the blocks where a designer *moved that knob*. Two consequences:

- `n` is "how many blocks they adjusted it on", not "how many blocks have it".
  A low `n` means the knob is usually left alone — which is itself a finding.
  `Hype` (n=17) is not unpopular; it is used **selectively**, and when used it
  lands around 0.23.
- The bands say *where they put a knob when they chose to move it*. They say
  nothing about the models' defaults. So "cab `HighCut` median 8000" means:
  on the minority of cabs where they reached for it at all, they cut to 8–10 kHz.
  A rule that cuts to 6500–7000 on **every** preset is wrong twice over — more
  often than they do, and further than they ever do.

**Amp model family:** {'Agoura': 69, 'legacy': 20}

**Blocks per preset:** {'n': 66, 'min': 6, 'p25': 9, 'median': 11.5, 'p75': 14, 'max': 19}

**Named snapshots per preset:** {'n': 66, 'min': 4, 'p25': 4, 'median': 5.0, 'p75': 8, 'max': 8}

## amp

| param | n | min | p25 | median | p75 | max |
|---|---|---|---|---|---|---|
| Drive | 32 | 0.21 | 0.41 | 0.5 | 0.59 | 0.88 |
| NormDrv | 5 | 0.11 | 0.14 | 0.32 | 0.44 | 0.61 |
| BrightDrv | 5 | 0.44 | 0.45 | 0.5 | 0.71 | 0.76 |
| Master | 43 | 0.33 | 0.57 | 0.85 | 1 | 1 |
| ChVol | 4 | 0.54 | 0.61 | 0.67 | 0.73 | 0.74 |
| Level | 46 | -22 | -11.6 | -9.9 | -6 | 2.22045e-15 |
| Hype | 17 | 0 | 0 | 0.23 | 0.33 | 0.58 |
| Channel | 10 | 0 | 1 | 1 | 4 | 4 |
| Sag | 13 | -0.66 | 0 | 0 | 0 | 0.58 |
| Ripple | 8 | 0 | 0 | 0 | 0 | 0 |
| Bias | 2 | 0.55 | 0.55 | 0.6 | 0.65 | 0.65 |
| BiasX | 1 | 0.5 | 0.5 | 0.5 | 0.5 | 0.5 |
| ZPrePost | 8 | 0.5 | 0.5 | 0.5 | 1 | 1 |
| Bass | 45 | 0.19 | 0.37 | 0.5 | 0.58 | 1 |
| Mid | 22 | 0.28 | 0.47 | 0.53 | 0.63 | 1 |
| Treble | 42 | 0.35 | 0.5 | 0.635 | 0.76 | 1 |
| Presence | 16 | 0.02 | 0.5 | 0.54 | 0.6 | 1 |

## cab

| param | n | min | p25 | median | p75 | max |
|---|---|---|---|---|---|---|
| Distance | 35 | 1 | 1 | 3 | 4 | 9 |
| Angle | 14 | 0 | 0 | 45 | 45 | 45 |
| Position | 48 | 0 | 0.23 | 0.305 | 0.4 | 0.77 |
| Mic | 42 | 0 | 1 | 5 | 9 | 11 |
| HighCut | 37 | 3600 | 8000 | 8000 | 10000 | 20100 |
| LowCut | 32 | 19 | 19.9 | 24.95 | 60 | 90 |
| Level | 39 | -5.2 | 0 | 0 | 2 | 6 |
| Pan | 12 | 0 | 0 | 0.425 | 1 | 1 |

## delay

| param | n | min | p25 | median | p75 | max |
|---|---|---|---|---|---|---|
| Mix | 42 | 0.13 | 0.26 | 0.335 | 0.42 | 1 |
| Feedback | 40 | 0 | 0.27 | 0.385 | 0.44 | 0.64 |
| Time | 29 | 0.035 | 0.145 | 0.357 | 0.5 | 1.17888 |

## reverb

| param | n | min | p25 | median | p75 | max |
|---|---|---|---|---|---|---|
| Mix | 33 | 0.13 | 0.27 | 0.32 | 0.37 | 0.43 |
| Decay | 20 | 0.33 | 0.6884 | 0.745 | 2.8 | 6.5 |
| PreDelay | 2 | 0.005 | 0.005 | 0.012 | 0.019 | 0.019 |

## drive

| param | n | min | p25 | median | p75 | max |
|---|---|---|---|---|---|---|
| Gain | 39 | 0 | 0.22 | 0.39 | 0.45 | 0.76 |
| Level | 66 | 0 | 0.6 | 0.69235 | 0.75 | 1 |
| Tone | 40 | 0.08 | 0.37 | 0.53 | 0.65 | 0.88 |

## dynamics

| param | n | min | p25 | median | p75 | max |
|---|---|---|---|---|---|---|
| Level | 49 | -12.6 | -3.3 | 0.75 | 2.5 | 17.3 |
| Threshold | 14 | -51.7 | -37.6 | -33.2 | -27 | 8 |
| Mix | 40 | 0.3205 | 0.67 | 0.7 | 0.7 | 1 |

