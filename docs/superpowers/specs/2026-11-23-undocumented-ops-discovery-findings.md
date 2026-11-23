# Discovering undocumented Stadium operations — findings (2026-11-23)

**Question that prompted this:** are there operations / features the Helix
Stadium supports that the Stadium Edit app (and helixgen) never use, and how
would we find them?

**Method:** two read-only sweeps against a live **Stadium XL, fw 1.4.1**
(192.168.4.84), driving the installed `helixgen` client under the CLI. Nothing
was written to the device; the active preset (cid 1998) was left as found.

**TL;DR**
- The **property** surface is a goldmine *by design*: the device self-describes
  **457** property defs, of which **297 are absent from** helixgen's curated
  164-key Global-Settings catalog (the two sets overlap on 160 keys; 4 curated
  keys are not among the 457) — including a **readable Matrix
  Mixer** (`server.mixer.state`), a whole `hal.*` analog-I/O layer, drum
  triggers, control-port config, per-preset reference clips, and live XY
  controller state.
- The **command** surface has **no cheap discovery path**. Blind command-name
  probing is a dead end: the device dispatches by **(address + argument
  signature)**, so a *known* verb sent with the wrong args returns the
  **identical** `"… is NOT known!!!"` error as a genuinely unknown address.
  Frida capture (address + signature observed together) stays the only reliable
  method — exactly as `helix-protocol.md` already does for `/doAgenda`.

Two corrections to the authoritative `helix-protocol.md` (in **helixgen-core**)
fall out of this — see §4. The raw artifacts are in the session scratchpad
(`all_property_defs.json`, `unknown_keys.txt`, `cmd_probe_results.json`,
`bin_addrs.txt`) and should be regenerated rather than committed (they are
device- and firmware-specific).

---

## 1. Property sweep — the device describes itself

`/MatchingPropertyDefinitionsGet [reqid, "*"]` returns an `sfdppgsm` blob of
**every** property def the firmware knows — key, display name, type, min/max.
This is the same enumerable surface `helix-protocol.md` §6 notes (it is how
`server.active.preset.id` was originally found); nobody had diffed the **full**
set against the curated catalog.

| | count |
|---|---|
| defs returned (fw 1.4.1) | **457** |
| helixgen curated `global.*` catalog (`device.settings.all_keys()`) | 164 |
| curated keys also present in the device defs | 160 (4 curated keys absent from the 457) |
| **keys NOT in the curated catalog** | **297** |

Breakdown of the 297 by top-level namespace: `global.*` ~225, **`hal.*` 32,
`server.*` 16, `preset.*` 14, `volatile.*` 10** — the non-`global` namespaces
are entirely absent from the Global-Settings surface.

### High-value leads (values below were read live, read-only)

| Key(s) | What it is | Live read |
|---|---|---|
| **`server.mixer.state`** | **The entire Matrix Mixer** as one structured blob — per channel `vol_`/`pan_`/`mute`/`solo`/`src_`/`name`/`enbl` for AUX, Bluetooth, Click, Count, the four Home paths (1A/1B/2A/2B) and the layer mixes | decoded, populated (see §2) |
| `hal.audio.micpreampgain`, `phantompower`, `inputimpedance.1/2`, `groundlift`, `fxsendlevel.1-4`, `qtr/xlroutlevel` | Low-level **analog I/O config** (a whole hardware layer) | `micpreampgain=48`, `phantompower=0` |
| `hal.drumtrigger.sensitivity/threshold.{a-d}`, `hal.controlport.assign/polarity.{a-d}`, `hal.treadle.polarity` | **Drum-trigger + control-port** config on the four jacks | `drumtrigger.threshold.a=0` |
| `preset.clip.filename/path/start/end` | Per-preset **reference audio clip** | filename=`"2 Guitar Rig"` |
| `preset.xyctrl.x/y/rubberband/rbtime` | Live **XY controller** position (distinct from the `helix-protocol.md` §9 "XY-zone storage unresolved" item — that is about where inactive *zone definitions* persist in the saved `_sbepgsm`; reading the live knob position does not resolve it) | `x=0, y=0` |
| `server.floorboard.mode{,.curr,.upper,.lower}` | Physical **footswitch-layout mode** | `mode.curr=4` |
| `volatile.song.tempobpm` | Live song tempo | `120.0` |
| `hal.proxy.*`, `global.proxy.*` | Clone/proxy-device routing | — |

Not everything that is *defined* is *readable over the net*:
`volatile.dev.cpumonitor` (the DSP headroom the editor-parity epic explicitly
wanted) and `volatile.midi.tempobpm` answered `-21 / unavailable` on this
firmware — they likely populate only in a song/USB context or stream rather than
answer a point `get`. As with `dsp.globaleq.*`, **defined ≠ net-readable**;
confirm each lead with a live read before building on it.

---

## 2. The Matrix Mixer *is* a readable property

`server.mixer.state` decodes to a 4CC-keyed map — abbreviated:

```
atto: 3
lmix:
  home:
    chan:
      [0] {name: 'Path 1A', src_: 1, vol_: 0.0, pan_: 0.0, mute: False, solo: False, enbl: -1}
      [1] {name: 'Path 1B', src_: 2, ...}
      [2] {name: 'Path 2A', src_: 3, ...}
      [3] {name: 'Path 2B', src_: 4, ...}
  auxn: {name: 'AUX In',    src_: 19, vol_, pan_, mute, solo, enbl}
  bt__: {name: 'Bluetooth', src_: 18, ...}
  clik: {name: 'Click',     src_: 15, ...}
  cntn: {name: 'Count',     src_: 16, ...}
  ...
```

That is exactly the per-strip **Level / Pan / Mute / Solo** plane that
`helix-protocol.md` §6 ("Matrix Mixer") and §9 declare **"NOT a property… a
hardware-front-panel feature; `device matrix` is a won't-do via the editor
protocol."** The earlier conclusion rested on a glob for `dsp.matrix*` /
`dsp.out*` / `*.pan` / `*.mute`, which returned zero — but the mixer is **not**
per-strip dotted keys, it is **one structured `server.*` property the glob
didn't match.** The **read side demonstrably exists.**

**What this does and does not change:**
- ✅ **Read** of the full monitor mix is available now, over the LAN, no Frida.
- ❓ **Write** is still unproven. The likely path is `/PropertyValueSet
  server.mixer.state` with a variant/structured codec (cf. the Global-EQ
  `dsp.globaleq.*` variant write), but it has not been tested and
  `server.*` may be read-only. A single HW write-capture (or a careful
  scratch-value write + read-back) settles it.
- So **81v.8 is no longer "no surface / won't-do"** — it is "read-ready;
  write path needs one capture." Re-scoped in the parity backlog, not killed.

---

## 3. Command sweep — why blind probing cannot work

Goal: find commands the device honors that the app never sends. I extracted the
app's OSC-address vocabulary from the binary
(`/Applications/Line6/Helix Stadium.app/Contents/MacOS/Helix Stadium`) —
**392** command-shaped `/CamelCase` addresses, of which helixgen references only
35 — then tried to validate which the **device** honors by firing the
read-shaped ones (reqid-only; every mutating/destructive name was filtered out
and never sent).

It does not work, and the reason is the finding:

> **The device dispatches by (address + argument signature), not by address
> alone.** A *known* verb sent with the wrong argument count is rejected with the
> **same** `"Msg dispatch failed: /X is NOT known!!!"` error as a truly unknown
> address.

Proven with verbs we use constantly — same address, right vs. wrong signature:

| Verb | correct signature | reqid-only |
|---|---|---|
| `/GetContentRef` | answers `/GetContentRef` | **"NOT known"** |
| `/PropertyValueGet` | answers `/getPropertyValue` | **"NOT known"** |
| `/GetContainerContents` | answers | **"NOT known"** |

### Consequences
1. **Blind command-name probing is a dead end.** You cannot distinguish "wrong
   address" from "wrong signature," and you cannot know the signature of an
   *undocumented* verb a priori. (My first probe pass even flagged
   `/GetContainerContents` as unknown — a verb used minutes earlier — until the
   signature dependency was found.)
2. **The app binary gives you the *app's* vocabulary, not the *device's*.**
   Commands the device supports but the app never sends live in the **firmware**
   dispatch table, not the app bundle — invisible from the app binary. Finding
   those needs firmware RE, not string extraction.
3. **Frida stays the command-discovery method** (observe address + signature +
   payload together on a real app gesture), exactly as `helix-protocol.md`
   already does for `/doAgenda` and the Command Center.

The 392-string vocabulary is still worth keeping as the candidate list for a
targeted Frida session, but it cannot be LAN-validated into a known/unknown
partition.

---

## 4. Corrections owed to `helix-protocol.md` (helixgen-core, authoritative)

The protocol reference here is a **synced copy** (core is authoritative), so
these land in **helixgen-core** and sync down — not edited in the plugin repo.

1. **Matrix Mixer (§6 "Matrix Mixer", §9 open item).** Replace "NOT a
   property / won't-do via the editor protocol" with: the per-output monitor
   mix is **readable** as the single structured property **`server.mixer.state`**
   (per-channel `vol_`/`pan_`/`mute`/`solo`/`src_`/`name`); the earlier
   `dsp.matrix*`/`dsp.out*` glob missed it because the mixer is one `server.*`
   blob, not per-strip dotted keys. The **write** path remains unproven
   (candidate: `/PropertyValueSet server.mixer.state` variant codec). The
   sibling core spec `docs/superpowers/specs/2026-11-22-matrix-mixer-re-spike.md`
   (helixgen-core) reached the same now-superseded "won't-do" conclusion and
   owes the same correction when this syncs to core.

2. **Command dispatch keying (§6 `/doAgenda` note).** The note
   *"`/error` means unknown verb — the device tolerates a bogus extra arg on a
   known verb, so it is not an arity complaint"* is half right. **Extra** args
   are tolerated, but a **wrong (esp. shorter) argument signature is rejected
   with the identical `"… is NOT known!!!"` error as an unknown address.** The
   device keys dispatch on **(address + arg signature)**. The error-probe method
   is therefore only valid when the correct signature is sent — so it cannot
   discover undocumented verbs blindly; use Frida.

---

## 5. Reproduce

```bash
export HELIXGEN_LIBRARY="$PWD/data/library"   # dev checkout; bundled library
helixgen device discover                      # persist the device address
helixgen device settings list | wc -l         # curated catalog == 164
```

The two sweeps are small ad-hoc scripts over `helixgen.device.client.HelixClient`:
`/MatchingPropertyDefinitionsGet [reqid, "*"]` for the property dump (decode the
`sfdppgsm` blob: 8-byte magic + msgpack, 4CC keys), and a drain-before-send
`_rpc`-level probe for the command experiment. Both are read-only; keep any
write-capable probe to a scratch slot and ask the owner first.
