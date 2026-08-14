#!/usr/bin/env python3
"""Check an authored .hsp against the factory preset corpus.

Line 6's own preset designers are the reference: a param value outside what they
ever used on 66 factory presets is almost certainly an authoring mistake, and a
value outside their interquartile band is a choice that should be deliberate.

Run:    python3 envelope-check.py <preset.hsp> [more.hsp ...]
Needs:  data/factory-corpus.json (see tools/harvest-factory-corpus.py)
Exit:   1 if any param is outside the factory min..max, else 0.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = Path(os.environ.get("HELIXGEN_FACTORY_CORPUS",
                             HERE.parent / "data" / "factory-corpus.json"))
LIB = os.environ.get("HELIXGEN_LIBRARY", str(Path.home() / ".helixgen" / "library"))
MIN_N = 3          # below this, a distribution is too thin to judge against


def model_index():
    idx = {}
    for cat_dir in (Path(LIB) / "blocks").iterdir():
        if cat_dir.is_dir():
            for f in cat_dir.glob("*.json"):
                d = json.loads(f.read_text())
                idx[d.get("display_name")] = cat_dir.name
    return idx


def check(hsp, corpus, idx):
    env = {**os.environ, "HELIXGEN_LIBRARY": LIB}
    r = subprocess.run(["helixgen", "view", str(hsp)], capture_output=True,
                       text=True, env=env, timeout=120)
    if r.returncode != 0:
        return [("FAIL", str(hsp), "", "", f"view failed: {r.stderr.strip()[:120]}")]
    v = json.loads(r.stdout)
    out = []
    for pi, p in enumerate(v.get("paths", [])):
        for bi, b in enumerate(p.get("blocks", [])):
            name = b.get("block")
            if not name:
                continue
            cat = idx.get(name, "unknown")
            for k, val in (b.get("params") or {}).items():
                if isinstance(val, bool) or not isinstance(val, (int, float)):
                    continue
                # Same-model evidence is the only thing strong enough to call a
                # value wrong: the same param name can carry a different unit or
                # default in a different model of the same category (an IR block
                # defaults Level to -18 dB, a stock cab to 0.0). Category-level
                # stats are a weaker signal, so they only ever produce a NOTE.
                d = corpus["by_model"].get(f"{cat}|{name}", {}).get(k)
                same_model = bool(d and d["n"] >= MIN_N)
                if not same_model:
                    d = corpus["by_category"].get(cat, {}).get(k)
                if not d or d["n"] < MIN_N:
                    continue
                # disambiguate duplicate display names (two IR cabs, etc)
                where = f"{name}[{pi}.{bi}].{k}"
                scope = "this model" if same_model else f"the {cat} category"
                band = (f"factory {d['min']:g}..{d['max']:g} "
                        f"(p25-p75 {d['p25']:g}..{d['p75']:g}, n={d['n']}, {scope})")
                if val < d["min"] or val > d["max"]:
                    out.append(("FAIL" if same_model else "NOTE", str(hsp), where,
                                f"{val:g}", f"outside anything Line 6 shipped — {band}"))
                elif val < d["p25"] or val > d["p75"]:
                    out.append(("NOTE", str(hsp), where, f"{val:g}",
                                f"outside the typical band — {band}"))
    return out


def main():
    if not CORPUS.exists():
        sys.exit(f"no corpus at {CORPUS}")
    corpus = json.loads(CORPUS.read_text())
    idx = model_index()
    fails = 0
    for hsp in sys.argv[1:]:
        rows = check(hsp, corpus, idx)
        fails += sum(1 for r in rows if r[0] == "FAIL")
        print(f"\n== {Path(hsp).name}: {len(rows)} finding(s)")
        for level, _, where, val, why in sorted(rows):
            print(f"  {level}  {where} = {val}  {why}")
        if not rows:
            print("  inside the factory envelope on every param")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
