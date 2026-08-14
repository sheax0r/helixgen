#!/usr/bin/env python3
"""Check an authored .hsp against the factory preset corpus.

Line 6's own preset designers are the reference. A param value outside what they
ever used **on the same model** is almost certainly an authoring mistake; a value
outside their interquartile band is a choice that should be deliberate.

Reads the `.hsp` directly (8-byte `rpshnosj` magic + JSON) rather than through
`helixgen view`, and back-fills every param the model declares, because `view`
omits any param equal to the model default — comparing a defaults-stripped
projection against a defaults-included corpus would silently skip half the
preset. Blocks are keyed by **model id**, which is how the corpus is keyed and
what makes a same-model (FAIL-worthy) comparison possible at all.

Run:    python3 envelope-check.py <preset.hsp> [more.hsp ...]
Needs:  data/factory-corpus.json (see tools/harvest-factory-corpus.py)
Exit:   1 if any param is outside the factory range for its own model, else 0.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = Path(os.environ.get("HELIXGEN_FACTORY_CORPUS",
                             HERE.parent / "data" / "factory-corpus.json"))
LIB = Path(os.environ.get("HELIXGEN_LIBRARY", Path.home() / ".helixgen" / "library"))
HELIXGEN = os.environ.get("HELIXGEN_BIN", "helixgen")
MIN_N = 3          # below this, a distribution is too thin to judge against
# params are stored as float32, so a value authored as 0.7 reads back as
# 0.69999998 — compare with a tolerance or every exact-match lands as a finding
EPS = 1e-5
HSP_MAGIC = b"rpshnosj"

# Params whose reference point is set by the MODEL FAMILY, not the category, so
# a CATEGORY-level comparison is meaningless: an IR block's Level defaults to
# -18 dB against a stock cab's 0.0. Same-model comparison is still done.
NO_CATEGORY_FALLBACK = {"Level", "Pan", "Delay"}


def read_hsp(path: Path):
    raw = path.read_bytes()
    return json.loads(raw[len(HSP_MAGIC):] if raw.startswith(HSP_MAGIC) else raw)


def category_index():
    blocks = LIB / "blocks"
    if not blocks.is_dir():
        sys.exit(f"no block library at {blocks} — set HELIXGEN_LIBRARY")
    idx = {}
    for cat_dir in blocks.iterdir():
        if cat_dir.is_dir():
            for f in cat_dir.glob("*.json"):
                d = json.loads(f.read_text())
                idx[d.get("model_id")] = cat_dir.name
    return idx


def model_meta(model_id, _cache={}):
    """Declared params for a model: {name: {min, max, default, internal}}."""
    if model_id not in _cache:
        r = subprocess.run([HELIXGEN, "show-block", model_id, "--json"],
                           capture_output=True, text=True, timeout=120,
                           env={**os.environ, "HELIXGEN_LIBRARY": str(LIB)})
        try:
            _cache[model_id] = json.loads(r.stdout).get("params", {})
        except (json.JSONDecodeError, ValueError):
            _cache[model_id] = {}
    return _cache[model_id]


def judge(val, d, same_model, where, hsp, is_default=False):
    """One value against one distribution -> zero or one finding.

    The full range (defaults included) decides whether a value is *possible*;
    the `moved` sub-distribution — instances a designer actually changed —
    decides whether it is *typical*. Judging "typical" against the full pool
    would compare a deliberate setting to a crowd of untouched defaults.
    """
    scope = "this model" if same_model else "the category"
    band = f"factory {d['min']:g}..{d['max']:g}, n={d['n']}, {scope}"
    if val < d["min"] - EPS or val > d["max"] + EPS:
        # only same-model evidence is strong enough to call a value wrong
        return (("FAIL" if same_model else "NOTE"), hsp, where, f"{val:g}",
                f"outside anything Line 6 shipped — {band}")
    if is_default:
        # the value IS the model's default. Leaving a knob alone is the single
        # most common factory behaviour (51 of 78 cabs never touch HighCut), so
        # it can't be atypical by definition — only the range check applies.
        return None
    design = d.get("moved") or d
    if "mode" in design:                # enum/index: min..max says nothing
        seen = [v for v, _ in design.get("frequencies", [])]
        if seen and not any(abs(val - v) <= EPS for v in seen):
            return ("NOTE", hsp, where, f"{val:g}",
                    f"not among the factory choices (mode {design['mode']:g}) — {band}")
    elif "p25" in design and (val < design["p25"] - EPS or val > design["p75"] + EPS):
        at_def = d.get("at_default")
        extra = (f"; {at_def} of {d['n']} factory instances leave this at the "
                 f"model default" if at_def else "")
        return ("NOTE", hsp, where, f"{val:g}",
                f"outside the band Line 6 uses when they set it "
                f"(p25-p75 {design['p25']:g}..{design['p75']:g}) — {band}{extra}")
    return None


def check(hsp, corpus, cat_idx):
    out, unknown = [], set()
    preset = read_hsp(Path(hsp)).get("preset") or {}
    for flow in preset.get("flow") or []:
        for key, entry in flow.items():
            if not (isinstance(entry, dict) and key.startswith("b")):
                continue
            for slot in entry.get("slot") or []:
                mid = slot.get("model")
                if not mid:
                    continue
                cat = cat_idx.get(mid)
                if cat is None:
                    unknown.add(mid)        # infrastructure block, or not in library
                    continue
                stored = slot.get("params") or {}
                for pname, pmeta in model_meta(mid).items():
                    if pmeta.get("internal"):
                        continue
                    raw = stored.get(pname, {})
                    values = [(raw.get("value", pmeta.get("default")), "")]
                    for i, sv in enumerate(raw.get("snapshots") or []):
                        if isinstance(sv, (int, float)) and not isinstance(sv, bool):
                            values.append((sv, f" (snapshot {i + 1})"))
                    d = corpus["by_model"].get(f"{cat}|{mid}", {}).get(pname)
                    same_model = bool(d and d["n"] >= MIN_N)
                    if not same_model:
                        if pname in NO_CATEGORY_FALLBACK:
                            continue
                        d = corpus["by_category"].get(cat, {}).get(pname)
                    if not d or d["n"] < MIN_N:
                        continue
                    dflt = pmeta.get("default")
                    for val, tag in values:
                        if isinstance(val, bool) or not isinstance(val, (int, float)):
                            continue
                        is_def = (isinstance(dflt, (int, float))
                                  and abs(float(val) - float(dflt))
                                  <= EPS * max(1.0, abs(float(dflt))))
                        f = judge(float(val), d, same_model,
                                  f"{key} {mid}.{pname}{tag}", str(hsp), is_def)
                        if f:
                            out.append(f)
    return out, unknown


def main():
    if len(sys.argv) < 2:
        sys.exit(f"usage: {Path(sys.argv[0]).name} <preset.hsp> [more.hsp ...]")
    if not CORPUS.exists():
        sys.exit(f"no factory corpus at {CORPUS} — set HELIXGEN_FACTORY_CORPUS")
    corpus = json.loads(CORPUS.read_text())
    cat_idx = category_index()
    fails = 0
    for hsp in sys.argv[1:]:
        rows, unknown = check(hsp, corpus, cat_idx)
        fails += sum(1 for r in rows if r[0] == "FAIL")
        print(f"\n== {Path(hsp).name}: {len(rows)} finding(s)")
        for level, _, where, val, why in sorted(rows):
            print(f"  {level}  {where} = {val}  {why}")
        if not rows:
            print("  inside the factory envelope on every param")
        if unknown:
            print(f"  (not in the block library, unchecked: {', '.join(sorted(unknown))})")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
