#!/usr/bin/env python3
"""Harvest Line 6 factory Stadium presets into a parameter-distribution corpus.

Input:  a directory of .sbe backups (helixgen device backup --setlist factory)
Output: <out>/hsp/*.hsp        converted presets
        <out>/factory-corpus.json   per-model + per-category param distributions
        <out>/factory-corpus.md     human/agent-readable reference

Run:    python3 harvest.py <sbe-dir> <out-dir>
"""
import json
import subprocess
import sys
import statistics
from pathlib import Path
from collections import defaultdict

LIB = str(Path.home() / ".helixgen" / "library")


def sh(args, **kw):
    return subprocess.run(args, capture_output=True, text=True, timeout=180, **kw)


def convert(sbe_dir: Path, hsp_dir: Path):
    """.sbe -> .hsp via `helixgen device to-hsp` (offline file conversion)."""
    hsp_dir.mkdir(parents=True, exist_ok=True)
    ok, failed = [], []
    for sbe in sorted(sbe_dir.glob("*.sbe")):
        out = hsp_dir / (sbe.stem + ".hsp")
        if out.exists():
            ok.append(out)
            continue
        r = sh(["helixgen", "device", "to-hsp", str(sbe), "-o", str(out),
                "--library", LIB, "--no-verify"])
        (ok if r.returncode == 0 and out.exists() else failed).append(
            out if r.returncode == 0 else (sbe.name, r.stderr.strip()[:200]))
    return ok, failed


def model_index():
    """display_name -> (model_id, category) from the block library."""
    idx = {}
    blocks = Path(LIB) / "blocks"
    for cat_dir in blocks.iterdir():
        if not cat_dir.is_dir():
            continue
        for f in cat_dir.glob("*.json"):
            d = json.loads(f.read_text())
            idx[d.get("display_name")] = (d.get("model_id"), cat_dir.name)
    return idx


def harvest(hsp_files, idx):
    """Collect param values per (category, model) and per category."""
    by_model = defaultdict(lambda: defaultdict(list))   # model -> param -> values
    by_cat = defaultdict(lambda: defaultdict(list))     # category -> param -> values
    model_use = defaultdict(int)
    family_use = defaultdict(int)
    presets = []

    for f in hsp_files:
        r = sh(["helixgen", "view", str(f)], env={**__import__("os").environ,
                                                  "HELIXGEN_LIBRARY": LIB})
        if r.returncode != 0:
            continue
        try:
            v = json.loads(r.stdout)
        except json.JSONDecodeError:
            continue
        info = {"file": Path(f).name, "blocks": 0, "paths": 0, "snapshots":
                len(v.get("snapshots") or [])}
        for p in v.get("paths", []):
            info["paths"] += 1
            for b in p.get("blocks", []):
                name = b.get("block", "")
                mid, cat = idx.get(name, (None, "unknown"))
                info["blocks"] += 1
                model_use[f"{cat}:{name}"] += 1
                if cat == "amp":
                    family_use["Agoura" if str(mid).startswith("Agoura")
                               else "legacy"] += 1
                for k, val in (b.get("params") or {}).items():
                    if isinstance(val, (int, float)) and not isinstance(val, bool):
                        by_model[f"{cat}|{name}"][k].append(float(val))
                        by_cat[cat][k].append(float(val))
        presets.append(info)
    return by_model, by_cat, model_use, family_use, presets


def dist(vals):
    vals = sorted(vals)
    n = len(vals)

    def pct(p):
        if n == 1:
            return vals[0]
        i = min(n - 1, max(0, int(round(p * (n - 1)))))
        return vals[i]
    return {"n": n, "min": vals[0], "p25": pct(.25), "median": statistics.median(vals),
            "p75": pct(.75), "max": vals[-1]}


def main():
    sbe_dir, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    hsp_dir = out_dir / "hsp"

    ok, failed = convert(sbe_dir, hsp_dir)
    print(f"converted {len(ok)} presets, {len(failed)} failed")
    for f in failed:
        print("  FAILED", f)

    idx = model_index()
    by_model, by_cat, model_use, family_use, presets = harvest(ok, idx)

    corpus = {
        "source": "Line 6 Helix Stadium factory setlist",
        "presets": len(presets),
        "amp_family_use": dict(family_use),
        "model_use": dict(sorted(model_use.items(), key=lambda kv: -kv[1])),
        "preset_shape": dist([p["blocks"] for p in presets]) if presets else {},
        "snapshot_count": dist([p["snapshots"] for p in presets]) if presets else {},
        "by_category": {c: {k: dist(v) for k, v in sorted(ps.items())}
                        for c, ps in sorted(by_cat.items())},
        "by_model": {m: {k: dist(v) for k, v in sorted(ps.items())}
                     for m, ps in sorted(by_model.items())},
    }
    (out_dir / "factory-corpus.json").write_text(json.dumps(corpus, indent=1))

    # markdown reference: the params the tone skill actually reasons about
    KEY = {"amp": ["Drive", "NormDrv", "BrightDrv", "Master", "ChVol", "Level",
                   "Hype", "Channel", "Sag", "Ripple", "Bias", "BiasX", "ZPrePost",
                   "Bass", "Mid", "Treble", "Presence"],
           "cab": ["Distance", "Angle", "Position", "Mic", "HighCut", "LowCut",
                   "Level", "Pan"],
           "delay": ["Mix", "Feedback", "Time"],
           "reverb": ["Mix", "Decay", "PreDelay"],
           "drive": ["Gain", "Level", "Tone"],
           "dynamics": ["Level", "Threshold", "Mix"]}
    lines = [f"# Factory preset corpus — {len(presets)} Line 6 Stadium factory presets", "",
             "Measured from the device's own factory setlist. These are the",
             "distributions the tone skill's defaults should sit inside.", "",
             f"**Amp model family:** {dict(family_use)}", "",
             f"**Blocks per preset:** {corpus['preset_shape']}", "",
             f"**Snapshots per preset:** {corpus['snapshot_count']}", ""]
    for cat, params in KEY.items():
        if cat not in corpus["by_category"]:
            continue
        lines += [f"## {cat}", "", "| param | n | min | p25 | median | p75 | max |",
                  "|---|---|---|---|---|---|---|"]
        for p in params:
            d = corpus["by_category"][cat].get(p)
            if d:
                lines.append(f"| {p} | {d['n']} | {d['min']:g} | {d['p25']:g} | "
                             f"{d['median']:g} | {d['p75']:g} | {d['max']:g} |")
        lines.append("")
    (out_dir / "factory-corpus.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {out_dir}/factory-corpus.json and .md")


if __name__ == "__main__":
    main()
