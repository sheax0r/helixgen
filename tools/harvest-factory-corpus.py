#!/usr/bin/env python3
"""Harvest Line 6 factory Stadium presets into a parameter-distribution corpus.

Reads the converted `.hsp` files directly (8-byte `rpshnosj` magic + JSON). Param
metadata comes from `helixgen show-block --json` — the public CLI, so this runs
anywhere the pinned engine is installed, with no engine-internal imports.

THE THING THAT MAKES THIS USABLE: every row separates values the designer LEFT AT
THE MODEL DEFAULT from values they deliberately MOVED. Pool them and you get
medians that describe nobody — factory `cab HighCut` "median 11750" is the
midpoint between 29 cabs left wide open at 20100 and 13 cut to 8000, and occurs
zero times in the corpus. `moved_*` is the design signal; `at_default` is how
often the answer is "leave it alone".

Also recorded: bypass state (most factory drive/delay blocks are OFF at load, and
their values run ~20% different), integer/enum params as mode+frequencies rather
than medians, and the conversion warnings.

Run:    python3 harvest-factory-corpus.py <sbe-dir> <out-dir>
"""
import json
import os
import re
import subprocess
import sys
import statistics
from pathlib import Path
from collections import defaultdict, Counter

LIB = Path(os.environ.get("HELIXGEN_LIBRARY", Path.home() / ".helixgen" / "library"))
HELIXGEN = os.environ.get("HELIXGEN_BIN", "helixgen")
MIN_N_QUANTILE = 8      # below this, no quartiles — an IQR over 3 points is theatre
MIN_N_PUBLISH = 3       # below this, a by_model row is one preset's values verbatim
EPS = 1e-5              # params are float32; 0.3 reads back as 0.30000001
HSP_MAGIC = b"rpshnosj"
# effects whose base bypass state changes what a value means
BYPASSABLE = {"drive", "delay", "reverb", "modulation", "pitch", "filter", "dynamics"}


def sh(args):
    return subprocess.run(args, capture_output=True, text=True, timeout=180,
                          env={**os.environ, "HELIXGEN_LIBRARY": str(LIB)})


def read_hsp(path: Path):
    raw = path.read_bytes()
    return json.loads(raw[len(HSP_MAGIC):] if raw.startswith(HSP_MAGIC) else raw)


def convert(sbe_dir: Path, hsp_dir: Path):
    """.sbe -> .hsp, KEEPING the warning channel (silence means nothing lost)."""
    hsp_dir.mkdir(parents=True, exist_ok=True)
    ok, failed, warnings = [], [], Counter()
    for sbe in sorted(sbe_dir.glob("*.sbe")):
        out = hsp_dir / (sbe.stem + ".hsp")
        r = sh([HELIXGEN, "device", "to-hsp", str(sbe), "-o", str(out),
                "--library", str(LIB), "--no-verify"])
        if r.returncode != 0 or not out.exists():
            failed.append({"file": sbe.name, "error": (r.stderr or "").strip()[:200]})
            continue
        ok.append(out)
        for line in (r.stderr or "").splitlines():
            if line.startswith("warning:"):
                warnings[re.sub(r"\b\d+\b", "N", line)] += 1
    return ok, failed, warnings


def category_index():
    idx = {}
    for cat_dir in (LIB / "blocks").iterdir():
        if cat_dir.is_dir():
            for f in cat_dir.glob("*.json"):
                idx[json.loads(f.read_text()).get("model_id")] = cat_dir.name
    return idx


def model_meta(model_id, _cache={}):
    """{param: {min,max,default,type,internal}} straight from the CLI."""
    if model_id not in _cache:
        r = sh([HELIXGEN, "show-block", model_id, "--json"])
        try:
            _cache[model_id] = json.loads(r.stdout).get("params", {})
        except (json.JSONDecodeError, ValueError):
            _cache[model_id] = {}
    return _cache[model_id]


def enabled_of(obj):
    e = (obj or {}).get("@enabled")
    return bool(e.get("value", True)) if isinstance(e, dict) else True


def harvest(hsp_files, cat_idx):
    # key -> param -> list of (value, at_default, enabled)
    obs = defaultdict(lambda: defaultdict(list))
    kinds = defaultdict(dict)          # key -> param -> "int"/"float"
    model_use, family_use = Counter(), Counter()
    skipped = Counter()
    presets = []

    for f in hsp_files:
        preset = read_hsp(Path(f)).get("preset") or {}
        nblocks = 0
        for flow in preset.get("flow") or []:
            for bkey, entry in flow.items():
                if not (isinstance(entry, dict) and bkey.startswith("b")):
                    continue
                block_on = enabled_of(entry)
                for slot in entry.get("slot") or []:
                    mid = slot.get("model")
                    if not mid:
                        continue
                    cat = cat_idx.get(mid)
                    if cat is None:
                        skipped[mid] += 1
                        continue
                    nblocks += 1
                    model_use[f"{cat}:{mid}"] += 1
                    if cat == "amp":
                        family_use["Agoura" if mid.startswith("Agoura")
                                   else "legacy"] += 1
                    on = block_on and enabled_of(slot)
                    stored = slot.get("params") or {}
                    key = f"{cat}|{mid}"
                    for pname, pmeta in model_meta(mid).items():
                        if pmeta.get("internal"):
                            continue
                        raw = stored.get(pname)
                        val = raw.get("value") if isinstance(raw, dict) else None
                        if val is None:
                            val = pmeta.get("default")
                        if val is None:
                            continue
                        if isinstance(val, bool):     # a switch: count it as 0/1
                            val, is_int = float(val), True
                        elif isinstance(val, (int, float)):
                            is_int = pmeta.get("type") == "int" or isinstance(val, int)
                            val = float(val)
                        else:
                            continue
                        dflt = pmeta.get("default")
                        dflt = float(dflt) if isinstance(dflt, (int, float, bool)) else None
                        at_default = dflt is not None and abs(val - dflt) <= EPS * max(1.0, abs(dflt))
                        obs[key][pname].append((val, at_default, on))
                        kinds[key][pname] = "int" if is_int else "float"
        named = [s for s in (preset.get("snapshots") or [])
                 if isinstance(s, dict) and not re.fullmatch(
                     r"(SNAPSHOT|Snap)\s*\d+", str(s.get("name", "")).strip(), re.I)]
        presets.append({"file": Path(f).name, "blocks": nblocks,
                        "named_snapshots": len(named)})
    return obs, kinds, model_use, family_use, presets, skipped


def summarise(vals, categorical):
    """vals: list of floats. -> n/min/max plus median+quartiles or mode+freqs."""
    if not vals:
        return None
    vals = sorted(vals)
    out = {"n": len(vals), "min": vals[0], "max": vals[-1]}
    if categorical:
        top = Counter(vals).most_common(4)
        out["mode"] = top[0][0]
        out["frequencies"] = [[v, c] for v, c in top]
    else:
        out["median"] = statistics.median(vals)
        if len(vals) >= MIN_N_QUANTILE:
            q = statistics.quantiles(vals, n=4, method="inclusive")
            out["p25"], out["p75"] = q[0], q[2]
    return out


def row(entries, categorical):
    """One published row: everything, plus the MOVED subset and the ON subset."""
    allv = [v for v, _, _ in entries]
    moved = [v for v, d, _ in entries if not d]
    on = [v for v, _, o in entries if o]
    r = summarise(allv, categorical)
    r["at_default"] = len(allv) - len(moved)
    if moved:
        r["moved"] = summarise(moved, categorical)
    if on and len(on) != len(allv):
        r["enabled_only"] = summarise(on, categorical)
    return r


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: harvest-factory-corpus.py <sbe-dir> <out-dir>")
    sbe_dir, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)

    ok, failed, warnings = convert(sbe_dir, out_dir / "hsp")
    print(f"converted {len(ok)}, failed {len(failed)}")
    cat_idx = category_index()
    obs, kinds, model_use, family_use, presets, skipped = harvest(ok, cat_idx)

    by_model, by_cat = {}, {}
    pooled = defaultdict(lambda: defaultdict(list))
    shapes = defaultdict(lambda: defaultdict(set))
    for key, params in obs.items():
        cat, mid = key.split("|", 1)
        meta = model_meta(mid)
        for pname, entries in params.items():
            cat_flag = kinds[key][pname] == "int"
            if len(entries) >= MIN_N_PUBLISH:
                by_model.setdefault(key, {})[pname] = row(entries, cat_flag)
            m = meta.get(pname, {})
            shapes[cat][pname].add((m.get("type"), m.get("min"), m.get("max"),
                                    cat_flag))
            pooled[cat][pname].extend(entries)
    suppressed = {}
    for cat, params in pooled.items():
        for pname, entries in params.items():
            if len({s[:1] + s[1:3] for s in shapes[cat][pname]}) > 1:
                suppressed.setdefault(cat, {})[pname] = (
                    f"{len(shapes[cat][pname])} incompatible declared ranges across "
                    f"models — a pooled value would be a unit mixture")
                continue
            by_cat.setdefault(cat, {})[pname] = row(
                entries, any(s[3] for s in shapes[cat][pname]))

    ver = sh([HELIXGEN, "--version"]).stdout.strip()
    corpus = {
        "source": "Line 6 Helix Stadium factory setlist",
        "engine": ver,
        "presets": len(presets),
        "inputs": sorted(p["file"] for p in presets),
        "failed_conversions": failed,
        "method": ("parsed from the .hsp directly (to-hsp writes every param the "
                   "model declares); each row separates values left at the model "
                   "default from values the designer moved"),
        "conversion_warnings": dict(warnings.most_common()),
        "skipped_models": dict(skipped.most_common()),
        "amp_family_use": dict(family_use),
        "model_use": dict(model_use.most_common()),
        "blocks_per_preset": summarise([p["blocks"] for p in presets], False),
        "named_snapshots_per_preset": summarise(
            [p["named_snapshots"] for p in presets], False),
        "by_category": {c: dict(sorted(ps.items())) for c, ps in sorted(by_cat.items())},
        "by_category_suppressed": suppressed,
        "by_model": {k: dict(sorted(v.items())) for k, v in sorted(by_model.items())},
    }
    (out_dir / "factory-corpus.json").write_text(json.dumps(corpus, indent=1))
    (out_dir / "factory-corpus.md").write_text(render_md(corpus))
    print(f"models={len(by_model)} skipped={sum(skipped.values())} "
          f"warnings={sum(warnings.values())} engine={ver}")


def cell(d, key="median"):
    if d is None:
        return "-"
    if "mode" in d:
        return f"mode {d['mode']:g}"
    v = d.get(key)
    return "-" if v is None else f"{v:g}"


def render_md(c):
    KEY = {"amp": ["Drive", "Master", "MasterVol", "Level", "Hype", "Channel",
                   "Sag", "ZPrePost", "Bass", "Mid", "Treble", "Presence"],
           "cab": ["Distance", "Angle", "Position", "Mic", "HighCut", "LowCut",
                   "Level", "Pan"],
           "drive": ["Gain", "Level", "Tone"],
           "delay": ["Mix", "Feedback", "Time"],
           "reverb": ["Mix", "Decay", "PreDelay"],
           "dynamics": ["Level", "Threshold", "Mix"]}
    L = [f"# Factory preset corpus — {c['presets']} Line 6 Stadium factory presets", "",
         "What Line 6's own preset designers actually do, measured from the",
         f"Stadium's factory setlist. Engine: `{c['engine']}`.", "",
         "## How to read a row — this matters more than the numbers",
         "",
         "**`at_default` is half the answer.** Each row counts every instance of the",
         "param, including the ones nobody touched. A median over that pool describes",
         "no real preset: cab `HighCut` pools 29 cabs left wide open at 20100 with 13",
         "deliberately cut to 8000, and the resulting median (11750) occurs **zero**",
         "times in the corpus. So each row also carries:",
         "",
         "- **`at_default`** — how many of the `n` instances sit on the model's own",
         "  default. High `at_default` means the factory answer is *leave it alone*.",
         "- **`moved`** — the distribution over the instances a designer actually",
         "  changed. **This is the design signal.** Use it when you have decided to",
         "  set the param at all.",
         "- **`enabled_only`** — for effect blocks, the distribution over instances",
         "  that are ON in the preset's base state. Most factory drive and delay",
         "  blocks are bypassed at load (engaged by snapshot or footswitch), and",
         "  their values differ by ~20% from the bypassed ones.",
         "",
         "Integer and switch params report **mode + frequencies**, never a median —",
         "a median mic index is meaningless and a fractional one is unsettable.",
         "Quartiles are omitted below n=8.",
         "",
         "A category row appears only where every contributing model declares the",
         "same type and range; the rest are listed as suppressed, because the same",
         "param name carries different units in different models (reverb `Decay` is",
         "a 0..1 knob on HD2 models and SECONDS on VIC ones). Per-model numbers for",
         "those live in `data/factory-corpus.json` under `by_model`.", "",
         "**Known gaps.** `device to-hsp` drops the second model slot of every",
         "two-slot cab block; 48 of those hold `NoCab` and lose nothing, but ~30 real",
         "second cabs are missing (bead hgc-q38). Rows are BASE values — snapshot",
         "arrays are ignored here, and `amp Drive` alone is snapshot-modulated on 21",
         "of 60 amps, so a single number can be one end of a designed range.",
         "Infrastructure blocks (inputs, outputs, splits, joins, looper) are excluded.",
         "", f"**Amp model family:** Agoura {c['amp_family_use'].get('Agoura', 0)} vs "
         f"legacy {c['amp_family_use'].get('legacy', 0)} amp instances.", "",
         f"**Blocks per preset:** median {c['blocks_per_preset']['median']:g} "
         f"(min {c['blocks_per_preset']['min']:g}, max {c['blocks_per_preset']['max']:g})", "",
         f"**Named snapshots per preset:** median "
         f"{c['named_snapshots_per_preset']['median']:g} "
         f"(min {c['named_snapshots_per_preset']['min']:g}, "
         f"max {c['named_snapshots_per_preset']['max']:g})", ""]
    for cat, params in KEY.items():
        rows = c["by_category"].get(cat)
        if not rows:
            continue
        L += [f"## {cat}", "",
              "| param | n | at default | median (all) | median (moved) | moved p25-p75 | min..max |",
              "|---|---|---|---|---|---|---|"]
        for p in params:
            d = rows.get(p)
            if not d:
                continue
            mv = d.get("moved")
            iqr = (f"{mv['p25']:g}-{mv['p75']:g}"
                   if mv and "p25" in mv else "-")
            L.append(f"| {p} | {d['n']} | {d['at_default']} | {cell(d)} | "
                     f"{cell(mv)} | {iqr} | {d['min']:g}..{d['max']:g} |")
        L.append("")
        on_rows = [(p, rows[p]["enabled_only"]) for p in params
                   if p in rows and "enabled_only" in rows[p]]
        if on_rows:
            L += ["Blocks that are ON at load (the rest are engaged by a snapshot "
                  "or footswitch):", "",
                  "| param | n on | median (on) |", "|---|---|---|"]
            L += [f"| {p} | {d['n']} | {cell(d)} |" for p, d in on_rows]
            L.append("")
        sup = c["by_category_suppressed"].get(cat, {})
        if sup:
            L += [f"Suppressed in {cat} (unit mixture — see `by_model`): "
                  + ", ".join(f"`{k}`" for k in sorted(sup)), ""]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
