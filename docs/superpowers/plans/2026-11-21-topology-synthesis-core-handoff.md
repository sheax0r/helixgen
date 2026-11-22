# Handoff prompt — helixgen-core topology-synthesis epic

> **CORRECTION 2026-11-22 — read before implementing.** A Frida capture of the
> Stadium app's own traffic disproved this document's "live whole-buffer SET"
> mechanism: that verb does not exist. **Live** topology edits are a
> **`/doAgenda` op-transaction** (`movb` / `swap` / `setm` / `spld` / `jono` /
> `clrb`); the whole-buffer `/setEditBuffer` the spike saw is the device's 2001
> *echo*. What changes here:
> - Do not pin or implement a whole-buffer SET RPC; the live push emits a
>   `/doAgenda` op-list. Reasoning built on "a push replaces the entire buffer"
>   (concurrency, undo) needs redoing for op-transactions, not word substitution.
> - Do not implement `/ClearBlock` — `/clearBlock` is an echo; clear is a `clrb` op.
> - Dual cab's second cab is confirmed: a plain `/ModelSet` with `subpos = 1`.
> - **Unchanged:** the byte-faithful `_sbepgsm` encoder and the `.hsp`
>   harness/branch modelling are still needed for Save and library round-trip.
>
> Facts: [`docs/helix-protocol.md`](../../helix-protocol.md) → "Structural edits —
> `/doAgenda` op-transactions".

Give the block below to a new agent working in **helixgen-core**. Tasks 1–2 need
the owner's **Stadium XL on the LAN + the Helix Stadium app**, so run them on the
owner's machine (where this plugin checkout and the design doc are readable at the
paths cited); the pure-engine modelling (once decoded) can run anywhere.

---

You are implementing the **engine topology-synthesis** epic in **helixgen-core**
(`github.com/sheax0r/helixgen-core`, Python package `helixgen`). This is the engine
prerequisite the `device live` signal-flow editor (`helixgen-81v.1`) is gated on:
helixgen can *preserve* an existing routing topology but can't *synthesize* new
routing (split/merge, parallel lane, dual-cab 2nd slot, mono→stereo). Build that.

**Read first (same machine, plugin checkout):**
- `/Users/michael.shea/git/helixgen/docs/superpowers/specs/2026-11-21-topology-synthesis-engine-design.md`
  — the full design (goals, approach, acceptance, capture recipe). Authoritative.
- `/Users/michael.shea/git/helixgen/docs/superpowers/specs/2026-11-21-signalflow-editor-parity-design.md`
  §2, §8.6 — why this is engine-first and what the UI will consume.
- In helixgen-core: `docs/helix-protocol.md` §4 (content encodings), §6 (`/ModelSet`
  cascade, live edit verbs), §9 (known-unknowns incl. the `hrns` "main lift").

**What the 2026-11-21 spike already settled (don't re-derive):**
- Topology is pushed to the device as a **whole-buffer replace** — one
  `/setEditBuffer`, in place, **no reload** — not a granular opcode. A live
  whole-buffer SET path exists; its 2002 command verb is still unpinned.
- Routing representation (decoded first-pass, `sfg_.flow[dsp]`): grid order =
  `bmap` (index→slot) + `bcnt`; branching = per-block `hasb`/`bflw`/`bblk`; each
  block has an always-present `hrns` harness dict (harness-type `id__` + harness
  `parm`s like Trails/Amp>Cab Link), distinct from the specific model in `mdls`.
  Synthesis must emit all of these device-native; the `.hsp` already carries
  `xbranch` for round-trip, but *generating* new branches is unmodeled.

**First tasks, in order (design §9):**
1. **Pin the whole-buffer-SET 2002 verb** (keystone). MITM the app↔device 2002
   socket during a move/split, or probe the write-twin of `/EditBufferStateGet`
   (send a known-good `_sbepgsm`, confirm `/setEditBuffer` echo with no
   `/loadContentRef`). Confirm `/ClearBlock` and dual-cab `subpos`/`mdls[1]` the
   same way.
2. **Finish the lane/split decode** by before/after diff: in the app, take a series
   preset → add one split (also → dual-cab, → mono/stereo widen); `helixgen device
   pull <cid> out.sbe` + `helixgen device decode out.sbe` before/after; diff the
   `sfg_.flow[dsp]` region. Isolate how A/B lanes + split/merge blocks are encoded.
3. **Model the harness** (`hrns` params, branch pointers, lane structure) as
   first-class round-trip-preserving fields in the `_sbepgsm`↔`.hsp` bridge.
4. **Synthesis ops** in `mutate`/patch: add/remove split, add parallel lane, set
   dual-cab, convert mono↔stereo, move block (bmap rewrite) — each emits
   device-native wiring and defaults `hrns` like the add-block cascade.
5. **Device client:** add the whole-buffer SET RPC + `/ClearBlock`.
6. **CLI verbs** with `--help` behavioral contracts (parity-pinned); **sync docs**
   (`helix-protocol.md`, `CLI.md`, `recipe-reference.md`); **HW-validate on the
   Stadium XL**; then the plugin repo bumps its engine pin + ships the companion
   skills/docs PR.

**Guardrails (project CLAUDE.md):** work in a git worktree branched from fresh
`origin/main`; the export round-trip net (`tests/`) is the fidelity gate — a
synthesized topology must round-trip byte-faithfully; dispatch an adversarial
review subagent before merge; emit the device's own `hrns`/`bmap`/`hasb`-`bflw`-
`bblk` wiring, never a helixgen-only routing abstraction; prefer PostgreSQL/stdlib
per the global rules; don't edit `gen/`.

**Done when:** the engine authors a flat series chain up to multi-lane parallel +
dual-cab + stereo blocks entirely offline, it loads/plays on a real Stadium XL and
round-trips `.hsp`↔device byte-faithfully, and `device live` can push a synthesized
topology live (whole-buffer SET, no reload). File the work as a core epic;
`helixgen-81v.1` (plugin) depends on it.

**Capture recipe:** `HELIXGEN_LIBRARY` must point at a populated block library
(plugin `data/library` or `~/.helixgen/library`) or `list-blocks` silently returns
empty. `device watch --seconds N` streams 2001/2003 — `grep -v dspEvent` to cut
telemetry. USB-originated app edits **do** echo on network 2001.
