# Venue Variants (plugin + library migration) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Teach the `tone` skill about venues, remove doubling guidance, pin the engine release that ships venue support, then migrate the owner's library (doubled presets → headphone room tones).

**Architecture:** Docs-only plugin change plus a one-off, hardware-touching migration run through the shipped CLI. Nothing here is engine code.

**Tech Stack:** Markdown skills, `python3 -m pytest` (skill-doc content checks), `helixgen` CLI.

**Spec:** `docs/superpowers/specs/2026-11-11-venue-variants-design.md`. Engine plan: `helixgen-core` `docs/superpowers/plans/2026-11-12-venue-variants.md`.

## Global Constraints

- **Blocked on the engine release** from the engine plan. Do not start Task 1 until `helixgen --version` on PyPI has `generate --venue`, `library fork --venue` and `library venue`.
- Worktree from fresh `origin/main`; never commit on local `main`; release only by version bump (repo CLAUDE.md). Adversarial review subagent before merge.
- Skills describe CLI behaviour only; verify every command in the new skill text against the released CLI's `--help`.
- The skill never asks about, or offers, propagating a tweak to sibling variants.
- Never commit paid IR packs.

## Review Focus

1. A tone request that names no venue, with `default_venue` unset: the skill must behave exactly as today (no venue talk). Pinned by a content check in Task 1.
2. A user tweak to one variant: skill text must say "that variant only". Pinned in Task 1.
3. Migration on a tone whose plain variant was hand-tuned since the doubled one was made: converting in place must not lose it; `library venue` only adds. Checked by the `view` diff in Task 3.
4. Device unreachable mid-migration: every step is re-runnable; do not delete a doubled preset from the library before its replacement is confirmed on the device. Ordering in Task 3 enforces this.
5. A doubled preset still referenced by another setlist: `device rm --also-pool` refuses; remove the other reference first, report it.

---

### Task 1: `tone` skill — Venue section, doubling removed

**Files:**
- Modify: `skills/tone/SKILL.md`
- Modify: `skills/setup/SKILL.md` (engine pin; `default_venue` onboarding line next to `default_guitar`), `skills/device/SKILL.md` (pin echo), `README.md` (pin)
- Test: `tests/` skill-doc content checks (extend the existing file)

- [ ] **Step 1: Failing content checks**

```python
def test_tone_skill_has_venue_section():
    s = read("skills/tone/SKILL.md")
    for needle in ("## Venue", "default_venue", "generate --venue", "library fork", "library venue",
                   "ROOM MIC", "never a bypass", "minimum-phase", "that variant only"):
        assert needle in s

def test_no_doubling_guidance_remains():
    for f in all_skill_and_doc_files():
        assert "doubled" not in read(f).lower() and "haas" not in read(f).lower()
```

- [ ] **Step 2:** Run `python3 -m pytest -q`; expect the two new checks to fail.
- [ ] **Step 3:** Write the `## Venue` section from the spec's "Skill changes" list, verbatim in substance: why (near-field close mic), when (named → `default_venue` → unspecified; never ask on a routine request; state the venue in one clause in the report), how (author the recipe in direct form, let `generate --venue` transform; never hand-build the split), the ear-language table (five rows in the spec), the "do not" line, the other-venues notes, the sibling rule ("a tweak lands on that variant only; do not offer or ask"). Add three rows to "Common Mistakes" (hand-built room split; bypass-toggling a parallel IR; room stage on a PA-bound tone). Add `venue` to step 7a's description checklist and step 8's report. Delete every doubling reference.
- [ ] **Step 4:** Bump the engine pin everywhere it appears. Run `python3 -m pytest -q`; expect pass.
- [ ] **Step 5:** Commit `skills: venue variants; remove doubling; engine pin X.Y.Z`.

### Task 2: Sync docs and release

- [ ] **Step 1:** Copy `docs/CLI.md` and `docs/recipe-reference.md` from the released core tag.
- [ ] **Step 2:** Bump `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` to the same new version.
- [ ] **Step 3:** PR, adversarial review, merge. Confirm the release workflow tagged and moved `stable`.

### Task 3: Library migration (owner's `~/.helixgen`, hardware at `192.168.4.84`)

Run only after Task 2 and `uv tool install --force 'helixgen[device]==<new>'`. Commit in `~/.helixgen` first so the tree is clean. Use non-activating device verbs only.

- [ ] **Step 1:** Set `"default_venue": "headphones"` in `~/.helixgen/preferences.json`.
- [ ] **Step 2:** Record the hand-built Venom variant: in `library/tones/my-chemical-romance-thank-you-for-the-venom.json`, variant `ibanez-prestige`, set `venue: "headphones"` and `venue_detail` `{"treatment": "room-ir", "room_ir": "24c8d4c338a11b9d200bcc865e6a965d", "room_level_db": -30.0, "room_switch": "FS4", "ambience_block": "Tile", "ambience_switch": "FS5", "fallback_reason": null}`. Verify: `helixgen library venue "My Chemical Romance - Thank You for the Venom - Ibanez Prestige" direct --dry-run` succeeds (proves the detail matches the chain).
- [ ] **Step 3:** For each plain counterpart of a doubled preset **except Venom Ibanez** — Arch Enemy *The World Is Yours* (Ibanez), Avenged Sevenfold *Hail to the King* (Ibanez), Metallica *Master of Puppets* (Ibanez), Muse *Time Is Running Out* (EC-1000, Ibanez), MCR *Thank You for the Venom* (EC-1000), The Sword *Rhythm* (EC-1000, Ibanez), Toadies *Possum Kingdom* (Ibanez):
  1. `helixgen view <plain.hsp>` → save.
  2. `helixgen library venue "<plain preset name>" headphones`. Expect `room-ir`; a `tile` fallback is acceptable but must be listed in the final report with its reason.
  3. `helixgen view` again; the only differences are the room split, room IR, Tile and their two switches.
  4. `helixgen device copy <plain.hsp> --to Mike --ip 192.168.4.84` → expect `updated`.
  5. `helixgen device list-irs --ip 192.168.4.84` shows the room IR.
- [ ] **Step 4:** Only after Step 3 succeeded for a song: `helixgen device rm "<doubled preset name>" --from Mike --also-pool --yes --ip 192.168.4.84` (device names carry `DOUBLED`; take exact names from `device list --setlist Mike`), then `git rm` its `.hsp`; remove the `...-doubled.json` metadata once all its variants are gone. Includes both doubled Venom presets.
- [ ] **Step 5:** `helixgen library validate`; `ls ~/.helixgen/library/tones | grep -i doubled` prints nothing; `device list --setlist Mike | grep -i doubled` prints nothing. Commit in `~/.helixgen`: `tone: replace doubled presets with headphone room variants`.
- [ ] **Step 6:** In `~/git/guitar-training`: replace `tools/band-variant.py` usage with `helixgen library fork <tone> --venue amp-in` in `CLAUDE.md` / memory notes and delete the script; delete the doubled-technique memory note; note `default_venue` in the "Helix tones" section. Commit `tools: retire band-variant.py and doubling in favour of helixgen venues`. Existing `<slug>-amp-in` tones are left as they are.
