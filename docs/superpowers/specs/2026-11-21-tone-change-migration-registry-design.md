# Tone change-migration registry + provenance — design

**Date:** 2026-11-21
**Status:** design, pending approval
**Repos:** primarily `helixgen-core` (engine behavior); companion PR in this repo (skills + synced docs)

## Intent / why

When core fixes a bug or changes a protocol, tones authored by an older engine
can be subtly wrong — and today nothing tells you *which* of your tones are
affected, or repairs them. The 2026-11-21 library fix-up (the pasted agent
report, reproduced at the end) is the evidence: a human-driven run that found
affected tones by scripting, source-diving `mutate.wire_footswitch`, and
guessing counts — breaking the skills' own "work through the CLI, never parse
`.hsp`, never read engine source" rules. Its shortcoming #1 is the whole thesis:
*the 0.84 bypass fix shipped no migration verb, so there was no sanctioned way
to apply it.*

Two goals come out of that:

1. Make **"is my library stale, and fix it"** a built-in, consent-gated,
   mostly-automatic capability that works for *any* helixgen user without a
   bespoke agent session in this project.
2. Stop throwing away the **intent and recipe** behind each tone, so repair,
   regeneration, and future edits don't re-derive what we already knew.

## Goals

- Every tone-affecting core change ships, **in the same release**, a registry
  entry that can *detect* affected tones and *repair* them in place,
  idempotently. This is a release-discipline rule, not just code.
- A single umbrella verb (`library upgrade`) scans the managed tone library,
  reports **exact** per-change affected counts (never estimates), dry-runs, and
  applies **only on `--apply`**. Never auto-applies.
- `setup` automatically runs the scan **read-only** and tells the user how many
  tones are affected by changes since they were authored, pointing at the fix.
  No chat required; it asks, it does not apply.
- The registry doubles as the human **"what changed between versions"**
  changelog (`helixgen changes [--since V]`) — the same artifact, two uses.
- Each authored tone stores **provenance**: a prompt/intent summary, a
  generation-research summary, the **recipe** (`spec.json`) that produced it,
  and the engine + plugin versions. Lives in the existing per-tone library JSON.

## Non-goals / anti-goals

- **Not regeneration-first.** The stored recipe makes deterministic
  regeneration possible (re-run `generate` on it), but that stays an opt-in
  per-tone action, not the migration mechanism. Regeneration itself is **not
  built in this work** — only unblocked.
- **Not auto-apply.** The engine proposes; the user disposes. *Anti-goal:* any
  path that mutates tones — or the device — without explicit consent.
- **Not changing a tone's sound silently.** Superseded-model conversion stays
  manual (as `library audit` already is); the registry is for correctness/
  protocol fixes, not voicing changes.
- **Not device-side.** This repairs library `.hsp`s. Re-pushing to hardware and
  HW validation stay with the `device` skill. The report's device read-back /
  HW-validation / IR-MD5 gaps are out of scope here.
- **Not a fix for the unrelated engine CLI gaps** the report hit (shortcomings
  #2–#4: `set-footswitch` last-wins / can't target an input block, `add-block`
  placement vs the USB tap). Logged separately. The registry sidesteps them by
  having migrations operate through engine read/write helpers, not by
  re-running fragile CLI verbs.

## Constraints

- Lives in **core**; agent-facing surfaces ship in sync — a companion PR here
  updates `skills/*` + synced `docs/` (`CLI.md`), cross-referenced.
- `.hsp` stays canonical for preset **data**. Provenance goes in the existing
  `library/tones/*.json` logical-tone record, the same layer that already holds
  `forked_from`, `normalized`, tags, and `description_md`. No new sidecar.
- **Corpus** = the managed tone library (`$HELIXGEN_HOME/library/tones/`),
  identity by `meta.name`. Loose `.hsp` files outside the library are not
  scanned — documented, not solved here.
- **Detectors inspect content**, via engine read helpers — never trust a
  version stamp alone (a stamp is a UX pre-filter, not truth) and never parse
  CLI text output (report #5: `view` renders a path input as dict *or* bare
  string, which made the hand-run miss 2 tones; report #8: `usb-taps --migrate`
  errored off a missing *preference* while the tones' *content* carried taps).
- Existing **auto-commit-before-mutate** posture (gated by `git_commit_tones`)
  applies to `--apply`.
- Verb name: `migrate` is taken (pre-library → library). Use `library upgrade`.

## Approaches considered

**A. Code pairs, surfaced.** Each change ships a detector + in-place migration
(today's `info-backfill` / `venue-retrofit`, made systematic). `library
upgrade` scans → reports → applies on `--apply`; `setup` surfaces it. Simplest
extension of what exists, but "what changed" stays scattered across each verb's
`--help`.

**B. Declarative index over code *(chosen)*.** Same detector+migration code,
but each registers into **one central index** carrying `{id, landed-in-version,
human description + research summary, detector, migration}`. `library upgrade`
and `setup` drive off the index; the *same* index renders the "what changed"
changelog. One place answers both "what changed" and "how to fix it," and the
index **is** the discipline mechanism — the rule "every tone-affecting change
adds an entry" is exactly what shortcoming #1 needed. Costs a thin registration
layer over A.

**C. Regeneration-first.** Store full prompt+recipe, migrate by re-running
generation. The report already killed this as the *primary* path: non-
deterministic, and it re-opens voicing decisions. Kept only as the opt-in
secondary that B's stored recipe unblocks.

**Chosen: B.**

## The design (decided parts)

### Registry entry

A central registry in core. Each entry:

- `id` — stable slug (e.g. `fs-bypass-snapshot-assign`).
- `landed_in` — the engine version the fix shipped in.
- `kind` — `bugfix` | `protocol` | `cosmetic` (drives how loudly `setup`
  surfaces it).
- `description` + `research_summary` — human text; the "why it was needed / what
  it affects / how we detect it" that otherwise gets re-investigated. This is
  the change-side research record.
- `detect(variant) -> affected?` (and which blocks) — content inspection via
  engine read helpers.
- `migrate(variant) -> changed?` — idempotent in-place repair.

**Unit of work (decided).** Detect and migrate operate on each **variant `.hsp`**
— that is where the blocks are and what the report counted ("77 presets / 174
blocks"). The logical tone is a reporting roll-up only. Headline counts show all
three grains, e.g. *"12 tones / 18 variants / 174 blocks affected"* — exact,
never estimated (report #6). `migrate` takes no config; an entry that needs a
value (e.g. `venue-retrofit`'s highcut Hz) reads it from preferences itself, so
`upgrade` carries no per-entry tuning flags. When two entries touch one variant,
apply in ascending `landed_in` order. Each applied migration mirrors
`venue-retrofit`'s side effects: bump `updated`, clear any `normalized` record,
auto-commit (gated) — no setlist-manifest / `preset_name` / device touch.

**Entry discipline (decided).** Every registry entry must be
**content-detectable**. A future tone-affecting change that is *not* content-
detectable is flagged to the author case-by-case rather than shipped as a silent
no-op entry — the one dent in the "every change ships an entry" rule, surfaced
not swallowed.

Existing `info-backfill`, `venue-retrofit`, and `ir-backfill` register their
detect/migrate into the index; the standalone verbs stay as thin delegating
aliases.

### `helixgen library upgrade`

- **default** — scan + report exact per-entry affected counts across the
  library, read-only, exit 0.
- `--dry-run` — per-tone, per-entry plan of what *would* change.
- `--apply` — auto-commit (gated), apply every applicable entry idempotently,
  then re-report. **Dry-run must equal apply**: no false warnings on tones that
  are already up to date (report #7: `venue-retrofit` warned in dry-run on a
  tone it then called up-to-date).
- `--only <id>` / `--since <version>` — subset.
- `--json`.
- **Idempotent**: re-running yields no changes and no warnings on a clean
  library.

### `helixgen changes [--since VERSION] [--json]`

Renders the registry as a human changelog: each tone-affecting change, the
version it landed in, what it affects, and whether a migration exists. This is
the "describe what changed between versions" record the user asked for.

### Provenance (per variant)

Stored on the **variant** record (one `generate` run → one variant `.hsp` → one
recipe + its own engine/plugin versions), e.g.:

```json
"provenance": {
  "prompt_summary": "warm cleanish SRV-style strat lead, slight breakup",
  "research_summary": "picked Agoura clean, parallel mild drive lane to keep ...",
  "recipe": { "...embedded spec.json..." },
  "engine_version": "0.85.0",
  "plugin_version": "5.29.0",
  "authored_at": "2026-11-21T.."
}
```

`generate`'s default (no-`-o`) path writes it. **My call (surface for
confirmation):** embed the **recipe** (the input `spec.json`), not just the
prompt summary — it's cheap, additive, and it is the single thing that turns
regeneration from impossible (report #1) into a later `library regenerate`.
Prompt/research are human-readable *summaries* per the user's ask, not verbatim
transcripts.

### `setup` integration

A `setup` step runs `library upgrade` in report mode (read-only) and tells the
user: *"N tones affected by M known fixes — run `helixgen library upgrade
--apply`, or say the word and I will."* It **asks**; it never applies on its own.
Wording avoids per-tone "since authored" math because the existing library has
no provenance stamps yet (detection is content-based, so it still works). This is
what makes it "just work" for other users without a bespoke chat in this project.

## Report shortcomings — coverage

| # | Report shortcoming | How this design handles it |
|---|---|---|
| 1 | 0.84 bypass fix had no migration verb → source-diving, broke skill rules | **Core thesis.** Registry discipline: the fix ships its entry; `library upgrade` applies it. |
| 2 | `set-footswitch` last-wins; `view` hides curve/threshold → can't re-wire faithfully | Migrations are self-contained in-place transforms, not "re-run `set-footswitch`." Underlying verb gaps logged separately. |
| 3 | `set-footswitch` can't target an input block | Separate engine gap; not this feature. Noted. |
| 4 | `add-block` places before the USB tap (silences USB 5/6) | Separate engine gap; not this feature. Noted. |
| 5 | `view` reports path input as dict *or* string → missed 2 tones | Detectors read via engine helpers, never parse CLI text. |
| 6 | Peer estimate (70/159) low; real 77/174 | Scan-based **exact** counts; estimates never used. |
| 7 | `venue-retrofit` false warning in dry-run on an up-to-date tone | Requirement: accurate, idempotent dry-run == apply; no spurious warnings. |
| 8 | `usb-taps --migrate` errored on missing pref though tones carry taps | Detectors inspect tone **content**, not just preferences. |
| 9 | Dead `~/.helixgen/setlists/manifest.json` with tmp paths | Candidate registry entry (detect+remove stale state) or a one-off cleanup; builder's call. |

Report "Not verified / open" items (HW validation, device read-back, IR MD5,
legacy reverb/amp conversion, duplicate names) are device-side or
voicing-side — out of scope here, handled by the `device` skill / manual audit.

## Decided after builder check (author's / reviewer's calls)

- **Unit of work:** per-variant `.hsp`; counts roll up as tones / variants /
  blocks. (See "Unit of work" above.)
- **Provenance home:** the variant record; recipe embedded.
- **Entry config:** none on `upgrade`; entries read their own values from prefs.
- **Multi-entry order:** ascending `landed_in`.
- **Migration side effects:** bump `updated`, clear `normalized`, gated
  auto-commit; nothing device-side.
- **Existing backfill verbs:** register into the index, keep as thin aliases.
- **Report #9 dead manifest:** a one-off `setup`/cleanup step, not a registry
  entry (not a per-tone content fix).
- **Entry discipline:** every entry content-detectable; non-detectable future
  changes flagged to the author, not shipped as no-ops.
- **Registry shape:** a single core module exposing an ordered list of entries;
  `--only <id>` errors on an unknown id; `changes` defaults to all, `--since`
  subsets by `landed_in`.

## Genuinely left to the builder

- Exact internal registry API and provenance field names (shapes above are
  indicative).
- Deferred, explicitly: `library regenerate` (unblocked by the stored recipe,
  not built); the standalone engine CLI gaps (report #2–#4); device re-push +
  HW validation (the `device` skill's job).

## Appendix: source report (2026-11-21 library fix-up)

> Reproduced verbatim as the empirical basis for this design; see shortcomings
> #1–#9 above. (Full text in the brainstorming thread.)
