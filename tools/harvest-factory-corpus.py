#!/usr/bin/env python3
"""Harvest Line 6 factory Stadium presets into a parameter-distribution corpus.

Reads the converted `.hsp` files DIRECTLY (8-byte `rpshnosj` magic + JSON) and
back-fills every param the model declares from helixgen's vendored device defs,
so a knob the designer left alone still counts. That distinction is the whole
point: `helixgen view` omits any param equal to the model default, which makes
its projection a record of *deliberate moves*, not of typical values.

Aggregates by MODEL ID (display names collide: "Mono" and "Stereo" each name six
different models). A category-level roll-up is published only for params whose
type and declared range are identical across every contributing model — the same
param name carries different units in different models (reverb `Decay` is a 0..1
knob on HD2 models and SECONDS on VIC ones; `Level` is dB on some, 0..1 on others).

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
CORE_SRC = Path.home() / "git" / "helixgen-core" / "src"
MIN_N_QUANTILE = 8      # below this, publish n/min/max but no quartiles
HSP_MAGIC = b"rpshnosj"

sys.path.insert(0, str(CORE_SRC))
from helixgen.device import defs           # noqa: E402
try:
    from helixgen.device import modelmap    # noqa: E402
except ImportError:
    modelmap = None

# params that are an enum/index, not a quantity — a median mic is meaningless
CATEGORICAL = {"Mic", "Channel", "Angle", "Polarity", "IrData", "Jack",
               "SyncSelect1", "SyncSelect2", "TempoSync1",
               "TempoSync2", "WaveShape", "VolumeTaper"}


def read_hsp(path: Path):
    raw = path.read_bytes()
    if raw.startswith(HSP_MAGIC):
        raw = raw[len(HSP_MAGIC):]
    return json.loads(raw)


def convert(sbe_dir: Path, hsp_dir: Path):
    """.sbe -> .hsp, KEEPING the warning channel (silence means nothing lost)."""
    hsp_dir.mkdir(parents=True, exist_ok=True)
    ok, failed, warnings = [], [], Counter()
    for sbe in sorted(sbe_dir.glob("*.sbe")):
        out = hsp_dir / (sbe.stem + ".hsp")
        r = subprocess.run(
            ["helixgen", "device", "to-hsp", str(sbe), "-o", str(out),
             "--library", str(LIB), "--no-verify"],
            capture_output=True, text=True, timeout=180)
        if r.returncode != 0 or not out.exists():
            failed.append((sbe.name, (r.stderr or "").strip()[:200]))
            continue
        ok.append(out)
        for line in (r.stderr or "").splitlines():
            if line.startswith("warning:"):
                # collapse "grid slot 7:" style specifics into a class
                warnings[re.sub(r"\b\d+\b", "N", line)] += 1
    return ok, failed, warnings


def category_index():
    """model_id -> category, from the block library (display names collide)."""
    idx = {}
    for cat_dir in (LIB / "blocks").iterdir():
        if cat_dir.is_dir():
            for f in cat_dir.glob("*.json"):
                d = json.loads(f.read_text())
                idx[d.get("model_id")] = (cat_dir.name, d.get("display_name"))
    return idx


def resolve_meta(model_id, _cache={}):
    """Param metadata for a model: exact -> modelmap -> Stereo/Mono sibling."""
    if model_id in _cache:
        return _cache[model_id]
    meta = defs.model_params_for(model_id) or {}
    if not meta and modelmap is not None:
        try:
            alt = modelmap.device_model_id(model_id)
            if alt:
                meta = defs.model_params_for(alt) or {}
        except Exception:
            pass
    if not meta:
        for a, b in (("Stereo", "Mono"), ("Mono", "Stereo")):
            if model_id.endswith(a):
                meta = defs.model_params_for(model_id[: -len(a)] + b) or {}
                if meta:
                    break
    _cache[model_id] = meta
    return meta


def harvest(hsp_files, cat_idx):
    by_model = defaultdict(lambda: defaultdict(list))    # model -> param -> values
    changed = defaultdict(Counter)                       # model -> param -> n moved
    model_use, family_use = Counter(), Counter()
    unresolved = Counter()
    presets = []

    for f in hsp_files:
        d = read_hsp(Path(f))
        preset = d.get("preset") or {}
        nblocks = 0
        for flow in preset.get("flow") or []:
            for key, entry in flow.items():
                if not (isinstance(entry, dict) and key.startswith("b")):
                    continue
                for slot in entry.get("slot") or []:
                    mid = slot.get("model")
                    if not mid:
                        continue
                    cat, disp = cat_idx.get(mid, (None, None))
                    if cat is None:
                        unresolved[mid] += 1
                        continue
                    nblocks += 1
                    model_use[f"{cat}:{mid}"] += 1
                    if cat == "amp":
                        family_use["Agoura" if mid.startswith("Agoura")
                                   else "legacy"] += 1
                    meta = resolve_meta(mid)
                    stored = {k: v.get("value") for k, v in
                              (slot.get("params") or {}).items()
                              if isinstance(v, dict)}
                    # every param the MODEL declares, defaulted when untouched
                    for pname, pmeta in meta.items():
                        val = stored.get(pname, pmeta.get("def"))
                        if isinstance(val, bool) or not isinstance(val, (int, float)):
                            continue
                        by_model[f"{cat}|{mid}"][pname].append(float(val))
                        if pname in stored and stored[pname] != pmeta.get("def"):
                            changed[f"{cat}|{mid}"][pname] += 1
        named = [s for s in (preset.get("snapshots") or [])
                 if isinstance(s, dict) and not re.fullmatch(
                     r"(SNAPSHOT|Snap)\s*\d+", str(s.get("name", "")).strip(), re.I)]
        presets.append({"file": Path(f).name, "blocks": nblocks,
                        "named_snapshots": len(named)})
    return by_model, changed, model_use, family_use, presets, unresolved


def dist(vals, categorical=False):
    vals = sorted(vals)
    n = len(vals)
    out = {"n": n, "min": vals[0], "max": vals[-1]}
    if categorical:
        top = Counter(vals).most_common(4)
        out["mode"] = top[0][0]
        out["frequencies"] = [[v, c] for v, c in top]
        return out
    out["median"] = statistics.median(vals)
    if n >= MIN_N_QUANTILE:
        q = statistics.quantiles(vals, n=4, method="inclusive")
        out["p25"], out["p75"] = q[0], q[2]
    return out


def rollup(by_model, cat_idx):
    """Category-level stats, ONLY where every contributing model agrees on
    type and declared range. Otherwise the pooled number is a unit mixture."""
    pooled = defaultdict(lambda: defaultdict(list))
    shapes = defaultdict(lambda: defaultdict(set))
    for key, params in by_model.items():
        cat, mid = key.split("|", 1)
        meta = resolve_meta(mid)
        for pname, vals in params.items():
            m = meta.get(pname, {})
            shapes[cat][pname].add((m.get("type"), m.get("min"), m.get("max")))
            pooled[cat][pname].extend(vals)
    out, suppressed = {}, {}
    for cat, params in pooled.items():
        for pname, vals in params.items():
            if len(shapes[cat][pname]) > 1:
                suppressed.setdefault(cat, {})[pname] = (
                    f"{len(shapes[cat][pname])} incompatible declared ranges "
                    f"across models — pooled value would be a unit mixture")
                continue
            out.setdefault(cat, {})[pname] = dist(vals, pname in CATEGORICAL)
    return out, suppressed


def fmt(d):
    def g(k):
        v = d.get(k)
        return "-" if v is None else f"{v:g}"
    if "mode" in d:
        freq = ", ".join(f"{v:g}x{c}" for v, c in d["frequencies"][:3])
        return f"| {d['n']} | {g('min')} | {g('max')} | mode {g('mode')} | {freq} |"
    return (f"| {d['n']} | {g('min')} | {g('p25')} | {g('median')} | {g('p75')} | "
            f"{g('max')} |")


def span(d):
    q = (f", p25-p75 {d['p25']:g}-{d['p75']:g}" if "p25" in d else "")
    return f"median {d['median']:g} (min {d['min']:g}, max {d['max']:g}{q}, n={d['n']})"


def dualcab(c):
    return sum(v for k, v in c["conversion_warnings"].items() if "dual-cab" in k)


def render_md(c, cat_idx):
    KEY = {"amp": ["Drive", "Master", "Level", "Hype", "Channel", "Sag", "ZPrePost",
                   "Bass", "Mid", "Treble", "Presence"],
           "cab": ["Distance", "Angle", "Position", "Mic", "HighCut", "LowCut",
                   "Level", "Pan"],
           "drive": ["Gain", "Level", "Tone"],
           "delay": ["Mix", "Feedback", "Time"],
           "reverb": ["Mix", "Decay", "PreDelay"],
           "dynamics": ["Level", "Threshold", "Mix"]}
    L = [f"# Factory preset corpus — {c['presets']} Line 6 Stadium factory presets", "",
         "What Line 6's own preset designers actually do. These distributions are",
         "the reference the tone skill's defaults should sit inside.", "",
         "**Method.** Parsed from the `.hsp` directly, NOT from `helixgen view`.",
         "Every param the model declares is counted, defaulted when the designer",
         "left it alone — `view` omits any param equal to the model default, so a",
         "projection-based corpus silently drops every knob the designer was happy",
         "to leave alone (about half of all values) and reports only deliberate moves.",
         "Aggregated by **model id**: display names collide (`Mono` and `Stereo` each",
         "name six different models).", "",
         "**A category row is published only where every contributing model declares",
         "the same type and range.** The same param name carries different units in",
         "different models — reverb `Decay` is a 0..1 knob on HD2 models and SECONDS",
         "on VIC ones; amp `Level` is dB on Agoura amps and a 0..1 knob elsewhere.",
         "Pooling those would produce a median no amp can take. Suppressed rows are",
         "listed per category; use `data/factory-corpus.json` `by_model` for those.", "",
         "**Quartiles are omitted below n=8** — at n=2 or 3 an IQR is just the data",
         "points wearing a disguise.", "",
         f"**Amp model family:** {c['amp_family_use']} — Agoura is what the factory",
         "presets are built on; the legacy HX models exist for preset compatibility.", "",
         "**Blocks per preset:** " + span(c["blocks_per_preset"]), "",
         "**Named snapshots per preset:** " + span(c["named_snapshots_per_preset"]), "",
         "**Known gaps.** `device to-hsp` drops the B-cab of every dual-cab block "
         f"({dualcab(c)} occurrences here), so the cab rows are the A-mic half "
         "of the truth (bead",
         "hgc-q38). Per-snapshot values are also partly dropped, so these are BASE",
         "values. Infrastructure blocks (inputs, outputs, splits, joins, looper) are",
         "excluded by design.", ""]
    for cat, params in KEY.items():
        if cat not in c["by_category"]:
            continue
        L += [f"## {cat}", "",
              "| param | n | min | p25 | median | p75 | max |",
              "|---|---|---|---|---|---|---|"]
        cats = []
        for p in params:
            d = c["by_category"][cat].get(p)
            if not d:
                continue
            if "mode" in d:
                cats.append((p, d))
            else:
                L.append(f"| {p} {fmt(d)}")
        L.append("")
        if cats:
            L += ["Categorical (an index or a switch — mode, not median):", "",
                  "| param | n | min | max | mode | most common |",
                  "|---|---|---|---|---|---|"]
            L += [f"| {p} {fmt(d)}" for p, d in cats]
            L.append("")
        sup = c["by_category_suppressed"].get(cat, {})
        if sup:
            L += [f"Suppressed in {cat} (unit mixture — see `by_model`): "
                  + ", ".join(f"`{k}`" for k in sorted(sup)), ""]
    return "\n".join(L) + "\n"


def main():
    sbe_dir, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    ok, failed, warnings = convert(sbe_dir, out_dir / "hsp")
    print(f"converted {len(ok)}, failed {len(failed)}")
    for f in failed:
        print("  FAILED", f)

    cat_idx = category_index()
    by_model, changed, model_use, family_use, presets, unresolved = harvest(ok, cat_idx)
    by_cat, suppressed = rollup(by_model, cat_idx)

    corpus = {
        "source": "Line 6 Helix Stadium factory setlist",
        "presets": len(presets),
        "method": ("parsed .hsp directly; every param the model declares is "
                   "counted, defaulted when the designer left it alone"),
        "conversion_warnings": dict(warnings.most_common()),
        "infrastructure_models_skipped": dict(unresolved.most_common()),
        "amp_family_use": dict(family_use),
        "model_use": dict(model_use.most_common()),
        "blocks_per_preset": dist([p["blocks"] for p in presets]),
        "named_snapshots_per_preset": dist([p["named_snapshots"] for p in presets]),
        "by_category": by_cat,
        "by_category_suppressed": suppressed,
        "by_model": {k: {p: dist(v, p in CATEGORICAL) for p, v in sorted(ps.items())}
                     for k, ps in sorted(by_model.items())},
        "params_moved_by_designer": {k: dict(c.most_common())
                                     for k, c in sorted(changed.items())},
    }
    (out_dir / "factory-corpus.json").write_text(json.dumps(corpus, indent=1))
    (out_dir / "factory-corpus.md").write_text(render_md(corpus, cat_idx))
    print(f"models={len(by_model)} unresolved={sum(unresolved.values())} "
          f"warnings={sum(warnings.values())}")
    return corpus


if __name__ == "__main__":
    main()
