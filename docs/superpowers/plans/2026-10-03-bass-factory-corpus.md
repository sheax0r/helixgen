# Bass/Guitar Factory Corpus Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop bass presets from contaminating the guitar factory statistics, publish a separate bass corpus, and give the `tone` skill a bass section built from measured Line 6 bass presets.

**Architecture:** `tools/harvest-factory-corpus.py` sorts presets into guitar and bass by the `BAS` title prefix Line 6 gives its bass presets, then builds one corpus per instrument. Guitar keeps the existing file names, so `tools/envelope-check.py` and every existing skill reference stay valid. Bass gets `data/factory-corpus-bass.json` + `docs/factory-corpus-bass.md`, and envelope-check selects it through the existing `HELIXGEN_FACTORY_CORPUS` env var. Every number the `tone` skill cites is then re-measured against the guitar-only corpus, and a bass section is written from the bass corpus.

**Tech Stack:** Python 3 stdlib (harvester, scratch scripts), pytest (tests), `helixgen` CLI 0.52.1 (`device to-hsp`, `show-block`), Markdown skills.

**Spec:** No written spec. The design was agreed in conversation on 2026-10-03 and is summarized below. Background: the 66-preset factory corpus (PR #33, harvested at engine 0.47.2) contains 16 bass presets (`50-13C-BAS-Rock-Legends` … `65-17B-BAS-Live-n-Let-DI`). The harvester has no instrument filter, so the pooled `by_category` rows the tone skill quotes as guitar practice include bass amps, bass cabs and 21 bass DI blocks.

## Global Constraints

- Work in worktree `.worktrees/bass-corpus`, branch `bass-corpus`, cut from `origin/main` at `e934cd4` (release 5.0.1, engine 0.52.1). Fetch again before choosing the release number.
- **Never commit factory preset content.** Commit statistics only (`data/*.json`, `docs/*.md`). The converted `.hsp` files and the `.sbe` source stay in the scratchpad.
- Guitar corpus keeps its paths: `data/factory-corpus.json`, `docs/factory-corpus.md`. Bass corpus: `data/factory-corpus-bass.json`, `docs/factory-corpus-bass.md`.
- Bass classification rule: preset title (file stem with the `NN-BBS-` position prefix removed) starts with the token `BAS`. Nothing else is used: no model sniffing, no hand-kept list.
- Harvest with the pinned engine: `helixgen --version` must print `0.52.1`. If not, stop and run `uv tool install --force 'helixgen[device]==0.52.1'`.
- Factory source: `/Users/michael.shea/git/helixgen-core-wt/untranscode-fixes/tests/fixtures/device_content/` holds the 66 factory `.sbe` files (untracked fixtures). Confirm 66 files, 16 with `BAS` in the name. If the directory is missing or the counts differ, **stop and ask the user**. A re-export needs the hardware.
- Skills operate through the CLI. Skill text must not tell agents to read harvester source.
- Tests: `python3 -m pytest` from the worktree root (needs only pytest).
- Release: bump the version in **both** `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`. Never push tags or move `stable` by hand.
- Bass guidance is **corpus-derived and not ear-validated**. The skill must say so.

## Review Focus

1. **A guitar preset whose name contains "bass"** (e.g. a "Bassman" tone, `Brit-MegaGuitar`, `Badonkulous`) must classify as guitar. Only a leading `BAS` token counts. Pinned in Task 1 tests.
2. **Numbers that were never in the corpus JSON** (routing counts such as "59 of 66", "11 dual-amp", "17 split/join") get no automatic re-measurement. They must be recounted per instrument, not silently relabelled. Pinned by Task 3 Step 2's reproduction check.
3. **Engine drift and the split are confounded.** 0.52.1 `to-hsp` keeps dual-cab B slots that 0.47.2 dropped, so cab numbers move for two reasons. The diff report must separate the two (Task 2).
4. **A bass tone checked against the guitar envelope** produces confident FAILs on correct bass values. The skill must route bass tones to the bass corpus. Pinned by a Task 4 test.
5. **Hard-coded prose in `render_md`** (the "29 cabs … 13 cut to 8000 … 11750" example, the hgc-q38 "known gaps" paragraph) goes stale after re-harvest. It must be re-checked against new data, not trusted (Task 2 Step 6).

---

### Task 1: Instrument split in the harvester

**Files:**
- Modify: `tools/harvest-factory-corpus.py` (add `instrument_of`, `split_by_instrument`; extract `build_corpus` from `main`; `render_md` title)
- Create: `tests/test_harvest_corpus.py`

**Interfaces:**
- Produces: `instrument_of(name: str) -> str` (`"guitar"` | `"bass"`), `split_by_instrument(paths: list[Path]) -> dict[str, list[Path]]` (always both keys, order kept), `build_corpus(hsp_files, cat_idx, failed, warnings, instrument, ver) -> dict` (the corpus dict, now with an `"instrument"` key). `main()` writes `factory-corpus.json/.md` (guitar) and `factory-corpus-bass.json/.md` (bass) into `<out-dir>`.

- [ ] **Step 1: Write the failing tests**

`tests/test_harvest_corpus.py`:

```python
"""Instrument split in tools/harvest-factory-corpus.py.

Line 6 titles every factory bass preset `BAS …`; the harvester must route those
to the bass corpus and everything else to guitar, or bass amps/cabs/DIs leak
into the guitar baselines the tone skill quotes.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "harvest", REPO_ROOT / "tools" / "harvest-factory-corpus.py")
harvest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(harvest)


@pytest.mark.parametrize("name, expected", [
    ("50-13C-BAS-Rock-Legends.hsp", "bass"),
    ("65-17B-BAS-Live-n-Let-DI.sbe", "bass"),
    ("59-15D-BAS-Slap-City", "bass"),
    ("00-1A-Stadium-Rock-Rig.hsp", "guitar"),
    ("03-1D-Brit-MegaGuitar.hsp", "guitar"),
    ("10-3C-Badonkulous.hsp", "guitar"),
    ("99-1A-Bassman-Blues.hsp", "guitar"),   # "Bass" inside a word is not the BAS tag
    ("Rock-BAS-Thing.hsp", "guitar"),        # BAS must lead the title
])
def test_instrument_of(name: str, expected: str) -> None:
    assert harvest.instrument_of(name) == expected


def test_split_by_instrument_keeps_both_keys_and_order() -> None:
    files = [Path("01-1B-Double-Double.hsp"), Path("50-13C-BAS-Rock-Legends.hsp"),
             Path("02-1C-Plexiglass.hsp")]
    got = harvest.split_by_instrument(files)
    assert got == {"guitar": [files[0], files[2]], "bass": [files[1]]}
    assert harvest.split_by_instrument([]) == {"guitar": [], "bass": []}


@pytest.mark.parametrize("fname, instrument", [
    ("factory-corpus.json", "guitar"), ("factory-corpus-bass.json", "bass")])
def test_published_corpora_are_instrument_pure(fname: str, instrument: str) -> None:
    path = REPO_ROOT / "data" / fname
    if not path.exists():
        pytest.skip(f"{fname} not harvested yet")
    c = json.loads(path.read_text())
    assert c["instrument"] == instrument
    assert c["inputs"], "empty corpus"
    assert all(harvest.instrument_of(f) == instrument for f in c["inputs"])
```

(The third test skips until Task 2 publishes the data. Task 2 turns it into a real check.)

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_harvest_corpus.py -v`
Expected: FAIL with `AttributeError: module 'harvest' has no attribute 'instrument_of'`

- [ ] **Step 3: Implement**

Add after `enabled_of` in `tools/harvest-factory-corpus.py`:

```python
def instrument_of(name) -> str:
    """Line 6 titles every factory bass preset `BAS …` (file: NN-13C-BAS-Rock-Legends)."""
    title = re.sub(r"^\d+-\d+[A-Z]-", "", Path(name).stem)
    return "bass" if re.match(r"BAS\b", title) else "guitar"


def split_by_instrument(paths):
    out = {"guitar": [], "bass": []}
    for p in paths:
        out[instrument_of(Path(p).name)].append(p)
    return out
```

Then move everything in `main()` from `obs, kinds, ... = harvest(ok, cat_idx)` through the `corpus = {...}` literal into:

```python
def build_corpus(hsp_files, cat_idx, failed, warnings, instrument, ver):
    obs, kinds, model_use, family_use, presets, skipped = harvest(hsp_files, cat_idx)
    # ... the by_model / pooled / shapes / suppressed / by_cat block, unchanged ...
    return {
        "source": "Line 6 Helix Stadium factory setlist",
        "instrument": instrument,
        "engine": ver,
        "presets": len(presets),
        "inputs": sorted(p["file"] for p in presets),
        "failed_conversions": [f for f in failed if instrument_of(f["file"]) == instrument],
        # ... remaining keys unchanged ...
    }
```

Leave `conversion_warnings` as the whole-run counter (it describes the converter, not an instrument). Then `main()` becomes:

```python
def main():
    if len(sys.argv) < 3:
        sys.exit("usage: harvest-factory-corpus.py <sbe-dir> <out-dir>")
    sbe_dir, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)

    ok, failed, warnings = convert(sbe_dir, out_dir / "hsp")
    print(f"converted {len(ok)}, failed {len(failed)}")
    cat_idx = category_index()
    ver = sh([HELIXGEN, "--version"]).stdout.strip()
    for instrument, files in split_by_instrument(ok).items():
        corpus = build_corpus(files, cat_idx, failed, warnings, instrument, ver)
        stem = "factory-corpus" if instrument == "guitar" else f"factory-corpus-{instrument}"
        (out_dir / f"{stem}.json").write_text(json.dumps(corpus, indent=1))
        (out_dir / f"{stem}.md").write_text(render_md(corpus))
        print(f"{instrument}: presets={corpus['presets']} models={len(corpus['by_model'])} "
              f"skipped={sum(corpus['skipped_models'].values())} engine={ver}")
```

In `render_md`, change the title line to:

```python
    L = [f"# Factory preset corpus — {c['presets']} Line 6 Stadium factory "
         f"{c.get('instrument', 'guitar')} presets", "",
```

Update the module docstring's `Run:` line to say the script writes both corpora.

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_harvest_corpus.py -v`
Expected: 9 passed, 2 skipped.

- [ ] **Step 5: Commit**

```bash
git add tools/harvest-factory-corpus.py tests/test_harvest_corpus.py
git commit -m "feat(tools): split factory corpus by instrument (BAS-prefixed presets are bass)"
```

---

### Task 2: Re-harvest both corpora at engine 0.52.1, with a drift report

**Files:**
- Modify: `data/factory-corpus.json`, `docs/factory-corpus.md`
- Create: `data/factory-corpus-bass.json`, `docs/factory-corpus-bass.md`
- Modify (if the numbers moved): `tools/harvest-factory-corpus.py` `render_md` prose
- Scratch only (never committed): `$SCRATCH/harvest-mixed/`, `$SCRATCH/harvest-split/`, `$SCRATCH/drift.md`

**Interfaces:**
- Consumes: Task 1's harvester.
- Produces: the four committed corpus files, plus `$SCRATCH/drift.md`, the three-column table that Task 3 works from.

Set `SCRATCH` to the session scratchpad and `SBE=/Users/michael.shea/git/helixgen-core-wt/untranscode-fixes/tests/fixtures/device_content` in every command. Shell variables do not persist between agent Bash calls, so repeat them.

- [ ] **Step 1: Preflight**

```bash
helixgen --version                       # expect: helixgen, version 0.52.1
ls "$SBE"/*.sbe | wc -l                  # expect: 66
ls "$SBE"/*.sbe | grep -c -- '-BAS-'     # expect: 16
```

Any mismatch: stop and ask the user.

- [ ] **Step 2: Mixed baseline at 0.52.1 (old harvester)**

This isolates engine drift from the split:

```bash
git show e934cd4:tools/harvest-factory-corpus.py > "$SCRATCH/harvest-old.py"
HELIXGEN_LIBRARY="$PWD/data/library" python3 "$SCRATCH/harvest-old.py" "$SBE" "$SCRATCH/harvest-mixed"
```

Expected: `converted 66, failed 0`. If any conversion fails, stop and report the `failed_conversions` entries.

- [ ] **Step 3: Split harvest (new harvester)**

```bash
HELIXGEN_LIBRARY="$PWD/data/library" python3 tools/harvest-factory-corpus.py "$SBE" "$SCRATCH/harvest-split"
```

Expected: `guitar: presets=50 …` and `bass: presets=16 …`.

- [ ] **Step 4: Drift report**

Write `$SCRATCH/drift.py` and run it:

```python
"""committed(0.47.2 mixed) | 0.52.1 mixed | 0.52.1 guitar — every by_category row + amp family."""
import json, sys
from pathlib import Path
scratch = Path(sys.argv[1])
cols = {"committed": json.load(open("data/factory-corpus.json")),
        "mixed-0.52.1": json.load(open(scratch / "harvest-mixed/factory-corpus.json")),
        "guitar-0.52.1": json.load(open(scratch / "harvest-split/factory-corpus.json"))}

def fmt(d):
    if not d:
        return "-"
    mv = d.get("moved") or {}
    mid = mv.get("median", mv.get("mode"))
    band = f" {mv['p25']:g}-{mv['p75']:g}" if "p25" in mv else ""
    return (f"n={d['n']} def={d['at_default']} "
            f"moved={'-' if mid is None else format(mid, 'g')}{band}")

print("| row | " + " | ".join(cols) + " |\n|---|---|---|---|")
print("| amp family | " + " | ".join(str(c["amp_family_use"]) for c in cols.values()) + " |")
print("| presets | " + " | ".join(str(c["presets"]) for c in cols.values()) + " |")
cats = sorted({k for c in cols.values() for k in c["by_category"]})
for cat in cats:
    params = sorted({p for c in cols.values() for p in c["by_category"].get(cat, {})})
    for p in params:
        cells = [fmt(c["by_category"].get(cat, {}).get(p)) for c in cols.values()]
        if len(set(cells)) > 1:
            print(f"| {cat}.{p} | " + " | ".join(cells) + " |")
```

```bash
python3 "$SCRATCH/drift.py" "$SCRATCH" > "$SCRATCH/drift.md"; wc -l "$SCRATCH/drift.md"
```

Only rows that differ are printed. Column 1 → 2 is engine drift; column 2 → 3 is the bass contamination.

- [ ] **Step 5: Publish**

```bash
cp "$SCRATCH/harvest-split/factory-corpus.json"      data/factory-corpus.json
cp "$SCRATCH/harvest-split/factory-corpus-bass.json" data/factory-corpus-bass.json
cp "$SCRATCH/harvest-split/factory-corpus.md"        docs/factory-corpus.md
cp "$SCRATCH/harvest-split/factory-corpus-bass.md"   docs/factory-corpus-bass.md
git status --short   # must show ONLY those 4 files (+ Task 1 files if uncommitted) — no .hsp, no .sbe
```

- [ ] **Step 6: Fix stale `render_md` prose**

Two hard-coded passages in `render_md` must match the new guitar data:
- The "`HighCut` pools 29 cabs left wide open at 20100 with 13 deliberately cut to 8000 … median (11750)" example. Recompute from `data/factory-corpus.json` → `by_category.cab.HighCut` (`n`, `at_default`, `moved.mode`/`median`, overall `median`). Rewrite the sentence with the new numbers, or drop the specific counts if the example no longer shows the point (a pooled median that no preset actually uses).
- The "**Known gaps.** `device to-hsp` drops the second model slot of every two-slot cab block … (bead hgc-q38)" paragraph. Run `helixgen device to-hsp --help | grep -i "dual-cab"`. If 0.52.1 states that every model slot of a dual-cab block is kept, delete that sentence. Then re-check the "`amp Drive` snapshot-modulated on 21 of 60 amps" claim. It isn't in the JSON: either recount it with Task 3's `structure.py` (snapshot arrays on amp `Drive`) or remove the number.

Re-run Step 3 and Step 5 so the `.md` files pick up the new prose.

- [ ] **Step 7: Tests and commit**

Run: `python3 -m pytest -q`. Expected: all pass; `test_published_corpora_are_instrument_pure` now runs (no skips from it).

```bash
git add data/factory-corpus.json data/factory-corpus-bass.json docs/factory-corpus.md docs/factory-corpus-bass.md tools/harvest-factory-corpus.py
git commit -m "data: re-harvest factory corpus at engine 0.52.1, split guitar (50) / bass (16)"
```

Paste the full `$SCRATCH/drift.md` table into the commit body or the PR description. It is the evidence for Task 3.

---

### Task 3: Re-cite the guitar numbers in the `tone` skill

**Files:**
- Modify: `skills/tone/SKILL.md`
- Modify: `tests/test_skills.py`
- Scratch: `$SCRATCH/structure.py`

**Interfaces:**
- Consumes: `data/factory-corpus.json` (guitar), `$SCRATCH/drift.md`, `$SCRATCH/harvest-split/hsp/*.hsp`.

- [ ] **Step 1: List every cited number**

```bash
grep -nE "66|factory|corpus|of [0-9]+|[0-9]+ of|median|p25|p75" skills/tone/SKILL.md
```

On `origin/main` the cited numbers sit at about lines 158, 173–176, 200, 299–349, 388–449, 828–829, 1055, 1119–1122, 1181–1185 and 1207–1210. Make a checklist in `$SCRATCH/citations.md`, one line per claim: line number, quoted text, and source. The source is either a `by_category`/`by_model`/`model_use`/`amp_family_use` path in the JSON, or `structure`.

- [ ] **Step 2: Recount structural claims per instrument**

Routing claims ("59 of 66 use path 2", "11 dual-amp", "41 serial cascade", "17 split/join", mic-pick counts, stereo/mono counts) are not stored in the JSON. Write `$SCRATCH/structure.py`:

```python
"""Per-instrument structural counts over the converted factory .hsp files."""
import json, sys, re
from collections import Counter
from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location("h", "tools/harvest-factory-corpus.py")
h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)

INFRA = re.compile(r"^P35_")
def models(flow):
    for k, e in flow.items():
        if isinstance(e, dict) and k.startswith("b"):
            for s in e.get("slot") or []:
                if s.get("model"):
                    yield s["model"]

cat_idx = h.category_index()   # model_id -> category, from $HELIXGEN_LIBRARY
tally = {"all": Counter(), "guitar": Counter(), "bass": Counter()}
for f in sorted(Path(sys.argv[1]).glob("*.hsp")):
    p = h.read_hsp(f).get("preset") or {}
    flows = p.get("flow") or []
    ms = [list(models(fl)) for fl in flows]
    real = [[m for m in fm if not INFRA.match(m)] for fm in ms]
    # by library category, not name: "ZeroAmpBassDI" is a drive, not an amp
    amps = sum(1 for fm in real for m in fm if cat_idx.get(m) == "amp")
    feats = {
        "presets": True,
        "path2 has non-infra blocks": len(real) > 1 and bool(real[1]),
        "any split block": any(m.startswith("P35_AppDSPSplit") for fm in ms for m in fm),
        ">=2 amp blocks": amps >= 2,
        "path2 input none": len(ms) > 1 and "P35_InputNone" in ms[1],
    }
    for inst in ("all", h.instrument_of(f.name)):
        for k, v in feats.items():
            tally[inst][k] += bool(v)
for inst, c in tally.items():
    print(inst, dict(c))
```

```bash
HELIXGEN_LIBRARY="$PWD/data/library" python3 "$SCRATCH/structure.py" "$SCRATCH/harvest-split/hsp"
```

**Reproduction check:** the `all` row must reproduce the skill's current counts (59, 11, 41, 17). If a count does not reproduce, the feature definition above differs from the one the original author used. Adjust that one predicate until `all` matches, and note what you changed. **Do not quote a guitar number from a predicate that cannot reproduce the all-presets number.** If you can't reproduce it, reword the claim to "N of the 66 factory presets (guitar and bass)" and flag it in the PR description.

- [ ] **Step 3: Rewrite citations**

For every checklist line, replace the number with the guitar-corpus value and the denominator with the guitar count. For example, "Line 6's own 66 factory presets use **69 Agoura amp instances to 22 legacy**" becomes "Line 6's 50 factory guitar presets use **X Agoura … to Y legacy**", with X and Y from `amp_family_use`. When a rule's *direction* changes (e.g. a "leave it at default" row flips to "usually moved"), change the guidance text too, not just the digits, and list it under "Guidance changed" in the PR description.

- [ ] **Step 4: Scope the guitar-only advice**

- In the pickup table (step 5, "Amp-EQ tweaks"), replace the `Bass guitar` row with: `| Bass guitar | — | not a guitar tweak: see **Bass tones** (end of Workflow) |`.
- In step 10, change "**Boomy / flubby**" to start with "(guitar)". Add a line after it: `- **Bass "boomy / flubby"** → see **Bass tones**; do not raise cab LowCut into the fundamental`.

- [ ] **Step 5: Test: no stale denominators**

Add to `tests/test_skills.py`:

```python
def test_tone_skill_cites_guitar_corpus_not_mixed_66() -> None:
    """The 66-preset corpus mixed 16 bass presets into guitar baselines (2026-10-03)."""
    text = (SKILLS_ROOT / "tone" / "SKILL.md").read_text()
    corpus = json.loads((REPO_ROOT / "data" / "factory-corpus.json").read_text())
    assert corpus["instrument"] == "guitar"
    assert "66 factory presets" not in text
    assert f"{corpus['presets']} factory guitar presets" in text
```

Run: `python3 -m pytest tests/test_skills.py -q`. Expected: all pass. If `66 factory presets` still matches, Step 3 missed a citation; fix it. If Step 2 kept a deliberate "of the 66 factory presets (guitar and bass)" wording, that string does not match `66 factory presets`, which is intended.

- [ ] **Step 6: Commit**

```bash
git add skills/tone/SKILL.md tests/test_skills.py
git commit -m "fix(tone): re-cite factory numbers against the guitar-only corpus"
```

---

### Task 4: Bass section in the `tone` skill

**Files:**
- Modify: `skills/tone/SKILL.md` (gate in step 1; new `### Bass tones` subsection after step 10, before `## Common Mistakes`; bass sentence in 7b)
- Modify: `tests/test_skills.py`
- Scratch: `$SCRATCH/bass_facts.py`

**Interfaces:**
- Consumes: `data/factory-corpus-bass.json`, `$SCRATCH/harvest-split/hsp/*BAS*.hsp`, `structure.py`'s `models()` approach.

- [ ] **Step 1: Write the failing test**

```python
def test_tone_skill_has_a_measured_bass_section() -> None:
    text = (SKILLS_ROOT / "tone" / "SKILL.md").read_text()
    assert "### Bass tones" in text
    bass = text.split("### Bass tones", 1)[1].split("\n## ", 1)[0]
    # routed to the bass envelope, never the guitar one
    assert "HELIXGEN_FACTORY_CORPUS" in bass and "factory-corpus-bass.json" in bass
    assert "factory-corpus-bass.md" in bass
    # the guitar boomy fix must not leak in
    assert "LowCut" in bass
    # honest provenance
    assert "not ear-validated" in bass.lower() or "not yet ear-validated" in bass.lower()
    # gate early in the workflow so the agent reads it before picking blocks
    assert text.index("Bass tones") < text.index("### 3. Pick blocks from the library")
```

Run: `python3 -m pytest tests/test_skills.py::test_tone_skill_has_a_measured_bass_section -v`. Expected: FAIL.

- [ ] **Step 2: Extract the bass facts**

`$SCRATCH/bass_facts.py`:

```python
"""Print the measured bass facts the skill section is written from."""
import json, re, sys
from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location("h", "tools/harvest-factory-corpus.py")
h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)
c = json.load(open("data/factory-corpus-bass.json"))
print("PRESETS", c["presets"], "| amp family", c["amp_family_use"])
print("\nMODEL USE (bass)")
for k, n in c["model_use"].items():
    if not k.split(":")[1].startswith("P35_"):
        print(f"  {n:3d}  {k}")
print("\nBY_MODEL rows (amp, cab, drive, dynamics, eq)")
KEEP = {"amp": ["Drive", "Master", "MasterVol", "Level", "Bass", "Mid", "Treble", "Presence", "Hype"],
        "cab": ["Mic", "Distance", "HighCut", "LowCut", "Level"],
        "drive": ["Gain", "Level", "Blend", "Bass", "Treble"],
        "dynamics": ["Threshold", "Ratio", "Level", "Mix"], "eq": None}
for key, params in c["by_model"].items():
    cat, mid = key.split("|")
    if cat not in KEEP:
        continue
    for p, d in params.items():
        if KEEP[cat] is not None and p not in KEEP[cat]:
            continue
        mv = d.get("moved") or {}
        print(f"  {mid:40s} {p:10s} n={d['n']} def={d['at_default']} "
              f"all={d.get('median', d.get('mode'))} moved={mv.get('median', mv.get('mode'))} "
              f"band={mv.get('p25','-')}..{mv.get('p75','-')} range={d['min']:g}..{d['max']:g}")
print("\nCHAINS (path: blocks in order; | marks a split)")
for f in sorted(Path(sys.argv[1]).glob("*BAS*.hsp")):
    p = h.read_hsp(f).get("preset") or {}
    print(f.stem)
    for i, fl in enumerate(p.get("flow") or []):
        seq = []
        for k in sorted((k for k in fl if k.startswith("b")), key=lambda k: int(k[1:]) if k[1:].isdigit() else 0):
            for s in (fl[k].get("slot") or []):
                m = s.get("model") or ""
                if m.startswith("P35_AppDSPSplit"): seq.append("|split")
                elif m.startswith("P35_AppDSPJoin"): seq.append("join|")
                elif m and not m.startswith("P35_"): seq.append(m.replace("HD2_", "").replace("Agoura_", ""))
        if seq:
            print(f"  path{i+1}: " + " > ".join(seq))
```

```bash
python3 "$SCRATCH/bass_facts.py" "$SCRATCH/harvest-split/hsp" > "$SCRATCH/bass_facts.txt"
```

Block order inside a flow follows the `bNN` keys. If the chains print in an implausible order (a cab before its amp in most presets), the key ordering is wrong. Check one preset with `helixgen view <file>.hsp` and fix the sort before going on.

- [ ] **Step 3: Write the section**

Add the gate to step 1 (Clarify), as the first bullet after "Common gaps:":

```markdown
- **Bass guitar?** If the instrument is a bass (the user says so, or the profile's
  `type` is `"bass"` in `helixgen library show <guitar> --json`), read
  **Bass tones** (end of the Workflow) before step 3. Several guitar rules in
  steps 3–10 do not apply to bass.
```

Add `### Bass tones` immediately before `## Common Mistakes`. Write it from `$SCRATCH/bass_facts.txt` alone; every number must trace to that file. Required content, in this order:

1. **Provenance line:** "Measured from Line 6's N factory bass presets (`${CLAUDE_PLUGIN_ROOT}/docs/factory-corpus-bass.md`); not yet ear-validated on hardware."
2. **Amps:** the bass amp models the factory uses, with use counts, Agoura first, display names from `helixgen show-block <model_id> --json`. Then say plainly: when the instrument is a bass, pick from these, never from the guitar Agoura list.
3. **Cabs and mics:** bass cab models and counts; the factory's mic picks on bass cabs if `by_model` has rows for `Mic`.
4. **The factory bass layout:** describe the chain patterns `CHAINS` shows (how many presets blend a DI with an amp/cab in a split, where the DI blocks `RegalBassDI`/`ZeroAmpBassDI` sit, whether a compressor leads, whether an octaver appears). Show it in helixgen's own recipe vocabulary, using the split/join shapes step 5 already documents ("Signal-flow params" / "Two paths"). Use the same field names as those sections; do not invent new ones.
5. **Starting values table:** `| block / param | factory (moved median, p25–p75, n) | note |` for every row in `BY_MODEL` with `n >= 3`. Where `at_default` is the majority, the note says "leave at default".
6. **Guitar rules that do not apply:** cab `LowCut` (quote the bass corpus's cab `LowCut` row; the guitar "boomy → raise LowCut" fix cuts the fundamental); the guitar pickup table; guitar Agoura picks.
7. **Envelope check for bass**, exact command:

   ```bash
   HELIXGEN_LIBRARY="${CLAUDE_PLUGIN_ROOT}/data/library" \
   HELIXGEN_FACTORY_CORPUS="${CLAUDE_PLUGIN_ROOT}/data/factory-corpus-bass.json" \
     python3 "${CLAUDE_PLUGIN_ROOT}/tools/envelope-check.py" <path-to>/<variant-slug>.hsp
   ```

In step 7b, after the existing command block, add one sentence: "**Bass tone?** Check against the bass corpus instead (command in **Bass tones**). The guitar envelope FAILs correct bass values."

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest -q`. Expected: all pass.

- [ ] **Step 5: Smoke-run the bass envelope on a factory bass preset**

```bash
HELIXGEN_LIBRARY="$PWD/data/library" HELIXGEN_FACTORY_CORPUS="$PWD/data/factory-corpus-bass.json" \
  python3 tools/envelope-check.py "$SCRATCH/harvest-split/hsp/59-15D-BAS-Slap-City.hsp"; echo "exit=$?"
HELIXGEN_LIBRARY="$PWD/data/library" \
  python3 tools/envelope-check.py "$SCRATCH/harvest-split/hsp/59-15D-BAS-Slap-City.hsp"; echo "exit=$?"
```

Expected: the first (bass corpus) exits 0. A factory preset sits inside its own corpus by construction. The second (guitar corpus) prints FAIL/NOTE lines or "unknown model" lines. Put both outputs in the PR description: the second one shows why the routing matters.

- [ ] **Step 6: Commit**

```bash
git add skills/tone/SKILL.md tests/test_skills.py
git commit -m "feat(tone): bass section measured from Line 6's factory bass presets"
```

---

### Task 5: Review, release, PR

**Files:**
- Modify: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`

- [ ] **Step 1: Adversarial review**

Dispatch at least one independent review subagent. Brief: break this change. Check every number in the `tone` skill diff against `data/factory-corpus*.json` and `$SCRATCH/drift.md`. Hunt for guitar guidance still built on mixed data, bass guidance with no corpus source, any committed preset content (`git diff origin/main --stat` must list no `.hsp`/`.sbe`), and classification edge cases. Fix confirmed findings or defer them explicitly in the PR description.

- [ ] **Step 2: Version bump**

```bash
git fetch origin && git log --oneline -1 origin/main && git tag -l 'helixgen--v*' --sort=-v:refname | head -1
```

Next minor over the latest tag (5.1.0 if 5.0.1 is still latest). Set it in both `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`. Run `python3 -m pytest -q` (`test_plugin_and_marketplace_versions_agree`).

```bash
git add .claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "release 5.1.0 — guitar/bass factory corpus split, measured bass guidance"
```

- [ ] **Step 3: Rebase, push, PR**

```bash
git fetch origin && git rebase origin/main && python3 -m pytest -q
git push -u origin bass-corpus
gh pr create --title "release 5.1.0 — guitar/bass factory corpus split, measured bass guidance" --body-file "$SCRATCH/pr-body.md"
```

PR body: why (16 BAS presets pooled into guitar baselines), the drift table, "Guidance changed" list, Task 3 Step 2 reproduction notes, Task 4 Step 5 outputs, review findings and their disposition, and "bass guidance not ear-validated". End the body with the attribution footer the session's system reminder specifies, if any.

Merge only on the user's go-ahead.
