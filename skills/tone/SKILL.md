---
name: tone
description: Use when the user asks for a guitar/bass tone targeted at a specific artist, song, genre, or feel (e.g. "lead in White Limo by Foo Fighters", "warm jazz clean", "thrash rhythm"). Drives the helixgen CLI (provisioned by the `setup` skill as an isolated uv tool) to design and generate a Helix Stadium `.hsp` preset.
---

# Tone

## Overview

Turn a tone description into a `.hsp` Helix Stadium preset that's ready to load on the device. Drive the `helixgen` CLI: survey blocks, pick a chain, verify exact param names, build a recipe JSON, run `helixgen generate`, deliver the file.

## When to Use

- User describes a target tone (artist, song, section, genre, vibe)
- User wants a starting point to A/B against a reference
- User mentions a guitar/bass and a role (rhythm, lead, clean, pad, solo boost)

When NOT to use: editing an existing `.hsp` (surgical edits — `helixgen patch` / the single-op verbs — see **Adjusting an existing tone** below); ingesting new blocks (`helixgen ingest`); answering "what blocks do I have?" — just run `helixgen list-blocks` directly without the rest of the workflow; **putting an authored preset onto the physical Helix over the LAN, or syncing a library to the device** — that's the `device` skill (install / sync / backup), which picks up where this skill's saved `.hsp` leaves off. (Device-mutating verbs auto-acquire machine-local advisory locks as of core 0.22.0 — the `device` skill's "Device locks" section is the model; nothing in this skill touches the device.)

## Prerequisites

- The `helixgen` CLI is installed (the `setup` skill provisions it:
  `uv tool install 'helixgen[device]==0.45.0'` — isolated env, `helixgen`
  binary on PATH). If `helixgen --version` fails or prints a traceback, go
  run the setup skill's step 0 (a stale install may be shadowing the uv
  tool binary — invoke `"$(NO_COLOR=1 uv tool dir --bin)/helixgen"` by
  absolute path; `NO_COLOR=1` keeps uv from emitting ANSI codes inside the
  substitution under `FORCE_COLOR`, or use the plain
  `~/.local/bin/helixgen` fallback).
- **Every invocation that touches the block library needs `HELIXGEN_LIBRARY`**
  unless the user has their own populated `~/.helixgen/library/` or the env
  var is already set. Prefix each call with the plugin's bundled library:

  ```bash
  HELIXGEN_LIBRARY="${CLAUDE_PLUGIN_ROOT}/data/library" helixgen list-blocks --category amp
  ```

  (`${CLAUDE_PLUGIN_ROOT}` is expanded by Claude Code when this skill loads;
  if the literal token appears, the plugin root is the ancestor directory
  containing `.claude-plugin/plugin.json` — walk up from this skill's own
  directory. The prefix must be repeated on every Bash call — exports
  don't persist between calls. Resolution order and details: the `setup`
  skill's "Invoking helixgen" section.)
- **IR env vars, when they apply:** IR-touching verbs (`list-irs`,
  `register-irs`, `generate` with IR blocks) read `HELIXGEN_IRS="<dir>"` if
  the user has a custom IR directory on record (else `<library>/irs` — i.e.
  inside whatever `HELIXGEN_LIBRARY` points at, *not* `~/.helixgen/irs/`,
  which is the legacy pre-0.26 location core only reads to bridge an old
  `mapping.json`).
  Note the **IR-hash cache** lives separately at
  `~/.helixgen/cache/irhash.json` and is written by IR verbs **regardless of
  `HELIXGEN_IRS`** — since core 0.29.0 a fully isolated session just sets
  `$HELIXGEN_HOME` (the cache follows it); `HELIXGEN_IRHASH_CACHE` (single
  cache file) and `HELIXGEN_CACHE` (cache directory) remain finer-grained
  overrides, same prefix-per-call mechanism.
- The library must be populated. Verify quickly with
  `helixgen list-blocks --category amp` — an empty/`no blocks` result means
  the library env isn't reaching the CLI (or the library is empty); note the
  exit code is still 0, so read the output, and fix this before any tone
  work.

## The CLI surface

**Discover capabilities from the CLI itself, first:** run `helixgen --help`
(verb groups + the mental models), then the specific verb's `--help` — that
help text is the full behavioral contract (the role the old MCP tool
descriptions used to play). The verbs this skill drives:

| Verb | Use | Output |
|---|---|---|
| `helixgen list-blocks [--category <cat>] [--json]` | survey the library (categories: amp/cab/drive/delay/reverb/modulation/filter/eq/dynamics/pitch/volume/send) | text grouped by category, one `<display_name>  [<model_id>]` per line; `--json` = array of `{display_name, model_id, category}` |
| `helixgen show-block "<name-or-id>" [--json]` | exact param names/types/defaults/ranges for one block | text or `{display_name, model_id, category, aliases, params}` |
| `helixgen generate <recipe.json> [--artist A --song S \| --descriptor D] [--guitar G]` | author a tone into the library (default flow): writes `library/tones/<variant-slug>.hsp` + per-tone metadata JSON, keyed by identity + target guitar | writes the `.hsp` + metadata; warnings on stderr |
| `helixgen generate <recipe.json> -o <out.hsp>` | LEGACY ad-hoc output: writes there, auto-registers, naming flags IGNORED, no metadata JSON | writes the `.hsp`; warnings on stderr |
| `helixgen library doc <name> (--from-file <md> \| -) [--variant <guitar-slug>]` | author/update the tone's `description_md` (or a variant's `notes_md`) — replaces the old companion `.md` sidecar | updates metadata in place |
| `helixgen describe <tone>` | read a tone back: identity + variants table + `description_md` verbatim | text |
| `helixgen library show <name> [--json]` | compact/JSON tone- OR guitar-profile metadata (resolved as a TONE first — logical slug / metadata filename / variant preset_name — else a guitar profile by slug/name/short_name) | text or JSON |
| `helixgen list-irs [--json]` | locally registered user IRs | `<hash>  <wav-path>` lines; `--json` = array of `{hash, path}` |
| `helixgen patch <preset.hsp> <ops.json\|-> [--json]` | atomic batch of surgical edits, in place | warnings on stderr; `--json` = `{path, warnings}` |
| `helixgen view <preset.hsp>` | read-only recipe-shaped projection of a `.hsp` | JSON by default |
| `helixgen controllers [--json]` | assignable-controller vocabulary (FS/EXP) with English names + positions | text lines or JSON array |

## Workflow

### 1. Clarify only what's missing

Ask at most 3 short questions, and only the ones the request didn't already answer. Common gaps:

- **Guitar** (single-coil / humbucker / acoustic / bass; specific model if mentioned)
- **Role(s)** — single role (rhythm / lead / clean / pad / solo boost), or multiple. If multiple, **ask the family question** (see 1a below).
- **Reference specifics** (which section of a song; live vs studio version)

If the request implies an answer ("lead in X" → role known; "Strat" → single-coil known), skip that question.

#### 1a. Multi-part disambiguation (only when there are 2+ roles/sections)

When the user wants multiple parts of one song, multiple roles, or multiple sections, first pin down **how many distinct sounds** are actually in play. The unit is a distinct guitar **sound**, not a song section — a six-section song played on three tones is three parts, not six. Signals that mark a new part: a gain/saturation shift (clean → edge-of-breakup → crunch → high-gain — the most reliable boundary), a rhythm/lead role shift, an effect that switches on/off with the section (chorus on a clean verse, a bigger delay on the solo), or a channel/amp swap in the source rig. Merge any two candidate sections that would be reached by the same amp+cab with only knob/effect-bypass differences. If the true count still exceeds 8, keep the 8 the player actually needs and push the overflow to a separate preset.

Then ask one focused question:

> "Do these parts share an amp/cab family (e.g. all British crunch, just different gain/effects per part), or are they fundamentally different sounds (e.g. clean Fender for verse, high-gain Mesa for chorus)?"

Then pick the path:

| Answer | Approach |
|--------|----------|
| Same family | **One preset, multiple snapshots.** Pick a chain that fits all parts, vary gain/EQ/effect bypass per snapshot. (See 5.5.) |
| Different families | **One preset, layered amps + snapshot bypass — the default.** Place both amps (and both cabs, if different) in the chain; each snapshot enables one amp+cab pair and disables the other. Capped at 2 amp+cab pairs, 12 blocks/lane, 8 snapshots. (See 5.5.) |

Default to the **layered-snapshot preset** for "different sounds" — even when the user hasn't said they need instant mid-song switching — because it delivers every part in one file the player can recall live. Fall back to **multiple presets** (one `.hsp` per part, named `<song>-<part>`) only when the layered approach won't fit the budget: more than 2 amp+cab pairs needed, the lane would exceed 12 blocks, or you'd need more than 8 snapshots.

#### 1b. Research the reference sound — REQUIRED for artist/song/specific-gear targets

When the target is a named artist, song, section, or specific piece of gear, **do web research before sketching the chain** (step 2). Don't rely on model memory alone — signature tones often hinge on one non-obvious detail (a specific pedal, an octave generator, an unusual amp pairing, a studio trick) that memory gets wrong or omits, and getting it wrong wastes the whole generation.

Use `WebSearch` / `WebFetch` (or dispatch a research subagent for deep cases). Search for the rig and the *sound*, e.g. `"<artist> <song> guitar tone gear amp pedals"`. Extract and note:

- **Amps / cabs** actually used (model + which channel if known)
- **Pedals / effects** in the signal path — especially anything that defines the character (fuzz, octave/POG, Whammy, modulation)
- **Guitar / pickups** if it shapes the tone (single-coil vs humbucker, specific instrument)
- **Tonal adjectives** from how people describe it (bright/biting, woolly, scooped, saggy, etc.)
- **Signature technique** that's part of the sound (palm-muting, octave riffing, heavy vibrato)

State a one-line summary of what you found back to the user before committing to the chain, and **cite sources** (markdown links) so they can verify. Fold the findings into the chain sketch in step 2 and the IR/cab choice in step 3.

**Skip research only when** there's nothing specific to research — a generic vibe target ("warm jazz clean", "thrash rhythm" with no artist) — or the user already named the exact gear/chain they want. When skipping, it's because the target is generic, not because you "probably know it."

### 2. Sketch the chain in one line

Based on the reference AND the user's guitar, pick a slot shape. The guitar shapes choices upstream of EQ — e.g. a Strat into a Plexi needs less treble-pull at the amp than a Les Paul into the same Plexi.

State your call briefly so the user can redirect before you commit:

- Classic rock: light drive → plexi-style amp → 4x12 → tape echo → plate
- Modern metal: tube-screamer boost → high-gain amp → 4x12 V30 → noise gate front
- Clean: comp → clean amp (AC15/Twin/Deluxe-style) → 1x12 → optional chorus → plate/spring
- Lead: stack drive higher → less compression → longer delay → bigger verb
- Bass: comp → bass amp → 4x10/8x10 → optional drive parallel

### 3. Pick blocks from the library

For each slot, run `helixgen list-blocks --category <cat>` and scan the output for display names that read closest to the reference gear. Categories are amp / cab / drive / delay / reverb / modulation / filter / eq / dynamics / pitch / volume / send.

#### Amps: Agoura first — this is the single biggest choice in the preset

The Stadium ships **23 Agoura amps** (17 guitar, 6 bass). Everything else in the
amp category is the ported **HX/legacy** set, kept so presets from older Helix
hardware still load — Line 6 files them under `LEGACY` on the device itself.

**Pick an Agoura amp unless no Agoura model fits the reference.** Agoura is a
different engine, not a re-voice: component + behavioural modelling, real touch
response, and **SIC** — the cab's speaker-impedance curve feeds back into the
amp's power section (that's what `ZPrePost` and the `AmpCabZ*` / `AmpCabPeak*`
params on the amp block are). Legacy models get none of it, and they are why a
generated preset can feel flat and lifeless next to a factory one.

Line 6's own 66 factory presets use **69 Agoura amp instances to 22 legacy**
(`${CLAUDE_PLUGIN_ROOT}/docs/factory-corpus.md`). Tell them apart by model id — Agoura models are
`Agoura_Amp*`, legacy are `HD2_Amp*`/`HD2_Preamp*`:

```bash
HELIXGEN_LIBRARY="${CLAUDE_PLUGIN_ROOT}/data/library" helixgen list-blocks --category amp --json \
  | python3 -c 'import json,sys; [print(b["display_name"]) for b in json.load(sys.stdin) if b["model_id"].startswith("Agoura")]'
```

Common swaps: legacy `USDouble Nrm` → Agoura **`USDouble Black`** (Fender Twin);
legacy `Brit 2204`/`Brit Plexi Brt` → Agoura **`Brit 2203 MV`** / **`Brit Plexi`**.
Say in the report when you had to fall back to a legacy model, and why.

#### Cabs

- **Pick the mic deliberately, and know that ribbons are the factory habit.**
  Across the corpus, when Line 6 chooses a mic rather than leaving the default,
  the picks are `121 Ribbon` (15), `57 Dynamic` (11), `160 Ribbon` (11),
  `47 Cond FET` (7) — ribbons lead, and often sit on the second cab of a
  dual-cab pair. Angle is **0° on-axis on 87 of 108 cabs**.
- Mic, distance, position and the cut frequencies are all step-5 decisions now,
  and they have measured starting points — see the **cab voicing baseline**.

**Check for user IRs (preference-gated).** Run `helixgen list-irs --json`. If the result is non-empty, check whether the user prefers IRs over stock cabs: read `favor_irs` from `~/.helixgen/preferences.json` if that file exists; if the file or the key is absent, fall back to the existing feedback-memory check (a saved memory saying the user prefers IRs over stock cabs). When either source says yes, look for an IR that matches the chain's tonal target:

- Parse the wav filenames in the output — commercial IR packs encode cab + mic + position (e.g. `YA VX30 212 BLU Mix 01.wav` → Vox AC30-style 2x12 Blue, mix-position).
- If a match exists, use an IR block instead of a stock cab:
  ```json
  {"block": "With Pan", "ir": "YA VX30 212 BLU Mix 01.wav",
   "params": {"Mix": 1.0}}
  ```
- The cab voicing baseline (step 5) applies to the IR block too — but note an IR
  block's `Level` defaults to **−18 dB**, not 0, and its `HighCut`/`LowCut`
  default wide open. Leave the cuts alone unless the tone needs them.
- New users (no `favor_irs` preference and no feedback memory) get stock cabs by default. The preference flips on when the user explicitly says "from now on, prefer IRs when I have them" — record it in `~/.helixgen/preferences.json`'s `favor_irs` key if you can write there, otherwise as a feedback memory.

### 4. Get exact param names — REQUIRED step

For each chosen block, run `helixgen show-block "<display name>"`.

Skipping this is the #1 way to waste a generation cycle. Param names are case-sensitive (`Treble` vs `Tone`), tone-stack labels vary by amp, and the generator rejects unknown keys with a list of valid ones. If `helixgen generate` later errors with `Unknown param(s)`, the recovery (spelled out in `generate --help` too) is: `show-block` the offending block, fix the recipe, retry.

### 5. Build the recipe

Construct the recipe as a JSON dict and write it to a scratch file (e.g. `/tmp/<slug>.recipe.json`) — the recipe is **input-only** (never written back; the `.hsp` is the sole source of truth, no sidecar). The schema is the helixgen recipe format — full per-field reference (base shape + every optional section) in `docs/recipe-reference.md`.

Minimal shape:

```json
{
  "name": "Preset Display Name",
  "author": "...",
  "paths": [
    {
      "blocks": [
        {"block": "Compulsive Drive", "params": {"Gain": 0.45}},
        {"block": "Brit Plexi",       "params": {"NormDrv": 0.5, "Master": 1.0, "Level": -8.0}},
        {"block": "Mic Ir_4x12 Greenback 25 With Pan", "params": {}},
        {"block": "Tape Echo Stereo", "params": {"Mix": 0.33}},
        {"block": "Plate Stereo",     "params": {"Mix": 0.32}}
      ]
    }
  ]
}
```

#### Signal-flow params (input / output / split / merge) — use when the tone calls for them

The recipe also models the signal-flow layer (full field reference:
`docs/recipe-reference.md`). Reach for these when the tone needs them — don't add them
ritually:

- **Input noise gate** — for high-gain tones, prefer the input-block gate over
  spending a block slot: `"input": {"gate": {"threshold": -55.0}}` on the
  path. A `dynamics` Noise Gate block is still right when the gate must sit
  mid-chain (e.g. post-drive) or be footswitchable.
- **Input impedance / pad / trim** — only when the reference or the user's
  pickup setup calls for it (e.g. `"impedance": "230K"` to tame a fuzz the
  vintage way; `"pad": true` for hot active pickups):
  `"input": {"source": "inst1", "impedance": "230K"}`.
- **Output level/pan** — `"output": {"level": -3.0}` is a clean final trim of
  the whole path; `pan` for hard-panned dual-path tones. It is **not** the
  actuator for the *authoring-time* normalization pass (5.7) — it is the
  actuator `device normalize` owns, and a snapshot-scope run overwrites it.
  When the amp has no channel volume, that pass uses an end-of-chain volume
  block instead (see section 5.7). (The trim is **not** invisible to
  `device measure`: the meters tap DOWNSTREAM of the output gain — [MEASURED]
  Stadium XL fw 1.3.2, 2026-07-30; earlier revisions of this skill claimed the
  opposite.)
- **Split type + merge mixer** — a `split` entry requires a `type` (or raw
  `model`): `"y"` (plain even split), `"ab"` (footswitch/morph between
  branches), `"crossover"` (frequency split, e.g. bass bi-amping:
  `{"split": {"type": "crossover", "params": {"Frequency": 250.0}}}`), or
  `"dynamic"` (level-dependent routing). Balance the branches at the join:
  `{"join": {"params": {"B Level": -2.0}}}` — note the merge's master
  `"Level"` defaults to the device's +3 dB; set `"Level": 0.0` for unity.
- **Trails** — `"trails": true` is valid on delay, reverb, AND FX-Loop blocks.

After generating, tweak these without re-authoring via a `helixgen patch`
`set_param` op on the pseudo-blocks `input` / `output` / `split` / `join`
(e.g. `{"op": "set_param", "block": "input", "param": "threshold",
"value": -60.0}`).

#### Name the tone — identity flags, not the recipe title

The tone's identity and display name come from **`generate`'s naming flags**,
not from a hand-formatted recipe `"name"`. Name it one of two ways:

- **Song identity** — `--artist "<Artist>" --song "<Song>"` (paired). Display
  name is synthesized as `"$Artist - $Song - $Guitar"`.
- **Descriptor** — `--descriptor "<Descriptor>"` (mutually exclusive with
  `--artist`/`--song`). Display name is `"$Descriptor - $Guitar"`. With **no**
  naming flag at all, the recipe's bare `"name"` becomes the descriptor.

The **guitar segment** is the target guitar's profile `short_name` (resolved in
step 6, passed as `--guitar <label>`). The `.hsp` filename and metadata slugs
use the **same** schema, slugged lowercase-with-dashes — e.g.
`--artist "Foo Fighters" --song "White Limo" --guitar "Les Paul Jr"` yields
display `"Foo Fighters - White Limo - Les Paul Jr"` and file
`foo-fighters-white-limo-les-paul-jr.hsp`.

**Omit the guitar segment** (no `--guitar`) **only** when the tone is
explicitly *not* targeted at a specific guitar — a guitar-agnostic/generic
patch; the variant is then keyed `"generic"`. Note in the report and the
`description_md` that it's not guitar-specific.

**Logical tone vs variant.** One artist+song (or one descriptor) = one
**logical tone** = one metadata JSON at `library/tones/<logical-slug>.json`,
grouping one or more **variants** — each a real `.hsp` targeting a single
guitar, keyed by that guitar's profile slug (or `"generic"`). To add another
variant of an existing tone, re-run `generate --guitar <other-guitar>` against
the **same** artist/song/descriptor (see step 6's variant offer).

(Guitar resolution happens in step 6; build the recipe in step 5 without
worrying about the title — the naming flags stamp identity at `generate` time.)

#### Cab voicing baseline — measured, not folklore

**Read `${CLAUDE_PLUGIN_ROOT}/docs/factory-corpus.md` before you set a cab
param.** It is the measured distribution of what Line 6's own designers do
across the 66 factory presets, and it replaced a set of invented "anti-fizz"
numbers that were making every generated preset dark and dry.

Read its rows the way that file explains: **`at_default` first, then `moved`.**
A high `at_default` means the factory answer is *leave this knob alone* — and
for most cab params it is. `moved` is where to land IF you have decided to set
the param at all. A median over both together describes no real preset.

The failure mode this fixes is real but it is **not** fizz — it is a preset that
sounds muffled and lifeless next to a factory one. The old baseline cut the top
off at 6500–7000 Hz and the bottom at 80–100 Hz on *every* preset. Line 6 does
neither.

| Cab param | Factory practice (n=108 cabs) | What to do |
|---|---|---|
| `HighCut` | **61 of 108 left at the model default.** Of the 47 moved, median 9500 (p25–p75 8000–10000) | Default is the majority answer. If you do cut, 8000–10000 is the factory window — **6500–7000 is below anything they shipped** |
| `LowCut` | **71 of 108 left at default.** Of the 37 moved, median 50 (p25–p75 39–69) | Mostly untouched. When they do move it they land around 40–70, not 80–100 |
| `Distance` | 56 at default. Of the 52 moved, median 2.9" (p25–p75 1–3.6), max 9 | 1–3.5" is the working range. Close-micing is normal; distance is not a mud cure |
| `Position` | 44 at default — the most-adjusted cab param. Moved median 0.30 (p25–p75 0.24–0.39) | This is what they actually voice with. Toward 0 brighter, toward 1 darker |
| `Angle` | 87 at default. When moved, they move it **to 0°** | On-axis. Several cabs already default to 45°, so "try 45°" may be a no-op — `show-block` first |
| `Mic` | 36 at default. Deliberate picks: **`121 Ribbon` (15), `57 Dynamic` (11), `160 Ribbon` (11), `47 Cond FET` (7)** | Pick by label — `show-block` prints them. When Line 6 chooses a mic at all, a **ribbon** is the most common choice, and it often lives on the second cab of a dual-cab pair |
| `Level` | 68 at default (0 dB). Of the 40 moved, median +2.5 (p25–p75 −3…+6) | Leave at 0 on a single cab; it is the balance knob between the two halves of a dual cab. An **IR block defaults to −18 dB** — a different reference; don't compare the two |

Still true, and still worth doing:

- **Optional Parametric EQ** cutting 2–4 dB around 3–4 kHz (medium Q) if a
  specific tone has an ice-pick peak. This is a targeted fix for one preset —
  **not** a baseline move.
- **Where the tone is going matters, and the corpus can't see it.** These are
  base `.hsp` values with no knowledge of output destination. Into FRFR or
  studio monitors, a wide-open cab plus a near-1.0 master is the classic
  too-bright complaint — that is the case for a *targeted* `HighCut` (8000+) or
  a darker mic, decided by ear, not for restoring the old blanket rule.
- **Optional front-of-chain comp** (an LA-style studio comp — exact display name
  via `list-blocks --category dynamics`; ~1–2 dB of gain reduction, before the
  amp) for a polished, "produced" feel. Skip for raw dynamics.

**"It sounds fine while I play but harsh in the recording."** Not a patch bug.
Many interfaces (e.g. Focusrite 2i2) have a *direct monitor* feeding the pre-A/D
analog signal to your ears, which flatters the source; the recorded track is the
honest one. Judge by the recording. But fix it with a **targeted** move — a
narrow EQ cut, a different mic, `Angle` 45° — not by clamping `HighCut` down to
7 kHz, which trades harshness for mud.

#### Tuning heuristics — factory-measured starting points

Ranges below are the factory corpus's p25–p75 unless noted. A value outside
p25–p75 is allowed but should be a deliberate choice you can justify in the
write-up; a value outside the corpus min–max for that **same model** is almost
certainly a mistake (the envelope check in step 7b catches it).

| Knob | Range | Notes |
|------|-------|-------|
| Drive `Gain` | **0.12–0.48, median 0.32 when set** (almost always set: 5 of 56 at default) | Factory drives run LOW and push the amp. The ones actually ON at load sit at 0.30 — most factory drives are bypassed and engaged by a snapshot/footswitch |
| Drive `Gain` (pedal AS the distortion) | up to 0.76 | The top of the same distribution, not a separate factory practice — use when the pedal is the gain source |
| Amp `Drive` | **0.41–0.61** (median 0.50) | The most reliably-dialled amp param — only 7 of 60 sit at default. Far lower than you would guess; saturation comes from the power amp, not from piling on preamp gain |
| Amp power-amp volume | **41 of 83 sit at the model default** (usually 1.0). Of the 42 moved, median **0.645** (p25–p75 0.42–0.85) | The knob's NAME varies — `Master` on most, **`MasterVol` on `USDouble Black`**, `Output Volume` on `Who Watt 103`, absent on `Mandarin Rocker Mk 3`; `show-block` first or `generate` errors. Start from the model's own default rather than a fixed number: the factory habit is to leave it high, and when they move it they move it DOWN. The high-gain Agouras (`EVPanama`, `German Xtra`, `Revv`, `Solid 100`, `Agua 751`) sit at 0.36–0.55 |
| Amp channel volume | `ChVol` is 0..1; Agoura `Level` is **dB** | Also seen: `Ch Vol`, `Ch Level` (alongside a separate `Level`!), `Output`, `ODLevel`. See the level-units box below and read `show-block` every time |
| Amp `Hype` | **leave at 0** | 51 of 69 factory amps never touch it. The 18 that do sit at **0.21–0.39 (median 0.275)**. A seasoning, not a baseline |
| Amp `Sag` / `Ripple` | **−1..1 default 0 on Agoura; 0..1 default 0.5 on legacy** | Different scales entirely — the corpus suppresses this row for exactly that reason. On a legacy amp, 0 is not neutral, it is the extreme. `show-block` before writing |
| Amp `ZPrePost` | **58 of 62 at the model default** | Effectively never touched. Leave it unless research names a specific sag/feel behaviour |
| Cab params | see the voicing baseline above | |
| Delay `Mix` | **0.29–0.42** (median 0.33; set on 65 of 70) | Factory delays are much wetter than the old 0.10–0.20 guidance. ON-at-load delays sit slightly wetter still (0.36) |
| Delay `Feedback` | **0.29–0.50** (median 0.39 when set) | |
| Reverb `Mix` | **0.24–0.39** (median 0.32, max 0.92) | Factory reverb is wet. The old 0.08–0.15 was a third of real practice |
| Comp before amp (optional) | ~1–2 dB gain reduction | Polished feel; skip for raw dynamics |

**Level units — the bug this table exists to prevent.** Amps expose channel
volume under two different names *with two different units*:

- `ChVol` — a **0..1 knob** (legacy amps).
- `Level` — **decibels**, typically `-40..10`, default around `-10`
  (Agoura amps).

`show-block` prints the unit and range explicitly since engine 0.45.0
(`Level  float -40..10 dB (default -10)`). Writing `Level: 0.5` on an Agoura amp
is not "half volume" — it is **+10.5 dB over the model default**, and it clips.
Factory amps sit around −11 to −6 dB. Always read the unit off `show-block`
before writing a level.

Amp-EQ tweaks for the user's specific guitar (apply to whichever amp params actually exist — check `show-block` first):

| Guitar | Pickups | Typical adjustments |
|--------|---------|---------------------|
| Fender Strat / similar | bright SC | bump `Treble` to 0.65–0.75, `Presence` to 0.60–0.70; can run more amp gain (SCs compress less) |
| Fender Tele | bright SC, sharper | same as Strat but pull `Bass` to ~0.45 to avoid flubby low end |
| Gibson Les Paul / SG | warm HB | pull `Treble` to 0.55–0.60, `Presence` to 0.50–0.55; HBs already push the amp, back amp `Drive` off ~0.10 |
| Ibanez Prestige (RG/AZ/S) | hot HB, tight low-mids | as LP/SG but you can run `Treble` slightly higher (0.60–0.65); these excel at fast tight runs, keep `Mid` ~0.60 for cut |
| ES-335 / hollow / semi-hollow | warm HB, more body | pull `Bass` to ~0.45 to avoid boom; `Master` ~0.45 to control feedback |
| PRS / generic HB | balanced HB | midpoint of Strat and LP — start at amp defaults and adjust from ear |
| Bass guitar | varies | more `Bass`, less `Mid`; back `Master` off to keep cab tight |

### 5.5. Snapshots (when the user wants multiple scenes in one preset)

Stadium presets support 8 snapshots — named scenes that override block bypass and param values without leaving the preset. Use them when the user asks for "rhythm + lead", "verse + chorus + solo", "clean + crunch + lead", etc., or when 1a's part-count derivation turned up 2+ distinct sounds (same family or different).

**Keep the count lean.** Aim for the biggest **≤4** distinct parts — the ones the player actually needs to recall live. Only go up to the 8-snapshot hardware max when the user explicitly asks for more or the song genuinely has that many distinct sounds; don't pad to 8 by default.

**Name snapshots by sound, not song section** — `Clean` / `Crunch` / `Lead`, not `Verse` / `Chorus` / `Bridge`. Names are what shows on the Stadium scribble strip, and a player recalling a scene live thinks in tone, not arrangement.

**A solo boost is its own snapshot, not a footswitch.** It recalls a full lead voice — gain, EQ, delay, and reverb all moving together — which is exactly what a snapshot is for. Reserve footswitches (5.6) for single in-scene toggles.

Recipe extension (top-level `snapshots` array, up to 8 entries):

```json
"snapshots": [
  {"name": "Rhythm"},
  {"name": "Lead",  "params": {"Brit Plexi": {"NormDrv": 0.7, "Level": -5.0},
                               "Tape Echo Stereo": {"Mix": 0.30}}},
  {"name": "Clean", "disable": ["Compulsive Drive"],
                    "params": {"Brit Plexi": {"NormDrv": 0.25}}}
]
```

Rules:
- Each snapshot is a *delta* from the base path values. Plain `{"name": "X"}` means "use all base values" — that's snapshot 1 typically.
- `disable: [...]` bypasses a block in that snapshot (matched by display_name).
- `params: {block: {p: v}}` overrides param values in that snapshot.
- Snapshot 1 (index 0) is the one that loads on hardware boot.
- Block names in `disable` / `params` must already exist in the path's `blocks`.
- Param names in `params` are validated like base params — run `show-block` if unsure.

Common patterns:
- **Rhythm/Lead**: lead = higher amp `Drive` + `Master`, +0.10 reverb `Mix`, +0.15 delay `Mix`
- **Clean/Crunch/Lead**: clean = `disable` drive(s), back amp `Drive` to ~0.25; crunch = base; lead = stack as above
- **Clean/Crunch/Solo**: same as above, with the solo snapshot as the dedicated lead-boost scene (raise amp `Drive` 0.10–0.15 and delay `Mix` 0.20→0.35) rather than a footswitch

**Different amps across snapshots — the default when families differ (see 1a).** A single snapshot can't swap the amp model — only override knobs and bypass — so place both amps (and matching cabs) in the chain and have each snapshot enable one amp+cab pair while disabling the other. Keep this to 2 amp+cab pairs max so the chain stays under the 12-slot cap.

**Disable-only limitation — author every layered block base-ENABLED.** A snapshot can only `disable` a block; there is no `enable` field, so a block that's base-bypassed (`enabled: false`) can never be turned back on in a later snapshot. For a layered (different-amps) preset, place every amp/cab/drive it needs **base-enabled** in the path, and have each snapshot `disable` the complement — the pair(s) it isn't using that moment. Never set `enabled: false` at the base level on a block some snapshot needs lit up.

If the user doesn't ask for snapshots, skip this section — omitting the field leaves the device's snapshot slots named "Snap 1..8" with no per-scene variation.

### 5.6. Auto-wire controls (footswitches + expression)

By default, wire the chain for live use: give every toggle-able effect a footswitch and route any sweep-able pedal to an expression pedal. Shipping a preset with no live control is a miss, not a safe default. All of this is **research-overridable** — if step 1b turned up something that dictates a different set (e.g. "this tone only ever uses the one drive live, not the others"), follow the tone over the defaults below.

**Footswitches — chain order, top row then bottom:**
- Assign a **latching** footswitch to every drive/fuzz/boost, modulation, delay, reverb, and non-wah pitch/filter toggle, in signal-chain order. Walk the assignable switches in order: `FS1 → FS2 → FS3 → FS4 → FS5` (top row), then `FS7 → FS8 → FS9 → FS10 → FS11` (bottom row). **Skip `FS6` — it is the reserved MODE switch, not assignable** (and `FS12` is TAP/Tuner). This puts dirt near the low switches and time-based effects up top — the conventional live layout falls out for free.
- Skip amp, cab, EQ, comp/dynamics, and other always-on/utility blocks — they never get a footswitch. Tonal boosts belong in a snapshot (5.5), not a stomp.
- Cap at **10 assignable switches** (FS1–FS5, FS7–FS11). If more than 10 toggle-able blocks exist, either **merge** related toggles onto one switch (several `footswitches` entries may share a `switch` — e.g. a boost + its delay bump on one stomp) or wire the first 10 in chain order and tell the user in the report which ones were left un-switched.
- Use `momentary` only when the user explicitly asks for a hold gesture (e.g. a boost or pitch dive you only want while your foot is down); everything else is `latching`.
- **Label every wired switch**: set a short `label` (≤12 chars — the device truncates longer) naming the effect (`"label": "Tape Echo"`), and a `color` when it aids grouping (e.g. all dirt `red`); the valid color names are listed in the `docs/recipe-reference.md` footswitches section. One scribble strip per switch — on a merged switch, set label/color on one entry only.
- A switch can also toggle a **param** between two values instead of a bypass — add `"param"` + numeric `"min"`/`"max"` (raw param units) to the entry (e.g. FS kicks amp `Drive` 0.45→0.7). Use it when the user asks for a single-knob stomp (a multi-param change is a snapshot, 5.5).

**Expression pedals — wah/whammy → EXP1, volume → EXP2:**
- Detect a pedal-controllable block by running `show-block` and checking for a **`Pedal`** float param (0..1) — that's the real sweep param for every wah, `Pitch Wham`, and volume pedal in the library (e.g. `Teardrop 310 Mono`). Wah/expression blocks have **no `Position` param** (don't confuse it with the mic-`Position` knob on IR-cab `With Pan` blocks) — always confirm with `show-block` before writing the recipe. Poly-pitch/int-`Interval` blocks are out of EXP v1 scope.
- Route a wah or whammy's `Pedal` to **EXP1**; route a volume block's `Pedal` to **EXP2**. If only a volume pedal is present (no wah/whammy), put it on EXP1 instead. Full `min: 0.0, max: 1.0` sweep by default.
- **Wah ships bypassed, engaged by the toe switch** — set `"enabled": false` on the wah block and assign its bypass to `"switch": "EXP1Toe"` (the real expression-pedal toe switch — push the pedal fully forward to click it on, then sweep with EXP1). This is the standard Helix wah behavior. Do **not** spend a regular `FS` slot on the wah, and do not count it against the FS budget. Unless research says the reference keeps the wah always inline.
- If the user already claimed a pedal (e.g. "EXP2 sweeps amp Master"), that wins; auto-routing only fills what's left, and skips a target it can't place — telling the user — rather than overriding the user's mapping.

**Snapshot/footswitch relationship:** a change that touches ≥2 blocks/params is a snapshot (5.5, including the solo snapshot); a single live on/off or sweep is a footswitch/EXP (here). Auto-wire footswitches and EXP even on a preset that already has snapshots — they're complementary, not competing: the snapshot sets the scene's base bypass state, and the footswitch toggles from there.

If the user says "no footswitches" or "leave the controls alone," skip this step.

**MIDI CC control (only on request):** if the user wants a param or bypass driven by an external MIDI controller / DAW, add a top-level `midi` list (see the `docs/recipe-reference.md` "MIDI CC control" section) — each `{"cc": 0-127, "targets": [...]}` sweeps a param (`{"block", "param", "min", "max"}`) or toggles a bypass (`{"block", "bypass": true}`). CC-only, EXPERIMENTAL, and realized on `device install`/`sync`. Do **not** auto-wire MIDI by default — only when asked; it does not consume the FS/EXP budget, and a `(block, param)` still gets only one controller across FS/EXP/MIDI.

**Command Center commands (only on request):** if the user wants a footswitch (or Instant slot) to **send** a MIDI message (PC/CC/Note/MMC) or a Preset/Snapshot action to the device / external gear — as opposed to toggling a block — add a top-level `commands` list (see the `docs/recipe-reference.md` "Command Center commands" section). Each `{"switch": "FS1".."FS11"|"Instant1".."Instant6", "command": <family>, ...fields}`. EXPERIMENTAL, storage-validated, realized on `device install`/`sync`. Do **not** auto-wire commands by default — only when asked. A command switch is distinct from a block-bypass footswitch (a switch can't do both in helixgen yet), so don't put a command on a switch already used in `footswitches`.

### 5.7. Volume-normalization pass

A final level pass so the preset's loudness is sane and — especially when
replicating a reference — the **relative** loudness between parts/snapshots
tracks the source. helixgen never renders audio, so this sets **starting**
levels by rule of thumb; the user fine-tunes by ear on the device.

**Read the preferences first** (`~/.helixgen/preferences.json`). Two toggles,
both default on:
- `volume_normalize_baseline: false` → skip force 1 (the across-preset anchor).
- `volume_normalize_snapshots: false` → skip forces 2–3 (between-snapshot
  leveling). If both are false, skip this step and say so in the report.

**The knob:** `show-block` the amp and use its channel-volume param — and read
the **unit** off that output, because there are two:

- `ChVol` — a 0..1 knob (legacy amps). A 0.05–0.10 nudge is roughly a couple dB.
- `Level` — **decibels** (Agoura amps), typically `-40..10`, default about `-10`.
  Here you set dB directly: `-8.0` is 2 dB up from a `-10` default. A "0.5" on
  this param means +10.5 dB and clips. Factory amps sit around **-11 to -6 dB**.

Do **not** use `Master` for level (it sets power-amp saturation, and the factory
runs it near 1.0 — turning it down to balance a level throws away the feel the
Agoura models are for). Only if the amp has no channel-volume param,
add one end-of-chain volume block (from `list-blocks --category volume`) and
automate that. In a layered two-amp preset, level whichever amp is active in
each snapshot via that amp's own channel volume.

**Never gate this pass on `path.output`.** An absent or `null` `output` on a
path (or a snapshot) means the output block is at **device defaults** (0.0 dB /
0.5 pan) — **not** that the path has no output target. Every DSP path
terminates in a `b13` output endpoint whose `gain` always exists; `view` just
omits the `output` object when both level and pan are default. So an absent
`output` in `helixgen view` is a fact about the **value** (it's at defaults),
never a reason to skip normalizing. (Engine-side readers have
`PathEntry.has_output_override` for the explicit-override question — see
`docs/recipe-reference.md`; that's a Python property, not a CLI-visible field,
so it isn't something you can query from here.)

And normalize with the **amp channel volume anyway**, not that output block —
though **not** for the reason this skill used to give. The old rationale ("the
meters tap upstream of the `b13` `gain`, so an authoring-time output trim is
invisible to `device measure`") is **FALSE**: the taps sit **DOWNSTREAM** of
the output gain and a measure DOES see the trim ([MEASURED] Stadium XL fw
1.3.2, 2026-07-30 — a −20 dB output-gain write moved the meter −20.04 dB;
`docs/helix-protocol.md`, core PR #51). The actual reason to leave the output
block alone here: it is the actuator **`device normalize` owns** — a
snapshot-scope run rewrites `output.level` per snapshot outright, so any
part-to-part balance parked there is discarded by the first normalize pass,
while channel-volume balance survives it. Reserve `output` for a final clean
trim of the whole path (section 5).

**FORCE ZERO — the reachable floor. Apply this before the other three.**

A later `device normalize` can trim a snapshot DOWN without limit, but it can
only trim UP by **+20 dB** — the output-block cap. So a snapshot whose chain
gain lands below `target − 20` (≈ **−2.5 dB** against the standard 17.5 dB
target) can NEVER be level-matched, however good it sounds. Nothing downstream
rescues it; the fix has to happen here.

The trap is specific and it bites the same part every time: **a clean or
edge-of-breakup snapshot on an otherwise high-gain preset.** High gain brings
compression, which brings apparent loudness for free; a clean part has none of
that, so an "even-looking" channel volume leaves it 20–40 dB behind its
siblings. Measured on a real library, 6 of 35 tones shipped in this state, and
two of them could not be repaired afterwards at all — their amps had run out
of `ChVol` headroom.

So when a preset mixes a clean part with a high-gain part:

- **Author the clean part's channel volume HIGH** — near the top of its range,
  not at the anchor. It is not "louder than the rhythm", it is compensating for
  the compression the rhythm gets and it does not.
- **Never leave a clean snapshot at the 0.5 anchor** of a preset whose other
  snapshots are saturated. That single choice is what produced every
  unrepairable tone found so far.
- **Prefer gain earlier in the chain** (amp channel volume, a boost block) over
  planning to make it up at the output later. The output trim is the LAST
  stage and the smallest.

You cannot measure this while authoring — helixgen renders no audio — so it is
a rule of thumb like the rest of 5.7. What makes it different is that getting
it wrong is not a tweak, it is a dead end.

Apply three forces, in order:

1. **Anchor** (force 1, `volume_normalize_baseline`): set the reference part
   (usually rhythm) to a standard channel-volume anchor, default `~0.5` (leaves
   headroom, no clipping; adjust if `show-block` shows an unusual taper). Every
   preset anchoring its main part to the same value keeps presets at a
   consistent baseline. If research says the source should sit hotter/softer
   relative to its material, offset the anchor.
2. **Gain compensation** (force 2, `volume_normalize_snapshots`): more gain →
   more compression → louder *perceived* level at the same knob. So push
   **lower-gain parts up** to sit even — a clean/edge-of-breakup part usually
   needs its channel volume raised to match a high-gain rhythm; a very hot,
   highly-compressed rhythm may need a small trim.
3. **Intended dynamics** (force 3, `volume_normalize_snapshots`), relative to the
   rhythm anchor: **lead/solo ~+2–3 dB** (to cut through), **crunch ~= rhythm**,
   **clean = perceptually matched** (via force 2). When step-1b research reveals
   the source's actual part-to-part dynamics, those override these conventions.

**dB → param:** on a `Level` (dB) amp, an intended dB delta IS the value — add
it to the current dB. On a `ChVol` (0..1) amp we can't measure, so use *a small
nudge (~0.05–0.10) ≈ a couple dB* to turn intended dB deltas into starting
values. Per-snapshot moves become `params` overrides on the channel-volume param
(alongside the gain/EQ/effect deltas from 5.5); a base preset gets the anchor on
its base amp params.

### 6. Pick the instrument, then resolve its controls

For the report (next step), the user's hands-on guitar settings are part of the tone — pickup choice and rolled-back knobs shape the sound as much as the amp settings do.

**Guitars are first-class profiles** at `library/guitars/<slug>.json` (they
replace the old `preferences.instruments`). Read a profile with
`helixgen library show <guitar> --json` — it resolves by slug, name, or
`short_name`. A profile carries `character_md` (tonal character — what the
guitar is for), `pickups`, `construction`, and `controls[]` (the control
inventory). **Adapt block params to the resolved profile** — bright
single-coils want less amp treble-pull than dark humbuckers; a variant's
`guitar_settings` keys should reference the profile's real `controls[]` names.

Resolve the target guitar in this order (first hit wins). The resolved guitar
is **the target guitar** passed to `generate --guitar <label>` (step 7),
naming the tone and keying its variant:

**(a) A user-named guitar always wins.** If the user named a specific guitar,
use it. If research (1b) or the tone target suggests it's a poor fit, give
**one** honest nudge — not an argument — e.g. "the EC-1000's scooped active EMGs
will fight this vintage-crunch voicing — if you have it handy, the LP Jr's P-90
nails it more directly" — then proceed with the guitar they asked for.

**(b) Else, use `default_guitar` from preferences.** If no guitar was named and
`~/.helixgen/preferences.json` has a `default_guitar` set, use it — it names a
guitar **profile** (by slug or name/`short_name`); state it briefly ("using
your default guitar, the <X>"). Still give the one-nudge from (a) if it's a
poor fit for the tone.

**(c) Else, ask which guitar to use — and offer to save it.** When no guitar was
named and `default_guitar` is unset, **ask the user which guitar to use.** Offer
a best-fit suggestion from their guitar **profiles** (`helixgen library show`
each; fall back to the user's guitar memory — Les Paul Jr, ESP LTD EC-1000,
Strandberg Boden Essential 6, Ibanez Prestige — if no profiles exist yet) using
the pickup-class table below, and **offer to save their choice as
`default_guitar` in preferences.json** (confirm-first, per the setup skill's
write-back rule) so you won't have to ask next time. Only fall through to the
generic tone-goal table (further down) plus a single clarifying question when
the lineup is entirely unknown — no profiles, no preferences file, and no
memory.

**Offer per-guitar variants — only when 2+ guitars are plausible.** When the
user owns/names **two or more** guitar profiles that could plausibly carry this
tone, **offer** (via a structured question) to author per-guitar variants —
each a `generate --guitar <other>` against the **same** identity (step 5's
logical-tone/variant model). With a **single** guitar in play, do **not** ask
(backlog #22) — just proceed with it.

Match tone character to pickup class (this is the best-fit suggestion in (c),
and the nudge check in (a)/(b)):

| Tone target | Wants | Pick |
|---|---|---|
| Punk, garage, raw blues, vintage rock, early breakup, gritty midrange bark | P-90: hot single-coil, breaks up early | **Les Paul Jr** (single bridge P-90, no selector) |
| Modern metal, djent, tight scooped high-gain rhythm | Active humbucker: tight, scooped, high-output | **ESP LTD EC-1000** (active EMGs, 3-way) |
| Prog/fusion clarity, pristine clean needing sparkle, technical lead | Coil-split humbucker: HB for gain, split for SC clarity | **Strandberg Boden Essential 6** (HSS, 5-way with splits) |
| Classic rock, versatile hard rock, ambiguous mid-gain | Versatile HSH, bridge HB for gain | **Ibanez Prestige** (HSH, 5-way) |

Research (1b) beats the table when it names the reference's actual pickup type — match that class first, the table is the fallback for a generic target. Only name a runner-up when the top two are a genuine toss-up (one clause: "or the Prestige if you want it tighter and less hairy").

**Resolve controls, then translate into the selected guitar's real switch language.** Start from the tone-goal defaults:

| Tone goal | Selector | Volume | Tone |
|-----------|----------|--------|------|
| Aggressive rhythm/lead | bridge | 10 | 10 |
| Singing lead (Slash-style) | bridge | 10 | 7–8 (round off the edge) |
| Mellow / woman tone | neck | 10 | 4–6 |
| Clean breakup | bridge or neck | 6–8 (back off to clean it up) | 10 |
| Chimey clean (Strat-style) | middle or position 2/4 | 10 | 8–10 |
| Jazz / hollow body | neck | 7–9 | 5–7 |
| Funk single-note | bridge or position 2 | 10 | 10 |

Then translate the generic position into the guitar's actual switches — never say "middle position" for a guitar that doesn't have one:

- **Les Paul Jr** — no selector; single bridge P-90. Nothing to move — note pick attack instead (digging in near the bridge is the "selector" here).
- **ESP LTD EC-1000** — 3-way: rhythm (neck) / middle (both) / treble (bridge).
- **Strandberg Boden Essential 6** — 5-way, HSS: position 1 = bridge humbucker … position 5 = neck single; positions 2–4 include coil-splits. Flag "confirm your wiring if it differs."
- **Ibanez Prestige** — 5-way, HSH: position 1 = bridge HB, positions 2/4 = split in-betweens, position 3 = middle single, position 5 = neck HB.

Round out the recommendation with, where relevant: a **coil-split** call for the Strandberg/Prestige ("split the bridge for the clean verse's glassy top, full humbucker for the chorus push"), a one-clause **pick-attack** note (P-90 rewards digging in near the bridge; active EMGs want a tight palm mute and let the pickup compress; single-coil/split positions want a lighter touch to avoid brittleness), and a one-clause **"why this guitar"** tying pickup class to the tone.

If nothing is known about the user's lineup (no preferences file, no memory, no named guitar), fall back to the generic tone-goal table above with generic switch language, and ask one clarifying question only if the guitar is genuinely load-bearing for the tone.

**Snapshots stay on one instrument.** For a snapshot preset (5.5), the recommendation names a single guitar — the player isn't swapping guitars mid-song — and expresses per-scene differences as control moves on that one guitar (e.g. "split (Strandberg pos 4) + volume 7 for the clean verse snapshot, full bridge (pos 1) + volume 10 for the lead snapshot").

### 7. Generate into the library

Write the recipe JSON to a scratch file, then run `generate` with the **naming
flags** from step 5 (no `-o` — this is the default library flow):

```bash
HELIXGEN_LIBRARY="${CLAUDE_PLUGIN_ROOT}/data/library" helixgen generate /tmp/<slug>.recipe.json \
  --artist "Foo Fighters" --song "White Limo" --guitar "Les Paul Jr"
```

**Say where it landed, and whether that's durable.** Report the written
`.hsp` path. Under the bundled-library fallback
(`${CLAUDE_PLUGIN_ROOT}/data/library`) the tone — and the `description_md`
written in 7a — lives inside the plugin, which a `/plugin` update can
replace: tell the user in one clause, and that a populated
`~/.helixgen/library/` (or `$HELIXGEN_LIBRARY`) is the durable home. No
warning needed when the resolved library is already the user's own.

(Or `--descriptor "<Descriptor>"` instead of `--artist`/`--song`; drop
`--guitar` only for a guitar-agnostic tone. The library prefix is per the
Prerequisites resolution.) With no `-o`, `generate` writes the `.hsp` into the
tone library at `library/tones/<variant-slug>.hsp` **and** authors the per-tone
metadata JSON at `library/tones/<logical-slug>.json`. **Warnings appear on
stderr** — read them and surface them to the user.

- **Slug collisions error, never overwrite.** If the target `.hsp` already
  exists, `generate` errors with a rename suggestion — don't force past it;
  either you're re-authoring (adjust identity) or you meant a new variant
  (change `--guitar`).
- **`--guitar` resolution:** the label resolves to a guitar profile
  (slug/name/`short_name`, case-insensitive). If profiles exist but none
  matches, it errors listing the known guitars; ambiguous → errors asking you
  to disambiguate by exact slug. If **no** profiles exist yet (fresh /
  pre-`library migrate`), it falls back to a literal `slugify(label)` with a
  stderr notice — authoring still works.
- **Ad-hoc `-o` (legacy):** an explicit `-o <out.hsp>` preserves the old
  behavior exactly — writes there, auto-registers, **ignores** the naming
  flags, and writes **no** metadata JSON. Use it only for throwaway/scratch
  output; the library flow above is the default for real tones.

If the validator errors with `Unknown param(s) [...]`, re-run `show-block` on the offending block, fix the recipe, retry. Never guess the corrected name.

#### 7a. Author the description into the tone metadata — REQUIRED

(Run the envelope check in 7b **first** if you want to avoid rewriting
this section — a finding there changes the settings you are about to
document.)

The durable, human-readable record of the tone is **not** a `.md` sidecar
anymore — it's the tone metadata's `description_md`, authored with
`helixgen library doc`. Write it after `generate`:

```bash
HELIXGEN_LIBRARY="${CLAUDE_PLUGIN_ROOT}/data/library" helixgen library doc "<name>" --from-file /tmp/<slug>.description.md   # or: … - (reads stdin)
```

(`<name>` resolves as the logical slug (`test-artist-test-song`), the metadata filename (`<slug>.json`), or a full variant **preset name** — which includes the guitar, e.g. `Test Artist - Test Song - Scratch Tele`. A bare `Artist - Song` without the guitar segment won't match; use the slug or the full preset name.)
Compose the markdown (to a scratch file or via stdin), covering — it's
effectively the step-8 report, persisted so the tone stands alone without the
chat:

- **Title + target** — the tone name, the guitar it's voiced for, and what it's aiming at (artist/song/section/genre/feel). State the target guitar clearly near the top (omit it only when the tone is explicitly not guitar-specific — then say so)
- **Reference notes & sources** — the key findings from step 1b research, with the source links (omit if research was skipped because the target was generic)
- **The chain** — one line per block: position, model, and the 2–3 settings that matter
- **IRs referenced** — basenames, so the user knows what must be loaded on the device
- **Snapshots** — one line each (only if the recipe has them)
- **Levels** — the intended relative balance line from step 8 (or that normalization was off per preferences)
- **Footswitches** — one line per assigned switch, rendered in **English name + position**, not a bare identifier (`Footswitch 1 (top row, 1st from left) → Compulsive Drive`, …). Get the English string from `helixgen controllers` (`--json` for the machine shape). Only if the recipe has them.
- **Expression** — one line per pedal mapping, also in English (`Expression Pedal 1 (onboard pedal, EXP 1) → Teardrop 310 Mono Pedal`, …), only if the recipe has them
- **Recommended instrument** — a `## Recommended instrument` section (see step 6): **Pick**, **Why**, **Controls** (selector / volume / tone / coil-split if applicable / pick attack), **Second choice** (only on a genuine toss-up), **Note** (any lineup caveat, e.g. active-vs-passive TBD)
- **Tweaks** — the one concrete tweak from step 8, plus any obvious alternates

Keep it tight and scannable — it's reference material, not a transcript. **Per-variant notes** (anything specific to one guitar's `.hsp`) go to that
variant's `notes_md` instead: `helixgen library doc "<name>" --variant
<guitar-slug> (--from-file <md> | -)`. If you regenerate/iterate on the preset
(step 10), re-run `library doc` to update the description in place.

Read it back any time with `helixgen describe "<tone>"` (identity + variants
table + `description_md` verbatim) or `helixgen library show "<name>" [--json]`
(compact/JSON metadata).

#### 7b. Check it against the factory envelope — REQUIRED

Before you report, run the envelope check. It reads the generated `.hsp`
directly, back-fills every param the model declares, and compares each value —
base and per-snapshot — against `${CLAUDE_PLUGIN_ROOT}/data/factory-corpus.json`,
the measured distributions from Line 6's own 66 factory presets. It is the only
automatic check that the tone is voiced like a real preset rather than like a
plausible-sounding guess:

```bash
HELIXGEN_LIBRARY="${CLAUDE_PLUGIN_ROOT}/data/library" \
  python3 "${CLAUDE_PLUGIN_ROOT}/tools/envelope-check.py" <path-to>/<variant-slug>.hsp
```

Reading the result:

- **FAIL** — the value is outside anything Line 6 shipped **for that same
  model**. Treat as a bug in the recipe: fix it, or state in the write-up why
  this tone genuinely needs it. Exit code is 1 when any FAIL is present.
- **NOTE** — outside the typical p25–p75 band, or outside a category-level
  reference. Fine when deliberate; each one should be a choice you can name.
- Silence means every param sits inside factory practice.

Do not "fix" a FAIL by nudging the number just inside the band — check the
reason. The common causes are the ones this skill exists to prevent: a legacy
amp where an Agoura model exists, a dB `Level` written as if it were 0..1, a
`Master` parked at 0.5, or a cab clamped dark.

#### 7c. Do NOT git-commit library paths yourself

Core **auto-commits** library changes to the `~/.helixgen` git repo after every
library-mutating verb (the no-`-o` `generate`, `library doc`, …), advisory and
gated by the `git_commit_tones` preference. **The skill must not git-add or
git-commit library files itself** — that behavior now lives in the engine.
(You may still commit a **non-library** directory you explicitly wrote into,
e.g. a project presets folder reached via an ad-hoc `-o` path — but the default
library flow is hands-off.)

### 8. Report back

Tell the user, in this order:
1. **The chain** — one short line per block (position, model, the 2–3 settings that matter for this tone)
2. **Snapshots** (only if the recipe has them) — one line per snapshot summarizing what differs from base, e.g. `Lead: amp Drive 0.85, delay Mix 0.30; Clean: drive bypassed, amp Drive 0.30`
3. **Levels** (from 5.7) — one line on the *intended* relative balance, e.g. `rhythm anchor; lead +~2 dB; clean bumped to match (fine-tune by ear)`. If normalization was skipped by preference, say `Levels: normalization off per preferences`.
4. **Instrument** — `<guitar> — <one-clause why>` (skip the "why" if the user named the guitar themselves), then `Selector: <position> · Volume: <0–10> · Tone: <0–10>` in that guitar's real switch language, plus a one-clause note for any non-obvious move (roll-off, coil-split, pick attack)
5. **Controls** (only if 5.6 wired any) — render every controller in **English (name + physical position)**, never a bare `FS#`: the footswitch map (`Footswitch 1 (top row, 1st from left) → Compulsive Drive`, …), the expression routing (`Expression Pedal 1 → wah Pedal`, …), and any toe-switch engage (`Expression pedal toe switch → Teardrop 310 Mono (bypass)`). Use `helixgen controllers` (or `--json`) for the exact strings. Conversely, if the **user** describes a switch in plain language, run it through the small-model controller-translation sub-agent (fed the `helixgen controllers --json` mapping) to get the canonical identifier before wiring it, and validate the result against the canonical set.
6. **The file** — the `.hsp` in the tone library (`library/tones/<variant-slug>.hsp`), with its description authored into the tone metadata (step 7a; read it back with `helixgen describe "<tone>"`). *"Open Line 6's HX Edit, connect your device via USB, and import that file."* Per user preference, run `open -R "<path-to>/<variant-slug>.hsp"` so it's pre-selected in Finder. If the user instead wants it pushed **straight onto the Stadium over the LAN** (no HX Edit), hand off to the `device` skill — a live install is more involved than a file drop. Once it's on the device, offer the measured level-match (step 9).
7. **One concrete tweak** they can try after loading (e.g. "if it's too dark, raise Treble to 0.65"; "for a thicker lead, push Tape Echo Mix to 0.25")

Don't hedge with a list of 5 things to maybe try; pick one.

### 9. Offer to level-match it on the device (measured)

The levels you set in 5.7 are **rules of thumb** — helixgen renders no audio,
so they are a starting balance, not a measurement. `device normalize` closes
that loop against the real hardware. Offer it once the tone exists; don't
make the user know the feature is there.

**Run the dry-run as a DESIGN CHECK, before you consider the tone finished.**
It is the only way to find out whether every snapshot cleared the reachable
floor (force zero in 5.7), and the answer is cheap to act on right now and
expensive later: an `UNREACHABLE` target costs one `set-param ChVol` while you
are still in the tone, versus an install → sync → measure → step loop on
hardware afterwards — which has already failed outright on tones whose amps
had no headroom left. If the device is reachable, measure before you report.

**Offer when** the preset has **≥2 named snapshots** (their relative balance is
exactly what the loop equalizes), or the user keeps other tones on the device
that this one should sit level with. A single-snapshot one-off that nothing
else is compared against doesn't need it — say so rather than upselling.

**Read `~/.helixgen/preferences.json` → `normalization` FIRST** — the mode
decides what you ask for, and asking before you know it gets the cost wrong.
`play` is the default when the block is absent, and needs no setup at all.

| Mode | What the user does | What must be connected | The ask |
|---|---|---|---|
| `play` (default) | plays the guitar, ~10 s per target | **Nothing beyond the LAN** — Helix on WiFi/Ethernet, guitar in Inst 1 as usual. Measurement is network telemetry; USB is not involved | "about 10 seconds of you playing per snapshot" |
| `sample` | **nothing** — the CLI plays a recorded loop | Computer's analog output → 1/4" Inst 1, **guitar unplugged**, and the computer's output device pinned to the one actually cabled (the Stadium steals the system default) | "hands off — it plays the calibration loop itself" |
| `looper` | **nothing** — an on-device looper replays | Nothing extra; they record the loop first | "keep the looper running" |

**Then ask, in one line, with that mode's cost in it** — e.g. for `play`:

> "Want me to level-match those snapshots against the real hardware? It takes
> about 10 seconds of you playing per snapshot — 3 snapshots, so roughly half a
> minute of steady playing. Or skip it and I'll leave the levels as authored."

If the user says no, stop — the authored levels stand and the report already
said what they are.

**`sample` mode needs a calibration first**, and its own order matters: run
`helixgen device calibrate` **with the guitar still plugged in**, because step
1 of that verb asks the user to *play by hand* to capture the reference jack
level. Only step 2 has them unplug the guitar and cable the computer in. Doing
it the other way round fails the reference window and saves nothing. Skip this
whenever `normalization.calibration` is already filled in and fresh (the CLI
warns when it isn't).

**The sequence** — this is the part to get right, because the tone has to be on
the device *and selected* before anything can be measured:

1. **Put it on the Helix and SELECT it.** `device install` (or `device sync
   <setlist>`) writes the preset but **leaves the active tone untouched** —
   snapshot-scope normalize verifies the active preset's name and aborts on a
   mismatch, which on a freshly installed preset is guaranteed. So follow the
   install with `helixgen device load <cid>` (the `device` skill covers finding
   the cid) and confirm with `helixgen device active`.
2. **Dry run first, always** — and pass the absolute target if there is one:

   ```bash
   HELIXGEN_LIBRARY="${CLAUDE_PLUGIN_ROOT}/data/library" helixgen device normalize <preset.hsp> --target-db <profile target>   # dry run
   ```

   It recalls each snapshot, measures a window per target, and reports the
   trims it *would* write. Show the user that report. **There is no per-target
   prompt** — the windows run back to back, so in `play` mode the user must be
   playing from the moment the run starts and keep going until it ends. Say so
   before you start it.
3. **Write them:** re-run the same command with `--yes`. Trims land in the
   **local `.hsp`**, as per-snapshot output-level moves — not on the device.
4. **Re-sync** (`device sync` / `device install`) or nothing changes audibly on
   the hardware.
5. **Update the write-up** — the balance is now measured, so refresh the
   Levels line via `helixgen library doc` (7a), and the run itself is recorded
   on the tone as a `normalized` record you can read back with
   `helixgen describe "<tone>"`.

**Scope rules that decide whether the loop can run at all:** snapshot scope
needs **≥2 named snapshots**, or an explicit `--target-db` with one. A preset
with no named snapshots can't be normalized this way at all — level-match it
as part of a setlist instead (`device normalize --setlist <name>`, the `device`
skill's territory).

**Cross-tone matching needs an absolute target.** Without `--target-db` the
run anchors on its own first snapshot, which equalizes *within this preset
only* — two presets normalized separately still won't sit level with each
other. If the user keeps a library, use their `normalization.target_db` (or 17.5 dB, the shipped reference —
the measured total of the factory *Stadium Rock Rig*) and
reuse it for every tone.

**If a snapshot can't reach the target**, the run says so with its ceiling —
that one is a **gain-staging** problem, and unlike the rest of this step it is
*your* job, not the device skill's: raise the amp's channel volume (both amps
on a layered preset) and re-run. `ChVol` is wildly non-linear — 0.55 → 1.0 was
+24.7 dB of chain gain on one measured amp — so move it in small steps.
**Re-sync before re-measuring**: a `ChVol` edit lands in the local `.hsp`, so
until `device sync`/`install` rebuilds the device copy the hardware is still
running the old chain and the re-measure reads "no change". Do **not** solve it by raising the output block instead: that
amplifies the chain's noise floor by the same amount.

#### Repairing a tone that can't reach the target (the gain-staging loop)

When `device normalize` reports `UNREACHABLE (ceiling X)` for a snapshot, the
output block has nothing left to give — its trim is the LAST stage, capped at
+20 dB. The chain itself has to get louder. This is a loop, not a
calculation: `ChVol` is wildly non-linear (a measured 0.55 → 1.0 was +24.7 dB
on one amp), so you converge on it the same way the volume calibration does.

Run it yourself; don't hand the user a list of verbs.

1. **Read the shortfall from the run.** `--json` gives `ceiling_db` and the
   run's `target_total_db` per target. `shortfall = target − ceiling`. That is
   how much MORE chain gain the snapshot needs.
2. **Find the actuator.** `helixgen view <preset.hsp>` → the amp block's
   channel-volume param (`ChVol`, or the amp's `Level` — confirm with
   `show-block`, the name varies). **Never `Master`** (it moves power-amp sag
   and feel). No channel volume ⇒ add an end-of-chain volume block instead.
3. **Check the headroom first.** If `ChVol` is already at 1.0, this loop
   cannot help — say so plainly rather than nudging a maxed knob. The fix is
   then a hotter amp model, a drive/boost in front, or accepting a lower
   target for that tone.
4. **Step, don't solve.** Raise `ChVol` by ~0.05–0.10 for a few dB, more for a
   large shortfall — but never jump straight to 1.0 on a >20 dB shortfall, or
   you overshoot into a wall of gain. On a dual-amp preset raise **both amps
   by the same amount**, or the blend moves.
   `helixgen set-param <preset.hsp> "<amp>" ChVol <value> --snapshot <name>`
   (per-snapshot: it is usually ONE quiet snapshot that is short, and a base
   edit would move the whole preset).
5. **Sync before re-measuring.** The edit is in the local `.hsp`; until
   `device sync <setlist>` / `device install` rebuilds the device copy, a
   re-measure reads the OLD chain and looks like the edit did nothing. This
   is the single most common way to waste a loop.
6. **Re-measure and repeat** until `ceiling ≥ target`. Then run the normal
   `--yes` pass to set the trim.

Report each iteration in one line — the param, the value, the resulting chain
gain — so the user can see it converging rather than watching silence. Stop
and ask if it has not converged in ~4 iterations: something else is wrong
(wrong actuator, a bypassed block, a gate killing the signal).

**Chain-out `output_db` over 0 dBFS in the results is in-chain clipping**, and
no level move fixes it — back off the amp/drive gain and re-run (see step 10's
ear-language table).

### 10. Iterate on feedback (when the user loads it and says it's not quite right)

After the user loads the preset and reports back ("the lead is too compressed", "verses are too dark", "swap that delay for something slappier", "clean snapshot needs a touch of reverb"), don't start over. The `.hsp` you saved is the source of truth — make the smallest edit that addresses the feedback with a single in-place `helixgen patch` call (see **Adjusting an existing tone** above; do NOT regenerate from the recipe), and tell the user what changed in one line so they can A/B. If the change is worth recording, refresh the tone's `description_md` with `helixgen library doc` (7a). Don't git-commit library paths yourself — core auto-commits (7c).

Rules of thumb for translating ear-language to param moves:
- **"Too compressed"** on a lead → back amp `Drive` off ~0.10, raise `Master`; or back drive pedal `Gain` off ~0.10
- **"Too dark"** → raise `Treble` 0.05–0.10, raise `Presence` 0.05; or change to a brighter amp variant if the EQ is already at ceiling
- **"Too bright / harsh"** → drop `Treble`/`Presence` first; then try cab `Angle` 45°, a darker `Mic`, or `Position` toward 0.4. Pull `HighCut` down only as a last resort, and not below 8000 — that is already at the aggressive end of factory practice
- **"Fizzy / digital / not amp-in-the-room"** → in order: (1) confirm the amp is an **Agoura** model, not a legacy HX one — that is the biggest single difference in feel, and no EQ move substitutes for it; (2) raise the amp's power-amp volume (`Master`/`MasterVol` — check `show-block`) toward its factory value for that model and back `Drive` off to ~0.5, so the saturation comes from the power amp; (3) try a different cab `Mic` and `Angle` 45°; (4) a Parametric EQ cutting 2–4 dB at 3–4 kHz medium Q; (5) a subtle comp (~1–2 dB GR) at the front. Do NOT reach for a big `HighCut` — a dark preset is the more common failure here
- **"Not enough body"** → raise `Bass` 0.05–0.10 or `Mid` 0.05; if a `LowCut` was set, lower it back toward the 19.9 default
- **"Boomy / flubby"** → raise cab `LowCut` toward 60–90 (factory's upper range), back `Bass` off
- **"Lead doesn't sing / cut"** → raise `Mid` 0.05–0.10 in the lead snapshot, raise delay `Mix` 0.05
- **"Delay is washy / too long"** → drop `Mix` 0.05 OR drop `Time` 0.05
- **"Reverb feels too loud"** → drop `Mix` 0.03–0.05 (Stadium plates run hot, small moves matter)
- **"Swap X for something Y"** → run `list-blocks --category <cat>`, scan for candidates, `show-block` the chosen one, then a `swap_model` op in a `helixgen patch` call
- **Feedback about ONE snapshot** ("the lead snapshot is too loud", "clean scene needs less drive") → a per-snapshot override, not a base edit: add `"snapshot": "<name-or-0-based-index>"` to the `set_param`/`set_enabled` patch op (or the single-op form `helixgen set-param <hsp> <block> <param> <value> --snapshot <name-or-index>`, 0.23.0). The param must already carry a base value and the preset must define snapshots; overrides reach the device on the next `device install`/`sync`. Once a param varies per-snapshot, a later plain base edit of it is inaudible on-device (`set-param` warns) — keep editing that param per-snapshot.

**Objective numbers from a recording (optional).** If the user has (or makes)
a WAV capture of the tone and wants measurements instead of ear-language,
`helixgen analyze-audio <capture.wav> --json` (0.23.0) reports LUFS, crest
factor, peak/true-peak/RMS, a clipping flag, spectral centroid, and 5-band
energies (low/low_mid/mid/high_mid/high) you can map straight onto the moves
above (e.g. a fat `high` band → a targeted EQ cut or a darker mic). **It needs the
`[analyze]` extra, which is NOT in the plugin's default install** (the pin
stays `helixgen[device]`) — if the user asks for audio metrics, reinstall
once with `uv tool install --force 'helixgen[device,analyze]==0.45.0'`.
The EXPERIMENTAL `--record N -o <out.wav>` path records the capture first
from an audio input — e.g. the Stadium's USB return — via sounddevice
before analyzing it; that additionally needs the `[capture]` extra (plus
the PortAudio system library):
`uv tool install --force 'helixgen[device,analyze,capture]==0.45.0'`.
The capture flags `--input`/`--rate`/`--channels` apply only to `--record` —
passing any of them without `--record` is a **usage error** (0.27.0; they
used to be silently ignored). Two measurement caveats (0.27.0): the WAV is
decoded **whole-file into memory** as float64 (~2.7 GB peak for an hour of
48 kHz stereo — keep captures to minutes; there is no streaming mode), and
the momentary/short-term LUFS **maxima** are computed on a 100 ms hop, so a
peak straddling two hop positions can under-read by a fraction of a dB
(integrated LUFS is unaffected).
Don't reach for either unprompted; ear-feedback plus the table above is the
normal loop. (On-device loudness leveling across snapshots/setlists is the
`device` skill's `device normalize`.)

**Read the tone's `normalized` record before proposing level/gain moves
(0.26.0).** When a library tone has been level-matched on hardware, `device
normalize --yes` records the run on that variant as a `normalized` record —
a human summary prints in `helixgen describe "<tone>"` / `helixgen library
show "<name>"`, and the full per-target measurement telemetry is under
`helixgen library show "<name>" --json`. Two things to read off it before
touching the tone:

- **Level-match state** — per-target `trim_db` / `total_db` against the
  run's `target_total_db`. A tone whose targets measured in band is already
  level-matched: don't propose output-level moves on top of it (and know
  that hand-editing output `level` will unbalance what normalize set).
- **Chain-out clipping** — each target's `output_db` is chain-out dBFS;
  over 0 dBFS means **in-chain clipping** that no output trim fixes.
  Fix the gain staging (amp/drive `Level`/`Gain` params) *first* instead of
  proposing tone tweaks on top of a clipping chain — then have the user
  re-run `device normalize`.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Guessing param names | Always run `show-block` before writing params for a block |
| Recommending a block not in the user's library | Always verify with `list-blocks --category <cat>` first |
| Running `helixgen` without the library env | Prefix every library-touching call with `HELIXGEN_LIBRARY` (see Prerequisites) — a wrong/empty library makes every block lookup fail |
| Stacking too much gain | Drive `Gain` + amp `Drive` compound; back one off |
| Forgetting a cab | Output is dry/fizzy without one; place after the amp |
| Clamping cab `HighCut` to 6500–7000 and `LowCut` to 80–100 on every preset | That was invented guidance and it is what makes generated presets sound muffled next to factory ones. Factory median is HighCut 11750 / LowCut 19.9 — mostly untouched (step 5 cab voicing baseline) |
| Leaving cab `Mic` unset and calling it neutral | The default is a per-cab accident, not a choice. When Line 6 picks, the most common pick is `121 Ribbon`, then `57 Dynamic` and `160 Ribbon`, at 0° on-axis. Choose by label — `show-block` prints them (step 5) |
| Heavy reverb defaults | Stadium plates run hot; start at 0.10 |
| Asking 5 clarifying questions | Cap at 3, only what's actually missing |
| Reporting only amp settings, not the instrument recommendation | Selector + volume + tone (+ coil-split/pick-attack where relevant) are part of the tone; include them in the report (step 6, step 8 item 4) |
| Authoring a multi-snapshot tone and never offering the measured level-match | 5.7's levels are unmeasured rules of thumb; `device normalize` closes the loop against real hardware in ~10 s of playing per snapshot (step 9). Offer it — don't wait to be asked |
| Running `device normalize` per preset with no `--target-db` and calling the library level-matched | The default anchor equalizes WITHIN one run only; separate runs land nowhere near each other. Use one absolute target for every tone (step 9) |
| Leaving a clean/low-gain part at the same level knob as a high-gain part and calling it balanced | High gain reads louder (more compression); push the lower-gain part's channel volume up to sit even — the volume-normalization pass (5.7), gain-compensation force |
| Generic guitar advice that ignores the named or auto-selected guitar | If the user said "Strat", say "middle/position 4"; for the user's own lineup use its real switches — LP Jr has no selector, EC-1000 is a 3-way (not 5-way), Strandberg/Prestige are 5-way with specific split positions |
| Defaulting to multiple presets when amp families differ | Default to ONE preset with layered amps + snapshot bypass instead (1a, 5.5); fall back to multiple presets only when it won't fit the 2-pair/12-block/8-snapshot budget |
| Bypassing a block at the base level that a later snapshot needs lit up | Snapshots can only `disable`, never `enable` — author every layered block base-ENABLED and disable the complement (5.5) |
| Naming snapshots after song sections | Name by sound (`Clean`/`Crunch`/`Lead`), not arrangement (`Verse`/`Chorus`) — that's what reads on the scribble strip (5.5) |
| Giving a solo boost its own footswitch | A solo/lead boost changes gain + EQ + delay/reverb together — that's a snapshot (5.5), not a stomp |
| Forcing one preset per role when snapshots fit | If the user wants "rhythm and lead" or "verse/chorus/solo" on one amp family, build ONE preset with snapshots, not multiple files |
| Snapshot referencing a block name that isn't in the path | `disable` / `params` only see blocks the path actually places; add the block to the path first (even if it'll be bypassed in some snapshots) |
| Shipping a preset with no live control | By default wire toggle-able blocks to footswitches and sweep-able blocks to EXP (5.6) — don't ship silent presets unless the user asked for hands-off |
| Using `Position` as the wah/expression sweep param | The real param is `Pedal` (float 0..1) on blocks like `Teardrop 310 Mono`; wah/expression blocks have no `Position` param (that name is the IR-cab mic knob) — always confirm with `show-block` (5.6) |
| Building an artist/song tone from memory | Research the real rig from the web first (step 1b) — signature tones hinge on non-obvious details; cite sources |
| Generating a tone without a description | Author the tone metadata's `description_md` with `helixgen library doc` (step 7a) — there is no `.md` sidecar anymore; the write-up lives in the tone metadata |
| Writing a companion `.md` next to the `.hsp` | Gone — descriptions live in `description_md` via `library doc` (per-variant notes → `notes_md`); read back with `helixgen describe` |
| Naming a tone without its target guitar | Pass `--guitar <label>` so the display name/slug carry the guitar (`"$Artist - $Song - $Guitar"` / `"$Descriptor - $Guitar"`, step 5); omit it only when the tone is explicitly guitar-agnostic |
| Hand-formatting the old `"<Tone> — <Guitar>"` title in the recipe | Identity comes from `generate`'s `--artist`/`--song` or `--descriptor` + `--guitar` flags, not the recipe `"name"` (step 5 naming) |
| Picking a legacy HX amp when an Agoura model exists | Agoura is the Stadium's own engine (SIC amp/cab interaction, real touch response) and is what all 66 factory presets are built on, 69 uses to 22. Legacy models exist for backward compatibility — reaching for one by name-similarity is how a preset ends up feeling flat (step 3) |
| Writing an Agoura amp's `Level` as if it were a 0..1 knob | `Level` is **dB** (`-40..10`, default ~`-10`); `ChVol` is the 0..1 one. `Level: 0.5` is +10.5 dB and clips. `show-block` prints the unit — read it (step 5 level-units box) |
| Overriding the amp's power-amp volume by habit | Half of factory amps sit at the model default (usually 1.0) — the power-amp saturation is what the Agoura models are for. When Line 6 does move it, they move it DOWN (median 0.645), and the high-gain Agouras sit at 0.36–0.55. Start from the model's default, and check `by_model` before overriding. The knob is `MasterVol` on `USDouble Black`, absent on `Mandarin Rocker Mk 3` — `show-block` first (step 5) |
| Setting `Hype` on every Agoura amp | 51 of 69 factory amps leave it at 0. The 18 that use it sit at 0.21–0.39. A seasoning, not a baseline (step 5) |
| Shipping without running the envelope check | Step 7b is the only automatic check that the preset is voiced like a real one; a FAIL is a recipe bug, not a formality |
| Reverb/delay `Mix` at 0.08–0.20 | That was invented guidance. Factory sets these on nearly every block, at reverb 0.32 and delay 0.33 medians — generated presets have been shipping far too dry (step 5) |
| Git-committing the generated `.hsp`/library files yourself | Core auto-commits library changes (gated by `git_commit_tones`); the skill must not add/commit library paths (step 7c) |

## Adjusting an existing tone (surgical edits)

When the user asks to *tweak* a tone you already generated (e.g. "brighter
cab", "swap to a Plexi", "more delay", "kill the reverb"), do NOT regenerate
from a fresh description. The `.hsp` is the source of truth — edit it in place
with a single `helixgen patch` call. There is **no** decompile→edit-recipe→
regenerate round-trip.

1. You already have the `.hsp` file's path (the one you saved, or an orphan the
   user imported) — no recovery step needed.
2. Run `helixgen patch "<dir>/<slug>.hsp" - --json` with the smallest set of
   ops that expresses the change, passed as a JSON list on stdin (batch
   multiple changes into one call — `patch` applies all ops in memory and
   writes the file once; an invalid op anywhere leaves the file untouched):

   ```bash
   HELIXGEN_LIBRARY="${CLAUDE_PLUGIN_ROOT}/data/library" helixgen patch "<dir>/<slug>.hsp" - --json <<'EOF'
   [{"op": "set_param", "block": "Mic Ir_4x12 Greenback 25 With Pan", "param": "HighCut", "value": 9000},
    {"op": "set_enabled", "block": "Plate Stereo", "enabled": false}]
   EOF
   ```

   - "brighter" → `set_param` on the cab `HighCut` (raise it).
   - "swap to a Plexi" → `swap_model` (old → new amp; same category required).
   - "kill the reverb" → `set_enabled` with `enabled: false` on the reverb block.
   - "add a delay" → `add_block` with the delay block, `after` the amp/cab.
   - "…but only in the Lead snapshot" → add `"snapshot": "Lead"` (a name, or
     a 0-based index) to the `set_param`/`set_enabled` op — a per-snapshot
     override instead of a base edit (0.23.0; see step 10's per-snapshot rule).

   Run `helixgen patch --help` for the full ops schema.
3. `patch` edits the file **in place** — the user just re-imports the same
   file. To inspect the result in recipe shape, run `helixgen view
   "<dir>/<slug>.hsp"` (read-only, JSON output) on the same path.
4. Surface any warnings (stderr, or the `--json` result's `warnings` — e.g.
   dropped params on a swap) to the user.

Prefer one `patch` call with multiple ops over several single-op verbs.
The `.hsp` file is the thing you mutate — the recipe is author-input
only and is not read back as truth.

### Addressing duplicate blocks

When a preset has two blocks with the same name (e.g. two IR "With Pan" blocks,
one per lane, or a volume block per split lane), reference the specific one by
its coordinate: add `"pos": N` (and `"lane": 0|1`, `"path": 0|1`) to the
patch operation or the snapshot/footswitch/expression reference. A bare
name only works when it is unique in the preset.

If `patch` or `view` refuses a preset (more than two parallel
splits, or an unknown routing block), tell the user it's an unsupported routing
shape rather than editing it blindly. If `patch` warns that an IR hash
was passed through unregistered, mention the user must `register-irs` that WAV
to edit it locally.
